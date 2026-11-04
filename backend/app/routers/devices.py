"""Attendance device registration, enrollment code lifecycle, and device management."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import STAFF_ROLES, VIEWER_ROLES, check_scope
from ..models import (
    AttendanceDevice,
    Branch,
    Camera,
    CameraAssurance,
    CameraDirection,
    CameraSourceType,
    DeviceEnrollmentCode,
    DeviceMode,
    DeviceStatus,
    Role,
)
from ..rate_limiter import check_rate_limit
from ..schemas import (
    AttendanceDeviceOut,
    CameraCreate,
    CameraOut,
    CameraUpdate,
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    DeviceEnrollmentCodeRequest,
    DeviceEnrollmentCodeResponse,
    DeviceUpdateRequest,
)
from ..security import (
    AppError,
    Principal,
    create_device_access_token,
    record_audit,
    require_roles,
    tenant_scope,
)

router = APIRouter()

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _device_out(device: AttendanceDevice) -> AttendanceDeviceOut:
    return AttendanceDeviceOut(
        id=device.id,
        organization_id=device.organization_id,
        name=device.name,
        branch_id=device.branch_id,
        mode=device.mode,
        status=device.status,
        registered_by=device.registered_by,
        last_seen_at=device.last_seen_at,
        revoked_at=device.revoked_at,
        created_at=device.created_at,
    )


def _camera_out(cam: Camera) -> CameraOut:
    return CameraOut(
        id=cam.id,
        organization_id=cam.organization_id,
        source_type=cam.source_type,
        device_id=cam.device_id,
        name=cam.name,
        branch_id=cam.branch_id,
        direction=cam.direction,
        assurance=cam.assurance,
        enabled=cam.enabled,
        last_seen_at=cam.last_seen_at,
        created_at=cam.created_at,
    )


@router.post("/devices/enrollment-code", response_model=DeviceEnrollmentCodeResponse, status_code=201)
def create_enrollment_code(
    payload: DeviceEnrollmentCodeRequest = DeviceEnrollmentCodeRequest(),
    request: Request = None,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> DeviceEnrollmentCodeResponse:
    """Issues a 6-character, 10-minute single-use code to register a physical kiosk device."""
    check_scope(principal, branch_id=payload.branch_id)

    if payload.branch_id:
        branch = db.scalar(
            select(Branch).where(
                Branch.id == payload.branch_id,
                Branch.organization_id == principal.organization_id,
            )
        )
        if branch is None:
            raise AppError("NOT_FOUND", "Branch not found.", 404)

    raw_code = _generate_code(6)
    code_hash = _hash_code(raw_code)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)

    device_name = (payload.device_name or "").strip() or "Attendance Kiosk"
    record = DeviceEnrollmentCode(
        organization_id=principal.organization_id,
        code_hash=code_hash,
        created_by_user_id=principal.user_id,
        device_name=device_name,
        branch_id=payload.branch_id,
        mode=payload.mode,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()

    record_audit(
        db,
        action="device.code_issued",
        principal=principal,
        target_type="device_enrollment_code",
        target_id=record.id,
        request=request,
        device_name=device_name or "",
        mode=payload.mode.value,
    )
    db.commit()

    return DeviceEnrollmentCodeResponse(
        code=raw_code,
        expires_at=expires_at,
        device_name=device_name,
        mode=payload.mode,
    )


@router.post("/devices/enroll", response_model=DeviceEnrollResponse)
def enroll_device(
    payload: DeviceEnrollRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> DeviceEnrollResponse:
    """Exchanges an active enrollment code for a long-lived, revocable ATTENDANCE_DEVICE credential."""
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"device_enroll:{client_ip}", max_attempts=10, window_seconds=60)

    code_hash = _hash_code(payload.code)
    record = db.scalar(
        select(DeviceEnrollmentCode).where(DeviceEnrollmentCode.code_hash == code_hash)
    )

    now = datetime.now(timezone.utc)
    if (
        record is None
        or record.used_at is not None
        or record.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise AppError("CODE_INVALID_OR_EXPIRED", "Invalid or expired enrollment code.", 400)

    record.used_at = now

    device_name = (payload.name or "").strip() or record.device_name or "Attendance Kiosk"
    device = AttendanceDevice(
        organization_id=record.organization_id,
        name=device_name,
        branch_id=record.branch_id,
        mode=record.mode,
        status=DeviceStatus.ACTIVE,
        registered_by=record.created_by_user_id,
        last_seen_at=now,
    )
    db.add(device)
    db.flush()

    camera = Camera(
        organization_id=device.organization_id,
        device_id=device.id,
        name=f"{device.name} Camera",
        source_type=CameraSourceType.ANDROID_KIOSK,
        branch_id=device.branch_id,
        direction=CameraDirection(device.mode.value),
        assurance=CameraAssurance.HIGH,
        enabled=True,
        last_seen_at=now,
    )
    db.add(camera)
    db.flush()

    record_audit(
        db,
        action="device.enrolled",
        organization_id=device.organization_id,
        target_type="device",
        target_id=device.id,
        request=request,
        name=device.name,
        mode=device.mode.value,
    )

    access_token = create_device_access_token(device)
    db.commit()

    return DeviceEnrollResponse(
        device_id=device.id,
        organization_id=device.organization_id,
        name=device.name,
        mode=device.mode,
        access_token=access_token,
        token_type="bearer",
    )


@router.get("/devices", response_model=list[AttendanceDeviceOut])
def list_devices(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[AttendanceDeviceOut]:
    """Lists registered devices for this organization, scoped by branch for HR/managers."""
    query = select(AttendanceDevice).where(
        AttendanceDevice.organization_id == principal.organization_id
    )

    if principal.branch_id is not None:
        query = query.where(AttendanceDevice.branch_id == principal.branch_id)

    devices = db.scalars(query.order_by(AttendanceDevice.name)).all()
    return [_device_out(device) for device in devices]


@router.patch("/devices/{device_id}", response_model=AttendanceDeviceOut)
def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> AttendanceDeviceOut:
    """Updates device name, assigned branch, or operating mode (AUTO, IN_ONLY, OUT_ONLY)."""
    device = db.scalar(
        select(AttendanceDevice).where(
            AttendanceDevice.id == device_id,
            AttendanceDevice.organization_id == principal.organization_id,
        )
    )
    if device is None:
        raise AppError("NOT_FOUND", "Device not found.", 404)

    check_scope(principal, branch_id=device.branch_id)
    if payload.branch_id is not None:
        check_scope(principal, branch_id=payload.branch_id)

    if payload.name is not None:
        device.name = payload.name.strip()
    if payload.branch_id is not None:
        device.branch_id = payload.branch_id
    if payload.mode is not None:
        device.mode = payload.mode
        record_audit(
            db,
            action="device.mode_changed",
            principal=principal,
            target_type="device",
            target_id=device.id,
            request=request,
            new_mode=payload.mode.value,
        )

    db.commit()
    return _device_out(device)


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    """Immediately revokes an attendance kiosk. Its credential will fail with DEVICE_NOT_AUTHORIZED."""
    device = db.scalar(
        select(AttendanceDevice).where(
            AttendanceDevice.id == device_id,
            AttendanceDevice.organization_id == principal.organization_id,
        )
    )
    if device is None:
        raise AppError("NOT_FOUND", "Device not found.", 404)

    check_scope(principal, branch_id=device.branch_id)

    now = datetime.now(timezone.utc)
    device.status = DeviceStatus.REVOKED
    device.revoked_at = now

    record_audit(
        db,
        action="device.revoked",
        principal=principal,
        target_type="device",
        target_id=device.id,
        request=request,
    )
    db.commit()

    return {"device_id": device.id, "revoked": True, "status": device.status.value}


# ---------------------------------------------------------------------------
# Camera Management (Camera-Independent Architecture)
# ---------------------------------------------------------------------------

@router.get("/cameras", response_model=list[CameraOut])
def list_cameras(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[CameraOut]:
    """Lists cameras for the organization, scoped to branch if manager/HR."""
    query = select(Camera).where(Camera.organization_id == principal.organization_id)
    if principal.branch_id is not None:
        query = query.where(Camera.branch_id == principal.branch_id)
    cameras = db.scalars(query.order_by(Camera.name)).all()
    return [_camera_out(c) for c in cameras]


@router.post("/cameras", response_model=CameraOut, status_code=201)
def create_camera(
    payload: CameraCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> CameraOut:
    """Registers a new camera associated with an existing device."""
    check_scope(principal, branch_id=payload.branch_id)

    device = db.scalar(
        select(AttendanceDevice).where(
            AttendanceDevice.id == payload.device_id,
            AttendanceDevice.organization_id == principal.organization_id,
        )
    )
    if device is None:
        raise AppError("NOT_FOUND", "Device not found for camera association.", 404)

    camera = Camera(
        organization_id=principal.organization_id,
        device_id=device.id,
        name=payload.name.strip(),
        source_type=payload.source_type,
        branch_id=payload.branch_id or device.branch_id,
        direction=payload.direction,
        assurance=payload.assurance,
        enabled=True,
    )
    db.add(camera)
    db.flush()

    record_audit(
        db,
        action="camera.created",
        principal=principal,
        target_type="camera",
        target_id=camera.id,
        request=request,
        name=camera.name,
        device_id=camera.device_id,
    )
    db.commit()
    return _camera_out(camera)


@router.patch("/cameras/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> CameraOut:
    """Updates camera parameters (direction, assurance, branch, enabled)."""
    camera = db.scalar(
        select(Camera).where(
            Camera.id == camera_id,
            Camera.organization_id == principal.organization_id,
        )
    )
    if camera is None:
        raise AppError("NOT_FOUND", "Camera not found.", 404)

    check_scope(principal, branch_id=camera.branch_id)
    if payload.branch_id is not None:
        check_scope(principal, branch_id=payload.branch_id)
        camera.branch_id = payload.branch_id

    if payload.name is not None:
        camera.name = payload.name.strip()
    if payload.direction is not None:
        camera.direction = payload.direction
    if payload.assurance is not None:
        camera.assurance = payload.assurance
    if payload.enabled is not None:
        camera.enabled = payload.enabled

    record_audit(
        db,
        action="camera.updated",
        principal=principal,
        target_type="camera",
        target_id=camera.id,
        request=request,
    )
    db.commit()
    return _camera_out(camera)

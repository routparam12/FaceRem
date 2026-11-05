"""Recognition scans, the records they produce, PIN fallback, and attendance history."""

from datetime import date, datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..attendance_service import (
    confirm_provisional_event,
    process_face_observation,
    process_pin_attendance,
    undo_last_event,
    void_event_admin,
)
from ..config import get_settings
from ..db import get_db
from ..deps import SCANNER_ROLES, STAFF_ROLES, VIEWER_ROLES, enrolled_ids, read_image
from ..face import embed_async, find_best_match, get_engine
from ..liveness import LivenessResult, get_liveness_service
from ..models import (
    AttendanceDevice,
    AttendanceEvent,
    AttendanceRecord,
    AttendanceStatus,
    DeviceStatus,
    AuditLog,
    Camera,
    CameraAssurance,
    CameraDirection,
    Employee,
    Organization,
    Role,
    Shift,
)
from ..rate_limiter import check_rate_limit
from ..schemas import (
    AttendanceEventOut,
    AttendanceOut,
    AttentionItem,
    AuditLogOut,
    DashboardResponse,
    FaceObservation,
    LivenessChallengeResponse,
    ObservationResult,
    PinVerifyRequest,
    PinVerifyResponse,
    RecognizeResponse,
    UndoRequest,
    UndoResponse,
    VoidEventRequest,
)
from ..security import (
    AppError,
    Principal,
    get_principal,
    record_audit,
    require_roles,
    tenant_scope,
    verify_password,
)

settings = get_settings()
router = APIRouter()


@router.post("/attendance/challenge", response_model=LivenessChallengeResponse)
def get_challenge(
    request: Request,
    principal: Principal = Depends(require_roles(*SCANNER_ROLES)),
    _: Principal = Depends(tenant_scope),
) -> LivenessChallengeResponse:
    """Issues an active challenge sequence with a short-lived nonce for kiosk scan verification."""
    challenge = get_liveness_service().create_challenge(
        device_id=principal.user_id,
        organization_id=principal.organization_id,
    )
    return LivenessChallengeResponse(
        challenge_id=challenge.challenge_id,
        nonce=challenge.nonce,
        actions=challenge.actions,
        expires_at=challenge.expires_at,
    )


@router.post("/attendance/recognize", response_model=RecognizeResponse)
async def recognize(
    request: Request,
    image: UploadFile = File(...),
    challenge_id: str | None = Form(default=None),
    nonce: str | None = Form(default=None),
    burst: list[UploadFile] = File(default=[]),
    device_label: str = Form(default=""),
    camera_id: str | None = Form(default=None),
    liveness_score: float | None = Form(default=None),  # ignored legacy client score
    principal: Principal = Depends(require_roles(*SCANNER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> RecognizeResponse:
    """
    Thin adapter over process_face_observation for camera-independent attendance recognition.
    """
    organization_id = principal.organization_id
    image_bytes = await read_image(image)

    # 1. Resolve camera
    camera = None
    if camera_id:
        camera = db.scalar(
            select(Camera).where(Camera.id == camera_id, Camera.organization_id == organization_id)
        )
    if camera is None:
        camera = db.scalar(
            select(Camera).where(Camera.device_id == principal.user_id, Camera.organization_id == organization_id)
        )
    if camera is None:
        # Fallback for devices without camera row: auto-provision default camera
        dev = db.get(AttendanceDevice, principal.user_id)
        dev_name = dev.name if dev else (device_label or "Attendance Kiosk")
        branch_id = dev.branch_id if dev else None
        dev_mode = dev.mode.value if dev else "AUTO"
        camera = Camera(
            organization_id=organization_id,
            device_id=principal.user_id,
            name=f"{dev_name} Camera",
            branch_id=branch_id,
            direction=CameraDirection(dev_mode) if dev_mode in CameraDirection.__members__ else CameraDirection.AUTO,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        db.add(camera)
        db.flush()

    # 2. Extract burst frames and verify liveness
    liveness_evidence = None
    if settings.liveness_mode == "disabled":
        liveness_evidence = {"passed": True, "score": 1.0, "provider": "disabled"}
    elif challenge_id:
        burst_files = list(burst)
        if not burst_files:
            form = await request.form()
            for key in ("burst_frames", "burst[]", "frames"):
                candidate = form.getlist(key)
                if candidate:
                    burst_files = [f for f in candidate if isinstance(f, (UploadFile, StarletteUploadFile))]
                    break

        burst_bytes: list[bytes] = []
        for b_file in burst_files:
            burst_bytes.append(await read_image(b_file))

        embedding = await embed_async(image_bytes)
        liveness = get_liveness_service().verify_challenge(
            challenge_id=challenge_id or "",
            nonce=nonce or "",
            device_id=principal.user_id,
            organization_id=organization_id,
            burst_frames=burst_bytes,
            primary_vector=embedding.vector,
            tracking_bbox=embedding.bbox,
        )
        get_liveness_service().verify_passive(image_bytes)
        liveness_evidence = {
            "passed": liveness.passed,
            "score": liveness.score,
            "provider": liveness.provider,
        }

    observation_id = challenge_id or str(uuid.uuid4())
    observation = FaceObservation(
        observation_id=observation_id,
        camera_id=camera.id,
        captured_at=datetime.now(timezone.utc),
        image=image_bytes,
        liveness_evidence=liveness_evidence,
    )

    result = await process_face_observation(
        db=db,
        organization_id=organization_id,
        observation=observation,
        principal=principal,
    )

    return RecognizeResponse(
        employee_id=result.employee_id,
        employee_code=result.employee_code,
        full_name=result.full_name,
        department=result.department,
        event=result.event,
        recorded_at=result.recorded_at,
        status=result.status,
        late_minutes=result.late_minutes,
        match_confidence=result.match_confidence,
        liveness_score=result.liveness_score,
        check_in_at=result.check_in_at,
        check_out_at=result.check_out_at,
        undo_token=result.undo_token,
        provisional=result.provisional,
        event_id=result.event_id,
    )


@router.post("/attendance/scan", response_model=ObservationResult)
async def scan_observation(
    observation: FaceObservation,
    principal: Principal = Depends(require_roles(*SCANNER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> ObservationResult:
    """Camera-independent attendance scan endpoint consuming a FaceObservation."""
    return await process_face_observation(
        db=db,
        organization_id=principal.organization_id,
        observation=observation,
        principal=principal,
        raise_on_cooldown=True,
    )


@router.post("/attendance/undo", response_model=UndoResponse)
def undo_attendance(
    payload: UndoRequest,
    principal: Principal = Depends(require_roles(*SCANNER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> UndoResponse:
    """Voids the last recorded event inside the 30-second window."""
    event_id = undo_last_event(db, principal.organization_id, payload.undo_token, principal)
    return UndoResponse(
        success=True,
        event_id=event_id,
        message="Attendance event successfully undone.",
    )


@router.post("/attendance/events/{event_id}/void")
def void_event(
    event_id: str,
    payload: VoidEventRequest,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
):
    """Admin/HR operation: voids an attendance event with audit trail."""
    voided_id = void_event_admin(db, principal.organization_id, event_id, payload.reason, principal)
    return {"success": True, "voided_event_id": voided_id}


@router.post("/attendance/events/{event_id}/confirm", response_model=AttendanceEventOut)
def confirm_event(
    event_id: str,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> AttendanceEventOut:
    """Admin/HR operation: confirms a provisional event, promoting it to the daily AttendanceRecord."""
    event = confirm_provisional_event(db, principal.organization_id, event_id, principal)
    emp = db.get(Employee, event.employee_id)
    return AttendanceEventOut(
        id=event.id,
        organization_id=event.organization_id,
        employee_id=event.employee_id,
        employee_name=emp.full_name if emp else None,
        device_id=event.device_id,
        camera_id=event.camera_id,
        source_type=event.source_type,
        type=event.type,
        occurred_at=event.occurred_at,
        confidence=event.confidence,
        method=event.method,
        idempotency_key=event.idempotency_key,
        provisional=event.provisional,
        voided_at=event.voided_at,
        void_reason=event.void_reason,
    )


@router.get("/attendance/events", response_model=list[AttendanceEventOut])
def list_attendance_events(
    limit: int = 50,
    employee_id: str | None = None,
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[AttendanceEventOut]:
    """Lists immutable attendance events, scoped by role and branch/department."""
    query = (
        select(AttendanceEvent, Employee)
        .join(Employee, Employee.id == AttendanceEvent.employee_id)
        .where(AttendanceEvent.organization_id == principal.organization_id)
    )
    if employee_id:
        query = query.where(AttendanceEvent.employee_id == employee_id)
    if principal.branch_id is not None:
        query = query.where(Employee.branch_id == principal.branch_id)
    if principal.department_id is not None:
        query = query.where(Employee.department_id == principal.department_id)

    rows = db.execute(query.order_by(AttendanceEvent.occurred_at.desc()).limit(limit)).all()
    return [
        AttendanceEventOut(
            id=ev.id,
            organization_id=ev.organization_id,
            employee_id=ev.employee_id,
            employee_name=emp.full_name,
            device_id=ev.device_id,
            camera_id=ev.camera_id,
            source_type=ev.source_type,
            type=ev.type,
            occurred_at=ev.occurred_at,
            confidence=ev.confidence,
            method=ev.method,
            idempotency_key=ev.idempotency_key,
            provisional=ev.provisional,
            voided_at=ev.voided_at,
            void_reason=ev.void_reason,
        )
        for ev, emp in rows
    ]


@router.post("/attendance/pin-verify", response_model=PinVerifyResponse)
def pin_verify(
    payload: PinVerifyRequest,
    request: Request,
    principal: Principal = Depends(require_roles(Role.ATTENDANCE_DEVICE)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> PinVerifyResponse:
    """Verifies employee_code + PIN fallback from a registered kiosk. Does NOT record attendance in Phase 2."""
    client_ip = request.client.host if request.client else "unknown"
    # Dual rate limiting: per-IP and per-device to prevent distributed or single-device lockout attacks
    check_rate_limit(f"pin_verify:ip:{client_ip}", max_attempts=15, window_seconds=60)
    check_rate_limit(f"pin_verify:device:{principal.user_id}", max_attempts=15, window_seconds=60)

    employee = db.scalar(
        select(Employee).where(
            Employee.organization_id == principal.organization_id,
            func.lower(Employee.employee_code) == payload.employee_code.strip().lower(),
            Employee.is_active.is_(True),
        )
    )

    now = datetime.now(timezone.utc)
    # Generic error for unknown code or unconfigured PIN to prevent account enumeration
    if employee is None:
        raise AppError("INVALID_CREDENTIALS", "Invalid employee code or PIN.", 401)

    locked_until = employee.pin_locked_until
    if locked_until is not None:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise AppError("PIN_LOCKED", "PIN entry is locked due to too many failed attempts. Try again later.", 423)

    if not employee.pin_hash or not verify_password(payload.pin, employee.pin_hash):
        employee.failed_pin_attempts += 1
        if employee.failed_pin_attempts >= 5:
            employee.pin_locked_until = now + timedelta(minutes=15)
            record_audit(
                db,
                action="auth.pin_lockout",
                principal=principal,
                target_type="employee",
                target_id=employee.id,
                request=request,
            )
        db.commit()
        raise AppError("INVALID_CREDENTIALS", "Invalid employee code or PIN.", 401)

    # Success: reset failed attempt counter and lockout
    employee.failed_pin_attempts = 0
    employee.pin_locked_until = None
    db.commit()

    # Look up or provision default camera for kiosk device
    camera = db.scalar(
        select(Camera).where(
            Camera.organization_id == principal.organization_id,
            Camera.device_id == principal.user_id,
            Camera.enabled.is_(True),
        )
    )
    if camera is None:
        device = db.get(AttendanceDevice, principal.user_id)
        dev_name = device.name if device else "Kiosk"
        dev_mode = device.mode.value if device and hasattr(device.mode, "value") else "AUTO"
        camera = Camera(
            organization_id=principal.organization_id,
            device_id=principal.user_id,
            name=f"{dev_name} Camera",
            direction=CameraDirection(dev_mode) if dev_mode in CameraDirection.__members__ else CameraDirection.AUTO,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        db.add(camera)
        db.flush()

    att_result = process_pin_attendance(
        db=db,
        organization_id=principal.organization_id,
        employee=employee,
        principal=principal,
        camera=camera,
    )

    return PinVerifyResponse(
        employee_id=employee.id,
        full_name=employee.full_name,
        employee_code=employee.employee_code,
        department=employee.department.name if employee.department else "",
        event=att_result.event,
        recorded_at=att_result.recorded_at,
        status=att_result.status,
        late_minutes=att_result.late_minutes,
        undo_token=att_result.undo_token,
        event_id=att_result.event_id,
        check_in_at=att_result.check_in_at,
        check_out_at=att_result.check_out_at,
    )


def _decide_event(record: AttendanceRecord | None, now: datetime) -> str:
    if record is None:
        return "CHECK_IN"
    if record.check_out_at is not None:
        return "ALREADY_PRESENT"
    if record.check_in_at is None:
        return "CHECK_IN"

    since_check_in = (now - record.check_in_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    if since_check_in < settings.checkout_after_minutes:
        return "ALREADY_PRESENT"
    return "CHECK_OUT"


def _recognize_response(
    employee: Employee,
    record: AttendanceRecord | None,
    event: str,
    now: datetime,
    confidence: float,
    liveness_score: float,
) -> RecognizeResponse:
    return RecognizeResponse(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department.name if employee.department else "",
        event=event,
        recorded_at=now,
        status=record.status if record else AttendanceStatus.PRESENT,
        late_minutes=record.late_minutes if record else 0,
        match_confidence=confidence,
        liveness_score=liveness_score,
        check_in_at=record.check_in_at if record else None,
        check_out_at=record.check_out_at if record else None,
    )


def _late_minutes(moment: datetime, shift: Shift | None) -> int:
    if shift is not None:
        hour, minute = (int(part) for part in shift.start_time.split(":"))
        grace_minutes = shift.grace_minutes
    else:
        hour, minute = settings.shift_start_hour, 0
        grace_minutes = settings.shift_grace_minutes

    start = moment.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
        minutes=grace_minutes
    )
    if moment <= start:
        return 0
    return int((moment - start).total_seconds() // 60)


@router.get("/attendance", response_model=list[AttendanceOut])
def list_attendance(
    on: date | None = None,
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[AttendanceOut]:
    """Lists attendance records, scoped to the caller's assigned branch/department for HR and managers."""
    query = (
        select(AttendanceRecord, Employee)
        .join(Employee, Employee.id == AttendanceRecord.employee_id)
        .where(AttendanceRecord.organization_id == principal.organization_id)
    )
    if on is not None:
        query = query.where(AttendanceRecord.date == on)

    if principal.branch_id is not None:
        query = query.where(Employee.branch_id == principal.branch_id)
    if principal.department_id is not None:
        query = query.where(Employee.department_id == principal.department_id)

    rows = db.execute(query.order_by(AttendanceRecord.date.desc())).all()
    return [
        AttendanceOut(
            id=record.id,
            employee_id=record.employee_id,
            employee_name=employee.full_name,
            date=record.date,
            check_in_at=record.check_in_at,
            check_out_at=record.check_out_at,
            status=record.status,
            late_minutes=record.late_minutes,
        )
        for record, employee in rows
    ]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> DashboardResponse:
    organization_id = principal.organization_id
    organization = db.get(Organization, organization_id)
    today = datetime.now(timezone.utc).date()

    emp_query = select(Employee).where(
        Employee.organization_id == organization_id,
        Employee.is_active.is_(True),
    )
    if principal.branch_id is not None:
        emp_query = emp_query.where(Employee.branch_id == principal.branch_id)
    if principal.department_id is not None:
        emp_query = emp_query.where(Employee.department_id == principal.department_id)

    employees = db.scalars(emp_query).all()
    total = len(employees)
    scoped_emp_ids = {e.id for e in employees}

    records_query = select(AttendanceRecord).where(
        AttendanceRecord.organization_id == organization_id,
        AttendanceRecord.date == today,
    )
    if scoped_emp_ids:
        records_query = records_query.where(AttendanceRecord.employee_id.in_(scoped_emp_ids))
    elif total == 0:
        records_query = records_query.where(False)

    records = db.scalars(records_query).all()
    present = sum(1 for r in records if r.status is AttendanceStatus.PRESENT)
    late = sum(1 for r in records if r.status is AttendanceStatus.LATE)
    enrolled = enrolled_ids(db, organization_id)
    scoped_enrolled = len(scoped_emp_ids.intersection(enrolled))

    attention_items = []

    # 1. Provisional events needing confirmation
    prov_query = select(AttendanceEvent).where(
        AttendanceEvent.organization_id == organization_id,
        AttendanceEvent.provisional.is_(True),
        AttendanceEvent.voided_at.is_(None),
    )
    prov_events = db.scalars(prov_query.order_by(AttendanceEvent.occurred_at.desc()).limit(10)).all()
    provisional_count = len(prov_events)
    for pev in prov_events:
        attention_items.append(
            AttentionItem(
                category="PROVISIONAL_EVENT",
                title=f"Provisional Attendance Event ({pev.type.value if hasattr(pev.type, 'value') else pev.type})",
                description=f"Standard assurance scan on {pev.occurred_at.strftime('%H:%M')} requires admin review.",
                target_id=pev.id,
                action_url=f"/dashboard/attendance?highlight={pev.id}",
            )
        )

    # 2. Offline kiosks (not seen in past 15 minutes)
    fifteen_min_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
    dev_query = select(AttendanceDevice).where(
        AttendanceDevice.organization_id == organization_id,
        AttendanceDevice.status == DeviceStatus.ACTIVE,
    )
    if principal.branch_id is not None:
        dev_query = dev_query.where(AttendanceDevice.branch_id == principal.branch_id)
    devices = db.scalars(dev_query).all()
    offline_devices = [d for d in devices if d.last_seen_at is None or d.last_seen_at.replace(tzinfo=timezone.utc) < fifteen_min_ago]
    offline_count = len(offline_devices)
    for dev in offline_devices[:5]:
        last_str = dev.last_seen_at.strftime("%b %d, %H:%M") if dev.last_seen_at else "Never"
        attention_items.append(
            AttentionItem(
                category="OFFLINE_KIOSK",
                title=f"Kiosk Offline: {dev.name}",
                description=f"Device has not communicated since {last_str}.",
                target_id=dev.id,
                action_url="/dashboard/devices",
            )
        )

    # 3. Unenrolled employees
    unenrolled_emps = [e for e in employees if e.id not in enrolled]
    for uemp in unenrolled_emps[:5]:
        attention_items.append(
            AttentionItem(
                category="UNENROLLED_EMPLOYEE",
                title=f"Missing Biometrics: {uemp.full_name}",
                description=f"Employee #{uemp.employee_code} has no active face profile.",
                target_id=uemp.id,
                action_url=f"/dashboard/employees/{uemp.id}",
            )
        )

    return DashboardResponse(
        organization_name=organization.name if organization else "",
        date=today,
        total_employees=total,
        present=present,
        late=late,
        not_checked_in=max(0, total - len(records)),
        pending_enrollments=max(0, total - scoped_enrolled),
        provisional_events_count=provisional_count,
        offline_devices_count=offline_count,
        attention_items=attention_items,
    )


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = 50,
    principal: Principal = Depends(require_roles(Role.ORGANIZATION_ADMIN)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[AuditLogOut]:
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.organization_id == principal.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 200))
    ).all()
    return [
        AuditLogOut(
            id=log.id,
            action=log.action,
            actor_user_id=log.actor_user_id,
            target_type=log.target_type,
            target_id=log.target_id,
            meta=log.meta or {},
            created_at=log.created_at,
        )
        for log in logs
    ]

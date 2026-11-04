"""The employee roster and the face profile attached to each person."""

from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    ALLOWED_IMAGE_TYPES,
    STAFF_ROLES,
    VIEWER_ROLES,
    assert_seat_available,
    check_scope,
    enrolled_ids,
    get_org_employee,
    get_scoped_employee,
    read_image,
    revoke_active_face_profiles,
)
from ..face import embed_async, get_engine
from ..models import Branch, Department, Employee, FaceProfile, Shift
from ..schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate, EnrollResponse, SetPinRequest
from ..security import AppError, Principal, hash_password, record_audit, require_roles, tenant_scope

router = APIRouter()


def _employee_out(employee: Employee, enrolled_ids: set[str]) -> EmployeeOut:
    return EmployeeOut(
        id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        email=employee.email,
        phone=employee.phone,
        department=employee.department.name if employee.department else "",
        branch=employee.branch.name if employee.branch else "",
        job_title=employee.job_title,
        shift_name=employee.shift.name if employee.shift else "",
        is_active=employee.is_active,
        face_enrolled=employee.id in enrolled_ids,
    )


def _get_or_create_department(db: Session, organization_id: str, name: str) -> Department:
    clean = (name or "").strip() or "General"
    department = db.scalar(
        select(Department).where(
            Department.organization_id == organization_id,
            func.lower(Department.name) == clean.lower(),
        )
    )
    if department is None:
        department = Department(organization_id=organization_id, name=clean)
        db.add(department)
        db.flush()
    return department


def _get_or_create_branch(db: Session, organization_id: str, name: str | None) -> Branch | None:
    clean = (name or "").strip()
    if not clean:
        return None
    branch = db.scalar(
        select(Branch).where(
            Branch.organization_id == organization_id, func.lower(Branch.name) == clean.lower()
        )
    )
    if branch is None:
        branch = Branch(organization_id=organization_id, name=clean)
        db.add(branch)
        db.flush()
    return branch


def _find_shift(db: Session, organization_id: str, name: str | None) -> Shift | None:
    clean = (name or "").strip()
    if not clean:
        return None
    shift = db.scalar(
        select(Shift).where(
            Shift.organization_id == organization_id, func.lower(Shift.name) == clean.lower()
        )
    )
    if shift is None:
        raise AppError("SHIFT_NOT_FOUND", f"Shift '{clean}' does not exist.", 404)
    return shift


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    include_inactive: bool = False,
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[EmployeeOut]:
    organization_id = principal.organization_id
    query = select(Employee).where(Employee.organization_id == organization_id)
    if not include_inactive:
        query = query.where(Employee.is_active.is_(True))

    # Apply branch and department scope for HR_ADMIN and MANAGER
    if principal.branch_id is not None:
        query = query.where(Employee.branch_id == principal.branch_id)
    if principal.department_id is not None:
        query = query.where(Employee.department_id == principal.department_id)

    employees = db.scalars(query.order_by(Employee.full_name)).all()
    enrolled = enrolled_ids(db, organization_id)
    return [_employee_out(employee, enrolled) for employee in employees]


@router.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(
    payload: EmployeeCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> EmployeeOut:
    organization_id = principal.organization_id
    assert_seat_available(db, organization_id)
    duplicate = db.scalar(
        select(Employee).where(
            Employee.organization_id == organization_id,
            func.lower(Employee.employee_code) == payload.employee_code.strip().lower(),
        )
    )
    if duplicate is not None:
        raise AppError("CONFLICT", "That employee code is already in use.", 409)

    if payload.department_id:
        department = db.scalar(
            select(Department).where(
                Department.id == payload.department_id,
                Department.organization_id == organization_id,
            )
        )
        if department is None:
            raise AppError("NOT_FOUND", "Department not found.", 404)
    else:
        department = _get_or_create_department(db, organization_id, payload.department)

    if payload.branch_id:
        branch = db.scalar(
            select(Branch).where(
                Branch.id == payload.branch_id,
                Branch.organization_id == organization_id,
            )
        )
        if branch is None:
            raise AppError("NOT_FOUND", "Branch not found.", 404)
    else:
        branch = _get_or_create_branch(db, organization_id, payload.branch)
    shift = _find_shift(db, organization_id, payload.shift_name)

    # Scoped administrators can only create employees in their branch/department
    check_scope(
        principal,
        branch_id=branch.id if branch else None,
        department_id=department.id if department else None,
    )

    employee = Employee(
        organization_id=organization_id,
        employee_code=payload.employee_code.strip(),
        full_name=payload.full_name.strip(),
        email=str(payload.email).lower(),
        phone=payload.phone.strip(),
        department_id=department.id,
        branch_id=branch.id if branch else None,
        shift_id=shift.id if shift else None,
        job_title=payload.job_title,
    )
    db.add(employee)
    db.flush()
    record_audit(
        db,
        action="employee.created",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
        employee_code=employee.employee_code,
    )
    db.commit()
    return _employee_out(employee, set())


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> EmployeeOut:
    employee = get_scoped_employee(db, principal, employee_id)
    return _employee_out(employee, enrolled_ids(db, principal.organization_id))


@router.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> EmployeeOut:
    """Partial update: only fields present in the payload are changed."""
    employee = get_scoped_employee(db, principal, employee_id)
    changed_fields = payload.model_fields_set

    new_branch_id = employee.branch_id
    new_dept_id = employee.department_id
    if "department_id" in changed_fields and payload.department_id is not None:
        new_dept_id = payload.department_id
    elif "department" in changed_fields and payload.department is not None:
        new_dept = _get_or_create_department(db, employee.organization_id, payload.department)
        new_dept_id = new_dept.id

    new_branch_id = employee.branch_id
    if "branch_id" in changed_fields:
        new_branch_id = payload.branch_id
    elif "branch" in changed_fields:
        new_branch = _get_or_create_branch(db, employee.organization_id, payload.branch)
        new_branch_id = new_branch.id if new_branch else None

    # Verify that the caller has scope over the target state
    check_scope(principal, branch_id=new_branch_id, department_id=new_dept_id)

    if "full_name" in changed_fields and payload.full_name is not None:
        employee.full_name = payload.full_name.strip()
    if "email" in changed_fields and payload.email is not None:
        employee.email = str(payload.email).lower()
    if "phone" in changed_fields and payload.phone is not None:
        employee.phone = payload.phone.strip()
    if "job_title" in changed_fields and payload.job_title is not None:
        employee.job_title = payload.job_title
    if ("department" in changed_fields or "department_id" in changed_fields) and new_dept_id is not None:
        employee.department_id = new_dept_id
    if "branch" in changed_fields or "branch_id" in changed_fields:
        employee.branch_id = new_branch_id
    if "shift_name" in changed_fields:
        shift = _find_shift(db, employee.organization_id, payload.shift_name)
        employee.shift_id = shift.id if shift else None
    if "is_active" in changed_fields and payload.is_active is not None:
        employee.is_active = payload.is_active
        if not payload.is_active:
            revoke_active_face_profiles(db, employee, datetime.now(timezone.utc))

    db.flush()
    record_audit(
        db,
        action="employee.updated",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
        fields=sorted(changed_fields),
    )
    db.commit()
    return _employee_out(employee, enrolled_ids(db, employee.organization_id))


@router.delete("/employees/{employee_id}", status_code=200)
def delete_employee(
    employee_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    """Soft delete: the employee row and attendance history are kept, but the employee is
    deactivated and can no longer be recognized by a scan."""
    employee = get_scoped_employee(db, principal, employee_id)
    now = datetime.now(timezone.utc)
    employee.is_active = False
    revoked = revoke_active_face_profiles(db, employee, now)

    record_audit(
        db,
        action="employee.deactivated",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
        revoked_profiles=revoked,
    )
    db.commit()
    return {"employee_id": employee.id, "is_active": False, "face_profiles_revoked": revoked}


@router.post("/employees/{employee_id}/pin")
def set_employee_pin(
    employee_id: str,
    payload: SetPinRequest,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    """Sets or resets an employee PIN for kiosk fallback. Restricted to Admin/HR scope."""
    employee = get_scoped_employee(db, principal, employee_id)
    employee.pin_hash = hash_password(payload.pin)
    employee.failed_pin_attempts = 0
    employee.pin_locked_until = None

    record_audit(
        db,
        action="employee.pin_set",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
    )
    db.commit()
    return {"employee_id": employee.id, "pin_set": True}


@router.post("/employees/{employee_id}/face/enroll", response_model=EnrollResponse)
async def enroll_face(
    employee_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> EnrollResponse:
    form = await request.form()
    consent_val = form.get("consent") or form.get("consent_given")
    if consent_val is None:
        raise AppError("CONSENT_REQUIRED", "Explicit consent is required to enroll a face.", 422)
    if isinstance(consent_val, str) and consent_val.lower() not in ("true", "1", "yes", "on"):
        raise AppError("CONSENT_REQUIRED", "Explicit consent is required to enroll a face.", 422)
    if isinstance(consent_val, bool) and not consent_val:
        raise AppError("CONSENT_REQUIRED", "Explicit consent is required to enroll a face.", 422)

    employee = get_scoped_employee(db, principal, employee_id)

    # Collect frames and associated poses from form data
    # Supports:
    # 1. Named fields: front, left, right (and optional extra)
    # 2. Multi-value form fields: frames / images / files with poses
    # 3. Legacy single image field (rejected if < 3 distinct frames)
    frames_with_poses: list[tuple[UploadFile, str]] = []

    for pose_name in ("front", "left", "right"):
        item = form.get(pose_name)
        if isinstance(item, (UploadFile, StarletteUploadFile)):
            frames_with_poses.append((item, pose_name.upper()))

    list_items = form.getlist("frames") or form.getlist("images") or form.getlist("files")
    if list_items:
        pose_items = form.getlist("poses")
        if not pose_items and isinstance(form.get("poses"), str):
            pose_items = [p.strip().upper() for p in str(form.get("poses")).split(",") if p.strip()]

        for idx, item in enumerate(list_items):
            if isinstance(item, (UploadFile, StarletteUploadFile)):
                if idx < len(pose_items):
                    pose = pose_items[idx].strip().upper()
                elif len(list_items) == 3 and not pose_items:
                    pose = ["FRONT", "LEFT", "RIGHT"][idx]
                else:
                    pose = "FRONT"
                frames_with_poses.append((item, pose))

    single_img = form.get("image")
    if isinstance(single_img, (UploadFile, StarletteUploadFile)) and not frames_with_poses:
        frames_with_poses.append((single_img, "FRONT"))

    if len(frames_with_poses) < 3:
        raise AppError("INSUFFICIENT_FRAMES", "Enrollment requires at least 3 distinct poses: FRONT, LEFT, and RIGHT.", 422)
    if len(frames_with_poses) > 5:
        raise AppError("TOO_MANY_FRAMES", "Enrollment accepts at most 5 frames.", 422)

    submitted_poses = {pose for _, pose in frames_with_poses}
    if not {"FRONT", "LEFT", "RIGHT"}.issubset(submitted_poses):
        raise AppError("INSUFFICIENT_POSES", "Enrollment requires frames covering at least FRONT, LEFT, and RIGHT poses.", 422)

    MAX_FRAME_BYTES = 2 * 1024 * 1024
    extracted_embeddings: list[tuple[Any, str]] = []

    for upload_file, pose in frames_with_poses:
        if upload_file.content_type not in ALLOWED_IMAGE_TYPES:
            raise AppError("VALIDATION_ERROR", f"Invalid content type '{upload_file.content_type}'. Upload JPEG, PNG, or WebP.", 422)
        raw_bytes = await upload_file.read()
        if not raw_bytes:
            raise AppError("VALIDATION_ERROR", "Uploaded frame was empty.", 422)
        if len(raw_bytes) > MAX_FRAME_BYTES:
            raise AppError("FILE_TOO_LARGE", "Frame exceeds the maximum allowed size of 2 MB.", 413)

        embedding = await embed_async(raw_bytes, expected_pose=pose)
        extracted_embeddings.append((embedding, pose))

    # Pairwise cosine similarity checks
    # 1. Reject near-duplicates (> 0.98)
    # 2. Reject different people (< 0.70)
    for i in range(len(extracted_embeddings)):
        v_i = np.asarray(extracted_embeddings[i][0].vector, dtype=np.float32)
        norm_i = float(np.linalg.norm(v_i))
        if norm_i > 1e-6:
            v_i = v_i / norm_i

        for j in range(i + 1, len(extracted_embeddings)):
            v_j = np.asarray(extracted_embeddings[j][0].vector, dtype=np.float32)
            norm_j = float(np.linalg.norm(v_j))
            if norm_j > 1e-6:
                v_j = v_j / norm_j

            sim = float(np.dot(v_i, v_j))
            if sim > 0.98:
                raise AppError(
                    "DUPLICATE_FRAMES",
                    f"Frames {i+1} and {j+1} are near-duplicates (similarity {sim:.3f} > 0.98). Please provide distinct pose captures.",
                    422,
                )
            if sim < 0.70:
                raise AppError(
                    "INCONSISTENT_IDENTITY",
                    f"Frames {i+1} and {j+1} appear to belong to different individuals (similarity {sim:.3f} < 0.70).",
                    422,
                )

    # Atomic DB persistence: delete existing profiles and replace with new set sharing enrollment_id
    enrollment_id = str(uuid.uuid4())
    db.execute(delete(FaceProfile).where(FaceProfile.employee_id == employee.id))

    now = datetime.now(timezone.utc)
    new_profiles: list[FaceProfile] = []
    for emb, pose in extracted_embeddings:
        profile = FaceProfile(
            organization_id=employee.organization_id,
            employee_id=employee.id,
            enrollment_id=enrollment_id,
            pose=pose,
            embedding=emb.vector,
            embedding_vec=emb.vector,
            model_name=emb.model_name,
            model_version=emb.model_version,
            quality_score=emb.quality,
            consent_at=now,
            consented_by_user_id=principal.user_id,
        )
        db.add(profile)
        new_profiles.append(profile)

    db.flush()
    record_audit(
        db,
        action="face.enrolled",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
        model_name=extracted_embeddings[0][0].model_name,
        frames_enrolled=len(new_profiles),
        enrollment_id=enrollment_id,
    )
    db.commit()

    avg_quality = float(sum(p.quality_score for p in new_profiles) / len(new_profiles))
    return EnrollResponse(
        employee_id=employee.id,
        face_enrolled=True,
        quality_score=round(avg_quality, 3),
        model_name=new_profiles[0].model_name,
        enrollment_id=enrollment_id,
        frames_enrolled=len(new_profiles),
        poses=[p.pose for p in new_profiles],
    )


@router.delete("/employees/{employee_id}/face", status_code=200)
def revoke_face(
    employee_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    """Removes the biometric profile completely. Attendance history is deliberately left untouched."""
    employee = get_scoped_employee(db, principal, employee_id)
    existing_profiles = db.scalars(
        select(FaceProfile).where(FaceProfile.employee_id == employee.id)
    ).all()
    count = len(existing_profiles)
    for p in existing_profiles:
        db.delete(p)
    db.flush()

    record_audit(
        db,
        action="face.deleted",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        request=request,
        deleted_profiles=count,
    )
    db.commit()
    return {
        "employee_id": employee.id,
        "deleted_profiles": count,
        "revoked_profiles": count,
        "attendance_retained": True,
    }

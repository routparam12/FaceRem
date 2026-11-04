"""Shared pieces every router needs: who may do what, upload limits, and the handful of
queries that more than one group of endpoints performs."""

from datetime import datetime

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Employee, FaceProfile, Role, Subscription
from .security import AppError, Principal

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

#: Who may manage people, devices, and enroll faces.
STAFF_ROLES = (Role.ORGANIZATION_ADMIN, Role.HR_ADMIN)
#: Who may read organization-wide attendance.
VIEWER_ROLES = (Role.ORGANIZATION_ADMIN, Role.HR_ADMIN, Role.MANAGER)
#: Who may run a recognition scan. A kiosk device has its own credential.
SCANNER_ROLES = (Role.ATTENDANCE_DEVICE, Role.ORGANIZATION_ADMIN, Role.HR_ADMIN)


def check_scope(
    principal: Principal,
    *,
    branch_id: str | None = None,
    department_id: str | None = None,
) -> None:
    """
    Enforces branch and department scoping for HR_ADMIN and MANAGER.
    ORGANIZATION_ADMIN and ATTENDANCE_DEVICE have no internal department/branch restrictions.
    SUPER_ADMIN has no tenant access.
    """
    if principal.role is Role.SUPER_ADMIN:
        raise AppError("FORBIDDEN", "Platform operators cannot access tenant data.", 403)
    if principal.role is Role.ORGANIZATION_ADMIN or principal.role is Role.ATTENDANCE_DEVICE:
        return
    if principal.role in (Role.HR_ADMIN, Role.MANAGER):
        if principal.branch_id is not None and branch_id is not None and principal.branch_id != branch_id:
            raise AppError("FORBIDDEN", "You do not have access to resources in this branch.", 403)
        if principal.department_id is not None and department_id is not None and principal.department_id != department_id:
            raise AppError("FORBIDDEN", "You do not have access to resources in this department.", 403)


def get_scoped_employee(db: Session, principal: Principal, employee_id: str) -> Employee:
    """Loads an employee inside caller's organization, verifies scope, or 404s/403s."""
    employee = get_org_employee(db, principal.organization_id, employee_id)
    check_scope(principal, branch_id=employee.branch_id, department_id=employee.department_id)
    return employee


def revoke_active_face_profiles(db: Session, employee: Employee, now: datetime) -> int:
    revoked = 0
    for profile in db.scalars(
        select(FaceProfile).where(
            FaceProfile.employee_id == employee.id, FaceProfile.revoked_at.is_(None)
        )
    ).all():
        profile.revoked_at = now
        revoked += 1
    return revoked


def enrolled_ids(db: Session, organization_id: str) -> set[str]:
    return set(
        db.scalars(
            select(FaceProfile.employee_id).where(
                FaceProfile.organization_id == organization_id,
                FaceProfile.revoked_at.is_(None),
            )
        ).all()
    )


def get_org_employee(db: Session, organization_id: str, employee_id: str) -> Employee:
    """Loads an employee inside the caller's organization, or 404s.

    Cross-tenant reads answer 404 rather than 403 so one tenant cannot confirm that another
    tenant's id exists.
    """
    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.organization_id == organization_id
        )
    )
    if employee is None:
        raise AppError("EMPLOYEE_NOT_FOUND", "This employee could not be found.", 404)
    return employee


async def read_image(image: UploadFile) -> bytes:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError("VALIDATION_ERROR", "Upload a JPEG, PNG or WebP image.", 422)
    data = await image.read()
    if not data:
        raise AppError("VALIDATION_ERROR", "The uploaded image was empty.", 422)
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError("VALIDATION_ERROR", "The image is larger than 8 MB.", 413)
    return data


def assert_seat_available(db: Session, organization_id: str) -> None:
    """
    Refuse to exceed the plan's seat count.

    Checked at the point of creation rather than reported later, because a tenant that is
    already over its limit has no good remedy short of deleting people.
    """
    subscription = db.scalar(
        select(Subscription).where(Subscription.organization_id == organization_id)
    )
    if subscription is None:  # pre-subscription tenants are not metered
        return

    used = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.organization_id == organization_id, Employee.is_active.is_(True))
    ) or 0
    if used >= subscription.seat_limit:
        raise AppError(
            "SEAT_LIMIT_REACHED",
            f"Your {subscription.plan} plan includes {subscription.seat_limit} seats, "
            f"all of which are in use. Upgrade to add more people.",
            402,
        )

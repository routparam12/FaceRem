"""Departments, branches and shifts: the tenant-owned lookup entities."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Role, Subscription, Branch, Department, Employee, Shift, Organization
from ..schemas import (
    SubscriptionOut,
    BranchCreate,
    BranchOut,
    DepartmentCreate,
    DepartmentOut,
    OrganizationOut,
    OrganizationUpdate,
    ShiftCreate,
    ShiftOut,
)
from ..security import AppError, Principal, record_audit, require_roles, tenant_scope
from ..deps import STAFF_ROLES, VIEWER_ROLES

router = APIRouter()


def _department_out(db: Session, department: Department) -> DepartmentOut:
    head_count = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.department_id == department.id, Employee.is_active.is_(True))
    )
    return DepartmentOut(id=department.id, name=department.name, head_count=head_count or 0)


def _branch_out(db: Session, branch: Branch) -> BranchOut:
    head_count = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.branch_id == branch.id, Employee.is_active.is_(True))
    )
    return BranchOut(id=branch.id, name=branch.name, city=branch.city, head_count=head_count or 0)


def _shift_out(shift: Shift) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        name=shift.name,
        start_time=shift.start_time,
        end_time=shift.end_time,
        grace_minutes=shift.grace_minutes,
    )


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[DepartmentOut]:
    departments = db.scalars(
        select(Department)
        .where(Department.organization_id == principal.organization_id)
        .order_by(Department.name)
    ).all()
    return [_department_out(db, department) for department in departments]


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> DepartmentOut:
    name = payload.name.strip()
    duplicate = db.scalar(
        select(Department).where(
            Department.organization_id == principal.organization_id,
            func.lower(Department.name) == name.lower(),
        )
    )
    if duplicate is not None:
        raise AppError("CONFLICT", "A department with that name already exists.", 409)

    department = Department(organization_id=principal.organization_id, name=name)
    db.add(department)
    db.flush()
    record_audit(
        db,
        action="department.created",
        principal=principal,
        target_type="department",
        target_id=department.id,
        request=request,
        name=name,
    )
    db.commit()
    return _department_out(db, department)


@router.delete("/departments/{department_id}", status_code=200)
def delete_department(
    department_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    department = db.scalar(
        select(Department).where(
            Department.id == department_id, Department.organization_id == principal.organization_id
        )
    )
    if department is None:
        raise AppError("DEPARTMENT_NOT_FOUND", "This department could not be found.", 404)

    in_use = db.scalar(
        select(func.count()).select_from(Employee).where(Employee.department_id == department.id)
    )
    if in_use:
        raise AppError("CONFLICT", "This department still has employees assigned to it.", 409)

    db.delete(department)
    record_audit(
        db,
        action="department.deleted",
        principal=principal,
        target_type="department",
        target_id=department_id,
        request=request,
        name=department.name,
    )
    db.commit()
    return {"department_id": department_id, "deleted": True}


@router.get("/branches", response_model=list[BranchOut])
def list_branches(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[BranchOut]:
    branches = db.scalars(
        select(Branch)
        .where(Branch.organization_id == principal.organization_id)
        .order_by(Branch.name)
    ).all()
    return [_branch_out(db, branch) for branch in branches]


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(
    payload: BranchCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> BranchOut:
    name = payload.name.strip()
    duplicate = db.scalar(
        select(Branch).where(
            Branch.organization_id == principal.organization_id,
            func.lower(Branch.name) == name.lower(),
        )
    )
    if duplicate is not None:
        raise AppError("CONFLICT", "A branch with that name already exists.", 409)

    branch = Branch(organization_id=principal.organization_id, name=name, city=payload.city.strip())
    db.add(branch)
    db.flush()
    record_audit(
        db,
        action="branch.created",
        principal=principal,
        target_type="branch",
        target_id=branch.id,
        request=request,
        name=name,
    )
    db.commit()
    return _branch_out(db, branch)


@router.delete("/branches/{branch_id}", status_code=200)
def delete_branch(
    branch_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    branch = db.scalar(
        select(Branch).where(
            Branch.id == branch_id, Branch.organization_id == principal.organization_id
        )
    )
    if branch is None:
        raise AppError("BRANCH_NOT_FOUND", "This branch could not be found.", 404)

    in_use = db.scalar(
        select(func.count()).select_from(Employee).where(Employee.branch_id == branch.id)
    )
    if in_use:
        raise AppError("CONFLICT", "This branch still has employees assigned to it.", 409)

    db.delete(branch)
    record_audit(
        db,
        action="branch.deleted",
        principal=principal,
        target_type="branch",
        target_id=branch_id,
        request=request,
        name=branch.name,
    )
    db.commit()
    return {"branch_id": branch_id, "deleted": True}


@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[ShiftOut]:
    shifts = db.scalars(
        select(Shift)
        .where(Shift.organization_id == principal.organization_id)
        .order_by(Shift.name)
    ).all()
    return [_shift_out(shift) for shift in shifts]


@router.post("/shifts", response_model=ShiftOut, status_code=201)
def create_shift(
    payload: ShiftCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> ShiftOut:
    name = payload.name.strip()
    duplicate = db.scalar(
        select(Shift).where(
            Shift.organization_id == principal.organization_id,
            func.lower(Shift.name) == name.lower(),
        )
    )
    if duplicate is not None:
        raise AppError("CONFLICT", "A shift with that name already exists.", 409)

    shift = Shift(
        organization_id=principal.organization_id,
        name=name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        grace_minutes=payload.grace_minutes,
    )
    db.add(shift)
    db.flush()
    record_audit(
        db,
        action="shift.created",
        principal=principal,
        target_type="shift",
        target_id=shift.id,
        request=request,
        name=name,
    )
    db.commit()
    return _shift_out(shift)


@router.delete("/shifts/{shift_id}", status_code=200)
def delete_shift(
    shift_id: str,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> dict:
    shift = db.scalar(
        select(Shift).where(
            Shift.id == shift_id, Shift.organization_id == principal.organization_id
        )
    )
    if shift is None:
        raise AppError("SHIFT_NOT_FOUND", "This shift could not be found.", 404)

    in_use = db.scalar(
        select(func.count()).select_from(Employee).where(Employee.shift_id == shift.id)
    )
    if in_use:
        raise AppError("CONFLICT", "This shift still has employees assigned to it.", 409)

    db.delete(shift)
    record_audit(
        db,
        action="shift.deleted",
        principal=principal,
        target_type="shift",
        target_id=shift_id,
        request=request,
        name=shift.name,
    )
    db.commit()
    return {"shift_id": shift_id, "deleted": True}


@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    principal: Principal = Depends(require_roles(Role.ORGANIZATION_ADMIN, Role.HR_ADMIN)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> SubscriptionOut:
    """What this tenant is entitled to, and how much of it is in use."""
    subscription = db.scalar(
        select(Subscription).where(Subscription.organization_id == principal.organization_id)
    )
    if subscription is None:
        raise AppError("NOT_FOUND", "This organization has no subscription.", 404)

    used = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(
            Employee.organization_id == principal.organization_id,
            Employee.is_active.is_(True),
        )
    ) or 0
    return SubscriptionOut(
        plan=subscription.plan,
        status=subscription.status,
        seat_limit=subscription.seat_limit,
        seats_used=used,
        seats_available=max(0, subscription.seat_limit - used),
        current_period_end=subscription.current_period_end,
    )


@router.get("/organization", response_model=OrganizationOut)
def get_organization(
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> OrganizationOut:
    org = db.get(Organization, principal.organization_id)
    if org is None:
        raise AppError("NOT_FOUND", "Organization not found.", 404)
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        timezone=org.timezone,
        is_active=org.is_active,
        created_at=org.created_at,
    )


@router.patch("/organization", response_model=OrganizationOut)
def update_organization(
    payload: OrganizationUpdate,
    request: Request,
    principal: Principal = Depends(require_roles(Role.ORGANIZATION_ADMIN)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> OrganizationOut:
    import zoneinfo
    org = db.get(Organization, principal.organization_id)
    if org is None:
        raise AppError("NOT_FOUND", "Organization not found.", 404)

    if payload.timezone is not None:
        tz_str = payload.timezone.strip()
        try:
            zoneinfo.ZoneInfo(tz_str)
        except Exception:
            raise AppError("VALIDATION_ERROR", f"'{tz_str}' is not a valid IANA timezone identifier.", 422)
        org.timezone = tz_str

    if payload.name is not None:
        org.name = payload.name.strip()

    record_audit(
        db,
        action="organization.updated",
        principal=principal,
        target_type="organization",
        target_id=org.id,
        request=request,
    )
    db.commit()
    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        timezone=org.timezone,
        is_active=org.is_active,
        created_at=org.created_at,
    )

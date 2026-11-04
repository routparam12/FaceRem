"""
Accounts inside an organization: who can sign in, and as what.

Separate from auth.py on purpose — that file is about your own session, this one is about
administering other people's.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import STAFF_ROLES
from ..models import Employee, Role, User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import (
    AppError,
    Principal,
    assert_can_assign,
    hash_password,
    record_audit,
    require_roles,
    revoke_all_for_user,
    tenant_scope,
)

router = APIRouter()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        employee_id=user.employee_id,
        branch_id=user.branch_id,
        department_id=user.department_id,
        is_totp_enabled=user.is_totp_enabled,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def _get_org_user(db: Session, organization_id: str, user_id: str) -> User:
    """404 rather than 403 across tenants, so one organization cannot probe another's ids."""
    user = db.scalar(
        select(User).where(User.id == user_id, User.organization_id == organization_id)
    )
    if user is None:
        raise AppError("NOT_FOUND", "This user could not be found.", 404)
    return user


def _count_active_admins(db: Session, organization_id: str, *, excluding: str | None = None) -> int:
    query = select(func.count()).select_from(User).where(
        User.organization_id == organization_id,
        User.role == Role.ORGANIZATION_ADMIN,
        User.is_active.is_(True),
    )
    if excluding is not None:
        query = query.where(User.id != excluding)
    return db.scalar(query) or 0


@router.get("/users", response_model=list[UserOut])
def list_users(
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> list[UserOut]:
    users = db.scalars(
        select(User)
        .where(User.organization_id == principal.organization_id)
        .order_by(User.full_name)
    ).all()
    return [_user_out(user) for user in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> UserOut:
    organization_id = principal.organization_id
    # Staff cannot mint an unauthorized role or assign employee sign-in
    assert_can_assign(principal.role, payload.role)

    email = str(payload.email).strip().lower()
    if db.scalar(
        select(User).where(User.organization_id == organization_id, User.email == email)
    ):
        raise AppError("CONFLICT", "A user with that email already exists.", 409)

    employee_id = None
    if payload.employee_id is not None:
        employee = db.scalar(
            select(Employee).where(
                Employee.id == payload.employee_id,
                Employee.organization_id == organization_id,
            )
        )
        if employee is None:
            raise AppError("EMPLOYEE_NOT_FOUND", "This employee could not be found.", 404)
        employee_id = employee.id

    user = User(
        organization_id=organization_id,
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role,
        branch_id=payload.branch_id,
        department_id=payload.department_id,
        employee_id=employee_id,
    )
    db.add(user)
    db.flush()

    record_audit(
        db,
        action="user.created",
        principal=principal,
        target_type="user",
        target_id=user.id,
        request=request,
        role=user.role.value,
        branch_id=user.branch_id,
        department_id=user.department_id,
    )
    db.commit()
    return _user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    principal: Principal = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> UserOut:
    user = _get_org_user(db, principal.organization_id, user_id)
    changed: dict[str, object] = {}

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
        changed["full_name"] = True

    if payload.branch_id is not None and payload.branch_id != user.branch_id:
        user.branch_id = payload.branch_id
        changed["branch_id"] = payload.branch_id
        record_audit(
            db,
            action="user.scope_changed",
            principal=principal,
            target_type="user",
            target_id=user.id,
            request=request,
            branch_id=payload.branch_id,
        )

    if payload.department_id is not None and payload.department_id != user.department_id:
        user.department_id = payload.department_id
        changed["department_id"] = payload.department_id
        record_audit(
            db,
            action="user.scope_changed",
            principal=principal,
            target_type="user",
            target_id=user.id,
            request=request,
            department_id=payload.department_id,
        )

    if payload.role is not None and payload.role != user.role:
        # Editing your own role is how a privilege check gets bypassed.
        if user.id == principal.user_id:
            raise AppError("FORBIDDEN", "You cannot change your own role.", 403)
        assert_can_assign(principal.role, payload.role)
        # HR must not be able to demote the admin who manages them.
        assert_can_assign(principal.role, user.role)
        if user.role is Role.ORGANIZATION_ADMIN and _count_active_admins(
            db, principal.organization_id, excluding=user.id
        ) == 0:
            raise AppError("CONFLICT", "The last organization admin cannot be demoted.", 409)
        changed["role"] = payload.role.value
        user.role = payload.role
        record_audit(
            db,
            action="user.role_changed",
            principal=principal,
            target_type="user",
            target_id=user.id,
            request=request,
            new_role=payload.role.value,
        )

    if payload.is_active is not None and payload.is_active != user.is_active:
        if user.id == principal.user_id:
            raise AppError("FORBIDDEN", "You cannot deactivate your own account.", 403)
        if not payload.is_active:
            assert_can_assign(principal.role, user.role)
            if user.role is Role.ORGANIZATION_ADMIN and _count_active_admins(
                db, principal.organization_id, excluding=user.id
            ) == 0:
                raise AppError(
                    "CONFLICT", "The last organization admin cannot be deactivated.", 409
                )
            # A deactivated account must lose its live sessions, not just future logins.
            revoke_all_for_user(db, user.id)
        user.is_active = payload.is_active
        changed["is_active"] = payload.is_active

    record_audit(
        db,
        action="user.updated",
        principal=principal,
        target_type="user",
        target_id=user.id,
        request=request,
        **changed,
    )
    db.commit()
    return _user_out(user)

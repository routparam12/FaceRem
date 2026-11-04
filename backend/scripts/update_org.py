from pathlib import Path

path = Path("backend/app/routers/org.py")
content = path.read_text(encoding="utf-8")

old_import = """from ..models import Role, Subscription, Branch, Department, Employee, Shift
from ..schemas import (
    SubscriptionOut,
    BranchCreate,
    BranchOut,
    DepartmentCreate,
    DepartmentOut,
    ShiftCreate,
    ShiftOut,
)"""

new_import = """from ..models import Role, Subscription, Branch, Department, Employee, Shift, Organization
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
)"""

endpoints = """

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
"""

assert old_import in content, "old_import not found"
content = content.replace(old_import, new_import) + endpoints
path.write_text(content, encoding="utf-8")
print("Updated org.py successfully")


"""Demo tenants for the PoC. Two organizations exist so tenant isolation is testable."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    PLAN_SEATS,
    AttendanceDevice,
    Branch,
    Department,
    DeviceMode,
    DeviceStatus,
    Employee,
    Organization,
    Role,
    Shift,
    Subscription,
    SubscriptionStatus,
    User,
)
from .security import hash_password, hash_pin

DEMO_PASSWORD = "demo12345"

#: (slug, display name, plan, employee-code prefix)
_ORGS = [
    ("northwind", "Northwind Industries", "GROWTH", "NW"),
    ("acme", "Acme Logistics", "TRIAL", "AC"),
]

_STAFF = [
    ("admin@{slug}.demo", "Org Admin", Role.ORGANIZATION_ADMIN),
    ("hr@{slug}.demo", "HR Admin", Role.HR_ADMIN),
    ("manager@{slug}.demo", "Team Manager", Role.MANAGER),
    ("kiosk@{slug}.demo", "Lobby Kiosk", Role.ATTENDANCE_DEVICE),
]

_EMPLOYEES = [
    ("E-1001", "Aarav Sharma", "Engineering", "Android Engineer"),
    ("E-1002", "Priya Nair", "People & HR", "HR Business Partner"),
    ("E-1003", "Rahul Verma", "Operations", "Shift Supervisor"),
]


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Organization).limit(1)) is not None:
        return

    for slug, name, plan, code_prefix in _ORGS:
        organization = Organization(name=name, slug=slug, plan=plan)
        db.add(organization)
        db.flush()
        db.add(
            Subscription(
                organization_id=organization.id,
                plan=plan,
                seat_limit=PLAN_SEATS.get(plan, 25),
                status=SubscriptionStatus.ACTIVE,
            )
        )

        admin_user = None
        for email_template, full_name, role in _STAFF:
            user = User(
                organization_id=organization.id,
                email=email_template.format(slug=slug),
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=f"{full_name} ({name})",
                role=role,
            )
            db.add(user)
            db.flush()
            if role == Role.ORGANIZATION_ADMIN:
                admin_user = user

        departments: dict[str, Department] = {}
        branch = Branch(organization_id=organization.id, name="Head Office", city=name.split()[0])
        shift = Shift(organization_id=organization.id, name="General Shift", start_time="09:00")
        db.add(branch)
        db.add(shift)
        db.flush()

        kiosk_device = AttendanceDevice(
            organization_id=organization.id,
            name=f"Lobby Kiosk ({name})",
            branch_id=branch.id,
            mode=DeviceMode.AUTO,
            status=DeviceStatus.ACTIVE,
            registered_by=admin_user.id if admin_user else None,
        )
        db.add(kiosk_device)
        db.flush()

        for index, (code, full_name, department_name, title) in enumerate(_EMPLOYEES):
            department = departments.get(department_name)
            if department is None:
                department = Department(organization_id=organization.id, name=department_name)
                db.add(department)
                db.flush()
                departments[department_name] = department

            employee = Employee(
                organization_id=organization.id,
                employee_code=f"{code_prefix}-{code}",
                full_name=full_name,
                email=f"{full_name.split()[0].lower()}@{slug}.demo",
                phone="",
                department_id=department.id,
                # Only the first employee is assigned a branch/shift, so the rest exercise the
                # "unassigned" path the client also has to handle.
                branch_id=branch.id if index == 0 else None,
                shift_id=shift.id if index == 0 else None,
                job_title=title,
                pin_hash=hash_pin("1234") if index == 0 else None,
            )
            db.add(employee)
            db.flush()
            # Employees have NO login accounts in the kiosk-first model.

    db.add(
        User(
            organization_id=None,
            email="root@faceattend.platform",
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Platform Operator",
            role=Role.SUPER_ADMIN,
        )
    )
    db.commit()

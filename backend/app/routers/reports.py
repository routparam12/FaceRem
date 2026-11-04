"""
Streaming CSV export endpoints for compliance, audit, and payroll reporting.
Formula injection defense (CSV injection) and UTF-8 BOM encoding for Excel compatibility.
"""

from datetime import date, datetime, timezone
import io
import re
from typing import Generator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import STAFF_ROLES, VIEWER_ROLES, check_scope
from ..models import (
    AttendanceEvent,
    AttendanceRecord,
    AttendanceStatus,
    Branch,
    Camera,
    Department,
    Employee,
    Shift,
)
from ..security import AppError, Principal, require_roles, tenant_scope

router = APIRouter()

# Characters that trigger formula execution in Excel/Calc/Sheets
_DANGEROUS_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(value: any) -> str:
    """Neutralizes formula injection by escaping unsafe leading characters."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith(_DANGEROUS_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def _to_csv_row(columns: list[any]) -> str:
    escaped = []
    for col in columns:
        sanitized = _sanitize_csv_cell(col)
        # Escape internal quotes and wrap in quotes if containing comma or quote or newline
        if any(c in sanitized for c in (',', '"', '\n', '\r')):
            escaped.append('"' + sanitized.replace('"', '""') + '"')
        else:
            escaped.append(sanitized)
    return ",".join(escaped) + "\r\n"


@router.get("/reports/attendance-events.csv")
def export_attendance_events_csv(
    start_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    branch_id: str | None = Query(None, description="Filter by branch ID"),
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    method: str | None = Query(None, description="Filter by method: FACE | PIN"),
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> StreamingResponse:
    """Streams full raw attendance events as a formula-injection-safe CSV with UTF-8 BOM."""
    if branch_id:
        check_scope(principal, branch_id=branch_id)
    elif principal.branch_id is not None:
        branch_id = principal.branch_id

    # Base query joined with employee, branch, camera
    query = (
        select(
            AttendanceEvent,
            Employee.employee_code.label("emp_code"),
            Employee.full_name.label("emp_name"),
            Department.name.label("dept_name"),
            Branch.name.label("branch_name"),
            Camera.name.label("camera_name"),
            Camera.assurance.label("cam_assurance"),
        )
        .outerjoin(Employee, AttendanceEvent.employee_id == Employee.id)
        .outerjoin(Department, Employee.department_id == Department.id)
        .outerjoin(Branch, Employee.branch_id == Branch.id)
        .outerjoin(Camera, AttendanceEvent.camera_id == Camera.id)
        .where(AttendanceEvent.organization_id == principal.organization_id)
    )

    if branch_id:
        query = query.where(Employee.branch_id == branch_id)
    if camera_id:
        query = query.where(AttendanceEvent.camera_id == camera_id)
    if method:
        query = query.where(AttendanceEvent.method == method.upper())
    if start_date:
        query = query.where(AttendanceEvent.occurred_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
    if end_date:
        query = query.where(AttendanceEvent.occurred_at <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))

    query = query.order_by(AttendanceEvent.occurred_at.desc())

    headers = [
        "Event ID",
        "Timestamp (UTC)",
        "Employee ID",
        "Employee Code",
        "Employee Name",
        "Department",
        "Branch",
        "Direction",
        "Method",
        "Camera Name",
        "Device ID",
        "Assurance",
        "Provisional",
        "Status",
        "Void Reason",
    ]

    def event_stream() -> Generator[bytes, None, None]:
        # UTF-8 BOM for Microsoft Excel compatibility
        yield b"\xef\xbb\xbf"
        yield _to_csv_row(headers).encode("utf-8")

        # Stream rows in chunks
        batch_size = 500
        offset = 0
        while True:
            batch = db.execute(query.limit(batch_size).offset(offset)).all()
            if not batch:
                break
            for row in batch:
                ev = row[0]
                status = (
                    "VOIDED" if ev.voided_at
                    else ("PROVISIONAL" if ev.provisional else "VALID")
                )
                direction = ev.type.value if hasattr(ev.type, "value") else str(ev.type)
                assurance = (
                    row.cam_assurance.value
                    if hasattr(row.cam_assurance, "value")
                    else (str(row.cam_assurance) if row.cam_assurance else "")
                )
                row_data = [
                    ev.id,
                    ev.occurred_at.isoformat() if ev.occurred_at else "",
                    ev.employee_id,
                    row.emp_code or "",
                    row.emp_name or "",
                    row.dept_name or "",
                    row.branch_name or "",
                    direction,
                    ev.method.value if hasattr(ev.method, "value") else str(ev.method),
                    row.camera_name or "",
                    ev.device_id or "",
                    assurance,
                    "true" if ev.provisional else "false",
                    status,
                    ev.void_reason or "",
                ]
                yield _to_csv_row(row_data).encode("utf-8")
            offset += batch_size

    filename = f"attendance-events-{date.today().isoformat()}.csv"
    return StreamingResponse(
        event_stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/monthly-summary.csv")
def export_monthly_summary_csv(
    year: int = Query(default=None, description="Year (YYYY)"),
    month: int = Query(default=None, ge=1, le=12, description="Month (1-12)"),
    branch_id: str | None = Query(None, description="Filter by branch ID"),
    principal: Principal = Depends(require_roles(*VIEWER_ROLES)),
    db: Session = Depends(get_db),
    _: Principal = Depends(tenant_scope),
) -> StreamingResponse:
    """Streams monthly attendance summary (days present, late, absent, hours) as formula-safe CSV."""
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    if branch_id:
        check_scope(principal, branch_id=branch_id)
    elif principal.branch_id is not None:
        branch_id = principal.branch_id

    # Active employees
    emp_query = (
        select(
            Employee,
            Department.name.label("dept_name"),
            Branch.name.label("branch_name"),
            Shift.name.label("shift_name"),
        )
        .outerjoin(Department, Employee.department_id == Department.id)
        .outerjoin(Branch, Employee.branch_id == Branch.id)
        .outerjoin(Shift, Employee.shift_id == Shift.id)
        .where(
            Employee.organization_id == principal.organization_id,
            Employee.is_active.is_(True),
        )
    )
    if branch_id:
        emp_query = emp_query.where(Employee.branch_id == branch_id)

    employees = db.execute(emp_query.order_by(Employee.full_name)).all()

    # Query attendance records for the given year/month
    # Date range for the month
    import calendar
    _, last_day = calendar.monthrange(year, month)
    m_start = date(year, month, 1)
    m_end = date(year, month, last_day)

    rec_query = (
        select(AttendanceRecord)
        .where(
            AttendanceRecord.organization_id == principal.organization_id,
            AttendanceRecord.date >= m_start,
            AttendanceRecord.date <= m_end,
        )
    )
    records = db.scalars(rec_query).all()

    # Group records by employee_id
    from collections import defaultdict
    emp_records = defaultdict(list)
    for rec in records:
        emp_records[rec.employee_id].append(rec)

    headers = [
        "Employee Code",
        "Employee Name",
        "Department",
        "Branch",
        "Shift",
        "Days Present",
        "Days Late",
        "Days Absent",
        "Total Work Hours",
        "Total Late Minutes",
    ]

    def summary_stream() -> Generator[bytes, None, None]:
        yield b"\xef\xbb\xbf"
        yield _to_csv_row(headers).encode("utf-8")

        for emp_row in employees:
            emp = emp_row[0]
            recs = emp_records.get(emp.id, [])
            present_days = sum(1 for r in recs if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
            late_days = sum(1 for r in recs if r.status == AttendanceStatus.LATE)
            absent_days = sum(1 for r in recs if r.status == AttendanceStatus.ABSENT)
            total_hours = 0.0
            for r in recs:
                if r.check_in_at and r.check_out_at:
                    total_hours += (r.check_out_at - r.check_in_at).total_seconds() / 3600.0
            total_late_min = sum(r.late_minutes or 0 for r in recs)

            row_data = [
                emp.employee_code,
                emp.full_name,
                emp_row.dept_name or "",
                emp_row.branch_name or "",
                emp_row.shift_name or "",
                present_days,
                late_days,
                absent_days,
                f"{total_hours:.1f}",
                total_late_min,
            ]
            yield _to_csv_row(row_data).encode("utf-8")

    filename = f"monthly-summary-{year}-{month:02d}.csv"
    return StreamingResponse(
        summary_stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


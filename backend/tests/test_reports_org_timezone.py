"""Focused tests for Phase 4+ reporting, org timezone, and audit endpoints.

Covers success, wrong-role (403), cross-org isolation, CSV formula injection,
and large date-range streaming.
"""

from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(
    DATABASE_URL="sqlite:///./test_reports_org.db",
    JWT_SECRET="test-secret-that-is-long-enough-for-hs256-abcdef",
    FACE_ENGINE="stub",
    LIVENESS_MODE="disabled",
    LIVENESS_THRESHOLD="0.7",
    CHECKOUT_AFTER_MINUTES="240",
    SEED_DEMO_DATA="true",
)

DB_PATH = Path("./test_reports_org.db")
if DB_PATH.exists():
    DB_PATH.unlink()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
_alembic.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
command.upgrade(_alembic, "head")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AttendanceDevice,
    AttendanceEvent,
    AttendanceEventType,
    AttendanceMethod,
    AttendanceRecord,
    AttendanceStatus,
    Employee,
    Organization,
)
from app.seed import DEMO_PASSWORD  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_formula_employee_and_event(org_slug: str = "northwind") -> str:
    """Create an employee whose name starts with a formula prefix and one attendance event."""
    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.slug == org_slug).one()
        device = db.query(AttendanceDevice).filter(AttendanceDevice.organization_id == org.id).first()
        assert device is not None
        emp = Employee(
            organization_id=org.id,
            employee_code=f"FX-{uuid.uuid4().hex[:6].upper()}",
            full_name='=HYPERLINK("http://evil")',
            email=f"formula-{uuid.uuid4().hex[:8]}@{org_slug}.demo",
            is_active=True,
        )
        db.add(emp)
        db.flush()
        event = AttendanceEvent(
            organization_id=org.id,
            employee_id=emp.id,
            device_id=device.id,
            type=AttendanceEventType.CHECK_IN,
            method=AttendanceMethod.PIN,
            occurred_at=datetime.now(timezone.utc),
            provisional=False,
        )
        db.add(event)
        db.commit()
        return emp.employee_code


# ---------------------------------------------------------------------------
# Attendance events CSV export
# ---------------------------------------------------------------------------

def test_attendance_events_csv_success(client):
    token = login(client, "admin@northwind.demo")
    res = client.get("/api/v1/reports/attendance-events.csv", headers=auth(token))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    body = res.content
    assert body[:3] == b"\xef\xbb\xbf"
    text = body.decode("utf-8-sig")
    assert "Event ID" in text
    assert "Employee Name" in text


def test_attendance_events_csv_manager_allowed_viewer(client):
    """VIEWER_ROLES includes MANAGER — read export must succeed."""
    token = login(client, "manager@northwind.demo")
    res = client.get("/api/v1/reports/attendance-events.csv", headers=auth(token))
    assert res.status_code == 200, res.text


def test_attendance_events_csv_wrong_role_device_forbidden(client):
    """Device tokens must not export reports."""
    admin = login(client, "admin@northwind.demo")
    code_res = client.post("/api/v1/devices/enrollment-code", headers=auth(admin))
    assert code_res.status_code == 201, code_res.text
    enroll_code = code_res.json()["data"]["code"]
    enroll = client.post(
        "/api/v1/devices/enroll",
        json={"code": enroll_code, "name": "CSV Guard Tablet"},
    )
    assert enroll.status_code == 200, enroll.text
    device_token = enroll.json()["data"]["access_token"]
    res = client.get("/api/v1/reports/attendance-events.csv", headers=auth(device_token))
    assert res.status_code == 403


def test_attendance_events_csv_cross_org_isolation(client):
    """Org A export must not contain Org B employee codes."""
    acme_code = _seed_formula_employee_and_event("acme")
    nw_token = login(client, "admin@northwind.demo")
    nw_text = client.get("/api/v1/reports/attendance-events.csv", headers=auth(nw_token)).content.decode("utf-8-sig")
    assert acme_code not in nw_text

    acme_token = login(client, "admin@acme.demo")
    acme_text = client.get("/api/v1/reports/attendance-events.csv", headers=auth(acme_token)).content.decode("utf-8-sig")
    assert acme_code in acme_text
    assert "NW-E-1001" not in acme_text


def test_attendance_events_csv_formula_injection_escaped(client):
    emp_code = _seed_formula_employee_and_event("northwind")
    token = login(client, "admin@northwind.demo")
    res = client.get("/api/v1/reports/attendance-events.csv", headers=auth(token))
    assert res.status_code == 200
    text = res.content.decode("utf-8-sig")
    assert emp_code in text
    assert "'=HYPERLINK" in text
    for line in text.splitlines()[1:]:
        for cell in line.split(","):
            cell = cell.strip().strip('"')
            if cell.startswith(("=", "+", "-", "@")):
                pytest.fail(f"Unescaped formula cell: {cell!r}")


def test_attendance_events_csv_large_date_range_streams(client):
    token = login(client, "admin@northwind.demo")
    start = (date.today() - timedelta(days=3650)).isoformat()
    end = (date.today() + timedelta(days=365)).isoformat()
    res = client.get(
        f"/api/v1/reports/attendance-events.csv?start_date={start}&end_date={end}",
        headers=auth(token),
    )
    assert res.status_code == 200, res.text
    assert res.content[:3] == b"\xef\xbb\xbf"
    assert b"Event ID" in res.content


# ---------------------------------------------------------------------------
# Monthly summary CSV
# ---------------------------------------------------------------------------

def test_monthly_summary_csv_success(client):
    # Seed a completed day so work-hours derivation is exercised
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.slug == "northwind").one()
        emp = db.query(Employee).filter(Employee.organization_id == org.id).first()
        db.add(
            AttendanceRecord(
                organization_id=org.id,
                employee_id=emp.id,
                date=now.date(),
                check_in_at=now.replace(hour=9, minute=0, second=0, microsecond=0),
                check_out_at=now.replace(hour=17, minute=30, second=0, microsecond=0),
                status=AttendanceStatus.PRESENT,
                late_minutes=0,
            )
        )
        db.commit()
        emp_code = emp.employee_code

    token = login(client, "hr@northwind.demo")
    res = client.get(
        f"/api/v1/reports/monthly-summary.csv?year={now.year}&month={now.month}",
        headers=auth(token),
    )
    assert res.status_code == 200, res.text
    assert res.content[:3] == b"\xef\xbb\xbf"
    text = res.content.decode("utf-8-sig")
    assert "Employee Code" in text
    assert "Days Present" in text
    assert "Total Work Hours" in text
    assert emp_code in text
    assert "8.5" in text


def test_monthly_summary_csv_wrong_role_device_forbidden(client):
    admin = login(client, "admin@northwind.demo")
    code_res = client.post("/api/v1/devices/enrollment-code", headers=auth(admin))
    enroll_code = code_res.json()["data"]["code"]
    enroll = client.post(
        "/api/v1/devices/enroll",
        json={"code": enroll_code, "name": "Summary Guard"},
    )
    device_token = enroll.json()["data"]["access_token"]
    res = client.get("/api/v1/reports/monthly-summary.csv", headers=auth(device_token))
    assert res.status_code == 403


def test_monthly_summary_csv_cross_org_isolation(client):
    nw = login(client, "admin@northwind.demo")
    acme = login(client, "admin@acme.demo")
    nw_text = client.get("/api/v1/reports/monthly-summary.csv", headers=auth(nw)).content.decode("utf-8-sig")
    acme_text = client.get("/api/v1/reports/monthly-summary.csv", headers=auth(acme)).content.decode("utf-8-sig")
    # Employee codes are prefixed per org (NW- vs AC-)
    assert "NW-E-" in nw_text
    assert "NW-E-" not in acme_text
    assert "AC-E-" in acme_text


# ---------------------------------------------------------------------------
# Organization timezone setting
# ---------------------------------------------------------------------------

def test_organization_timezone_update_success(client):
    token = login(client, "admin@northwind.demo")
    res = client.patch(
        "/api/v1/organization",
        headers=auth(token),
        json={"timezone": "Asia/Kolkata"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["timezone"] == "Asia/Kolkata"
    get_res = client.get("/api/v1/organization", headers=auth(token))
    assert get_res.json()["data"]["timezone"] == "Asia/Kolkata"


def test_organization_timezone_wrong_role_forbidden(client):
    hr = login(client, "hr@northwind.demo")
    mgr = login(client, "manager@northwind.demo")
    for token in (hr, mgr):
        res = client.patch(
            "/api/v1/organization",
            headers=auth(token),
            json={"timezone": "America/New_York"},
        )
        assert res.status_code == 403, res.text


def test_organization_timezone_invalid_iana_rejected(client):
    token = login(client, "admin@northwind.demo")
    res = client.patch(
        "/api/v1/organization",
        headers=auth(token),
        json={"timezone": "Not/A_Real_Zone"},
    )
    assert res.status_code == 422


def test_organization_timezone_cross_org_isolation(client):
    """Updating org A must not change org B's timezone."""
    nw = login(client, "admin@northwind.demo")
    acme = login(client, "admin@acme.demo")
    client.patch("/api/v1/organization", headers=auth(nw), json={"timezone": "Europe/London"})
    client.patch("/api/v1/organization", headers=auth(acme), json={"timezone": "Asia/Tokyo"})
    nw_tz = client.get("/api/v1/organization", headers=auth(nw)).json()["data"]["timezone"]
    acme_tz = client.get("/api/v1/organization", headers=auth(acme)).json()["data"]["timezone"]
    assert nw_tz == "Europe/London"
    assert acme_tz == "Asia/Tokyo"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def test_audit_log_success_admin_only(client):
    admin = login(client, "admin@northwind.demo")
    res = client.get("/api/v1/audit-logs", headers=auth(admin))
    assert res.status_code == 200, res.text
    assert isinstance(res.json()["data"], list)


def test_audit_log_wrong_role_forbidden(client):
    hr = login(client, "hr@northwind.demo")
    mgr = login(client, "manager@northwind.demo")
    assert client.get("/api/v1/audit-logs", headers=auth(hr)).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=auth(mgr)).status_code == 403


def test_audit_log_cross_org_isolation(client):
    nw = login(client, "admin@northwind.demo")
    acme = login(client, "admin@acme.demo")
    # Distinct timezone updates create distinct audit targets per org
    client.patch("/api/v1/organization", headers=auth(nw), json={"timezone": "UTC"})
    client.patch("/api/v1/organization", headers=auth(acme), json={"timezone": "Pacific/Auckland"})
    nw_org_id = client.get("/api/v1/organization", headers=auth(nw)).json()["data"]["id"]
    acme_org_id = client.get("/api/v1/organization", headers=auth(acme)).json()["data"]["id"]
    nw_logs = client.get("/api/v1/audit-logs?limit=200", headers=auth(nw)).json()["data"]
    acme_logs = client.get("/api/v1/audit-logs?limit=200", headers=auth(acme)).json()["data"]
    nw_targets = {log["target_id"] for log in nw_logs if log.get("target_type") == "organization"}
    acme_targets = {log["target_id"] for log in acme_logs if log.get("target_type") == "organization"}
    assert nw_org_id in nw_targets
    assert acme_org_id in acme_targets
    assert acme_org_id not in nw_targets
    assert nw_org_id not in acme_targets

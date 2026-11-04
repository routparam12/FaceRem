"""
PoC test suite. The tenant-isolation cases are the important ones: they prove an admin in one
organization cannot reach another organization's employees, attendance or biometric data.
"""

import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(
    DATABASE_URL="sqlite:///./test_faceattend.db",
    JWT_SECRET="test-secret-that-is-long-enough-for-hs256-abcdef",
    FACE_ENGINE="stub",
    LIVENESS_MODE="disabled",
    LIVENESS_THRESHOLD="0.7",
    CHECKOUT_AFTER_MINUTES="240",
    SEED_DEMO_DATA="true",
)

DB_PATH = Path("./test_faceattend.db")
if DB_PATH.exists():
    DB_PATH.unlink()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

# Build the test schema the same way production does. Running migrations here rather than
# creating tables directly means a broken migration fails the suite instead of shipping.
_alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
_alembic.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
command.upgrade(_alembic, "head")

from app.routers.attendance import _late_minutes  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Shift  # noqa: E402
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


def face_image(seed: int) -> bytes:
    """A deterministic, distinctive image. Two different seeds must not match each other."""
    rng = __import__("random").Random(seed)
    image = Image.new("RGB", (128, 128))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(128 * 128)])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def face_frames(seed: int) -> dict:
    """Returns 3 distinct pose frames (front, left, right) for enrollment."""
    rng = __import__("random").Random(seed)
    base_data = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(128 * 128)]
    frames = []
    for variation in [0, 1, 2]:
        var_data = list(base_data)
        v_rng = __import__("random").Random(seed * 100 + variation)
        for _ in range(int(len(var_data) * 0.05 * variation)):
            idx = v_rng.randrange(len(var_data))
            var_data[idx] = (v_rng.randrange(256), v_rng.randrange(256), v_rng.randrange(256))
        img = Image.new("RGB", (128, 128))
        img.putdata(var_data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        frames.append(buf.getvalue())
    return {
        "front": ("front.png", frames[0], "image/png"),
        "left": ("left.png", frames[1], "image/png"),
        "right": ("right.png", frames[2], "image/png"),
    }


# ----------------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------------

def test_login_returns_tokens_in_envelope(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "hr@northwind.demo", "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["access_token"]


def test_bad_password_is_rejected_with_a_generic_code(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "hr@northwind.demo", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_unknown_organization_slug_is_indistinguishable_from_a_bad_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "hr@northwind.demo",
            "password": DEMO_PASSWORD,
            "organization_slug": "does-not-exist",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_endpoints_require_a_token(client):
    assert client.get("/api/v1/employees").status_code == 401


# ----------------------------------------------------------------------------------
# RBAC
# ----------------------------------------------------------------------------------

def test_employee_role_cannot_sign_in_or_access_endpoints(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@northwind.demo", "password": "demo12345"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_manager_can_read_but_not_create_employees(client):
    token = login(client, "manager@northwind.demo")
    assert client.get("/api/v1/employees", headers=auth(token)).status_code == 200

    response = client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={"employee_code": "NEW-1", "full_name": "Nope", "email": "nope@northwind.demo"},
    )
    assert response.status_code == 403


def test_hr_can_create_an_employee(client):
    token = login(client, "hr@northwind.demo")
    response = client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={
            "employee_code": "NW-9001",
            "full_name": "Neha Desai",
            "email": "neha@northwind.demo",
            "department": "Finance",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["face_enrolled"] is False


def test_duplicate_employee_code_conflicts(client):
    token = login(client, "hr@northwind.demo")
    response = client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={"employee_code": "NW-9001", "full_name": "Dup", "email": "dup@northwind.demo"},
    )
    assert response.status_code == 409


def test_super_admin_cannot_reach_tenant_data(client):
    """Platform staff must not read customer employees through the ordinary API."""
    token = login(client, "root@faceattend.platform")
    assert client.get("/api/v1/employees", headers=auth(token)).status_code == 403


def test_only_org_admin_reads_audit_logs(client):
    assert client.get("/api/v1/audit-logs", headers=auth(login(client, "hr@northwind.demo"))).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=auth(login(client, "admin@northwind.demo"))).status_code == 200


# ----------------------------------------------------------------------------------
# Face enrollment and recognition
# ----------------------------------------------------------------------------------

def _first_employee_id(client, token: str) -> str:
    return client.get("/api/v1/employees", headers=auth(token)).json()["data"][0]["id"]


def test_enrollment_requires_consent(client):
    token = login(client, "hr@northwind.demo")
    employee_id = _first_employee_id(client, token)
    response = client.post(
        f"/api/v1/employees/{employee_id}/face/enroll",
        headers=auth(token),
        files={"image": ("face.png", face_image(1), "image/png")},
        data={"consent": "false"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_enroll_then_recognize_checks_in_then_reports_already_present(client):
    hr = login(client, "hr@northwind.demo")
    employee_id = _first_employee_id(client, hr)
    image = face_image(42)

    enroll = client.post(
        f"/api/v1/employees/{employee_id}/face/enroll",
        headers=auth(hr),
        files=face_frames(42),
        data={"consent": "true"},
    )
    assert enroll.status_code == 200, enroll.text
    assert enroll.json()["data"]["face_enrolled"] is True

    kiosk = login(client, "kiosk@northwind.demo")
    first = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", image, "image/png")},
        data={"liveness_score": "0.95", "device_label": "lobby-1"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["event"] == "CHECK_IN"
    assert first.json()["data"]["employee_id"] == employee_id

    # An unattended gate gets scanned again by the same person minutes later. That must not
    # punch them out, and must not be an error the kiosk has to render as a failure.
    second = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", image, "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert second.status_code == 200, second.text
    repeat = second.json()["data"]
    assert repeat["event"] == "ALREADY_PRESENT"
    assert repeat["employee_id"] == employee_id
    assert repeat["check_in_at"] is not None, "the kiosk needs the original time to display"
    assert repeat["check_out_at"] is None, "a repeat scan must not end the day"


def test_repeat_scans_do_not_create_audit_noise(client):
    """A gate kiosk scans all day; only real events belong in the audit trail."""
    admin = login(client, "admin@northwind.demo")
    kiosk = login(client, "kiosk@northwind.demo")
    image = face_image(42)

    def check_in_rows() -> int:
        logs = client.get("/api/v1/audit-logs?limit=200", headers=auth(admin)).json()["data"]
        return sum(1 for row in logs if row["action"] == "attendance.check_in")

    before = check_in_rows()
    for _ in range(3):
        response = client.post(
            "/api/v1/attendance/recognize",
            headers=auth(kiosk),
            files={"image": ("scan.png", image, "image/png")},
            data={"liveness_score": "0.95"},
        )
        assert response.json()["data"]["event"] == "ALREADY_PRESENT"

    assert check_in_rows() == before


def test_scan_after_the_checkout_window_ends_the_day(client):
    """Back-date the check-in so the next scan falls outside CHECKOUT_AFTER_MINUTES."""
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import AttendanceRecord

    hr = login(client, "hr@northwind.demo")
    employee_id = _first_employee_id(client, hr)
    kiosk = login(client, "kiosk@northwind.demo")

    with SessionLocal() as db:
        record = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == employee_id)
            .order_by(AttendanceRecord.date.desc())
            .first()
        )
        record.check_in_at = datetime.now(timezone.utc) - timedelta(hours=9)
        record.check_out_at = None
        db.commit()

    response = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", face_image(42), "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["event"] == "CHECK_OUT"
    assert body["check_out_at"] is not None


def test_failed_liveness_blocks_recognition(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    kiosk = login(client, "kiosk@northwind.demo")
    response = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", face_image(42), "image/png")},
        data={"liveness_score": "0.10"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LIVENESS_FAILED"


def test_unknown_face_is_rejected_without_naming_a_near_match(client):
    kiosk = login(client, "kiosk@northwind.demo")
    response = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", face_image(999), "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "FACE_NOT_RECOGNIZED"
    assert "employee" not in str(body["error"]).lower()


def test_revoking_a_face_keeps_attendance_history(client):
    hr = login(client, "hr@northwind.demo")
    employee_id = _first_employee_id(client, hr)

    before = client.get("/api/v1/attendance", headers=auth(hr)).json()["data"]
    assert any(row["employee_id"] == employee_id for row in before)

    revoke = client.delete(f"/api/v1/employees/{employee_id}/face", headers=auth(hr))
    assert revoke.status_code == 200
    assert revoke.json()["data"]["attendance_retained"] is True

    after = client.get("/api/v1/attendance", headers=auth(hr)).json()["data"]
    assert any(row["employee_id"] == employee_id for row in after)

    # The revoked profile must no longer match.
    kiosk = login(client, "kiosk@northwind.demo")
    rescan = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", face_image(42), "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert rescan.status_code == 404


# ----------------------------------------------------------------------------------
# Tenant isolation
# ----------------------------------------------------------------------------------

def test_admin_cannot_read_another_organizations_employee(client):
    northwind = login(client, "hr@northwind.demo")
    acme = login(client, "hr@acme.demo")

    acme_employee_id = _first_employee_id(client, acme)
    response = client.get(f"/api/v1/employees/{acme_employee_id}", headers=auth(northwind))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


def test_admin_cannot_enroll_a_face_for_another_organization(client):
    northwind = login(client, "hr@northwind.demo")
    acme_employee_id = _first_employee_id(client, login(client, "hr@acme.demo"))

    response = client.post(
        f"/api/v1/employees/{acme_employee_id}/face/enroll",
        headers=auth(northwind),
        files={"image": ("face.png", face_image(7), "image/png")},
        data={"consent": "true"},
    )
    assert response.status_code == 404


def test_employee_lists_never_cross_organizations(client):
    northwind_codes = {
        row["employee_code"]
        for row in client.get(
            "/api/v1/employees", headers=auth(login(client, "hr@northwind.demo"))
        ).json()["data"]
    }
    acme_codes = {
        row["employee_code"]
        for row in client.get(
            "/api/v1/employees", headers=auth(login(client, "hr@acme.demo"))
        ).json()["data"]
    }
    assert northwind_codes and acme_codes
    assert northwind_codes.isdisjoint(acme_codes)


def test_a_face_enrolled_in_one_org_does_not_match_in_another(client):
    """The tenant filter runs before similarity, so an identical face is unknown next door."""
    image = face_image(31337)

    northwind_hr = login(client, "hr@northwind.demo")
    northwind_employee = _first_employee_id(client, northwind_hr)
    client.post(
        f"/api/v1/employees/{northwind_employee}/face/enroll",
        headers=auth(northwind_hr),
        files=face_frames(31337),
        data={"consent": "true"},
    )

    acme_kiosk = login(client, "kiosk@acme.demo")
    response = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(acme_kiosk),
        files={"image": ("scan.png", image, "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FACE_NOT_RECOGNIZED"


def test_employee_login_is_rejected_with_invalid_credentials(client):
    """Employee self-service login is removed in the kiosk-first model."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@northwind.demo", "password": "demo12345"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ----------------------------------------------------------------------------------
# Employee update and delete
# ----------------------------------------------------------------------------------

def test_update_employee_changes_only_the_given_fields(client):
    hr = login(client, "hr@northwind.demo")
    # A freshly created employee, so this doesn't disturb the seeded department/branch/shift
    # membership that other tests in this module assert on.
    created = client.post(
        "/api/v1/employees",
        headers=auth(hr),
        json={"employee_code": "NW-9050", "full_name": "Update Target", "email": "target@northwind.demo"},
    ).json()["data"]

    response = client.put(
        f"/api/v1/employees/{created['id']}",
        headers=auth(hr),
        json={"phone": "+91-9000000000", "department": "Platform"},
    )
    assert response.status_code == 200, response.text
    after = response.json()["data"]
    assert after["phone"] == "+91-9000000000"
    assert after["department"] == "Platform"
    assert after["full_name"] == created["full_name"]  # untouched field is preserved


def test_update_employee_with_unknown_shift_is_rejected(client):
    hr = login(client, "hr@northwind.demo")
    employee_id = _first_employee_id(client, hr)
    response = client.put(
        f"/api/v1/employees/{employee_id}",
        headers=auth(hr),
        json={"shift_name": "Night Owl Shift That Does Not Exist"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHIFT_NOT_FOUND"


def test_manager_cannot_update_or_delete_employees(client):
    manager = login(client, "manager@northwind.demo")
    employee_id = _first_employee_id(client, manager)
    assert client.put(
        f"/api/v1/employees/{employee_id}", headers=auth(manager), json={"phone": "1"}
    ).status_code == 403
    assert client.delete(
        f"/api/v1/employees/{employee_id}", headers=auth(manager)
    ).status_code == 403


def test_delete_employee_soft_deletes_and_revokes_face_and_hides_from_default_list(client):
    hr = login(client, "hr@northwind.demo")
    create = client.post(
        "/api/v1/employees",
        headers=auth(hr),
        json={"employee_code": "NW-9100", "full_name": "Temp Worker", "email": "temp@northwind.demo"},
    )
    employee_id = create.json()["data"]["id"]

    enroll = client.post(
        f"/api/v1/employees/{employee_id}/face/enroll",
        headers=auth(hr),
        files=face_frames(5001),
        data={"consent": "true"},
    )
    assert enroll.status_code == 200

    delete = client.delete(f"/api/v1/employees/{employee_id}", headers=auth(hr))
    assert delete.status_code == 200
    assert delete.json()["data"]["face_profiles_revoked"] == 3

    listed = client.get("/api/v1/employees", headers=auth(hr)).json()["data"]
    assert all(row["id"] != employee_id for row in listed)

    listed_all = client.get(
        "/api/v1/employees", headers=auth(hr), params={"include_inactive": "true"}
    ).json()["data"]
    assert any(row["id"] == employee_id and row["is_active"] is False for row in listed_all)

    kiosk = login(client, "kiosk@northwind.demo")
    rescan = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", face_image(5001), "image/png")},
        data={"liveness_score": "0.95"},
    )
    assert rescan.status_code == 404


def test_admin_cannot_update_another_organizations_employee(client):
    northwind = login(client, "hr@northwind.demo")
    acme_employee_id = _first_employee_id(client, login(client, "hr@acme.demo"))
    response = client.put(
        f"/api/v1/employees/{acme_employee_id}",
        headers=auth(northwind),
        json={"phone": "0"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EMPLOYEE_NOT_FOUND"


# ----------------------------------------------------------------------------------
# Departments, branches and shifts
# ----------------------------------------------------------------------------------

def test_departments_are_created_implicitly_by_employee_creation_and_listed_with_head_count(client):
    hr = login(client, "hr@northwind.demo")
    departments = client.get("/api/v1/departments", headers=auth(hr)).json()["data"]
    names = {d["name"] for d in departments}
    assert "Engineering" in names
    engineering = next(d for d in departments if d["name"] == "Engineering")
    assert engineering["head_count"] >= 1


def test_creating_a_duplicate_department_conflicts(client):
    hr = login(client, "hr@northwind.demo")
    first = client.post("/api/v1/departments", headers=auth(hr), json={"name": "Legal"})
    assert first.status_code == 201
    second = client.post("/api/v1/departments", headers=auth(hr), json={"name": "legal"})
    assert second.status_code == 409


def test_cannot_delete_a_department_still_in_use(client):
    hr = login(client, "hr@northwind.demo")
    departments = client.get("/api/v1/departments", headers=auth(hr)).json()["data"]
    engineering_id = next(d["id"] for d in departments if d["name"] == "Engineering")
    response = client.delete(f"/api/v1/departments/{engineering_id}", headers=auth(hr))
    assert response.status_code == 409


def test_branch_and_shift_crud_and_employee_assignment(client):
    hr = login(client, "hr@northwind.demo")

    branch = client.post(
        "/api/v1/branches", headers=auth(hr), json={"name": "Riverside", "city": "Pune"}
    )
    assert branch.status_code == 201
    assert branch.json()["data"]["head_count"] == 0

    shift = client.post(
        "/api/v1/shifts",
        headers=auth(hr),
        json={"name": "Night Shift", "start_time": "22:00", "end_time": "06:00", "grace_minutes": 5},
    )
    assert shift.status_code == 201

    create = client.post(
        "/api/v1/employees",
        headers=auth(hr),
        json={
            "employee_code": "NW-9200",
            "full_name": "Night Owl",
            "email": "owl@northwind.demo",
            "branch": "Riverside",
            "shift_name": "Night Shift",
        },
    )
    assert create.status_code == 201
    employee = create.json()["data"]
    assert employee["branch"] == "Riverside"
    assert employee["shift_name"] == "Night Shift"

    branches = client.get("/api/v1/branches", headers=auth(hr)).json()["data"]
    riverside = next(b for b in branches if b["name"] == "Riverside")
    assert riverside["head_count"] == 1

    # In-use branch cannot be deleted.
    assert client.delete(
        f"/api/v1/branches/{riverside['id']}", headers=auth(hr)
    ).status_code == 409


def test_late_minutes_uses_the_employee_shift_when_assigned():
    """Deterministic unit test for the function `recognize()` calls — avoids depending on the
    wall-clock time the test happens to run at."""
    moment = datetime(2024, 1, 1, 9, 20, tzinfo=timezone.utc)
    shift = Shift(start_time="09:00", grace_minutes=10)
    assert _late_minutes(moment, shift) == 10


def test_late_minutes_falls_back_to_the_organization_default_without_a_shift():
    moment = datetime(2024, 1, 1, 9, 25, tzinfo=timezone.utc)
    # Test env leaves SHIFT_START_HOUR/SHIFT_GRACE_MINUTES at their defaults: 9 and 10.
    assert _late_minutes(moment, None) == 15


def test_departments_branches_and_shifts_never_cross_organizations(client):
    acme_hr = login(client, "hr@acme.demo")
    acme_departments = {d["name"] for d in client.get("/api/v1/departments", headers=auth(acme_hr)).json()["data"]}
    northwind_hr = login(client, "hr@northwind.demo")
    northwind_departments = {
        d["name"] for d in client.get("/api/v1/departments", headers=auth(northwind_hr)).json()["data"]
    }
    # Both orgs seed an "Engineering" department independently; the row ids must differ.
    acme_ids = {d["id"] for d in client.get("/api/v1/departments", headers=auth(acme_hr)).json()["data"]}
    northwind_ids = {
        d["id"] for d in client.get("/api/v1/departments", headers=auth(northwind_hr)).json()["data"]
    }
    assert acme_ids.isdisjoint(northwind_ids)


# ---------------------------------------------------------------------------
# SaaS onboarding and account management
# ---------------------------------------------------------------------------

def _signup(client: TestClient, slug: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": f"Tenant {slug}",
            "organization_slug": slug,
            "full_name": "Founding Admin",
            "email": email,
            "password": "signup-password-1",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_signup_creates_an_organization_with_its_first_admin(client):
    data = _signup(client, "zephyr", "founder@zephyr.demo")
    assert data["organization_slug"] == "zephyr"

    me = client.get("/api/v1/auth/me", headers=auth(data["access_token"])).json()["data"]
    assert me["role"] == "ORGANIZATION_ADMIN"
    assert me["organization_id"] == data["organization_id"]


def test_signup_rejects_a_taken_organization_code(client):
    _signup(client, "duplicate-co", "first@duplicate.demo")
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Duplicate Again",
            "organization_slug": "duplicate-co",
            "full_name": "Second Founder",
            "email": "second@duplicate.demo",
            "password": "signup-password-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_a_new_tenant_cannot_see_another_tenants_people(client):
    """The signup path must land inside its own tenant, not a shared pool."""
    data = _signup(client, "isolated-co", "founder@isolated.demo")
    employees = client.get("/api/v1/employees", headers=auth(data["access_token"]))
    assert employees.status_code == 200
    assert employees.json()["data"] == []


def test_hr_cannot_create_an_org_admin(client):
    """The escalation that matters: HR must not be able to promote anyone to ORG_ADMIN."""
    hr = login(client, "hr@northwind.demo")
    response = client.post(
        "/api/v1/users",
        headers=auth(hr),
        json={
            "full_name": "Sneaky Admin",
            "email": "sneaky@northwind.demo",
            "password": "another-password-1",
            "role": "ORGANIZATION_ADMIN",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_hr_cannot_create_an_employee_user_account(client):
    hr = login(client, "hr@northwind.demo")
    created = client.post(
        "/api/v1/users",
        headers=auth(hr),
        json={
            "full_name": "New Starter",
            "email": "new.starter@northwind.demo",
            "password": "starter-password-1",
            "role": "EMPLOYEE",
        },
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "VALIDATION_ERROR"


def test_hr_can_create_a_manager_login_that_works(client):
    hr = login(client, "hr@northwind.demo")
    created = client.post(
        "/api/v1/users",
        headers=auth(hr),
        json={
            "full_name": "New Manager",
            "email": "new.manager@northwind.demo",
            "password": "manager-password-1",
            "role": "MANAGER",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["role"] == "MANAGER"

    token = login(client, "new.manager@northwind.demo", "manager-password-1")
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()["data"]
    assert me["role"] == "MANAGER"


def test_nobody_can_change_their_own_role(client):
    admin_token = login(client, "admin@northwind.demo")
    me = client.get("/api/v1/auth/me", headers=auth(admin_token)).json()["data"]
    response = client.patch(
        f"/api/v1/users/{me['id']}", headers=auth(admin_token), json={"role": "MANAGER"}
    )
    assert response.status_code == 403


def test_the_last_org_admin_cannot_be_locked_out(client):
    data = _signup(client, "solo-co", "solo@solo.demo")
    admin_token = data["access_token"]
    other = client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={
            "full_name": "HR Person",
            "email": "hr@solo.demo",
            "password": "hr-password-1",
            "role": "HR_ADMIN",
        },
    ).json()["data"]

    # HR may not demote the only admin...
    hr_token = login(client, "hr@solo.demo", "hr-password-1")
    assert client.patch(
        f"/api/v1/users/{data['user_id']}", headers=auth(hr_token), json={"role": "MANAGER"}
    ).status_code == 403

    # ...and the admin cannot strand the tenant by demoting themselves either.
    assert client.patch(
        f"/api/v1/users/{data['user_id']}", headers=auth(admin_token), json={"role": "MANAGER"}
    ).status_code == 403
    assert other["role"] == "HR_ADMIN"


def test_users_from_another_tenant_are_not_reachable(client):
    a = _signup(client, "tenant-a", "a@tenant.demo")
    b = _signup(client, "tenant-b", "b@tenant.demo")
    response = client.patch(
        f"/api/v1/users/{b['user_id']}", headers=auth(a["access_token"]), json={"full_name": "Hijacked"}
    )
    assert response.status_code == 404, "a cross-tenant id must not even be confirmed to exist"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def test_refresh_rotates_and_logout_revokes(client):
    data = _signup(client, "session-co", "session@session.demo")
    first = data["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["data"]["refresh_token"]
    assert second != first, "the refresh token must rotate"

    logout = client.post(
        "/api/v1/auth/logout",
        headers=auth(data["access_token"]),
        json={"refresh_token": second},
    )
    assert logout.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_replaying_a_used_refresh_token_ends_every_session(client):
    """A token presented twice is the signature of theft, so all sessions are dropped."""
    data = _signup(client, "replay-co", "replay@replay.demo")
    first = data["refresh_token"]

    live = client.post("/api/v1/auth/refresh", json={"refresh_token": first}).json()["data"]
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "TOKEN_REUSED"

    # The token the thief did not have is dead too.
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": live["refresh_token"]}
    ).status_code == 401


def test_changing_a_password_ends_other_sessions(client):
    data = _signup(client, "rotate-co", "rotate@rotate.demo")
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=auth(data["access_token"]),
        json={"current_password": "signup-password-1", "new_password": "a-better-password-2"},
    )
    assert changed.status_code == 200, changed.text

    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    ).status_code == 401
    assert login(client, "rotate@rotate.demo", "a-better-password-2")


def test_change_password_requires_the_current_one(client):
    data = _signup(client, "wrongpw-co", "wrongpw@wrongpw.demo")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth(data["access_token"]),
        json={"current_password": "not-the-password", "new_password": "a-better-password-2"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_deactivating_a_user_drops_their_live_session(client):
    data = _signup(client, "deactivate-co", "owner@deactivate.demo")
    admin_token = data["access_token"]
    member = client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={
            "full_name": "Temp Staff",
            "email": "temp@deactivate.demo",
            "password": "temp-password-1",
            "role": "MANAGER",
        },
    ).json()["data"]

    member_login = client.post(
        "/api/v1/auth/login",
        json={"email": "temp@deactivate.demo", "password": "temp-password-1"},
    ).json()["data"]

    client.patch(
        f"/api/v1/users/{member['id']}", headers=auth(admin_token), json={"is_active": False}
    )

    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": member_login["refresh_token"]}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "temp@deactivate.demo", "password": "temp-password-1"},
    ).status_code == 401


# ---------------------------------------------------------------------------
# Subscription and seat limits
# ---------------------------------------------------------------------------

def test_a_new_tenant_starts_on_a_metered_trial(client):
    data = _signup(client, "metered-co", "owner@metered.demo")
    sub = client.get("/api/v1/subscription", headers=auth(data["access_token"]))
    assert sub.status_code == 200, sub.text
    body = sub.json()["data"]
    assert body["plan"] == "TRIAL"
    assert body["status"] == "TRIALING"
    assert body["seats_used"] == 0
    assert body["seats_available"] == body["seat_limit"] > 0


def test_adding_people_consumes_seats(client):
    data = _signup(client, "seats-co", "owner@seats.demo")
    token = data["access_token"]
    client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={"employee_code": "S-1", "full_name": "First Hire", "email": "first@seats.demo"},
    )
    body = client.get("/api/v1/subscription", headers=auth(token)).json()["data"]
    assert body["seats_used"] == 1
    assert body["seats_available"] == body["seat_limit"] - 1


def test_the_seat_limit_is_enforced_when_it_runs_out(client):
    """A trial tenant must not be able to add people without limit."""
    from app.db import SessionLocal
    from app.models import Subscription

    data = _signup(client, "capped-co", "owner@capped.demo")
    token = data["access_token"]

    # Shrink the plan to one seat rather than creating 25 employees.
    with SessionLocal() as db:
        sub = db.query(Subscription).filter(
            Subscription.organization_id == data["organization_id"]
        ).one()
        sub.seat_limit = 1
        db.commit()

    first = client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={"employee_code": "C-1", "full_name": "Only Hire", "email": "only@capped.demo"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/employees",
        headers=auth(token),
        json={"employee_code": "C-2", "full_name": "One Too Many", "email": "extra@capped.demo"},
    )
    assert second.status_code == 402
    assert second.json()["error"]["code"] == "SEAT_LIMIT_REACHED"


def test_a_cancelled_subscription_blocks_sign_in(client):
    from app.db import SessionLocal
    from app.models import Subscription, SubscriptionStatus

    data = _signup(client, "cancelled-co", "owner@cancelled.demo")
    assert login(client, "owner@cancelled.demo", "signup-password-1")

    with SessionLocal() as db:
        sub = db.query(Subscription).filter(
            Subscription.organization_id == data["organization_id"]
        ).one()
        sub.status = SubscriptionStatus.CANCELLED
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@cancelled.demo", "password": "signup-password-1"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SUBSCRIPTION_CANCELLED"


def test_past_due_still_allows_sign_in(client):
    """Failed payment starts dunning; locking people out of attendance is worse than chasing."""
    from app.db import SessionLocal
    from app.models import Subscription, SubscriptionStatus

    data = _signup(client, "pastdue-co", "owner@pastdue.demo")
    with SessionLocal() as db:
        sub = db.query(Subscription).filter(
            Subscription.organization_id == data["organization_id"]
        ).one()
        sub.status = SubscriptionStatus.PAST_DUE
        db.commit()

    assert login(client, "owner@pastdue.demo", "signup-password-1")


def test_subscription_is_not_visible_to_ordinary_staff(client):
    hr = login(client, "manager@northwind.demo")
    assert client.get("/api/v1/subscription", headers=auth(hr)).status_code == 403

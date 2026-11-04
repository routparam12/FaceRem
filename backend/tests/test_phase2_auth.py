"""Tests for Phase 2: Auth and Identity Model.

Comprehensive suite covering:
1. Roles and Scoping (SUPER_ADMIN, ORGANIZATION_ADMIN, HR_ADMIN, MANAGER, ATTENDANCE_DEVICE).
2. Admin sign-in, RFC 6238 TOTP 2FA, recovery codes, production mandatory 2FA.
3. Attendance devices (enrollment code, expiry, wrong-org isolation, single-use, immediate revocation).
4. Employee PIN fallback (hashing, lockout after 5 failures, lockout expiry, per-IP and per-device rate limiting).
5. Cross-tenant isolation (devices, audit logs, employees).
6. Manager restricted to read-only on devices in scope.
7. Legacy kiosk login configurable and disabled in production.
8. Startup check requiring Redis in production.
9. Alembic migration downgrade and re-upgrade.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(
    DATABASE_URL="sqlite:///./test_phase2.db",
    JWT_SECRET="test-secret-that-is-long-enough-for-hs256-abcdef",
    FACE_ENGINE="stub",
    LIVENESS_MODE="client_attested",
    LIVENESS_THRESHOLD="0.7",
    CHECKOUT_AFTER_MINUTES="240",
    SEED_DEMO_DATA="true",
)

DB_PATH = Path("./test_phase2.db")
if DB_PATH.exists():
    DB_PATH.unlink()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
_alembic.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
command.upgrade(_alembic, "head")

import pyotp  # noqa: E402
import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.main import app, _assert_production_requirements  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AttendanceDevice,
    Branch,
    Department,
    DeviceEnrollmentCode,
    DeviceMode,
    DeviceStatus,
    Employee,
    Organization,
    Role,
    User,
)
from app.rate_limiter import reset_memory_rate_limiter  # noqa: E402
from app.security import (  # noqa: E402
    create_device_access_token,
    decrypt_totp_secret,
    hash_password,
    hash_pin,
)
from app.seed import DEMO_PASSWORD  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


# ----------------------------------------------------------------------------------
# 1. Checklist Item: Employee-only sign-in rejected
# ----------------------------------------------------------------------------------

def test_employee_only_signin_rejected(client):
    """Employees have NO login accounts in the kiosk-first model and are rejected with generic error."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@northwind.demo", "password": DEMO_PASSWORD},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ----------------------------------------------------------------------------------
# 2. Checklist Item: Manager / HR denied on another branch/department
# ----------------------------------------------------------------------------------

def test_manager_hr_denied_on_another_branch_department(client):
    """Managers and HR scoped to a branch/dept cannot see or alter resources in other scopes."""
    admin_token = login(client, "admin@northwind.demo")

    # Create two branches and two departments
    b1 = client.post("/api/v1/branches", headers=auth(admin_token), json={"name": "Scope Branch Alpha"}).json()["data"]
    b2 = client.post("/api/v1/branches", headers=auth(admin_token), json={"name": "Scope Branch Beta"}).json()["data"]
    d1 = client.post("/api/v1/departments", headers=auth(admin_token), json={"name": "Scope Dept Alpha"}).json()["data"]
    d2 = client.post("/api/v1/departments", headers=auth(admin_token), json={"name": "Scope Dept Beta"}).json()["data"]

    # Create employees in each scope
    emp1 = client.post(
        "/api/v1/employees",
        headers=auth(admin_token),
        json={
            "employee_code": "SCOPE-EMP-A",
            "full_name": "Emp Scope Alpha",
            "email": "alpha.scope@demo.com",
            "branch_id": b1["id"],
            "department_id": d1["id"],
        },
    ).json()["data"]

    emp2 = client.post(
        "/api/v1/employees",
        headers=auth(admin_token),
        json={
            "employee_code": "SCOPE-EMP-B",
            "full_name": "Emp Scope Beta",
            "email": "beta.scope@demo.com",
            "branch_id": b2["id"],
            "department_id": d2["id"],
        },
    ).json()["data"]

    # 1. Test Manager scoped to Branch Alpha / Dept Alpha
    client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={
            "full_name": "Manager Scope Alpha",
            "email": "mgr.alpha.scope@demo.com",
            "password": "manager-password-1",
            "role": "MANAGER",
            "branch_id": b1["id"],
            "department_id": d1["id"],
        },
    )
    mgr_token = login(client, "mgr.alpha.scope@demo.com", "manager-password-1")

    # Manager sees emp1 in list, emp2 is filtered out
    mgr_employees = client.get("/api/v1/employees", headers=auth(mgr_token)).json()["data"]
    mgr_emp_ids = [e["id"] for e in mgr_employees]
    assert emp1["id"] in mgr_emp_ids
    assert emp2["id"] not in mgr_emp_ids

    # Manager can access emp1, but gets 403 FORBIDDEN accessing emp2
    assert client.get(f"/api/v1/employees/{emp1['id']}", headers=auth(mgr_token)).status_code == 200
    res_mgr_emp2 = client.get(f"/api/v1/employees/{emp2['id']}", headers=auth(mgr_token))
    assert res_mgr_emp2.status_code == 403
    assert res_mgr_emp2.json()["error"]["code"] == "FORBIDDEN"

    # 2. Test HR Admin scoped to Branch Alpha
    client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={
            "full_name": "HR Scope Alpha",
            "email": "hr.alpha.scope@demo.com",
            "password": "hr-password-1",
            "role": "HR_ADMIN",
            "branch_id": b1["id"],
        },
    )
    hr_token = login(client, "hr.alpha.scope@demo.com", "hr-password-1")

    # HR admin sees emp1, but emp2 in Branch Beta is forbidden
    assert client.get(f"/api/v1/employees/{emp1['id']}", headers=auth(hr_token)).status_code == 200
    res_hr_emp2 = client.get(f"/api/v1/employees/{emp2['id']}", headers=auth(hr_token))
    assert res_hr_emp2.status_code == 403
    assert res_hr_emp2.json()["error"]["code"] == "FORBIDDEN"


# ----------------------------------------------------------------------------------
# 3. Checklist Item: Admin Sign-In & TOTP 2FA Flow
# ----------------------------------------------------------------------------------

def test_totp_setup_and_login_flow(client):
    """Admin configures TOTP 2FA, verifies, and subsequent logins require 2FA challenge."""
    try:
        admin_token = login(client, "admin@northwind.demo")

        # Step 1: Request TOTP setup
        setup_res = client.post("/api/v1/auth/totp/setup", headers=auth(admin_token))
        assert setup_res.status_code == 200
        setup_data = setup_res.json()["data"]
        secret = setup_data["secret"]
        assert setup_data["provisioning_uri"].startswith("otpauth://totp/")

        # Secret must be encrypted in db
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "admin@northwind.demo").first()
            assert user.totp_secret is not None
            assert user.totp_secret != secret  # must be ciphertext, not plaintext
            decrypted = decrypt_totp_secret(user.totp_secret)
            assert decrypted == secret

        # Step 2: Verify with invalid code -> rejected
        bad_res = client.post(
            "/api/v1/auth/totp/verify",
            headers=auth(admin_token),
            json={"code": "000000"},
        )
        assert bad_res.status_code == 401
        assert bad_res.json()["error"]["code"] == "TOTP_INVALID"

        # Step 3: Verify with valid pyotp code -> success, returns recovery codes
        valid_code = pyotp.TOTP(secret).now()
        verify_res = client.post(
            "/api/v1/auth/totp/verify",
            headers=auth(admin_token),
            json={"code": valid_code},
        )
        assert verify_res.status_code == 200
        verify_data = verify_res.json()["data"]
        recovery_codes = verify_data["recovery_codes"]
        assert len(recovery_codes) == 8

        # Step 4: Login with 2FA enabled returns TOTP challenge
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@northwind.demo", "password": DEMO_PASSWORD},
        )
        assert login_res.status_code == 200
        login_data = login_res.json()["data"]
        assert login_data["totp_required"] is True
        challenge_token = login_data["challenge_token"]

        # Step 5: Complete challenge with invalid code -> rejected
        bad_challenge = client.post(
            "/api/v1/auth/totp/login",
            json={"challenge_token": challenge_token, "code": "999999"},
        )
        assert bad_challenge.status_code == 401
        assert bad_challenge.json()["error"]["code"] == "TOTP_INVALID"

        # Step 6: Complete challenge with valid code -> returns access token
        new_code = pyotp.TOTP(secret).now()
        good_challenge = client.post(
            "/api/v1/auth/totp/login",
            json={"challenge_token": challenge_token, "code": new_code},
        )
        assert good_challenge.status_code == 200
        assert good_challenge.json()["data"]["access_token"]

    finally:
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == "admin@northwind.demo").first()
            if u:
                u.is_totp_enabled = False
                u.totp_secret = None
                u.recovery_codes = None
                db.commit()


# ----------------------------------------------------------------------------------
# 4. Checklist Item: Recovery code single use
# ----------------------------------------------------------------------------------

def test_recovery_code_single_use(client):
    """One-time recovery codes succeed on first use and are invalidated immediately for subsequent attempts."""
    try:
        admin_token = login(client, "admin@northwind.demo")
        setup_res = client.post("/api/v1/auth/totp/setup", headers=auth(admin_token))
        secret = setup_res.json()["data"]["secret"]
        valid_code = pyotp.TOTP(secret).now()
        verify_res = client.post(
            "/api/v1/auth/totp/verify",
            headers=auth(admin_token),
            json={"code": valid_code},
        )
        recovery_codes = verify_res.json()["data"]["recovery_codes"]
        rc = recovery_codes[0]

        # Login to get challenge token
        login_res1 = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@northwind.demo", "password": DEMO_PASSWORD},
        )
        ch_token1 = login_res1.json()["data"]["challenge_token"]

        # First use of recovery code succeeds
        first_use = client.post(
            "/api/v1/auth/totp/login",
            json={"challenge_token": ch_token1, "code": rc},
        )
        assert first_use.status_code == 200
        assert first_use.json()["data"]["access_token"]

        # Login again for a second challenge token
        login_res2 = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@northwind.demo", "password": DEMO_PASSWORD},
        )
        ch_token2 = login_res2.json()["data"]["challenge_token"]

        # Attempting to reuse the same recovery code must fail
        reuse_attempt = client.post(
            "/api/v1/auth/totp/login",
            json={"challenge_token": ch_token2, "code": rc},
        )
        assert reuse_attempt.status_code == 401
        assert reuse_attempt.json()["error"]["code"] == "TOTP_INVALID"

    finally:
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == "admin@northwind.demo").first()
            if u:
                u.is_totp_enabled = False
                u.totp_secret = None
                u.recovery_codes = None
                db.commit()


# ----------------------------------------------------------------------------------
# 5. Checklist Item: Mandatory 2FA in production mode
# ----------------------------------------------------------------------------------

def test_mandatory_2fa_in_production_mode(client, monkeypatch):
    """In production, admins without 2FA receive a scoped bootstrap token locked to TOTP setup."""
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")

    try:
        # Admin logs in without 2FA enabled
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@northwind.demo", "password": DEMO_PASSWORD},
        )
        assert res.status_code == 200
        data = res.json()["data"]
        bootstrap_token = data["access_token"]
        assert bootstrap_token

        # Attempting to access regular tenant resources with bootstrap token is forbidden
        emp_res = client.get("/api/v1/employees", headers=auth(bootstrap_token))
        assert emp_res.status_code == 403
        assert emp_res.json()["error"]["code"] == "TOTP_REQUIRED"

        # The bootstrap token IS permitted to access TOTP setup
        setup_res = client.post("/api/v1/auth/totp/setup", headers=auth(bootstrap_token))
        assert setup_res.status_code == 200
        assert "secret" in setup_res.json()["data"]

    finally:
        monkeypatch.setattr(settings, "app_env", "development")


# ----------------------------------------------------------------------------------
# 6. Checklist Item: Code reuse rejected
# ----------------------------------------------------------------------------------

def test_code_reuse_rejected(client):
    """Single-use enrollment codes cannot be exchanged more than once."""
    admin_token = login(client, "admin@northwind.demo")
    code = client.post(
        "/api/v1/devices/enrollment-code",
        headers=auth(admin_token),
    ).json()["data"]["code"]

    # First exchange succeeds
    res1 = client.post(
        "/api/v1/devices/enroll",
        json={"code": code, "name": "Device Primary"},
    )
    assert res1.status_code == 200
    assert res1.json()["data"]["access_token"]

    # Second exchange with the same code fails
    res2 = client.post(
        "/api/v1/devices/enroll",
        json={"code": code, "name": "Device Duplicate"},
    )
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "CODE_INVALID_OR_EXPIRED"


# ----------------------------------------------------------------------------------
# 7. Checklist Item: Expired enrollment code rejected
# ----------------------------------------------------------------------------------

def test_expired_enrollment_code_rejected(client):
    """Enrollment codes past their 10-minute TTL are rejected."""
    admin_token = login(client, "admin@northwind.demo")
    code = client.post(
        "/api/v1/devices/enrollment-code",
        headers=auth(admin_token),
    ).json()["data"]["code"]

    code_hash = hashlib.sha256(code.strip().upper().encode()).hexdigest()
    # Backdate the expiration in database
    with SessionLocal() as db:
        record = db.query(DeviceEnrollmentCode).filter(DeviceEnrollmentCode.code_hash == code_hash).first()
        assert record is not None
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

    # Attempt to enroll with expired code
    res = client.post(
        "/api/v1/devices/enroll",
        json={"code": code, "name": "Expired Device"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "CODE_INVALID_OR_EXPIRED"


# ----------------------------------------------------------------------------------
# 8. Checklist Item: Wrong-organization code & device isolation
# ----------------------------------------------------------------------------------

def test_wrong_organization_code_and_device_isolation(client):
    """An enrollment code issued in Org B cannot be managed by Org A; cross-org device calls fail."""
    admin_nw = login(client, "admin@northwind.demo")
    admin_acme = login(client, "admin@acme.demo")

    # Acme generates an enrollment code
    code_acme = client.post(
        "/api/v1/devices/enrollment-code",
        headers=auth(admin_acme),
        json={"device_name": "Acme Kiosk Isol"},
    ).json()["data"]["code"]

    # Device enrolls into Acme
    acme_enroll = client.post(
        "/api/v1/devices/enroll",
        json={"code": code_acme, "name": "Acme Kiosk Isol"},
    ).json()["data"]
    acme_device_token = acme_enroll["access_token"]
    acme_device_id = acme_enroll["device_id"]

    # Northwind admin cannot see Acme device in device list
    nw_devices = client.get("/api/v1/devices", headers=auth(admin_nw)).json()["data"]
    assert all(d["id"] != acme_device_id for d in nw_devices)

    # Northwind admin cannot mutate or revoke Acme device (404 Not Found)
    res_revoke = client.post(f"/api/v1/devices/{acme_device_id}/revoke", headers=auth(admin_nw))
    assert res_revoke.status_code == 404
    assert res_revoke.json()["error"]["code"] == "NOT_FOUND"

    res_patch = client.patch(f"/api/v1/devices/{acme_device_id}", headers=auth(admin_nw), json={"name": "Hacked"})
    assert res_patch.status_code == 404

    # Acme device cannot verify a Northwind employee PIN (employee not found in Acme)
    nw_emp = client.get("/api/v1/employees", headers=auth(admin_nw)).json()["data"][0]
    pin_res = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(acme_device_token),
        json={"employee_code": nw_emp["employee_code"], "pin": "1234"},
    )
    assert pin_res.status_code == 401
    assert pin_res.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ----------------------------------------------------------------------------------
# 9. Checklist Item: Revoked device rejected on next request
# ----------------------------------------------------------------------------------

def test_revoked_device_rejected_on_next_request(client):
    """Revoking a device immediately invalidates its credential on the very next API call."""
    admin_token = login(client, "admin@northwind.demo")

    code = client.post("/api/v1/devices/enrollment-code", headers=auth(admin_token)).json()["data"]["code"]
    enroll = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Revoke Kiosk"}).json()["data"]
    dev_token = enroll["access_token"]
    dev_id = enroll["device_id"]

    # Revoke device
    revoke_res = client.post(f"/api/v1/devices/{dev_id}/revoke", headers=auth(admin_token))
    assert revoke_res.status_code == 200
    assert revoke_res.json()["data"]["status"] == "REVOKED"

    # The very next device request is rejected immediately with 401 DEVICE_NOT_AUTHORIZED
    res = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(dev_token),
        json={"employee_code": "NON_EXISTENT", "pin": "0000"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "DEVICE_NOT_AUTHORIZED"


# ----------------------------------------------------------------------------------
# 10. Checklist Item: PIN lockout and lockout expiry
# ----------------------------------------------------------------------------------

def test_pin_lockout_and_lockout_expiry(client):
    """5 failed PIN attempts lock out the employee for 15 minutes; lockout expires automatically."""
    admin_token = login(client, "admin@northwind.demo")

    # Create device
    code = client.post("/api/v1/devices/enrollment-code", headers=auth(admin_token)).json()["data"]["code"]
    dev_token = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Lockout Kiosk"}).json()["data"]["access_token"]

    # Create employee and set PIN
    emp = client.post(
        "/api/v1/employees",
        headers=auth(admin_token),
        json={
            "employee_code": "LOCKOUT-EMP",
            "full_name": "Lockout Employee",
            "email": "lockout@test.demo",
        },
    ).json()["data"]

    client.post(f"/api/v1/employees/{emp['id']}/pin", headers=auth(admin_token), json={"pin": "7777"})
    reset_memory_rate_limiter()

    # 4 failed attempts
    for _ in range(4):
        res = client.post(
            "/api/v1/attendance/pin-verify",
            headers=auth(dev_token),
            json={"employee_code": "LOCKOUT-EMP", "pin": "wrong"},
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # 5th failed attempt triggers lockout
    res5 = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(dev_token),
        json={"employee_code": "LOCKOUT-EMP", "pin": "wrong"},
    )
    assert res5.status_code == 401

    # 6th attempt with correct PIN is blocked with PIN_LOCKED (423)
    locked_res = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(dev_token),
        json={"employee_code": "LOCKOUT-EMP", "pin": "7777"},
    )
    assert locked_res.status_code == 423
    assert locked_res.json()["error"]["code"] == "PIN_LOCKED"

    # Simulate lockout expiry by winding back pin_locked_until past now
    with SessionLocal() as db:
        emp_record = db.query(Employee).filter(Employee.id == emp["id"]).first()
        emp_record.pin_locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    reset_memory_rate_limiter()

    # Now correct PIN succeeds immediately
    unlocked_res = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(dev_token),
        json={"employee_code": "LOCKOUT-EMP", "pin": "7777"},
    )
    assert unlocked_res.status_code == 200
    assert unlocked_res.json()["data"]["employee_id"] == emp["id"]


# ----------------------------------------------------------------------------------
# 11. Checklist Item: Audit-log and device isolation between organizations
# ----------------------------------------------------------------------------------

def test_audit_log_and_device_isolation_between_organizations(client):
    """Audit logs are strictly isolated per tenant; non-admins are forbidden from audit logs."""
    admin_nw = login(client, "admin@northwind.demo")
    admin_acme = login(client, "admin@acme.demo")

    # Generate an audit event in Northwind
    client.post("/api/v1/branches", headers=auth(admin_nw), json={"name": "Audit Isolated Branch"})

    # Acme admin retrieves audit logs
    acme_res = client.get("/api/v1/audit-logs", headers=auth(admin_acme))
    assert acme_res.status_code == 200, acme_res.text
    acme_logs = acme_res.json()["data"]
    # All Acme logs must belong to Acme, never Northwind
    with SessionLocal() as db:
        nw_org = db.query(Organization).filter(Organization.slug == "northwind").first()
        acme_org = db.query(Organization).filter(Organization.slug == "acme").first()

    for log in acme_logs:
        assert log.get("organization_id") != nw_org.id

    # Manager role attempting to view audit logs receives 403 FORBIDDEN
    mgr = client.post(
        "/api/v1/users",
        headers=auth(admin_nw),
        json={
            "full_name": "Audit Test Manager",
            "email": "mgr.audit@northwind.demo",
            "password": "mgr-password-1",
            "role": "MANAGER",
        },
    )
    mgr_token = login(client, "mgr.audit@northwind.demo", "mgr-password-1")
    res_mgr = client.get("/api/v1/audit-logs", headers=auth(mgr_token))
    assert res_mgr.status_code == 403


# ----------------------------------------------------------------------------------
# 12. Checklist Item 6: Restrict device mutations to ORG_ADMIN & HR_ADMIN
# ----------------------------------------------------------------------------------

def test_manager_denied_device_mutations(client):
    """Managers may view devices in scope, but are forbidden from creating codes, updating, or revoking devices."""
    admin_token = login(client, "admin@northwind.demo")

    # Issue a device as admin first
    code = client.post("/api/v1/devices/enrollment-code", headers=auth(admin_token)).json()["data"]["code"]
    device = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Manager Test Kiosk"}).json()["data"]
    device_id = device["device_id"]

    # Create Manager user
    client.post(
        "/api/v1/users",
        headers=auth(admin_token),
        json={
            "full_name": "Device Test Manager",
            "email": "mgr.dev@northwind.demo",
            "password": "mgr-password-1",
            "role": "MANAGER",
        },
    )
    mgr_token = login(client, "mgr.dev@northwind.demo", "mgr-password-1")

    # Manager can list devices -> 200 OK
    list_res = client.get("/api/v1/devices", headers=auth(mgr_token))
    assert list_res.status_code == 200

    # Manager forbidden from issuing enrollment code -> 403
    code_res = client.post("/api/v1/devices/enrollment-code", headers=auth(mgr_token))
    assert code_res.status_code == 403

    # Manager forbidden from updating device -> 403
    patch_res = client.patch(f"/api/v1/devices/{device_id}", headers=auth(mgr_token), json={"name": "Hacked"})
    assert patch_res.status_code == 403

    # Manager forbidden from revoking device -> 403
    revoke_res = client.post(f"/api/v1/devices/{device_id}/revoke", headers=auth(mgr_token))
    assert revoke_res.status_code == 403


# ----------------------------------------------------------------------------------
# 13. Checklist Item 7: Legacy kiosk password login disabled in production
# ----------------------------------------------------------------------------------

def test_legacy_kiosk_login_disabled_in_production(client, monkeypatch):
    """Legacy kiosk username/password login is rejected when disabled or in production mode."""
    settings = get_settings()

    # Create a user with ATTENDANCE_DEVICE role (legacy scanner)
    with SessionLocal() as db:
        org = db.query(Organization).filter(Organization.slug == "northwind").first()
        scanner_user = db.query(User).filter(User.email == "legacy.scanner@northwind.demo").first()
        if not scanner_user:
            scanner_user = User(
                organization_id=org.id,
                email="legacy.scanner@northwind.demo",
                password_hash=hash_password("legacy-pass"),
                full_name="Legacy Scanner",
                role=Role.ATTENDANCE_DEVICE,
                is_active=True,
            )
            db.add(scanner_user)
            db.commit()

    # 1. When enabled in development, it functions
    monkeypatch.setattr(settings, "allow_legacy_kiosk_login", True)
    monkeypatch.setattr(settings, "app_env", "development")
    ok_res = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy.scanner@northwind.demo", "password": "legacy-pass"},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["data"]["access_token"]

    # 2. When disabled via config, it returns 403 FORBIDDEN
    monkeypatch.setattr(settings, "allow_legacy_kiosk_login", False)
    dis_res = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy.scanner@northwind.demo", "password": "legacy-pass"},
    )
    assert dis_res.status_code == 403
    assert dis_res.json()["error"]["code"] == "FORBIDDEN"

    # 3. When in production mode, it is automatically rejected even if allow_legacy_kiosk_login is True
    monkeypatch.setattr(settings, "allow_legacy_kiosk_login", True)
    monkeypatch.setattr(settings, "app_env", "production")
    prod_res = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy.scanner@northwind.demo", "password": "legacy-pass"},
    )
    assert prod_res.status_code == 403
    assert prod_res.json()["error"]["code"] == "FORBIDDEN"

    monkeypatch.setattr(settings, "app_env", "development")


# ----------------------------------------------------------------------------------
# 14. Checklist Item 8: Startup check refusing production without Redis
# ----------------------------------------------------------------------------------

def test_production_startup_without_redis(monkeypatch):
    """In production mode, the application refuses to start if REDIS_URL is not set or unreachable."""
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")

    # Case A: REDIS_URL is empty
    monkeypatch.setattr(settings, "redis_url", "")
    with pytest.raises(RuntimeError, match="Production mode requires REDIS_URL to be configured"):
        _assert_production_requirements()

    # Case B: REDIS_URL is set to an unreachable host/port
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:63999")
    with pytest.raises(RuntimeError, match="Production mode requires a reachable Redis instance"):
        _assert_production_requirements()

    monkeypatch.setattr(settings, "app_env", "development")


# ----------------------------------------------------------------------------------
# 15. Checklist Item 9: PIN verify rate limits per-IP and per-device
# ----------------------------------------------------------------------------------

def test_pin_verify_per_ip_and_per_device_rate_limits(client):
    """Pin verification enforces rate limits across both IP and device to stop broad lockout attacks."""
    admin_token = login(client, "admin@northwind.demo")
    code = client.post("/api/v1/devices/enrollment-code", headers=auth(admin_token)).json()["data"]["code"]
    dev_token = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Rate Limit Kiosk"}).json()["data"]["access_token"]

    reset_memory_rate_limiter()

    # 15 attempts in 60 seconds are allowed
    for _ in range(15):
        res = client.post(
            "/api/v1/attendance/pin-verify",
            headers=auth(dev_token),
            json={"employee_code": "NON_EXISTENT", "pin": "0000"},
        )
        assert res.status_code == 401

    # 16th attempt breaches the sliding window limit and returns 429 RATE_LIMITED
    res16 = client.post(
        "/api/v1/attendance/pin-verify",
        headers=auth(dev_token),
        json={"employee_code": "NON_EXISTENT", "pin": "0000"},
    )
    assert res16.status_code == 429
    assert res16.json()["error"]["code"] == "RATE_LIMITED"

    reset_memory_rate_limiter()


# ----------------------------------------------------------------------------------
# 16. Alembic Migration Downgrade and Upgrade Test
# ----------------------------------------------------------------------------------

def test_alembic_downgrade_and_upgrade():
    """Verify that migration b4a1c8f309d2 seeds EMPLOYEE, ORG_ADMIN, and scanner users, upgrades, downgrades, and re-upgrades cleanly on SQLite."""
    from sqlalchemy import create_engine, text
    import uuid

    db_file = Path(__file__).resolve().parents[1] / "test_phase2_mig.db"
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass

    db_url = f"sqlite:///{db_file.as_posix()}"
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade dedicated test db to 4f1d9c27f6a2 (pre-Phase-2 schema)
    command.upgrade(cfg, "4f1d9c27f6a2")

    engine = create_engine(db_url)
    org_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    emp_user_id = str(uuid.uuid4())
    scanner_id = str(uuid.uuid4())

    with engine.connect() as conn:
        conn.execute(
            text("INSERT OR IGNORE INTO organizations (id, name, slug, plan, is_active, created_at) VALUES (:id, 'Mig Test Org', 'mig-test-slug', 'trial', 1, datetime('now'))"),
            {"id": org_id},
        )
        row = conn.execute(text("SELECT id FROM organizations WHERE slug = 'mig-test-slug'")).first()
        org_id = row[0]

        # Clean existing test users
        conn.execute(text("DELETE FROM users WHERE email IN ('sqlite_admin@mig.demo', 'sqlite_emp@mig.demo', 'sqlite_scanner@mig.demo')"))

        # Seed ORG_ADMIN, EMPLOYEE, and ATTENDANCE_DEVICE
        conn.execute(
            text("""
                INSERT INTO users (id, organization_id, email, password_hash, full_name, role, is_active, created_at)
                VALUES
                    (:admin_id, :org_id, 'sqlite_admin@mig.demo', 'hash1', 'SQLite Admin', 'ORG_ADMIN', 1, datetime('now')),
                    (:emp_id, :org_id, 'sqlite_emp@mig.demo', 'hash2', 'SQLite Employee User', 'EMPLOYEE', 1, datetime('now')),
                    (:scanner_id, :org_id, 'sqlite_scanner@mig.demo', 'hash3', 'SQLite Scanner Kiosk', 'ATTENDANCE_DEVICE', 1, datetime('now'))
            """),
            {"admin_id": admin_id, "emp_id": emp_user_id, "scanner_id": scanner_id, "org_id": org_id},
        )
        conn.commit()

    # 2. Upgrade to head
    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'sqlite_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORGANIZATION_ADMIN"

        emp_row = conn.execute(text("SELECT id FROM users WHERE email = 'sqlite_emp@mig.demo'")).first()
        assert emp_row is None  # Legacy EMPLOYEE user cleaned up

        device_row = conn.execute(text("SELECT id, name, status, mode FROM attendance_devices WHERE id = :id"), {"id": scanner_id}).first()
        assert device_row is not None
        assert device_row[1] == "SQLite Scanner Kiosk"
        assert device_row[2] == "ACTIVE"

    # 3. Downgrade back to 4f1d9c27f6a2
    command.downgrade(cfg, "4f1d9c27f6a2")

    with engine.connect() as conn:
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'sqlite_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORG_ADMIN"

    # 4. Re-upgrade to head
    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        admin_row = conn.execute(text("SELECT role FROM users WHERE email = 'sqlite_admin@mig.demo'")).first()
        assert admin_row is not None
        assert admin_row[0] == "ORGANIZATION_ADMIN"

    try:
        engine.dispose()
        if db_file.exists():
            db_file.unlink()
    except Exception:
        pass

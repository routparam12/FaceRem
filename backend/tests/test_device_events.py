"""
Tests for POST /api/v1/devices/me/events (Stage 5A).

Covers:
 1. Success for each of the 3 event types with a valid device credential.
 2. Audit entry written without secrets.
 3. 403 for an admin token.
 4. 403 for a manager token.
 5. 401 DEVICE_NOT_AUTHORIZED for a revoked device.
 6. Audit entry lands in the device's own organization only (no cross-org leakage).
 7. 429 after 30 rapid requests (rate-limit enforced).
 8. Unknown event type rejected (422).
"""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(
    DATABASE_URL="sqlite:///./test_device_events.db",
    JWT_SECRET="test-secret-that-is-long-enough-for-hs256-abcdef",
    FACE_ENGINE="stub",
    LIVENESS_MODE="client_attested",
    LIVENESS_THRESHOLD="0.7",
    CHECKOUT_AFTER_MINUTES="240",
    SEED_DEMO_DATA="true",
)

DB_PATH = Path("./test_device_events.db")
if DB_PATH.exists():
    DB_PATH.unlink()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
_alembic.set_main_option(
    "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
)
command.upgrade(_alembic, "head")

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import AuditLog, AttendanceDevice, DeviceStatus, Organization  # noqa: E402
from app.rate_limiter import reset_memory_rate_limiter  # noqa: E402
from app.seed import DEMO_PASSWORD  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as tc:
        yield tc


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def enroll_device(client: TestClient, admin_token: str, name: str = "Test Kiosk") -> dict:
    """Create enrollment code and exchange it for a device token. Returns the full enroll response."""
    code = client.post(
        "/api/v1/devices/enrollment-code", headers=auth(admin_token)
    ).json()["data"]["code"]
    enroll = client.post("/api/v1/devices/enroll", json={"code": code, "name": name})
    assert enroll.status_code == 200, enroll.text
    return enroll.json()["data"]


# ---------------------------------------------------------------------------
# 1 & 2. Success for each event type; audit entry written without secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    ["KIOSK_EXIT_UNLOCK", "SUPERVISED_ENROLL_START", "KIOSK_EXIT_FAILED"],
)
def test_event_type_success_and_audit(client, event_type):
    """Each valid event_type returns 200 with status=recorded and writes a sanitized audit row."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")
    device = enroll_device(client, admin_token, name=f"Kiosk-{event_type}")
    dev_token = device["access_token"]
    device_id = device["device_id"]

    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(dev_token),
        json={"event_type": event_type, "details": {"reason": "unit test"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["status"] == "recorded"
    assert body["event_type"] == event_type

    # Verify audit row was written and contains NO secrets
    with SessionLocal() as db:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == device_id,
                AuditLog.action.like(f"device.{event_type.lower()}"),
            )
        ).all()
        assert len(logs) >= 1, "Expected at least one audit row for this event"
        for log in logs:
            meta_str = str(log.meta).lower()
            for sensitive in ("token", "password", "pin", "secret", "code"):
                assert sensitive not in meta_str, (
                    f"Sensitive key '{sensitive}' found in audit meta: {log.meta}"
                )


# ---------------------------------------------------------------------------
# 3. 403 for admin token
# ---------------------------------------------------------------------------


def test_admin_token_rejected(client):
    """An ORGANIZATION_ADMIN bearer token must be rejected with 403."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")

    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(admin_token),
        json={"event_type": "KIOSK_EXIT_UNLOCK"},
    )
    assert res.status_code == 403, res.text


# ---------------------------------------------------------------------------
# 4. 403 for manager token
# ---------------------------------------------------------------------------


def test_manager_token_rejected(client):
    """A MANAGER bearer token must be rejected with 403."""
    reset_memory_rate_limiter()
    manager_token = login(client, "manager@northwind.demo")

    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(manager_token),
        json={"event_type": "KIOSK_EXIT_UNLOCK"},
    )
    assert res.status_code == 403, res.text


# ---------------------------------------------------------------------------
# 5. 401 DEVICE_NOT_AUTHORIZED for a revoked device
# ---------------------------------------------------------------------------


def test_revoked_device_rejected(client):
    """Events from a revoked device must be rejected with 401 DEVICE_NOT_AUTHORIZED."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")
    device = enroll_device(client, admin_token, name="Revoke-Events Kiosk")
    dev_token = device["access_token"]
    dev_id = device["device_id"]

    # Revoke the device via admin
    revoke = client.post(f"/api/v1/devices/{dev_id}/revoke", headers=auth(admin_token))
    assert revoke.status_code == 200, revoke.text

    # Now attempt to record an event with the revoked token
    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(dev_token),
        json={"event_type": "KIOSK_EXIT_UNLOCK"},
    )
    assert res.status_code == 401, res.text
    assert res.json()["error"]["code"] == "DEVICE_NOT_AUTHORIZED"


# ---------------------------------------------------------------------------
# 6. Audit entry lands in the device's own organization only
# ---------------------------------------------------------------------------


def test_audit_scoped_to_device_organization(client):
    """Audit rows are written only into the enrolling organization; no cross-org leakage."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")

    with SessionLocal() as db:
        org = db.scalars(
            select(Organization).where(Organization.slug == "northwind")
        ).first()
        assert org is not None, "Demo org 'northwind' must exist"
        org_id = org.id

    device = enroll_device(client, admin_token, name="Audit-Scope Kiosk")
    dev_token = device["access_token"]
    device_id = device["device_id"]

    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(dev_token),
        json={"event_type": "SUPERVISED_ENROLL_START"},
    )
    assert res.status_code == 200, res.text

    with SessionLocal() as db:
        # The audit row's organization_id must match the device's org
        log = db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == device_id,
                AuditLog.action == "device.supervised_enroll_start",
            )
        ).first()
        assert log is not None, "Audit row not found"
        assert log.organization_id == org_id, (
            f"Audit org_id mismatch: expected {org_id}, got {log.organization_id}"
        )

        # Confirm no audit row leaked to any OTHER organization
        all_orgs = db.scalars(select(Organization)).all()
        other_org_ids = [o.id for o in all_orgs if o.id != org_id]
        for other_id in other_org_ids:
            leaked = db.scalars(
                select(AuditLog).where(
                    AuditLog.target_id == device_id,
                    AuditLog.organization_id == other_id,
                )
            ).first()
            assert leaked is None, (
                f"Audit row leaked to org {other_id}"
            )


# ---------------------------------------------------------------------------
# 7. 429 after 30 rapid requests (rate limit)
# ---------------------------------------------------------------------------


def test_rate_limit_after_30_requests(client):
    """The endpoint allows 30 requests per 60 s; the 31st must return 429."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")
    device = enroll_device(client, admin_token, name="RateLimit Kiosk")
    dev_token = device["access_token"]

    # Fire 30 requests — all should succeed (or at least not be 429)
    for i in range(30):
        r = client.post(
            "/api/v1/devices/me/events",
            headers=auth(dev_token),
            json={"event_type": "KIOSK_EXIT_FAILED"},
        )
        assert r.status_code == 200, f"Request {i + 1} unexpectedly failed: {r.text}"

    # 31st request must be rate-limited
    r31 = client.post(
        "/api/v1/devices/me/events",
        headers=auth(dev_token),
        json={"event_type": "KIOSK_EXIT_FAILED"},
    )
    assert r31.status_code == 429, f"Expected 429 on 31st request, got {r31.status_code}: {r31.text}"


# ---------------------------------------------------------------------------
# 8. Unknown event type rejected (422 Unprocessable Entity)
# ---------------------------------------------------------------------------


def test_unknown_event_type_rejected(client):
    """An unrecognized event_type value must be rejected with 422."""
    reset_memory_rate_limiter()
    admin_token = login(client, "admin@northwind.demo")
    device = enroll_device(client, admin_token, name="UnknownEvent Kiosk")
    dev_token = device["access_token"]

    res = client.post(
        "/api/v1/devices/me/events",
        headers=auth(dev_token),
        json={"event_type": "TOTALLY_UNKNOWN_EVENT"},
    )
    assert res.status_code == 422, res.text


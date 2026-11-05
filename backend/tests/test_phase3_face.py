"""
Comprehensive test suite for Phase 3: Face Pipeline, Liveness, and Vector Storage.
"""

from datetime import datetime, timedelta, timezone
import io
import os
from pathlib import Path
import random
import sys
from unittest.mock import MagicMock
import uuid

import numpy as np
from PIL import Image
import pytest
from sqlalchemy import delete, select
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./test_faceattend.db")
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-abcdef"
os.environ["FACE_ENGINE"] = "stub"
os.environ["LIVENESS_MODE"] = "disabled"
os.environ["SEED_DEMO_DATA"] = "true"

from app.config import get_settings
from app.db import SessionLocal
from app.face import StubEngine, find_best_match, get_engine
from app.main import _assert_production_requirements, app
from app.models import AttendanceEvent, AttendanceRecord, AuditLog, Employee, FaceProfile, Organization, Role
from app.seed import DEMO_PASSWORD


@pytest.fixture(scope="module", autouse=True)
def setup_database_schema():
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", "sqlite:///./test_faceattend.db"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_raw_image(seed: int, width: int = 128, height: int = 128, variation: int = 0) -> bytes:
    rng = random.Random(seed)
    base = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(width * height)]
    if variation > 0:
        v_rng = random.Random(seed * 100 + variation)
        for _ in range(int(len(base) * 0.05 * variation)):
            idx = v_rng.randrange(len(base))
            base[idx] = (v_rng.randrange(256), v_rng.randrange(256), v_rng.randrange(256))
    img = Image.new("RGB", (width, height))
    img.putdata(base)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def valid_enrollment_frames(seed: int) -> dict:
    return {
        "front": ("front.png", make_raw_image(seed, 128, 128, 0), "image/png"),
        "left": ("left.png", make_raw_image(seed, 128, 128, 1), "image/png"),
        "right": ("right.png", make_raw_image(seed, 128, 128, 2), "image/png"),
    }


def _get_first_employee_id(client: TestClient, token: str) -> str:
    res = client.get("/api/v1/employees", headers=auth(token))
    return res.json()["data"][0]["id"]


# --------------------------------------------------------------------------------------
# 1. Multi-Frame Enrollment & Pose Coverage
# --------------------------------------------------------------------------------------

def test_enrollment_requires_at_least_three_poses(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # Only 2 frames provided
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(10), "image/png"),
            "left": ("l.png", make_raw_image(10, variation=1), "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INSUFFICIENT_FRAMES"


def test_enrollment_requires_front_left_right_poses(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # 3 frames, but missing RIGHT pose (FRONT, LEFT, LEFT)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files=[
            ("frames", ("f1.png", make_raw_image(20, variation=0), "image/png")),
            ("frames", ("f2.png", make_raw_image(20, variation=1), "image/png")),
            ("frames", ("f3.png", make_raw_image(20, variation=2), "image/png")),
        ],
        data={"poses": ["FRONT", "LEFT", "LEFT"], "consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INSUFFICIENT_POSES"


# --------------------------------------------------------------------------------------
# 2. Quality & Anomaly Rejections
# --------------------------------------------------------------------------------------

def test_enrollment_rejects_multiple_faces(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # Frame 2 triggers simulated multiple faces (width=111 in StubEngine)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(30, 128, 128, 0), "image/png"),
            "left": ("l.png", make_raw_image(30, 111, 128, 1), "image/png"),
            "right": ("r.png", make_raw_image(30, 128, 128, 2), "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "MULTIPLE_FACES"


def test_enrollment_rejects_no_face_detected(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # Frame 1 triggers simulated no face (width=112 in StubEngine)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(40, 112, 128, 0), "image/png"),
            "left": ("l.png", make_raw_image(40, 128, 128, 1), "image/png"),
            "right": ("r.png", make_raw_image(40, 128, 128, 2), "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "FACE_NOT_FOUND"


def test_enrollment_rejects_blurry_frame(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # Frame 3 triggers simulated blur (width=113 in StubEngine)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(50, 128, 128, 0), "image/png"),
            "left": ("l.png", make_raw_image(50, 128, 128, 1), "image/png"),
            "right": ("r.png", make_raw_image(50, 113, 128, 2), "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "FACE_QUALITY_LOW"


def test_enrollment_rejects_duplicate_frames(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # Submitting the exact same frame 3 times (similarity == 1.0 > 0.98)
    same_img = make_raw_image(60)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", same_img, "image/png"),
            "left": ("l.png", same_img, "image/png"),
            "right": ("r.png", same_img, "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "DUPLICATE_FRAMES"


def test_enrollment_rejects_inconsistent_identity_across_frames(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # 3 completely different seeds (similarity ~0.0 < 0.70)
    res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(71), "image/png"),
            "left": ("l.png", make_raw_image(72), "image/png"),
            "right": ("r.png", make_raw_image(73), "image/png"),
        },
        data={"consent": "true"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INCONSISTENT_IDENTITY"


# --------------------------------------------------------------------------------------
# 3. Atomic Replacement & Enrollment ID
# --------------------------------------------------------------------------------------

def test_atomic_replacement_keeps_old_profiles_on_failure(client):
    hr = login(client, "hr@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # 1. Successfully enroll initial profile set
    initial = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files=valid_enrollment_frames(80),
        data={"consent": "true"},
    )
    assert initial.status_code == 200
    old_enrollment_id = initial.json()["data"]["enrollment_id"]
    assert old_enrollment_id is not None

    with SessionLocal() as db:
        old_profiles = db.scalars(
            select(FaceProfile).where(FaceProfile.employee_id == emp_id)
        ).all()
        assert len(old_profiles) == 3

    # 2. Attempt replacement that fails on the 3rd frame (e.g. duplicate or blurry)
    fail_res = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files={
            "front": ("f.png", make_raw_image(85, 128, 128, 0), "image/png"),
            "left": ("l.png", make_raw_image(85, 128, 128, 1), "image/png"),
            "right": ("r.png", make_raw_image(85, 113, 128, 2), "image/png"),  # blurry
        },
        data={"consent": "true"},
    )
    assert fail_res.status_code == 422

    # 3. Verify old profile set is completely intact
    with SessionLocal() as db:
        intact_profiles = db.scalars(
            select(FaceProfile).where(FaceProfile.employee_id == emp_id)
        ).all()
        assert len(intact_profiles) == 3
        for p in intact_profiles:
            assert p.enrollment_id == old_enrollment_id

    # 4. Successfully replace with new set
    success_replace = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files=valid_enrollment_frames(90),
        data={"consent": "true"},
    )
    assert success_replace.status_code == 200
    new_enrollment_id = success_replace.json()["data"]["enrollment_id"]
    assert new_enrollment_id != old_enrollment_id

    with SessionLocal() as db:
        updated_profiles = db.scalars(
            select(FaceProfile).where(FaceProfile.employee_id == emp_id)
        ).all()
        assert len(updated_profiles) == 3
        for p in updated_profiles:
            assert p.enrollment_id == new_enrollment_id


# --------------------------------------------------------------------------------------
# 4. Margin Rule & Discrimination
# --------------------------------------------------------------------------------------

def test_margin_rule_rejects_ambiguous_near_matches(client):
    """When top two candidates are within margin, neither is recognized."""
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp1 = Employee(
            organization_id=org.id,
            employee_code="AMB-01",
            full_name="Candidate One",
            email="amb1@northwind.demo",
        )
        emp2 = Employee(
            organization_id=org.id,
            employee_code="AMB-02",
            full_name="Candidate Two",
            email="amb2@northwind.demo",
        )
        db.add_all([emp1, emp2])
        db.flush()

        # Query vector: unit vector
        q_vec = np.zeros(16, dtype=np.float32)
        q_vec[0] = 1.0

        # Candidate 1: similarity = 0.95
        v1 = np.zeros(16, dtype=np.float32)
        v1[0] = 0.95
        v1[1] = np.sqrt(1.0 - 0.95**2)

        # Candidate 2: similarity = 0.93 (gap is 0.02 < default margin 0.05)
        v2 = np.zeros(16, dtype=np.float32)
        v2[0] = 0.93
        v2[1] = np.sqrt(1.0 - 0.93**2)

        p1 = FaceProfile(
            organization_id=org.id,
            employee_id=emp1.id,
            embedding=v1.tolist(),
            model_name="stub-gray16",
            model_version="0",
            quality_score=0.95,
        )
        p2 = FaceProfile(
            organization_id=org.id,
            employee_id=emp2.id,
            embedding=v2.tolist(),
            model_name="stub-gray16",
            model_version="0",
            quality_score=0.95,
        )
        db.add_all([p1, p2])
        db.commit()

        # Match query: margin rule must reject
        match = find_best_match(db, org.id, q_vec.tolist())
        assert match is None, "Ambiguous match with margin < 0.05 should be rejected"

        # Cleanup
        db.delete(p1)
        db.delete(p2)
        db.delete(emp1)
        db.delete(emp2)
        db.commit()


# --------------------------------------------------------------------------------------
# 5. Challenge-Response Liveness Lifecycle
# --------------------------------------------------------------------------------------

def test_challenge_creation_and_fields(client):
    kiosk = login(client, "kiosk@northwind.demo")
    res = client.post("/api/v1/attendance/challenge", headers=auth(kiosk))
    assert res.status_code == 200
    data = res.json()["data"]
    assert "challenge_id" in data
    assert "nonce" in data
    assert "actions" in data
    assert len(data["actions"]) >= 1
    assert "expires_at" in data


def test_challenge_expiry(monkeypatch):
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    from app.liveness import get_liveness_service

    svc = get_liveness_service()
    challenge = svc.create_challenge("dev-1", "org-1")

    # Manually backdate expiration to 10 seconds ago
    expired_ch = challenge.__class__(
        challenge_id=challenge.challenge_id,
        nonce=challenge.nonce,
        actions=challenge.actions,
        device_id=challenge.device_id,
        organization_id=challenge.organization_id,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    svc._store_challenge(expired_ch)

    with pytest.raises(Exception) as exc_info:
        svc.verify_challenge(
            challenge_id=challenge.challenge_id,
            nonce=challenge.nonce,
            device_id="dev-1",
            organization_id="org-1",
            burst_frames=[b"1", b"2"],
            primary_vector=[0.0] * 16,
        )
    assert "invalid, expired, or already used" in str(exc_info.value)


def test_challenge_single_use_replay_prevention(monkeypatch):
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    from app.liveness import get_liveness_service
    svc = get_liveness_service()
    challenge = svc.create_challenge("dev-replay", "org-replay")

    # First consumption succeeds (in stub engine mode)
    res = svc.verify_challenge(
        challenge_id=challenge.challenge_id,
        nonce=challenge.nonce,
        device_id="dev-replay",
        organization_id="org-replay",
        burst_frames=[b"frame1", b"frame2"],
        primary_vector=[0.0] * 16,
    )
    assert res.passed is True

    # Immediate replay fails
    with pytest.raises(Exception) as exc_info:
        svc.verify_challenge(
            challenge_id=challenge.challenge_id,
            nonce=challenge.nonce,
            device_id="dev-replay",
            organization_id="org-replay",
            burst_frames=[b"frame1", b"frame2"],
            primary_vector=[0.0] * 16,
        )
    assert "invalid, expired, or already used" in str(exc_info.value)


def test_challenge_wrong_device_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    from app.liveness import get_liveness_service
    svc = get_liveness_service()
    challenge = svc.create_challenge("dev-alpha", "org-common")

    with pytest.raises(Exception) as exc_info:
        svc.verify_challenge(
            challenge_id=challenge.challenge_id,
            nonce=challenge.nonce,
            device_id="dev-beta",  # Different device
            organization_id="org-common",
            burst_frames=[b"frame1", b"frame2"],
            primary_vector=[0.0] * 16,
        )
    assert "not issued to this device" in str(exc_info.value)


def test_challenge_wrong_organization_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    from app.liveness import get_liveness_service
    svc = get_liveness_service()
    challenge = svc.create_challenge("dev-shared", "org-alpha")

    with pytest.raises(Exception) as exc_info:
        svc.verify_challenge(
            challenge_id=challenge.challenge_id,
            nonce=challenge.nonce,
            device_id="dev-shared",
            organization_id="org-beta",  # Different organization
            burst_frames=[b"frame1", b"frame2"],
            primary_vector=[0.0] * 16,
        )
    assert "does not belong to this organization" in str(exc_info.value)


def test_client_attested_liveness_score_without_challenge_fails(client, monkeypatch):
    """Enabling challenge liveness rejects requests relying solely on client liveness_score=1.0."""
    monkeypatch.setattr(get_settings(), "liveness_mode", "challenge")
    kiosk = login(client, "kiosk@northwind.demo")

    res = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", make_raw_image(99), "image/png")},
        data={"liveness_score": "1.0"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "LIVENESS_FAILED"


# --------------------------------------------------------------------------------------
# 6. Hard Biometric Delete & Audit Logging
# --------------------------------------------------------------------------------------

def test_hard_delete_removes_embeddings_and_preserves_attendance(client):
    hr = login(client, "hr@northwind.demo")
    kiosk = login(client, "kiosk@northwind.demo")
    emp_id = _get_first_employee_id(client, hr)

    # 1. Enroll face
    enroll = client.post(
        f"/api/v1/employees/{emp_id}/face/enroll",
        headers=auth(hr),
        files=valid_enrollment_frames(110),
        data={"consent": "true"},
    )
    assert enroll.status_code == 200

    # 2. Check in
    scan = client.post(
        "/api/v1/attendance/recognize",
        headers=auth(kiosk),
        files={"image": ("scan.png", make_raw_image(110), "image/png")},
    )
    assert scan.status_code == 200

    # 3. Hard delete face profile
    del_res = client.delete(f"/api/v1/employees/{emp_id}/face", headers=auth(hr))
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted_profiles"] == 3
    assert del_res.json()["data"]["attendance_retained"] is True

    # 4. Confirm FaceProfile rows are completely deleted from DB
    with SessionLocal() as db:
        remaining = db.scalars(
            select(FaceProfile).where(FaceProfile.employee_id == emp_id)
        ).all()
        assert len(remaining) == 0

        # Attendance event is intact (preserved after face deletion)
        att_events = db.scalars(
            select(AttendanceEvent).where(AttendanceEvent.employee_id == emp_id)
        ).all()
        assert len(att_events) > 0

        # Audit log has 'face.deleted' with NO biometric data
        del_log = db.scalars(
            select(AuditLog)
            .where(AuditLog.target_id == emp_id, AuditLog.action == "face.deleted")
            .order_by(AuditLog.created_at.desc())
        ).first()
        assert del_log is not None
        assert "embedding" not in str(del_log.meta).lower()
        assert "vector" not in str(del_log.meta).lower()


# --------------------------------------------------------------------------------------
# 7. Production Startup Enforcement
# --------------------------------------------------------------------------------------

def test_production_startup_fails_with_stub_engine(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    monkeypatch.setattr(s, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(s, "face_engine", "stub")

    mock_redis = MagicMock()
    mock_redis.Redis.from_url.return_value.ping.return_value = True
    monkeypatch.setitem(sys.modules, "redis", mock_redis)

    with pytest.raises(RuntimeError) as exc_info:
        _assert_production_requirements()
    assert "stub" in str(exc_info.value).lower()


def test_production_startup_fails_with_disabled_liveness(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    monkeypatch.setattr(s, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(s, "face_engine", "insightface")
    monkeypatch.setattr(s, "liveness_mode", "disabled")

    mock_redis = MagicMock()
    mock_redis.Redis.from_url.return_value.ping.return_value = True
    monkeypatch.setitem(sys.modules, "redis", mock_redis)

    with pytest.raises(RuntimeError) as exc_info:
        _assert_production_requirements()
    assert "liveness_mode='disabled' is forbidden" in str(exc_info.value).lower()


def test_production_startup_refuses_without_passive_liveness_override(monkeypatch):
    """Production mode refuses to start without passive anti-spoof model unless explicitly overridden."""
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    monkeypatch.setattr(s, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(s, "face_engine", "insightface")
    monkeypatch.setattr(s, "liveness_mode", "challenge")
    monkeypatch.setattr(s, "allow_unconfigured_passive_liveness", False)

    mock_redis = MagicMock()
    mock_redis.Redis.from_url.return_value.ping.return_value = True
    monkeypatch.setitem(sys.modules, "redis", mock_redis)

    with pytest.raises(RuntimeError) as exc_info:
        _assert_production_requirements()
    assert "passive liveness model or allow_unconfigured_passive_liveness=true" in str(exc_info.value).lower()

    # Allowed with explicit override
    monkeypatch.setattr(s, "allow_unconfigured_passive_liveness", True)
    _assert_production_requirements()


# --------------------------------------------------------------------------------------
# 8. Pgvector & NumPy Parity (Gated by POSTGRES_TEST_URL)
# --------------------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="PostgreSQL test URL not configured")
def test_pgvector_and_numpy_matching_parity():
    """Confirms SQL cosine similarity query matches NumPy dot product on normalized vectors."""
    from sqlalchemy import create_engine, text
    pg_url = os.getenv("POSTGRES_TEST_URL")
    eng = create_engine(pg_url)

    v1 = np.random.randn(512).astype(np.float32)
    v1 /= np.linalg.norm(v1)

    v2 = np.random.randn(512).astype(np.float32)
    v2 /= np.linalg.norm(v2)

    numpy_sim = float(np.dot(v1, v2))

    with eng.connect() as conn:
        has_vec = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        if not has_vec:
            pytest.skip("pgvector extension not installed in postgresql")

        # 1 - cosine distance = cosine similarity
        query = text("SELECT 1.0 - (:v1::vector <=> :v2::vector) AS sim")
        pg_sim = conn.execute(query, {"v1": str(v1.tolist()), "v2": str(v2.tolist())}).scalar()
        assert np.isclose(numpy_sim, pg_sim, atol=1e-4)

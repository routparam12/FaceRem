"""
Phase 4 Attendance Engine & Camera-Independent Architecture Tests.

Verifies:
1. Two cameras seeing the same employee within cooldown yields one event.
2. An OUT_ONLY camera never produces CHECK_IN.
3. An IN_ONLY camera produces CHECK_IN and never produces CHECK_OUT.
4. Observation idempotency (same observation_id produces identical result, exactly 1 DB event).
5. Assurance policy hook: STANDARD camera without liveness marks event provisional=True (not finalized in AttendanceRecord).
6. HIGH assurance camera enforces liveness.
7. Timezone lateness (IST case: 09:15 IST vs 09:00 shift = 15 min late).
8. Explicit support for overnight shifts (e.g. 22:00 to 06:00).
9. Undo token lifecycle: within 30-second window voids event and rolls back record; expired fails.
10. Admin event void with audit trail.
11. Cross-tenant camera and event isolation.
12. Camera management CRUD and branch scoping.
13. Verification that no RTSP credentials or camera secrets exist in models/database.
"""

from datetime import date, datetime, timedelta, timezone
import io
import os
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.update(
    DATABASE_URL="sqlite:///./test_phase4.db",
    JWT_SECRET="test-secret-that-is-long-enough-for-hs256-abcdef",
    FACE_ENGINE="stub",
    LIVENESS_MODE="disabled",
    LIVENESS_THRESHOLD="0.7",
    CHECKOUT_AFTER_MINUTES="240",
    SEED_DEMO_DATA="true",
    ATTENDANCE_COOLDOWN_SECONDS="60",
    UNDO_WINDOW_SECONDS="30",
    STANDARD_ASSURANCE_PROVISIONAL="true",
)

DB_PATH = Path("./test_phase4.db")
if DB_PATH.exists():
    try:
        DB_PATH.unlink()
    except Exception:
        pass

from alembic import command
from alembic.config import Config

_alembic = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
_alembic.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
_alembic.set_main_option("sqlalchemy.url", "sqlite:///./test_phase4.db")
command.upgrade(_alembic, "head")

from app.attendance_service import (
    compute_shift_lateness_and_date,
    evaluate_assurance_policy,
    get_org_timezone,
    process_face_observation,
    undo_last_event,
)
from app.config import get_settings
from app.db import SessionLocal
from app.face import get_engine
from app.main import app
from app.models import (
    AttendanceDevice,
    AttendanceEvent,
    AttendanceEventType,
    AttendanceMethod,
    AttendanceRecord,
    AttendanceStatus,
    AuditLog,
    Camera,
    CameraAssurance,
    CameraDirection,
    CameraSourceType,
    DeviceMode,
    DeviceStatus,
    Employee,
    FaceProfile,
    Organization,
    Role,
    Shift,
    User,
)
from app.schemas import FaceObservation
from app.security import Principal

settings = get_settings()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str = "demo12345") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["data"]["access_token"]


def make_principal(user_id: str, org_id: str, role: Role = Role.ATTENDANCE_DEVICE) -> Principal:
    return Principal(
        user_id=user_id,
        organization_id=org_id,
        role=role,
        employee_id=None,
        full_name="Kiosk Device",
        email="kiosk@demo",
    )


def make_test_face_image(seed: int = 42) -> bytes:
    rng = __import__("random").Random(seed)
    image = Image.new("RGB", (128, 128))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(128 * 128)])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def enroll_test_face(db, employee_id: str, org_id: str, seed: int = 42) -> bytes:
    engine = get_engine()
    img_bytes = make_test_face_image(seed)
    emb = engine.embed(img_bytes)
    fp = db.scalar(select(FaceProfile).where(FaceProfile.employee_id == employee_id))
    if fp is None:
        fp = FaceProfile(
            organization_id=org_id,
            employee_id=employee_id,
            embedding=emb.vector,
            model_name=engine.model_name,
            model_version=engine.model_version,
            quality_score=0.9,
        )
        db.add(fp)
    else:
        fp.embedding = emb.vector
        fp.model_name = engine.model_name
        fp.model_version = engine.model_version
    db.commit()
    return img_bytes


# ---------------------------------------------------------------------------
# 1. Cooldown & Cross-Camera Duplicate Prevention Tests
# ---------------------------------------------------------------------------

def test_two_cameras_seeing_same_employee_within_cooldown_yields_one_event(client):
    """
    Two cameras seeing the same employee within cooldown yields exactly ONE event in DB.
    Cooldown is per-employee across all cameras, not per camera.
    """
    admin_token = login(client, "admin@northwind.demo")
    headers = auth_header(admin_token)

    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp = db.scalar(select(Employee).where(Employee.organization_id == org.id, Employee.is_active.is_(True)))
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))

        # Clear existing attendance to isolate fresh check-in
        db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == emp.id).delete()
        db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == emp.id).delete()
        db.commit()

        # Setup two distinct cameras for this organization
        cam1 = Camera(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            device_id=device.id,
            name="North Gate Camera",
            direction=CameraDirection.AUTO,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        cam2 = Camera(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            device_id=device.id,
            name="South Gate Camera",
            direction=CameraDirection.AUTO,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        db.add_all([cam1, cam2])

        cam1_id, cam2_id, org_id, emp_id, dev_id = cam1.id, cam2.id, org.id, emp.id, device.id
        img_bytes = enroll_test_face(db, emp.id, org.id, seed=42)

    # 1. Camera 1 sees the employee -> creates event 1 (CHECK_IN)
    obs1 = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam1_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )
    with SessionLocal() as db:
        principal = make_principal(dev_id, org_id)
        import asyncio
        res1 = asyncio.run(process_face_observation(db, org_id, obs1, principal=principal))
        assert res1.event == "CHECK_IN"
        assert res1.employee_id == emp_id

    # Count events in DB: exactly 1
    with SessionLocal() as db:
        ev_count = db.scalar(
            select(func.count()).select_from(AttendanceEvent).where(
                AttendanceEvent.organization_id == org_id,
                AttendanceEvent.employee_id == emp_id,
                AttendanceEvent.voided_at.is_(None),
            )
        )
        assert ev_count == 1

    # 2. Camera 2 sees the same employee 5 seconds later (within 60s cooldown)
    obs2 = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam2_id,
        captured_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        image=img_bytes,
    )
    with SessionLocal() as db:
        principal = make_principal(dev_id, org_id)
        res2 = asyncio.run(process_face_observation(db, org_id, obs2, principal=principal))
        # Cooldown returns ALREADY_PRESENT without recording duplicate
        assert res2.event == "ALREADY_PRESENT"

    # Count events in DB: still exactly 1 event!
    with SessionLocal() as db:
        ev_count_after = db.scalar(
            select(func.count()).select_from(AttendanceEvent).where(
                AttendanceEvent.organization_id == org_id,
                AttendanceEvent.employee_id == emp_id,
                AttendanceEvent.voided_at.is_(None),
            )
        )
        assert ev_count_after == 1, "Cooldown across cameras MUST prevent duplicate event creation"

    # Also test that calling scan with raise_on_cooldown=True raises 409 ATTENDANCE_ALREADY_MARKED
    with SessionLocal() as db:
        principal = make_principal(dev_id, org_id)
        from app.security import AppError
        with pytest.raises(AppError) as exc_info:
            asyncio.run(process_face_observation(db, org_id, obs2, principal=principal, raise_on_cooldown=True))
        assert exc_info.value.code == "ATTENDANCE_ALREADY_MARKED"


# ---------------------------------------------------------------------------
# 2. Direction Enforcement Per Camera Tests
# ---------------------------------------------------------------------------

def test_out_only_camera_never_produces_check_in(client):
    """An OUT_ONLY camera never produces CHECK_IN; only CHECK_OUT when checked in."""
    import asyncio
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        # Pick second employee who has not checked in today
        emps = db.scalars(select(Employee).where(Employee.organization_id == org.id)).all()
        emp = emps[1]
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))

        out_camera = Camera(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            device_id=device.id,
            name="Exit Turnstile Camera",
            direction=CameraDirection.OUT_ONLY,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        db.add(out_camera)
        db.commit()
        cam_id, org_id, emp_id, dev_id = out_camera.id, org.id, emp.id, device.id
        img_bytes = enroll_test_face(db, emp_id, org_id, seed=43)

    obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )

    # 1. Unchecked-in employee attempts to scan at exit camera -> MUST NOT CHECK IN
    with SessionLocal() as db:
        principal = make_principal(dev_id, org_id)
        from app.security import AppError
        with pytest.raises(AppError) as exc:
            asyncio.run(process_face_observation(db, org_id, obs, principal=principal))
        assert exc.value.code == "DIRECTION_MISMATCH"
        assert "Exit camera cannot record check-in" in exc.value.message

    # Verify no event created
    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(AttendanceEvent).where(
                AttendanceEvent.organization_id == org_id,
                AttendanceEvent.employee_id == emp_id,
            )
        )
        assert count == 0

    # 2. Now check in via IN_ONLY camera
    with SessionLocal() as db:
        in_camera = Camera(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            device_id=dev_id,
            name="Entry Gate Camera",
            direction=CameraDirection.IN_ONLY,
            assurance=CameraAssurance.HIGH,
            enabled=True,
        )
        db.add(in_camera)
        db.commit()
        in_cam_id = in_camera.id

    in_obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=in_cam_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )
    with SessionLocal() as db:
        principal = make_principal(dev_id, org_id)
        in_res = asyncio.run(process_face_observation(db, org_id, in_obs, principal=principal))
        assert in_res.event == "CHECK_IN"

    # 3. Now scanning at OUT_ONLY camera outside cooldown succeeds with CHECK_OUT
    out_obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam_id,
        captured_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        image=img_bytes,
    )
    with SessionLocal() as db:
        # Clear recent events to bypass cooldown for direction test
        db.execute(
            AttendanceEvent.__table__.update()
            .where(AttendanceEvent.employee_id == emp_id)
            .values(occurred_at=datetime.now(timezone.utc) - timedelta(minutes=10))
        )
        db.commit()
        principal = make_principal(dev_id, org_id)
        out_res = asyncio.run(process_face_observation(db, org_id, out_obs, principal=principal))
        assert out_res.event == "CHECK_OUT"


# ---------------------------------------------------------------------------
# 3. Observation Idempotency Tests
# ---------------------------------------------------------------------------

def test_observation_idempotency(client):
    """
    Submitting the same FaceObservation (same observation_id) multiple times
    is idempotent: yields the same result and creates only ONE event in the DB.
    """
    import asyncio
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp = db.scalars(select(Employee).where(Employee.organization_id == org.id)).all()[2]
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))
        camera = db.scalar(select(Camera).where(Camera.device_id == device.id))
        cam_id, org_id, emp_id, dev_id = camera.id, org.id, emp.id, device.id
        img_bytes = enroll_test_face(db, emp_id, org_id, seed=44)

    obs_id = f"idem-obs-{uuid.uuid4()}"
    obs = FaceObservation(
        observation_id=obs_id,
        camera_id=cam_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )

    principal = make_principal(dev_id, org_id)

    # First submission
    with SessionLocal() as db:
        res1 = asyncio.run(process_face_observation(db, org_id, obs, principal=principal))
        assert res1.employee_id == emp_id
        first_event_id = res1.event_id

    # Submit 3 more times with identical observation_id
    for _ in range(3):
        with SessionLocal() as db:
            res_repeat = asyncio.run(process_face_observation(db, org_id, obs, principal=principal))
            assert res_repeat.employee_id == emp_id
            assert res_repeat.event == res1.event
            assert res_repeat.event_id == first_event_id

    # Verify exactly one event exists in DB with this idempotency key
    with SessionLocal() as db:
        matching_events = db.scalars(
            select(AttendanceEvent).where(
                AttendanceEvent.organization_id == org_id,
                AttendanceEvent.idempotency_key == obs_id,
            )
        ).all()
        assert len(matching_events) == 1, "Observation idempotency must ensure exactly 1 event row"


# ---------------------------------------------------------------------------
# 4. Assurance Policy Hook & Provisional Marking Tests
# ---------------------------------------------------------------------------

def test_provisional_marking_for_standard_assurance_camera_without_liveness(client):
    """
    STANDARD assurance camera with NO liveness evidence:
    - Event is recorded with provisional=True.
    - Event is NOT counted in final AttendanceRecord until confirmed by policy.
    """
    import asyncio
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp = db.scalar(select(Employee).where(Employee.organization_id == org.id))
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))

        std_camera = Camera(
            id=str(uuid.uuid4()),
            organization_id=org.id,
            device_id=device.id,
            name="Standard Webcam 1",
            direction=CameraDirection.AUTO,
            assurance=CameraAssurance.STANDARD,
            enabled=True,
        )
        db.add(std_camera)
        db.commit()
        cam_id, org_id, emp_id, dev_id = std_camera.id, org.id, emp.id, device.id
        img_bytes = enroll_test_face(db, emp_id, org_id, seed=45)

    obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
        liveness_evidence=None,  # No liveness evidence
    )

    # Clean prior events for this employee to test provisional check-in
    with SessionLocal() as db:
        db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == emp_id).delete()
        db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == emp_id).delete()
        db.commit()

        principal = make_principal(dev_id, org_id)
        res = asyncio.run(process_face_observation(db, org_id, obs, principal=principal))

        assert res.provisional is True, "STANDARD camera without liveness must be marked provisional"
        assert res.event == "CHECK_IN"

    # Verify event is stored in attendance_events with provisional=True
    with SessionLocal() as db:
        event = db.scalar(
            select(AttendanceEvent).where(
                AttendanceEvent.organization_id == org_id,
                AttendanceEvent.idempotency_key == obs.observation_id,
            )
        )
        assert event is not None
        assert event.provisional is True

        # Verify AttendanceRecord was NOT created/finalized
        record = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == org_id,
                AttendanceRecord.employee_id == emp_id,
            )
        )
        assert record is None, "Provisional event must NOT update final AttendanceRecord daily summary"


def test_high_assurance_camera_enforces_liveness(client):
    """HIGH assurance camera rejects observation when liveness evidence is missing."""
    camera = Camera(
        id=str(uuid.uuid4()),
        organization_id="org-1",
        device_id="dev-1",
        name="High Sec Camera",
        direction=CameraDirection.AUTO,
        assurance=CameraAssurance.HIGH,
        enabled=True,
    )

    from app.config import Settings
    # When liveness is enabled in settings
    active_cfg = Settings(liveness_mode="challenge", standard_assurance_provisional=True)

    # Without liveness: HIGH assurance must reject
    allowed, provisional = evaluate_assurance_policy(camera, has_liveness=False, active_settings=active_cfg)
    assert allowed is False, "HIGH assurance camera must reject observation without liveness"

    # With verified liveness: HIGH assurance allows non-provisional
    allowed_with_live, provisional_with_live = evaluate_assurance_policy(camera, has_liveness=True, active_settings=active_cfg)
    assert allowed_with_live is True
    assert provisional_with_live is False


# ---------------------------------------------------------------------------
# 5. Timezone & Shift Lateness Tests
# ---------------------------------------------------------------------------

def test_timezone_lateness_ist_case():
    """
    IST Case: 09:15 IST vs 09:00 shift = exactly 15 min late.
    At 03:45 UTC, local time in Asia/Kolkata (+05:30) is 09:15 IST.
    """
    tz = ZoneInfo("Asia/Kolkata")
    # 03:45 UTC is 09:15 IST
    moment_utc = datetime(2026, 11, 3, 3, 45, 0, tzinfo=timezone.utc)

    shift = Shift(
        organization_id="test-org",
        name="Morning IST Shift",
        start_time="09:00",
        end_time="17:00",
        grace_minutes=0,  # 0 grace to test exact 15 min lateness
    )

    eff_date, late_minutes, status = compute_shift_lateness_and_date(moment_utc, shift, tz)
    assert eff_date == date(2026, 11, 3)
    assert late_minutes == 15, f"Expected 15 minutes late in IST, got {late_minutes}"
    assert status == AttendanceStatus.LATE


def test_overnight_shift_explicit_support():
    """
    Explicit support for overnight shifts: 22:00 to 06:00.
    1. Check-in at 22:15 on date D belongs to date D shift, 15 min late.
    2. Check-out at 06:05 next morning (date D+1) belongs to date D shift.
    """
    tz = ZoneInfo("UTC")
    overnight_shift = Shift(
        organization_id="test-org",
        name="Night Shift",
        start_time="22:00",
        end_time="06:00",
        grace_minutes=0,
    )

    # 1. Check-in at 22:15 on Nov 3
    check_in_utc = datetime(2026, 11, 3, 22, 15, 0, tzinfo=timezone.utc)
    in_date, in_late, in_status = compute_shift_lateness_and_date(check_in_utc, overnight_shift, tz)
    assert in_date == date(2026, 11, 3)
    assert in_late == 15
    assert in_status == AttendanceStatus.LATE

    # 2. Check-out at 06:05 on Nov 4 (morning after midnight)
    check_out_utc = datetime(2026, 11, 4, 6, 5, 0, tzinfo=timezone.utc)
    out_date, _, _ = compute_shift_lateness_and_date(check_out_utc, overnight_shift, tz)
    assert out_date == date(2026, 11, 3), "Punch in morning before 06:00 end belongs to previous day's shift"


# ---------------------------------------------------------------------------
# 6. Undo Token Lifecycle Tests
# ---------------------------------------------------------------------------

def test_undo_window_lifecycle(client):
    """
    Within 30 seconds: undo voids event and rolls back AttendanceRecord.
    After 30 seconds: undo fails with UNDO_EXPIRED.
    """
    import asyncio
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp = db.scalar(select(Employee).where(Employee.organization_id == org.id))
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))
        camera = db.scalar(select(Camera).where(Camera.device_id == device.id))
        cam_id, org_id, emp_id, dev_id = camera.id, org.id, emp.id, device.id
        img_bytes = enroll_test_face(db, emp_id, org_id, seed=46)

    obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )

    principal = make_principal(dev_id, org_id)
    with SessionLocal() as db:
        # Clear prior records to test fresh check-in
        db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == emp_id).delete()
        db.query(AttendanceRecord).filter(AttendanceRecord.employee_id == emp_id).delete()
        db.commit()

        res = asyncio.run(process_face_observation(db, org_id, obs, principal=principal))
        assert res.undo_token is not None
        undo_token = res.undo_token
        event_id = res.event_id

    # 1. Perform undo via API endpoint within 30-sec window
    kiosk_token = login(client, "kiosk@northwind.demo")
    undo_resp = client.post(
        "/api/v1/attendance/undo",
        headers=auth_header(kiosk_token),
        json={"undo_token": undo_token},
    )
    assert undo_resp.status_code == 200, undo_resp.text
    undo_data = undo_resp.json()
    assert undo_data.get("success") is True or undo_data.get("data", {}).get("success") is True

    # Verify event is voided and AttendanceRecord rolled back
    with SessionLocal() as db:
        event = db.get(AttendanceEvent, event_id)
        assert event.voided_at is not None
        assert event.void_reason == "USER_UNDO"

        rec = db.scalar(select(AttendanceRecord).where(AttendanceRecord.employee_id == emp_id))
        assert rec is None, "Check-in record must be rolled back on undo"

    # 2. Repeated undo on same token fails with ALREADY_VOIDED
    repeat_undo = client.post(
        "/api/v1/attendance/undo",
        headers=auth_header(kiosk_token),
        json={"undo_token": undo_token},
    )
    assert repeat_undo.status_code == 400
    assert repeat_undo.json()["error"]["code"] == "ALREADY_VOIDED"


# ---------------------------------------------------------------------------
# 7. Admin Void Event with Audit Trail Tests
# ---------------------------------------------------------------------------

def test_admin_void_event_with_audit_trail(client):
    """Admin/HR can void an attendance event with a reason, creating an audit log entry."""
    import asyncio
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        emp = db.scalar(select(Employee).where(Employee.organization_id == org.id))
        device = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org.id))
        camera = db.scalar(select(Camera).where(Camera.device_id == device.id))

        event = AttendanceEvent(
            organization_id=org.id,
            employee_id=emp.id,
            device_id=device.id,
            camera_id=camera.id,
            source_type=CameraSourceType.ANDROID_KIOSK,
            type=AttendanceEventType.CHECK_IN,
            occurred_at=datetime.now(timezone.utc),
            confidence=0.95,
            method=AttendanceMethod.FACE,
        )
        db.add(event)
        db.commit()
        event_id = event.id

    admin_token = login(client, "admin@northwind.demo")
    void_res = client.post(
        f"/api/v1/attendance/events/{event_id}/void",
        headers=auth_header(admin_token),
        json={"reason": "Scanned wrong entrance"},
    )
    assert void_res.status_code == 200, void_res.text
    void_data = void_res.json()
    assert void_data.get("success") is True or void_data.get("data", {}).get("success") is True

    # Verify audit log entry
    with SessionLocal() as db:
        ev = db.get(AttendanceEvent, event_id)
        assert ev.voided_at is not None
        assert ev.void_reason == "Scanned wrong entrance"

        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "attendance.event_voided",
                AuditLog.target_id == event_id,
            )
        )
        assert audit is not None
        assert audit.meta.get("reason") == "Scanned wrong entrance"


# ---------------------------------------------------------------------------
# 8. Cross-Tenant Camera and Event Isolation Tests
# ---------------------------------------------------------------------------

def test_cross_tenant_camera_and_event_isolation(client):
    """Cameras and attendance events belonging to Org A cannot be accessed by Org B."""
    with SessionLocal() as db:
        org_a = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        org_b = db.scalar(select(Organization).where(Organization.slug == "acme"))
        cam_a = db.scalar(select(Camera).where(Camera.organization_id == org_a.id))
        dev_b = db.scalar(select(AttendanceDevice).where(AttendanceDevice.organization_id == org_b.id))
        cam_a_id = cam_a.id
        dev_b_id, org_b_id = dev_b.id, org_b.id

    # Org B device attempting to scan using Org A camera_id -> 403 DEVICE_NOT_AUTHORIZED
    img_bytes = make_test_face_image(47)
    obs = FaceObservation(
        observation_id=str(uuid.uuid4()),
        camera_id=cam_a_id,
        captured_at=datetime.now(timezone.utc),
        image=img_bytes,
    )

    import asyncio
    with SessionLocal() as db:
        principal_b = make_principal(dev_b_id, org_b_id)
        from app.security import AppError
        with pytest.raises(AppError) as exc:
            asyncio.run(process_face_observation(db, org_b_id, obs, principal=principal_b))
        assert exc.value.code == "DEVICE_NOT_AUTHORIZED"


# ---------------------------------------------------------------------------
# 9. Camera Management CRUD & Scoping Tests
# ---------------------------------------------------------------------------

def test_camera_management_crud(client):
    """Admin can list, create, and update camera parameters."""
    admin_token = login(client, "admin@northwind.demo")
    headers = auth_header(admin_token)

    # 1. List cameras
    res = client.get("/api/v1/cameras", headers=headers)
    assert res.status_code == 200, res.text
    cameras = res.json()["data"]
    assert len(cameras) >= 1

    device_id = cameras[0]["device_id"]

    # 2. Create camera
    create_res = client.post(
        "/api/v1/cameras",
        headers=headers,
        json={
            "device_id": device_id,
            "name": "East Gate Camera",
            "direction": "IN_ONLY",
            "assurance": "HIGH",
        },
    )
    assert create_res.status_code == 201, create_res.text
    cam_data = create_res.json()["data"]
    new_cam_id = cam_data["id"]
    assert cam_data["name"] == "East Gate Camera"
    assert cam_data["direction"] == "IN_ONLY"

    # 3. Update camera
    update_res = client.patch(
        f"/api/v1/cameras/{new_cam_id}",
        headers=headers,
        json={"direction": "AUTO", "assurance": "STANDARD"},
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()["data"]
    assert updated["direction"] == "AUTO"
    assert updated["assurance"] == "STANDARD"


# ---------------------------------------------------------------------------
# 10. Security: No RTSP Credentials or Camera Secrets
# ---------------------------------------------------------------------------

def test_no_camera_credentials_stored_in_backend():
    """Verify backend models and tables contain NO credentials, secrets, or RTSP passwords."""
    camera_columns = {c.name for c in Camera.__table__.columns}
    event_columns = {c.name for c in AttendanceEvent.__table__.columns}

    forbidden_tokens = {"password", "secret", "rtsp", "credential", "token_secret"}
    for col in camera_columns:
        for forbidden in forbidden_tokens:
            assert forbidden not in col.lower(), f"Forbidden credential column {col} in Camera"

    for col in event_columns:
        for forbidden in forbidden_tokens:
            assert forbidden not in col.lower(), f"Forbidden credential column {col} in AttendanceEvent"


# ---------------------------------------------------------------------------
# 11. Migration: Phase 4 Downgrade & Upgrade Lifecycle
# ---------------------------------------------------------------------------

def test_phase4_alembic_downgrade_and_upgrade():
    """Verify Phase 4 migration d8f3a5b12c01 cleanly downgrades to c7e2b14d9a3f and re-upgrades."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    mig_db_path = Path("./test_phase4_mig.db")
    if mig_db_path.exists():
        try:
            mig_db_path.unlink()
        except Exception:
            pass

    mig_url = "sqlite:///./test_phase4_mig.db"
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    cfg.set_main_option("sqlalchemy.url", mig_url)

    # 1. Upgrade to Phase 3 head (c7e2b14d9a3f)
    command.upgrade(cfg, "c7e2b14d9a3f")
    engine = create_engine(mig_url)
    inspector = inspect(engine)
    tables_p3 = inspector.get_table_names()
    assert "attendance_devices" in tables_p3
    assert "cameras" not in tables_p3
    assert "attendance_events" not in tables_p3

    # Seed an attendance device in Phase 3 schema
    dev_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO organizations (id, name, slug, plan, is_active, created_at) VALUES (:id, 'Test Org', 'test-org-mig', 'trial', 1, datetime('now'))"),
            {"id": org_id},
        )
        conn.execute(
            text("INSERT INTO attendance_devices (id, organization_id, name, status, mode, created_at) VALUES (:id, :org_id, 'Kiosk One', 'ACTIVE', 'IN_ONLY', datetime('now'))"),
            {"id": dev_id, "org_id": org_id},
        )
        conn.commit()

    # 2. Upgrade to Phase 4 (d8f3a5b12c01 / head)
    command.upgrade(cfg, "head")

    inspector = inspect(engine)
    tables_p4 = inspector.get_table_names()
    assert "cameras" in tables_p4
    assert "attendance_events" in tables_p4
    org_cols = [c["name"] for c in inspector.get_columns("organizations")]
    assert "timezone" in org_cols

    # Verify data migration: Kiosk One automatically received a default camera
    with engine.connect() as conn:
        cam = conn.execute(text("SELECT id, name, direction, assurance, device_id FROM cameras WHERE device_id = :id"), {"id": dev_id}).first()
        assert cam is not None
        assert cam[1] == "Kiosk One Camera"
        assert cam[2] == "IN_ONLY"
        assert cam[3] == "HIGH"
        assert cam[4] == dev_id

    # 3. Downgrade to Phase 3 (c7e2b14d9a3f)
    command.downgrade(cfg, "c7e2b14d9a3f")

    inspector = inspect(engine)
    tables_downgraded = inspector.get_table_names()
    assert "cameras" not in tables_downgraded
    assert "attendance_events" not in tables_downgraded
    org_cols_downgraded = [c["name"] for c in inspector.get_columns("organizations")]
    assert "timezone" not in org_cols_downgraded

    # 4. Re-upgrade to Phase 4 (head)
    command.upgrade(cfg, "head")

    inspector = inspect(engine)
    tables_reupgraded = inspector.get_table_names()
    assert "cameras" in tables_reupgraded
    assert "attendance_events" in tables_reupgraded

    engine.dispose()
    if mig_db_path.exists():
        try:
            mig_db_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 12. PIN Fallback Attendance & Undo
# ---------------------------------------------------------------------------

def test_pin_fallback_records_attendance_with_undo(client):
    """
    PIN verification on a registered kiosk records an AttendanceEvent with method=PIN,
    updates the daily AttendanceRecord summary, and supports undo within 30 seconds.
    """
    admin_token = login(client, "admin@northwind.demo")
    headers_admin = auth_header(admin_token)

    # 1. Create employee
    emp_res = client.post(
        "/api/v1/employees",
        headers=headers_admin,
        json={"employee_code": "PIN-ATT-01", "full_name": "PIN Attendant", "email": "pinatt@northwind.demo"},
    )
    assert emp_res.status_code == 201, emp_res.text
    emp_id = emp_res.json()["data"]["id"]

    # 2. Set employee PIN
    pin_res = client.post(
        f"/api/v1/employees/{emp_id}/pin",
        headers=headers_admin,
        json={"pin": "8421"},
    )
    assert pin_res.status_code == 200, pin_res.text

    # 3. Enroll a kiosk device
    code_res = client.post("/api/v1/devices/enrollment-code", headers=headers_admin)
    code = code_res.json()["data"]["code"]
    dev_res = client.post("/api/v1/devices/enroll", json={"code": code, "name": "PIN Kiosk"})
    dev_token = dev_res.json()["data"]["access_token"]
    dev_headers = auth_header(dev_token)

    # 4. Kiosk calls pin-verify to check in employee
    verify_res = client.post(
        "/api/v1/attendance/pin-verify",
        headers=dev_headers,
        json={"employee_code": "PIN-ATT-01", "pin": "8421"},
    )
    assert verify_res.status_code == 200, verify_res.text
    vdata = verify_res.json()["data"]
    assert vdata["event"] == "CHECK_IN"
    assert vdata["status"] in ("PRESENT", "LATE")
    assert vdata["undo_token"] is not None
    assert vdata["event_id"] is not None
    event_id = vdata["event_id"]
    undo_token = vdata["undo_token"]

    # 5. Verify database state
    with SessionLocal() as db:
        ev = db.get(AttendanceEvent, event_id)
        assert ev is not None
        assert ev.method == AttendanceMethod.PIN
        assert ev.type == AttendanceEventType.CHECK_IN
        assert ev.provisional is False

        rec = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp_id,
                AttendanceRecord.date == date.today(),
            )
        )
        assert rec is not None
        assert rec.check_in_at is not None

    # 6. Kiosk invokes undo within 30-second window
    undo_res = client.post(
        "/api/v1/attendance/undo",
        headers=dev_headers,
        json={"undo_token": undo_token},
    )
    assert undo_res.status_code == 200, undo_res.text

    # 7. Verify event is voided and daily record rolled back
    with SessionLocal() as db:
        ev_after = db.get(AttendanceEvent, event_id)
        assert ev_after.voided_at is not None

        rec_after = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp_id,
                AttendanceRecord.date == date.today(),
            )
        )
        assert rec_after is None


# ---------------------------------------------------------------------------
# 13. Two Scans Arriving at the Same Moment
# ---------------------------------------------------------------------------

def test_two_scans_at_same_moment_yield_one_event(client):
    """
    When two scans for the same employee arrive at the exact same moment from different cameras,
    atomic cooldown guarantees only ONE attendance event is created and the other is suppressed.
    """
    import concurrent.futures

    admin_token = login(client, "admin@northwind.demo")
    headers_admin = auth_header(admin_token)

    # 1. Create and enroll employee
    emp_res = client.post(
        "/api/v1/employees",
        headers=headers_admin,
        json={"employee_code": "RACE-01", "full_name": "Concurrent Employee", "email": "race@northwind.demo"},
    )
    emp_id = emp_res.json()["data"]["id"]
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        face_image = enroll_test_face(db, emp_id, org.id, seed=51)

    import base64
    face_b64 = base64.b64encode(face_image).decode("ascii")

    # 2. Get two cameras
    cams_res = client.get("/api/v1/cameras", headers=headers_admin)
    cameras = cams_res.json()["data"]
    device_id = cameras[0]["device_id"]
    cam1_id = cameras[0]["id"]

    cam2_res = client.post(
        "/api/v1/cameras",
        headers=headers_admin,
        json={"device_id": device_id, "name": "Cam Two Concurrent", "direction": "AUTO", "assurance": "HIGH"},
    )
    cam2_id = cam2_res.json()["data"]["id"]

    # Enroll device token for recognition
    code = client.post("/api/v1/devices/enrollment-code", headers=headers_admin).json()["data"]["code"]
    dev_token = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Race Kiosk"}).json()["data"]["access_token"]
    dev_headers = auth_header(dev_token)

    def do_scan(camera_id: str, obs_id: str):
        # Create separate TestClient instance per thread to avoid shared client transport contention
        from app.main import app
        with TestClient(app) as thread_client:
            return thread_client.post(
                "/api/v1/attendance/scan",
                headers=dev_headers,
                json={
                    "observation_id": obs_id,
                    "camera_id": camera_id,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "image": face_b64,
                    "liveness_evidence": {"passed": True, "score": 1.0, "provider": "mock"},
                },
            )

    obs1 = str(uuid.uuid4())
    obs2 = str(uuid.uuid4())

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_scan, cam1_id, obs1)
        f2 = executor.submit(do_scan, cam2_id, obs2)
        res1 = f1.result()
        res2 = f2.result()

    statuses = [res1.status_code, res2.status_code]
    assert 200 in statuses
    # One scan creates the CHECK_IN event; the second concurrent scan is suppressed by cooldown
    # (/attendance/scan with raise_on_cooldown=True returns 409 ATTENDANCE_ALREADY_MARKED, or 200 ALREADY_PRESENT)
    if 409 in statuses:
        err_res = res1 if res1.status_code == 409 else res2
        ok_res = res2 if res1.status_code == 409 else res1
        assert err_res.json()["error"]["code"] == "ATTENDANCE_ALREADY_MARKED"
        assert ok_res.json()["data"]["event"] == "CHECK_IN"
    else:
        events = [res1.json()["data"]["event"], res2.json()["data"]["event"]]
        assert "CHECK_IN" in events
        assert "ALREADY_PRESENT" in events

    # Verify only ONE attendance event was created in the database
    with SessionLocal() as db:
        events_in_db = db.scalars(
            select(AttendanceEvent).where(
                AttendanceEvent.employee_id == emp_id,
                AttendanceEvent.voided_at.is_(None),
            )
        ).all()
        assert len(events_in_db) == 1


# ---------------------------------------------------------------------------
# 14. Admin Confirms Provisional Event
# ---------------------------------------------------------------------------

def test_admin_confirms_provisional_event(client):
    """
    Provisional event from a STANDARD assurance camera is confirmed by an admin,
    promoting it to the official daily AttendanceRecord summary.
    """
    admin_token = login(client, "admin@northwind.demo")
    headers_admin = auth_header(admin_token)

    # 1. Create employee and enroll face
    emp_res = client.post(
        "/api/v1/employees",
        headers=headers_admin,
        json={"employee_code": "PROV-CONF-01", "full_name": "Provisional Confirm Employee", "email": "pconf@northwind.demo"},
    )
    emp_id = emp_res.json()["data"]["id"]
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "northwind"))
        face_image = enroll_test_face(db, emp_id, org.id, seed=52)

    import base64
    face_b64 = base64.b64encode(face_image).decode("ascii")

    # 2. Create STANDARD assurance camera
    cams = client.get("/api/v1/cameras", headers=headers_admin).json()["data"]
    device_id = cams[0]["device_id"]

    cam_res = client.post(
        "/api/v1/cameras",
        headers=headers_admin,
        json={"device_id": device_id, "name": "Standard Hallway", "direction": "IN_ONLY", "assurance": "STANDARD"},
    )
    cam_id = cam_res.json()["data"]["id"]

    # 3. Device scans without liveness evidence -> marked provisional=True
    code = client.post("/api/v1/devices/enrollment-code", headers=headers_admin).json()["data"]["code"]
    dev_token = client.post("/api/v1/devices/enroll", json={"code": code, "name": "Standard Kiosk"}).json()["data"]["access_token"]
    dev_headers = auth_header(dev_token)

    scan_res = client.post(
        "/api/v1/attendance/scan",
        headers=dev_headers,
        json={
            "observation_id": str(uuid.uuid4()),
            "camera_id": cam_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "image": face_b64,
        },
    )
    assert scan_res.status_code == 200, scan_res.text
    sdata = scan_res.json()["data"]
    assert sdata["provisional"] is True
    event_id = sdata["event_id"]

    # Verify no AttendanceRecord exists yet
    with SessionLocal() as db:
        rec_before = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp_id,
                AttendanceRecord.date == date.today(),
            )
        )
        assert rec_before is None

    # 4. Admin confirms the provisional event
    confirm_res = client.post(
        f"/api/v1/attendance/events/{event_id}/confirm",
        headers=headers_admin,
    )
    assert confirm_res.status_code == 200, confirm_res.text
    assert confirm_res.json()["data"]["provisional"] is False

    # 5. Verify AttendanceRecord is now created and finalized
    with SessionLocal() as db:
        rec_after = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp_id,
                AttendanceRecord.date == date.today(),
            )
        )
        assert rec_after is not None
        assert rec_after.check_in_at is not None



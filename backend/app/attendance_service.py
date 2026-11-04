"""
Camera-independent attendance engine.

Processes FaceObservations from any registered camera source (kiosks, edge agents),
enforces cross-camera cooldowns per employee, evaluates assurance policies,
enforces directionality per camera, derives daily AttendanceRecord summaries,
and supports observation idempotency and undo tokens.

CRITICAL ARCHITECTURAL CONSTRAINTS:
- Camera-independent: no imports or references to CameraX, ML Kit, RTSP, or ONVIF.
- Never log or store camera credentials or secrets.
- Organization isolation: all queries filter strictly on organization_id.
"""

from datetime import date, datetime, time, timedelta, timezone
import logging
import secrets
import threading
import time as time_mod
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .face import embed_async, find_best_match, get_engine
from .liveness import LivenessResult, get_liveness_service
from .models import (
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
    Organization,
    Role,
    Shift,
)
from .rate_limiter import check_rate_limit
from .schemas import FaceObservation, ObservationResult
from .security import AppError, Principal, record_audit

logger = logging.getLogger("faceattend.attendance")
settings = get_settings()

_cooldown_lock = threading.Lock()
_memory_cooldown_store: dict[tuple[str, str], float] = {}


def acquire_concurrency_lock(organization_id: str, employee_id: str, lock_ttl_seconds: int = 5) -> bool:
    """
    Atomically attempts to acquire a short-lived concurrency lock for an employee.
    Used to prevent duplicate event creation when two scans arrive at the exact same moment.
    Returns True if acquired (no concurrent scan in flight).
    Returns False if another scan is in-flight at this exact moment.

    Uses Redis atomic SET NX EX if redis_url is configured.
    Falls back to a thread-safe mutex and in-memory TTL dictionary for single-instance / test suites.
    """
    current_settings = get_settings()
    if current_settings.redis_url:
        try:
            import redis
            r = redis.Redis.from_url(current_settings.redis_url)
            key = f"attendance:lock:{organization_id}:{employee_id}"
            acquired = r.set(key, "1", ex=lock_ttl_seconds, nx=True)
            return bool(acquired)
        except Exception as exc:
            logger.warning("Redis concurrency lock failed; falling back to in-memory store: %s", exc)

    now = time_mod.time()
    key = (organization_id, employee_id)
    with _cooldown_lock:
        expires_at = _memory_cooldown_store.get(key, 0.0)
        if now < expires_at:
            return False
        _memory_cooldown_store[key] = now + lock_ttl_seconds
        # Clean expired keys if dictionary grows large
        if len(_memory_cooldown_store) > 5000:
            for k in list(_memory_cooldown_store.keys()):
                if _memory_cooldown_store[k] <= now:
                    del _memory_cooldown_store[k]
        return True


def release_concurrency_lock(organization_id: str, employee_id: str) -> None:
    """Releases the short-lived concurrency lock."""
    current_settings = get_settings()
    if current_settings.redis_url:
        try:
            import redis
            r = redis.Redis.from_url(current_settings.redis_url)
            r.delete(f"attendance:lock:{organization_id}:{employee_id}")
        except Exception:
            pass
    key = (organization_id, employee_id)
    with _cooldown_lock:
        _memory_cooldown_store.pop(key, None)


def reset_cooldown_store() -> None:
    """Resets the in-memory cooldown/concurrency store (primarily for test isolation)."""
    with _cooldown_lock:
        _memory_cooldown_store.clear()




# ---------------------------------------------------------------------------
# Timezone & Shift Resolution
# ---------------------------------------------------------------------------

def get_org_timezone(org: Organization | None) -> ZoneInfo:
    """Resolves an organization's configured IANA timezone, defaulting to UTC."""
    if org is None or not org.timezone:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(org.timezone)
    except (ZoneInfoNotFoundError, Exception):
        return ZoneInfo("UTC")


def compute_shift_lateness_and_date(
    moment_utc: datetime,
    shift: Shift | None,
    tz: ZoneInfo,
) -> tuple[date, int, AttendanceStatus]:
    """
    Computes the effective attendance date, lateness (in minutes), and initial
    status in the organization's local timezone.
    Explicitly supports overnight shifts (e.g. 22:00 to 06:00).
    """
    moment_local = moment_utc.astimezone(tz)

    if shift is not None:
        start_hour, start_minute = (int(p) for p in shift.start_time.split(":"))
        end_hour, end_minute = (int(p) for p in shift.end_time.split(":"))
        grace_minutes = shift.grace_minutes
    else:
        start_hour, start_minute = settings.shift_start_hour, 0
        end_hour, end_minute = 17, 0
        grace_minutes = settings.shift_grace_minutes

    is_overnight = (start_hour > end_hour) or (start_hour == end_hour and start_minute > end_minute)

    if is_overnight:
        # If the punch occurs in the early morning after midnight before shift end (e.g. 02:00),
        # it belongs to the previous calendar day's shift cycle.
        if moment_local.time() <= time(end_hour, end_minute) or moment_local.hour < (start_hour - 4):
            effective_date = moment_local.date() - timedelta(days=1)
        else:
            effective_date = moment_local.date()
    else:
        effective_date = moment_local.date()

    shift_start_dt = datetime(
        effective_date.year,
        effective_date.month,
        effective_date.day,
        start_hour,
        start_minute,
        tzinfo=tz,
    )

    grace_cutoff = shift_start_dt + timedelta(minutes=grace_minutes)

    if moment_local <= grace_cutoff:
        late_minutes = 0
        status = AttendanceStatus.PRESENT
    else:
        # Standard lateness: elapsed minutes from scheduled shift start once grace is exceeded
        late_minutes = int((moment_local - shift_start_dt).total_seconds() // 60)
        status = AttendanceStatus.LATE

    return effective_date, late_minutes, status


# ---------------------------------------------------------------------------
# Assurance Policy Hook
# ---------------------------------------------------------------------------

def evaluate_assurance_policy(
    camera: Camera,
    has_liveness: bool,
    active_settings: Settings | None = None,
) -> tuple[bool, bool]:
    """
    Evaluates camera assurance against liveness evidence.
    Returns: (is_allowed, is_provisional)
    - If camera assurance is STANDARD and no liveness evidence is present,
      the event is allowed but marked provisional=True.
    - If camera assurance is HIGH and no liveness evidence is present,
      the observation is rejected unless liveness is globally disabled.
    """
    cfg = active_settings or settings

    if camera.assurance == CameraAssurance.STANDARD:
        if not has_liveness and cfg.standard_assurance_provisional:
            return True, True
        return True, False

    elif camera.assurance == CameraAssurance.HIGH:
        if cfg.liveness_mode == "disabled":
            return True, False
        if not has_liveness:
            return False, False
        return True, False

    return True, False


# ---------------------------------------------------------------------------
# Undo Token Lifecycle
# ---------------------------------------------------------------------------

def create_undo_token(event_id: str, organization_id: str, expires_in_seconds: int = 30) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "attendance_undo",
        "event_id": event_id,
        "org_id": organization_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_undo_token(token: str, organization_id: str) -> str:
    """Verifies the undo token and returns the event_id if valid and unexpired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AppError("UNDO_EXPIRED", "The undo window of 30 seconds has expired.", 400)
    except Exception:
        raise AppError("INVALID_TOKEN", "Invalid undo token.", 400)

    if payload.get("sub") != "attendance_undo":
        raise AppError("INVALID_TOKEN", "Token is not an undo token.", 400)
    if payload.get("org_id") != organization_id:
        raise AppError("FORBIDDEN", "Cross-tenant undo token rejected.", 403)

    return payload["event_id"]


# ---------------------------------------------------------------------------
# Core Attendance Observation Processing
# ---------------------------------------------------------------------------

async def process_face_observation(
    db: Session,
    organization_id: str,
    observation: FaceObservation,
    principal: Principal,
    raise_on_cooldown: bool = False,
) -> ObservationResult:
    """
    Main service entrypoint: processes a camera-independent FaceObservation.
    1. Idempotency verification via observation_id.
    2. Camera authorization and direction validation.
    3. Assurance policy evaluation (STANDARD provisional vs HIGH enforcement).
    4. Face match and cross-camera per-employee cooldown enforcement.
    5. Event emission and AttendanceRecord synchronization.
    """
    # 1. Observation Idempotency: check if already processed
    existing_event = db.scalar(
        select(AttendanceEvent).where(
            AttendanceEvent.organization_id == organization_id,
            AttendanceEvent.idempotency_key == observation.observation_id,
        )
    )
    if existing_event is not None:
        return _build_result_from_existing_event(db, existing_event)

    # 2. Camera Verification
    camera = db.scalar(
        select(Camera).where(
            Camera.id == observation.camera_id,
            Camera.organization_id == organization_id,
        )
    )
    if camera is None or not camera.enabled:
        raise AppError("DEVICE_NOT_AUTHORIZED", "Camera is not registered or disabled.", 403)

    # Update camera last_seen_at throttled
    now = datetime.now(timezone.utc)
    if camera.last_seen_at is None or (now - camera.last_seen_at.replace(tzinfo=timezone.utc)).total_seconds() > 60:
        camera.last_seen_at = now

    # 3. Liveness Evidence & Assurance Policy
    has_liveness = False
    liveness_score = 0.0
    liveness_provider = "none"

    if observation.liveness_evidence:
        evidence = observation.liveness_evidence
        # If evidence was already verified or contains active challenge parameters:
        if evidence.get("passed"):
            has_liveness = True
            liveness_score = float(evidence.get("score", 1.0))
            liveness_provider = str(evidence.get("provider", "active"))
        elif "challenge_id" in evidence and "burst_frames" in evidence:
            liveness_res = get_liveness_service().verify_challenge(
                challenge_id=evidence["challenge_id"],
                nonce=evidence.get("nonce", ""),
                device_id=camera.device_id,
                organization_id=organization_id,
                burst_frames=evidence["burst_frames"],
                primary_vector=evidence.get("primary_vector"),
                tracking_bbox=evidence.get("tracking_bbox"),
            )
            has_liveness = liveness_res.passed
            liveness_score = liveness_res.score
            liveness_provider = liveness_res.provider

    allowed, is_provisional = evaluate_assurance_policy(camera, has_liveness, settings)
    if not allowed:
        raise AppError("LIVENESS_FAILED", "Liveness verification failed or required for camera.", 422)

    # 4. Face Recognition Matching
    if observation.image is None:
        raise AppError("INVALID_OBSERVATION", "Face observation must include image bytes.", 422)

    if isinstance(observation.image, bytes):
        image_bytes = observation.image
    elif isinstance(observation.image, str):
        import base64
        try:
            image_bytes = base64.b64decode(observation.image)
        except Exception:
            image_bytes = observation.image.encode()
    else:
        image_bytes = bytes(observation.image)
    embedding = await embed_async(image_bytes)
    match = find_best_match(db, organization_id, embedding.vector)

    if match is None:
        record_audit(
            db,
            action="attendance.unrecognized",
            principal=principal,
            camera_id=camera.id,
            device_id=camera.device_id,
            liveness_score=liveness_score,
        )
        db.commit()
        raise AppError("FACE_NOT_RECOGNIZED", "Face could not be recognized.", 404)

    employee = match.employee
    org = db.get(Organization, organization_id)
    org_tz = get_org_timezone(org)
    attendance_date, late_minutes, status = compute_shift_lateness_and_date(now, employee.shift, org_tz)

    # 5. Cooldown & Duplicate Prevention: PER EMPLOYEE ACROSS ALL CAMERAS
    # Fetch existing AttendanceRecord for this employee and date first
    record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == organization_id,
            AttendanceRecord.employee_id == employee.id,
            AttendanceRecord.date == attendance_date,
        )
    )

    is_checkout_time = (
        record is not None
        and record.check_in_at is not None
        and record.check_out_at is None
        and (now - record.check_in_at.replace(tzinfo=timezone.utc)).total_seconds() / 60 >= settings.checkout_after_minutes
    )

    # 5. Cooldown & Duplicate Prevention: PER EMPLOYEE ACROSS ALL CAMERAS
    cooldown_cutoff = now - timedelta(seconds=settings.attendance_cooldown_seconds)
    recent_active_event = db.scalar(
        select(AttendanceEvent)
        .where(
            AttendanceEvent.organization_id == organization_id,
            AttendanceEvent.employee_id == employee.id,
            AttendanceEvent.voided_at.is_(None),
            AttendanceEvent.occurred_at >= cooldown_cutoff,
        )
        .order_by(AttendanceEvent.occurred_at.desc())
    )

    if recent_active_event is not None and not is_checkout_time:
        if raise_on_cooldown:
            raise AppError("ATTENDANCE_ALREADY_MARKED", "Attendance was already marked recently.", 409)
        # Suppress duplicate event creation and return existing state as ALREADY_PRESENT
        record_audit(
            db,
            action="attendance.cooldown_suppressed",
            principal=principal,
            target_type="employee",
            target_id=employee.id,
            camera_id=camera.id,
        )
        db.commit()
        return ObservationResult(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department.name if employee.department else "",
            event="ALREADY_PRESENT",
            recorded_at=recent_active_event.occurred_at,
            status=record.status if record else AttendanceStatus.PRESENT,
            late_minutes=record.late_minutes if record else 0,
            match_confidence=match.confidence,
            liveness_score=liveness_score,
            undo_token=None,
            provisional=recent_active_event.provisional,
            event_id=recent_active_event.id,
            check_in_at=record.check_in_at if record else None,
            check_out_at=record.check_out_at if record else None,
        )

    # 6. Direction Enforcement Per Camera

    event_type: AttendanceEventType
    if camera.direction == CameraDirection.IN_ONLY:
        if record is not None and record.check_in_at is not None:
            # Already checked in: IN_ONLY camera cannot check out
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=match.confidence,
                liveness_score=liveness_score,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        event_type = AttendanceEventType.CHECK_IN

    elif camera.direction == CameraDirection.OUT_ONLY:
        # OUT_ONLY camera NEVER produces CHECK_IN
        if record is None or record.check_in_at is None:
            raise AppError("DIRECTION_MISMATCH", "Exit camera cannot record check-in.", 400)
        if record.check_out_at is not None:
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=match.confidence,
                liveness_score=liveness_score,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        event_type = AttendanceEventType.CHECK_OUT

    else:  # AUTO
        if record is None or record.check_in_at is None:
            event_type = AttendanceEventType.CHECK_IN
        elif record.check_out_at is not None:
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=match.confidence,
                liveness_score=liveness_score,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        else:
            since_check_in = (now - record.check_in_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
            if since_check_in < settings.checkout_after_minutes:
                return ObservationResult(
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    full_name=employee.full_name,
                    department=employee.department.name if employee.department else "",
                    event="ALREADY_PRESENT",
                    recorded_at=now,
                    status=record.status,
                    late_minutes=record.late_minutes,
                    match_confidence=match.confidence,
                    liveness_score=liveness_score,
                    undo_token=None,
                    provisional=False,
                    event_id=None,
                    check_in_at=record.check_in_at,
                    check_out_at=record.check_out_at,
                )
            event_type = AttendanceEventType.CHECK_OUT

    # 7. Create Immutable AttendanceEvent
    # Concurrency lock prevents race conditions if two scans arrive at the exact same moment
    if not is_checkout_time and not acquire_concurrency_lock(organization_id, employee.id, lock_ttl_seconds=5):
        record_audit(
            db,
            action="attendance.cooldown_suppressed",
            principal=principal,
            target_type="employee",
            target_id=employee.id,
            camera_id=camera.id,
        )
        db.commit()
        return ObservationResult(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department.name if employee.department else "",
            event="ALREADY_PRESENT",
            recorded_at=now,
            status=record.status if record else AttendanceStatus.PRESENT,
            late_minutes=record.late_minutes if record else 0,
            match_confidence=match.confidence,
            liveness_score=liveness_score,
            undo_token=None,
            provisional=False,
            event_id=None,
            check_in_at=record.check_in_at if record else None,
            check_out_at=record.check_out_at if record else None,
        )

    event = AttendanceEvent(
        organization_id=organization_id,
        employee_id=employee.id,
        device_id=camera.device_id,
        camera_id=camera.id,
        source_type=camera.source_type,
        type=event_type,
        occurred_at=now,
        confidence=match.confidence,
        method=AttendanceMethod.FACE,
        idempotency_key=observation.observation_id,
        provisional=is_provisional,
    )
    db.add(event)
    db.flush()

    # 8. Synchronize / Derive Daily AttendanceRecord (Only if NOT provisional)
    if not is_provisional:
        if record is None:
            record = AttendanceRecord(
                organization_id=organization_id,
                employee_id=employee.id,
                date=attendance_date,
                check_in_at=now,
                status=status,
                late_minutes=late_minutes,
                match_confidence=match.confidence,
                liveness_score=liveness_score,
                device_label=camera.name,
            )
            db.add(record)
        else:
            if event_type == AttendanceEventType.CHECK_OUT:
                record.check_out_at = now
            elif event_type == AttendanceEventType.CHECK_IN and record.check_in_at is None:
                record.check_in_at = now
            record.match_confidence = match.confidence
            record.liveness_score = liveness_score

    record_audit(
        db,
        action=f"attendance.{event_type.value.lower()}",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        camera_id=camera.id,
        provisional=is_provisional,
        event_id=event.id,
        status=status.value if record else "PROVISIONAL",
        late_minutes=late_minutes,
    )
    db.commit()
    release_concurrency_lock(organization_id, employee.id)

    undo_token = create_undo_token(event.id, organization_id, settings.undo_window_seconds)

    return ObservationResult(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department.name if employee.department else "",
        event=event_type.value,
        recorded_at=now,
        status=record.status if record else status,
        late_minutes=late_minutes,
        match_confidence=match.confidence,
        liveness_score=liveness_score,
        undo_token=undo_token,
        provisional=is_provisional,
        event_id=event.id,
        check_in_at=record.check_in_at if record else (now if event_type == AttendanceEventType.CHECK_IN else None),
        check_out_at=record.check_out_at if record else (now if event_type == AttendanceEventType.CHECK_OUT else None),
    )


def _build_result_from_existing_event(db: Session, event: AttendanceEvent) -> ObservationResult:
    """Builds an idempotent ObservationResult from an existing event row."""
    employee = event.employee
    org = db.get(Organization, event.organization_id)
    org_tz = get_org_timezone(org)
    att_date, _, _ = compute_shift_lateness_and_date(event.occurred_at.replace(tzinfo=timezone.utc), employee.shift, org_tz)

    record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == event.organization_id,
            AttendanceRecord.employee_id == employee.id,
            AttendanceRecord.date == att_date,
        )
    )
    return ObservationResult(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department.name if employee.department else "",
        event=event.type.value,
        recorded_at=event.occurred_at,
        status=record.status if record else AttendanceStatus.PRESENT,
        late_minutes=record.late_minutes if record else 0,
        match_confidence=event.confidence,
        liveness_score=1.0,
        undo_token=None,
        provisional=event.provisional,
        event_id=event.id,
        check_in_at=record.check_in_at if record else None,
        check_out_at=record.check_out_at if record else None,
    )


# ---------------------------------------------------------------------------
# Employee PIN Fallback Attendance Processing
# ---------------------------------------------------------------------------

def process_pin_attendance(
    db: Session,
    organization_id: str,
    employee: Employee,
    principal: Principal,
    camera: Camera,
    raise_on_cooldown: bool = False,
) -> ObservationResult:
    """
    Processes PIN fallback attendance for an employee from a registered kiosk.
    Emits an AttendanceEvent with method=AttendanceMethod.PIN, confidence=1.0, provisional=False.
    Enforces camera directionality, shift lateness in org timezone, cross-camera cooldown,
    and derives daily AttendanceRecord summary.
    """
    now = datetime.now(timezone.utc)
    org = db.get(Organization, organization_id)
    org_tz = get_org_timezone(org)
    attendance_date, late_minutes, status = compute_shift_lateness_and_date(now, employee.shift, org_tz)

    record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == organization_id,
            AttendanceRecord.employee_id == employee.id,
            AttendanceRecord.date == attendance_date,
        )
    )

    is_checkout_time = (
        record is not None
        and record.check_in_at is not None
        and record.check_out_at is None
        and (now - record.check_in_at.replace(tzinfo=timezone.utc)).total_seconds() / 60 >= settings.checkout_after_minutes
    )

    cooldown_cutoff = now - timedelta(seconds=settings.attendance_cooldown_seconds)
    recent_active_event = db.scalar(
        select(AttendanceEvent)
        .where(
            AttendanceEvent.organization_id == organization_id,
            AttendanceEvent.employee_id == employee.id,
            AttendanceEvent.voided_at.is_(None),
            AttendanceEvent.occurred_at >= cooldown_cutoff,
        )
        .order_by(AttendanceEvent.occurred_at.desc())
    )

    if recent_active_event is not None and not is_checkout_time:
        if raise_on_cooldown:
            raise AppError("ATTENDANCE_ALREADY_MARKED", "Attendance was already marked recently.", 409)
        record_audit(
            db,
            action="attendance.cooldown_suppressed",
            principal=principal,
            target_type="employee",
            target_id=employee.id,
            camera_id=camera.id,
            method="PIN",
        )
        db.commit()
        return ObservationResult(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department.name if employee.department else "",
            event="ALREADY_PRESENT",
            recorded_at=recent_active_event.occurred_at,
            status=record.status if record else AttendanceStatus.PRESENT,
            late_minutes=record.late_minutes if record else 0,
            match_confidence=1.0,
            liveness_score=1.0,
            undo_token=None,
            provisional=False,
            event_id=recent_active_event.id,
            check_in_at=record.check_in_at if record else None,
            check_out_at=record.check_out_at if record else None,
        )

    # Direction enforcement
    event_type: AttendanceEventType
    if camera.direction == CameraDirection.IN_ONLY:
        if record is not None and record.check_in_at is not None:
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=1.0,
                liveness_score=1.0,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        event_type = AttendanceEventType.CHECK_IN

    elif camera.direction == CameraDirection.OUT_ONLY:
        if record is None or record.check_in_at is None:
            raise AppError("DIRECTION_MISMATCH", "Exit camera cannot record check-in.", 400)
        if record.check_out_at is not None:
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=1.0,
                liveness_score=1.0,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        event_type = AttendanceEventType.CHECK_OUT

    else:  # AUTO
        if record is None or record.check_in_at is None:
            event_type = AttendanceEventType.CHECK_IN
        elif record.check_out_at is not None:
            return ObservationResult(
                employee_id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                department=employee.department.name if employee.department else "",
                event="ALREADY_PRESENT",
                recorded_at=now,
                status=record.status,
                late_minutes=record.late_minutes,
                match_confidence=1.0,
                liveness_score=1.0,
                undo_token=None,
                provisional=False,
                event_id=None,
                check_in_at=record.check_in_at,
                check_out_at=record.check_out_at,
            )
        else:
            since_check_in = (now - record.check_in_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
            if since_check_in < settings.checkout_after_minutes:
                return ObservationResult(
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    full_name=employee.full_name,
                    department=employee.department.name if employee.department else "",
                    event="ALREADY_PRESENT",
                    recorded_at=now,
                    status=record.status,
                    late_minutes=record.late_minutes,
                    match_confidence=1.0,
                    liveness_score=1.0,
                    undo_token=None,
                    provisional=False,
                    event_id=None,
                    check_in_at=record.check_in_at,
                    check_out_at=record.check_out_at,
                )
            event_type = AttendanceEventType.CHECK_OUT

    if not is_checkout_time and not acquire_concurrency_lock(organization_id, employee.id, lock_ttl_seconds=5):
        record_audit(
            db,
            action="attendance.cooldown_suppressed",
            principal=principal,
            target_type="employee",
            target_id=employee.id,
            camera_id=camera.id,
            method="PIN",
        )
        db.commit()
        return ObservationResult(
            employee_id=employee.id,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department.name if employee.department else "",
            event="ALREADY_PRESENT",
            recorded_at=now,
            status=record.status if record else AttendanceStatus.PRESENT,
            late_minutes=record.late_minutes if record else 0,
            match_confidence=1.0,
            liveness_score=1.0,
            undo_token=None,
            provisional=False,
            event_id=None,
            check_in_at=record.check_in_at if record else None,
            check_out_at=record.check_out_at if record else None,
        )

    idempotency_key = f"pin:{camera.device_id}:{employee.id}:{int(now.timestamp())}:{secrets.token_hex(4)}"
    event = AttendanceEvent(
        organization_id=organization_id,
        employee_id=employee.id,
        device_id=camera.device_id,
        camera_id=camera.id,
        source_type=camera.source_type,
        type=event_type,
        occurred_at=now,
        confidence=1.0,
        method=AttendanceMethod.PIN,
        idempotency_key=idempotency_key,
        provisional=False,
    )
    db.add(event)
    db.flush()

    if record is None:
        record = AttendanceRecord(
            organization_id=organization_id,
            employee_id=employee.id,
            date=attendance_date,
            check_in_at=now,
            status=status,
            late_minutes=late_minutes,
            match_confidence=1.0,
            liveness_score=1.0,
            device_label=f"{camera.name} (PIN)",
        )
        db.add(record)
    else:
        if event_type == AttendanceEventType.CHECK_OUT:
            record.check_out_at = now
        elif event_type == AttendanceEventType.CHECK_IN and record.check_in_at is None:
            record.check_in_at = now

    record_audit(
        db,
        action=f"attendance.pin_{event_type.value.lower()}",
        principal=principal,
        target_type="employee",
        target_id=employee.id,
        camera_id=camera.id,
        event_id=event.id,
        method="PIN",
    )
    db.commit()
    release_concurrency_lock(organization_id, employee.id)

    undo_token = create_undo_token(event.id, organization_id, settings.undo_window_seconds)

    return ObservationResult(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        department=employee.department.name if employee.department else "",
        event=event_type.value,
        recorded_at=now,
        status=record.status if record else status,
        late_minutes=late_minutes,
        match_confidence=1.0,
        liveness_score=1.0,
        undo_token=undo_token,
        provisional=False,
        event_id=event.id,
        check_in_at=record.check_in_at if record else (now if event_type == AttendanceEventType.CHECK_IN else None),
        check_out_at=record.check_out_at if record else (now if event_type == AttendanceEventType.CHECK_OUT else None),
    )


# ---------------------------------------------------------------------------
# Undo & Void Operations
# ---------------------------------------------------------------------------

def undo_last_event(
    db: Session,
    organization_id: str,
    undo_token: str,
    principal: Principal,
) -> str:
    """Voids the last recorded event inside the 30-second window."""
    event_id = verify_undo_token(undo_token, organization_id)
    now = datetime.now(timezone.utc)

    event = db.scalar(
        select(AttendanceEvent).where(
            AttendanceEvent.id == event_id,
            AttendanceEvent.organization_id == organization_id,
        )
    )
    if event is None:
        raise AppError("NOT_FOUND", "Attendance event not found.", 404)

    if event.voided_at is not None:
        raise AppError("ALREADY_VOIDED", "Event has already been voided.", 400)

    elapsed = (now - event.occurred_at.replace(tzinfo=timezone.utc)).total_seconds()
    if elapsed > settings.undo_window_seconds:
        raise AppError("UNDO_EXPIRED", "The undo window of 30 seconds has expired.", 400)

    event.voided_at = now
    event.void_reason = "USER_UNDO"
    db.flush()

    release_concurrency_lock(organization_id, event.employee_id)
    _recompute_daily_attendance_record(db, event)

    record_audit(
        db,
        action="attendance.undo",
        principal=principal,
        target_type="attendance_event",
        target_id=event.id,
        occurred_at=event.occurred_at.isoformat(),
    )
    db.commit()
    return event.id


def void_event_admin(
    db: Session,
    organization_id: str,
    event_id: str,
    reason: str,
    principal: Principal,
) -> str:
    """Admin/HR operation: voids an attendance event with audit trail."""
    now = datetime.now(timezone.utc)
    event = db.scalar(
        select(AttendanceEvent).where(
            AttendanceEvent.id == event_id,
            AttendanceEvent.organization_id == organization_id,
        )
    )
    if event is None:
        raise AppError("NOT_FOUND", "Attendance event not found.", 404)
    if event.voided_at is not None:
        raise AppError("ALREADY_VOIDED", "Event has already been voided.", 400)

    event.voided_at = now
    event.void_reason = reason.strip()
    db.flush()

    release_concurrency_lock(organization_id, event.employee_id)
    _recompute_daily_attendance_record(db, event)

    record_audit(
        db,
        action="attendance.event_voided",
        principal=principal,
        target_type="attendance_event",
        target_id=event.id,
        reason=event.void_reason,
    )
    db.commit()
    return event.id


def confirm_provisional_event(
    db: Session,
    organization_id: str,
    event_id: str,
    principal: Principal,
) -> AttendanceEvent:
    """
    Confirms a provisional event (e.g. from a STANDARD camera without liveness).
    Marks provisional=False, applies the event to the employee's daily AttendanceRecord,
    and logs an audit trail.
    """
    event = db.scalar(
        select(AttendanceEvent).where(
            AttendanceEvent.organization_id == organization_id,
            AttendanceEvent.id == event_id,
        )
    )
    if event is None:
        raise AppError("NOT_FOUND", "Attendance event not found.", 404)
    if event.voided_at is not None:
        raise AppError("EVENT_VOIDED", "Cannot confirm a voided event.", 400)
    if not event.provisional:
        return event

    event.provisional = False
    db.flush()

    _recompute_daily_attendance_record(db, event)

    record_audit(
        db,
        action="attendance.event_confirmed",
        principal=principal,
        target_type="attendance_event",
        target_id=event.id,
        employee_id=event.employee_id,
    )
    db.commit()
    db.refresh(event)
    return event


def _recompute_daily_attendance_record(db: Session, event: AttendanceEvent) -> None:
    """Re-derives the AttendanceRecord for the affected employee and date."""
    org = db.get(Organization, event.organization_id)
    org_tz = get_org_timezone(org)
    att_date, _, _ = compute_shift_lateness_and_date(
        event.occurred_at.replace(tzinfo=timezone.utc),
        event.employee.shift if event.employee else None,
        org_tz,
    )

    record = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == event.organization_id,
            AttendanceRecord.employee_id == event.employee_id,
            AttendanceRecord.date == att_date,
        )
    )

    # Find remaining valid non-provisional events for this day
    valid_events = db.scalars(
        select(AttendanceEvent).where(
            AttendanceEvent.organization_id == event.organization_id,
            AttendanceEvent.employee_id == event.employee_id,
            AttendanceEvent.voided_at.is_(None),
            AttendanceEvent.provisional.is_(False),
        ).order_by(AttendanceEvent.occurred_at.asc())
    ).all()

    # Filter by effective date in org timezone
    day_events = [
        ev for ev in valid_events
        if compute_shift_lateness_and_date(ev.occurred_at.replace(tzinfo=timezone.utc), event.employee.shift if event.employee else None, org_tz)[0] == att_date
    ]

    check_in_ev = next((ev for ev in day_events if ev.type == AttendanceEventType.CHECK_IN), None)
    check_out_ev = next((ev for ev in reversed(day_events) if ev.type == AttendanceEventType.CHECK_OUT), None)

    if check_in_ev is None and check_out_ev is None:
        if record is not None:
            db.delete(record)
    else:
        if record is None:
            shift = event.employee.shift if event.employee else None
            _, late_minutes, status = compute_shift_lateness_and_date(
                check_in_ev.occurred_at.replace(tzinfo=timezone.utc) if check_in_ev else event.occurred_at.replace(tzinfo=timezone.utc),
                shift,
                org_tz,
            )
            record = AttendanceRecord(
                organization_id=event.organization_id,
                employee_id=event.employee_id,
                date=att_date,
                check_in_at=check_in_ev.occurred_at if check_in_ev else None,
                check_out_at=check_out_ev.occurred_at if check_out_ev else None,
                status=status,
                late_minutes=late_minutes,
                match_confidence=check_in_ev.confidence if check_in_ev else 1.0,
                liveness_score=1.0,
                device_label="Confirmed Event",
            )
            db.add(record)
        else:
            record.check_in_at = check_in_ev.occurred_at if check_in_ev else None
            record.check_out_at = check_out_ev.occurred_at if check_out_ev else None

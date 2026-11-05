from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field

from .models import (
    AttendanceEventType,
    AttendanceMethod,
    AttendanceStatus,
    CameraAssurance,
    CameraDirection,
    CameraSourceType,
    DeviceMode,
    DeviceStatus,
    Role,
    SubscriptionStatus,
)


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_slug: str | None = None
    totp_code: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    totp_required: bool = False
    challenge_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


# bcrypt silently truncates beyond 72 bytes, so a longer password would not be fully
# checked. Reject it instead of pretending to store it.
Password = Annotated[str, Field(min_length=8, max_length=72)]


class SignupRequest(BaseModel):
    """Self-serve onboarding: creates the organization and its first ORGANIZATION_ADMIN together."""

    organization_name: str = Field(min_length=2, max_length=160)
    #: URL-safe tenant handle used at sign-in. Derived from the name when omitted.
    organization_slug: str | None = Field(default=None, min_length=2, max_length=64)
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: Password


class SignupResponse(BaseModel):
    organization_id: str
    organization_slug: str
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Password


class TotpSetupResponse(BaseModel):
    provisioning_uri: str
    secret: str


class TotpVerifyRequest(BaseModel):
    code: str


class TotpVerifyResponse(BaseModel):
    recovery_codes: list[str]
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TotpLoginRequest(BaseModel):
    challenge_token: str
    code: str


class SubscriptionOut(BaseModel):
    plan: str
    status: SubscriptionStatus
    seat_limit: int
    seats_used: int
    seats_available: int
    current_period_end: datetime | None


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: Password
    role: Role
    branch_id: str | None = None
    department_id: str | None = None
    employee_id: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: Role | None = None
    branch_id: str | None = None
    department_id: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: Role
    employee_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    is_totp_enabled: bool = False
    is_active: bool
    created_at: datetime


class MeResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: Role
    organization_id: str | None
    organization_name: str | None
    employee_id: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    is_totp_enabled: bool = False


# ---------------------------------------------------------------------------
# Attendance Devices & Kiosk Enrollment
# ---------------------------------------------------------------------------

class DeviceEnrollmentCodeRequest(BaseModel):
    device_name: str | None = Field(default=None, max_length=96)
    branch_id: str | None = None
    mode: DeviceMode = DeviceMode.AUTO


class DeviceEnrollmentCodeResponse(BaseModel):
    code: str
    expires_at: datetime
    device_name: str | None = None
    mode: DeviceMode


class DeviceEnrollRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)
    name: str | None = Field(default=None, min_length=2, max_length=96)


class DeviceEnrollResponse(BaseModel):
    device_id: str
    organization_id: str
    name: str
    mode: DeviceMode
    access_token: str
    token_type: str = "bearer"


class DeviceEventType(str, Enum):
    KIOSK_EXIT_UNLOCK = "KIOSK_EXIT_UNLOCK"
    SUPERVISED_ENROLL_START = "SUPERVISED_ENROLL_START"
    KIOSK_EXIT_FAILED = "KIOSK_EXIT_FAILED"


class DeviceEventRequest(BaseModel):
    event_type: DeviceEventType
    details: dict[str, Any] | None = None


class DeviceEventResponse(BaseModel):
    status: str = "recorded"
    event_type: DeviceEventType


class AttendanceDeviceOut(BaseModel):
    id: str
    organization_id: str
    name: str
    branch_id: str | None
    mode: DeviceMode
    status: DeviceStatus
    registered_by: str | None
    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class DeviceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=96)
    branch_id: str | None = None
    mode: DeviceMode | None = None


# ---------------------------------------------------------------------------
# Cameras (Camera-Independent Architecture)
# ---------------------------------------------------------------------------

class CameraOut(BaseModel):
    id: str
    organization_id: str
    source_type: CameraSourceType
    device_id: str
    name: str
    branch_id: str | None = None
    direction: CameraDirection
    assurance: CameraAssurance
    enabled: bool
    last_seen_at: datetime | None = None
    created_at: datetime


class CameraCreate(BaseModel):
    device_id: str
    name: str = Field(min_length=2, max_length=96)
    source_type: CameraSourceType = CameraSourceType.ANDROID_KIOSK
    branch_id: str | None = None
    direction: CameraDirection = CameraDirection.AUTO
    assurance: CameraAssurance = CameraAssurance.HIGH


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=96)
    branch_id: str | None = None
    direction: CameraDirection | None = None
    assurance: CameraAssurance | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Employee PIN Fallback
# ---------------------------------------------------------------------------

class SetPinRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class PinVerifyRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=48)
    pin: str = Field(min_length=4, max_length=8)


class PinVerifyResponse(BaseModel):
    employee_id: str
    full_name: str
    employee_code: str
    department: str | None = None
    event: Literal["CHECK_IN", "CHECK_OUT", "ALREADY_PRESENT"] | None = None
    recorded_at: datetime | None = None
    status: AttendanceStatus | None = None
    late_minutes: int | None = None
    undo_token: str | None = None
    event_id: str | None = None
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


# ---------------------------------------------------------------------------
# Employees and Org Structure
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=48)
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str = ""
    department: str = "General"
    branch: str | None = None
    shift_name: str | None = None
    job_title: str = ""
    branch_id: str | None = None
    department_id: str | None = None


class EmployeeUpdate(BaseModel):
    """All fields optional: only the ones present are changed."""

    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    department: str | None = None
    branch: str | None = None
    shift_name: str | None = None
    job_title: str | None = None
    branch_id: str | None = None
    department_id: str | None = None
    is_active: bool | None = None


class EmployeeOut(BaseModel):
    id: str
    employee_code: str
    full_name: str
    email: str
    phone: str
    department: str
    branch: str
    job_title: str
    shift_name: str
    is_active: bool
    face_enrolled: bool


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)


class DepartmentOut(BaseModel):
    id: str
    name: str
    head_count: int


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    city: str = ""


class BranchOut(BaseModel):
    id: str
    name: str
    city: str
    head_count: int


class ShiftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    start_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(default="17:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    grace_minutes: int = Field(default=10, ge=0, le=180)


class ShiftOut(BaseModel):
    id: str
    name: str
    start_time: str
    end_time: str
    grace_minutes: int


class LivenessChallengeResponse(BaseModel):
    challenge_id: str
    nonce: str
    actions: list[str]
    expires_at: datetime


class EnrollResponse(BaseModel):
    employee_id: str
    face_enrolled: bool
    quality_score: float
    model_name: str
    enrollment_id: str | None = None
    frames_enrolled: int = 1
    poses: list[str] = ["FRONT"]


class RecognizeResponse(BaseModel):
    employee_id: str
    employee_code: str
    full_name: str
    department: str
    #: CHECK_IN, CHECK_OUT, or ALREADY_PRESENT when the day was already recorded. The last of
    #: these writes nothing: an unattended kiosk can be scanned repeatedly without side effects.
    event: Literal["CHECK_IN", "CHECK_OUT", "ALREADY_PRESENT"]
    recorded_at: datetime
    status: AttendanceStatus
    late_minutes: int
    match_confidence: float
    liveness_score: float
    #: The day's timestamps so a repeat scan can say "already in since 09:05".
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    undo_token: str | None = None
    provisional: bool = False
    event_id: str | None = None


# ---------------------------------------------------------------------------
# Camera-Independent Attendance & Observations
# ---------------------------------------------------------------------------

class FaceObservation(BaseModel):
    """
    Observation schema for camera-independent attendance recognition.
    observation_id serves as the idempotency key.
    """
    observation_id: str = Field(..., min_length=1, max_length=64, description="Idempotency key")
    camera_id: str = Field(..., min_length=1, max_length=36, description="Registered camera identifier")
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    track_id: str | None = None
    image: bytes | str | None = None
    quality: float | None = None
    liveness_evidence: dict | None = None


class ObservationResult(BaseModel):
    employee_id: str
    employee_code: str
    full_name: str
    department: str
    event: Literal["CHECK_IN", "CHECK_OUT", "ALREADY_PRESENT"]
    recorded_at: datetime
    status: AttendanceStatus
    late_minutes: int
    match_confidence: float
    liveness_score: float
    undo_token: str | None = None
    provisional: bool = False
    event_id: str | None = None
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


class AttendanceEventOut(BaseModel):
    id: str
    organization_id: str
    employee_id: str
    employee_name: str | None = None
    device_id: str
    camera_id: str | None = None
    source_type: CameraSourceType
    type: AttendanceEventType
    occurred_at: datetime
    confidence: float
    method: AttendanceMethod
    idempotency_key: str | None = None
    provisional: bool = False
    voided_at: datetime | None = None
    void_reason: str | None = None


class UndoRequest(BaseModel):
    undo_token: str = Field(min_length=1, max_length=512)


class UndoResponse(BaseModel):
    success: bool
    event_id: str
    message: str


class VoidEventRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class AttendanceOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    date: date
    check_in_at: datetime | None
    check_out_at: datetime | None
    status: AttendanceStatus
    late_minutes: int


class AttentionItem(BaseModel):
    category: str
    title: str
    description: str
    target_id: str
    action_url: str


class DashboardResponse(BaseModel):
    organization_name: str
    date: date
    total_employees: int
    present: int
    late: int
    not_checked_in: int
    pending_enrollments: int
    provisional_events_count: int = 0
    offline_devices_count: int = 0
    attention_items: list[AttentionItem] = []


class OrganizationOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    timezone: str
    is_active: bool
    created_at: datetime


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    timezone: str | None = Field(None, min_length=1, max_length=64)


class AuditLogOut(BaseModel):
    id: str
    action: str
    actor_user_id: str | None
    target_type: str
    target_id: str
    meta: dict
    created_at: datetime

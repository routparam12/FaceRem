"""
Tenant-owned tables all carry `organization_id`. Every query in `api.py` filters on it; a
client-supplied organization id is never trusted.
"""

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
import numpy as np

from .db import Base


class VectorType(TypeDecorator):
    """
    Transparent vector type that maps to pgvector's VECTOR(dim) on PostgreSQL
    and JSON on SQLite or fallback.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 512, **kwargs):
        super().__init__(**kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import VECTOR
                return dialect.type_descriptor(VECTOR(self.dim))
            except Exception:
                return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value.tolist()
        return list(value)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
    HR_ADMIN = "HR_ADMIN"
    MANAGER = "MANAGER"
    ATTENDANCE_DEVICE = "ATTENDANCE_DEVICE"


class DeviceMode(str, enum.Enum):
    AUTO = "AUTO"
    IN_ONLY = "IN_ONLY"
    OUT_ONLY = "OUT_ONLY"


class DeviceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    ABSENT = "ABSENT"
    ON_LEAVE = "ON_LEAVE"


class CameraSourceType(str, enum.Enum):
    ANDROID_KIOSK = "ANDROID_KIOSK"
    EDGE_AGENT = "EDGE_AGENT"


class CameraDirection(str, enum.Enum):
    IN_ONLY = "IN_ONLY"
    OUT_ONLY = "OUT_ONLY"
    AUTO = "AUTO"


class CameraAssurance(str, enum.Enum):
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class AttendanceEventType(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"


class AttendanceMethod(str, enum.Enum):
    FACE = "FACE"
    PIN = "PIN"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="TRIAL")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    """A staff sign-in login (Super Admin, Organization Admin, HR Admin, Manager)."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_user_org_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(190), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id"), nullable=True
    )
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    branch: Mapped["Branch | None"] = relationship()
    department: Mapped["Department | None"] = relationship()


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    #: Payment failed but access continues — dunning, not a lockout.
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"


#: Seats each plan includes. Seats are counted in active employees, because that is what an
#: attendance product actually meters — not logins.
PLAN_SEATS: dict[str, int] = {
    "TRIAL": 25,
    "STARTER": 100,
    "GROWTH": 500,
    "ENTERPRISE": 100_000,
}


class Subscription(Base):
    """
    What a tenant is entitled to.

    Without this the `plan` string was decorative: nothing stopped a trial organization
    adding ten thousand employees.
    """

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    #: One subscription per organization, so the FK is unique rather than merely indexed.
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, unique=True
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="TRIAL")
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.TRIALING
    )
    #: When the current billing (or trial) period ends. Null means open-ended.
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RefreshToken(Base):
    """
    One issued refresh token.

    Only a hash is stored: a leaked database still cannot be used to mint access tokens.
    Rows are kept after revocation so a replayed token can be recognised as theft rather
    than treated as merely invalid.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Department(Base):
    """A tenant-owned lookup entity. Replaces the old free-text `Employee.department` string."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_department_org_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_branch_org_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    city: Mapped[str] = mapped_column(String(96), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Shift(Base):
    """`start_time`/`end_time` are stored as `HH:MM` strings; a PoC has no per-org timezone yet."""

    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_shift_org_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), default="09:00")
    end_time: Mapped[str] = mapped_column(String(5), default="17:00")
    grace_minutes: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_code", name="uq_employee_org_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(String(48), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(190), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), default="")
    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id"), nullable=True, index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True, index=True
    )
    shift_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shifts.id"), nullable=True, index=True
    )
    job_title: Mapped[str] = mapped_column(String(96), default="")
    pin_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    department: Mapped[Department | None] = relationship()
    branch: Mapped[Branch | None] = relationship()
    shift: Mapped[Shift | None] = relationship()
    face_profiles: Mapped[list["FaceProfile"]] = relationship(back_populates="employee")


class AttendanceDevice(Base):
    __tablename__ = "attendance_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    mode: Mapped[DeviceMode] = mapped_column(
        Enum(DeviceMode), default=DeviceMode.AUTO, nullable=False
    )
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus), default=DeviceStatus.ACTIVE, nullable=False
    )
    registered_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    branch: Mapped[Branch | None] = relationship()
    cameras: Mapped[list["Camera"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    source_type: Mapped[CameraSourceType] = mapped_column(
        Enum(CameraSourceType), default=CameraSourceType.ANDROID_KIOSK, nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attendance_devices.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    direction: Mapped[CameraDirection] = mapped_column(
        Enum(CameraDirection), default=CameraDirection.AUTO, nullable=False
    )
    assurance: Mapped[CameraAssurance] = mapped_column(
        Enum(CameraAssurance), default=CameraAssurance.HIGH, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    device: Mapped["AttendanceDevice"] = relationship(back_populates="cameras")
    branch: Mapped["Branch | None"] = relationship()


class DeviceEnrollmentCode(Base):
    __tablename__ = "device_enrollment_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(96), nullable=False)
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id"), nullable=True
    )
    mode: Mapped[DeviceMode] = mapped_column(
        Enum(DeviceMode), default=DeviceMode.AUTO, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FaceProfile(Base):
    """
    Face embeddings for an employee. Multiple poses (FRONT, LEFT, RIGHT) are grouped
    by enrollment_id. Revoking or deleting a face profile hard-deletes the biometric
    embeddings, leaving attendance history untouched.
    """

    __tablename__ = "face_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    pose: Mapped[str] = mapped_column(String(16), default="FRONT", nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_vec: Mapped[list[float] | None] = mapped_column(VectorType(512), nullable=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    consented_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    consent_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    employee: Mapped[Employee] = relationship(back_populates="face_profiles")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_id", "date", name="uq_attendance_day"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.PRESENT
    )
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    liveness_score: Mapped[float] = mapped_column(Float, default=0.0)
    device_label: Mapped[str] = mapped_column(String(96), default="")


class AttendanceEvent(Base):
    """
    Immutable event stream. Daily AttendanceRecord summaries are derived from these events.
    The attendance engine is camera-independent and does not reference any camera hardware SDKs.
    """
    __tablename__ = "attendance_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_attendance_events_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attendance_devices.id"), nullable=False, index=True
    )
    camera_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cameras.id"), nullable=True, index=True
    )
    source_type: Mapped[CameraSourceType] = mapped_column(
        Enum(CameraSourceType), default=CameraSourceType.ANDROID_KIOSK, nullable=False
    )
    type: Mapped[AttendanceEventType] = mapped_column(
        Enum(AttendanceEventType), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[AttendanceMethod] = mapped_column(
        Enum(AttendanceMethod), default=AttendanceMethod.FACE, nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provisional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)

    employee: Mapped[Employee] = relationship()
    device: Mapped[AttendanceDevice] = relationship()
    camera: Mapped[Camera | None] = relationship()


class AuditLog(Base):
    """Append-only trail. Never store embeddings, tokens or passwords in `meta`."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(48), default="")
    target_id: Mapped[str] = mapped_column(String(36), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

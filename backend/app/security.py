"""Password hashing, JWT issue/verify, and the RBAC + tenant-scoping dependencies."""

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import bcrypt
from cryptography.fernet import Fernet
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AttendanceDevice, AuditLog, DeviceStatus, RefreshToken, Role, User

bearer_scheme = HTTPBearer(auto_error=False)

SENSITIVE_KEYS = {
    "password", "token", "access_token", "refresh_token", "pin", "pin_hash",
    "secret", "totp_secret", "code", "enrollment_code", "recovery_code", "recovery_codes",
}


class AppError(Exception):
    """Domain error carrying a machine-readable code, rendered by the envelope handler."""

    def __init__(self, code: str, message: str, status_code: int = 400, reason: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.reason = reason


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def hash_pin(plain: str) -> str:
    return hash_password(plain)


def verify_pin(plain: str, hashed: str) -> bool:
    return verify_password(plain, hashed)


def _fernet() -> Fernet:
    key = get_settings().totp_encryption_key
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
    return Fernet(derived)


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


def _issue(subject: str, token_type: str, expires: timedelta, **claims) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + expires, **claims}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, scope: str | None = None) -> str:
    claims = {
        "org": user.organization_id,
        "role": user.role.value,
    }
    if scope:
        claims["scope"] = scope
    return _issue(
        user.id,
        "access",
        timedelta(minutes=get_settings().access_token_minutes),
        **claims,
    )


def create_device_access_token(device: AttendanceDevice) -> str:
    return _issue(
        device.id,
        "device_access",
        timedelta(days=365),
        org=device.organization_id,
        role=Role.ATTENDANCE_DEVICE.value,
        device_id=device.id,
    )


def create_totp_challenge_token(user: User) -> str:
    return _issue(
        user.id,
        "totp_challenge",
        timedelta(minutes=5),
        org=user.organization_id,
        role=user.role.value,
    )


def create_refresh_token(user: User) -> str:
    return _issue(
        user.id,
        "refresh",
        timedelta(days=get_settings().refresh_token_days),
        jti=str(uuid.uuid4()),
    )


def decode_token(token: str, expected_type: str | tuple[str, ...]) -> dict:
    settings = get_settings()
    expected = (expected_type,) if isinstance(expected_type, str) else expected_type
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AppError("TOKEN_EXPIRED", "Your session has expired. Please sign in again.", 401)
    except jwt.PyJWTError:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)
    if payload.get("type") not in expected:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)
    return payload


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. `organization_id` comes from the token, never from the request."""

    user_id: str
    organization_id: str | None
    role: Role
    employee_id: str | None
    full_name: str
    email: str
    branch_id: str | None = None
    department_id: str | None = None
    device_id: str | None = None
    scope: str | None = None


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "Authentication required.", 401)

    payload = decode_token(credentials.credentials, ("access", "device_access"))
    token_type = payload.get("type")

    # 1. Device credential
    if token_type == "device_access" or payload.get("role") == Role.ATTENDANCE_DEVICE.value:
        device_id = payload.get("device_id") or payload.get("sub")
        org_id = payload.get("org")
        device = db.get(AttendanceDevice, device_id)
        if (
            device is None
            or device.organization_id != org_id
            or device.status != DeviceStatus.ACTIVE
            or device.revoked_at is not None
        ):
            raise AppError("DEVICE_NOT_AUTHORIZED", "Device is not authorized or has been revoked.", 401)

        # Throttled update of last_seen_at (write at most once every 60 seconds)
        now = datetime.now(timezone.utc)
        if (
            device.last_seen_at is None
            or (now - device.last_seen_at.replace(tzinfo=timezone.utc)).total_seconds() > 60
        ):
            device.last_seen_at = now
            db.commit()

        return Principal(
            user_id=device.id,
            organization_id=device.organization_id,
            role=Role.ATTENDANCE_DEVICE,
            employee_id=None,
            full_name=device.name,
            email="",
            branch_id=device.branch_id,
            device_id=device.id,
        )

    # 2. User credential
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)

    # Scoped tokens (such as totp_setup) are recorded in principal
    scope = payload.get("scope")

    return Principal(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        employee_id=user.employee_id,
        full_name=user.full_name,
        email=user.email,
        branch_id=user.branch_id,
        department_id=user.department_id,
        scope=scope,
    )


def require_roles(*allowed: Role):
    """
    Dependency factory for role checks.

    SUPER_ADMIN is deliberately not an implicit member of any tenant scope: platform staff must
    not be able to read a customer's employees or biometric data through the ordinary API.
    """

    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.scope == "totp_setup":
            raise AppError("TOTP_REQUIRED", "Two-factor authentication must be enabled before accessing this resource.", 403)
        if principal.role not in allowed:
            raise AppError("FORBIDDEN", "You do not have permission to perform this action.", 403)
        return principal

    return dependency


def tenant_scope(principal: Principal = Depends(get_principal)) -> Principal:
    """Guarantees the caller belongs to exactly one organization before any tenant query runs."""
    if principal.scope == "totp_setup":
        raise AppError("TOTP_REQUIRED", "Two-factor authentication must be enabled before accessing this resource.", 403)
    if principal.role is Role.SUPER_ADMIN or principal.organization_id is None:
        raise AppError("FORBIDDEN", "This endpoint is scoped to a single organization.", 403)
    return principal


def record_audit(
    db: Session,
    *,
    action: str,
    principal: Principal | None = None,
    organization_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    request: Request | None = None,
    **meta,
) -> None:
    """Writes an audit row. Sanitizes any sensitive values so secrets are never persisted."""
    if request is not None and request.client is not None:
        meta.setdefault("client_host", request.client.host)

    sanitized_meta = {}
    for key, value in meta.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            continue
        sanitized_meta[key] = value

    db.add(
        AuditLog(
            organization_id=organization_id or (principal.organization_id if principal else None),
            actor_user_id=principal.user_id if principal else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=sanitized_meta,
        )
    )


# ---------------------------------------------------------------------------
# Who may hand out which role
# ---------------------------------------------------------------------------

ASSIGNABLE_ROLES: dict[Role, tuple[Role, ...]] = {
    Role.ORGANIZATION_ADMIN: (
        Role.ORGANIZATION_ADMIN,
        Role.HR_ADMIN,
        Role.MANAGER,
        Role.ATTENDANCE_DEVICE,
    ),
    Role.HR_ADMIN: (Role.MANAGER,),
    Role.MANAGER: (),
    Role.SUPER_ADMIN: (),
    Role.ATTENDANCE_DEVICE: (),
}


def assert_can_assign(actor: Role, target: Role) -> None:
    if target not in ASSIGNABLE_ROLES.get(actor, ()):
        raise AppError(
            "FORBIDDEN",
            f"Your role cannot assign {target.value}.",
            403,
        )


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(db: Session, user: User) -> str:
    token = create_refresh_token(user)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_fingerprint(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    return token


def revoke_all_for_user(db: Session, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    for row in rows:
        row.revoked_at = now
    return len(rows)


def consume_refresh_token(db: Session, token: str) -> User:
    claims = decode_token(token, "refresh")
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _fingerprint(token)))

    if stored is None:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)

    if stored.revoked_at is not None:
        revoke_all_for_user(db, stored.user_id)
        db.commit()
        raise AppError(
            "TOKEN_REUSED",
            "This session was ended for security. Please sign in again.",
            401,
        )

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AppError("TOKEN_EXPIRED", "Your session has expired. Please sign in again.", 401)

    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)

    stored.revoked_at = datetime.now(timezone.utc)
    return user


def revoke_refresh_token(db: Session, token: str) -> None:
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _fingerprint(token)))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)

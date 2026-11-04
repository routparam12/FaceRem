"""Sign in, token refresh, TOTP two-factor authentication, and who the caller is."""

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (
    PLAN_SEATS,
    AttendanceDevice,
    DeviceMode,
    DeviceStatus,
    Organization,
    Role,
    Subscription,
    SubscriptionStatus,
    User,
)
from ..rate_limiter import check_rate_limit, clear_rate_limit
from ..schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenPair,
    TotpLoginRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
    TotpVerifyResponse,
)
from ..security import (
    AppError,
    Principal,
    consume_refresh_token,
    create_access_token,
    create_device_access_token,
    create_totp_challenge_token,
    decode_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    get_principal,
    hash_password,
    issue_refresh_token,
    record_audit,
    revoke_all_for_user,
    revoke_refresh_token,
    verify_password,
)

settings = get_settings()

#: How long a self-serve trial lasts before it needs a plan.
TRIAL_DAYS = 14

router = APIRouter()


@router.post("/auth/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{payload.email.strip().lower()}"
    check_rate_limit(rate_key, max_attempts=5, window_seconds=60)

    query = select(User).where(User.email == payload.email.strip().lower())
    if payload.organization_slug:
        organization = db.scalar(
            select(Organization).where(Organization.slug == payload.organization_slug)
        )
        if organization is None:
            # Same error as a bad password, so slugs cannot be probed.
            raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)
        query = query.where(User.organization_id == organization.id)

    users = db.scalars(query).all()
    user = next((candidate for candidate in users if candidate.is_active), None)

    # In MVP, employees have NO login account. Disallow employee sign-in with generic error.
    if user is None or getattr(user.role, "value", str(user.role)) == "EMPLOYEE" or not verify_password(payload.password, user.password_hash):
        record_audit(
            db,
            action="auth.login_failed",
            request=request,
            email_domain=payload.email.split("@")[-1] if "@" in payload.email else "",
        )
        db.commit()
        raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)

    if user.organization_id is not None:
        organization = db.get(Organization, user.organization_id)
        if organization is None or not organization.is_active:
            raise AppError("ORGANIZATION_SUSPENDED", "This organization is not active.", 403)

        subscription = db.scalar(
            select(Subscription).where(Subscription.organization_id == organization.id)
        )
        if subscription is not None and subscription.status is SubscriptionStatus.CANCELLED:
            raise AppError(
                "SUBSCRIPTION_CANCELLED",
                "This organization's subscription has ended. Contact your administrator.",
                403,
            )

    # 1. Check if user is a legacy scanner account: issue device credential
    if user.role == Role.ATTENDANCE_DEVICE:
        # TODO(Phase 5): Remove legacy kiosk username/password login path entirely.
        if not settings.is_legacy_kiosk_login_enabled:
            raise AppError(
                "FORBIDDEN",
                "Kiosk password login is disabled. Enroll using an enrollment code.",
                403,
            )
        device = db.scalar(
            select(AttendanceDevice).where(
                AttendanceDevice.organization_id == user.organization_id,
                AttendanceDevice.status == DeviceStatus.ACTIVE,
            )
        )
        if device is None:
            device = AttendanceDevice(
                organization_id=user.organization_id,
                name=user.full_name,
                registered_by=user.id,
                mode=DeviceMode.AUTO,
                status=DeviceStatus.ACTIVE,
            )
            db.add(device)
            db.flush()

        clear_rate_limit(rate_key)
        record_audit(
            db,
            action="auth.login",
            organization_id=user.organization_id,
            target_type="device",
            target_id=device.id,
            request=request,
            role=user.role.value,
        )
        tokens = TokenPair(
            access_token=create_device_access_token(device),
            refresh_token=issue_refresh_token(db, user),
        )
        db.commit()
        return tokens

    # 2. Check 2FA requirement
    if user.is_totp_enabled:
        if payload.totp_code:
            code = payload.totp_code.strip()
            verified = False
            # Try TOTP
            if user.totp_secret:
                try:
                    totp = pyotp.TOTP(decrypt_totp_secret(user.totp_secret))
                    verified = totp.verify(code, valid_window=1)
                except Exception:
                    verified = False

            # Try recovery code if TOTP failed
            if not verified and user.recovery_codes:
                matched_hash = None
                for stored_hash in user.recovery_codes:
                    if verify_password(code, stored_hash):
                        matched_hash = stored_hash
                        verified = True
                        break
                if matched_hash:
                    user.recovery_codes = [h for h in user.recovery_codes if h != matched_hash]
                    record_audit(
                        db,
                        action="auth.recovery_code_used",
                        principal=None,
                        organization_id=user.organization_id,
                        target_type="user",
                        target_id=user.id,
                        request=request,
                    )

            if not verified:
                record_audit(
                    db,
                    action="auth.login_failed",
                    organization_id=user.organization_id,
                    target_type="user",
                    target_id=user.id,
                    request=request,
                    reason="totp_invalid",
                )
                db.commit()
                raise AppError("TOTP_INVALID", "Invalid two-factor authentication code.", 401)
        else:
            # 2FA is required; issue short-lived challenge token
            challenge = create_totp_challenge_token(user)
            return TokenPair(
                access_token="",
                refresh_token="",
                totp_required=True,
                challenge_token=challenge,
            )

    # 3. Mandatory 2FA in Production: if not yet enabled, provide scoped bootstrap token
    if settings.is_production and user.role in (Role.ORGANIZATION_ADMIN, Role.HR_ADMIN) and not user.is_totp_enabled:
        clear_rate_limit(rate_key)
        tokens = TokenPair(
            access_token=create_access_token(user, scope="totp_setup"),
            refresh_token=issue_refresh_token(db, user),
        )
        record_audit(
            db,
            action="auth.login",
            organization_id=user.organization_id,
            target_type="user",
            target_id=user.id,
            request=request,
            role=user.role.value,
            bootstrap_2fa=True,
        )
        db.commit()
        return tokens

    clear_rate_limit(rate_key)
    record_audit(
        db,
        action="auth.login",
        organization_id=user.organization_id,
        target_type="user",
        target_id=user.id,
        request=request,
        role=user.role.value,
    )
    tokens = TokenPair(
        access_token=create_access_token(user),
        refresh_token=issue_refresh_token(db, user),
    )
    db.commit()
    return tokens


@router.post("/auth/totp/setup", response_model=TotpSetupResponse)
def totp_setup(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> TotpSetupResponse:
    """Generates an RFC 6238 TOTP key and provisioning URI for Google Authenticator / 1Password."""
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"totp_setup:{client_ip}:{principal.user_id}", max_attempts=10, window_seconds=60)

    user = db.get(User, principal.user_id)
    if user is None:
        raise AppError("UNAUTHORIZED", "User not found.", 401)

    secret = pyotp.random_base32()
    user.totp_secret = encrypt_totp_secret(secret)
    db.commit()

    org_name = "FaceAttend"
    if principal.organization_id:
        org = db.get(Organization, principal.organization_id)
        if org:
            org_name = org.name

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name=org_name)

    record_audit(
        db,
        action="totp.setup_initiated",
        principal=principal,
        target_type="user",
        target_id=user.id,
        request=request,
    )
    db.commit()

    return TotpSetupResponse(provisioning_uri=provisioning_uri, secret=secret)


@router.post("/auth/totp/verify", response_model=TotpVerifyResponse)
def totp_verify(
    payload: TotpVerifyRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> TotpVerifyResponse:
    """Confirms the TOTP code, enables 2FA, and returns 8 one-time backup recovery codes."""
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"totp_verify:{client_ip}:{principal.user_id}", max_attempts=5, window_seconds=60)

    user = db.get(User, principal.user_id)
    if user is None or not user.totp_secret:
        raise AppError("VALIDATION_ERROR", "TOTP setup must be initiated first.", 400)

    try:
        secret = decrypt_totp_secret(user.totp_secret)
        totp = pyotp.TOTP(secret)
        if not totp.verify(payload.code.strip(), valid_window=1):
            raise AppError("TOTP_INVALID", "Invalid two-factor authentication code.", 401)
    except Exception as e:
        if isinstance(e, AppError):
            raise
        raise AppError("TOTP_INVALID", "Invalid two-factor authentication code.", 401)

    user.is_totp_enabled = True

    # Generate 8 single-use recovery codes
    raw_codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper() for _ in range(8)]
    user.recovery_codes = [hash_password(code) for code in raw_codes]

    record_audit(
        db,
        action="totp.enabled",
        principal=principal,
        target_type="user",
        target_id=user.id,
        request=request,
    )

    access_token = create_access_token(user)  # full scope
    refresh_token = issue_refresh_token(db, user)
    db.commit()

    return TotpVerifyResponse(
        recovery_codes=raw_codes,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/auth/totp/login", response_model=TokenPair)
def totp_login(
    payload: TotpLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenPair:
    """Completes sign-in using a short-lived challenge token and TOTP or recovery code."""
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"totp_login:{client_ip}", max_attempts=5, window_seconds=60)

    claims = decode_token(payload.challenge_token, "totp_challenge")
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active or not user.is_totp_enabled:
        raise AppError("UNAUTHORIZED", "Authentication failed.", 401)

    code = payload.code.strip()
    verified = False

    if user.totp_secret:
        try:
            totp = pyotp.TOTP(decrypt_totp_secret(user.totp_secret))
            verified = totp.verify(code, valid_window=1)
        except Exception:
            verified = False

    if not verified and user.recovery_codes:
        matched_hash = None
        for stored_hash in user.recovery_codes:
            if verify_password(code, stored_hash):
                matched_hash = stored_hash
                verified = True
                break
        if matched_hash:
            user.recovery_codes = [h for h in user.recovery_codes if h != matched_hash]
            record_audit(
                db,
                action="auth.recovery_code_used",
                organization_id=user.organization_id,
                target_type="user",
                target_id=user.id,
                request=request,
            )

    if not verified:
        record_audit(
            db,
            action="auth.login_failed",
            organization_id=user.organization_id,
            target_type="user",
            target_id=user.id,
            request=request,
            reason="totp_invalid",
        )
        db.commit()
        raise AppError("TOTP_INVALID", "Invalid two-factor authentication code.", 401)

    record_audit(
        db,
        action="auth.login",
        organization_id=user.organization_id,
        target_type="user",
        target_id=user.id,
        request=request,
        role=user.role.value,
    )
    tokens = TokenPair(
        access_token=create_access_token(user),
        refresh_token=issue_refresh_token(db, user),
    )
    db.commit()
    return tokens


@router.post("/auth/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = consume_refresh_token(db, payload.refresh_token)
    tokens = TokenPair(
        access_token=create_access_token(user),
        refresh_token=issue_refresh_token(db, user),
    )
    db.commit()
    return tokens


@router.get("/auth/me", response_model=MeResponse)
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> MeResponse:
    organization = (
        db.get(Organization, principal.organization_id) if principal.organization_id else None
    )
    user = db.get(User, principal.user_id) if principal.user_id else None
    return MeResponse(
        id=principal.user_id,
        full_name=principal.full_name,
        email=principal.email,
        role=principal.role,
        organization_id=principal.organization_id,
        organization_name=organization.name if organization else None,
        employee_id=principal.employee_id,
        branch_id=principal.branch_id,
        department_id=principal.department_id,
        is_totp_enabled=user.is_totp_enabled if user else False,
    )


@router.post("/auth/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)) -> SignupResponse:
    slug = (payload.organization_slug or _slugify(payload.organization_name)).lower()
    if not slug:
        raise AppError("VALIDATION_ERROR", "Could not derive an organization code.", 422)

    if db.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        raise AppError("CONFLICT", "That organization code is already taken.", 409)

    email = str(payload.email).strip().lower()
    organization = Organization(name=payload.organization_name.strip(), slug=slug)
    db.add(organization)
    db.flush()

    db.add(
        Subscription(
            organization_id=organization.id,
            plan="TRIAL",
            seat_limit=PLAN_SEATS["TRIAL"],
            status=SubscriptionStatus.TRIALING,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS),
        )
    )

    user = User(
        organization_id=organization.id,
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=Role.ORGANIZATION_ADMIN,
    )
    db.add(user)
    db.flush()

    record_audit(
        db,
        action="auth.signup",
        organization_id=organization.id,
        target_type="user",
        target_id=user.id,
        request=request,
        organization_slug=slug,
    )
    response = SignupResponse(
        organization_id=organization.id,
        organization_slug=slug,
        user_id=user.id,
        access_token=create_access_token(user),
        refresh_token=issue_refresh_token(db, user),
    )
    db.commit()
    return response


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:64]


@router.post("/auth/logout")
def logout(
    payload: RefreshRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    revoke_refresh_token(db, payload.refresh_token)
    record_audit(db, action="auth.logout", principal=principal, request=request)
    db.commit()
    return {"signed_out": True}


@router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, principal.user_id)
    if user is None or not verify_password(payload.current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Current password is incorrect.", 401)

    user.password_hash = hash_password(payload.new_password)
    revoked = revoke_all_for_user(db, user.id)
    record_audit(
        db,
        action="auth.password_changed",
        principal=principal,
        target_type="user",
        target_id=user.id,
        request=request,
        sessions_ended=revoked,
    )
    db.commit()
    return {"password_changed": True, "other_sessions_ended": revoked}

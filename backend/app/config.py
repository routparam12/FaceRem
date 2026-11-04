from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SECRET = "dev-only-insecure-secret-change-me"
DEFAULT_TOTP_KEY = "dev-only-totp-encryption-key-32b!"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite:///./faceattend.db"

    jwt_secret: str = DEFAULT_DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    totp_encryption_key: str = DEFAULT_TOTP_KEY
    redis_url: str | None = None

    face_engine: str = "insightface"
    insightface_model_name: str = "buffalo_l"
    # Leave unset to use the active engine's own default
    face_match_threshold: float | None = None
    face_match_margin: float | None = None

    liveness_mode: str = "challenge"
    liveness_threshold: float = 0.7
    allow_unconfigured_passive_liveness: bool = False

    # Minutes that must pass after check-in before another scan counts as check-out.
    # Below this, a repeat scan is reported as ALREADY_PRESENT instead of punching out,
    # so someone walking past the gate mid-shift cannot accidentally end their day.
    checkout_after_minutes: int = 240
    shift_start_hour: int = 9
    shift_grace_minutes: int = 10

    # Phase 4: Attendance Cooldown, Undo & Camera Assurance
    attendance_cooldown_seconds: int = 60
    undo_window_seconds: int = 30
    standard_assurance_provisional: bool = True

    seed_demo_data: bool = True
    allow_legacy_kiosk_login: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def is_legacy_kiosk_login_enabled(self) -> bool:
        if self.is_production:
            return False
        return self.allow_legacy_kiosk_login


MIN_SECRET_BYTES = 32


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production:
        if settings.jwt_secret == DEFAULT_DEV_SECRET:
            raise RuntimeError("JWT_SECRET must be set to a real value outside development.")
        if len(settings.jwt_secret.encode()) < MIN_SECRET_BYTES:
            raise RuntimeError(
                f"JWT_SECRET must be at least {MIN_SECRET_BYTES} bytes for HS256. "
                "Generate one with: python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        if settings.totp_encryption_key == DEFAULT_TOTP_KEY:
            raise RuntimeError("TOTP_ENCRYPTION_KEY must be set to a real value outside development.")
        if not settings.redis_url:
            raise RuntimeError("Production mode requires REDIS_URL to be configured for rate limiting.")
        if len(settings.totp_encryption_key.encode()) < MIN_SECRET_BYTES:
            raise RuntimeError(f"TOTP_ENCRYPTION_KEY must be at least {MIN_SECRET_BYTES} bytes.")
        if settings.face_engine == "stub":
            raise RuntimeError("FACE_ENGINE='stub' is forbidden in production mode. Set FACE_ENGINE='insightface'.")
        if settings.liveness_mode == "disabled":
            raise RuntimeError("LIVENESS_MODE='disabled' is forbidden in production mode.")
        if not settings.allow_unconfigured_passive_liveness:
            raise RuntimeError(
                "Production mode requires a configured passive liveness model or ALLOW_UNCONFIGURED_PASSIVE_LIVENESS=true override."
            )
    return settings

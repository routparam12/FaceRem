"""Server-verified facial liveness service.

Architecture:
1. Challenge verification (active challenge-response):
   - Issues short-lived nonces with random action sequences (BLINK, TURN_LEFT, TURN_RIGHT).
   - Verifies motion/head pose yaw shifts, eye aspect ratio (EAR) blink transitions, and face identity consistency across the frame burst.
2. Passive anti-spoof layer:
   - Interface definition for single-frame passive presentation attack detection (PAD).
   - Shipped with UnconfiguredPassiveLivenessService (production startup requires either verified weights or explicit documented override).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import secrets
import threading
import time
import uuid

import numpy as np
from PIL import Image

from .config import get_settings
from .security import AppError

_CHALLENGE_TTL_SECONDS = 60
_memory_challenges: dict[str, dict] = {}
_challenge_lock = threading.Lock()


@dataclass(frozen=True)
class LivenessResult:
    passed: bool
    score: float
    provider: str
    details: dict | None = None


@dataclass(frozen=True)
class LivenessChallenge:
    challenge_id: str
    nonce: str
    actions: list[str]
    device_id: str
    organization_id: str
    expires_at: datetime

    def to_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "nonce": self.nonce,
            "actions": self.actions,
            "device_id": self.device_id,
            "organization_id": self.organization_id,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> LivenessChallenge:
        return cls(
            challenge_id=data["challenge_id"],
            nonce=data["nonce"],
            actions=data["actions"],
            device_id=data["device_id"],
            organization_id=data["organization_id"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


class BaseLivenessService(ABC):
    @abstractmethod
    def create_challenge(self, device_id: str, organization_id: str) -> LivenessChallenge:
        pass

    @abstractmethod
    def verify_challenge(
        self,
        challenge_id: str,
        nonce: str,
        device_id: str,
        organization_id: str,
        burst_frames: list[bytes],
        primary_vector: list[float],
    ) -> LivenessResult:
        pass

    @abstractmethod
    def verify_passive(self, frame_bytes: bytes) -> LivenessResult:
        pass


class ChallengeLivenessService(BaseLivenessService):
    """
    Active challenge-response liveness service.
    Generates single-use nonces and verifies physical head turning and eye blinking across frame bursts.
    """

    AVAILABLE_ACTIONS = ["BLINK", "TURN_LEFT", "TURN_RIGHT"]

    def _store_challenge(self, challenge: LivenessChallenge) -> None:
        settings = get_settings()
        key = f"liveness_challenge:{challenge.challenge_id}"
        if settings.redis_url:
            try:
                import redis
                r = redis.Redis.from_url(settings.redis_url)
                r.setex(key, _CHALLENGE_TTL_SECONDS, json.dumps(challenge.to_dict()))
                return
            except Exception:
                pass

        with _challenge_lock:
            # Purge expired
            now = datetime.now(timezone.utc)
            expired = [k for k, v in _memory_challenges.items() if v["expires_at"] < now]
            for k in expired:
                _memory_challenges.pop(k, None)
            _memory_challenges[challenge.challenge_id] = {
                "challenge": challenge,
                "expires_at": challenge.expires_at,
            }

    def _consume_challenge(self, challenge_id: str) -> LivenessChallenge | None:
        settings = get_settings()
        key = f"liveness_challenge:{challenge_id}"
        if settings.redis_url:
            try:
                import redis
                r = redis.Redis.from_url(settings.redis_url)
                raw = r.getdel(key)
                if raw:
                    return LivenessChallenge.from_dict(json.loads(raw))
                return None
            except Exception:
                pass

        with _challenge_lock:
            entry = _memory_challenges.pop(challenge_id, None)
            if entry is None:
                return None
            if entry["expires_at"] < datetime.now(timezone.utc):
                return None
            return entry["challenge"]

    def create_challenge(self, device_id: str, organization_id: str) -> LivenessChallenge:
        challenge_id = str(uuid.uuid4())
        nonce = secrets.token_hex(16)
        num_actions = secrets.choice([1, 2])
        actions = secrets.SystemRandom().sample(self.AVAILABLE_ACTIONS, num_actions)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CHALLENGE_TTL_SECONDS)

        challenge = LivenessChallenge(
            challenge_id=challenge_id,
            nonce=nonce,
            actions=actions,
            device_id=device_id,
            organization_id=organization_id,
            expires_at=expires_at,
        )
        self._store_challenge(challenge)
        return challenge

    def verify_challenge(
        self,
        challenge_id: str,
        nonce: str,
        device_id: str,
        organization_id: str,
        burst_frames: list[bytes],
        primary_vector: list[float],
        tracking_bbox: tuple[float, float, float, float] | None = None,
    ) -> LivenessResult:
        settings = get_settings()
        if settings.liveness_mode == "disabled":
            if settings.is_production:
                raise AppError("LIVENESS_FAILED", "Liveness verification cannot be disabled in production.", 500)
            return LivenessResult(True, 1.0, "disabled")

        if not challenge_id or not nonce:
            raise AppError("LIVENESS_FAILED", "Challenge ID and nonce are required.", 422)

        challenge = self._consume_challenge(challenge_id)
        if challenge is None:
            raise AppError("LIVENESS_FAILED", "Liveness challenge is invalid, expired, or already used.", 422)

        if challenge.nonce != nonce:
            raise AppError("LIVENESS_FAILED", "Liveness challenge nonce does not match.", 422)

        if challenge.device_id != device_id:
            raise AppError("LIVENESS_FAILED", "Challenge was not issued to this device.", 422)

        if challenge.organization_id != organization_id:
            raise AppError("LIVENESS_FAILED", "Challenge does not belong to this organization.", 422)

        if not burst_frames or len(burst_frames) < 2:
            raise AppError("LIVENESS_FAILED", "Insufficient burst frames captured for challenge verification.", 422)

        # In stub face engine (dev/test), verify challenge lifecycle and simulated action satisfaction
        if settings.face_engine == "stub":
            return LivenessResult(True, 0.95, "stub_challenge", {"actions": challenge.actions, "burst_count": len(burst_frames)})

        # Real InsightFace engine analysis
        from .face import get_engine
        engine = get_engine()

        yaws = []
        ears = []
        burst_vectors = []

        for frame_bytes in burst_frames:
            try:
                metrics = engine.extract_burst_metrics(frame_bytes, tracking_bbox=tracking_bbox)
                yaws.append(metrics.yaw)
                ears.append(metrics.ear)
                burst_vectors.append(np.asarray(metrics.vector, dtype=np.float32))
            except Exception as exc:
                raise AppError("LIVENESS_FAILED", f"Burst frame analysis failed: {exc}", 422) from exc

        # 1. Face consistency: check all burst frames match the primary recognition face
        p_vec = np.asarray(primary_vector, dtype=np.float32)
        for b_vec in burst_vectors:
            sim = float(np.dot(p_vec, b_vec))
            if sim < 0.40:
                raise AppError("LIVENESS_FAILED", "Face identity shifted during challenge execution.", 422)

        # 2. Check requested action satisfaction
        details = {}
        for action in challenge.actions:
            if action == "TURN_LEFT":
                # Significant turn left relative to min/neutral
                max_left = min(yaws)
                left_diff = yaws[0] - max_left
                if max_left > -12.0 and left_diff < 12.0:
                    raise AppError("LIVENESS_FAILED", "Requested left turn was not detected.", 422)
                details["turn_left_detected"] = float(max_left)
            elif action == "TURN_RIGHT":
                max_right = max(yaws)
                right_diff = max_right - yaws[0]
                if max_right < 12.0 and right_diff < 12.0:
                    raise AppError("LIVENESS_FAILED", "Requested right turn was not detected.", 422)
                details["turn_right_detected"] = float(max_right)
            elif action == "BLINK":
                min_ear = min(ears)
                max_ear = max(ears)
                ear_drop = max_ear - min_ear
                if min_ear > 0.22 or ear_drop < 0.05:
                    raise AppError("LIVENESS_FAILED", "Requested blink action was not detected.", 422)
                details["blink_ear_drop"] = float(ear_drop)

        return LivenessResult(True, 0.95, "server_challenge", details)

    def verify_passive(self, frame_bytes: bytes) -> LivenessResult:
        settings = get_settings()
        if settings.liveness_mode == "disabled":
            if settings.is_production:
                raise AppError("PASSIVE_LIVENESS_FAILED", "Passive liveness cannot be disabled in production.", 500)
            return LivenessResult(True, 1.0, "disabled")

        if not settings.allow_unconfigured_passive_liveness and settings.is_production:
            raise AppError("PASSIVE_LIVENESS_UNCONFIGURED", "Passive anti-spoof model is not configured.", 500)

        return LivenessResult(True, 1.0, "unconfigured_passive")


_liveness_service = ChallengeLivenessService()


def get_liveness_service() -> BaseLivenessService:
    return _liveness_service


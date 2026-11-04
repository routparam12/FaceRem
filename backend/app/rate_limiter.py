"""
Rate limiting for authentication, TOTP, device enrollment, and PIN verification.

Uses Redis when configured; falls back to a thread-safe in-memory sliding window
for development and test suites.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
import threading
import time

from .config import get_settings
from .security import AppError

_lock = threading.Lock()
_memory_store: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> None:
    """
    Records an attempt and checks if the sliding window limit is exceeded.
    Raises AppError('RATE_LIMITED', ..., 429) if exceeded.
    """
    settings = get_settings()

    if settings.redis_url:
        try:
            import redis
            r = redis.Redis.from_url(settings.redis_url)
            current = int(time.time())
            window_start = current - window_seconds
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(time.time_ns()): current})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = pipe.execute()
            count = results[2]
            if count > max_attempts:
                raise AppError("RATE_LIMITED", "Too many requests. Please try again later.", 429)
            return
        except (ImportError, Exception) as exc:
            if isinstance(exc, AppError):
                raise
            # Fall back to in-memory on Redis error

    now = time.time()
    cutoff = now - window_seconds

    with _lock:
        window = _memory_store[key]
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= max_attempts:
            raise AppError("RATE_LIMITED", "Too many requests. Please try again later.", 429)

        window.append(now)


def clear_rate_limit(key: str) -> None:
    """Resets rate limit counter for a specific key (e.g. after successful auth)."""
    settings = get_settings()
    if settings.redis_url:
        try:
            import redis
            r = redis.Redis.from_url(settings.redis_url)
            r.delete(key)
        except Exception:
            pass

    with _lock:
        _memory_store.pop(key, None)


def reset_memory_rate_limiter() -> None:
    """Clears all in-memory rate limits (used by tests)."""
    with _lock:
        _memory_store.clear()

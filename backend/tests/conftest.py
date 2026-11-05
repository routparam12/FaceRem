"""
Pytest configuration and test isolation fixtures.

Sets up a session-scoped temporary SQLite database so test runs never touch or pollute
./faceattend.db in the working directory. Clears global LRU caches (settings, face engine)
and resets in-memory rate limiters before and after each test.
"""

import atexit
import os
from pathlib import Path
import tempfile
import pytest

# Initialize session-scoped temporary SQLite database
_temp_dir = tempfile.TemporaryDirectory(prefix="faceattend_test_session_")
_session_db_path = Path(_temp_dir.name) / "test_session.db"
_session_db_url = f"sqlite:///{_session_db_path.as_posix()}"

# If DATABASE_URL is not explicitly set or points to default faceattend.db, use session DB
if "DATABASE_URL" not in os.environ or os.environ.get("DATABASE_URL") in ("sqlite:///./faceattend.db", "./faceattend.db"):
    os.environ["DATABASE_URL"] = _session_db_url

from alembic import command
from alembic.config import Config

_backend_root = Path(__file__).resolve().parents[1]
_alembic_cfg = Config(str(_backend_root / "alembic.ini"))
_alembic_cfg.set_main_option("script_location", str(_backend_root / "migrations"))
_alembic_cfg.set_main_option("sqlalchemy.url", _session_db_url)
try:
    command.upgrade(_alembic_cfg, "head")
except Exception:
    pass

atexit.register(_temp_dir.cleanup)

from app.config import get_settings
from app.face import get_engine
from app.rate_limiter import reset_memory_rate_limiter


@pytest.fixture(autouse=True)
def test_isolation_fixture(request):
    """
    Ensures complete isolation between test functions and test files.
    """
    # 1. Reset state before test
    get_settings.cache_clear()
    get_engine.cache_clear()
    reset_memory_rate_limiter()

    # If the test module relies on the stub engine, ensure it is set
    module_name = request.module.__name__ if request.module else ""
    if "test_face_engine" not in module_name:
        # Default non-slow tests to stub engine
        os.environ["FACE_ENGINE"] = os.environ.get("FACE_ENGINE", "stub")

    yield

    # 2. Reset state after test
    get_settings.cache_clear()
    get_engine.cache_clear()
    reset_memory_rate_limiter()

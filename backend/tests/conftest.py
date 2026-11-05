"""
Pytest configuration and test isolation fixtures.

Clears global LRU caches (settings, face engine) and resets in-memory rate limiters
before and after each test function/module to prevent test pollution across suites.
"""

import os
import pytest
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


from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import DeclarativeBase, Session

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engines: dict[str, Engine] = {}


def get_engine() -> Engine:
    url = get_settings().database_url
    if url not in _engines:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engines[url] = create_engine(url, connect_args=connect_args, future=True)
    return _engines[url]


class _EngineProxy:
    """Proxy object so code using `app.db.engine` or `inspect(engine)` always talks to active database."""
    def __getattr__(self, name: str) -> Any:
        return getattr(get_engine(), name)


engine = _EngineProxy()


class _SessionLocalProxy:
    """Proxy factory so `SessionLocal()` creates a Session bound to current database URL."""
    def __call__(self, **kwargs) -> Session:
        return Session(bind=get_engine(), autoflush=False, expire_on_commit=False, **kwargs)


SessionLocal = _SessionLocalProxy()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

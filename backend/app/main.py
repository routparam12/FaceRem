import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import inspect, text
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routers import attendance, auth, devices, employees, org, reports, users
from .config import get_settings
from .db import SessionLocal, engine
from .security import AppError
from .seed import seed_demo_data

settings = get_settings()


def _assert_schema_exists() -> None:
    """
    Fail loudly if migrations have not been run.

    Alembic owns the schema now. Creating tables here as well would let the two drift
    apart silently, which is the failure mode that costs you a database.
    """
    if not inspect(engine).has_table("organizations"):
        raise RuntimeError(
            "Database schema is missing. Run:  alembic upgrade head"
        )


def _assert_production_requirements() -> None:
    """Refuse to start in production without essential security infrastructure."""
    if not settings.is_production:
        return
    if not settings.redis_url:
        raise RuntimeError(
            "Production mode requires REDIS_URL to be configured for distributed rate limiting."
        )
    try:
        import redis
        client = redis.Redis.from_url(settings.redis_url, socket_timeout=2)
        client.ping()
    except Exception as exc:
        raise RuntimeError(
            f"Production mode requires a reachable Redis instance for distributed rate limiting: {exc}"
        ) from exc
    if settings.face_engine == "stub":
        raise RuntimeError("FACE_ENGINE='stub' is forbidden in production mode. Set FACE_ENGINE='insightface'.")
    if settings.liveness_mode == "disabled":
        raise RuntimeError("LIVENESS_MODE='disabled' is forbidden in production mode.")
    if not settings.allow_unconfigured_passive_liveness:
        raise RuntimeError(
            "Production mode requires a configured passive liveness model or ALLOW_UNCONFIGURED_PASSIVE_LIVENESS=true override."
        )
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            ext = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
            if not ext:
                raise RuntimeError(
                    "Production mode on PostgreSQL requires the 'vector' (pgvector) extension to be active. "
                    "Install pgvector and run: CREATE EXTENSION IF NOT EXISTS vector;"
                )
            insp = inspect(db.bind)
            cols = {c["name"]: c for c in insp.get_columns("face_profiles")}
            if "embedding_vec" not in cols:
                raise RuntimeError(
                    "Production mode requires the 'embedding_vec' column in 'face_profiles'. Run alembic upgrade head."
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _assert_schema_exists()
    _assert_production_requirements()
    if settings.face_engine == "insightface":
        try:
            from .face import warmup_engine
            warmup_engine()
        except Exception:
            pass
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title="FaceAttend API",
    version="0.1.0",
    description="Multi-tenant facial attendance PoC.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(status_code: int, code: str, message: str, reason: str | None = None) -> JSONResponse:
    err_obj = {"code": code, "message": message}
    if reason:
        err_obj["reason"] = reason
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": err_obj},
    )


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message, exc.reason)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMITED"}
    return _error(exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "VALIDATION_ERROR", "Please check the submitted values and try again.")


@app.middleware("http")
async def envelope_response(request: Request, call_next):
    """Wraps successful JSON bodies in the project envelope. Errors are shaped by the handlers."""
    response = await call_next(request)
    if request.url.path in {"/docs", "/openapi.json", "/redoc"}:
        return response
    if response.status_code >= 400 or response.headers.get("content-type") != "application/json":
        return response

    body = b"".join([chunk async for chunk in response.body_iterator])
    if not body:
        return response

    payload = json.loads(body)
    if isinstance(payload, dict) and "success" in payload:
        return JSONResponse(status_code=response.status_code, content=payload)
    return JSONResponse(
        status_code=response.status_code,
        content={"success": True, "data": payload, "message": "Operation successful"},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "face_engine": settings.face_engine, "liveness": settings.liveness_mode}


for _router, _tag in (
    (auth.router, "auth"),
    (devices.router, "devices"),
    (employees.router, "employees"),
    (attendance.router, "attendance"),
    (org.router, "organization"),
    (reports.router, "reports"),
    (users.router, "users"),
):
    app.include_router(_router, prefix="/api/v1", tags=[_tag])

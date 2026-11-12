# FaceAttend Backend

The core FastAPI service powering multi-tenant identity, biometric face recognition, kiosk check in / check out, and attendance reporting.

---

## Quick Start

### Installation & Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Interactive OpenAPI Docs:** <http://127.0.0.1:8000/docs>
* **Raw OpenAPI JSON:** <http://127.0.0.1:8000/openapi.json>
* **Complete Endpoint Documentation:** See [`docs/API.md`](../docs/API.md) (generated via `python backend/scripts/generate_api_docs.py`).

### Seeding Behavior
Setting `SEED_DEMO_DATA=true` seeds two organizations (`northwind` and `acme`) with standard shifts, departments, staff accounts, and dummy employees. Passwords default to `demo12345`. If any organization already exists in the database, seeding is safely skipped.

---

## Environment Variables (`app/config.py`)

| Name | Default | Purpose | Production Requirement |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `"dev"` | Environment mode (`dev`, `test`, `staging`, `production`). | Optional |
| `DATABASE_URL` | `"sqlite:///./faceattend.db"` | SQLAlchemy database connection string. | Required to be PostgreSQL in production. |
| `JWT_SECRET` | `"dev-only-insecure-secret-change-me"` | Secret for signing HS256 JWT access and refresh tokens. | **Required** (>= 32 bytes; refuses default value). |
| `JWT_ALGORITHM` | `"HS256"` | JWT signature algorithm. | Optional |
| `ACCESS_TOKEN_MINUTES` | `30` | Access token lifetime. | Optional |
| `REFRESH_TOKEN_DAYS` | `14` | Refresh token lifetime. | Optional |
| `TOTP_ENCRYPTION_KEY` | `"dev-only-totp-encryption-key-32b!"` | 32-byte secret for AES-256-GCM encryption of TOTP keys at rest. | **Required** (>= 32 bytes; refuses default value). |
| `REDIS_URL` | `None` | Redis connection URL for distributed rate limiting. | **Required** in production (must be reachable on startup). |
| `FACE_ENGINE` | `"insightface"` | Face embedding engine (`"insightface"` or `"stub"`). | Must be `"insightface"` in production (`stub` is rejected). |
| `INSIGHTFACE_MODEL_NAME` | `"buffalo_l"` | InsightFace ONNX model bundle name. | Optional |
| `FACE_MATCH_THRESHOLD` | `None` | Cosine similarity match threshold. Uses engine default (0.45 ArcFace, 0.62 stub) if unset. | Optional |
| `FACE_MATCH_MARGIN` | `None` | Margin requirement between best and second-best candidate (default 0.05). | Optional |
| `LIVENESS_MODE` | `"challenge"` | Anti-spoofing mode (`"disabled"`, `"challenge"`, `"passive"`, `"client_attested"`). | Must not be `"disabled"` in production. |
| `LIVENESS_THRESHOLD` | `0.7` | Minimum liveness score for verification. | Optional |
| `ALLOW_UNCONFIGURED_PASSIVE_LIVENESS` | `False` | Overrides production requirement for passive liveness model. | Required if passive model weights are not loaded. |
| `CHECKOUT_AFTER_MINUTES` | `240` | Cooldown window before a second scan counts as check-out. | Optional |
| `SHIFT_START_HOUR` | `9` | Fallback daily start hour for lateness derivation when shift is unassigned. | Optional |
| `SHIFT_GRACE_MINUTES` | `10` | Grace minutes past shift start before marking record `LATE`. | Optional |
| `ATTENDANCE_COOLDOWN_SECONDS` | `60` | Cooldown period between successive scans for the same employee. | Optional |
| `UNDO_WINDOW_SECONDS` | `30` | Time window to cancel an accidental check-in via `/attendance/undo`. | Optional |
| `STANDARD_ASSURANCE_PROVISIONAL` | `True` | Flags scans from standard cameras without liveness as provisional. | Optional |
| `SEED_DEMO_DATA` | `False` | Triggers initial demo seed if database is empty. | Optional |
| `ALLOW_LEGACY_KIOSK_LOGIN` | `True` | Allows username/password sign-in for kiosks in development. | Disabled automatically in production. |

---

## Roles and Permissions Matrix

Read from `app/deps.py` and router dependencies.

| Role | Classification | Permissions & Endpoints |
| :--- | :--- | :--- |
| `SUPER_ADMIN` | Platform Operator | Platform maintenance only. **Explicitly barred** from tenant routes by `tenant_scope`. |
| `ORGANIZATION_ADMIN` | Tenant Staff | Full tenant control: manages employees, face profiles, kiosk devices, cameras, reports, audit logs, and organization settings. |
| `HR_ADMIN` | Tenant Staff | People operations: creates/updates employees, enrolls and revokes face profiles, manages kiosk devices and cameras, views reports. Scoped to branch/department if assigned. |
| `MANAGER` | Tenant Staff | Read-only access to employees, daily attendance, dashboard, and reports. Scoped to branch/department if assigned. |
| `ATTENDANCE_DEVICE` | Dedicated Hardware | Kiosk identity: runs `/attendance/recognize`, `/attendance/scan`, `/attendance/challenge`, and device heartbeats. Blocked from admin routes. |
| `EMPLOYEE` | Data Record | Not a staff sign-in role. Represents an individual on the roster with an employee code and optional 4-digit PIN for fallback kiosk check-in. |

---

## Authentication & Credentials

* **Staff Sign-in (`POST /api/v1/auth/login`):**
  Accepts email, password, and optional organization slug. If 2FA is active, returns a short-lived challenge token (`totp_required=True`).
* **Two-Factor Authentication (2FA / TOTP):**
  RFC 6238 TOTP secrets are encrypted at rest with AES-256-GCM using `TOTP_ENCRYPTION_KEY`. Setup (`/auth/totp/setup`) provides an `otpauth://` provisioning URI; verification (`/auth/totp/verify`) issues 8 single-use hashed recovery backup codes. In production, unconfigured admins receive a scoped `totp_setup` token that blocks all API access until 2FA is enabled.
* **Token Refresh Rotation (`POST /api/v1/auth/refresh`):**
  Issues a new access token and burns the old refresh token. Refresh tokens are stored as SHA-256 hashes in `refresh_tokens`. Presenting an already-consumed refresh token triggers theft detection, instantly revoking all active sessions for that user.
* **Device Credentials (`POST /api/v1/devices/enroll`):**
  Kiosks receive a non-refreshing JWT valid for 365 days. To ensure instant revocation, `security.py:get_principal` queries the database on every device request to confirm `AttendanceDevice.status == ACTIVE` and `revoked_at IS NULL`.

---

## Kiosk Hardware Pairing

1. **Enrollment Code Generation (`POST /api/v1/devices/enrollment-code`):**
   An authenticated administrator generates an 8-character single-use code valid for 15 minutes (`DeviceEnrollmentCode`).
2. **Device Registration (`POST /api/v1/devices/enroll`):**
   The physical kiosk sends the enrollment code and its hardware identifier. The server hashes the code, checks validity, creates an `AttendanceDevice` record, marks the code used, and issues device credentials.
3. **Revocation (`POST /api/v1/devices/{id}/revoke`):**
   Setting `revoked_at` instantly invalidates the device's authorization on its very next HTTP call.
4. **Buffered Device Events (`POST /api/v1/devices/me/events`):**
   Allows kiosks to sync offline-buffered operational status logs.

---

## Attendance Processing Engine

* **Scan & Recognition (`POST /api/v1/attendance/recognize`, `/attendance/scan`):**
  Processes face observations against active organization embeddings. Filters by organization before similarity matching.
* **Cooldown Enforcement:**
  Enforced in `attendance_service.py:process_face_observation`. If an employee checks in and is detected again within `ATTENDANCE_COOLDOWN_SECONDS` (60s), the event is recorded as `COOLDOWN_SUPPRESSED` without altering records.
* **Check-out Delay Window (`CHECKOUT_AFTER_MINUTES`):**
  Within 240 minutes of check-in, repeat scans return `ALREADY_PRESENT`. After 240 minutes, a scan writes `check_out_at` and sets status to `CHECK_OUT`.
* **Challenge Liveness (`POST /api/v1/attendance/challenge`):**
  Issues randomized challenges (blink, nod, smile). Rejects unverified client scores when in challenge mode.
* **Directionality per Camera:**
  Configured per camera in `cameras` (`IN_ONLY`, `OUT_ONLY`, `BIDIRECTIONAL`). An `IN_ONLY` camera will reject check-out attempts (`DIRECTION_MISMATCH`).
* **Assurance & Provisional Status:**
  Scans from standard assurance cameras without confirmed liveness create provisional events that require admin confirmation (`/attendance/events/{id}/confirm`).
* **Undo Window (`POST /api/v1/attendance/undo`):**
  Within 30 seconds of an accidental check-in, the kiosk can present the `undo_token` to delete the check-in record.
* **Lateness & Shifts:**
  Compares arrival against the assigned `Shift` start time plus `grace_period_minutes`. Records late minutes and marks status as `LATE`.

---

## Face Recognition Pipeline

* **Engine:** InsightFace ArcFace (`buffalo_l`, 512-dimensional normalized embeddings).
* **Test Stub:** Deterministic 256-dimensional grayscale descriptor for test execution without model weight downloads.
* **Thresholds & Margin:**
  * ArcFace default threshold: `0.45` cosine similarity.
  * Stub default threshold: `0.62`.
  * Margin requirement: `0.05` separation between best candidate and runner-up to prevent ambiguous matches.
* **Multi-Pose Enrollment:**
  `POST /api/v1/employees/{id}/face/enroll` accepts three camera frames (`front_frame`, `left_frame`, `right_frame`) and explicit `consent=true`. Each frame is evaluated for head pose, yaw, pitch, roll, blur, and lighting before generating embeddings.
* **PostgreSQL vs SQLite:**
  PostgreSQL uses `VectorType(512)` mapped to `pgvector.sqlalchemy.VECTOR(512)`. SQLite falls back to JSON-serialized vectors. In both environments, nearest-neighbor matching is computed in Python using `numpy` dot product across organization-scoped records.
* **Production Startup Checks (`main.py`):**
  Startup raises `RuntimeError` if:
  1. Alembic migrations have not run (`organizations` table missing).
  2. `APP_ENV=production` and `JWT_SECRET` or `TOTP_ENCRYPTION_KEY` are using insecure defaults or < 32 bytes.
  3. `REDIS_URL` is missing or unreachable.
  4. `FACE_ENGINE` is set to `"stub"`.
  5. `LIVENESS_MODE` is set to `"disabled"`.
  6. PostgreSQL is used but the `vector` (pgvector) extension is not installed or `embedding_vec` column is missing.
  7. Passive liveness is unconfigured and `ALLOW_UNCONFIGURED_PASSIVE_LIVENESS` is false.
* **Model Weights & Documentation:** Detailed pipeline specifications and model weight licensing notes are documented in [`docs/FACE_PIPELINE.md`](../docs/FACE_PIPELINE.md).

---

## Privacy, Storage, & Data Retention

* **Biometric Templates:**
  Embeddings are stored as 512-dimensional floating-point vectors in `face_profiles`. Raw facial images from enrollment are not retained in the database.
* **Employee Avatar Photos:**
  The front-facing enrollment frame is saved to `storage/avatars/{org_id}/{employee_id}.jpg` and served to authenticated staff via `GET /api/v1/employees/{id}/avatar`.
* **Rolling 7-Day Kiosk Scan Photos:**
  Kiosk recognition events optionally save an audit frame to `storage/scans/{org_id}/{employee_id}/{timestamp}_{event_id}.jpg`.
* **Automated Retention Purge:**
  `storage.py:prune_scan_photos` runs automatically on each scan save, deleting any snapshot older than 7 days (`max_age_days=7`). Access to audit snapshots is restricted to tenant administrators via `/api/v1/employees/{id}/recent-scans`.

---

## Data Model (15 Tables)

Real tables declared in `app/models.py`:

| Table Name | Entity | Purpose |
| :--- | :--- | :--- |
| `organizations` | `Organization` | Tenant boundary with unique slug and display name. |
| `subscriptions` | `Subscription` | SaaS entitlement tier and active employee seat limit enforcement. |
| `users` | `User` | Staff login credentials, roles, encrypted TOTP secrets, and recovery codes. |
| `refresh_tokens` | `RefreshToken` | Hashed single-use session refresh tokens with reuse detection. |
| `departments` | `Department` | Organization departments for personnel grouping and analytics. |
| `branches` | `Branch` | Physical office, branch, or facility locations. |
| `shifts` | `Shift` | Work schedules with start/end hours, grace periods, and half-day thresholds. |
| `employees` | `Employee` | Personnel roster records with department/shift bindings and PIN hash. |
| `face_profiles` | `FaceProfile` | 512-dim biometric embeddings, pose labels, quality scores, and consent timestamps. |
| `attendance_devices`| `AttendanceDevice` | Enrolled physical kiosk hardware records and revocation status. |
| `device_enrollment_codes` | `DeviceEnrollmentCode` | Single-use 15-minute pairing tokens for kiosks. |
| `cameras` | `Camera` | Registered optical sensors, RTSP streams, directionality, and assurance levels. |
| `attendance_records`| `AttendanceRecord` | Daily attendance roll-up per employee per date (in, out, status, late minutes). |
| `attendance_events` | `AttendanceEvent` | Immutable stream of raw scan transactions, confidence scores, and undo tokens. |
| `audit_logs` | `AuditLog` | Audit log of administrative operations, credential events, and biometric deletions. |

---

## API Reference

API documentation is generated directly from the OpenAPI specification using the project generator script:

```bash
python backend/scripts/generate_api_docs.py
```

The resulting reference documentation is maintained at [`docs/API.md`](../docs/API.md).

---

## Testing

```powershell
# 1. Fast Suite (skips heavy ML model downloads and inference):
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -m "not slow" -v

# 2. Full Suite (runs all unit and integration tests):
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -v

# 3. Live PostgreSQL Migration Test (requires running Postgres instance):
$env:POSTGRES_TEST_URL="postgresql+psycopg://postgres:postgres@localhost:5432/facerem_test"
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_postgres_migration.py -v
```

* **Test Isolation:** `backend/tests/conftest.py` configures a session-scoped temporary SQLite database. The local development `./faceattend.db` database is never altered by test runs.
* **Windows Sandbox Note:** Starlette's `TestClient` uses an internal asyncio loop that binds to loopback sockets (`127.0.0.1`). If running under an environment that blocks local network loopback, tests must be run with sandbox loopback permitted.

---

## Known Limitations

| Limitation | Status | Notes |
| :--- | :--- | :--- |
| Vector Similarity Computation | Implemented (In-Python) | Cosine similarity matching is executed via `numpy` dot product; native SQL `<->` pgvector queries are not used in `find_best_match`. |
| Device Token Refresh | Implemented as Permanent | Kiosk device tokens are issued with 365-day lifespans and have no refresh flow; revocation relies on real-time database lookups. |
| Passive Anti-Spoofing Model | Partial | Challenge liveness is implemented; passive single-frame anti-spoofing requires `ALLOW_UNCONFIGURED_PASSIVE_LIVENESS=true` unless custom weights are supplied. |
| Face Model Weights Licensing | Note | InsightFace ArcFace models are licensed for non-commercial research use by default; commercial production deployment requires appropriate licensing or an open-weight alternative. |
| Self-Service Password Reset | Planned | Email-based password reset endpoints are not implemented in the backend. |

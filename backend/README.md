# FaceAttend backend — proof of concept

A deliberately small FastAPI service covering the two things that decide whether this product
works: **multi-tenant RBAC** and **server-side face recognition**. Twelve source files, SQLite,
no infrastructure to stand up.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then change JWT_SECRET
uvicorn app.main:app --reload
```

Interactive docs: <http://127.0.0.1:8000/docs>

## Demo logins

Password for all of them: `demo12345`. Two organizations exist so tenant isolation is real and
testable.

| Email | Role | Can do |
| --- | --- | --- |
| `admin@northwind.demo` | `ORG_ADMIN` | everything in its organization, including audit logs |
| `hr@northwind.demo` | `HR_ADMIN` | manage employees, enroll and revoke faces, run scans |
| `manager@northwind.demo` | `MANAGER` | read employees, attendance, dashboard |
| `employee@northwind.demo` | `EMPLOYEE` | own profile and own attendance only |
| `kiosk@northwind.demo` | `ATTENDANCE_DEVICE` | run recognition scans, nothing else |
| `root@faceattend.platform` | `SUPER_ADMIN` | platform account — **blocked** from tenant data |

Swap `northwind` for `acme` for the second organization.

## Endpoints

```text
POST   /api/v1/auth/login                          public
POST   /api/v1/auth/refresh                        public
GET    /api/v1/auth/me                             any signed-in user

GET    /api/v1/employees                           ORG_ADMIN, HR_ADMIN, MANAGER  (?include_inactive=)
POST   /api/v1/employees                           ORG_ADMIN, HR_ADMIN
GET    /api/v1/employees/{id}                      ORG_ADMIN, HR_ADMIN, MANAGER
PUT    /api/v1/employees/{id}                      ORG_ADMIN, HR_ADMIN   (partial update)
DELETE /api/v1/employees/{id}                      ORG_ADMIN, HR_ADMIN   (soft delete: deactivates,
                                                                           revokes face, keeps history)
POST   /api/v1/employees/{id}/face/enroll          ORG_ADMIN, HR_ADMIN   (multipart + consent)
DELETE /api/v1/employees/{id}/face                 ORG_ADMIN, HR_ADMIN   (keeps attendance)

GET    /api/v1/departments                         ORG_ADMIN, HR_ADMIN, MANAGER
POST   /api/v1/departments                         ORG_ADMIN, HR_ADMIN   (also created implicitly
                                                                           by employee create/update)
DELETE /api/v1/departments/{id}                     ORG_ADMIN, HR_ADMIN   (409 if still in use)

GET    /api/v1/branches                            ORG_ADMIN, HR_ADMIN, MANAGER
POST   /api/v1/branches                            ORG_ADMIN, HR_ADMIN
DELETE /api/v1/branches/{id}                       ORG_ADMIN, HR_ADMIN   (409 if still in use)

GET    /api/v1/shifts                              ORG_ADMIN, HR_ADMIN, MANAGER
POST   /api/v1/shifts                              ORG_ADMIN, HR_ADMIN
DELETE /api/v1/shifts/{id}                         ORG_ADMIN, HR_ADMIN   (409 if still in use)

POST   /api/v1/attendance/recognize                ATTENDANCE_DEVICE, ORG_ADMIN, HR_ADMIN
GET    /api/v1/attendance                          staff see all; EMPLOYEE sees only own
GET    /api/v1/dashboard                           ORG_ADMIN, HR_ADMIN, MANAGER
GET    /api/v1/audit-logs                          ORG_ADMIN
```

Every response uses the project envelope:

```json
{ "success": true, "data": {}, "message": "Operation successful" }
{ "success": false, "error": { "code": "FACE_NOT_RECOGNIZED", "message": "Face could not be recognized." } }
```

## Try it

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"hr@northwind.demo","password":"demo12345"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["access_token"])')

EMP=$(curl -s localhost:8000/api/v1/employees -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')

curl -X POST "localhost:8000/api/v1/employees/$EMP/face/enroll" \
  -H "Authorization: Bearer $TOKEN" -F image=@face.jpg -F consent=true

curl -X POST localhost:8000/api/v1/attendance/recognize \
  -H "Authorization: Bearer $TOKEN" \
  -F image=@face.jpg -F liveness_score=0.95 -F device_label=lobby-1
```

## How RBAC and tenant isolation work

`Principal` is built from the JWT, and it carries the organization id. A client-supplied
`organization_id` is never read from a request body or query string.

- `require_roles(...)` gates each route by role.
- `tenant_scope` guarantees the caller belongs to exactly one organization before any tenant
  query runs, and **rejects `SUPER_ADMIN`**: platform staff should not be able to read a
  customer's employees or biometric data through the ordinary API.
- Cross-tenant reads answer `404`, not `403`, so one tenant cannot use error codes to confirm
  that another tenant's record ids exist.
- `find_best_match` filters by organization *before* similarity, never after. A face is never
  compared against another tenant's profiles.

## Accounts and roles

A tenant is created by signing up; everyone else is created by someone already inside it.

```text
POST /auth/signup   ->  new Organization + its first ORG_ADMIN   (public)
POST /users         ->  ORG_ADMIN or HR_ADMIN creates a login
```

Who may hand out which role — the table that stops privilege escalation:

| Actor | Can create / assign |
| --- | --- |
| `ORG_ADMIN` | `ORG_ADMIN`, `HR_ADMIN`, `MANAGER`, `EMPLOYEE`, `ATTENDANCE_DEVICE` |
| `HR_ADMIN` | `MANAGER`, `EMPLOYEE`, `ATTENDANCE_DEVICE` |
| everyone else | nothing |

`SUPER_ADMIN` is in no row, so platform access can never be granted through the tenant API.
On top of that: nobody can change their own role or deactivate themselves, and the last
active `ORG_ADMIN` cannot be demoted or disabled — otherwise a tenant could lock itself out.

## Sessions

Refresh tokens are stored as SHA-256 hashes and **rotate on every use**: refreshing burns
the old token and issues a new one. That is what makes logout mean something.

- `POST /auth/logout` revokes the presented refresh token.
- `POST /auth/change-password` revokes every other session, which is usually the point.
- Deactivating a user revokes their live sessions, not just future logins.
- Presenting an already-used refresh token is treated as **theft**: every session for that
  user is ended and the caller gets `TOKEN_REUSED`.

Access tokens are not revocable — they are short-lived instead (`ACCESS_TOKEN_MINUTES`).

## Plans and seats

`subscriptions` is what makes this a SaaS rather than a single-tenant app: without it the
`plan` string was decorative and a trial tenant could add unlimited people.

| Plan | Seats |
| --- | --- |
| `TRIAL` | 25 |
| `STARTER` | 100 |
| `GROWTH` | 500 |
| `ENTERPRISE` | 100,000 |

Seats are counted in **active employees**, not logins — that is what an attendance product
meters. `POST /employees` refuses with `SEAT_LIMIT_REACHED` (402) when the plan is full,
checked at creation because a tenant already over its limit has no good remedy.

Signup starts a 14-day `TRIALING` subscription. `GET /subscription` shows the plan and
usage to an org or HR admin.

Status affects sign-in deliberately:

- `CANCELLED` blocks login with `SUBSCRIPTION_CANCELLED`.
- `PAST_DUE` still works. A failed payment should start dunning, not lock a factory out of
  its attendance gate.

## Face recognition

Two engines, chosen with `FACE_ENGINE`:

| | `insightface` (default) | `stub` |
| --- | --- | --- |
| What it is | ArcFace embeddings, `buffalo_l` | 256-dim grayscale descriptor |
| Dimensions | 512 | 256 |
| Threshold | 0.45 | 0.62 |
| Real recognition | yes | **no** |

Measured on the same pair of photos — one person shot twice under different light and
angle, versus two different people:

| | ArcFace | stub |
| --- | --- | --- |
| Same person, different photo | **+0.846** | +0.634 |
| Two different people | **−0.013** | +0.347 |
| Separation | **0.859** | 0.287 |

The stub clears its own threshold by 0.014. That is not recognition, it is a coincidence
with a margin — which is why it exists only to keep the API suite fast and model-free.

**Thresholds belong to the engine, not to the config.** `FACE_MATCH_THRESHOLD` is unset by
default so each engine supplies its own; reusing the stub's 0.62 with ArcFace would reject
the same person photographed in different light.

The ~280 MB model downloads to `~/.insightface` on first use, so the first request after a
cold start is slow. Nothing matches below the threshold: the nearest candidate is never
returned, and an unknown face learns nothing about the roster.

### Tightly cropped photos

Employee photos often arrive as bare head crops. The detector needs *context* around a
face, not more pixels — upscaling a 112×112 crop still finds nothing, while padding it
finds the face immediately. The engine retries with a margin rather than rejecting a
perfectly usable picture.

### Switching engines requires re-enrollment

Embeddings from different models are not comparable — different dimensions, different
vector space. `find_best_match` filters to the active model in SQL, so profiles enrolled
under another engine are simply invisible: those people must enroll again. Filtering in SQL
also stops a mixed table from producing a ragged matrix, which would raise rather than
merely fail to match.

## Liveness and the KBY-AI SDK

[`kby-ai/FaceLivenessDetection-Android`](https://github.com/kby-ai/FaceLivenessDetection-Android)
is an **on-device, liveness-only** SDK. `FaceSDK.faceDetection(bitmap)` returns `FaceBox` objects
carrying a rectangle, a liveness score and yaw/roll/pitch. It needs `FaceSDK.setActivation(key)`
with a commercial licence key bound to your application id, and that tier does **not** produce
face embeddings — recognition stays on this server either way.

So the split is:

```text
Android: detect face -> quality checks -> KBY-AI liveness score
            |
            v  multipart: image + liveness_score
Server:  enforce liveness threshold -> ArcFace embedding
      -> organization-scoped vector search -> confidence check
      -> attendance rules -> audit log
```

`LIVENESS_MODE=client_attested` enforces `LIVENESS_THRESHOLD` against the score the client sends.
**A client-reported score is evidence, not proof** — a modified client can send any number. The
mode is an explicit setting rather than an assumption so this decision stays visible. Before
production, replace it with a server-side check or with an attestation the server can verify
(Play Integrity plus an SDK-signed result). `LIVENESS_MODE=disabled` skips the check entirely and
is for local development only.

To wire the SDK into the Android client: add `libfacesdk` per the KBY-AI README, call
`FaceSDK.setActivation(BuildConfig.KBYAI_LICENSE)` at startup, and feed the analyzer's bitmap to
`FaceSDK.faceDetection(...)`. The existing `FaceQualityEvaluator` already gates frames on pose,
size, centring and brightness, so the liveness score becomes one more condition before capture.

## What this PoC deliberately does not do

SQLite instead of PostgreSQL + pgvector (matching is a numpy dot product; the query to replace is
noted in `face.py`). No Alembic — tables are created at startup. Refresh tokens are stateless, so
they cannot be revoked. No rate limiting. No shift/branch/department modelling beyond a flat
`SHIFT_START_HOUR`. Secrets come from `.env`, not a managed secret store.

## Tests

```bash
pytest                          # 62 tests
pytest tests/test_api.py        # 53 — API, RBAC, tenant isolation, sessions, seats
pytest tests/test_face_engine.py  # 9 — the real engine
```

`test_api.py` runs on the stub so it stays fast and needs no model. `test_face_engine.py`
loads the real one and is skipped automatically when insightface is not installed, so the
suite still passes on a machine without it.

Tenant-isolation cases are the ones that matter most: they prove an admin in one
organization gets 403 or 404 on another organization's employees, attendance, face
profiles and users.

## Testing from a real Android phone

The emulator reaches this machine at `10.0.2.2`; a phone cannot. It needs the LAN address,
and three things have to line up.

**1. Bind the server to every interface.** The default only listens on loopback, which the
phone cannot reach:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**2. Build the app against this machine's address.** The URL is compiled into the APK, so
it is a build property rather than a runtime setting:

```bash
ipconfig getifaddr en0                                        # e.g. 192.168.1.28
./gradlew assembleDebug -Pfaceattend.apiHost=192.168.1.28
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

**3. Check the phone can actually see the server.** Open `http://<ip>:8000/health` in the
phone's browser before blaming the app. If that fails, the app will too.

### When it does not connect

- **macOS firewall.** It is on by default and blocks incoming connections to Python. Allow
  it in System Settings → Network → Firewall → Options, or turn the firewall off while
  testing. This is the usual cause.
- **Different networks.** Phone on mobile data, or the Mac on a different Wi-Fi band that
  is client-isolated. Guest networks often block device-to-device traffic entirely.
- **The IP changed.** DHCP reassigns it. Rebuild the APK with the new one.

Cleartext HTTP is permitted only in debug builds — `app/src/debug/res/xml/network_security_config.xml`
replaces the restrictive config in `src/main` for debug, so release builds still require TLS
with no exemption.

## Testing

The project uses `pytest` with a `@pytest.mark.slow` marker distinguishing fast unit/integration tests from heavy ML inference (`InsightFaceEngine` ArcFace loading) and live PostgreSQL tests.

### Running Tests

```powershell
# 1. Fast Suite (recommended during development):
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -m "not slow" -v

# 2. Single test file (e.g. attendance or auth):
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_phase4_attendance.py -v

# 3. Full Suite (including ML model inference):
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -v
```

> **Windows Sandbox Note:**
> On Windows, Starlette / FastAPI's `TestClient` uses an internal `asyncio` event loop whose `socketpair()` creates a loopback TCP connection on `127.0.0.1`. Under strict sandbox isolation with loopback networking blocked, `TestClient.__enter__()` hangs waiting for the socket pair handshake. When running tests in automation or agents on Windows, always execute tests outside network isolation (`BypassSandbox: true`).

## Layout

Routes are grouped by what they act on, so nothing is a thousand-line file:

```text
app/
  main.py          app wiring, response envelope, schema guard
  config.py        every setting, read from .env
  db.py            engine + session
  models.py        SQLAlchemy tables
  schemas.py       request/response models
  security.py      passwords, JWT, RBAC dependencies, audit writer
  face.py          embedding engine, liveness, organization-scoped search
  deps.py          shared across routers: role tuples, upload limits, common queries
  seed.py          demo tenants
  routers/
    auth.py        login, refresh, me
    employees.py   roster + face profiles
    attendance.py  recognition, records, dashboard, audit log
    org.py         departments, branches, shifts
migrations/        Alembic
```

## Migrations

Alembic owns the schema. The app refuses to start if migrations have not been run, rather
than creating tables behind Alembic's back and letting the two drift apart.

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "add x"        # after changing models.py
alembic downgrade -1                              # step back
```

The test suite runs `alembic upgrade head` too, so a broken migration fails the build.

## What a scan means

The gate is unattended, so the same person passes it several times a day. `recognize` answers one
of three events, and only two of them write anything:

| Situation | `event` | Writes |
| --- | --- | --- |
| No record for today | `CHECK_IN` | Creates the record, sets `PRESENT` or `LATE` |
| Checked in less than `CHECKOUT_AFTER_MINUTES` ago | `ALREADY_PRESENT` | Nothing |
| Checked in longer ago than that | `CHECK_OUT` | Stamps `check_out_at` |
| Already checked out | `ALREADY_PRESENT` | Nothing |

`ALREADY_PRESENT` is a normal `200`, not an error: a kiosk shows "already present since 09:05"
rather than a red failure. It is also **not audited** — a gate scans all day, and turning those
repeats into audit rows would bury the real events.

`CHECKOUT_AFTER_MINUTES` (default `240`) is what stops someone walking past at lunchtime from
accidentally ending their day. Lower it for short shifts.


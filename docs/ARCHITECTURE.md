# FaceAttend Platform Architecture Blueprint

This document captures the end-to-end architectural blueprint, system design, data models, and component boundaries for the FaceAttend multi-tenant facial attendance platform.

---

## 1. High-Level Platform Architecture

```text
Android Kiosk / Admin App          Web Console (Next.js 16)
        |                                     |
        | (HTTPS / Bearer token)              | (HTTPS / httpOnly cookies)
        v                                     v
   Backend API Gateway <----------------- Next.js BFF Proxy (/api/proxy/*)
   (FastAPI / Python 3.11)
        |
        +---> PostgreSQL 16 + pgvector (Embeddings, tenant records, audit logs)
        |     (Development fallback: SQLite + in-memory cosine similarity)
        |
        +---> Redis (Challenge nonces, rate limits, revocation cache)
        |
        +---> Face AI Engine (InsightFace / ArcFace embeddings)
```

### Component Status

| Component | Status | Details |
| :--- | :--- | :--- |
| **Backend API** | `Implemented` | FastAPI, SQLAlchemy 2.0, multi-tenant RBAC, vector similarity search. |
| **Web Console** | `Implemented` | Next.js 16 App Router, BFF secure proxy, Tailwind CSS, liquid-glass UI. |
| **Android Kiosk Flavor** | `Implemented` | CameraX, ML Kit face detection, interactive liveness, attendance check-in/out. |
| **Android Admin Flavor** | `Implemented` | Dashboard, employee management, 3-pose face enrollment, reports, settings. |
| **PostgreSQL + pgvector** | `Implemented` | Production database with pgvector cosine distance indexing (`<=>`). |
| **Redis Cache** | `Implemented` | Nonce storage for liveness challenges, token revocation, rate limiting. |
| **Edge IP Camera Daemon** | `Planned` | Standalone edge daemon for RTSP camera stream attendance ingestion. |
| **Docker / docker-compose**| `Planned` | Production container manifests and compose orchestrations. |

---

## 2. Multi-Tenancy and Authorization

Every tenant-owned record has explicit organization ownership via `organization_id`. Tenant scope is derived exclusively from the authenticated user or device session and validated on every operation. Client-supplied `organization_id` parameters are never trusted.

### Role Hierarchy

- `SUPER_ADMIN`: Cross-tenant platform management (reserved; disabled for general console access).
- `ORGANIZATION_ADMIN`: Full administrative control over an organization's employees, devices, policies, and audit logs.
- `HR_ADMIN`: Employee onboarding, face enrollment, shift assignments, and attendance records management.
- `MANAGER`: Scoped view of subordinate employees and departmental attendance reports.
- `ATTENDANCE_DEVICE`: Machine account for registered Android kiosk devices (scoped exclusively to `/attendance/*` and device heartbeat endpoints).
- `EMPLOYEE`: *Data record only*. Employees check in via facial scans or PINs; they do not have administrative sign-in access.

---

## 3. Data Model Blueprint

The platform uses SQLAlchemy declarative models with PostgreSQL (or SQLite in local dev):

| Table | Status | Purpose |
| :--- | :--- | :--- |
| `organizations` | `Implemented` | Tenant organization profile, slug, and subscription state. |
| `users` | `Implemented` | Administrative user credentials, roles, and 2FA secrets. |
| `employees` | `Implemented` | Employee identity, employee code, department/shift links, PIN hash. |
| `departments` | `Implemented` | Organizational departments. |
| `branches` | `Implemented` | Physical office or work locations. |
| `shifts` | `Implemented` | Work schedule timings, grace periods, and late thresholds. |
| `attendance_devices` | `Implemented` | Kiosk hardware pairings, public keys, and heartbeat status. |
| `device_enrollment_tokens` | `Implemented` | 6-character, 10-minute pairing codes for kiosk registration. |
| `device_events` | `Implemented` | Telemetry, battery, offline events, and network status logs. |
| `face_profiles` | `Implemented` | 512-dimension ArcFace embeddings, multi-pose references, consent timestamp. |
| `attendance_records` | `Implemented` | Authoritative check-in/check-out logs with confidence score and lateness. |
| `attendance_events` | `Implemented` | Intermediate scan events (PROVISIONAL, CONFIRMED, REJECTED). |
| `face_scan_snapshots` | `Implemented` | Encrypted 7-day audit images captured during kiosk scans. |
| `audit_logs` | `Implemented` | Immutable trail of administrative actions. |
| `refresh_tokens` | `Implemented` | Hashed refresh tokens with family rotation and revocation tracking. |
| `holidays` | `Planned` | Calendar holidays per organization or branch. |
| `leave_requests` | `Planned` | Employee time-off requests and approvals. |
| `subscriptions` | `Planned` | Stripe/Razorpay billing, tier quotas, and plan enforcement. |

---

## 4. Biometric Pipeline: Enrollment & Recognition

### Face Enrollment Flow (Admin App)

```text
Admin selects employee -> Consent dialog -> Front camera preview
  -> ML Kit Quality & Pose Evaluator (Yaw/Pitch angles)
  -> 3 Pose Captures (Center / Left ~30° / Right ~30°)
  -> Multipart upload to /api/v1/employees/{id}/face/enroll
  -> Backend InsightFace: extract 512-d normalized embeddings
  -> Validate embedding quality & consistency
  -> Store in face_profiles (pgvector) + update employee enrollment status
```

### Attendance Recognition Flow (Kiosk App)

```text
Kiosk CameraX stream -> ML Kit Face Detection -> Stable face lock
  -> Request liveness challenge from backend (or local challenge)
  -> Evaluate liveness gesture (Blink, Turn Left, Turn Right, Smile)
  -> Frame burst capture -> POST /api/v1/attendance/recognize (Device JWT)
  -> Backend InsightFace: extract embedding from best frame
  -> Organization-scoped pgvector cosine similarity search (<=>)
  -> Threshold checks: match score >= 0.65, margin >= 0.10
  -> Shift & lateness evaluation -> Record AttendanceRecord
  -> Return match result (Employee name, direction, late status)
  -> Kiosk cooldown timer prevents duplicate double-scans
```

---

## 5. Client Architecture (Android)

The Android codebase is structured around Clean Architecture with MVVM:

```text
app/
  src/
    main/     # Shared domain, network, models, design system, FaceCaptureSource
    admin/    # Admin flavor: management screens, 3-pose enrollment, reports
    kiosk/    # Kiosk flavor: CameraX scanner, ML Kit detection, PIN fallback
```

### Boundary Rules
- `UI (Compose)` -> `ViewModel` -> `Repository Interface` -> `Network / Local Data Source`.
- Compose screens never import Retrofit or perform business validations.
- `FaceCaptureSource` interface decouples the attendance scan engine from CameraX and ML Kit, allowing mocked unit tests.
- Offline persistence via Room is `Planned`; current builds require an active network connection.

---

## 6. Web Architecture (Next.js Console)

- Built with Next.js 16 (App Router), React 19, and Tailwind CSS.
- **BFF Security Proxy**: All browser network calls go to `/api/proxy/*`.
- JWT access tokens and refresh tokens are stored in `httpOnly`, `SameSite=Lax`, and `Secure` cookies.
- Browser JavaScript never reads or stores authorization tokens.
- Strict CSRF validation: mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) must include `X-CSRF-Token` matching the `csrf_token` cookie.

---

## 7. API Error Contract

All backend responses use a standard envelope structure:

```json
{
  "success": true,
  "data": {},
  "message": "Operation successful"
}
```

Failure envelope with machine-readable error codes:

```json
{
  "success": false,
  "error": {
    "code": "FACE_NOT_RECOGNIZED",
    "message": "Face could not be recognized."
  }
}
```

### Key Error Codes

`INVALID_CREDENTIALS`, `TOKEN_EXPIRED`, `UNAUTHORIZED`, `FORBIDDEN`, `EMPLOYEE_NOT_FOUND`, `FACE_NOT_FOUND`, `FACE_NOT_RECOGNIZED`, `MULTIPLE_FACES`, `FACE_QUALITY_LOW`, `LIVENESS_FAILED`, `ATTENDANCE_ALREADY_MARKED`, `DEVICE_NOT_AUTHORIZED`, `ORGANIZATION_SUSPENDED`.

---

## 8. MVP Sequence & Roadmap Traceability

The original 22 implementation phases are mapped as follows:
- **Phases 1–14, 16–19**: Core Android foundations, backend RBAC, face AI, attendance kiosk, device pairing, audit logging, reporting, and web console are `Implemented`.
- **Phase 15 (Offline & Poor Network Support)**: Android Room caching and offline scan queueing are `Planned`.
- **Phases 20–22 (Production Hardening & Packaging)**: CI/CD, production Docker deployment, and release signing are `Planned`. Detailed work items are tracked in [docs/ROADMAP.md](ROADMAP.md).


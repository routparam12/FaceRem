# FaceAttend (FaceRem)

FaceAttend is a multi-tenant facial attendance platform designed for enterprises, educational institutions, factories, and multi-branch organizations.

> **Note on Naming**: The repository is named `FaceRem`. The product branding is configurable via environment settings and UI constants, defaulting to **FaceAttend**.

---

## Architecture Model: Kiosk-First

FaceAttend operates on a **kiosk-first** operational model:
- **Administrative Staff** (`ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER`): Sign in to the Next.js web console or Android Admin app with email, password, and optional TOTP 2FA to manage employees, view audit logs, assign shifts, and enroll employee face profiles.
- **Employees**: Do not sign in to administrative apps. Employees **check in** and **check out** by presenting their face to registered, locked tablet kiosks running the Android Kiosk flavor. A PIN fallback is available if biometrics cannot be evaluated.

---

## Implementation Status

| Component / Feature | Status | Details |
| :--- | :--- | :--- |
| **Backend API Service** | `Implemented` | FastAPI, PostgreSQL/SQLite, pgvector, Redis, JWT auth, TOTP 2FA. |
| **Web Admin Console** | `Implemented` | Next.js 16, React 19, BFF secure cookie proxy, dashboard, employee & device management. |
| **Android Kiosk App** | `Implemented` | Dedicated kiosk flavor, CameraX, ML Kit face detection, interactive liveness, attendance sync. |
| **Android Admin App** | `Implemented` | Dedicated admin flavor, dashboard, employee directory, 3-pose face enrollment, reports. |
| **Biometric Engine** | `Implemented` | Multi-pose ArcFace 512-d embeddings via InsightFace, cosine distance search, quality evaluator. |
| **Audit & Privacy** | `Implemented` | Tamper-evident audit logs, encrypted 7-day scan snapshot retention with auto-purge. |
| **Offline Room Sync** | `Planned` | Local SQLite/Room caching and background WorkManager queue for offline kiosk check-ins. |
| **Kiosk LockTask Pinning**| `Planned` | Android DPC / LockTask mode integration to lock kiosk hardware. |
| **Shifts & Leave Web UI**| `Planned` | Dedicated web pages for managing custom work shifts, holidays, and leave requests. |

---

## Repository Structure

```text
FaceRem/
├── app/                  # Android client (Kotlin, Jetpack Compose, CameraX, ML Kit)
│   ├── src/admin/        # Admin flavor (management, face enrollment)
│   ├── src/kiosk/        # Kiosk flavor (attendance scanner, PIN fallback)
│   └── src/main/         # Shared architecture, network, domain, and FaceCaptureSource
├── backend/              # FastAPI backend service (Python 3.11, SQLAlchemy 2.0, pgvector)
│   ├── app/              # API routers, services, models, repositories, and security
│   ├── migrations/       # Alembic database migrations
│   └── scripts/          # Database seeding and OpenAPI documentation generators
├── web/                  # Next.js 16 administration console (App Router, Tailwind CSS, BFF proxy)
└── docs/                 # Platform blueprints, API contracts, and roadmap
    ├── API.md            # Generated OpenAPI reference (100+ endpoints)
    ├── ARCHITECTURE.md   # System architecture blueprint and data models
    ├── FACE_PIPELINE.md  # Detailed face recognition pipeline and thresholds
    └── ROADMAP.md        # Verified pending features and production milestones
```

---

## Local Quick Start (5 Commands)

### 1. Set Up and Run Backend
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

### 2. Run Web Console
```bash
cd web
npm install
npm run dev
```
*Open [http://localhost:3000](http://localhost:3000) and sign in using `admin@demo.com` / `Demo@123456`.*

### 3. Build Android Apps
```bash
cd app
./gradlew assembleAdminDebug    # Produces app/build/outputs/apk/admin/debug/app-admin-debug.apk
./gradlew assembleKioskDebug    # Produces app/build/outputs/apk/kiosk/debug/app-kiosk-debug.apk
```

---

## Documentation Links

- **Web Console Details**: [web/README.md](web/README.md)
- **Backend Service & Database**: [backend/README.md](backend/README.md)
- **Android App & Flavors**: [app/README.md](app/README.md)
- **Architecture & Schema Blueprint**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Documentation**: [docs/API.md](docs/API.md)
- **Product Roadmap**: [docs/ROADMAP.md](docs/ROADMAP.md)
- **Contributor & Agent Rules**: [AGENTS.md](AGENTS.md)

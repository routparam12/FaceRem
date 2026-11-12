# FaceAttend — Product Roadmap & Remaining Work

This document outlines verified pending features, technical debt, and production readiness milestones across the FaceAttend platform.

---

## 1. Android Client

| Feature / Milestone | Status | Description |
| :--- | :--- | :--- |
| **Offline Mode & Room Sync** | `Planned` | Local SQLite/Room caching for employee summaries and encrypted queuing of attendance scans during network outages via WorkManager. |
| **Kiosk LockTask / Pinning (DPC)** | `Planned` | Implement Device Policy Controller (DPC) integration or Android LockTask pinning to prevent users from exiting the kiosk app. |
| **Supervised Face Enrollment** | `Planned` | Allow administrators to initiate face enrollment directly on a kiosk terminal using an admin override PIN or badge scan. |
| **Dynamic Host Configuration** | `Partial` | Android builds currently set API base URLs via `BuildConfig.API_BASE_URL`. Dynamic URL entry on the pairing screen is planned for on-premise deployments. |

---

## 2. Web Console

| Feature / Milestone | Status | Description |
| :--- | :--- | :--- |
| **Shifts & Schedules UI** | `Planned` | Dedicated web pages to create, assign, and edit work shifts, grace periods, and late thresholds. |
| **Holidays & Leave Management** | `Planned` | Calendar management for organizational holidays and employee leave requests. |
| **Staff & Roles Management** | `Planned` | User management interface for inviting and assigning `ORGANIZATION_ADMIN`, `HR_ADMIN`, and `MANAGER` roles. |
| **CSV / Excel Bulk Import** | `Planned` | Bulk employee roster import and export functionality with validation error reporting. |
| **BFF Automatic Token Refresh** | `Planned` | Automatic refresh token rotation when access token expires during active user sessions in the web proxy. |
| **Server-Side Pagination** | `Partial` | Currently employee and attendance queries load full result sets; server-side paginated tables are required for large rosters (>500 staff). |

---

## 3. Backend Service

| Feature / Milestone | Status | Description |
| :--- | :--- | :--- |
| **Vector Index Optimization** | `Partial` | Production PostgreSQL uses `pgvector` with cosine distance (`<=>`). Building optimized HNSW or IVFFlat indexes on `face_profiles` for sub-50ms queries at scale is planned. |
| **Automated Password Reset** | `Planned` | Email notification worker to support `POST /api/v1/auth/forgot-password` and `POST /api/v1/auth/reset-password`. |
| **Branch-Specific Timezones** | `Partial` | Organization timezone is configurable in `config.py` (`DEFAULT_TIMEZONE = "Asia/Kolkata"`). Per-branch timezone overrides are planned. |
| **Edge CCTV Ingestion Agent** | `Planned` | Lightweight edge daemon for RTSP camera stream processing and continuous attendance logging. |

---

## 4. Production & DevOps

| Item | Status | Description |
| :--- | :--- | :--- |
| **Docker & Compose Packaging** | `Planned` | Multi-stage `Dockerfile` and `docker-compose.yml` for unified production deployment of backend, web, Redis, and PostgreSQL. |
| **CI / CD Pipelines** | `Planned` | Automated GitHub Actions pipelines for running backend `pytest`, web Playwright tests, and Android `assembleDebug` / `testDebugUnitTest`. |
| **InsightFace License Review** | `Planned` | Review InsightFace pre-trained model weights (e.g., `buffalo_l` / `antelopev2`) for non-commercial vs. commercial licensing compliance prior to paid SaaS launch. |
| **Tablet Pilot Checklist** | `Planned` | Hardware mounting guide, ambient lighting recommendations, anti-glare screen protectors, and minimum 5 Mbps network SLA requirements. |


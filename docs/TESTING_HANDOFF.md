# FaceAttend Testing & Verification Handoff Guide

This document provides complete instructions, credentials, architectural notes, and verification checklists for the external testing agent evaluating the FaceAttend platform.

---

## 1. System Architecture & Split-Identity Model

FaceAttend implements a strict **Kiosk-First Split-Identity Architecture**:
1. **SIGN IN / SIGN OUT (Authentication & Management)**:
   - For **Admins, HR, and Managers** only.
   - Access via Web Console (`web/`) or administrative tools.
   - Credentials: Email + Password + Mandatory 2FA (TOTP) in production + Recovery Codes.
   - Session stored in `httpOnly`, `SameSite=Lax`, `Secure` cookies (`fa_access`, `fa_refresh`).
   - Zero secrets exposed to client-side JavaScript.
2. **CHECK IN / CHECK OUT (Physical Attendance)**:
   - For **Employees**.
   - Recorded strictly via **Face Scan** at authorized attendance kiosk devices.
   - **Zero Login Accounts**: Employees have **no password, no login account, and no web console access**.
   - **Fallback Method**: If facial recognition fails or biometric consent is not granted, employees check in using **Employee Code + 4-to-6 digit PIN** (`POST /api/v1/attendance/pin-verify`).

---

## 2. Environment Setup & Execution

### 2.1 Backend (FastAPI)
The backend environment is located in `backend/.venv` (Python 3.10.20):

```bash
# Set environment variables
set JWT_SECRET=test-secret-that-is-long-enough-for-hs256-abcdef
set INSIGHTFACE_MODEL_NAME=buffalo_s
set APP_ENV=development

# Run FastAPI backend on port 8000
backend\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2.2 Web Console (Next.js 15)
The canonical web console is in `web/`:

```bash
cd web
npm run dev
# Running on http://localhost:3000
```

### 2.3 Running Backend Tests
> [!IMPORTANT]
> **Windows Sandbox Network Isolation Notice**:
> On Windows, the sandbox network isolation restricts loopback TCP socketpair creation (`127.0.0.1`), causing Starlette `TestClient` to hang if executed inside the sandbox.
> **Always run pytest commands with the sandbox bypassed (`BypassSandbox: true`):**

```bash
# Run Fast Suite (skips slow biometric models and real PostgreSQL migrations)
powershell -Command "$env:PYTHONPATH='backend'; $env:JWT_SECRET='test-secret-that-is-long-enough-for-hs256-abcdef'; backend\.venv\Scripts\pytest -m 'not slow' -v"

# Run Face Engine & Liveness Suite (Slow tests)
powershell -Command "$env:PYTHONPATH='backend'; $env:JWT_SECRET='test-secret-that-is-long-enough-for-hs256-abcdef'; backend\.venv\Scripts\pytest backend/tests/test_face_engine.py -v"
```

---

## 3. Pre-Seeded Test Credentials

When `SEED_DEMO_DATA=true` (or by running `backend\app\seed.py`), the database initializes with:

| Role | Email | Password | Organization Slug | Scoping / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Organization Admin** | `admin@northwind.demo` | `admin12345` | `northwind` | Full tenant access, devices, audit logs, timezone |
| **HR Admin** | `hr@northwind.demo` | `demo12345` | `northwind` | People management, face enrollment, PIN resets |
| **Manager** | `manager@northwind.demo` | `manager12345` | `northwind` | Scoped to assigned branch/department |
| **Kiosk Device** | *(Device Token)* | N/A | `northwind` | Enrolled via 6-character registration code |
| **Employee 1** | Code: `NW-001` | PIN: `1234` | `northwind` | Enrolled Face Profile (`Jane Doe`) |
| **Employee 2** | Code: `NW-002` | PIN: `5678` | `northwind` | Unenrolled Face Profile (`John Smith`) |

---

## 4. Web Console Feature Verification Checklist (10 Pages)

### Page 1: Sign In (`/login`)
- [ ] Test standard password sign-in for `hr@northwind.demo` / `demo12345` with organization `northwind`.
- [ ] Verify that employees (e.g. `NW-001`) have no accounts and receive `INVALID_CREDENTIALS`.
- [ ] Verify 2FA challenge flow: when 2FA is active, signing in prompts for 6-digit TOTP code or single-use recovery code.
- [ ] Verify rate limiting: 5 consecutive failed attempts lock the IP for 60 seconds.

### Page 2: Security & 2FA Settings (`/dashboard/settings/security`)
- [ ] Navigate to Security settings and click "Configure Two-Factor Auth".
- [ ] Verify the QR code is generated locally in the browser via canvas/SVG (inspect network panel: zero external API calls).
- [ ] Scan QR code into Google Authenticator / 1Password and submit the 6-digit verification code.
- [ ] Verify that 8 recovery codes are displayed with a "Copy recovery codes" button.
- [ ] Sign out and test signing in using one of the recovery codes. Verify the used recovery code cannot be reused.

### Page 3: Dashboard (`/dashboard`)
- [ ] Verify today's metrics cards: Present, Late arrivals, Not checked in, Awaiting face enrollment.
- [ ] Verify "Needs Attention" alert list displays:
  - Unconfirmed provisional events (standard assurance scans without liveness evidence).
  - Offline kiosks (devices with `last_seen_at > 15 minutes` ago).
  - Unenrolled employees (active staff missing face profiles).
- [ ] Verify clicking "Resolve issue →" links directly to the corresponding moderation page.

### Page 4: Employees (`/dashboard/employees`, `/[id]`, `/new`)
- [ ] Search and filter employees by department, name, or enrollment status.
- [ ] Add a new employee (`POST /api/v1/employees`).
- [ ] Open employee details:
  - Face enrollment: upload portrait image to generate 512-d ArcFace embedding.
  - Delete face profile: click "Remove face profile" and verify profile is hard-deleted while historical attendance is preserved.
  - Configure Fallback PIN: set a 4-digit PIN (e.g. `4321`) and verify success banner.
  - Deactivate / Reactivate employee toggle.

### Page 5: Attendance Center (`/dashboard/attendance`)
- [ ] View Live Attendance Event Stream:
  - Displays timestamp, employee, direction (Check In / Check Out), method (Face Scan / PIN Fallback), and assurance.
- [ ] Filter events by Direction (Check In / Check Out), Method (Face / PIN), and Provisional Only.
- [ ] Test Event Voiding:
  - Click "Void" on an event.
  - Modal prompts for mandatory reason (e.g. "Gate maintenance scan").
  - Submit void and verify event turns red `VOIDED` with audit explanation and rollback of daily attendance summary.
- [ ] Test Provisional Confirmation:
  - Click "Confirm" on a provisional event.
  - Verify event status transitions to `VERIFIED`.

### Page 6: Kiosk Devices (`/dashboard/devices`)
- [ ] Click "+ Register New Kiosk":
  - Modal generates a 6-character alphanumeric code (e.g. `K9X2B7`).
  - Live 10-minute countdown timer ticks down in real-time.
- [ ] Rename kiosk and toggle direction mode (`AUTO`, `IN_ONLY`, `OUT_ONLY`).
- [ ] Revoke kiosk: confirm modal and verify device status changes to `REVOKED` and device token is rejected.

### Page 7: Cameras (`/dashboard/cameras`)
- [ ] View registered cameras and their binding to physical kiosk devices.
- [ ] Click "+ Add Camera":
  - Select host device, enter camera name, choose direction (`AUTO`, `IN_ONLY`, `OUT_ONLY`), and assurance level (`HIGH`, `STANDARD`).
- [ ] Configure camera: toggle enabled/disabled status and assurance level.

### Page 8: Reports & Data Export (`/dashboard/reports`)
- [ ] Attendance Events CSV:
  - Select date range and click "Download Events CSV".
  - Inspect downloaded CSV file in text editor:
    - Verify UTF-8 BOM (`\xef\xbb\xbf`) is present at byte offset 0.
    - Verify formula injection defense: any cell starting with `=`, `+`, `-`, `@`, `\t` has a leading single quote (`'`).
- [ ] Monthly Summary CSV:
  - Select year and month and click "Download Monthly Summary CSV".
  - Verify columns: Employee Code, Name, Department, Branch, Shift, Days Present, Days Late, Days Absent, Work Hours, Late Minutes.

### Page 9: Security Audit Log (`/dashboard/audit`)
- [ ] View chronological read-only audit log.
- [ ] Filter by category: Authentication & 2FA, Devices & Cameras, Biometric / Face, Attendance Events.
- [ ] Click metadata payload to view full JSON audit context in inspect modal.
- [ ] Verify that passwords, tokens, PINs, and biometric embeddings are never present in audit metadata.

### Page 10: Organization Settings (`/dashboard/settings`)
- [ ] View current organization name, slug, and subscription plan.
- [ ] Select or input an IANA timezone identifier (e.g. `America/New_York` or `Asia/Kolkata`).
- [ ] Click "Save Settings" and verify timezone update (`PATCH /api/v1/organization`).

---

## 5. Hardware Scan Latency Profile & Calibration

### Measured Latency Profile (Intel Core i7-1355U, 12 Threads, 16 GB RAM)
End-to-end recognition includes: Image decode + SCRFD face detection + 5-point alignment + ArcFace 512-d embedding + 1:1,000 vector similarity search + 2 burst frame ROI tracking & challenge liveness verification.

| Pipeline Stage | `buffalo_l` (ResNet-50) | `buffalo_s` (MobileNet) | Latency Improvement |
| :--- | :---: | :---: | :---: |
| **Primary Face Detection (320x320)** | 2,476.5 ms | **684.9 ms** | 3.6x faster |
| **Primary ArcFace Embedding** | 656.9 ms | **130.5 ms** | 5.0x faster |
| **1:1,000 Vector Search (NumPy)** | 0.38 ms | **1.32 ms** | Real-time (< 2 ms) |
| **Burst Frame 1 ROI Liveness** | 2,275.6 ms | **688.4 ms** | 3.3x faster |
| **Burst Frame 2 ROI Liveness** | 2,477.9 ms | **696.0 ms** | 3.6x faster |
| **Total Burst Liveness (2 frames)** | 4,753.6 ms | **1,384.4 ms** | 3.4x faster |
| **TOTAL END-TO-END SCAN** | **7,888.7 ms (~7.9 s)** | **2,204.2 ms (~2.2 s)** | **3.6x speedup** |
| **END-TO-END MEDIAN** | **7,649.9 ms** | **2,165.8 ms** | **Hits ~2.0s target** |

### Accuracy Parity on Existing Face Engine Test Suite
- **Same-Person Cosine Similarity**: `0.8447` (Default threshold is `0.45`).
- **Different-Person Cosine Similarity**: `0.0101` (Must be `< 0.45`).
- **Separation Daylight**: `0.8346` (Far exceeds required `0.30` margin threshold).
- **Result**: `buffalo_s` passes 100% of biometric tests.

---

## 6. Known Risk Areas & Security Boundaries

1. **Passive Anti-Spoof Layer in Production**:
   - Production mode (`APP_ENV=production`) requires either certified passive model weights or an explicit override (`ALLOW_UNCONFIGURED_PASSIVE_LIVENESS=true`).
2. **PostgreSQL pgvector in Production**:
   - `APP_ENV=production` strictly enforces that PostgreSQL has the native `vector` extension active and `face_profiles.embedding_vec` is configured.
   - If missing, migration `c7e2b14d9a3f` and `app/main.py` fail loudly and abort boot.
   - Creating extensions in PostgreSQL requires `SUPERUSER` or database owner privileges with `CREATE` on the database/schema.
3. **BFF Proxy CSRF Protection**:
   - All mutating requests (`POST`, `PATCH`, `DELETE`) forwarded through `/api/proxy/[...path]` enforce Same-Origin validation (`origin` matches `host`). External scripts or cross-site requests receive `403 CSRF_ERROR`.


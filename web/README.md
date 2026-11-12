# FaceAttend Web Console

The web administration console and public landing page for the FaceAttend multi-tenant facial attendance platform, built with Next.js 15 (App Router), React 19, and Tailwind CSS.

---

## Quick Start

### Installation & Run

```bash
cd web
npm install
cp .env.example .env.local    # adjust if backend is not at http://127.0.0.1:8000
npm run dev                  # starts on http://localhost:3000
```

### Production Build

```bash
npm run build
npm run start
```

### Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `API_BASE_URL` | `http://127.0.0.1:8000` | Backend URL called by Next.js Server Components and BFF route handlers (server-to-server). |
| `COOKIE_SECURE` | `0` (dev) / `1` (prod) | Sets the `Secure` flag on `httpOnly` session cookies. Automatically `1` in production unless explicitly overridden. |
| `NEXT_PUBLIC_ENABLE_WEB_SCANNER` | `undefined` (off) | Feature flag. When `"1"`, enables `/dashboard/scan` in the sidebar and routes for in-browser testing. |
| `NEXT_PUBLIC_DEMO_MODE` | `undefined` (off) | When `"1"`, displays demo credential quick-fill buttons on the sign-in page. |
| `ANDROID_APK_URL` | `undefined` (none) | URL to download the companion Android APK (shown on landing page and Devices screen). |
| `ANDROID_APK_VERSION` | `null` | Optional release tag label displayed on APK download links (e.g. `v1.0.0`). |
| `ANDROID_APK_SIZE` | `null` | Optional file size label displayed on APK download links (e.g. `18 MB`). |

---

## Console Pages & Role Permissions

Employees do not sign in to the web console; authentication is restricted to organization staff (`ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER`).

| Route | Page Title | Allowed Roles | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | Landing Page | Public | Product overview and download link for the Android APK. |
| `/login` | Staff Sign-in | Public (Unauthenticated) | Staff email, password, and 2FA TOTP verification challenge. |
| `/dashboard` | Live Dashboard | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Real-time attendance counts, present/late stats, and quick actions. |
| `/dashboard/employees` | Personnel Roster | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Employee list with search, department filtering, and face status. |
| `/dashboard/employees/new` | Add Employee | `ORGANIZATION_ADMIN`, `HR_ADMIN` | Enrolls a new employee into the organization roster. |
| `/dashboard/employees/[id]` | Employee Details | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Profile details, avatar, 3-pose face enrollment, and rolling 7-day scan audit gallery. |
| `/dashboard/attendance` | Daily Attendance | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Daily check-in/out records, status badges (`PRESENT`, `LATE`, `ABSENT`), and CSV export. |
| `/dashboard/devices` | Kiosk Hardware | `ORGANIZATION_ADMIN`, `HR_ADMIN` | Tablet pairing code generator (10m single-use), device status, and instant revocation. |
| `/dashboard/cameras` | Camera Streams | `ORGANIZATION_ADMIN`, `HR_ADMIN` | Directional camera configuration (`IN_ONLY`, `OUT_ONLY`, `BIDIRECTIONAL`). |
| `/dashboard/scan` | Browser Scanner | `ORGANIZATION_ADMIN`, `HR_ADMIN` (Gated) | Browser-based webcam test scanner. Hidden unless `NEXT_PUBLIC_ENABLE_WEB_SCANNER=1`. |
| `/dashboard/reports` | Reports & Export | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Monthly metrics (hours worked, overtime, absences) and CSV downloads. |
| `/dashboard/audit` | Audit Trail | `ORGANIZATION_ADMIN` | Immutable administrative log of credential and biometric actions. |
| `/dashboard/settings` | Organization | `ORGANIZATION_ADMIN` | Organization profile and subscription seat usage. |
| `/dashboard/settings/security` | Security & 2FA | `ORGANIZATION_ADMIN`, `HR_ADMIN`, `MANAGER` | Password changes and RFC 6238 TOTP two-factor setup/recovery codes. |

---

## Security Model

* **Backend-For-Frontend (BFF) Architecture:**
  The browser never calls the FastAPI backend directly and never has access to JWT access or refresh tokens in JavaScript. All requests go through Next.js Server Components or the `/api/proxy/[...path]` route handler.
* **HttpOnly Session Cookies:**
  Access tokens (`fa_access`) and refresh tokens (`fa_refresh`) are stored in `httpOnly`, `SameSite=Lax` cookies. The `Secure` flag is enforced in production or when `COOKIE_SECURE=1`.
* **Proxy Allowlist:**
  `/api/proxy/[...path]` strictly checks incoming paths and methods against an explicit regex allowlist. Any path or method not explicitly permitted returns `403 FORBIDDEN`.
* **CSRF Validation:**
  For mutating methods (`POST`, `PUT`, `PATCH`, `DELETE`), the proxy verifies that the `Origin` header matches the incoming `Host` header. If `Origin` is missing, `Sec-Fetch-Site` must equal `"same-origin"`. Requests failing this check receive `403 CSRF_ERROR`.
* **Session Expiry:**
  When the access token expires (30 minutes), server calls receive `401 UNAUTHORIZED`, clearing cookies and redirecting the browser to `/login?expired=1`.
* **Local Storage Isolation:**
  `localStorage` contains only a single user interface preference: `faceattend_theme` (`"glass"` or `"flat"`). No tokens, identities, or organizational data are stored in the browser's local storage.

---

## Theme & Styling

* **Liquid Glass Skin:**
  Features soft pastel gradient backdrops with blurred glass panels (`backdrop-filter: blur(18px) saturate(140%)`, `rgba(255, 255, 255, 0.62)`).
* **Flat Theme Fallback:**
  A "Liquid glass" toggle in the top navigation allows switching to an opaque, flat design token set.
* **Accessibility Fallbacks:**
  * System prefers reduced transparency: `@media (prefers-reduced-transparency: reduce)` falls back to solid background colors.
  * Browser lacks backdrop filter: `@supports not (backdrop-filter: blur(1px))` falls back to opaque surface cards.
  * System prefers reduced motion: `@media (prefers-reduced-motion: reduce)` disables background float animations.
* **Design Tokens:**
  All tokens (`--surface-glass`, `--border-glass`, `--shadow-glass`, `--accent-primary`, etc.) are declared in [`src/app/globals.css`](src/app/globals.css).

---

## Testing

End-to-end tests use Playwright.

### Running Playwright Tests

```bash
# 1. Start backend with demo data:
cd ../backend
APP_ENV=dev SEED_DEMO_DATA=true uvicorn app.main:app --reload

# 2. Start web application:
cd ../web
npm run dev

# 3. Run Playwright suite:
npm run test:e2e
```

### Test Specs (`web/tests/`)
* `smoke.spec.ts`: Login, navigation across tabs, employee detail inspection, and reports export.
* `security.spec.ts`: BFF proxy allowlist enforcement, CSRF origin rejection, and cookie security flags.
* `org-isolation.spec.ts`: Cross-tenant boundary verification between `northwind` and `acme` organizations.

---

## Status of Features & Known Gaps

| Feature | Status | Notes |
| :--- | :--- | :--- |
| Liquid Glass Interface & Flat Toggle | Implemented | Responsive layout with token-based glass surface and accessibility fallbacks. |
| BFF Security Proxy & CSRF Gating | Implemented | Strict method allowlist with Origin and Sec-Fetch-Site checking. |
| 7-Day Rolling Scan Photo Inspection | Implemented | Admin review gallery for verification frames on employee detail page. |
| 2FA / TOTP Setup in Console | Implemented | QR code provisioning, code confirmation, and backup recovery codes. |
| Automatic Background Token Refresh | Planned | Expired access tokens redirect to sign-in; transparent refresh in BFF proxy is not built yet. |
| Table Pagination | Planned | Employees, attendance, and audit log tables load first page results without offset pagination controls. |
| Work Shifts & Scheduling Page | Planned | Shifts are created via API; no dedicated management screen in the web console yet. |
| Holidays & Time Off Calendar | Planned | Model and web calendar views are not implemented. |
| Staff Team & Role Management | Planned | User administration exists via API, but team role assignment UI is not implemented. |
| Bulk CSV Employee Import | Planned | Roster import currently requires individual creation via `/dashboard/employees/new` or API. |

# FaceAttend Android Client

A native Android application written in Kotlin and Jetpack Compose providing facial biometric attendance, kiosk scanning, and organization administration.

---

## Two Applications from One Codebase

The project uses Gradle product flavors on the `role` dimension to produce two distinct applications from a single shared codebase:

| Property | Admin Flavor (`admin`) | Kiosk Flavor (`kiosk`) |
| :--- | :--- | :--- |
| **Application ID** | `com.facerem.admin` | `com.facerem.kiosk` |
| **App Name** | FaceAttend Admin | FaceAttend Kiosk |
| **Target User** | Organization Admins & HR Staff | Physical Lobby / Gate Kiosk Devices |
| **Included Features** | Staff sign-in, 2FA/TOTP verification, 3-pose biometric face enrollment, roster management, attendance history, reports, and audit logs. | Unattended face scanner, challenge-based liveness verification, dynamic camera overlay, PIN fallback keypad, and single-use device enrollment. |
| **Excluded Features** | Attendance scanning is removed; staff cannot check in from the admin app. | Deliberately has **no** admin screens, **no** employee detail routes, and **no** demo/guest modes in release builds. |

---

## Build & Run

### Prerequisites
* Android Studio Ladybug or newer
* JDK 17
* Android SDK 35 / 36 (`minSdk = 23`, `compileSdk = 37`)

### Gradle Tasks & APK Outputs

```bash
# Build Debug APKs:
./gradlew assembleAdminDebug     # Output: app/build/outputs/apk/admin/debug/app-admin-debug.apk
./gradlew assembleKioskDebug     # Output: app/build/outputs/apk/kiosk/debug/app-kiosk-debug.apk

# Build Release APKs:
./gradlew assembleAdminRelease   # Output: app/build/outputs/apk/admin/release/app-admin-release-unsigned.apk
./gradlew assembleKioskRelease   # Output: app/build/outputs/apk/kiosk/release/app-kiosk-release-unsigned.apk
```

### Backend API Configuration

The API URL is determined at build time:
* **Debug Builds:** Default host is `10.0.2.2:8000` for the Android emulator. For testing on a physical handset on your local Wi-Fi network, pass your machine's LAN IP:
  ```bash
  ./gradlew assembleAdminDebug -Pfaceattend.apiHost=192.168.1.50 -Pfaceattend.apiPort=8000
  ```
* **Release Builds:** Hardcoded to `https://api.faceattend.example/` in `build.gradle.kts`.
* **Network Security:** Cleartext HTTP traffic is permitted **only** in debug builds via `src/debug/res/xml/network_security_config.xml`. Production release builds enforce TLS with cleartext disabled.

---

## Kiosk Attendance Flow

1. **Device Enrollment:**
   * A staff administrator generates a 6-character, 10-minute pairing code in the web console (`/dashboard/devices`).
   * The kiosk enters the code and registers itself with the server (`POST /api/v1/devices/enroll`).
   * The server issues a dedicated `ATTENDANCE_DEVICE` credential.
2. **Credential Storage (`KeystoreDeviceCredentialStore`):**
   * Device credentials are encrypted with AES-256-GCM using keys stored in the hardware-backed `AndroidKeyStore` (TEE / StrongBox).
   * Irreversible wipe occurs immediately if the device is revoked or unpaired.
3. **Revocation & Expiry:**
   * The backend validates device status against the database on every scan request.
   * If revoked, the API returns HTTP 401 `DEVICE_NOT_AUTHORIZED`, triggering `TokenAuthenticator` to wipe local credentials and return to the enrollment screen.
4. **Attendance Scanning (`ScanRoute` & `ScanViewModel`):**
   * Uses CameraX `ImageAnalysis` with ML Kit Face Detection (`COORDINATE_SYSTEM_VIEW_REFERENCED`) for real-time bounding box tracking.
   * Challenge-based liveness verification prompts for random actions (blink, nod, smile).
   * Only the largest, closest face in the frame is submitted for server-side recognition.
5. **Screen Overlay States & Colors:**
   * `ANALYZING` (White): Frame quality gating and server request in-flight.
   * `CHALLENGE` (Blue): Liveness instruction active (e.g. "Blink slowly").
   * `RECOGNIZED` (Green): Checkmark icon, employee name, event timestamp, and late minutes.
   * `ALREADY_PRESENT` (Green): "Already checked in at HH:MM".
   * `NOT_RECOGNIZED` (Red): Shown **only** after server returns `FACE_NOT_RECOGNIZED`. Offers PIN fallback button.
   * `LIVENESS_FAILED` / `QUALITY` (Amber): Warning icon with retry instructions ("Look straight", "Ensure good lighting").
6. **Result Hold & Undo:**
   * Recognized results hold on screen for 3 seconds before automatically resetting for the next person.
   * A 30-second undo banner allows canceling accidental punches via `POST /api/v1/attendance/undo`.
7. **PIN Fallback:**
   * Enables manual check in / check out with employee code and 4-digit PIN. Locks out for 15 minutes after 5 consecutive failures.

### Kiosk Security Implementation Status

| Capability | Status | Notes |
| :--- | :--- | :--- |
| Unattended Locked Scan Screen | Implemented | Dedicated scanning view without navigation back-stack. |
| Exit Protection Pill | Partial | Visual "Hold to exit" pill; admin PIN exit dialog is not configured. |
| Android LockTask / Kiosk Mode | Planned | Android Device Policy Controller (DPC) system pinning is not configured. |
| Supervised On-Kiosk Face Enrollment | Planned | Enrollment is performed exclusively from the admin app or web console. |

---

## Admin Application Flow

* **Screens:**
  * `SplashRoute`: Session verification and routing.
  * `LoginRoute`: Multi-tenant sign-in with email, password, and optional organization code.
  * `Two-Factor Challenge`: Handles `TOTP_REQUIRED` prompts for 6-digit codes or recovery keys.
  * `DashboardRoute`: Attendance stats, late arrival counters, and quick actions.
  * `EmployeesRoute` & `EmployeeDetailRoute`: Roster browsing, status inspection, and avatar views.
  * `FaceEnrollmentRoute`: Multi-pose face capture flow with on-screen consent.
  * `ReportsRoute`: High-level attendance rate charts and overtime summaries.
  * `SettingsRoute`: Profile, notifications, privacy policy, and sign-out.
* **Face Enrollment Action:**
  * Center navigation button and "Enroll face" quick action open an employee picker sheet.
  * Available **only** to `ORGANIZATION_ADMIN` and `HR_ADMIN`. Hidden for `MANAGER`.
  * Guided 3-pose camera capture (`FRONT`, `SLIGHT_LEFT`, `SLIGHT_RIGHT`) with explicit on-screen biometric consent checkbox before upload.
* **Attendance Scan Removal:**
  * All routes to attendance scanning are removed from the admin flavor (`AppRoute.Scan` eliminated).
* **Guest & Demo Credentials:**
  * "Fill demo credentials" and "Continue as guest" are restricted to debug builds (`if (BuildConfig.DEBUG)`). Release builds omit both.

---

## Architecture & Design Patterns

* **Package Layout:**
  * `core/common`: Result wrappers (`AppResult`), validation, and clock abstractions.
  * `core/network`: Retrofit 2 APIs, DTOs, OkHttp interceptors, and error mappers.
  * `core/camera`: CameraX preview, ML Kit analyzers, frame quality evaluation, and capture abstractions.
  * `core/security`: Hardware KeyStore encryption and device credential storage.
  * `feature/*`: Feature modules (auth, dashboard, employees, faceenrollment, attendance, reports).
* **FaceCaptureSource Abstraction:**
  * `FaceCaptureSource` decouples camera hardware and ML Kit detection from the presentation layer. ViewModels and state machines consume a unified `Flow<FaceCaptureObservation>`, allowing offline simulation and testability without Android camera bindings.
* **Dependency Injection:**
  * Hilt manages singleton network, datastore, and repository bindings across flavor source sets.

---

## Testing

### Unit Test Execution

```powershell
# Run unit tests for Admin flavor:
./gradlew testAdminDebugUnitTest

# Run unit tests for Kiosk flavor:
./gradlew testKioskDebugUnitTest
```

### Verified Test Classes
* **Shared (`src/test`):**
  * `FaceQualityEvaluatorTest`: Bounding box, blur, and lighting gating tests.
  * `ValidatorsTest`: Email and password validation logic.
  * `RoleTest`: Parsing and permission checks across all role strings.
  * `ApiErrorMapperTest`: Backend error envelope mapping.
  * `TokenAuthenticatorTest`: Refresh token rotation and device revocation handling.
  * `DeviceCredentialStoreTest`: KeyStore credential serialization and lifecycle.
  * `ScanStateMachineTest` & `ScanViewModelTest`: Kiosk scan state transitions.
  * `TrackOverlayMappingTest`: State-to-color mapping and non-recognized red rule verification.
* **Admin Flavor (`src/testAdmin`):**
  * `LoginViewModelTest`: Normal login, 2FA prompt transitions, recovery codes, and role rejections.
  * `FaceEnrollmentViewModelTest`: Consent gating and 3-pose frame aggregation.
  * `HistoryUiStateTest`: Filter selection and date formatting.
* **Kiosk Flavor (`src/testKiosk`):**
  * `KioskEnrollmentViewModelTest`: Code validation, pairing state, and error handling.
  * `KioskRoutingTest`: Enrollment vs scan screen routing based on credentials.
* **Hardware Requirements:**
  * Unit tests run without device dependencies. Physical devices or emulators are required only for hardware camera sensor preview and native AndroidKeyStore StrongBox operations.

---

## Security & Privacy Verification

* **Permissions:** `CAMERA`, `INTERNET`, `ACCESS_NETWORK_STATE` declared in manifest.
* **Cleartext Policy:** Enforced via `network_security_config.xml`; HTTP allowed only in debug builds.
* **Zero Logging of Credentials & Frames:**
  Code inspection of `TokenAuthenticator`, `AuthInterceptor`, and `DeviceCredentialStore` verifies that passwords, raw JWT tokens, PINs, and raw image byte arrays are never printed to Logcat.


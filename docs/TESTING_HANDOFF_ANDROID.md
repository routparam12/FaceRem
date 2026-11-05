# FaceAttend Android App Testing & Verification Handoff Guide

## 1. Scope & Architecture (Stage 5A)

Stage 5A establishes the foundation and device provisioning for the Android Kiosk application while preserving the legacy Admin application:
- **Flavor Split**:
  - `admin` (`com.facerem.admin`): Legacy multi-screen administrative client for Super Admin, Organization Admin, and HR. Contains People, History, Reports, and Settings screens.
  - `kiosk` (`com.facerem.kiosk`): Dedicated attendance tablet kiosk. Contains **only** device enrollment and biometric scanning entry. Zero admin screens, zero employee login accounts, zero guest/demo mode in release.
- **Camera Independence**:
  - `FaceCaptureSource` interface and observation models (`FaceCaptureObservation`, `FaceCaptureQuality`) decouple all ViewModels and use-cases from CameraX and ML Kit.
  - A test fake `FakeFaceCaptureSource` is provided for headless testing.
- **Hardware-Backed Keystore Credential Store**:
  - Native `AndroidKeyStore` with 256-bit AES-GCM authenticated encryption.
  - Generates key inside hardware TEE/StrongBox; zero plain-text tokens persisted.
  - `wipe()` irreversibly clears SharedPreferences and deletes master key from AndroidKeyStore.
- **Zero-Trust Device Revocation**:
  - If server responds with `401 DEVICE_NOT_AUTHORIZED` or `401 TOKEN_EXPIRED`, `TokenAuthenticator` immediately calls `deviceCredentialStore.wipe()` and broadcasts an event to return to the Enrollment screen with:
    `"This device was removed. Ask an admin for a new code."`

---

## 2. Backend Endpoints & Error Codes

| Endpoint | Method | Required Role | Request Body | Success Response | Error Codes |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/api/v1/devices/enroll` | `POST` | Anonymous (`X-No-Auth`) | `{ "code": "ABC234", "name": "Front Gate Tablet" }` | `200 OK`<br>`{ "device_id": "...", "access_token": "...", "mode": "AUTO" }` | `400 CODE_INVALID_OR_EXPIRED`<br>`429 RATE_LIMITED` |
| `/api/v1/devices/me/events` | `POST` | `ATTENDANCE_DEVICE` | `{ "event_type": "KIOSK_EXIT_UNLOCK", "details": {} }` | `200 OK`<br>`{ "status": "recorded", "event_type": "..." }` | `401 DEVICE_NOT_AUTHORIZED`<br>`429 RATE_LIMITED` |
| `/api/v1/attendance/recognize` | `POST` | `ATTENDANCE_DEVICE` | `MultipartBody` (image, challenge_id, nonce, burst) | `200 OK`<br>`{ "employee_id": "...", "event": "CHECK_IN" }` | `401 DEVICE_NOT_AUTHORIZED`<br>`422 FACE_NOT_RECOGNIZED`<br>`422 LIVENESS_FAILED` |
| `/api/v1/attendance/challenge` | `POST` | `ATTENDANCE_DEVICE` | None | `200 OK`<br>`{ "challenge_id": "...", "nonce": "...", "actions": [...] }` | `401 DEVICE_NOT_AUTHORIZED` |

---

## 3. How to Build Each Flavor

From the workspace root:

```bash
# Build Kiosk Debug APK
./gradlew :app:assembleKioskDebug

# Build Admin Debug APK
./gradlew :app:assembleAdminDebug

# Build All Debug Flavors
./gradlew :app:assembleDebug

# Build Release Flavors (HTTPS-only, Proguard optimization disabled in stage 5A)
./gradlew :app:assembleKioskRelease
./gradlew :app:assembleAdminRelease
```

Generated APK Outputs:
- `app/build/outputs/apk/kiosk/debug/app-kiosk-debug.apk`
- `app/build/outputs/apk/admin/debug/app-admin-debug.apk`

---

## 4. Test Suites Added (Written, Not Run)

Unit tests have been authored per the Stage 5A test plan:
1. `app/src/test/java/com/facerem/core/security/DeviceCredentialStoreTest.kt`:
   - Validates credential persistence, retrieval, `wipe()` state clearing, and `notifyRevoked()` emission.
2. `app/src/testKiosk/java/com/facerem/kiosk/enrollment/KioskEnrollmentViewModelTest.kt`:
   - Validates code input filtering (uppercase, unambiguous 32-character alphabet, 6-character truncation).
   - Validates successful enrollment and credential storage.
   - Validates error handling for `CODE_INVALID_OR_EXPIRED` (400), `RATE_LIMITED` (429), and network failure.
   - Validates automatic UI wipe and navigation trigger on device revocation event.
3. `app/src/testKiosk/java/com/facerem/kiosk/navigation/KioskRoutingTest.kt`:
   - Validates unprovisioned tablet starts at Enrollment screen.
   - Validates provisioned tablet starts at Scan screen.

---

## 5. Risk Areas & Priority Order

1. **Keystore Compatibility on Custom Android OEM Tablet ROMs**:
   - *Risk*: Some low-cost budget Android tablets (running non-standard Android distributions) exhibit key-loss bugs on reboot in `AndroidKeyStore`.
   - *Mitigation*: Implementation wraps decrypt in safe fallback to re-enroll cleanly rather than crashing.
2. **Device Token 365-Day Expiry**:
   - *Risk*: Device tokens are issued for 365 days. If a device token expires, the device cannot refresh silently and must be re-enrolled with a new registration code.
3. **Network Configuration**:
   - *Risk*: Debug builds connect to `http://10.0.2.2:8000` (emulator) or LAN IP via `-Pfaceattend.apiHost`. Physical tablets require LAN accessibility to the FastAPI port.

---

## 6. What Requires a Real Device / Emulator for Stage 5B

- CameraX ImageAnalysis stream verification with front-facing camera.
- Physical lighting and face distance/angle verification for ML Kit tracking.
- Immersive kiosk mode (`startLockTask`) and screen pinning on dedicated Android hardware.


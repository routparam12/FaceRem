# FaceAttend API Reference

> Auto-generated from `app.openapi()` by `backend/scripts/generate_api_docs.py`. Do not edit manually.

**API Version:** 0.1.0  
**FastAPI Title:** FaceAttend API

## Endpoints Summary

| Method | Path | Summary |
| :--- | :--- | :--- |
| `GET` | `/api/v1/attendance` | List Attendance |
| `POST` | `/api/v1/attendance/challenge` | Get Challenge |
| `GET` | `/api/v1/attendance/events` | List Attendance Events |
| `POST` | `/api/v1/attendance/events/{event_id}/confirm` | Confirm Event |
| `POST` | `/api/v1/attendance/events/{event_id}/void` | Void Event |
| `POST` | `/api/v1/attendance/pin-verify` | Pin Verify |
| `POST` | `/api/v1/attendance/recognize` | Recognize |
| `POST` | `/api/v1/attendance/scan` | Scan Observation |
| `POST` | `/api/v1/attendance/undo` | Undo Attendance |
| `GET` | `/api/v1/audit-logs` | List Audit Logs |
| `POST` | `/api/v1/auth/change-password` | Change Password |
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/auth/me` | Me |
| `POST` | `/api/v1/auth/refresh` | Refresh |
| `POST` | `/api/v1/auth/signup` | Signup |
| `POST` | `/api/v1/auth/totp/login` | Totp Login |
| `POST` | `/api/v1/auth/totp/setup` | Totp Setup |
| `POST` | `/api/v1/auth/totp/verify` | Totp Verify |
| `GET` | `/api/v1/branches` | List Branches |
| `POST` | `/api/v1/branches` | Create Branch |
| `DELETE` | `/api/v1/branches/{branch_id}` | Delete Branch |
| `GET` | `/api/v1/cameras` | List Cameras |
| `POST` | `/api/v1/cameras` | Create Camera |
| `PATCH` | `/api/v1/cameras/{camera_id}` | Update Camera |
| `GET` | `/api/v1/dashboard` | Dashboard |
| `GET` | `/api/v1/departments` | List Departments |
| `POST` | `/api/v1/departments` | Create Department |
| `DELETE` | `/api/v1/departments/{department_id}` | Delete Department |
| `GET` | `/api/v1/devices` | List Devices |
| `POST` | `/api/v1/devices/enroll` | Enroll Device |
| `POST` | `/api/v1/devices/enrollment-code` | Create Enrollment Code |
| `POST` | `/api/v1/devices/me/events` | Record Device Event |
| `PATCH` | `/api/v1/devices/{device_id}` | Update Device |
| `POST` | `/api/v1/devices/{device_id}/revoke` | Revoke Device |
| `GET` | `/api/v1/employees` | List Employees |
| `POST` | `/api/v1/employees` | Create Employee |
| `DELETE` | `/api/v1/employees/{employee_id}` | Delete Employee |
| `GET` | `/api/v1/employees/{employee_id}` | Get Employee |
| `PUT` | `/api/v1/employees/{employee_id}` | Update Employee |
| `GET` | `/api/v1/employees/{employee_id}/avatar` | Get Employee Avatar |
| `DELETE` | `/api/v1/employees/{employee_id}/face` | Revoke Face |
| `POST` | `/api/v1/employees/{employee_id}/face/enroll` | Enroll Face |
| `POST` | `/api/v1/employees/{employee_id}/pin` | Set Employee Pin |
| `GET` | `/api/v1/employees/{employee_id}/recent-scans` | Get Recent Scans |
| `GET` | `/api/v1/employees/{employee_id}/recent-scans/{photo_id}` | Get Recent Scan Photo |
| `GET` | `/api/v1/organization` | Get Organization |
| `PATCH` | `/api/v1/organization` | Update Organization |
| `GET` | `/api/v1/reports/attendance-events.csv` | Export Attendance Events Csv |
| `GET` | `/api/v1/reports/monthly-summary.csv` | Export Monthly Summary Csv |
| `GET` | `/api/v1/reports/summary` | Get Reports Summary |
| `GET` | `/api/v1/shifts` | List Shifts |
| `POST` | `/api/v1/shifts` | Create Shift |
| `DELETE` | `/api/v1/shifts/{shift_id}` | Delete Shift |
| `GET` | `/api/v1/subscription` | Get Subscription |
| `GET` | `/api/v1/users` | List Users |
| `POST` | `/api/v1/users` | Create User |
| `PATCH` | `/api/v1/users/{user_id}` | Update User |
| `GET` | `/health` | Health |

## Endpoint Details

### `GET` /api/v1/attendance

**Summary:** List Attendance  
**Operation ID:** `list_attendance_api_v1_attendance_get`  

Lists attendance records, scoped to the caller's assigned branch/department for HR and managers.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `on` | `query` | No | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/challenge

**Summary:** Get Challenge  
**Operation ID:** `get_challenge_api_v1_attendance_challenge_post`  

Issues an active challenge sequence with a short-lived nonce for kiosk scan verification.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `GET` /api/v1/attendance/events

**Summary:** List Attendance Events  
**Operation ID:** `list_attendance_events_api_v1_attendance_events_get`  

Lists immutable attendance events, scoped by role and branch/department.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `query` | No | `integer` | - |
| `employee_id` | `query` | No | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/events/{event_id}/confirm

**Summary:** Confirm Event  
**Operation ID:** `confirm_event_api_v1_attendance_events__event_id__confirm_post`  

Admin/HR operation: confirms a provisional event, promoting it to the daily AttendanceRecord.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/events/{event_id}/void

**Summary:** Void Event  
**Operation ID:** `void_event_api_v1_attendance_events__event_id__void_post`  

Admin/HR operation: voids an attendance event with audit trail.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `VoidEventRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/pin-verify

**Summary:** Pin Verify  
**Operation ID:** `pin_verify_api_v1_attendance_pin_verify_post`  

Verifies employee_code + PIN fallback from a registered kiosk. Does NOT record attendance in Phase 2.

**Request Body (application/json):** `PinVerifyRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/recognize

**Summary:** Recognize  
**Operation ID:** `recognize_api_v1_attendance_recognize_post`  

Thin adapter over process_face_observation for camera-independent attendance recognition.

**Request Body (multipart/form-data):** `Body_recognize_api_v1_attendance_recognize_post`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/scan

**Summary:** Scan Observation  
**Operation ID:** `scan_observation_api_v1_attendance_scan_post`  

Camera-independent attendance scan endpoint consuming a FaceObservation.

**Request Body (application/json):** `FaceObservation`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/attendance/undo

**Summary:** Undo Attendance  
**Operation ID:** `undo_attendance_api_v1_attendance_undo_post`  

Voids the last recorded event inside the 30-second window.

**Request Body (application/json):** `UndoRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/audit-logs

**Summary:** List Audit Logs  
**Operation ID:** `list_audit_logs_api_v1_audit_logs_get`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `query` | No | `integer` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/change-password

**Summary:** Change Password  
**Operation ID:** `change_password_api_v1_auth_change_password_post`  
**Request Body (application/json):** `ChangePasswordRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/login

**Summary:** Login  
**Operation ID:** `login_api_v1_auth_login_post`  
**Request Body (application/json):** `LoginRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/logout

**Summary:** Logout  
**Operation ID:** `logout_api_v1_auth_logout_post`  
**Request Body (application/json):** `RefreshRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/auth/me

**Summary:** Me  
**Operation ID:** `me_api_v1_auth_me_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/auth/refresh

**Summary:** Refresh  
**Operation ID:** `refresh_api_v1_auth_refresh_post`  
**Request Body (application/json):** `RefreshRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/signup

**Summary:** Signup  
**Operation ID:** `signup_api_v1_auth_signup_post`  
**Request Body (application/json):** `SignupRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/totp/login

**Summary:** Totp Login  
**Operation ID:** `totp_login_api_v1_auth_totp_login_post`  

Completes sign-in using a short-lived challenge token and TOTP or recovery code.

**Request Body (application/json):** `TotpLoginRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/auth/totp/setup

**Summary:** Totp Setup  
**Operation ID:** `totp_setup_api_v1_auth_totp_setup_post`  

Generates an RFC 6238 TOTP key and provisioning URI for Google Authenticator / 1Password.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/auth/totp/verify

**Summary:** Totp Verify  
**Operation ID:** `totp_verify_api_v1_auth_totp_verify_post`  

Confirms the TOTP code, enables 2FA, and returns 8 one-time backup recovery codes.

**Request Body (application/json):** `TotpVerifyRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/branches

**Summary:** List Branches  
**Operation ID:** `list_branches_api_v1_branches_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/branches

**Summary:** Create Branch  
**Operation ID:** `create_branch_api_v1_branches_post`  
**Request Body (application/json):** `BranchCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` /api/v1/branches/{branch_id}

**Summary:** Delete Branch  
**Operation ID:** `delete_branch_api_v1_branches__branch_id__delete`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `branch_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/cameras

**Summary:** List Cameras  
**Operation ID:** `list_cameras_api_v1_cameras_get`  

Lists cameras for the organization, scoped to branch if manager/HR.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/cameras

**Summary:** Create Camera  
**Operation ID:** `create_camera_api_v1_cameras_post`  

Registers a new camera associated with an existing device.

**Request Body (application/json):** `CameraCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `PATCH` /api/v1/cameras/{camera_id}

**Summary:** Update Camera  
**Operation ID:** `update_camera_api_v1_cameras__camera_id__patch`  

Updates camera parameters (direction, assurance, branch, enabled).

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `camera_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `CameraUpdate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/dashboard

**Summary:** Dashboard  
**Operation ID:** `dashboard_api_v1_dashboard_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `GET` /api/v1/departments

**Summary:** List Departments  
**Operation ID:** `list_departments_api_v1_departments_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/departments

**Summary:** Create Department  
**Operation ID:** `create_department_api_v1_departments_post`  
**Request Body (application/json):** `DepartmentCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` /api/v1/departments/{department_id}

**Summary:** Delete Department  
**Operation ID:** `delete_department_api_v1_departments__department_id__delete`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `department_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/devices

**Summary:** List Devices  
**Operation ID:** `list_devices_api_v1_devices_get`  

Lists registered devices for this organization, scoped by branch for HR/managers.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/devices/enroll

**Summary:** Enroll Device  
**Operation ID:** `enroll_device_api_v1_devices_enroll_post`  

Exchanges an active enrollment code for a long-lived, revocable ATTENDANCE_DEVICE credential.

**Request Body (application/json):** `DeviceEnrollRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/devices/enrollment-code

**Summary:** Create Enrollment Code  
**Operation ID:** `create_enrollment_code_api_v1_devices_enrollment_code_post`  

Issues a 6-character, 10-minute single-use code to register a physical kiosk device.

**Request Body (application/json):** `DeviceEnrollmentCodeRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/devices/me/events

**Summary:** Record Device Event  
**Operation ID:** `record_device_event_api_v1_devices_me_events_post`  

Records an operational event from an authenticated kiosk device into the organization audit log.

**Request Body (application/json):** `DeviceEventRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PATCH` /api/v1/devices/{device_id}

**Summary:** Update Device  
**Operation ID:** `update_device_api_v1_devices__device_id__patch`  

Updates device name, assigned branch, or operating mode (AUTO, IN_ONLY, OUT_ONLY).

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `device_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `DeviceUpdateRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/devices/{device_id}/revoke

**Summary:** Revoke Device  
**Operation ID:** `revoke_device_api_v1_devices__device_id__revoke_post`  

Immediately revokes an attendance kiosk. Its credential will fail with DEVICE_NOT_AUTHORIZED.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `device_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/employees

**Summary:** List Employees  
**Operation ID:** `list_employees_api_v1_employees_get`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `include_inactive` | `query` | No | `boolean` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/employees

**Summary:** Create Employee  
**Operation ID:** `create_employee_api_v1_employees_post`  
**Request Body (application/json):** `EmployeeCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` /api/v1/employees/{employee_id}

**Summary:** Delete Employee  
**Operation ID:** `delete_employee_api_v1_employees__employee_id__delete`  

Soft delete: the employee row and attendance history are kept, but the employee is
deactivated and can no longer be recognized by a scan.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/employees/{employee_id}

**Summary:** Get Employee  
**Operation ID:** `get_employee_api_v1_employees__employee_id__get`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `PUT` /api/v1/employees/{employee_id}

**Summary:** Update Employee  
**Operation ID:** `update_employee_api_v1_employees__employee_id__put`  

Partial update: only fields present in the payload are changed.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `EmployeeUpdate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/employees/{employee_id}/avatar

**Summary:** Get Employee Avatar  
**Operation ID:** `get_employee_avatar_api_v1_employees__employee_id__avatar_get`  

Returns the employee's profile photo captured during enrollment.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` /api/v1/employees/{employee_id}/face

**Summary:** Revoke Face  
**Operation ID:** `revoke_face_api_v1_employees__employee_id__face_delete`  

Removes the biometric profile completely. Attendance history is deliberately left untouched.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/employees/{employee_id}/face/enroll

**Summary:** Enroll Face  
**Operation ID:** `enroll_face_api_v1_employees__employee_id__face_enroll_post`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `POST` /api/v1/employees/{employee_id}/pin

**Summary:** Set Employee Pin  
**Operation ID:** `set_employee_pin_api_v1_employees__employee_id__pin_post`  

Sets or resets an employee PIN for kiosk fallback. Restricted to Admin/HR scope.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `SetPinRequest`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/employees/{employee_id}/recent-scans

**Summary:** Get Recent Scans  
**Operation ID:** `get_recent_scans_api_v1_employees__employee_id__recent_scans_get`  

Returns metadata for recent kiosk verification scan photos from the last 7 days (admin-only).

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/employees/{employee_id}/recent-scans/{photo_id}

**Summary:** Get Recent Scan Photo  
**Operation ID:** `get_recent_scan_photo_api_v1_employees__employee_id__recent_scans__photo_id__get`  

Streams a kiosk verification scan photo from the last 7 days (admin-only).

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `employee_id` | `path` | Yes | `string` | - |
| `photo_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/organization

**Summary:** Get Organization  
**Operation ID:** `get_organization_api_v1_organization_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `PATCH` /api/v1/organization

**Summary:** Update Organization  
**Operation ID:** `update_organization_api_v1_organization_patch`  
**Request Body (application/json):** `OrganizationUpdate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/reports/attendance-events.csv

**Summary:** Export Attendance Events Csv  
**Operation ID:** `export_attendance_events_csv_api_v1_reports_attendance_events_csv_get`  

Streams full raw attendance events as a formula-injection-safe CSV with UTF-8 BOM.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `start_date` | `query` | No | `string` | Start date (YYYY-MM-DD) |
| `end_date` | `query` | No | `string` | End date (YYYY-MM-DD) |
| `branch_id` | `query` | No | `string` | Filter by branch ID |
| `camera_id` | `query` | No | `string` | Filter by camera ID |
| `method` | `query` | No | `string` | Filter by method: FACE | PIN |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/reports/monthly-summary.csv

**Summary:** Export Monthly Summary Csv  
**Operation ID:** `export_monthly_summary_csv_api_v1_reports_monthly_summary_csv_get`  

Streams monthly attendance summary (days present, late, absent, hours) as formula-safe CSV.

#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `year` | `query` | No | `integer` | Year (YYYY) |
| `month` | `query` | No | `integer` | Month (1-12) |
| `branch_id` | `query` | No | `string` | Filter by branch ID |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/reports/summary

**Summary:** Get Reports Summary  
**Operation ID:** `get_reports_summary_api_v1_reports_summary_get`  

Returns aggregated report statistics for the current month.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `GET` /api/v1/shifts

**Summary:** List Shifts  
**Operation ID:** `list_shifts_api_v1_shifts_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/shifts

**Summary:** Create Shift  
**Operation ID:** `create_shift_api_v1_shifts_post`  
**Request Body (application/json):** `ShiftCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `DELETE` /api/v1/shifts/{shift_id}

**Summary:** Delete Shift  
**Operation ID:** `delete_shift_api_v1_shifts__shift_id__delete`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `shift_id` | `path` | Yes | `string` | - |

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /api/v1/subscription

**Summary:** Get Subscription  
**Operation ID:** `get_subscription_api_v1_subscription_get`  

What this tenant is entitled to, and how much of it is in use.

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `GET` /api/v1/users

**Summary:** List Users  
**Operation ID:** `list_users_api_v1_users_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

### `POST` /api/v1/users

**Summary:** Create User  
**Operation ID:** `create_user_api_v1_users_post`  
**Request Body (application/json):** `UserCreate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `201` | Successful Response |
| `422` | Validation Error |

---

### `PATCH` /api/v1/users/{user_id}

**Summary:** Update User  
**Operation ID:** `update_user_api_v1_users__user_id__patch`  
#### Parameters

| Name | In | Required | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `user_id` | `path` | Yes | `string` | - |

**Request Body (application/json):** `UserUpdate`  

#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |
| `422` | Validation Error |

---

### `GET` /health

**Summary:** Health  
**Operation ID:** `health_health_get`  
#### Responses

| Status Code | Description |
| :--- | :--- |
| `200` | Successful Response |

---

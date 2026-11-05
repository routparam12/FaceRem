package com.facerem.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Every backend response is wrapped: `{success, data, message}` or `{success, error}`. */
@Serializable
data class ApiEnvelope<T>(
    val success: Boolean = false,
    val data: T? = null,
    val message: String? = null,
    val error: ApiErrorBody? = null,
)

@Serializable
data class ApiErrorBody(
    val code: String = "UNKNOWN",
    val message: String = "Something went wrong.",
)

@Serializable
data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class LoginRequestDto(
    val email: String,
    val password: String,
    @SerialName("organization_slug") val organizationSlug: String? = null,
)

@Serializable
data class RefreshRequestDto(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class MeDto(
    val id: String,
    @SerialName("full_name") val fullName: String,
    val email: String,
    val role: String,
    @SerialName("organization_id") val organizationId: String? = null,
    @SerialName("organization_name") val organizationName: String? = null,
    @SerialName("employee_id") val employeeId: String? = null,
)

@Serializable
data class EmployeeDto(
    val id: String,
    @SerialName("employee_code") val employeeCode: String,
    @SerialName("full_name") val fullName: String,
    val email: String,
    val phone: String? = null,
    val department: String? = null,
    val branch: String? = null,
    @SerialName("job_title") val jobTitle: String? = null,
    val shift: String? = null,
    @SerialName("face_enrolled") val faceEnrolled: Boolean = false,
    @SerialName("is_active") val isActive: Boolean = true,
)

@Serializable
data class NewEmployeeDto(
    @SerialName("employee_code") val employeeCode: String,
    @SerialName("full_name") val fullName: String,
    val email: String,
    val phone: String? = null,
    val department: String? = null,
    val branch: String? = null,
    @SerialName("job_title") val jobTitle: String? = null,
    val shift: String? = null,
)

@Serializable
data class EnrollResponseDto(
    @SerialName("employee_id") val employeeId: String,
    @SerialName("face_enrolled") val faceEnrolled: Boolean,
    @SerialName("quality_score") val qualityScore: Float = 0f,
    @SerialName("model_name") val modelName: String = "",
)

@Serializable
data class AttendanceRecordDto(
    val id: String,
    @SerialName("employee_id") val employeeId: String,
    @SerialName("employee_name") val employeeName: String,
    val date: String,
    @SerialName("check_in_at") val checkInAt: String? = null,
    @SerialName("check_out_at") val checkOutAt: String? = null,
    val status: String,
    @SerialName("late_minutes") val lateMinutes: Int = 0,
)

@Serializable
data class RecognizeResponseDto(
    @SerialName("employee_id") val employeeId: String,
    @SerialName("employee_code") val employeeCode: String,
    @SerialName("full_name") val fullName: String,
    val department: String = "",
    val event: String,
    @SerialName("recorded_at") val recordedAt: String,
    val status: String,
    @SerialName("late_minutes") val lateMinutes: Int = 0,
    @SerialName("match_confidence") val matchConfidence: Float = 0f,
    @SerialName("liveness_score") val livenessScore: Float = 0f,
    @SerialName("check_in_at") val checkInAt: String? = null,
    @SerialName("check_out_at") val checkOutAt: String? = null,
    @SerialName("undo_token") val undoToken: String? = null,
    @SerialName("event_id") val eventId: String? = null,
    @SerialName("provisional") val provisional: Boolean = false,
)

@Serializable
data class UndoRequestDto(
    @SerialName("undo_token") val undoToken: String,
)

@Serializable
data class UndoResponseDto(
    val success: Boolean = true,
    @SerialName("event_id") val eventId: String = "",
    val message: String = "",
)

@Serializable
data class PinVerifyRequestDto(
    @SerialName("employee_code") val employeeCode: String,
    val pin: String,
)

@Serializable
data class PinVerifyResponseDto(
    @SerialName("employee_id") val employeeId: String,
    @SerialName("full_name") val fullName: String,
    @SerialName("employee_code") val employeeCode: String,
    val department: String = "",
    val event: String,
    @SerialName("recorded_at") val recordedAt: String,
    val status: String,
    @SerialName("late_minutes") val lateMinutes: Int = 0,
    @SerialName("undo_token") val undoToken: String? = null,
    @SerialName("event_id") val eventId: String? = null,
    @SerialName("check_in_at") val checkInAt: String? = null,
    @SerialName("check_out_at") val checkOutAt: String? = null,
)

@Serializable
data class DashboardDto(
    @SerialName("organization_name") val organizationName: String,
    val date: String,
    @SerialName("total_employees") val totalEmployees: Int,
    val present: Int,
    val late: Int,
    @SerialName("not_checked_in") val notCheckedIn: Int,
    @SerialName("pending_enrollments") val pendingEnrollments: Int,
)

@Serializable
data class NamedDto(val id: String, val name: String)

@Serializable
data class ChallengeResponseDto(
    @SerialName("challenge_id") val challengeId: String,
    val nonce: String,
    val actions: List<String> = emptyList(),
    @SerialName("expires_at") val expiresAt: String = "",
)

@Serializable
data class DeviceEnrollRequestDto(
    val code: String,
    val name: String? = null,
)

@Serializable
data class DeviceEnrollResponseDto(
    @SerialName("device_id") val deviceId: String,
    @SerialName("organization_id") val organizationId: String,
    val name: String,
    val mode: String,
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
)

@Serializable
data class DeviceEventRequestDto(
    @SerialName("event_type") val eventType: String,
    val details: Map<String, String>? = null,
)

@Serializable
data class DeviceEventResponseDto(
    val status: String = "recorded",
    @SerialName("event_type") val eventType: String,
)

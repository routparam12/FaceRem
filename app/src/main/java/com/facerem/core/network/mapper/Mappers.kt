package com.facerem.core.network.mapper

import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.model.Role
import com.facerem.core.model.User
import com.facerem.core.network.dto.AttendanceRecordDto
import com.facerem.core.network.dto.DashboardDto
import com.facerem.core.network.dto.EmployeeDto
import com.facerem.core.network.dto.MeDto
import com.facerem.core.network.dto.PinVerifyResponseDto
import com.facerem.core.network.dto.RecognizeResponseDto
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

private val isoDate = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
    timeZone = TimeZone.getTimeZone("UTC")
}
private val longDate = SimpleDateFormat("EEEE, d MMMM", Locale.getDefault())
private val timeFormat = SimpleDateFormat("h:mm a", Locale.getDefault())

/** Parses an ISO-8601 string into a local "9:05 AM" label. */
fun String?.toTimeLabel(): String? {
    if (this == null) return null
    return runCatching {
        // Fast paths: ISO with 'T' or a bare "HH:mm".
        if (contains("T")) {
            val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }
            iso.parse(substringBefore("."))?.let(timeFormat::format)
        } else if (contains(":")) {
            val bare = SimpleDateFormat("HH:mm", Locale.US)
            bare.parse(this)?.let(timeFormat::format)
        } else {
            null
        }
    }.getOrNull()
}

fun MeDto.toUser() = User(
    id = id,
    fullName = fullName,
    email = email,
    role = Role.fromWireValue(role),
    organizationId = organizationId.orEmpty(),
    organizationName = organizationName.orEmpty(),
)

fun EmployeeDto.toEmployee() = Employee(
    id = id,
    employeeCode = employeeCode,
    fullName = fullName,
    email = email,
    phone = phone.orEmpty(),
    department = department.orEmpty().ifBlank { "Unassigned" },
    branch = branch.orEmpty().ifBlank { "Unassigned" },
    jobTitle = jobTitle.orEmpty(),
    shiftName = shift.orEmpty().ifBlank { "Unassigned" },
    faceEnrollment = if (faceEnrolled) FaceEnrollmentStatus.ENROLLED else FaceEnrollmentStatus.PENDING,
    isActive = isActive,
)

fun AttendanceRecordDto.toRecord() = AttendanceRecord(
    id = id,
    employeeId = employeeId,
    employeeName = employeeName,
    employeeCode = "",
    department = "",
    date = date,
    checkInTime = checkInAt.toTimeLabel(),
    checkOutTime = checkOutAt.toTimeLabel(),
    status = status.toAttendanceStatus(),
    lateMinutes = lateMinutes,
)

private fun String.toAttendanceStatus(): AttendanceStatus =
    AttendanceStatus.entries.firstOrNull { it.name.equals(this, ignoreCase = true) }
        ?: AttendanceStatus.PRESENT

fun RecognizeResponseDto.toOutcome() = RecognitionOutcome.Recognized(
    employeeId = employeeId,
    employeeName = fullName,
    employeeCode = employeeCode,
    department = department,
    eventType = AttendanceEventType.entries.firstOrNull { it.name == event }
        ?: AttendanceEventType.CHECK_IN,
    timeLabel = recordedAt.toTimeLabel() ?: "",
    confidence = matchConfidence,
    status = status.toAttendanceStatus(),
    lateMinutes = lateMinutes,
    checkInLabel = checkInAt.toTimeLabel(),
    checkOutLabel = checkOutAt.toTimeLabel(),
    undoToken = undoToken,
    eventId = eventId,
)

fun PinVerifyResponseDto.toOutcome() = RecognitionOutcome.Recognized(
    employeeId = employeeId,
    employeeName = fullName,
    employeeCode = employeeCode,
    department = department,
    eventType = AttendanceEventType.entries.firstOrNull { it.name == event }
        ?: AttendanceEventType.CHECK_IN,
    timeLabel = recordedAt.toTimeLabel() ?: "",
    confidence = 1.0f,
    status = status.toAttendanceStatus(),
    lateMinutes = lateMinutes,
    checkInLabel = checkInAt.toTimeLabel(),
    checkOutLabel = checkOutAt.toTimeLabel(),
    undoToken = undoToken,
    eventId = eventId,
)

fun DashboardDto.toSummary(recent: List<AttendanceRecord>) = DashboardSummary(
    organizationName = organizationName,
    dateLabel = runCatching { isoDate.parse(date)?.let(longDate::format) }.getOrNull() ?: date,
    totalEmployees = totalEmployees,
    presentCount = present,
    lateCount = late,
    absentCount = notCheckedIn,
    onLeaveCount = 0,
    pendingEnrollments = pendingEnrollments,
    weeklyAttendanceRate = emptyList(),
    recentActivity = recent,
)

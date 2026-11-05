package com.facerem.core.model

data class AttendanceRecord(
    val id: String,
    val employeeId: String,
    val employeeName: String,
    val employeeCode: String,
    val department: String,
    /** ISO-8601 local date, e.g. 2026-09-13. */
    val date: String,
    val checkInTime: String?,
    val checkOutTime: String?,
    val status: AttendanceStatus,
    val lateMinutes: Int = 0,
    val overtimeMinutes: Int = 0,
    val workedMinutes: Int = 0,
    val capturedBy: String = "Face scan",
)

enum class AttendanceStatus(val displayName: String) {
    PRESENT("Present"),
    LATE("Late"),
    ABSENT("Absent"),
    ON_LEAVE("On leave"),
    HALF_DAY("Half day"),
}

enum class AttendanceEventType(val displayName: String) {
    CHECK_IN("Checked in"),
    CHECK_OUT("Checked out"),

    /**
     * The day was already recorded, so the scan changed nothing. An unattended gate sees the
     * same faces many times a day; this is the normal answer, not a failure.
     */
    ALREADY_PRESENT("Already present"),
    ;

    /** True when the scan wrote an attendance event rather than just reporting one. */
    val isNewEvent: Boolean get() = this != ALREADY_PRESENT
}

/** Outcome of a server-side recognition attempt. */
sealed interface RecognitionOutcome {
    data class Recognized(
        val employeeId: String,
        val employeeName: String,
        val employeeCode: String,
        val department: String,
        val eventType: AttendanceEventType,
        val timeLabel: String,
        val confidence: Float,
        val status: AttendanceStatus,
        val lateMinutes: Int,
        /** The day's timestamps, so a repeat scan can say "in since 09:05". */
        val checkInLabel: String? = null,
        val checkOutLabel: String? = null,
        val undoToken: String? = null,
        val eventId: String? = null,
    ) : RecognitionOutcome

    /** Never expose near matches for an unrecognised face. */
    data class NotRecognized(val message: String) : RecognitionOutcome

    data class Rejected(val code: String, val message: String) : RecognitionOutcome
}

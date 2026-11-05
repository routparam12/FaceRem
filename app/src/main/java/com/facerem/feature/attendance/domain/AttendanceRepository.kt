package com.facerem.feature.attendance.domain

import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.LivenessChallenge
import com.facerem.core.model.RecognitionOutcome

interface AttendanceRepository {
    /** Maps to `POST /api/v1/attendance/challenge`. */
    suspend fun requestChallenge(): AppResult<LivenessChallenge>

    /**
     * Maps to `POST /api/v1/attendance/recognize`. Identity is decided by the server against the
     * caller's organization only; the client never matches embeddings itself.
     */
    suspend fun recognize(
        image: ByteArray,
        challengeId: String? = null,
        nonce: String? = null,
        burstFrames: List<ByteArray> = emptyList(),
        deviceLabel: String = "android-kiosk",
    ): AppResult<RecognitionOutcome>

    /**
     * Maps to `POST /api/v1/attendance/undo`. Voids the last recorded attendance event inside the 30-second window.
     */
    suspend fun undo(undoToken: String): AppResult<String>

    /**
     * Maps to `POST /api/v1/attendance/pin-verify`. PIN fallback recording attendance for the employee.
     */
    suspend fun verifyPin(employeeCode: String, pin: String): AppResult<RecognitionOutcome>

    suspend fun history(): AppResult<List<AttendanceRecord>>
}

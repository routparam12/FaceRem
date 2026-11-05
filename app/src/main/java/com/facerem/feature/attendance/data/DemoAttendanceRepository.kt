package com.facerem.feature.attendance.data

import com.facerem.core.common.AppResult
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.LivenessChallenge
import com.facerem.core.model.RecognitionOutcome
import com.facerem.feature.attendance.domain.AttendanceRepository
import javax.inject.Inject
import kotlinx.coroutines.delay

class DemoAttendanceRepository @Inject constructor(
    private val demoDataStore: DemoDataStore,
) : AttendanceRepository {

    override suspend fun requestChallenge(): AppResult<LivenessChallenge> {
        delay(150)
        return AppResult.Success(
            LivenessChallenge(
                challengeId = "demo-chal-${System.currentTimeMillis()}",
                nonce = "demo-nonce",
                actions = listOf("BLINK"),
            ),
        )
    }

    override suspend fun recognize(
        image: ByteArray,
        challengeId: String?,
        nonce: String?,
        burstFrames: List<ByteArray>,
        deviceLabel: String,
    ): AppResult<RecognitionOutcome> {
        // The demo never looks at the frame; it picks a plausible employee instead.
        delay(1_400)
        return AppResult.Success(demoDataStore.simulateRecognition())
    }

    override suspend fun undo(undoToken: String): AppResult<String> {
        delay(200)
        return AppResult.Success("undone")
    }

    override suspend fun verifyPin(employeeCode: String, pin: String): AppResult<RecognitionOutcome> {
        delay(500)
        return AppResult.Success(demoDataStore.simulateRecognition())
    }

    override suspend fun history(): AppResult<List<AttendanceRecord>> {
        delay(400)
        return AppResult.Success(
            demoDataStore.attendance.value.sortedWith(
                compareByDescending<AttendanceRecord> { it.date }.thenBy { it.employeeName },
            ),
        )
    }
}

package com.facerem.feature.attendance

import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.LivenessChallenge
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.session.SessionManager
import com.facerem.feature.attendance.domain.AttendanceRepository
import com.facerem.feature.attendance.presentation.ScanPhase
import com.facerem.feature.attendance.presentation.ScanTiming
import com.facerem.feature.attendance.presentation.ScanViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ScanViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val fakeRepository = FakeAttendanceRepository()
    private val sessionManager = SessionManager(preferences = null, guestFlow = flowOf(false))

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel(kioskMode: Boolean = false): ScanViewModel {
        val vm = ScanViewModel(fakeRepository, sessionManager)
        vm.setKioskMode(kioskMode)
        return vm
    }

    private fun feedHeldFace(
        viewModel: ScanViewModel,
        captureMock: suspend () -> ByteArray?,
        count: Int = ScanTiming.REQUIRED_STABLE_FRAMES,
    ) {
        repeat(count) {
            viewModel.onQuality(FaceQualityStatus.VALID, captureMock)
        }
    }

    @Test
    fun `challenge requested and burst sent on face hold`() = runTest(testDispatcher) {
        val viewModel = createViewModel(kioskMode = false)
        val dummyFrame = byteArrayOf(0x01, 0x02, 0x03, 0x04)
        var captureCount = 0
        val captureMock: suspend () -> ByteArray? = {
            captureCount++
            dummyFrame
        }

        feedHeldFace(viewModel, captureMock)
        advanceUntilIdle()

        // 1. Challenge was requested from backend
        assertEquals(1, fakeRepository.requestChallengeCallCount)

        // 2. Frames were captured: 1 primary + 2 burst frames = 3 captures
        assertEquals(3, captureCount)

        // 3. Recognize endpoint was called with challengeId, nonce, burstFrames
        assertEquals(1, fakeRepository.recognizeCallCount)
        assertEquals("chal-test-uuid", fakeRepository.lastChallengeId)
        assertEquals("nonce-test-hex", fakeRepository.lastNonce)
        assertEquals(2, fakeRepository.lastBurstFrames.size)

        // 4. Successful result is displayed
        val state = viewModel.uiState.value
        assertEquals(ScanPhase.RESULT, state.phase)
        assertNotNull(state.outcome)
        val recognized = state.outcome as? RecognitionOutcome.Recognized
        assertNotNull(recognized)
        assertEquals("Alice Walker", recognized?.employeeName)
        assertNull(state.errorMessage)
    }

    @Test
    fun `challenge prompt displays expected guidance text for active challenges`() = runTest(testDispatcher) {
        val dummyFrame = byteArrayOf(0x01, 0x02, 0x03)
        val captureMock: suspend () -> ByteArray? = { dummyFrame }

        // Test BLINK action
        fakeRepository.challengeToReturn = AppResult.Success(
            LivenessChallenge("c1", "n1", listOf("BLINK"))
        )
        val vm1 = createViewModel(kioskMode = false)
        feedHeldFace(vm1, captureMock)
        advanceTimeBy(10)
        assertEquals("Please blink", vm1.uiState.value.challengePrompt)
        advanceUntilIdle()

        // Test TURN_LEFT action
        fakeRepository.challengeToReturn = AppResult.Success(
            LivenessChallenge("c2", "n2", listOf("TURN_LEFT"))
        )
        val vm2 = createViewModel(kioskMode = false)
        feedHeldFace(vm2, captureMock)
        advanceTimeBy(10)
        assertEquals("Turn slightly left", vm2.uiState.value.challengePrompt)
        advanceUntilIdle()

        // Test TURN_RIGHT action
        fakeRepository.challengeToReturn = AppResult.Success(
            LivenessChallenge("c3", "n3", listOf("TURN_RIGHT"))
        )
        val vm3 = createViewModel(kioskMode = false)
        feedHeldFace(vm3, captureMock)
        advanceTimeBy(10)
        assertEquals("Turn slightly right", vm3.uiState.value.challengePrompt)
        advanceUntilIdle()
    }

    @Test
    fun `LIVENESS_FAILED is mapped to rejection UI state and error message`() = runTest(testDispatcher) {
        fakeRepository.recognizeResultToReturn = AppResult.Error(
            AppError.Api(
                code = "LIVENESS_FAILED",
                userMessage = "Liveness check failed. Please blink or turn as instructed.",
            )
        )

        val viewModel = createViewModel(kioskMode = false)
        val dummyFrame = byteArrayOf(0x01, 0x02, 0x03)
        val captureMock: suspend () -> ByteArray? = { dummyFrame }

        feedHeldFace(viewModel, captureMock)
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(ScanPhase.RESULT, state.phase)
        assertNull("Outcome must be null on liveness failure", state.outcome)
        assertEquals("Liveness check failed. Please blink or turn as instructed.", state.errorMessage)
    }

    @Test
    fun `FACE_NOT_RECOGNIZED is mapped to not-recognized UI state`() = runTest(testDispatcher) {
        fakeRepository.recognizeResultToReturn = AppResult.Error(
            AppError.Api(
                code = "FACE_NOT_RECOGNIZED",
                userMessage = "Face could not be recognized.",
            )
        )

        val viewModel = createViewModel(kioskMode = false)
        val dummyFrame = byteArrayOf(0x01, 0x02, 0x03)
        val captureMock: suspend () -> ByteArray? = { dummyFrame }

        feedHeldFace(viewModel, captureMock)
        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(ScanPhase.RESULT, state.phase)
        assertNull("Outcome must be null when face is unrecognized", state.outcome)
        assertEquals("Face could not be recognized.", state.errorMessage)
    }

    @Test
    fun `absence of client-attested liveness score in recognize request`() = runTest(testDispatcher) {
        val viewModel = createViewModel(kioskMode = false)
        val dummyFrame = byteArrayOf(0x01, 0x02, 0x03)
        val captureMock: suspend () -> ByteArray? = { dummyFrame }

        feedHeldFace(viewModel, captureMock)
        advanceUntilIdle()

        // Verify that the repository received ONLY the biometric raw frame data and challenge nonces
        // No client-side liveness score, boolean, or verdict is transmitted.
        assertNotNull(fakeRepository.lastCapturedImage)
        assertEquals("chal-test-uuid", fakeRepository.lastChallengeId)
        assertEquals("nonce-test-hex", fakeRepository.lastNonce)
        assertEquals(2, fakeRepository.lastBurstFrames.size)
        assertEquals("android-kiosk", fakeRepository.lastDeviceLabel)
    }
}

class FakeAttendanceRepository : AttendanceRepository {
    var challengeToReturn: AppResult<LivenessChallenge> = AppResult.Success(
        LivenessChallenge(
            challengeId = "chal-test-uuid",
            nonce = "nonce-test-hex",
            actions = listOf("BLINK"),
        )
    )

    var recognizeResultToReturn: AppResult<RecognitionOutcome> = AppResult.Success(
        RecognitionOutcome.Recognized(
            employeeId = "emp-uuid-1",
            employeeName = "Alice Walker",
            employeeCode = "EMP001",
            department = "Engineering",
            eventType = AttendanceEventType.CHECK_IN,
            timeLabel = "10:00 AM",
            confidence = 0.95f,
            status = AttendanceStatus.PRESENT,
            lateMinutes = 0,
        )
    )

    var requestChallengeCallCount = 0
    var recognizeCallCount = 0
    var lastCapturedImage: ByteArray? = null
    var lastChallengeId: String? = null
    var lastNonce: String? = null
    var lastBurstFrames: List<ByteArray> = emptyList()
    var lastDeviceLabel: String? = null

    override suspend fun requestChallenge(): AppResult<LivenessChallenge> {
        requestChallengeCallCount++
        return challengeToReturn
    }

    override suspend fun recognize(
        image: ByteArray,
        challengeId: String?,
        nonce: String?,
        burstFrames: List<ByteArray>,
        deviceLabel: String,
    ): AppResult<RecognitionOutcome> {
        recognizeCallCount++
        lastCapturedImage = image
        lastChallengeId = challengeId
        lastNonce = nonce
        lastBurstFrames = burstFrames
        lastDeviceLabel = deviceLabel
        return recognizeResultToReturn
    }

    override suspend fun history(): AppResult<List<AttendanceRecord>> {
        return AppResult.Success(emptyList())
    }
}

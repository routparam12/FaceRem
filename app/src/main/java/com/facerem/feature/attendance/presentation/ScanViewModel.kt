package com.facerem.feature.attendance.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.common.AppResult
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.session.SessionManager
import com.facerem.feature.attendance.domain.AttendanceRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class ScanPhase {
    /** Watching for a face. */
    SCANNING,

    /** A frame has been sent; the server is deciding who this is. */
    VERIFYING,

    /** Showing the outcome. In kiosk mode this clears itself. */
    RESULT,
}

data class ScanUiState(
    val phase: ScanPhase = ScanPhase.SCANNING,
    val quality: FaceQualityStatus = FaceQualityStatus.NO_FACE,
    val stableFrames: Int = 0,
    val challengePrompt: String? = null,
    val outcome: RecognitionOutcome? = null,
    val isGuest: Boolean = false,
    val errorMessage: String? = null,
    /** Unattended mode: no buttons, results clear themselves, the screen stays awake. */
    val kioskMode: Boolean = true,
    /** After a result, the frame must empty before the next person can be scanned. */
    val awaitingFaceClear: Boolean = false,
    val scanCount: Int = 0,
) {
    /**
     * The preview is never torn down. Rebinding CameraX costs about a second, which at a gate
     * means the next person is already walking past before the camera is ready.
     */
    val isCameraActive: Boolean get() = true

    val isBusy: Boolean get() = phase == ScanPhase.VERIFYING

    /** In kiosk mode the loop drives itself, so there is nothing for a person to press. */
    val showsManualControls: Boolean get() = !kioskMode

    val guidance: String
        get() = when {
            phase == ScanPhase.VERIFYING -> challengePrompt ?: "Verifying…"
            phase == ScanPhase.RESULT -> ""
            awaitingFaceClear -> "Next person, please step up"
            else -> quality.guidance
        }
}

/**
 * Drives the scanner.
 *
 * Kiosk mode is the default because the common deployment is a tablet bolted next to a door:
 * someone walks up, is recognised, sees the result, and walks off without touching anything.
 * Three things make that work — the camera stays bound, the result clears itself, and the frame
 * must empty before the next scan arms, so one person standing still is not scanned on a loop.
 */
@HiltViewModel
class ScanViewModel @Inject constructor(
    private val attendanceRepository: AttendanceRepository,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(ScanUiState())
    val uiState = mutableUiState.asStateFlow()

    private var resultJob: Job? = null

    init {
        viewModelScope.launch {
            sessionManager.isGuest.collect { guest -> mutableUiState.update { it.copy(isGuest = guest) } }
        }
    }

    fun setKioskMode(enabled: Boolean) {
        mutableUiState.update { it.copy(kioskMode = enabled) }
        // Leaving kiosk mode mid-result should not strand the operator on a frozen card.
        if (!enabled && mutableUiState.value.phase == ScanPhase.RESULT) return
        if (enabled) armNextScan()
    }

    /**
     * @param captureFrame grabs a still from the live preview. Supplied by the screen so the
     *   ViewModel stays free of CameraX, and so guest mode can run without a camera at all.
     */
    fun onQuality(status: FaceQualityStatus, captureFrame: suspend () -> ByteArray?) {
        val transition = mutableUiState.value.onQualityFrame(status)
        mutableUiState.value = transition.state
        if (transition.shouldRecognize) recognize(captureFrame)
    }

    /** Manual mode only: dismiss the current result and watch for the next face. */
    fun scanAgain() = armNextScan()

    private fun recognize(captureFrame: suspend () -> ByteArray?) {
        viewModelScope.launch {
            val challengeResult = attendanceRepository.requestChallenge()
            val (challengeId, nonce, actions) = when (challengeResult) {
                is AppResult.Success -> Triple(
                    challengeResult.data.challengeId,
                    challengeResult.data.nonce,
                    challengeResult.data.actions,
                )
                else -> Triple(null, null, emptyList())
            }

            val prompt = actions.firstOrNull()?.let { action ->
                when (action) {
                    "BLINK" -> "Please blink"
                    "TURN_LEFT" -> "Turn slightly left"
                    "TURN_RIGHT" -> "Turn slightly right"
                    else -> "Verifying…"
                }
            } ?: "Verifying…"
            mutableUiState.update { it.copy(challengePrompt = prompt) }

            val frame = captureFrame()
            if (frame == null || frame.isEmpty()) {
                showResult(errorMessage = "The camera could not take a picture. Try again.")
                return@launch
            }

            val burstFrames = mutableListOf<ByteArray>()
            if (challengeId != null && nonce != null) {
                repeat(2) {
                    delay(80)
                    captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }
                }
            }

            when (
                val result = attendanceRepository.recognize(
                    image = frame,
                    challengeId = challengeId,
                    nonce = nonce,
                    burstFrames = burstFrames,
                    deviceLabel = DEVICE_LABEL,
                )
            ) {
                is AppResult.Success -> showResult(outcome = result.data)
                is AppResult.Error -> showResult(errorMessage = result.error.userMessage)
                AppResult.Loading -> Unit
            }
        }
    }

    private fun showResult(
        outcome: RecognitionOutcome? = null,
        errorMessage: String? = null,
    ) {
        mutableUiState.update {
            it.copy(
                phase = ScanPhase.RESULT,
                outcome = outcome,
                errorMessage = errorMessage,
                challengePrompt = null,
                scanCount = if (outcome != null) it.scanCount + 1 else it.scanCount,
            )
        }

        if (!mutableUiState.value.kioskMode) return

        resultJob?.cancel()
        resultJob = viewModelScope.launch {
            delay(resultHoldMillis(outcome, errorMessage))
            armNextScan()
        }
    }

    private fun armNextScan() {
        resultJob?.cancel()
        mutableUiState.update { it.armedForNextScan().copy(challengePrompt = null) }
    }

    private companion object {
        const val DEVICE_LABEL = "android-kiosk"
    }
}

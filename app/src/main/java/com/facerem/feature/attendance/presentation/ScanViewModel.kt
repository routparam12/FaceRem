package com.facerem.feature.attendance.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.camera.FaceCaptureObservation
import com.facerem.core.camera.FaceCaptureSource
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
    val activeUndoToken: String? = null,
    val undoSecondsRemaining: Int = 0,
    val undoMessage: String? = null,
    val showPinDialog: Boolean = false,
    val pinEmployeeCode: String = "",
    val pinCode: String = "",
    val pinError: String? = null,
    val pinIsSubmitting: Boolean = false,
) {
    val isCameraActive: Boolean get() = true
    val isBusy: Boolean get() = phase == ScanPhase.VERIFYING
    val showsManualControls: Boolean get() = !kioskMode
    val canUndo: Boolean get() = activeUndoToken != null && undoSecondsRemaining > 0

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
    private var undoJob: Job? = null

    init {
        viewModelScope.launch {
            sessionManager.isGuest.collect { guest -> mutableUiState.update { it.copy(isGuest = guest) } }
        }
    }

    fun setKioskMode(enabled: Boolean) {
        mutableUiState.update { it.copy(kioskMode = enabled) }
        if (!enabled && mutableUiState.value.phase == ScanPhase.RESULT) return
        if (enabled) armNextScan()
    }

    /**
     * Optional connection to a decoupled [FaceCaptureSource].
     */
    fun observeCaptureSource(source: FaceCaptureSource) {
        viewModelScope.launch {
            source.observations.collect { obs ->
                if (mutableUiState.value.phase == ScanPhase.SCANNING && !mutableUiState.value.awaitingFaceClear) {
                    processObservation(obs)
                }
            }
        }
    }

    fun processObservation(observation: FaceCaptureObservation) {
        viewModelScope.launch {
            mutableUiState.update { it.copy(phase = ScanPhase.VERIFYING, challengePrompt = "Verifying…") }

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

            when (
                val result = attendanceRepository.recognize(
                    image = observation.primaryImageJpeg,
                    challengeId = challengeId,
                    nonce = nonce,
                    burstFrames = observation.burstFramesJpeg,
                    deviceLabel = DEVICE_LABEL,
                )
            ) {
                is AppResult.Success -> {
                    val outcome = result.data
                    showResult(outcome = outcome)
                    if (outcome is RecognitionOutcome.Recognized && outcome.undoToken != null && outcome.eventType.isNewEvent) {
                        startUndoCountdown(outcome.undoToken)
                    }
                }
                is AppResult.Error -> showResult(errorMessage = result.error.userMessage)
                AppResult.Loading -> Unit
            }
        }
    }

    /**
     * Feeds camera analyzer verdicts into the scanner.
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
                is AppResult.Success -> {
                    val outcome = result.data
                    showResult(outcome = outcome)
                    if (outcome is RecognitionOutcome.Recognized && outcome.undoToken != null && outcome.eventType.isNewEvent) {
                        startUndoCountdown(outcome.undoToken)
                    }
                }
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

    // -------------------------------------------------------------------------
    // Undo 30-second Countdown & Action
    // -------------------------------------------------------------------------

    fun startUndoCountdown(token: String) {
        undoJob?.cancel()
        mutableUiState.update {
            it.copy(
                activeUndoToken = token,
                undoSecondsRemaining = 30,
                undoMessage = null,
            )
        }
        undoJob = viewModelScope.launch {
            for (second in 29 downTo 0) {
                delay(1000L)
                mutableUiState.update { it.copy(undoSecondsRemaining = second) }
            }
            mutableUiState.update { it.copy(activeUndoToken = null, undoSecondsRemaining = 0) }
        }
    }

    fun undo() {
        val token = mutableUiState.value.activeUndoToken ?: return
        viewModelScope.launch {
            undoJob?.cancel()
            mutableUiState.update { it.copy(activeUndoToken = null, undoSecondsRemaining = 0) }
            when (val res = attendanceRepository.undo(token)) {
                is AppResult.Success -> {
                    mutableUiState.update { it.copy(undoMessage = "Attendance event successfully undone.") }
                }
                is AppResult.Error -> {
                    mutableUiState.update { it.copy(errorMessage = res.error.userMessage) }
                }
                AppResult.Loading -> Unit
            }
        }
    }

    // -------------------------------------------------------------------------
    // PIN Fallback Flow
    // -------------------------------------------------------------------------

    fun openPinDialog() {
        mutableUiState.update {
            it.copy(
                showPinDialog = true,
                pinEmployeeCode = "",
                pinCode = "",
                pinError = null,
                pinIsSubmitting = false,
            )
        }
    }

    fun dismissPinDialog() {
        mutableUiState.update {
            it.copy(
                showPinDialog = false,
                pinEmployeeCode = "",
                pinCode = "",
                pinError = null,
                pinIsSubmitting = false,
            )
        }
    }

    fun onPinEmployeeCodeChange(code: String) {
        mutableUiState.update { it.copy(pinEmployeeCode = code.uppercase().trim(), pinError = null) }
    }

    fun onPinCodeChange(pin: String) {
        if (pin.length <= 8 && pin.all { it.isDigit() }) {
            mutableUiState.update { it.copy(pinCode = pin, pinError = null) }
        }
    }

    fun submitPin() {
        val code = mutableUiState.value.pinEmployeeCode
        val pin = mutableUiState.value.pinCode
        if (code.isBlank() || pin.isBlank()) {
            mutableUiState.update { it.copy(pinError = "Enter both employee code and PIN.") }
            return
        }

        viewModelScope.launch {
            mutableUiState.update { it.copy(pinIsSubmitting = true, pinError = null) }
            when (val res = attendanceRepository.verifyPin(code, pin)) {
                is AppResult.Success -> {
                    mutableUiState.update { it.copy(showPinDialog = false, pinIsSubmitting = false) }
                    val outcome = res.data
                    showResult(outcome = outcome)
                    if (outcome is RecognitionOutcome.Recognized && outcome.undoToken != null && outcome.eventType.isNewEvent) {
                        startUndoCountdown(outcome.undoToken)
                    }
                }
                is AppResult.Error -> {
                    mutableUiState.update {
                        it.copy(
                            pinIsSubmitting = false,
                            pinError = res.error.userMessage,
                        )
                    }
                }
                AppResult.Loading -> Unit
            }
        }
    }

    private companion object {
        const val DEVICE_LABEL = "android-kiosk"
    }
}

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
import com.google.mlkit.vision.face.Face
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
    /** Tracked face overlays displayed over the camera preview. */
    val trackedFaces: List<TrackedFaceUiModel> = emptyList(),
    val primaryTrackId: Int? = null,
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
 * Drives the kiosk scanner and multi-face track overlay lifecycle.
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

    // Tracking state: prevents re-submitting until face leaves
    private val submittedTrackIds = mutableSetOf<Int>()
    private val trackOutcomes = mutableMapOf<Int, RecognitionOutcome>()
    private val trackLastSeenMs = mutableMapOf<Int, Long>()
    @Volatile private var latestPrimaryFace: Face? = null

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
        val trackId = observation.trackId ?: 0
        if (submittedTrackIds.contains(trackId)) return
        submittedTrackIds.add(trackId)

        viewModelScope.launch {
            mutableUiState.update { it.copy(phase = ScanPhase.VERIFYING, challengePrompt = "Verifying…", primaryTrackId = trackId) }

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
                    showResult(outcome = outcome, primaryTrackId = trackId)
                    if (outcome is RecognitionOutcome.Recognized && outcome.undoToken != null && outcome.eventType.isNewEvent) {
                        startUndoCountdown(outcome.undoToken)
                    }
                }
                is AppResult.Error -> showResult(errorMessage = result.error.userMessage, primaryTrackId = trackId)
                AppResult.Loading -> Unit
            }
        }
    }

    /**
     * Ingests detected faces from CameraX ML Kit analysis, computes view-referenced bounding boxes,
     * isolates the largest closest face for server evaluation, and maintains track overlays.
     */
    fun onFacesDetected(
        faces: List<Face>,
        imageWidth: Int,
        imageHeight: Int,
        viewWidth: Float,
        viewHeight: Float,
        captureFrame: suspend () -> ByteArray?,
    ) {
        val now = System.currentTimeMillis()
        val currentUi = mutableUiState.value

        // Largest closest face in the frame is primary
        val primaryFace = if (faces.isNotEmpty()) {
            faces.maxByOrNull { it.boundingBox.width() * it.boundingBox.height() }
        } else null
        val primaryTrackId = primaryFace?.trackingId ?: primaryFace?.hashCode()
        latestPrimaryFace = primaryFace

        // Update last seen timestamps
        faces.forEach { face ->
            val trackId = face.trackingId ?: face.hashCode()
            trackLastSeenMs[trackId] = now
        }

        // Clean up tracks that departed more than TRACK_FADE_OUT_MILLIS (~1s) ago
        val iterator = trackLastSeenMs.iterator()
        while (iterator.hasNext()) {
            val (tId, lastSeen) = iterator.next()
            if (now - lastSeen > ScanOverlayConfig.TRACK_FADE_OUT_MILLIS) {
                iterator.remove()
                submittedTrackIds.remove(tId)
                trackOutcomes.remove(tId)
            }
        }

        // Build UI models for active/leaving tracks
        val presentTrackIds = faces.map { it.trackingId ?: it.hashCode() }.toSet()
        val allTrackIds = trackLastSeenMs.keys

        val updatedTracks = allTrackIds.mapNotNull { trackId ->
            val isPresent = presentTrackIds.contains(trackId)
            val face = faces.firstOrNull { (it.trackingId ?: it.hashCode()) == trackId }
            val isPrimary = (trackId == primaryTrackId)

            val bounds = if (face != null) {
                mapFaceBoundsToView(
                    faceRect = face.boundingBox,
                    imageWidth = imageWidth,
                    imageHeight = imageHeight,
                    viewWidth = viewWidth,
                    viewHeight = viewHeight,
                    isFrontCamera = true,
                )
            } else {
                currentUi.trackedFaces.firstOrNull { it.trackId == trackId }?.bounds ?: return@mapNotNull null
            }

            val outcome = trackOutcomes[trackId] ?: if (isPrimary) currentUi.outcome else null
            val overlayState = mapToTrackOverlayState(
                serverOutcome = outcome,
                isPrimary = isPrimary,
                challengePrompt = if (isPrimary) currentUi.challengePrompt else null,
                clientQuality = if (isPrimary) currentUi.quality else null,
            )

            TrackedFaceUiModel(
                trackId = trackId,
                bounds = bounds,
                isPrimary = isPrimary,
                state = overlayState,
                lastSeenTimestampMs = trackLastSeenMs[trackId] ?: now,
                isLeaving = !isPresent,
            )
        }

        mutableUiState.update {
            it.copy(
                trackedFaces = updatedTracks,
                primaryTrackId = primaryTrackId,
            )
        }

        // Dispatch server recognition only for the primary face if it hasn't been submitted
        if (primaryFace != null && primaryTrackId != null &&
            currentUi.phase == ScanPhase.SCANNING &&
            !currentUi.awaitingFaceClear &&
            !submittedTrackIds.contains(primaryTrackId)
        ) {
            submittedTrackIds.add(primaryTrackId)
            recognize(captureFrame, primaryTrackId)
        }
    }

    /**
     * Feeds camera analyzer verdicts into the scanner.
     */
    fun onQuality(status: FaceQualityStatus, captureFrame: suspend () -> ByteArray?) {
        if (status == FaceQualityStatus.NO_FACE) {
            submittedTrackIds.clear()
        }
        val transition = mutableUiState.value.onQualityFrame(status)
        mutableUiState.value = transition.state
        if (transition.shouldRecognize) {
            val primaryId = mutableUiState.value.primaryTrackId ?: 0
            if (!submittedTrackIds.contains(primaryId)) {
                submittedTrackIds.add(primaryId)
                recognize(captureFrame, primaryId)
            }
        }
    }

    /** Manual mode only: dismiss the current result and watch for the next face. */
    fun scanAgain() {
        submittedTrackIds.clear()
        armNextScan()
    }

    private fun recognize(captureFrame: suspend () -> ByteArray?, trackId: Int) {
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
            mutableUiState.update { it.copy(challengePrompt = prompt, phase = ScanPhase.VERIFYING, primaryTrackId = trackId) }

            val frame = captureFrame()
            if (frame == null || frame.isEmpty()) {
                showResult(errorMessage = "The camera could not take a picture. Try again.", primaryTrackId = trackId)
                return@launch
            }

            val burstFrames = mutableListOf<ByteArray>()
            if (challengeId != null && nonce != null) {
                val action = actions.firstOrNull()
                if (action == "BLINK") {
                    val blinkStart = System.currentTimeMillis()
                    while (System.currentTimeMillis() - blinkStart < 1800) {
                        val face = latestPrimaryFace
                        val left = face?.leftEyeOpenProbability ?: 1f
                        val right = face?.rightEyeOpenProbability ?: 1f
                        if (minOf(left, right) < 0.35f) {
                            break
                        }
                        delay(40)
                    }
                    captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }

                    val reopenStart = System.currentTimeMillis()
                    while (System.currentTimeMillis() - reopenStart < 800) {
                        val face = latestPrimaryFace
                        val left = face?.leftEyeOpenProbability ?: 0f
                        val right = face?.rightEyeOpenProbability ?: 0f
                        if (minOf(left, right) > 0.60f) {
                            break
                        }
                        delay(40)
                    }
                    captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }
                } else if (action == "TURN_LEFT" || action == "TURN_RIGHT") {
                    val targetYaw = if (action == "TURN_LEFT") 12f else -12f
                    val turnStart = System.currentTimeMillis()
                    while (System.currentTimeMillis() - turnStart < 1800) {
                        val face = latestPrimaryFace
                        val yaw = face?.headEulerAngleY ?: 0f
                        if (if (action == "TURN_LEFT") yaw >= targetYaw else yaw <= targetYaw) {
                            break
                        }
                        delay(40)
                    }
                    captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }
                    delay(120)
                    captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }
                } else {
                    repeat(2) {
                        delay(80)
                        captureFrame()?.let { if (it.isNotEmpty()) burstFrames.add(it) }
                    }
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
                    showResult(outcome = outcome, primaryTrackId = trackId)
                    if (outcome is RecognitionOutcome.Recognized && outcome.undoToken != null && outcome.eventType.isNewEvent) {
                        startUndoCountdown(outcome.undoToken)
                    }
                }
                is AppResult.Error -> showResult(errorMessage = result.error.userMessage, primaryTrackId = trackId)
                AppResult.Loading -> Unit
            }
        }
    }

    private fun showResult(
        outcome: RecognitionOutcome? = null,
        errorMessage: String? = null,
        primaryTrackId: Int? = null,
    ) {
        if (primaryTrackId != null && outcome != null) {
            trackOutcomes[primaryTrackId] = outcome
        }

        mutableUiState.update {
            it.copy(
                phase = ScanPhase.RESULT,
                outcome = outcome,
                errorMessage = errorMessage,
                challengePrompt = null,
                scanCount = if (outcome != null) it.scanCount + 1 else it.scanCount,
                trackedFaces = it.trackedFaces.map { track ->
                    if (track.trackId == primaryTrackId) {
                        track.copy(
                            state = mapToTrackOverlayState(
                                serverOutcome = outcome,
                                isPrimary = true,
                                challengePrompt = null,
                                clientQuality = it.quality,
                            ),
                        )
                    } else track
                },
            )
        }

        if (!mutableUiState.value.kioskMode) return

        resultJob?.cancel()
        resultJob = viewModelScope.launch {
            // Hold result on screen for ~3 seconds, then return to scanning
            delay(ScanOverlayConfig.RESULT_HOLD_MILLIS)
            armNextScan()
        }
    }

    private fun armNextScan() {
        resultJob?.cancel()
        mutableUiState.update {
            it.armedForNextScan().copy(
                challengePrompt = null,
                primaryTrackId = null,
            )
        }
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

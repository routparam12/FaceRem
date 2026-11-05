package com.facerem.feature.faceenrollment.presentation

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.app.navigation.AppRoute
import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.common.AppResult
import com.facerem.core.model.Employee
import com.facerem.feature.employees.domain.EmployeeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Enrollment captures three views so the backend can build a robust embedding set. */
val ENROLLMENT_POSES = listOf(
    FaceQualityEvaluator.HeadPose.FRONT,
    FaceQualityEvaluator.HeadPose.SLIGHT_LEFT,
    FaceQualityEvaluator.HeadPose.SLIGHT_RIGHT,
)

data class FaceEnrollmentUiState(
    val employee: Employee? = null,
    val consentGiven: Boolean = false,
    val capturedPoses: Int = 0,
    val capturedFrames: Map<FaceQualityEvaluator.HeadPose, ByteArray> = emptyMap(),
    val quality: FaceQualityStatus = FaceQualityStatus.NO_FACE,
    val stableFrames: Int = 0,
    val isSubmitting: Boolean = false,
    val isComplete: Boolean = false,
    val errorMessage: String? = null,
) {
    val currentPose: FaceQualityEvaluator.HeadPose
        get() = ENROLLMENT_POSES[capturedPoses.coerceAtMost(ENROLLMENT_POSES.lastIndex)]

    val allPosesCaptured: Boolean
        get() = capturedPoses >= ENROLLMENT_POSES.size && capturedFrames.size >= ENROLLMENT_POSES.size

    val progress: Float get() = capturedPoses.toFloat() / ENROLLMENT_POSES.size

    /**
     * Preview and camera controller remain bound throughout enrollment and retry.
     * Released only when enrollment is successfully complete.
     */
    val isCameraActive: Boolean get() = !isComplete
}

@HiltViewModel
class FaceEnrollmentViewModel @Inject constructor(
    private val employeeRepository: EmployeeRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val employeeId: String = checkNotNull(savedStateHandle[AppRoute.EmployeeIdArg])

    private val mutableUiState = MutableStateFlow(FaceEnrollmentUiState())
    val uiState = mutableUiState.asStateFlow()

    @Volatile
    private var isCapturingPose: Boolean = false

    init {
        viewModelScope.launch {
            val result = employeeRepository.employee(employeeId)
            if (result is AppResult.Success) {
                mutableUiState.update { it.copy(employee = result.data) }
            }
        }
    }

    fun onConsentChange(granted: Boolean) {
        mutableUiState.update { it.copy(consentGiven = granted) }
    }

    /**
     * A pose is accepted only after the quality verdict stays valid across consecutive frames,
     * which filters out single lucky frames during motion. The frame is captured only upon
     * reaching the required threshold and stored in [FaceEnrollmentUiState.capturedFrames].
     */
    fun onQuality(
        status: FaceQualityStatus,
        captureFrame: suspend () -> ByteArray?,
        requiredStableFrames: Int = REQUIRED_STABLE_FRAMES,
    ) {
        val state = mutableUiState.value
        if (state.allPosesCaptured || state.isSubmitting || !state.consentGiven || isCapturingPose) {
            mutableUiState.update { it.copy(quality = status) }
            return
        }
        if (!status.isValid) {
            mutableUiState.update { it.copy(quality = status, stableFrames = 0) }
            return
        }
        val frames = state.stableFrames + 1
        if (frames >= requiredStableFrames) {
            val poseToCapture = state.currentPose
            isCapturingPose = true
            mutableUiState.update { it.copy(quality = status, stableFrames = frames) }
            viewModelScope.launch {
                try {
                    val frame = captureFrame()
                    if (frame != null && frame.isNotEmpty()) {
                        mutableUiState.update { current ->
                            val updatedFrames = current.capturedFrames + (poseToCapture to frame)
                            current.copy(
                                quality = status,
                                stableFrames = 0,
                                capturedFrames = updatedFrames,
                                capturedPoses = updatedFrames.size,
                            )
                        }
                    } else {
                        mutableUiState.update { it.copy(stableFrames = 0) }
                    }
                } finally {
                    isCapturingPose = false
                }
            }
        } else {
            mutableUiState.update { it.copy(quality = status, stableFrames = frames) }
        }
    }

    fun retake() {
        mutableUiState.update {
            it.copy(
                capturedPoses = 0,
                capturedFrames = emptyMap(),
                stableFrames = 0,
                errorMessage = null,
            )
        }
    }

    /**
     * Submits all accumulated frames (FRONT, LEFT, RIGHT).
     * Blocked if fewer than 3 frames are captured.
     * Retains captured frames on error to allow retry.
     */
    fun submit(captureFrame: (suspend () -> ByteArray?)? = null) {
        val state = mutableUiState.value
        if (!state.allPosesCaptured || state.capturedFrames.size < ENROLLMENT_POSES.size) return
        mutableUiState.update { it.copy(isSubmitting = true, errorMessage = null) }
        viewModelScope.launch {
            val result = employeeRepository.submitFaceEnrollment(employeeId, state.capturedFrames)
            when (result) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isSubmitting = false, isComplete = true)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isSubmitting = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }

    companion object {
        const val REQUIRED_STABLE_FRAMES = 8
    }
}

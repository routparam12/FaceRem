package com.facerem.kiosk.enrollment

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.data.DeviceEnrollmentRepository
import com.facerem.core.security.DeviceCredentialStore
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// Unambiguous 32-character alphabet used by backend enrollment codes
private const val ALLOWED_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
private const val CODE_LENGTH = 6

data class KioskEnrollmentUiState(
    val code: String = "",
    val deviceName: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val revocationNotice: String? = null,
) {
    val isSubmitEnabled: Boolean get() = code.length == CODE_LENGTH && !isLoading
}

sealed interface KioskEnrollmentEvent {
    data object EnrollmentSuccess : KioskEnrollmentEvent
}

@HiltViewModel
class KioskEnrollmentViewModel @Inject constructor(
    private val enrollmentRepository: DeviceEnrollmentRepository,
    private val credentialStore: DeviceCredentialStore,
) : ViewModel() {

    private val _uiState = MutableStateFlow(KioskEnrollmentUiState())
    val uiState: StateFlow<KioskEnrollmentUiState> = _uiState.asStateFlow()

    private val _events = MutableSharedFlow<KioskEnrollmentEvent>()
    val events: SharedFlow<KioskEnrollmentEvent> = _events.asSharedFlow()

    init {
        // Observe revocation events from device token authenticator
        viewModelScope.launch {
            credentialStore.revocationEvents.collect { reason ->
                _uiState.update { it.copy(revocationNotice = reason, code = "", errorMessage = null) }
            }
        }
    }

    fun onCodeChange(rawInput: String) {
        val filtered = rawInput.uppercase()
            .filter { it in ALLOWED_ALPHABET }
            .take(CODE_LENGTH)

        _uiState.update {
            it.copy(code = filtered, errorMessage = null)
        }
    }

    fun onDeviceNameChange(name: String) {
        _uiState.update {
            it.copy(deviceName = name.take(64))
        }
    }

    fun enroll() {
        val state = _uiState.value
        if (!state.isSubmitEnabled) return

        _uiState.update { it.copy(isLoading = true, errorMessage = null) }

        viewModelScope.launch {
            // Note: Never log enrollment code
            val result = enrollmentRepository.enrollDevice(
                code = state.code,
                deviceName = state.deviceName.ifBlank { null },
            )

            when (result) {
                is AppResult.Success -> {
                    _uiState.update { it.copy(isLoading = false, revocationNotice = null) }
                    _events.emit(KioskEnrollmentEvent.EnrollmentSuccess)
                }

                is AppResult.Error -> {
                    val userMessage = when (val err = result.error) {
                        is AppError.Api -> when (err.code) {
                            "CODE_INVALID_OR_EXPIRED" ->
                                "Invalid or expired enrollment code. Please request a new 6-character code from an administrator."
                            "RATE_LIMITED" ->
                                "Too many registration attempts. Please wait a minute and try again."
                            else -> err.userMessage
                        }
                        is AppError.NoInternet -> "Unable to connect to server. Please check device network connection."
                        is AppError.Timeout -> "Connection timed out. Please check network connection and try again."
                        else -> "Device enrollment failed. Please check the code and try again."
                    }
                    _uiState.update { it.copy(isLoading = false, errorMessage = userMessage) }
                }

                AppResult.Loading -> Unit
            }
        }
    }
}


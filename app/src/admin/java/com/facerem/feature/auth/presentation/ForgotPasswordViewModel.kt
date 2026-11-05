package com.facerem.feature.auth.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.common.Validators
import com.facerem.feature.auth.domain.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ForgotPasswordUiState(
    val email: String = "",
    val emailError: String? = null,
    val formError: String? = null,
    val isSubmitting: Boolean = false,
    val isSent: Boolean = false,
)

@HiltViewModel
class ForgotPasswordViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(ForgotPasswordUiState())
    val uiState = mutableUiState.asStateFlow()

    fun onEmailChange(value: String) {
        mutableUiState.update { it.copy(email = value, emailError = null, formError = null) }
    }

    fun submit() {
        val email = mutableUiState.value.email
        val emailError = Validators.emailError(email)
        if (emailError != null) {
            mutableUiState.update { it.copy(emailError = emailError) }
            return
        }
        mutableUiState.update { it.copy(isSubmitting = true) }
        viewModelScope.launch {
            when (val result = authRepository.requestPasswordReset(email)) {
                is AppResult.Success -> mutableUiState.update { it.copy(isSubmitting = false, isSent = true) }
                is AppResult.Error -> mutableUiState.update {
                    it.copy(isSubmitting = false, formError = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }
}

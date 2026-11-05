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

data class LoginUiState(
    val organizationCode: String = "",
    val email: String = "",
    val password: String = "",
    val rememberMe: Boolean = true,
    val emailError: String? = null,
    val passwordError: String? = null,
    val formError: String? = null,
    val isSubmitting: Boolean = false,
    val isGuestSubmitting: Boolean = false,
    val authenticated: Boolean = false,
) {
    val canSubmit: Boolean
        get() = !isSubmitting && !isGuestSubmitting && email.isNotBlank() && password.isNotBlank()
}

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(LoginUiState())
    val uiState = mutableUiState.asStateFlow()

    fun onOrganizationCodeChange(value: String) {
        mutableUiState.update { it.copy(organizationCode = value, formError = null) }
    }

    fun onEmailChange(value: String) {
        mutableUiState.update { it.copy(email = value, emailError = null, formError = null) }
    }

    fun onPasswordChange(value: String) {
        mutableUiState.update { it.copy(password = value, passwordError = null, formError = null) }
    }

    fun onRememberMeChange(value: Boolean) {
        mutableUiState.update { it.copy(rememberMe = value) }
    }

    fun signIn() {
        val state = mutableUiState.value
        val emailError = Validators.emailError(state.email)
        val passwordError = Validators.passwordError(state.password)
        if (emailError != null || passwordError != null) {
            mutableUiState.update { it.copy(emailError = emailError, passwordError = passwordError) }
            return
        }

        mutableUiState.update { it.copy(isSubmitting = true, formError = null) }
        viewModelScope.launch {
            when (val result = authRepository.login(state.email, state.password, state.organizationCode)) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isSubmitting = false, authenticated = true)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isSubmitting = false, formError = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }

    fun continueAsGuest() {
        mutableUiState.update { it.copy(isGuestSubmitting = true, formError = null) }
        viewModelScope.launch {
            when (val result = authRepository.continueAsGuest()) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isGuestSubmitting = false, authenticated = true)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isGuestSubmitting = false, formError = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }

    /** Fills the form with the demo administrator so reviewers can try the signed-in path. */
    fun prefillDemoCredentials() {
        mutableUiState.update {
            it.copy(
                organizationCode = "NORTHWIND",
                email = "admin@northwind.demo",
                password = "demo12345",
                emailError = null,
                passwordError = null,
                formError = null,
            )
        }
    }
}

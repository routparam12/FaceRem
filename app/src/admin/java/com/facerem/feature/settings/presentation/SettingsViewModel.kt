package com.facerem.feature.settings.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.datastore.AppPreferences
import com.facerem.core.datastore.ThemeMode
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.core.session.SessionState
import com.facerem.feature.auth.domain.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val user: User? = null,
    val isGuest: Boolean = false,
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val showSignOutDialog: Boolean = false,
    val isSignedOut: Boolean = false,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val preferences: AppPreferences,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(SettingsUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        viewModelScope.launch {
            combine(sessionManager.state, preferences.themeMode) { session, theme -> session to theme }
                .collect { (session, theme) ->
                    val authenticated = session as? SessionState.Authenticated
                    mutableUiState.update {
                        it.copy(
                            user = authenticated?.user,
                            isGuest = authenticated?.isGuest == true,
                            themeMode = theme,
                        )
                    }
                }
        }
    }

    fun onThemeModeChange(mode: ThemeMode) {
        viewModelScope.launch { preferences.setThemeMode(mode) }
    }

    fun onSignOutRequested() = mutableUiState.update { it.copy(showSignOutDialog = true) }

    fun onSignOutDismissed() = mutableUiState.update { it.copy(showSignOutDialog = false) }

    fun confirmSignOut() {
        viewModelScope.launch {
            authRepository.logout()
            mutableUiState.update { it.copy(showSignOutDialog = false, isSignedOut = true) }
        }
    }
}

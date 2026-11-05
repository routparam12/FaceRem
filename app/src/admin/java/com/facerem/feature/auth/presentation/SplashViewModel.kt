package com.facerem.feature.auth.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.app.navigation.AppRoute
import com.facerem.core.datastore.AppPreferences
import com.facerem.core.session.SessionManager
import com.facerem.core.session.SessionState
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

@HiltViewModel
class SplashViewModel @Inject constructor(
    private val sessionManager: SessionManager,
    private val preferences: AppPreferences,
) : ViewModel() {

    /** Route to move to once branding has been shown, or null while still deciding. */
    private val mutableDestination = MutableStateFlow<String?>(null)
    val destination = mutableDestination.asStateFlow()

    init {
        viewModelScope.launch {
            val session = sessionManager.state.first { it !is SessionState.Unknown }
            val onboarded = preferences.hasCompletedOnboarding.first()
            mutableDestination.value = when {
                session is SessionState.Authenticated -> AppRoute.Main
                !onboarded -> AppRoute.Onboarding
                else -> AppRoute.Login
            }
        }
    }
}

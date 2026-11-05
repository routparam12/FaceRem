package com.facerem.feature.auth.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.datastore.AppPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.launch

@HiltViewModel
class OnboardingViewModel @Inject constructor(
    private val preferences: AppPreferences,
) : ViewModel() {
    fun markCompleted() {
        viewModelScope.launch { preferences.setOnboardingCompleted(true) }
    }
}

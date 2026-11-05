package com.facerem.feature.dashboard.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.core.session.SessionState
import com.facerem.feature.dashboard.domain.DashboardRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val user: User? = null,
    val isGuest: Boolean = false,
    val summary: DashboardSummary? = null,
    val errorMessage: String? = null,
)

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val dashboardRepository: DashboardRepository,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(DashboardUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        viewModelScope.launch {
            sessionManager.state.collect { session ->
                val authenticated = session as? SessionState.Authenticated
                mutableUiState.update {
                    it.copy(user = authenticated?.user, isGuest = authenticated?.isGuest == true)
                }
            }
        }
        load()
    }

    fun refresh() = load(isRefresh = true)

    private fun load(isRefresh: Boolean = false) {
        mutableUiState.update {
            it.copy(isLoading = !isRefresh && it.summary == null, isRefreshing = isRefresh, errorMessage = null)
        }
        viewModelScope.launch {
            when (val result = dashboardRepository.loadSummary()) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isLoading = false, isRefreshing = false, summary = result.data)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, isRefreshing = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }
}

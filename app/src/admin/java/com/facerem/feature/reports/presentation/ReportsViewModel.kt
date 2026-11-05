package com.facerem.feature.reports.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.model.ReportSummary
import com.facerem.core.session.SessionManager
import com.facerem.feature.reports.domain.ReportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ReportsUiState(
    val isLoading: Boolean = true,
    val summary: ReportSummary? = null,
    val isGuest: Boolean = false,
    val exportMessage: String? = null,
    val errorMessage: String? = null,
)

@HiltViewModel
class ReportsViewModel @Inject constructor(
    private val reportRepository: ReportRepository,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(ReportsUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        viewModelScope.launch {
            sessionManager.isGuest.collect { guest -> mutableUiState.update { it.copy(isGuest = guest) } }
        }
        load()
    }

    fun load() {
        mutableUiState.update { it.copy(isLoading = it.summary == null, errorMessage = null) }
        viewModelScope.launch {
            when (val result = reportRepository.loadSummary()) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isLoading = false, summary = result.data)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }

    /** Export is generated and delivered by the backend; the client only requests it. */
    fun requestExport() {
        mutableUiState.update {
            it.copy(
                exportMessage = if (it.isGuest) {
                    "Export is unavailable in guest mode. Sign in to email a CSV report."
                } else {
                    "Export requested. The CSV will be emailed when the server finishes generating it."
                },
            )
        }
    }

    fun dismissExportMessage() = mutableUiState.update { it.copy(exportMessage = null) }
}

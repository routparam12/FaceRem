package com.facerem.feature.history.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppClock
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.feature.attendance.domain.AttendanceRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class HistoryRange(val label: String, val days: Int) {
    TODAY("Today", 1),
    WEEK("7 days", 7),
    FORTNIGHT("14 days", 14),
}

data class HistoryUiState(
    val isLoading: Boolean = true,
    val records: List<AttendanceRecord> = emptyList(),
    val range: HistoryRange = HistoryRange.WEEK,
    val statusFilter: AttendanceStatus? = null,
    val query: String = "",
    val errorMessage: String? = null,
) {
    private val allowedDates: Set<String>
        get() = (0 until range.days).map(AppClock::isoDate).toSet()

    val visibleRecords: List<AttendanceRecord>
        get() = records
            .filter { it.date in allowedDates }
            .filter { statusFilter == null || it.status == statusFilter }
            .filter { record ->
                val needle = query.trim()
                needle.isBlank() ||
                    record.employeeName.contains(needle, ignoreCase = true) ||
                    record.employeeCode.contains(needle, ignoreCase = true)
            }

    val groupedByDate: List<Pair<String, List<AttendanceRecord>>>
        get() = visibleRecords.groupBy { it.date }.toList().sortedByDescending { it.first }
}

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val attendanceRepository: AttendanceRepository,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(HistoryUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        load()
    }

    fun onRangeChange(range: HistoryRange) = mutableUiState.update { it.copy(range = range) }

    fun onStatusFilterChange(status: AttendanceStatus?) =
        mutableUiState.update { it.copy(statusFilter = status) }

    fun onQueryChange(value: String) = mutableUiState.update { it.copy(query = value) }

    fun load() {
        mutableUiState.update { it.copy(isLoading = it.records.isEmpty(), errorMessage = null) }
        viewModelScope.launch {
            when (val result = attendanceRepository.history()) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isLoading = false, records = result.data)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }
}

package com.facerem.feature.employees.presentation

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.app.navigation.AppRoute
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Employee
import com.facerem.feature.employees.domain.EmployeeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EmployeeDetailUiState(
    val isLoading: Boolean = true,
    val employee: Employee? = null,
    val recentAttendance: List<AttendanceRecord> = emptyList(),
    val errorMessage: String? = null,
)

@HiltViewModel
class EmployeeDetailViewModel @Inject constructor(
    private val employeeRepository: EmployeeRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    private val employeeId: String = checkNotNull(savedStateHandle[AppRoute.EmployeeIdArg])

    private val mutableUiState = MutableStateFlow(EmployeeDetailUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        mutableUiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            when (val result = employeeRepository.employee(employeeId)) {
                is AppResult.Success -> {
                    val attendance = employeeRepository.attendanceFor(employeeId)
                    mutableUiState.update {
                        it.copy(
                            isLoading = false,
                            employee = result.data,
                            recentAttendance = (attendance as? AppResult.Success)?.data?.take(10).orEmpty(),
                        )
                    }
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }
}

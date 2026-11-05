package com.facerem.feature.employees.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.session.SessionManager
import com.facerem.feature.employees.domain.EmployeeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class EmployeeFilter(val label: String) {
    ALL("All"),
    ENROLLED("Enrolled"),
    PENDING("Needs enrollment"),
    INACTIVE("Inactive"),
}

data class EmployeesUiState(
    val isLoading: Boolean = true,
    val employees: List<Employee> = emptyList(),
    val query: String = "",
    val filter: EmployeeFilter = EmployeeFilter.ALL,
    val isGuest: Boolean = false,
    val errorMessage: String? = null,
) {
    val visibleEmployees: List<Employee>
        get() = employees
            .filter { employee ->
                when (filter) {
                    EmployeeFilter.ALL -> true
                    EmployeeFilter.ENROLLED -> employee.faceEnrollment == FaceEnrollmentStatus.ENROLLED
                    EmployeeFilter.PENDING -> employee.faceEnrollment != FaceEnrollmentStatus.ENROLLED
                    EmployeeFilter.INACTIVE -> !employee.isActive
                }
            }
            .filter { employee ->
                val needle = query.trim()
                needle.isBlank() ||
                    employee.fullName.contains(needle, ignoreCase = true) ||
                    employee.employeeCode.contains(needle, ignoreCase = true) ||
                    employee.department.contains(needle, ignoreCase = true)
            }
}

@HiltViewModel
class EmployeesViewModel @Inject constructor(
    private val employeeRepository: EmployeeRepository,
    sessionManager: SessionManager,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(EmployeesUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        viewModelScope.launch {
            sessionManager.isGuest.collect { guest -> mutableUiState.update { it.copy(isGuest = guest) } }
        }
        load()
    }

    fun onQueryChange(value: String) {
        mutableUiState.update { it.copy(query = value) }
    }

    fun onFilterChange(filter: EmployeeFilter) {
        mutableUiState.update { it.copy(filter = filter) }
    }

    fun load() {
        mutableUiState.update { it.copy(isLoading = it.employees.isEmpty(), errorMessage = null) }
        viewModelScope.launch {
            when (val result = employeeRepository.loadEmployees()) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isLoading = false, employees = result.data)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, errorMessage = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }
}

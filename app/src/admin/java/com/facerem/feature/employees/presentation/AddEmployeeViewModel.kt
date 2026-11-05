package com.facerem.feature.employees.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.common.Validators
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.employees.domain.NewEmployee
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AddEmployeeUiState(
    val fullName: String = "",
    val employeeCode: String = "",
    val email: String = "",
    val phone: String = "",
    val jobTitle: String = "",
    val department: String = "",
    val branch: String = "",
    val shiftName: String = "",
    val departments: List<String> = emptyList(),
    val branches: List<String> = emptyList(),
    val shifts: List<String> = emptyList(),
    val fieldErrors: Map<String, String> = emptyMap(),
    val formError: String? = null,
    val isSubmitting: Boolean = false,
    val createdEmployeeId: String? = null,
) {
    val canSubmit: Boolean
        get() = !isSubmitting && fullName.isNotBlank() && employeeCode.isNotBlank() && email.isNotBlank()
}

@HiltViewModel
class AddEmployeeViewModel @Inject constructor(
    private val employeeRepository: EmployeeRepository,
) : ViewModel() {

    private val mutableUiState = MutableStateFlow(AddEmployeeUiState())
    val uiState = mutableUiState.asStateFlow()

    init {
        viewModelScope.launch {
            val departments = employeeRepository.departments().map { it.name }
            val branches = employeeRepository.branches().map { it.name }
            val shifts = employeeRepository.shifts().map { it.name }
            mutableUiState.update {
                it.copy(
                    departments = departments,
                    branches = branches,
                    shifts = shifts,
                    department = departments.firstOrNull().orEmpty(),
                    branch = branches.firstOrNull().orEmpty(),
                    shiftName = shifts.firstOrNull().orEmpty(),
                )
            }
        }
    }

    fun onFullNameChange(value: String) = update { it.copy(fullName = value) }
    fun onEmployeeCodeChange(value: String) = update { it.copy(employeeCode = value) }
    fun onEmailChange(value: String) = update { it.copy(email = value) }
    fun onPhoneChange(value: String) = update { it.copy(phone = value) }
    fun onJobTitleChange(value: String) = update { it.copy(jobTitle = value) }
    fun onDepartmentChange(value: String) = update { it.copy(department = value) }
    fun onBranchChange(value: String) = update { it.copy(branch = value) }
    fun onShiftChange(value: String) = update { it.copy(shiftName = value) }

    fun submit() {
        val state = mutableUiState.value
        val errors = buildMap {
            Validators.requiredError(state.fullName, "Full name")?.let { put(FIELD_NAME, it) }
            Validators.requiredError(state.employeeCode, "Employee code")?.let { put(FIELD_CODE, it) }
            Validators.emailError(state.email)?.let { put(FIELD_EMAIL, it) }
            Validators.phoneError(state.phone)?.let { put(FIELD_PHONE, it) }
            Validators.requiredError(state.jobTitle, "Job title")?.let { put(FIELD_TITLE, it) }
        }
        if (errors.isNotEmpty()) {
            mutableUiState.update { it.copy(fieldErrors = errors) }
            return
        }

        mutableUiState.update { it.copy(isSubmitting = true, fieldErrors = emptyMap(), formError = null) }
        viewModelScope.launch {
            val result = employeeRepository.createEmployee(
                NewEmployee(
                    fullName = state.fullName,
                    employeeCode = state.employeeCode,
                    email = state.email,
                    phone = state.phone,
                    department = state.department,
                    branch = state.branch,
                    jobTitle = state.jobTitle,
                    shiftName = state.shiftName,
                ),
            )
            when (result) {
                is AppResult.Success -> mutableUiState.update {
                    it.copy(isSubmitting = false, createdEmployeeId = result.data.id)
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isSubmitting = false, formError = result.error.userMessage)
                }

                AppResult.Loading -> Unit
            }
        }
    }

    private fun update(transform: (AddEmployeeUiState) -> AddEmployeeUiState) {
        mutableUiState.update { transform(it).copy(fieldErrors = emptyMap(), formError = null) }
    }

    companion object {
        const val FIELD_NAME = "fullName"
        const val FIELD_CODE = "employeeCode"
        const val FIELD_EMAIL = "email"
        const val FIELD_PHONE = "phone"
        const val FIELD_TITLE = "jobTitle"
    }
}

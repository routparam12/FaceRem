package com.facerem.app.navigation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.model.Employee
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.feature.employees.domain.EmployeeRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class MainShellViewModel @Inject constructor(
    sessionManager: SessionManager,
    private val employeeRepository: EmployeeRepository,
) : ViewModel() {

    val currentUser: StateFlow<User?> = sessionManager.currentUser
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    private val _employees = MutableStateFlow<List<Employee>>(emptyList())
    val employees: StateFlow<List<Employee>> = _employees.asStateFlow()

    private val _isLoadingEmployees = MutableStateFlow(false)
    val isLoadingEmployees: StateFlow<Boolean> = _isLoadingEmployees.asStateFlow()

    fun loadEmployees() {
        viewModelScope.launch {
            _isLoadingEmployees.value = true
            when (val res = employeeRepository.loadEmployees()) {
                is AppResult.Success -> _employees.value = res.data
                else -> Unit
            }
            _isLoadingEmployees.value = false
        }
    }
}


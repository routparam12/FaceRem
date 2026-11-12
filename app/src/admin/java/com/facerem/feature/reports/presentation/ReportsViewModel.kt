package com.facerem.feature.reports.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.Employee
import com.facerem.core.model.ReportSummary
import com.facerem.core.session.SessionManager
import com.facerem.feature.attendance.domain.AttendanceRepository
import com.facerem.feature.dashboard.presentation.DashboardStatCategory
import com.facerem.feature.employees.domain.EmployeeRepository
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
    val dashboardSummary: DashboardSummary? = null,
    val allEmployees: List<Employee> = emptyList(),
    val todayAttendanceRecords: List<AttendanceRecord> = emptyList(),
    val selectedStatCategory: DashboardStatCategory? = null,
    val isGuest: Boolean = false,
    val exportMessage: String? = null,
    val errorMessage: String? = null,
)

@HiltViewModel
class ReportsViewModel @Inject constructor(
    private val reportRepository: ReportRepository,
    private val employeeRepository: EmployeeRepository,
    private val attendanceRepository: AttendanceRepository,
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

    fun selectStatCategory(category: DashboardStatCategory?) {
        mutableUiState.update { it.copy(selectedStatCategory = category) }
    }

    fun load() {
        mutableUiState.update { it.copy(isLoading = it.summary == null, errorMessage = null) }
        viewModelScope.launch {
            val reportResult = reportRepository.loadSummary()
            val employeesResult = employeeRepository.loadEmployees()
            val attendanceResult = attendanceRepository.history()

            when (reportResult) {
                is AppResult.Success -> {
                    val employees = (employeesResult as? AppResult.Success)?.data.orEmpty()
                    val attendance = (attendanceResult as? AppResult.Success)?.data.orEmpty()
                    val dummySummary = DashboardSummary(
                        organizationName = "",
                        dateLabel = "",
                        totalEmployees = employees.size,
                        presentCount = attendance.count { it.status.name == "PRESENT" },
                        lateCount = reportResult.data.lateArrivals,
                        absentCount = reportResult.data.absences,
                        onLeaveCount = 0,
                        pendingEnrollments = employees.count { it.faceEnrollment.name != "ENROLLED" },
                        weeklyAttendanceRate = emptyList(),
                        recentActivity = emptyList(),
                    )
                    mutableUiState.update {
                        it.copy(
                            isLoading = false,
                            summary = reportResult.data,
                            dashboardSummary = dummySummary,
                            allEmployees = employees,
                            todayAttendanceRecords = attendance,
                        )
                    }
                }

                is AppResult.Error -> mutableUiState.update {
                    it.copy(isLoading = false, errorMessage = reportResult.error.userMessage)
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

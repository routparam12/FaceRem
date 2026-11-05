package com.facerem.feature.dashboard.data

import com.facerem.core.common.AppClock
import com.facerem.core.common.AppResult
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.feature.dashboard.domain.DashboardRepository
import javax.inject.Inject
import kotlinx.coroutines.delay

class DemoDashboardRepository @Inject constructor(
    private val demoDataStore: DemoDataStore,
) : DashboardRepository {

    override suspend fun loadSummary(): AppResult<DashboardSummary> {
        delay(500)
        val today = AppClock.todayIso()
        val employees = demoDataStore.employees.value
        val todayRecords = demoDataStore.attendance.value.filter { it.date == today }
        return AppResult.Success(
            DashboardSummary(
                organizationName = demoDataStore.organization.name,
                dateLabel = AppClock.longDateLabel(),
                totalEmployees = employees.count { it.isActive },
                presentCount = todayRecords.count { it.status == AttendanceStatus.PRESENT },
                lateCount = todayRecords.count { it.status == AttendanceStatus.LATE },
                absentCount = todayRecords.count { it.status == AttendanceStatus.ABSENT },
                onLeaveCount = todayRecords.count { it.status == AttendanceStatus.ON_LEAVE },
                pendingEnrollments = employees.count { it.faceEnrollment != FaceEnrollmentStatus.ENROLLED },
                weeklyAttendanceRate = demoDataStore.weeklyRates(),
                recentActivity = todayRecords
                    .filter { it.checkInTime != null }
                    .sortedByDescending { it.checkInTime }
                    .take(6),
            ),
        )
    }
}

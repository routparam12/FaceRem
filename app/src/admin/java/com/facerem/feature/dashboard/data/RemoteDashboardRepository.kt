package com.facerem.feature.dashboard.data

import com.facerem.core.common.AppResult
import com.facerem.core.model.DashboardSummary
import com.facerem.core.network.ApiCall
import com.facerem.core.network.api.FaceAttendApi
import com.facerem.core.network.mapper.toRecord
import com.facerem.core.network.mapper.toSummary
import com.facerem.feature.dashboard.domain.DashboardRepository
import com.facerem.feature.employees.data.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RemoteDashboardRepository @Inject constructor(
    private val api: FaceAttendApi,
    private val apiCall: ApiCall,
) : DashboardRepository {

    override suspend fun loadSummary(): AppResult<DashboardSummary> {
        // Two calls: the dashboard gives the counts, the attendance list gives the names
        // behind "recent activity".
        val recent = (apiCall.invoke { api.attendance() } as? AppResult.Success)
            ?.data.orEmpty()
            .map { it.toRecord() }
            .filter { it.checkInTime != null }
            .take(6)

        return apiCall.invoke { api.dashboard() }.map { it.toSummary(recent) }
    }
}

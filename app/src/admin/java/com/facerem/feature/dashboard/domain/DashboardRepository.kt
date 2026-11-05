package com.facerem.feature.dashboard.domain

import com.facerem.core.common.AppResult
import com.facerem.core.model.DashboardSummary

interface DashboardRepository {
    /** Maps to `GET /api/v1/dashboard`. */
    suspend fun loadSummary(): AppResult<DashboardSummary>
}

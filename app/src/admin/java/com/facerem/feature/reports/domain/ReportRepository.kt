package com.facerem.feature.reports.domain

import com.facerem.core.common.AppResult
import com.facerem.core.model.ReportSummary

interface ReportRepository {
    suspend fun loadSummary(): AppResult<ReportSummary>
}

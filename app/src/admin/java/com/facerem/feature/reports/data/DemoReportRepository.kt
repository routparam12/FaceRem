package com.facerem.feature.reports.data

import com.facerem.core.common.AppResult
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.ReportSummary
import com.facerem.feature.reports.domain.ReportRepository
import javax.inject.Inject
import kotlinx.coroutines.delay

class DemoReportRepository @Inject constructor(
    private val demoDataStore: DemoDataStore,
) : ReportRepository {
    override suspend fun loadSummary(): AppResult<ReportSummary> {
        delay(500)
        return AppResult.Success(demoDataStore.reportSummary())
    }
}

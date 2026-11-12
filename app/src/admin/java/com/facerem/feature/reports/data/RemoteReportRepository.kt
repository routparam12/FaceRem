package com.facerem.feature.reports.data

import com.facerem.core.common.AppResult
import com.facerem.core.model.ReportSummary
import com.facerem.core.network.ApiCall
import com.facerem.core.network.api.FaceAttendApi
import com.facerem.core.network.mapper.toReportSummary
import com.facerem.feature.reports.domain.ReportRepository
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RemoteReportRepository @Inject constructor(
    private val api: FaceAttendApi,
    private val apiCall: ApiCall,
) : ReportRepository {
    override suspend fun loadSummary(): AppResult<ReportSummary> =
        apiCall.invoke { api.reportSummary() }.map { it.toReportSummary() }
}

private inline fun <T, R> AppResult<T>.map(transform: (T) -> R): AppResult<R> = when (this) {
    is AppResult.Success -> AppResult.Success(transform(data))
    is AppResult.Error -> this
    AppResult.Loading -> AppResult.Loading
}


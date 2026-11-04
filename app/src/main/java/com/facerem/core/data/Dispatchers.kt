package com.facerem.core.data

import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Branch
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.Department
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.LivenessChallenge
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.model.Shift
import com.facerem.core.session.SessionManager
import com.facerem.feature.attendance.domain.AttendanceRepository
import com.facerem.feature.dashboard.domain.DashboardRepository
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.employees.domain.NewEmployee
import kotlinx.coroutines.flow.first

/**
 * Picks the backend or the local sample data for each call.
 *
 * Re-read per call rather than cached: leaving guest mode must take effect immediately,
 * and a stale choice would have a signed-in user reading demo data.
 */
internal class DispatchingEmployeeRepository(
    private val remote: EmployeeRepository,
    private val demo: EmployeeRepository,
    private val session: SessionManager,
) : EmployeeRepository {

    private suspend fun active(): EmployeeRepository =
        if (session.isGuest.first()) demo else remote

    override suspend fun loadEmployees(): AppResult<List<Employee>> = active().loadEmployees()

    override suspend fun employee(id: String): AppResult<Employee> = active().employee(id)

    override suspend fun createEmployee(employee: NewEmployee): AppResult<Employee> =
        active().createEmployee(employee)

    override suspend fun submitFaceEnrollment(
        employeeId: String,
        frames: Map<FaceQualityEvaluator.HeadPose, ByteArray>,
    ): AppResult<FaceEnrollmentStatus> = active().submitFaceEnrollment(employeeId, frames)

    override suspend fun submitFaceEnrollment(
        employeeId: String,
        image: ByteArray,
    ): AppResult<FaceEnrollmentStatus> = active().submitFaceEnrollment(employeeId, image)

    override suspend fun attendanceFor(employeeId: String): AppResult<List<AttendanceRecord>> =
        active().attendanceFor(employeeId)

    override suspend fun departments(): List<Department> = active().departments()

    override suspend fun branches(): List<Branch> = active().branches()

    override suspend fun shifts(): List<Shift> = active().shifts()
}

internal class DispatchingDashboardRepository(
    private val remote: DashboardRepository,
    private val demo: DashboardRepository,
    private val session: SessionManager,
) : DashboardRepository {
    override suspend fun loadSummary(): AppResult<DashboardSummary> =
        (if (session.isGuest.first()) demo else remote).loadSummary()
}

internal class DispatchingAttendanceRepository(
    private val remote: AttendanceRepository,
    private val demo: AttendanceRepository,
    private val session: SessionManager,
) : AttendanceRepository {

    private suspend fun active(): AttendanceRepository =
        if (session.isGuest.first()) demo else remote

    override suspend fun requestChallenge(): AppResult<LivenessChallenge> =
        active().requestChallenge()

    override suspend fun recognize(
        image: ByteArray,
        challengeId: String?,
        nonce: String?,
        burstFrames: List<ByteArray>,
        deviceLabel: String,
    ): AppResult<RecognitionOutcome> =
        active().recognize(image, challengeId, nonce, burstFrames, deviceLabel)

    override suspend fun history(): AppResult<List<AttendanceRecord>> = active().history()
}

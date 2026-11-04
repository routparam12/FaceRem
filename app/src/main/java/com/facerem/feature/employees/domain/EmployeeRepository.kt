package com.facerem.feature.employees.domain

import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Branch
import com.facerem.core.model.Department
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.Shift

data class NewEmployee(
    val fullName: String,
    val employeeCode: String,
    val email: String,
    val phone: String,
    val department: String,
    val branch: String,
    val jobTitle: String,
    val shiftName: String,
)

interface EmployeeRepository {
    /** Maps to `GET /api/v1/employees`. */
    suspend fun loadEmployees(): AppResult<List<Employee>>

    /** Maps to `GET /api/v1/employees/{id}`. */
    suspend fun employee(id: String): AppResult<Employee>

    /** Maps to `POST /api/v1/employees`. */
    suspend fun createEmployee(employee: NewEmployee): AppResult<Employee>

    /**
     * Maps to `POST /api/v1/employees/{employeeId}/face/enroll`.
     * Multi-frame enrollment requires front, left, and right pose captures.
     */
    suspend fun submitFaceEnrollment(
        employeeId: String,
        frames: Map<FaceQualityEvaluator.HeadPose, ByteArray>,
    ): AppResult<FaceEnrollmentStatus>

    /** Backwards-compatible single frame overload. */
    suspend fun submitFaceEnrollment(
        employeeId: String,
        image: ByteArray,
    ): AppResult<FaceEnrollmentStatus> = submitFaceEnrollment(
        employeeId,
        mapOf(
            FaceQualityEvaluator.HeadPose.FRONT to image,
            FaceQualityEvaluator.HeadPose.SLIGHT_LEFT to image,
            FaceQualityEvaluator.HeadPose.SLIGHT_RIGHT to image,
        ),
    )

    suspend fun attendanceFor(employeeId: String): AppResult<List<AttendanceRecord>>

    suspend fun departments(): List<Department>

    suspend fun branches(): List<Branch>

    suspend fun shifts(): List<Shift>
}

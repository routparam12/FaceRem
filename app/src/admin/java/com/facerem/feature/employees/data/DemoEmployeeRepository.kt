package com.facerem.feature.employees.data

import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Branch
import com.facerem.core.model.Department
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.Shift
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.employees.domain.NewEmployee
import javax.inject.Inject
import kotlinx.coroutines.delay

class DemoEmployeeRepository @Inject constructor(
    private val demoDataStore: DemoDataStore,
) : EmployeeRepository {

    override suspend fun loadEmployees(): AppResult<List<Employee>> {
        delay(450)
        return AppResult.Success(demoDataStore.employees.value.sortedBy { it.fullName })
    }

    override suspend fun employee(id: String): AppResult<Employee> {
        delay(250)
        val employee = demoDataStore.employeeById(id)
            ?: return AppResult.Error(
                AppError.Api("EMPLOYEE_NOT_FOUND", "This employee is no longer available.", httpStatus = 404),
            )
        return AppResult.Success(employee)
    }

    override suspend fun createEmployee(employee: NewEmployee): AppResult<Employee> {
        delay(700)
        val duplicate = demoDataStore.employees.value.any {
            it.employeeCode.equals(employee.employeeCode, ignoreCase = true)
        }
        if (duplicate) {
            return AppResult.Error(
                AppError.Api("CONFLICT", "That employee code is already in use.", httpStatus = 409),
            )
        }
        val created = Employee(
            id = "emp-${System.currentTimeMillis()}",
            employeeCode = employee.employeeCode.trim(),
            fullName = employee.fullName.trim(),
            email = employee.email.trim(),
            phone = employee.phone.trim(),
            department = employee.department,
            branch = employee.branch,
            jobTitle = employee.jobTitle.trim(),
            shiftName = employee.shiftName,
            faceEnrollment = FaceEnrollmentStatus.PENDING,
            isActive = true,
        )
        demoDataStore.addEmployee(created)
        return AppResult.Success(created)
    }

    override suspend fun submitFaceEnrollment(
        employeeId: String,
        frames: Map<FaceQualityEvaluator.HeadPose, ByteArray>,
    ): AppResult<FaceEnrollmentStatus> {
        delay(1_200)
        if (frames.size < 3 || frames.values.any { it.isEmpty() }) {
            return AppResult.Error(
                AppError.Api("INSUFFICIENT_FRAMES", "Enrollment requires 3 valid frames.", httpStatus = 422),
            )
        }
        demoDataStore.updateEnrollment(employeeId, FaceEnrollmentStatus.ENROLLED)
        return AppResult.Success(FaceEnrollmentStatus.ENROLLED)
    }

    override suspend fun submitFaceEnrollment(
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

    override suspend fun attendanceFor(employeeId: String): AppResult<List<AttendanceRecord>> {
        delay(300)
        return AppResult.Success(demoDataStore.attendanceFor(employeeId).sortedByDescending { it.date })
    }

    override suspend fun departments(): List<Department> = demoDataStore.departments

    override suspend fun branches(): List<Branch> = demoDataStore.branches

    override suspend fun shifts(): List<Shift> = demoDataStore.shifts
}

package com.facerem.feature.employees.data

import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Branch
import com.facerem.core.model.Department
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.Shift
import com.facerem.core.network.ApiCall
import com.facerem.core.network.api.FaceAttendApi
import com.facerem.core.network.dto.NewEmployeeDto
import com.facerem.core.network.mapper.toEmployee
import com.facerem.core.network.mapper.toRecord
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.employees.domain.NewEmployee
import javax.inject.Inject
import javax.inject.Singleton
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

@Singleton
class RemoteEmployeeRepository @Inject constructor(
    private val api: FaceAttendApi,
    private val apiCall: ApiCall,
) : EmployeeRepository {

    override suspend fun loadEmployees(): AppResult<List<Employee>> =
        apiCall.invoke { api.employees() }.map { list -> list.map { it.toEmployee() } }

    override suspend fun employee(id: String): AppResult<Employee> =
        apiCall.invoke { api.employee(id) }.map { it.toEmployee() }

    override suspend fun createEmployee(employee: NewEmployee): AppResult<Employee> =
        apiCall.invoke {
            api.createEmployee(
                NewEmployeeDto(
                    employeeCode = employee.employeeCode.trim(),
                    fullName = employee.fullName.trim(),
                    email = employee.email.trim(),
                    phone = employee.phone.trim().ifBlank { null },
                    department = employee.department.ifBlank { null },
                    branch = employee.branch.ifBlank { null },
                    jobTitle = employee.jobTitle.trim().ifBlank { null },
                    shift = employee.shiftName.ifBlank { null },
                ),
            )
        }.map { it.toEmployee() }

    override suspend fun submitFaceEnrollment(
        employeeId: String,
        frames: Map<FaceQualityEvaluator.HeadPose, ByteArray>,
    ): AppResult<FaceEnrollmentStatus> = apiCall.invoke {
        val frontBytes = frames[FaceQualityEvaluator.HeadPose.FRONT] ?: ByteArray(0)
        val leftBytes = frames[FaceQualityEvaluator.HeadPose.SLIGHT_LEFT] ?: ByteArray(0)
        val rightBytes = frames[FaceQualityEvaluator.HeadPose.SLIGHT_RIGHT] ?: ByteArray(0)

        api.enrollFace(
            id = employeeId,
            front = frontBytes.asImagePart("front"),
            left = leftBytes.asImagePart("left"),
            right = rightBytes.asImagePart("right"),
            // Consent is collected on the device before the camera opens; the server
            // records it against the profile and refuses enrollment without it.
            consent = "true".toRequestBody(TEXT),
        )
    }.map { if (it.faceEnrolled) FaceEnrollmentStatus.ENROLLED else FaceEnrollmentStatus.PENDING }

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

    override suspend fun attendanceFor(employeeId: String): AppResult<List<AttendanceRecord>> =
        apiCall.invoke { api.attendance() }
            .map { rows -> rows.map { it.toRecord() }.filter { it.employeeId == employeeId } }

    override suspend fun departments(): List<Department> =
        apiCall.invoke { api.departments() }.dataOrEmpty()
            .map { Department(it.id, it.name, headCount = 0) }

    override suspend fun branches(): List<Branch> =
        apiCall.invoke { api.branches() }.dataOrEmpty()
            .map { Branch(it.id, it.name, city = "", headCount = 0) }

    override suspend fun shifts(): List<Shift> =
        apiCall.invoke { api.shifts() }.dataOrEmpty()
            .map { Shift(it.id, it.name, startTime = "", endTime = "", graceMinutes = 0) }
}

internal val TEXT = "text/plain".toMediaType()

internal fun ByteArray.asImagePart(name: String = "image"): MultipartBody.Part =
    MultipartBody.Part.createFormData(
        name,
        "$name.jpg",
        toRequestBody("image/jpeg".toMediaType()),
    )

internal inline fun <T, R> AppResult<T>.map(transform: (T) -> R): AppResult<R> = when (this) {
    is AppResult.Success -> AppResult.Success(transform(data))
    is AppResult.Error -> this
    AppResult.Loading -> AppResult.Loading
}

internal fun <T> AppResult<List<T>>.dataOrEmpty(): List<T> =
    (this as? AppResult.Success)?.data ?: emptyList()

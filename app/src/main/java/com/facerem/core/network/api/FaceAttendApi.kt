package com.facerem.core.network.api

import com.facerem.core.network.dto.ApiEnvelope
import com.facerem.core.network.dto.AttendanceRecordDto
import com.facerem.core.network.dto.ChallengeResponseDto
import com.facerem.core.network.dto.DashboardDto
import com.facerem.core.network.dto.EmployeeDto
import com.facerem.core.network.dto.EnrollResponseDto
import com.facerem.core.network.dto.NamedDto
import com.facerem.core.network.dto.NewEmployeeDto
import com.facerem.core.network.dto.RecognizeResponseDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface FaceAttendApi {
    @GET("api/v1/dashboard")
    suspend fun dashboard(): ApiEnvelope<DashboardDto>

    @GET("api/v1/employees")
    suspend fun employees(): ApiEnvelope<List<EmployeeDto>>

    @GET("api/v1/employees/{id}")
    suspend fun employee(@Path("id") id: String): ApiEnvelope<EmployeeDto>

    @POST("api/v1/employees")
    suspend fun createEmployee(@Body body: NewEmployeeDto): ApiEnvelope<EmployeeDto>

    @Multipart
    @POST("api/v1/employees/{id}/face/enroll")
    suspend fun enrollFace(
        @Path("id") id: String,
        @Part front: MultipartBody.Part,
        @Part left: MultipartBody.Part,
        @Part right: MultipartBody.Part,
        @Part("consent") consent: RequestBody,
    ): ApiEnvelope<EnrollResponseDto>

    @POST("api/v1/attendance/challenge")
    suspend fun challenge(): ApiEnvelope<ChallengeResponseDto>

    @Multipart
    @POST("api/v1/attendance/recognize")
    suspend fun recognize(
        @Part image: MultipartBody.Part,
        @Part("challenge_id") challengeId: RequestBody?,
        @Part("nonce") nonce: RequestBody?,
        @Part burst: List<MultipartBody.Part>,
        @Part("device_label") deviceLabel: RequestBody,
    ): ApiEnvelope<RecognizeResponseDto>

    @GET("api/v1/attendance")
    suspend fun attendance(@Query("on") on: String? = null): ApiEnvelope<List<AttendanceRecordDto>>

    @GET("api/v1/departments")
    suspend fun departments(): ApiEnvelope<List<NamedDto>>

    @GET("api/v1/branches")
    suspend fun branches(): ApiEnvelope<List<NamedDto>>

    @GET("api/v1/shifts")
    suspend fun shifts(): ApiEnvelope<List<NamedDto>>
}

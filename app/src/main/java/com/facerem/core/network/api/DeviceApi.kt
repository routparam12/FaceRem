package com.facerem.core.network.api

import com.facerem.core.network.AuthInterceptor
import com.facerem.core.network.dto.ApiEnvelope
import com.facerem.core.network.dto.DeviceEnrollRequestDto
import com.facerem.core.network.dto.DeviceEnrollResponseDto
import com.facerem.core.network.dto.DeviceEventRequestDto
import com.facerem.core.network.dto.DeviceEventResponseDto
import retrofit2.http.Body
import retrofit2.http.Headers
import retrofit2.http.POST

interface DeviceApi {

    /**
     * Exchanges a 6-character, 10-minute registration code for a long-lived device token.
     * Unauthenticated endpoint (device does not possess a token yet).
     */
    @Headers("${AuthInterceptor.NO_AUTH}: true")
    @POST("api/v1/devices/enroll")
    suspend fun enrollDevice(
        @Body request: DeviceEnrollRequestDto,
    ): ApiEnvelope<DeviceEnrollResponseDto>

    /**
     * Records an operational kiosk event (KIOSK_EXIT_UNLOCK, SUPERVISED_ENROLL_START, etc.)
     * into the organization audit log. Requires device credential.
     */
    @POST("api/v1/devices/me/events")
    suspend fun recordDeviceEvent(
        @Body request: DeviceEventRequestDto,
    ): ApiEnvelope<DeviceEventResponseDto>
}


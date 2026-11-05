package com.facerem.core.data

import com.facerem.core.common.AppResult
import com.facerem.core.network.ApiCall
import com.facerem.core.network.api.DeviceApi
import com.facerem.core.network.dto.DeviceEnrollRequestDto
import com.facerem.core.security.DeviceCredentialStore
import com.facerem.core.security.DeviceCredentials
import javax.inject.Inject
import javax.inject.Singleton

interface DeviceEnrollmentRepository {
    suspend fun enrollDevice(code: String, deviceName: String? = null): AppResult<DeviceCredentials>
}

@Singleton
class DeviceEnrollmentRepositoryImpl @Inject constructor(
    private val api: DeviceApi,
    private val apiCall: ApiCall,
    private val credentialStore: DeviceCredentialStore,
) : DeviceEnrollmentRepository {

    override suspend fun enrollDevice(code: String, deviceName: String?): AppResult<DeviceCredentials> {
        val cleanCode = code.trim().uppercase()
        val cleanName = deviceName?.trim()?.ifBlank { null }
        val result = apiCall.invoke {
            api.enrollDevice(DeviceEnrollRequestDto(code = cleanCode, name = cleanName))
        }
        return when (result) {
            is AppResult.Success -> {
                val dto = result.data
                val credentials = DeviceCredentials(
                    deviceId = dto.deviceId,
                    organizationId = dto.organizationId,
                    name = dto.name,
                    mode = dto.mode,
                    accessToken = dto.accessToken,
                )
                credentialStore.saveCredentials(credentials)
                AppResult.Success(credentials)
            }
            is AppResult.Error -> AppResult.Error(result.error)
            AppResult.Loading -> AppResult.Loading
        }
    }
}


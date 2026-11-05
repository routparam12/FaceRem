package com.facerem.core.network

import com.facerem.core.datastore.AppPreferences
import com.facerem.core.security.DeviceCredentialStore
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first

/**
 * Synchronous-ish access to the stored tokens for OkHttp, which runs off the coroutine
 * world. Reads check device credentials first (for Kiosk flavor) then DataStore (for Admin flavor).
 */
@Singleton
class TokenStore @Inject constructor(
    private val preferences: AppPreferences,
    private val deviceCredentialStore: DeviceCredentialStore,
) {
    suspend fun accessToken(): String? {
        val deviceToken = deviceCredentialStore.getCredentials()?.accessToken
        if (!deviceToken.isNullOrBlank()) {
            return deviceToken
        }
        return preferences.session.first().accessToken
    }

    suspend fun refreshToken(): String? = preferences.refreshToken.first()

    suspend fun updateTokens(accessToken: String, refreshToken: String) {
        preferences.updateTokens(accessToken, refreshToken)
    }

    suspend fun clear() {
        preferences.clearSession()
        deviceCredentialStore.wipe()
    }
}

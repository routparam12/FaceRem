package com.facerem.core.network

import android.util.Log
import com.facerem.core.network.api.AuthApi
import com.facerem.core.network.dto.RefreshRequestDto
import com.facerem.core.security.DeviceCredentialStore
import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

private const val TAG = "TokenAuthenticator"

/**
 * Handles 401 Unauthorized responses.
 *
 * For Kiosk devices: Device credentials have no refresh token. Any 401 (e.g. DEVICE_NOT_AUTHORIZED)
 * wipes stored device credentials and broadcasts a revocation event to route back to Enrollment.
 *
 * For Admin users: Refreshes user access tokens using the refresh token flow.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenStore: TokenStore,
    private val deviceCredentialStore: DeviceCredentialStore,
    @param:RefreshClient private val refreshApi: Provider<AuthApi>,
) : Authenticator {

    private val mutex = Mutex()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponseCount() >= MAX_RETRIES) {
            Log.w(TAG, "Giving up after $MAX_RETRIES refresh attempts")
            return null
        }

        val failedToken = response.request.header("Authorization")?.removePrefix("Bearer ")

        return runBlocking {
            mutex.withLock {
                // If a kiosk device credential failed with 401, wipe ONLY if revoked or expired
                val deviceCreds = deviceCredentialStore.getCredentials()
                if (deviceCreds != null && deviceCreds.accessToken == failedToken) {
                    val isRevokedOrExpired = try {
                        val body = response.peekBody(65536).string()
                        body.contains("DEVICE_NOT_AUTHORIZED") || body.contains("TOKEN_EXPIRED")
                    } catch (e: Exception) {
                        false
                    }

                    if (isRevokedOrExpired) {
                        Log.w(TAG, "Device token rejected by server (revoked or expired). Wiping credentials.")
                        deviceCredentialStore.notifyRevoked("This device was removed. Ask an admin for a new code.")
                    } else {
                        Log.w(TAG, "Device token 401 received without revocation code; preserving credentials.")
                    }
                    return@withLock null
                }

                val current = tokenStore.accessToken()
                // Another request already refreshed while this one waited for the lock.
                if (current != null && current != failedToken) {
                    return@withLock response.request.withToken(current)
                }

                val refresh = tokenStore.refreshToken() ?: return@withLock null
                val renewed = runCatching {
                    refreshApi.get().refresh(RefreshRequestDto(refresh))
                }.getOrNull()

                val tokens = renewed?.data
                if (tokens == null) {
                    // The refresh token is dead too, so the session is genuinely over.
                    tokenStore.clear()
                    return@withLock null
                }

                tokenStore.updateTokens(tokens.accessToken, tokens.refreshToken)
                response.request.withToken(tokens.accessToken)
            }
        }
    }

    private fun Request.withToken(token: String): Request =
        newBuilder().header("Authorization", "Bearer $token").build()

    private fun Response.priorResponseCount(): Int {
        var count = 0
        var prior = priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }

    private companion object {
        const val MAX_RETRIES = 1
    }
}

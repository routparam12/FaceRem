package com.facerem.feature.auth.data

import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.data.demo.DemoDataStore
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.feature.auth.domain.AuthRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.delay

/**
 * Demo-backed authentication.
 *
 * TODO(phase-3): replace the [DemoDataStore] calls with the Retrofit `AuthApi` and store the
 * returned access/refresh tokens in the secure token store. The surface of [AuthRepository]
 * is already the one the real implementation needs, so callers will not change.
 */
@Singleton
class DemoAuthRepository @Inject constructor(
    private val demoDataStore: DemoDataStore,
    private val sessionManager: SessionManager,
) : AuthRepository {

    override suspend fun login(email: String, password: String, organizationCode: String): AppResult<User> {
        delay(NETWORK_SIMULATION_MILLIS)
        if (password.equals("wrong", ignoreCase = true)) {
            return AppResult.Error(
                AppError.Api("INVALID_CREDENTIALS", "Email or password is incorrect.", httpStatus = 401),
            )
        }
        val user = demoDataStore.signInWithCredentials(email.trim())
        sessionManager.persist(
            user = user,
            accessToken = DEMO_ACCESS_TOKEN,
            refreshToken = DEMO_REFRESH_TOKEN,
            isGuest = false,
        )
        return AppResult.Success(user)
    }

    override suspend fun continueAsGuest(): AppResult<User> {
        delay(GUEST_SIMULATION_MILLIS)
        val user = demoDataStore.guestUser
        sessionManager.persist(user = user, accessToken = null, refreshToken = null, isGuest = true)
        return AppResult.Success(user)
    }

    override suspend fun requestPasswordReset(email: String): AppResult<Unit> {
        delay(NETWORK_SIMULATION_MILLIS)
        // The server always answers identically so that valid accounts cannot be enumerated.
        return AppResult.Success(Unit)
    }

    override suspend fun logout() {
        sessionManager.clear()
    }

    private companion object {
        const val NETWORK_SIMULATION_MILLIS = 900L
        const val GUEST_SIMULATION_MILLIS = 400L
        const val DEMO_ACCESS_TOKEN = "demo-access-token"
        const val DEMO_REFRESH_TOKEN = "demo-refresh-token"
    }
}

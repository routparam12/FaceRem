package com.facerem.feature.auth.data

import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.model.User
import com.facerem.core.network.ApiCall
import com.facerem.core.network.api.AuthApi
import com.facerem.core.network.dto.LoginRequestDto
import com.facerem.core.network.dto.RefreshRequestDto
import com.facerem.core.network.mapper.toUser
import com.facerem.core.datastore.AppPreferences
import com.facerem.core.session.SessionManager
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first

/** Real authentication against the FastAPI backend. */
@Singleton
class RemoteAuthRepository @Inject constructor(
    private val authApi: AuthApi,
    private val apiCall: ApiCall,
    private val sessionManager: SessionManager,
    private val preferences: AppPreferences,
) : AuthRepositoryContract {

    override suspend fun login(
        email: String,
        password: String,
        organizationCode: String,
    ): AppResult<User> {
        val tokens = apiCall.invoke {
            authApi.login(
                LoginRequestDto(
                    email = email.trim(),
                    password = password,
                    organizationSlug = organizationCode.trim().lowercase().ifBlank { null },
                ),
            )
        }
        if (tokens is AppResult.Error) return tokens

        val pair = (tokens as AppResult.Success).data
        // Store the tokens first: /auth/me is an authenticated call.
        preferences.updateTokens(pair.accessToken, pair.refreshToken)

        return when (val me = apiCall.invoke { authApi.me() }) {
            is AppResult.Success -> {
                val user = me.data.toUser()
                sessionManager.persist(
                    user = user,
                    accessToken = pair.accessToken,
                    refreshToken = pair.refreshToken,
                    isGuest = false,
                )
                AppResult.Success(user)
            }

            is AppResult.Error -> {
                // Half a session is worse than none; do not leave tokens behind.
                preferences.clearSession()
                me
            }

            AppResult.Loading -> AppResult.Error(AppError.Unknown)
        }
    }

    override suspend fun requestPasswordReset(email: String): AppResult<Unit> =
        AppResult.Error(
            AppError.Api(
                code = "NOT_IMPLEMENTED",
                userMessage = "Password reset is not available yet. Ask your administrator.",
            ),
        )

    override suspend fun logout() {
        // Tell the server so the refresh token is revoked rather than left alive.
        preferences.refreshToken.first()?.let { token ->
            runCatching { authApi.logout(RefreshRequestDto(token)) }
        }
        sessionManager.clear()
    }
}

/** The subset of [com.facerem.feature.auth.domain.AuthRepository] a backend can serve. */
interface AuthRepositoryContract {
    suspend fun login(email: String, password: String, organizationCode: String): AppResult<User>
    suspend fun requestPasswordReset(email: String): AppResult<Unit>
    suspend fun logout()
}

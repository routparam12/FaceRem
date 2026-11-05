package com.facerem.feature.auth.data

import com.facerem.core.common.AppResult
import com.facerem.core.model.User
import com.facerem.core.session.SessionManager
import com.facerem.feature.auth.domain.AuthRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first

/**
 * Routes each call to the backend or to the local demo data.
 *
 * Guest mode has to keep working without a server, and the decision cannot be made once at
 * startup because a guest can sign out and sign in for real. So it is re-read per call.
 */
@Singleton
class AuthRepositoryImpl @Inject constructor(
    private val remote: RemoteAuthRepository,
    private val demo: DemoAuthRepository,
    private val sessionManager: SessionManager,
) : AuthRepository {

    private suspend fun isGuest(): Boolean = sessionManager.isGuest.first()

    override suspend fun login(
        email: String,
        password: String,
        organizationCode: String,
    ): AppResult<User> = remote.login(email, password, organizationCode)

    override suspend fun continueAsGuest(): AppResult<User> = demo.continueAsGuest()

    override suspend fun requestPasswordReset(email: String): AppResult<Unit> =
        if (isGuest()) demo.requestPasswordReset(email) else remote.requestPasswordReset(email)

    override suspend fun logout() {
        if (isGuest()) demo.logout() else remote.logout()
    }
}

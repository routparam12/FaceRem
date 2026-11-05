package com.facerem.feature.auth.domain

import com.facerem.core.common.AppResult
import com.facerem.core.model.User

interface AuthRepository {
    /** Maps to `POST /api/v1/auth/login`. */
    suspend fun login(email: String, password: String, organizationCode: String): AppResult<User>

    /**
     * Starts a local, read-only demo session. No credentials are exchanged and no server
     * resources are touched; the session is flagged so write paths can be labelled clearly.
     */
    suspend fun continueAsGuest(): AppResult<User>

    /** Maps to `POST /api/v1/auth/forgot-password`. */
    suspend fun requestPasswordReset(email: String): AppResult<Unit>

    /** Maps to `POST /api/v1/auth/logout`, then clears the local session. */
    suspend fun logout()
}

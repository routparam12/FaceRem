package com.facerem.core.session

import com.facerem.core.datastore.AppPreferences
import com.facerem.core.datastore.StoredSession
import com.facerem.core.model.Role
import com.facerem.core.model.User
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.map

sealed interface SessionState {
    /** Session has not been read from disk yet; the splash screen waits on this. */
    data object Unknown : SessionState

    data object SignedOut : SessionState

    data class Authenticated(val user: User, val isGuest: Boolean) : SessionState
}

/**
 * Single source of truth for "who is signed in". Feature code observes [state] and never
 * reads tokens directly.
 */
@Singleton
open class SessionManager(
    private val preferences: AppPreferences?,
    guestFlow: Flow<Boolean>? = null,
) {
    @Inject
    constructor(preferences: AppPreferences) : this(preferences, null)

    open val state: Flow<SessionState> = preferences?.session?.map { it.toSessionState() } ?: emptyFlow()

    open val currentUser: Flow<User?> = state.map { (it as? SessionState.Authenticated)?.user }

    open val isGuest: Flow<Boolean> = guestFlow ?: state.map { (it as? SessionState.Authenticated)?.isGuest == true }

    open suspend fun persist(user: User, accessToken: String?, refreshToken: String?, isGuest: Boolean) {
        preferences?.saveSession(
            session = StoredSession(
                accessToken = accessToken,
                userId = user.id,
                fullName = user.fullName,
                email = user.email,
                role = user.role.name,
                organizationId = user.organizationId,
                organizationName = user.organizationName,
                isGuest = isGuest,
            ),
            refreshToken = refreshToken,
        )
    }

    open suspend fun clear() {
        preferences?.clearSession()
    }

    private fun StoredSession.toSessionState(): SessionState {
        if (!isActive) return SessionState.SignedOut
        return SessionState.Authenticated(
            user = User(
                id = requireNotNull(userId),
                fullName = fullName.orEmpty(),
                email = email.orEmpty(),
                role = Role.fromWireValue(role),
                organizationId = organizationId.orEmpty(),
                organizationName = organizationName.orEmpty(),
            ),
            isGuest = isGuest,
        )
    }
}

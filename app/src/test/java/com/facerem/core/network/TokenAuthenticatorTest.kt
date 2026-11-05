package com.facerem.core.network

import com.facerem.core.network.api.AuthApi
import com.facerem.core.security.DeviceCredentials
import com.facerem.core.security.FakeDeviceCredentialStore
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.mockito.Mockito.mock
import javax.inject.Provider

class TokenAuthenticatorTest {

    private lateinit var deviceCredentialStore: FakeDeviceCredentialStore
    private lateinit var tokenStore: TokenStore
    private lateinit var refreshApiProvider: Provider<AuthApi>
    private lateinit var authenticator: TokenAuthenticator

    private val deviceToken = "device-test-token-xyz"

    @Before
    fun setUp() = runTest {
        deviceCredentialStore = FakeDeviceCredentialStore()
        deviceCredentialStore.saveCredentials(
            DeviceCredentials(
                deviceId = "dev-1",
                organizationId = "org-1",
                name = "Kiosk Test",
                mode = "AUTO",
                accessToken = deviceToken,
            )
        )

        val mockPreferences = mock(com.facerem.core.datastore.AppPreferences::class.java)
        tokenStore = TokenStore(mockPreferences, deviceCredentialStore)
        refreshApiProvider = Provider { mock(AuthApi::class.java) }

        authenticator = TokenAuthenticator(
            tokenStore = tokenStore,
            deviceCredentialStore = deviceCredentialStore,
            refreshApi = refreshApiProvider,
        )
    }

    private fun build401Response(bodyString: String): Response {
        val request = Request.Builder()
            .url("https://api.facerem.com/api/v1/attendance/recognize")
            .header("Authorization", "Bearer $deviceToken")
            .build()

        return Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_2)
            .code(401)
            .message("Unauthorized")
            .body(bodyString.toResponseBody("application/json".toMediaType()))
            .build()
    }

    @Test
    fun `401 with DEVICE_NOT_AUTHORIZED wipes device credentials and emits revocation event`() = runTest {
        val response = build401Response("""{"success":false,"error":{"code":"DEVICE_NOT_AUTHORIZED","message":"Revoked"}}""")

        val resultRequest = authenticator.authenticate(null, response)

        assertNull(resultRequest)
        assertNull("Credentials should be wiped on DEVICE_NOT_AUTHORIZED", deviceCredentialStore.getCredentials())
        val revocationMsg = deviceCredentialStore.revocationEvents.firstOrNull()
        assertNotNull(revocationMsg)
        assertEquals("This device was removed. Ask an admin for a new code.", revocationMsg)
    }

    @Test
    fun `401 with TOKEN_EXPIRED wipes device credentials and emits revocation event`() = runTest {
        val response = build401Response("""{"success":false,"error":{"code":"TOKEN_EXPIRED","message":"Expired"}}""")

        val resultRequest = authenticator.authenticate(null, response)

        assertNull(resultRequest)
        assertNull("Credentials should be wiped on TOKEN_EXPIRED", deviceCredentialStore.getCredentials())
        val revocationMsg = deviceCredentialStore.revocationEvents.firstOrNull()
        assertNotNull(revocationMsg)
    }

    @Test
    fun `401 with generic unauthorized does NOT wipe device credentials`() = runTest {
        val response = build401Response("""{"success":false,"error":{"code":"UNAUTHORIZED","message":"Access denied"}}""")

        val resultRequest = authenticator.authenticate(null, response)

        assertNull(resultRequest)
        assertNotNull("Credentials must NOT be wiped on generic 401", deviceCredentialStore.getCredentials())
        assertEquals(deviceToken, deviceCredentialStore.getCredentials()?.accessToken)
    }
}


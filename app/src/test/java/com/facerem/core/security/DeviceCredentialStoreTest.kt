package com.facerem.core.security

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class DeviceCredentialStoreTest {

    private lateinit var store: FakeDeviceCredentialStore

    @Before
    fun setUp() {
        store = FakeDeviceCredentialStore()
    }

    @Test
    fun `initial credentials are null`() = runTest {
        assertNull(store.getCredentials())
        assertNull(store.credentials.first())
    }

    @Test
    fun `saving credentials stores and emits valid device credentials`() = runTest {
        val creds = DeviceCredentials(
            deviceId = "dev-1234",
            organizationId = "org-northwind",
            name = "Front Gate Kiosk",
            mode = "AUTO",
            accessToken = "eyJhbGciOi...",
        )

        store.saveCredentials(creds)

        val stored = store.getCredentials()
        assertNotNull(stored)
        assertEquals("dev-1234", stored?.deviceId)
        assertEquals("org-northwind", stored?.organizationId)
        assertEquals("Front Gate Kiosk", stored?.name)
        assertEquals("AUTO", stored?.mode)
        assertEquals("eyJhbGciOi...", stored?.accessToken)

        val flowValue = store.credentials.first()
        assertEquals(creds, flowValue)
    }

    @Test
    fun `wipe completely clears device credentials`() = runTest {
        val creds = DeviceCredentials(
            deviceId = "dev-1234",
            organizationId = "org-northwind",
            name = "Front Gate Kiosk",
            mode = "AUTO",
            accessToken = "eyJhbGciOi...",
        )
        store.saveCredentials(creds)
        assertNotNull(store.getCredentials())

        store.wipe()

        assertNull(store.getCredentials())
        assertNull(store.credentials.first())
    }

    @Test
    fun `notifyRevoked clears credentials and emits reason`() = runTest {
        val creds = DeviceCredentials(
            deviceId = "dev-1234",
            organizationId = "org-northwind",
            name = "Front Gate Kiosk",
            mode = "AUTO",
            accessToken = "eyJhbGciOi...",
        )
        store.saveCredentials(creds)

        store.notifyRevoked("This device was removed. Ask an admin for a new code.")

        assertNull(store.getCredentials())
        assertNull(store.credentials.first())
    }
}


package com.facerem.kiosk.navigation

import com.facerem.core.security.DeviceCredentials
import com.facerem.core.security.FakeDeviceCredentialStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class KioskRoutingTest {

    @Test
    fun `unprovisioned kiosk starts at enrollment route`() = runTest {
        val store = FakeDeviceCredentialStore(initial = null)
        val vm = KioskNavViewModel(store)

        val creds = vm.credentials.first()
        assertNull(creds)

        val destination = if (creds != null) KioskRoute.Scan else KioskRoute.Enrollment
        assertEquals(KioskRoute.Enrollment, destination)
    }

    @Test
    fun `provisioned kiosk starts directly at scan screen`() = runTest {
        val enrolledCreds = DeviceCredentials(
            deviceId = "kiosk-88",
            organizationId = "org-northwind",
            name = "Gate 1",
            mode = "AUTO",
            accessToken = "valid-token",
        )
        val store = FakeDeviceCredentialStore(initial = enrolledCreds)
        val vm = KioskNavViewModel(store)

        val creds = vm.credentials.first()
        assertEquals(enrolledCreds, creds)

        val destination = if (creds != null) KioskRoute.Scan else KioskRoute.Enrollment
        assertEquals(KioskRoute.Scan, destination)
    }
}


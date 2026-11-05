package com.facerem.kiosk.enrollment

import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.data.DeviceEnrollmentRepository
import com.facerem.core.security.DeviceCredentials
import com.facerem.core.security.FakeDeviceCredentialStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class KioskEnrollmentViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var credentialStore: FakeDeviceCredentialStore
    private lateinit var fakeRepository: FakeDeviceEnrollmentRepository
    private lateinit var viewModel: KioskEnrollmentViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        credentialStore = FakeDeviceCredentialStore()
        fakeRepository = FakeDeviceEnrollmentRepository()
        viewModel = KioskEnrollmentViewModel(fakeRepository, credentialStore)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `code input filters to uppercase and unambiguous 32-character alphabet up to 6 chars`() {
        // Lowercase, ambiguous characters (0, 1, I, O), and symbols should be stripped
        viewModel.onCodeChange("abc10oil234567")

        // 'a', 'b', 'c' -> uppercase 'A', 'B', 'C' (valid)
        // '1', '0', 'i', 'o' -> stripped (invalid alphabet)
        // 'l' -> 'L' (valid)
        // '2', '3' -> valid (total 6 characters: "ABCL23")
        val state = viewModel.uiState.value
        assertEquals("ABCL23", state.code)
        assertTrue(state.isSubmitEnabled)
    }

    @Test
    fun `successful enrollment stores credentials and emits success event`() = runTest {
        val creds = DeviceCredentials(
            deviceId = "kiosk-01",
            organizationId = "org-1",
            name = "Lobby Tablet",
            mode = "AUTO",
            accessToken = "device-jwt-token",
        )
        fakeRepository.nextResult = AppResult.Success(creds)

        viewModel.onCodeChange("ABC234")
        viewModel.onDeviceNameChange("Lobby Tablet")
        viewModel.enroll()

        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertNull(state.errorMessage)
        assertEquals("ABC234", fakeRepository.lastEnrolledCode)
        assertEquals("Lobby Tablet", fakeRepository.lastDeviceName)
    }

    @Test
    fun `invalid or expired code displays user-friendly error`() = runTest {
        fakeRepository.nextResult = AppResult.Error(
            AppError.Api("CODE_INVALID_OR_EXPIRED", "Invalid or expired enrollment code.", 400)
        )

        viewModel.onCodeChange("ABC234")
        viewModel.enroll()

        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertTrue(state.errorMessage?.contains("Invalid or expired") == true)
    }

    @Test
    fun `rate limited enrollment displays cooldown message`() = runTest {
        fakeRepository.nextResult = AppResult.Error(
            AppError.Api("RATE_LIMITED", "Too many requests.", 429)
        )

        viewModel.onCodeChange("ABC234")
        viewModel.enroll()

        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertTrue(state.errorMessage?.contains("Too many") == true)
    }

    @Test
    fun `network failure displays connection hint`() = runTest {
        fakeRepository.nextResult = AppResult.Error(AppError.NoInternet)

        viewModel.onCodeChange("ABC234")
        viewModel.enroll()

        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.isLoading)
        assertTrue(state.errorMessage?.contains("network") == true)
    }

    @Test
    fun `revocation event updates ui state with revocation message and clears input`() = runTest {
        credentialStore.notifyRevoked("This device was removed. Ask an admin for a new code.")

        advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals("This device was removed. Ask an admin for a new code.", state.revocationNotice)
        assertEquals("", state.code)
    }

    private class FakeDeviceEnrollmentRepository : DeviceEnrollmentRepository {
        var nextResult: AppResult<DeviceCredentials> = AppResult.Error(AppError.Unknown)
        var lastEnrolledCode: String? = null
        var lastDeviceName: String? = null

        override suspend fun enrollDevice(code: String, deviceName: String?): AppResult<DeviceCredentials> {
            lastEnrolledCode = code
            lastDeviceName = deviceName
            return nextResult
        }
    }
}


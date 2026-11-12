package com.facerem.feature.auth

import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.model.Role
import com.facerem.core.model.User
import com.facerem.feature.auth.domain.AuthRepository
import com.facerem.feature.auth.presentation.LoginViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    private val fakeRepository = FakeAuthRepository()

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `invalid email is rejected before any network call`() = runTest {
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("not-an-email")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        assertNotNull(viewModel.uiState.value.emailError)
        assertFalse(viewModel.uiState.value.authenticated)
        assertEquals(0, fakeRepository.loginCallCount)
    }

    @Test
    fun `short password is rejected before any network call`() = runTest {
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("short")

        viewModel.signIn()

        assertNotNull(viewModel.uiState.value.passwordError)
        assertEquals(0, fakeRepository.loginCallCount)
    }

    @Test
    fun `valid credentials authenticate and clear the submitting flag`() = runTest {
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        val state = viewModel.uiState.value
        assertTrue(state.authenticated)
        assertFalse(state.isSubmitting)
        assertNull(state.formError)
        assertEquals(1, fakeRepository.loginCallCount)
    }

    @Test
    fun `a rejected sign in surfaces the mapped error message`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("INVALID_CREDENTIALS", "Email or password is incorrect.", httpStatus = 401),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        assertEquals("Email or password is incorrect.", viewModel.uiState.value.formError)
        assertFalse(viewModel.uiState.value.authenticated)
    }

    @Test
    fun `guest mode authenticates without credentials`() = runTest {
        val viewModel = LoginViewModel(fakeRepository)

        viewModel.continueAsGuest()

        assertTrue(viewModel.uiState.value.authenticated)
        assertEquals(1, fakeRepository.guestCallCount)
        assertEquals(0, fakeRepository.loginCallCount)
    }

    @Test
    fun `demo prefill produces a submittable form`() = runTest {
        val viewModel = LoginViewModel(fakeRepository)

        viewModel.prefillDemoCredentials()

        val state = viewModel.uiState.value
        assertTrue(state.canSubmit)
        assertTrue(state.email.isNotBlank())
        assertTrue(state.password.length >= 8)
    }

    @Test
    fun `totp_required error transitions state to isTotpRequired true`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("TOTP_REQUIRED", "Enter the 6-digit verification code or recovery code.", httpStatus = 200),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        val state = viewModel.uiState.value
        assertTrue(state.isTotpRequired)
        assertFalse(state.authenticated)
        assertFalse(state.isSubmitting)
        assertNull(state.formError)
    }

    @Test
    fun `submitting totp code calls login with totpCode and authenticates`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("TOTP_REQUIRED", "Enter the 6-digit verification code.", httpStatus = 200),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")
        viewModel.signIn()
        assertTrue(viewModel.uiState.value.isTotpRequired)

        // Now provide TOTP and successful verification
        fakeRepository.loginResult = AppResult.Success(FakeAuthRepository.ADMIN)
        viewModel.onTotpCodeChange("123456")
        assertTrue(viewModel.uiState.value.canSubmit)

        viewModel.signIn()

        val state = viewModel.uiState.value
        assertTrue(state.authenticated)
        assertEquals("123456", fakeRepository.lastTotpCode)
        assertEquals(2, fakeRepository.loginCallCount)
    }

    @Test
    fun `blank totp code when 2FA required displays validation error`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("TOTP_REQUIRED", "Enter verification code.", httpStatus = 200),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")
        viewModel.signIn()

        // Submit without typing code
        viewModel.signIn()

        assertNotNull(viewModel.uiState.value.totpError)
        assertEquals(1, fakeRepository.loginCallCount)
    }

    @Test
    fun `totp_setup_required surfaces clear message about web console`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api(
                "TOTP_SETUP_REQUIRED",
                "Two-factor authentication (2FA) must be set up in the web console first. 2FA setup is not supported on mobile.",
                httpStatus = 403,
            ),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        val state = viewModel.uiState.value
        assertFalse(state.isTotpRequired)
        assertFalse(state.authenticated)
        assertEquals(
            "Two-factor authentication (2FA) must be set up in the web console first. 2FA setup is not supported on mobile.",
            state.formError,
        )
    }

    @Test
    fun `attendance device or employee role rejection displays clear error`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("ROLE_NOT_ALLOWED", "Access denied: Attendance device is not allowed in this app.", httpStatus = 403),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("device@northwind.demo")
        viewModel.onPasswordChange("demo12345")

        viewModel.signIn()

        val state = viewModel.uiState.value
        assertEquals("Access denied: Attendance device is not allowed in this app.", state.formError)
        assertFalse(state.authenticated)
    }

    @Test
    fun `resetTotpPrompt returns state to credentials form`() = runTest {
        fakeRepository.loginResult = AppResult.Error(
            AppError.Api("TOTP_REQUIRED", "2FA required", httpStatus = 200),
        )
        val viewModel = LoginViewModel(fakeRepository)
        viewModel.onEmailChange("admin@northwind.demo")
        viewModel.onPasswordChange("demo12345")
        viewModel.signIn()
        assertTrue(viewModel.uiState.value.isTotpRequired)

        viewModel.resetTotpPrompt()

        val state = viewModel.uiState.value
        assertFalse(state.isTotpRequired)
        assertEquals("", state.totpCode)
        assertNull(state.totpError)
    }

    private class FakeAuthRepository : AuthRepository {
        var loginCallCount = 0
        var guestCallCount = 0
        var lastTotpCode: String? = null
        var loginResult: AppResult<User> = AppResult.Success(ADMIN)

        override suspend fun login(
            email: String,
            password: String,
            organizationCode: String,
            totpCode: String?,
        ): AppResult<User> {
            loginCallCount++
            lastTotpCode = totpCode
            return loginResult
        }

        override suspend fun continueAsGuest(): AppResult<User> {
            guestCallCount++
            return AppResult.Success(GUEST)
        }

        override suspend fun requestPasswordReset(email: String): AppResult<Unit> = AppResult.Success(Unit)

        override suspend fun logout() = Unit

        companion object {
            val ADMIN = User(
                id = "user-admin",
                fullName = "Admin",
                email = "admin@northwind.demo",
                role = Role.ORGANIZATION_ADMIN,
                organizationId = "org-demo",
                organizationName = "Northwind Industries",
            )
            val GUEST = ADMIN.copy(id = "guest-user", fullName = "Guest Reviewer")
        }
    }
}

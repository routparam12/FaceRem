package com.facerem.feature.faceenrollment

import androidx.lifecycle.SavedStateHandle
import com.facerem.app.navigation.AppRoute
import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.common.AppError
import com.facerem.core.common.AppResult
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Branch
import com.facerem.core.model.Department
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.Shift
import com.facerem.feature.employees.domain.EmployeeRepository
import com.facerem.feature.employees.domain.NewEmployee
import com.facerem.feature.faceenrollment.presentation.FaceEnrollmentViewModel
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
class FaceEnrollmentViewModelTest {

    private val fakeRepository = FakeEmployeeRepository()
    private val testDispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun createViewModel(employeeId: String = "emp-test-1"): FaceEnrollmentViewModel {
        val savedStateHandle = SavedStateHandle(mapOf(AppRoute.EmployeeIdArg to employeeId))
        return FaceEnrollmentViewModel(fakeRepository, savedStateHandle)
    }

    @Test
    fun `frame capture on each pose transition accumulates all three poses`() = runTest {
        val viewModel = createViewModel()
        viewModel.onConsentChange(true)

        val dummyJpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte())
        var captureCallCount = 0
        val captureMock: suspend () -> ByteArray? = {
            captureCallCount++
            dummyJpeg
        }

        // Initially no captured frames
        assertEquals(0, viewModel.uiState.value.capturedPoses)
        assertEquals(0, viewModel.uiState.value.capturedFrames.size)
        assertEquals(FaceQualityEvaluator.HeadPose.FRONT, viewModel.uiState.value.currentPose)
        assertFalse(viewModel.uiState.value.allPosesCaptured)

        // Pose 1: FRONT -> 8 stable frames
        repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
            viewModel.onQuality(FaceQualityStatus.VALID, captureMock)
        }
        assertEquals(1, viewModel.uiState.value.capturedPoses)
        assertEquals(1, viewModel.uiState.value.capturedFrames.size)
        assertTrue(viewModel.uiState.value.capturedFrames.containsKey(FaceQualityEvaluator.HeadPose.FRONT))
        assertEquals(FaceQualityEvaluator.HeadPose.SLIGHT_LEFT, viewModel.uiState.value.currentPose)
        assertEquals(1, captureCallCount)

        // Pose 2: SLIGHT_LEFT -> 8 stable frames
        repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
            viewModel.onQuality(FaceQualityStatus.VALID, captureMock)
        }
        assertEquals(2, viewModel.uiState.value.capturedPoses)
        assertEquals(2, viewModel.uiState.value.capturedFrames.size)
        assertTrue(viewModel.uiState.value.capturedFrames.containsKey(FaceQualityEvaluator.HeadPose.SLIGHT_LEFT))
        assertEquals(FaceQualityEvaluator.HeadPose.SLIGHT_RIGHT, viewModel.uiState.value.currentPose)
        assertEquals(2, captureCallCount)

        // Pose 3: SLIGHT_RIGHT -> 8 stable frames
        repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
            viewModel.onQuality(FaceQualityStatus.VALID, captureMock)
        }
        assertEquals(3, viewModel.uiState.value.capturedPoses)
        assertEquals(3, viewModel.uiState.value.capturedFrames.size)
        assertTrue(viewModel.uiState.value.capturedFrames.containsKey(FaceQualityEvaluator.HeadPose.SLIGHT_RIGHT))
        assertTrue(viewModel.uiState.value.allPosesCaptured)
        assertEquals(3, captureCallCount)
    }

    @Test
    fun `camera not released prematurely during capture or after submit error`() = runTest {
        val viewModel = createViewModel()
        viewModel.onConsentChange(true)

        val dummyJpeg = byteArrayOf(1, 2, 3)

        // Camera must remain active when starting capture
        assertTrue("Camera must be active during capture", viewModel.uiState.value.isCameraActive)

        // Capture all 3 poses
        repeat(3) {
            repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
                viewModel.onQuality(FaceQualityStatus.VALID, { dummyJpeg })
            }
        }
        assertTrue(viewModel.uiState.value.allPosesCaptured)

        // Camera must still be active when all poses are captured (ready to submit)
        assertTrue("Camera must not be released when poses complete", viewModel.uiState.value.isCameraActive)

        // Simulate failure on submit
        fakeRepository.submitResult = AppResult.Error(
            AppError.Api("CONNECTION_ERROR", "Server timed out", 504),
        )
        viewModel.submit()

        assertFalse(viewModel.uiState.value.isSubmitting)
        assertNotNull(viewModel.uiState.value.errorMessage)
        // Camera must remain active after submission error
        assertTrue("Camera must remain active after submission failure", viewModel.uiState.value.isCameraActive)

        // When submit succeeds, isCameraActive becomes false (screen navigates to Complete)
        fakeRepository.submitResult = AppResult.Success(FaceEnrollmentStatus.ENROLLED)
        viewModel.submit()
        assertTrue(viewModel.uiState.value.isComplete)
        assertFalse("Camera is released when enrollment completes", viewModel.uiState.value.isCameraActive)
    }

    @Test
    fun `retry on submission failure retains captured frames`() = runTest {
        val viewModel = createViewModel()
        viewModel.onConsentChange(true)

        val dummyJpeg = byteArrayOf(10, 20, 30)
        repeat(3) {
            repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
                viewModel.onQuality(FaceQualityStatus.VALID, { dummyJpeg })
            }
        }
        assertEquals(3, viewModel.uiState.value.capturedFrames.size)
        assertEquals(3, viewModel.uiState.value.capturedPoses)

        // First attempt fails
        fakeRepository.submitResult = AppResult.Error(
            AppError.Api("NETWORK_ERROR", "Temporary network failure", 503),
        )
        viewModel.submit()

        assertEquals("Temporary network failure", viewModel.uiState.value.errorMessage)
        assertFalse(viewModel.uiState.value.isComplete)
        // Captured frames and poses must be preserved!
        assertEquals(3, viewModel.uiState.value.capturedFrames.size)
        assertEquals(3, viewModel.uiState.value.capturedPoses)
        assertTrue(viewModel.uiState.value.allPosesCaptured)

        // Retry succeeds without re-capturing
        fakeRepository.submitResult = AppResult.Success(FaceEnrollmentStatus.ENROLLED)
        viewModel.submit()

        assertTrue(viewModel.uiState.value.isComplete)
        assertNull(viewModel.uiState.value.errorMessage)
        assertEquals(2, fakeRepository.submitCallCount)
    }

    @Test
    fun `blocked submit with fewer than 3 frames`() = runTest {
        val viewModel = createViewModel()
        viewModel.onConsentChange(true)

        val dummyJpeg = byteArrayOf(1, 2)

        // Capture only 2 poses
        repeat(2) {
            repeat(FaceEnrollmentViewModel.REQUIRED_STABLE_FRAMES) {
                viewModel.onQuality(FaceQualityStatus.VALID, { dummyJpeg })
            }
        }
        assertEquals(2, viewModel.uiState.value.capturedFrames.size)
        assertFalse(viewModel.uiState.value.allPosesCaptured)

        // Submit should be a no-op
        viewModel.submit()

        assertFalse("Must not transition to submitting", viewModel.uiState.value.isSubmitting)
        assertFalse("Must not complete", viewModel.uiState.value.isComplete)
        assertEquals(0, fakeRepository.submitCallCount)
    }

    private class FakeEmployeeRepository : EmployeeRepository {
        var submitCallCount = 0
        var submitResult: AppResult<FaceEnrollmentStatus> = AppResult.Success(FaceEnrollmentStatus.ENROLLED)
        var lastSubmittedFrames: Map<FaceQualityEvaluator.HeadPose, ByteArray>? = null

        override suspend fun loadEmployees(): AppResult<List<Employee>> = AppResult.Success(emptyList())

        override suspend fun employee(id: String): AppResult<Employee> = AppResult.Success(
            Employee(
                id = id,
                employeeCode = "NW-1001",
                fullName = "Test Employee",
                email = "test@northwind.demo",
                phone = "555-0100",
                department = "Engineering",
                branch = "HQ",
                jobTitle = "Developer",
                shiftName = "General",
                faceEnrollment = FaceEnrollmentStatus.PENDING,
                isActive = true,
            ),
        )

        override suspend fun createEmployee(employee: NewEmployee): AppResult<Employee> =
            error("Not needed for test")

        override suspend fun submitFaceEnrollment(
            employeeId: String,
            frames: Map<FaceQualityEvaluator.HeadPose, ByteArray>,
        ): AppResult<FaceEnrollmentStatus> {
            submitCallCount++
            lastSubmittedFrames = frames
            return submitResult
        }

        override suspend fun attendanceFor(employeeId: String): AppResult<List<AttendanceRecord>> =
            AppResult.Success(emptyList())

        override suspend fun departments(): List<Department> = emptyList()

        override suspend fun branches(): List<Branch> = emptyList()

        override suspend fun shifts(): List<Shift> = emptyList()
    }
}


package com.facerem.kiosk.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.facerem.core.security.DeviceCredentialStore
import com.facerem.core.security.DeviceCredentials
import com.facerem.kiosk.enrollment.KioskEnrollmentRoute
import com.facerem.kiosk.scan.KioskScanPlaceholderScreen
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.StateFlow

@HiltViewModel
class KioskNavViewModel @Inject constructor(
    private val credentialStore: DeviceCredentialStore,
) : ViewModel() {
    val credentials: StateFlow<DeviceCredentials?> = credentialStore.credentials
    val revocationEvents = credentialStore.revocationEvents
}

@Composable
fun KioskNavHost(
    modifier: Modifier = Modifier,
    navController: NavHostController = rememberNavController(),
    viewModel: KioskNavViewModel = hiltViewModel(),
) {
    val credentials by viewModel.credentials.collectAsStateWithLifecycle()
    val isEnrolled = credentials != null

    val startDestination = if (isEnrolled) KioskRoute.Scan else KioskRoute.Enrollment

    LaunchedEffect(viewModel) {
        viewModel.revocationEvents.collect {
            navController.navigate(KioskRoute.Enrollment) {
                popUpTo(0) { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
    ) {
        composable(KioskRoute.Enrollment) {
            KioskEnrollmentRoute(
                onEnrolled = {
                    navController.navigate(KioskRoute.Scan) {
                        popUpTo(KioskRoute.Enrollment) { inclusive = true }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(KioskRoute.Scan) {
            KioskScanPlaceholderScreen(
                credentials = credentials,
            )
        }
    }
}


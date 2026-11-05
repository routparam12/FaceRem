package com.facerem.app.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.facerem.feature.attendance.presentation.ScanRoute
import com.facerem.feature.auth.presentation.ForgotPasswordRoute
import com.facerem.feature.auth.presentation.LoginRoute
import com.facerem.feature.auth.presentation.OnboardingRoute
import com.facerem.feature.auth.presentation.SplashRoute
import com.facerem.feature.employees.presentation.AddEmployeeRoute
import com.facerem.feature.employees.presentation.EmployeeDetailRoute
import com.facerem.feature.faceenrollment.presentation.FaceEnrollmentRoute
import com.facerem.feature.reports.presentation.ReportsRoute
import com.facerem.feature.settings.presentation.NotificationsRoute
import com.facerem.feature.settings.presentation.PrivacyRoute
import com.facerem.feature.settings.presentation.ProfileRoute

private const val TRANSITION_MILLIS = 280

@Composable
fun AppNavHost(navController: NavHostController) {
    NavHost(
        navController = navController,
        startDestination = AppRoute.Splash,
        enterTransition = {
            slideInHorizontally(tween(TRANSITION_MILLIS)) { it / 6 } + fadeIn(tween(TRANSITION_MILLIS))
        },
        exitTransition = { fadeOut(tween(TRANSITION_MILLIS)) },
        popEnterTransition = { fadeIn(tween(TRANSITION_MILLIS)) },
        popExitTransition = {
            slideOutHorizontally(tween(TRANSITION_MILLIS)) { it / 6 } + fadeOut(tween(TRANSITION_MILLIS))
        },
    ) {
        composable(AppRoute.Splash) {
            SplashRoute(
                onNavigate = { destination ->
                    navController.navigate(destination) {
                        popUpTo(AppRoute.Splash) { inclusive = true }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(AppRoute.Onboarding) {
            OnboardingRoute(
                onFinished = {
                    navController.navigate(AppRoute.Login) {
                        popUpTo(AppRoute.Onboarding) { inclusive = true }
                    }
                },
            )
        }

        composable(AppRoute.Login) {
            LoginRoute(
                onAuthenticated = {
                    navController.navigate(AppRoute.Main) {
                        popUpTo(AppRoute.Login) { inclusive = true }
                    }
                },
                onForgotPassword = { navController.navigate(AppRoute.ForgotPassword) },
            )
        }

        composable(AppRoute.ForgotPassword) {
            ForgotPasswordRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Main) {
            MainShell(
                onSignedOut = {
                    navController.navigate(AppRoute.Login) {
                        popUpTo(navController.graph.id) { inclusive = true }
                    }
                },
                onOpenDestination = navController::navigate,
            )
        }

        composable(AppRoute.AddEmployee) {
            AddEmployeeRoute(
                onNavigateUp = navController::popBackStack,
                onEmployeeCreated = { employeeId ->
                    navController.navigate(AppRoute.faceEnrollment(employeeId)) {
                        popUpTo(AppRoute.AddEmployee) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = AppRoute.EmployeeDetail,
            arguments = listOf(navArgument(AppRoute.EmployeeIdArg) { type = NavType.StringType }),
        ) {
            EmployeeDetailRoute(
                onNavigateUp = navController::popBackStack,
                onEnrollFace = { employeeId -> navController.navigate(AppRoute.faceEnrollment(employeeId)) },
            )
        }

        composable(
            route = AppRoute.FaceEnrollment,
            arguments = listOf(navArgument(AppRoute.EmployeeIdArg) { type = NavType.StringType }),
        ) {
            FaceEnrollmentRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Scan) {
            ScanRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Reports) {
            ReportsRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Profile) {
            ProfileRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Notifications) {
            NotificationsRoute(onNavigateUp = navController::popBackStack)
        }

        composable(AppRoute.Privacy) {
            PrivacyRoute(onNavigateUp = navController::popBackStack)
        }
    }
}

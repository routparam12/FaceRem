package com.facerem.app.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Route names. Sensitive records are fetched by id after authorization rather than passed
 * through navigation arguments.
 */
object AppRoute {
    const val Splash = "splash"
    const val Onboarding = "onboarding"
    const val Login = "login"
    const val ForgotPassword = "forgot_password"

    /** Container for the bottom-navigation experience. */
    const val Main = "main"

    const val Dashboard = "dashboard"
    const val Employees = "employees"
    const val Scan = "scan"
    const val History = "history"
    const val Settings = "settings"

    const val Reports = "reports"
    const val Profile = "profile"
    const val Notifications = "notifications"
    const val AddEmployee = "employees/new"
    const val Privacy = "privacy"

    const val EmployeeIdArg = "employeeId"
    const val EmployeeDetail = "employees/{$EmployeeIdArg}"
    const val FaceEnrollment = "face-enrollment/{$EmployeeIdArg}"

    fun employeeDetail(employeeId: String) = "employees/$employeeId"

    fun faceEnrollment(employeeId: String) = "face-enrollment/$employeeId"
}

enum class MainTab(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    Dashboard(AppRoute.Dashboard, "Home", Icons.Default.Home),
    Employees(AppRoute.Employees, "People", Icons.Default.Groups),
    History(AppRoute.History, "History", Icons.Default.History),
    Settings(AppRoute.Settings, "Settings", Icons.Default.Settings),
}

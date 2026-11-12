package com.facerem.app.navigation

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FaceRetouchingNatural
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.facerem.feature.dashboard.presentation.DashboardRoute
import com.facerem.feature.employees.presentation.EmployeesRoute
import com.facerem.feature.faceenrollment.presentation.EmployeePickerSheet
import com.facerem.feature.history.presentation.HistoryRoute
import com.facerem.feature.settings.presentation.SettingsRoute
import com.facerem.ui.theme.Glass

import androidx.compose.material3.ExperimentalMaterial3Api

/**
 * Bottom-navigation container. Tab switching lives in a nested graph so the root back stack keeps
 * modal flows (face enrollment, employee detail) above the shell.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainShell(
    onSignedOut: () -> Unit,
    onOpenDestination: (String) -> Unit,
    viewModel: MainShellViewModel = hiltViewModel(),
) {
    val tabController = rememberNavController()
    val backStackEntry by tabController.currentBackStackEntryAsState()
    val currentDestination = backStackEntry?.destination

    val currentUser by viewModel.currentUser.collectAsStateWithLifecycle()
    val employees by viewModel.employees.collectAsStateWithLifecycle()
    val isLoadingEmployees by viewModel.isLoadingEmployees.collectAsStateWithLifecycle()
    val canEnrollFaces = currentUser?.role?.canEnrollFaces == true
    var showEmployeePicker by remember { mutableStateOf(false) }

    val openFaceEnrollmentPicker = {
        viewModel.loadEmployees()
        showEmployeePicker = true
    }

    Box(modifier = Modifier.fillMaxSize()) {
        NavHost(
            navController = tabController,
            startDestination = AppRoute.Dashboard,
            modifier = Modifier.fillMaxSize(),
            enterTransition = { fadeIn(tween(200)) },
            exitTransition = { fadeOut(tween(200)) },
        ) {
            composable(AppRoute.Dashboard) {
                DashboardRoute(
                    onEnrollFace = openFaceEnrollmentPicker,
                    onOpenEmployees = { tabController.navigateToTab(AppRoute.Employees) },
                    onOpenHistory = { tabController.navigateToTab(AppRoute.History) },
                    onOpenReports = { onOpenDestination(AppRoute.Reports) },
                    onOpenNotifications = { onOpenDestination(AppRoute.Notifications) },
                    onOpenProfile = { onOpenDestination(AppRoute.Profile) },
                )
            }
            composable(AppRoute.Employees) {
                EmployeesRoute(
                    onOpenEmployee = { employeeId -> onOpenDestination(AppRoute.employeeDetail(employeeId)) },
                    onAddEmployee = { onOpenDestination(AppRoute.AddEmployee) },
                )
            }
            composable(AppRoute.History) {
                HistoryRoute(onOpenReports = { onOpenDestination(AppRoute.Reports) })
            }
            composable(AppRoute.Settings) {
                SettingsRoute(
                    onSignedOut = onSignedOut,
                    onOpenProfile = { onOpenDestination(AppRoute.Profile) },
                    onOpenReports = { onOpenDestination(AppRoute.Reports) },
                    onOpenNotifications = { onOpenDestination(AppRoute.Notifications) },
                    onOpenPrivacy = { onOpenDestination(AppRoute.Privacy) },
                )
            }
        }

        FloatingNavBar(
            currentDestination = currentDestination,
            canEnrollFaces = canEnrollFaces,
            onSelectTab = { tab ->
                tabController.navigate(tab.route) {
                    popUpTo(tabController.graph.findStartDestination().id) { saveState = true }
                    launchSingleTop = true
                    restoreState = true
                }
            },
            onEnrollFace = openFaceEnrollmentPicker,
            modifier = Modifier.align(Alignment.BottomCenter),
        )

        if (showEmployeePicker) {
            EmployeePickerSheet(
                employees = employees,
                isLoading = isLoadingEmployees,
                onDismissRequest = { showEmployeePicker = false },
                onSelectEmployee = { employeeId ->
                    showEmployeePicker = false
                    onOpenDestination(AppRoute.faceEnrollment(employeeId))
                },
            )
        }
    }
}

private fun androidx.navigation.NavHostController.navigateToTab(route: String) {
    navigate(route) {
        popUpTo(graph.findStartDestination().id) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

/**
 * Bottom padding a tab screen needs so its last row clears the floating bar.
 *
 * The bar overlays the content, so nothing reserves this space automatically.
 */
val BottomBarClearance = 116.dp

/** How far the center button is lifted clear of the bar. */
private val ScanLift = 32.dp
private val ScanSize = 64.dp
private val BarHeight = 64.dp

/**
 * The bottom bar, drawn as a floating pill with the center action raised out of it for admins.
 */
@Composable
private fun FloatingNavBar(
    currentDestination: NavDestination?,
    canEnrollFaces: Boolean,
    onSelectTab: (MainTab) -> Unit,
    onEnrollFace: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(top = if (canEnrollFaces) ScanLift + 12.dp else 12.dp)
            .navigationBarsPadding()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        contentAlignment = Alignment.BottomCenter,
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .height(BarHeight),
            shape = RoundedCornerShape(22.dp),
            color = if (Glass.isActive) Glass.tokens.overlay
            else MaterialTheme.colorScheme.surfaceContainer,
            shadowElevation = 10.dp,
            tonalElevation = 0.dp,
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (canEnrollFaces) {
                    MainTab.entries.take(2).forEach { tab ->
                        NavTab(tab, currentDestination, onSelectTab, Modifier.weight(1f))
                    }
                    Spacer(Modifier.width(ScanSize + 16.dp))
                    MainTab.entries.drop(2).forEach { tab ->
                        NavTab(tab, currentDestination, onSelectTab, Modifier.weight(1f))
                    }
                } else {
                    MainTab.entries.forEach { tab ->
                        NavTab(tab, currentDestination, onSelectTab, Modifier.weight(1f))
                    }
                }
            }
        }

        if (canEnrollFaces) {
            Box(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .offset(y = -ScanLift)
                    .size(ScanSize + 12.dp)
                    .clip(CircleShape)
                    .background(
                        if (Glass.isActive) Glass.tokens.cutout
                        else MaterialTheme.colorScheme.background,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Surface(
                    onClick = onEnrollFace,
                    modifier = Modifier.size(ScanSize),
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                    shadowElevation = 8.dp,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            Icons.Default.FaceRetouchingNatural,
                            contentDescription = "Enroll face",
                            modifier = Modifier.size(28.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun NavTab(
    tab: MainTab,
    currentDestination: NavDestination?,
    onSelect: (MainTab) -> Unit,
    modifier: Modifier = Modifier,
) {
    val selected = currentDestination?.hierarchy?.any { it.route == tab.route } == true
    val tint by animateColorAsState(
        targetValue = if (selected) MaterialTheme.colorScheme.primary
        else MaterialTheme.colorScheme.onSurfaceVariant,
        label = "nav-tint-${tab.route}",
    )

    Column(
        modifier = modifier
            .fillMaxHeight()
            .clip(RoundedCornerShape(16.dp))
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = ripple(bounded = false, radius = 28.dp),
                onClick = { onSelect(tab) },
            ),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(tab.icon, contentDescription = tab.label, tint = tint, modifier = Modifier.size(22.dp))
        Spacer(Modifier.height(3.dp))
        Text(
            tab.label,
            color = tint,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
        )
    }
}

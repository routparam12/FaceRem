package com.facerem.feature.settings.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.InsertChart
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PrivacyTip
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.app.navigation.BottomBarClearance
import com.facerem.core.datastore.ThemeMode
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.ConfirmationDialog
import com.facerem.core.designsystem.component.GuestModeBanner
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.core.designsystem.component.SettingRow
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.ui.theme.Spacing

@Composable
fun SettingsRoute(
    onSignedOut: () -> Unit,
    onOpenProfile: () -> Unit,
    onOpenReports: () -> Unit,
    onOpenNotifications: () -> Unit,
    onOpenPrivacy: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.isSignedOut) {
        if (uiState.isSignedOut) onSignedOut()
    }

    if (uiState.showSignOutDialog) {
        ConfirmationDialog(
            title = if (uiState.isGuest) "Leave guest mode?" else "Sign out?",
            message = if (uiState.isGuest) {
                "The sample data on this device will be cleared and you'll return to sign in."
            } else {
                "You'll need to sign in again to access your organization's attendance data."
            },
            confirmText = if (uiState.isGuest) "Leave" else "Sign out",
            onConfirm = viewModel::confirmSignOut,
            onDismiss = viewModel::onSignOutDismissed,
        )
    }

    Scaffold(topBar = { AppTopBar(title = "Settings") }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
        ) {
            if (uiState.isGuest) {
                GuestModeBanner()
                Spacer(Modifier.height(Spacing.md))
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = Spacing.md),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                UserAvatar(name = uiState.user?.fullName.orEmpty(), size = 56.dp)
                Spacer(Modifier.width(Spacing.lg))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        uiState.user?.fullName.orEmpty().ifBlank { "Signed in" },
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        uiState.user?.email.orEmpty(),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        uiState.user?.role?.displayName.orEmpty(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Spacer(Modifier.height(Spacing.md))

            SectionHeader(title = "Account")
            SettingRow(
                title = "Profile",
                subtitle = "Name, contact details and role",
                icon = Icons.Default.Person,
                onClick = onOpenProfile,
            )
            SettingRow(
                title = "Organization",
                subtitle = uiState.user?.organizationName.orEmpty().ifBlank { "Not set" },
                icon = Icons.Default.Apartment,
                onClick = onOpenProfile,
            )

            Spacer(Modifier.height(Spacing.lg))
            SectionHeader(title = "Workspace")
            SettingRow(
                title = "Reports",
                subtitle = "Attendance rate, overtime and exports",
                icon = Icons.Default.InsertChart,
                onClick = onOpenReports,
            )
            SettingRow(
                title = "Shifts and attendance rules",
                subtitle = "Grace period, overtime and late thresholds",
                icon = Icons.Default.Schedule,
                onClick = onOpenProfile,
            )
            SettingRow(
                title = "Notifications",
                subtitle = "Alerts for late arrivals and enrollment",
                icon = Icons.Default.Notifications,
                onClick = onOpenNotifications,
            )

            Spacer(Modifier.height(Spacing.lg))
            SectionHeader(title = "Appearance")
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SettingRow(
                    title = "Theme",
                    subtitle = "Follow system, always light or always dark",
                    icon = Icons.Default.DarkMode,
                    onClick = {},
                    trailing = { },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                verticalArrangement = Arrangement.spacedBy(Spacing.sm),
                modifier = Modifier.padding(start = 56.dp, bottom = Spacing.sm),
            ) {
                ThemeMode.entries.forEach { mode ->
                    FilterChip(
                        selected = uiState.themeMode == mode,
                        onClick = { viewModel.onThemeModeChange(mode) },
                        label = { Text(mode.label()) },
                    )
                }
            }

            Spacer(Modifier.height(Spacing.lg))
            SectionHeader(title = "Privacy and security")
            SettingRow(
                title = "Biometric data policy",
                subtitle = "Consent, retention and face-profile removal",
                icon = Icons.Default.PrivacyTip,
                onClick = onOpenPrivacy,
            )

            Spacer(Modifier.height(Spacing.lg))
            SettingRow(
                title = if (uiState.isGuest) "Leave guest mode" else "Sign out",
                subtitle = uiState.user?.email.orEmpty(),
                icon = Icons.AutoMirrored.Filled.Logout,
                onClick = viewModel::onSignOutRequested,
                trailing = { },
            )

            Spacer(Modifier.height(Spacing.xl))
            Text(
                "FaceAttend • version 1.0",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(BottomBarClearance))
        }
    }
}

private fun ThemeMode.label(): String = when (this) {
    ThemeMode.SYSTEM -> "System"
    ThemeMode.LIGHT -> "Light"
    ThemeMode.DARK -> "Dark"
    ThemeMode.LIQUID_GLASS -> "Liquid glass"
}

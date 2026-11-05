package com.facerem.feature.settings.presentation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.Public
import androidx.compose.material.icons.filled.Workspaces
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.GuestModeBanner
import com.facerem.core.designsystem.component.InfoRow
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.ui.theme.Spacing

@Composable
fun ProfileRoute(
    onNavigateUp: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = { AppTopBar(title = "Profile", onNavigateUp = onNavigateUp) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (uiState.isGuest) {
                GuestModeBanner()
                Spacer(Modifier.height(Spacing.md))
            }

            Spacer(Modifier.height(Spacing.lg))
            UserAvatar(name = uiState.user?.fullName.orEmpty(), size = 88.dp)
            Spacer(Modifier.height(Spacing.md))
            Text(
                uiState.user?.fullName.orEmpty().ifBlank { "Signed in" },
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                uiState.user?.role?.displayName.orEmpty(),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(Spacing.xl))
            SectionHeader(title = "Account", modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(Spacing.sm))
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.large,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(Spacing.lg)) {
                    InfoRow("Email", uiState.user?.email.orEmpty(), icon = Icons.Default.MailOutline)
                    InfoRow("Role", uiState.user?.role?.displayName.orEmpty(), icon = Icons.Default.Badge)
                }
            }

            Spacer(Modifier.height(Spacing.lg))
            SectionHeader(title = "Organization", modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(Spacing.sm))
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.large,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(Spacing.lg)) {
                    InfoRow("Name", uiState.organizationName, icon = Icons.Default.Apartment)
                    InfoRow("Plan", uiState.planLabel, icon = Icons.Default.Workspaces)
                    InfoRow("Branches", uiState.branchCount.toString(), icon = Icons.Default.Public)
                    InfoRow("Time zone", uiState.timeZone, icon = Icons.Default.Public)
                }
            }

            Spacer(Modifier.height(Spacing.lg))
            Text(
                "Profile edits are made by an organization administrator. Contact them to change " +
                    "your role, department or shift.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(Spacing.xxl))
        }
    }
}

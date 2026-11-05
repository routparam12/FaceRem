package com.facerem.feature.settings.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.background
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.FaceRetouchingNatural
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.ui.theme.AppTheme
import com.facerem.ui.theme.Spacing

private data class NotificationItem(
    val id: String,
    val title: String,
    val body: String,
    val timeLabel: String,
    val icon: ImageVector,
)

@Composable
fun NotificationsRoute(onNavigateUp: () -> Unit) {
    val semantic = AppTheme.colors
    val items = listOf(
        NotificationItem(
            id = "n1",
            title = "3 employees still need face enrollment",
            body = "Enrollment must be completed before they can use the scanner.",
            timeLabel = "Today",
            icon = Icons.Default.FaceRetouchingNatural,
        ),
        NotificationItem(
            id = "n2",
            title = "Late arrivals above average",
            body = "Operations recorded 6 late check-ins this week.",
            timeLabel = "Today",
            icon = Icons.Default.Schedule,
        ),
        NotificationItem(
            id = "n3",
            title = "2 leave requests awaiting approval",
            body = "Approve or decline before the shift roster is published.",
            timeLabel = "Yesterday",
            icon = Icons.Default.EventBusy,
        ),
    )
    val accents = listOf(MaterialTheme.colorScheme.primary, semantic.warning, semantic.info)

    Scaffold(
        topBar = { AppTopBar(title = "Notifications", onNavigateUp = onNavigateUp) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(
                start = Spacing.screenHorizontal,
                end = Spacing.screenHorizontal,
                bottom = Spacing.xxl,
            ),
            verticalArrangement = Arrangement.spacedBy(Spacing.lg),
        ) {
            items(items, key = { it.id }) { item ->
                val accent = accents[items.indexOf(item) % accents.size]
                NotificationRow(item = item, accent = accent)
            }
        }
    }
}

@Composable
private fun NotificationRow(item: NotificationItem, accent: Color) {
    Row(modifier = Modifier.fillMaxWidth()) {
        androidx.compose.foundation.layout.Box(
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(accent.copy(alpha = 0.14f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(item.icon, contentDescription = null, tint = accent, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.width(Spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(item.title, style = MaterialTheme.typography.bodyLarge)
            Text(
                item.body,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.padding(top = Spacing.xs))
            Text(
                item.timeLabel,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

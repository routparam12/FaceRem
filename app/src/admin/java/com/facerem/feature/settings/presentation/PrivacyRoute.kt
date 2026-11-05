package com.facerem.feature.settings.presentation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.ui.theme.Spacing

private data class PolicySection(val title: String, val body: String)

private val policySections = listOf(
    PolicySection(
        title = "What is stored",
        body = "The server stores a mathematical face embedding derived from enrollment images, " +
            "along with the model name, model version and a quality score. Photographs are not " +
            "kept after an embedding is produced.",
    ),
    PolicySection(
        title = "Who can see it",
        body = "Face profiles belong to a single organization. Every face search is filtered to the " +
            "requesting organization before any similarity matching runs, and access is checked on " +
            "the server for every request.",
    ),
    PolicySection(
        title = "Consent",
        body = "Enrollment requires explicit consent from the employee. The consent and its " +
            "timestamp are written to the audit log, and consent can be withdrawn at any time.",
    ),
    PolicySection(
        title = "Removal and retention",
        body = "Removing a face profile deletes the stored embedding and stops future recognition. " +
            "Attendance history is never deleted by removing a face profile, because it is an " +
            "employment record rather than biometric data.",
    ),
    PolicySection(
        title = "What is never logged",
        body = "Passwords, access and refresh tokens, and raw face embeddings are never written to " +
            "logs or analytics.",
    ),
    PolicySection(
        title = "Guest mode",
        body = "Guest mode runs entirely on this device with sample employees. No camera frames, " +
            "face data or attendance records are uploaded, and nothing is shared with any " +
            "organization.",
    ),
)

@Composable
fun PrivacyRoute(onNavigateUp: () -> Unit) {
    Scaffold(
        topBar = { AppTopBar(title = "Biometric data policy", onNavigateUp = onNavigateUp) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
        ) {
            Spacer(Modifier.height(Spacing.md))
            Text(
                "Face data is sensitive personal information. This summary describes how FaceAttend " +
                    "handles it.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(Spacing.lg))

            policySections.forEach { section ->
                SectionHeader(title = section.title, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(Spacing.sm))
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.large,
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainer,
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                ) {
                    Text(
                        section.body,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(Spacing.lg),
                    )
                }
                Spacer(Modifier.height(Spacing.lg))
            }
            Spacer(Modifier.height(Spacing.xxl))
        }
    }
}

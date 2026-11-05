package com.facerem.kiosk.scan

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.facerem.core.security.DeviceCredentials
import com.facerem.feature.attendance.presentation.ScanRoute

/**
 * Dedicated attendance scanning screen for the Kiosk flavor.
 * Embeds [ScanRoute] running in locked unattended mode with CameraX, ML Kit,
 * challenge liveness verification, 30-second undo countdown, and PIN fallback.
 */
@Composable
fun KioskScanScreen(
    credentials: DeviceCredentials?,
    modifier: Modifier = Modifier,
) {
    ScanRoute(
        onNavigateUp = { /* Unattended kiosk mode has no back navigation */ },
    )
}


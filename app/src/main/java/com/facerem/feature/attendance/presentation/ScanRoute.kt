package com.facerem.feature.attendance.presentation

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.camera.FaceCameraPreview
import com.facerem.core.camera.FaceQualityEvaluator
import com.facerem.core.camera.rememberCameraPermissionState
import com.facerem.core.camera.rememberFaceCaptureController
import com.facerem.core.camera.rememberFaceDetector
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.AttendanceStatusPill
import com.facerem.core.designsystem.component.FaceFramingOverlay
import com.facerem.core.designsystem.component.GuestModeBanner
import com.facerem.core.designsystem.component.PrimaryButton
import com.facerem.core.designsystem.component.SecondaryButton
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.RecognitionOutcome
import com.facerem.ui.theme.AppTheme
import com.facerem.ui.theme.Spacing
import kotlin.math.roundToInt

@Composable
fun ScanRoute(
    onNavigateUp: () -> Unit,
    viewModel: ScanViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val permission by rememberCameraPermissionState()
    val detector = rememberFaceDetector()
    val captureController = rememberFaceCaptureController()

    // A gate tablet must not sleep between visitors.
    val view = LocalView.current
    DisposableEffect(uiState.kioskMode) {
        view.keepScreenOn = uiState.kioskMode
        onDispose { view.keepScreenOn = false }
    }

    // Back would drop an unattended kiosk back into the app. Leaving is a deliberate long press.
    BackHandler(enabled = uiState.kioskMode) { /* swallowed on purpose */ }

    if (!permission.isGranted) {
        Scaffold(topBar = { AppTopBar(title = "Attendance scan", onNavigateUp = onNavigateUp) }) { padding ->
            ScanPermissionPrompt(
                hasBeenRequested = permission.hasBeenRequested,
                onRequest = permission.request,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = Spacing.screenHorizontal),
            )
        }
        return
    }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        // Camera live feed
        FaceCameraPreview(
            detector = detector,
            pose = FaceQualityEvaluator.HeadPose.FRONT,
            onQuality = { status -> viewModel.onQuality(status, captureController::capture) },
            modifier = Modifier.fillMaxSize(),
            captureController = captureController,
        )

        // Spring-animated camera reticle overlay
        FaceFramingOverlay(
            accent = when {
                uiState.phase != ScanPhase.SCANNING -> AppTheme.colors.info
                uiState.quality.isValid -> AppTheme.colors.success
                else -> AppTheme.colors.warning
            },
            isActive = uiState.phase == ScanPhase.SCANNING,
        )

        // Glassmorphism HUD Header
        KioskHeader(
            uiState = uiState,
            onExitKiosk = { viewModel.setKioskMode(false) },
            onEnterKiosk = { viewModel.setKioskMode(true) },
            onNavigateUp = onNavigateUp,
            modifier = Modifier.align(Alignment.TopCenter),
        )

        // Glassmorphism HUD Footer (shown ONLY in SCANNING phase when no active undo banner)
        AnimatedVisibility(
            visible = uiState.phase == ScanPhase.SCANNING && !uiState.canUndo && uiState.undoMessage == null,
            enter = fadeIn(tween(150)),
            exit = fadeOut(tween(150)),
            modifier = Modifier.align(Alignment.BottomCenter),
        ) {
            ScanFooter(
                uiState = uiState,
                onScanAgain = viewModel::scanAgain,
                onOpenPin = viewModel::openPinDialog,
            )
        }

        // 30-second Undo Banner
        AnimatedVisibility(
            visible = uiState.canUndo || uiState.undoMessage != null,
            enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
            exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(),
            modifier = Modifier.align(Alignment.BottomCenter),
        ) {
            UndoBanner(
                secondsRemaining = uiState.undoSecondsRemaining,
                undoMessage = uiState.undoMessage,
                onUndo = viewModel::undo,
            )
        }

        // Bouncy spring result card overlay
        AnimatedVisibility(
            visible = uiState.phase == ScanPhase.RESULT,
            enter = fadeIn(tween(250)) +
                scaleIn(
                    initialScale = 0.85f,
                    animationSpec = spring(
                        dampingRatio = Spring.DampingRatioMediumBouncy,
                        stiffness = Spring.StiffnessMediumLow,
                    ),
                ) +
                slideInVertically(
                    initialOffsetY = { it / 6 },
                    animationSpec = spring(
                        dampingRatio = Spring.DampingRatioMediumBouncy,
                        stiffness = Spring.StiffnessMediumLow,
                    ),
                ),
            exit = fadeOut(tween(200)),
        ) {
            ResultOverlay(
                outcome = uiState.outcome,
                errorMessage = uiState.errorMessage,
                onOpenPin = viewModel::openPinDialog,
                modifier = Modifier.fillMaxSize(),
            )
        }

        // Animated radar wave verifying overlay with challenge action prompt
        AnimatedVisibility(
            visible = uiState.phase == ScanPhase.VERIFYING,
            enter = fadeIn(tween(200)),
            exit = fadeOut(tween(200)),
        ) {
            VerifyingOverlay(prompt = uiState.challengePrompt)
        }

        // PIN Fallback Dialog
        if (uiState.showPinDialog) {
            PinFallbackDialog(
                employeeCode = uiState.pinEmployeeCode,
                pin = uiState.pinCode,
                error = uiState.pinError,
                isSubmitting = uiState.pinIsSubmitting,
                onEmployeeCodeChange = viewModel::onPinEmployeeCodeChange,
                onPinChange = viewModel::onPinCodeChange,
                onSubmit = viewModel::submitPin,
                onDismiss = viewModel::dismissPinDialog,
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun KioskHeader(
    uiState: ScanUiState,
    onExitKiosk: () -> Unit,
    onEnterKiosk: () -> Unit,
    onNavigateUp: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = Spacing.lg, vertical = Spacing.md),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .clip(RoundedCornerShape(20.dp))
                .background(Color.Black.copy(alpha = 0.5f))
                .border(1.dp, Color.White.copy(alpha = 0.15f), RoundedCornerShape(20.dp))
                .padding(horizontal = Spacing.md, vertical = Spacing.sm),
        ) {
            if (uiState.kioskMode) {
                Box(
                    modifier = Modifier
                        .clip(MaterialTheme.shapes.small)
                        .background(Color.White.copy(alpha = 0.18f))
                        .combinedClickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                            onClick = {},
                            onLongClick = onExitKiosk,
                        )
                        .padding(horizontal = Spacing.md, vertical = Spacing.xs),
                ) {
                    Text(
                        "Kiosk mode · hold to exit",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.95f),
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            } else {
                SecondaryButton("Back", onNavigateUp)
                Spacer(Modifier.width(Spacing.sm))
                SecondaryButton("Kiosk mode", onEnterKiosk)
            }

            Spacer(Modifier.weight(1f))

            if (uiState.scanCount > 0) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.8f))
                        .padding(horizontal = Spacing.md, vertical = Spacing.xs),
                ) {
                    Text(
                        "${uiState.scanCount} scanned",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        if (uiState.isGuest) {
            Spacer(Modifier.height(Spacing.sm))
            GuestModeBanner()
        }
    }
}

@Composable
private fun ScanFooter(
    uiState: ScanUiState,
    onScanAgain: () -> Unit,
    onOpenPin: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color.Transparent, Color.Black.copy(alpha = 0.85f), Color.Black),
                ),
            )
            .padding(horizontal = Spacing.screenHorizontal, vertical = Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        AnimatedContent(
            targetState = uiState.guidance,
            transitionSpec = {
                (fadeIn(tween(220)) + scaleIn(initialScale = 0.95f)) togetherWith fadeOut(tween(180))
            },
            label = "guidance-text",
        ) { text ->
            if (text.isNotBlank()) {
                Text(
                    text,
                    style = MaterialTheme.typography.headlineSmall,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                )
            }
        }

        Spacer(Modifier.height(Spacing.xs))
        Text(
            "Recognition runs on your organization's server. Internet is required.",
            style = MaterialTheme.typography.bodySmall,
            color = Color.White.copy(alpha = 0.65f),
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(Spacing.sm))
        TextButton(onClick = onOpenPin) {
            Text(
                "Use Employee Code & PIN instead",
                color = Color.White.copy(alpha = 0.9f),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
            )
        }

        if (uiState.showsManualControls) {
            Spacer(Modifier.height(Spacing.lg))
            PrimaryButton(
                text = "Scan next person",
                onClick = onScanAgain,
                modifier = Modifier.fillMaxWidth(),
                enabled = uiState.phase == ScanPhase.RESULT,
            )
        }
    }
}

@Composable
private fun UndoBanner(
    secondsRemaining: Int,
    undoMessage: String?,
    onUndo: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .padding(Spacing.lg),
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF1E293B),
        tonalElevation = 6.dp,
        border = BorderStroke(1.dp, Color(0xFF334155)),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = Spacing.lg, vertical = Spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            if (undoMessage != null) {
                Text(
                    text = undoMessage,
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White,
                    fontWeight = FontWeight.Medium,
                )
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = Color(0xFF10B981),
                        modifier = Modifier.size(20.dp),
                    )
                    Spacer(Modifier.width(Spacing.sm))
                    Text(
                        text = "Attendance recorded · Undo (${secondsRemaining}s)",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White,
                        fontWeight = FontWeight.Medium,
                    )
                }
                TextButton(onClick = onUndo) {
                    Text(
                        "UNDO",
                        color = Color(0xFFEF4444),
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

@Composable
private fun VerifyingOverlay(prompt: String?) {
    val infiniteTransition = rememberInfiniteTransition(label = "verifying-radar")
    val pulseProgress by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1_500, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "radar-pulse",
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.68f)),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(180.dp)) {
            val center = Offset(size.width / 2f, size.height / 2f)
            val maxRadius = size.width / 2f
            val currentRadius = maxRadius * pulseProgress
            val alpha = (1f - pulseProgress).coerceIn(0f, 1f)

            drawCircle(
                color = Color(0xFF00E5FF).copy(alpha = alpha * 0.45f),
                radius = currentRadius,
                center = center,
                style = Stroke(width = 3.dp.toPx()),
            )
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(contentAlignment = Alignment.Center) {
                CircularProgressIndicator(
                    color = Color(0xFF00E5FF),
                    strokeWidth = 3.5.dp,
                    modifier = Modifier.size(64.dp),
                )
                Icon(
                    imageVector = Icons.Default.CameraAlt,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(24.dp),
                )
            }
            Spacer(Modifier.height(Spacing.lg))
            Text(
                text = prompt ?: "Matching face profile…",
                color = Color.White,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun ResultOverlay(
    outcome: RecognitionOutcome?,
    errorMessage: String?,
    onOpenPin: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier.background(Color.Black.copy(alpha = 0.75f)),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.xl)
                .border(1.dp, Color.White.copy(alpha = 0.2f), MaterialTheme.shapes.extraLarge),
            shape = MaterialTheme.shapes.extraLarge,
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 8.dp,
        ) {
            when {
                outcome is RecognitionOutcome.Recognized -> RecognizedCard(outcome)
                outcome is RecognitionOutcome.NotRecognized -> MessageCard(
                    icon = Icons.Default.ErrorOutline,
                    tint = MaterialTheme.colorScheme.error,
                    title = "Face not recognized",
                    message = outcome.message,
                    actionButtonText = "Use Employee Code & PIN",
                    onAction = onOpenPin,
                )

                outcome is RecognitionOutcome.Rejected -> MessageCard(
                    icon = Icons.Default.ErrorOutline,
                    tint = MaterialTheme.colorScheme.error,
                    title = "Scan rejected",
                    message = outcome.message,
                    actionButtonText = "Use Employee Code & PIN",
                    onAction = onOpenPin,
                )

                else -> MessageCard(
                    icon = Icons.Default.ErrorOutline,
                    tint = MaterialTheme.colorScheme.error,
                    title = "Scan failed",
                    message = errorMessage ?: "Please try again.",
                    actionButtonText = "Use Employee Code & PIN",
                    onAction = onOpenPin,
                )
            }
        }
    }
}

@Composable
private fun RecognizedCard(outcome: RecognitionOutcome.Recognized) {
    val semantic = AppTheme.colors
    val isRepeat = outcome.eventType == AttendanceEventType.ALREADY_PRESENT
    val accent = if (isRepeat) semantic.info else semantic.success

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(76.dp)
                .clip(CircleShape)
                .background(accent.copy(alpha = 0.16f))
                .border(2.dp, accent.copy(alpha = 0.4f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = if (isRepeat) Icons.Default.Schedule else Icons.Default.CheckCircle,
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(48.dp),
            )
        }

        Spacer(Modifier.height(Spacing.lg))
        UserAvatar(name = outcome.employeeName, size = 64.dp)
        Spacer(Modifier.height(Spacing.md))

        Text(
            outcome.employeeName,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
        Text(
            "${outcome.employeeCode} · ${outcome.department}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(Spacing.lg))
        Text(
            outcome.eventType.displayName,
            style = MaterialTheme.typography.headlineSmall,
            color = accent,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(Spacing.xs))
        Text(
            text = if (isRepeat) repeatDetail(outcome) else "at ${outcome.timeLabel}",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )

        Spacer(Modifier.height(Spacing.md))
        AttendanceStatusPill(outcome.status)

        if (outcome.lateMinutes > 0 && !isRepeat) {
            Spacer(Modifier.height(Spacing.sm))
            Text(
                "${outcome.lateMinutes} minutes after shift start",
                style = MaterialTheme.typography.bodySmall,
                color = semantic.warning,
            )
        }

        Spacer(Modifier.height(Spacing.md))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.surfaceContainerHigh)
                .padding(horizontal = Spacing.md, vertical = Spacing.xs),
        ) {
            Text(
                "Match confidence ${(outcome.confidence * 100).roundToInt()}%",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

private fun repeatDetail(outcome: RecognitionOutcome.Recognized): String {
    val checkIn = outcome.checkInLabel
    val checkOut = outcome.checkOutLabel
    return when {
        checkOut != null && checkIn != null -> "In $checkIn · out $checkOut"
        checkIn != null -> "In since $checkIn"
        else -> "Already recorded for today"
    }
}

@Composable
private fun MessageCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    tint: Color,
    title: String,
    message: String,
    actionButtonText: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(64.dp))
        Spacer(Modifier.height(Spacing.lg))
        Text(title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
        Spacer(Modifier.height(Spacing.sm))
        Text(
            message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        if (actionButtonText != null && onAction != null) {
            Spacer(Modifier.height(Spacing.lg))
            PrimaryButton(
                text = actionButtonText,
                onClick = onAction,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun PinFallbackDialog(
    employeeCode: String,
    pin: String,
    error: String?,
    isSubmitting: Boolean,
    onEmployeeCodeChange: (String) -> Unit,
    onPinChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 8.dp,
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.md),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.xl),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    "PIN Attendance Fallback",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(Spacing.xs))
                Text(
                    "Enter your employee code and PIN to record attendance.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(Spacing.lg))

                OutlinedTextField(
                    value = employeeCode,
                    onValueChange = onEmployeeCodeChange,
                    label = { Text("Employee Code") },
                    placeholder = { Text("e.g. EMP-101") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Characters,
                        keyboardType = KeyboardType.Ascii,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(Spacing.md))

                OutlinedTextField(
                    value = pin,
                    onValueChange = onPinChange,
                    label = { Text("PIN") },
                    placeholder = { Text("••••") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.fillMaxWidth(),
                )

                if (error != null) {
                    Spacer(Modifier.height(Spacing.md))
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center,
                    )
                }

                Spacer(Modifier.height(Spacing.xl))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(
                        onClick = onDismiss,
                        enabled = !isSubmitting,
                    ) {
                        Text("Cancel")
                    }
                    Spacer(Modifier.width(Spacing.sm))
                    PrimaryButton(
                        text = if (isSubmitting) "Verifying…" else "Submit",
                        onClick = onSubmit,
                        enabled = !isSubmitting && employeeCode.isNotBlank() && pin.isNotBlank(),
                    )
                }
            }
        }
    }
}

@Composable
private fun ScanPermissionPrompt(
    hasBeenRequested: Boolean,
    onRequest: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = Icons.Default.CameraAlt,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(56.dp),
        )
        Spacer(Modifier.height(Spacing.lg))
        Text(
            text = "Camera access required",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(Spacing.sm))
        Text(
            text = "FaceAttend uses the front camera to detect faces and mark attendance.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(Spacing.xl))
        PrimaryButton(
            text = if (hasBeenRequested) "Open settings" else "Grant permission",
            onClick = onRequest,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

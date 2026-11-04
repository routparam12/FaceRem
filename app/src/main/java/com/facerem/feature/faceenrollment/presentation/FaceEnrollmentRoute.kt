package com.facerem.feature.faceenrollment.presentation

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material3.Checkbox
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.camera.FaceCameraPreview
import com.facerem.core.camera.FaceCaptureController
import com.facerem.core.camera.rememberCameraPermissionState
import com.facerem.core.camera.rememberFaceCaptureController
import com.facerem.core.camera.rememberFaceDetector
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.FaceFramingOverlay
import com.facerem.core.designsystem.component.InlineMessage
import com.facerem.core.designsystem.component.PrimaryButton
import com.facerem.core.designsystem.component.SecondaryButton
import com.facerem.ui.theme.AppTheme
import com.facerem.ui.theme.Spacing
import com.google.mlkit.vision.face.FaceDetector

private enum class EnrollmentStep {
    CONSENT,
    PERMISSION,
    CAPTURE,
    COMPLETE,
}

@Composable
fun FaceEnrollmentRoute(
    onNavigateUp: () -> Unit,
    viewModel: FaceEnrollmentViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val permission by rememberCameraPermissionState()
    val detector = rememberFaceDetector()
    val captureController = rememberFaceCaptureController()

    val currentStep = when {
        uiState.isComplete -> EnrollmentStep.COMPLETE
        !uiState.consentGiven -> EnrollmentStep.CONSENT
        !permission.isGranted -> EnrollmentStep.PERMISSION
        else -> EnrollmentStep.CAPTURE
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Face enrollment",
                subtitle = uiState.employee?.fullName,
                onNavigateUp = onNavigateUp,
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
        ) {
            AnimatedContent(
                targetState = currentStep,
                transitionSpec = {
                    (slideInHorizontally(tween(300)) { it / 2 } + fadeIn(tween(300))) togetherWith
                        (slideOutHorizontally(tween(200)) { -it / 2 } + fadeOut(tween(200)))
                },
                label = "enrollment-step-content",
            ) { step ->
                when (step) {
                    EnrollmentStep.COMPLETE -> EnrollmentComplete(
                        employeeName = uiState.employee?.fullName.orEmpty(),
                        onDone = onNavigateUp,
                    )

                    EnrollmentStep.CONSENT -> ConsentStep(
                        employeeName = uiState.employee?.fullName.orEmpty(),
                        onConsentChange = viewModel::onConsentChange,
                    )

                    EnrollmentStep.PERMISSION -> CameraPermissionStep(
                        hasBeenRequested = permission.hasBeenRequested,
                        onRequest = permission.request,
                    )

                    EnrollmentStep.CAPTURE -> CaptureStep(
                        uiState = uiState,
                        detector = detector,
                        captureController = captureController,
                        onQuality = { status ->
                            viewModel.onQuality(status, captureController::capture)
                        },
                        onSubmit = { viewModel.submit() },
                        onRetake = viewModel::retake,
                    )
                }
            }
            Spacer(Modifier.height(Spacing.xxl))
        }
    }
}

@Composable
private fun ConsentStep(employeeName: String, onConsentChange: (Boolean) -> Unit) {
    Column {
        Spacer(Modifier.height(Spacing.lg))
        Text("Biometric consent", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(Spacing.md))
        Text(
            "Enrolling ${employeeName.ifBlank { "this employee" }} creates a face profile used only " +
                "to verify attendance inside your organization.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(Spacing.lg))
        listOf(
            "Captured images are sent over HTTPS and are not stored as pictures.",
            "The server stores a mathematical face embedding, scoped to this organization only.",
            "The profile can be removed at any time; attendance history is kept.",
            "Consent and its timestamp are recorded in the audit log.",
        ).forEach { line ->
            Row(modifier = Modifier.padding(vertical = Spacing.xs)) {
                Text("•  ", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text(
                    line,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(Spacing.lg))
        var acknowledged by remember { mutableStateOf(false) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = acknowledged, onCheckedChange = { acknowledged = it })
            Text(
                "The employee has given informed consent to face enrollment.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(Modifier.height(Spacing.lg))
        PrimaryButton(
            text = "Continue to capture",
            onClick = { onConsentChange(true) },
            modifier = Modifier.fillMaxWidth(),
            enabled = acknowledged,
        )
    }
}

@Composable
private fun CameraPermissionStep(hasBeenRequested: Boolean, onRequest: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = Spacing.xxl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(72.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primaryContainer),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.CameraAlt,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
        Spacer(Modifier.height(Spacing.lg))
        Text("Camera access needed", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(Spacing.sm))
        Text(
            if (hasBeenRequested) {
                "Camera permission was declined. Enable it in system settings to continue enrollment."
            } else {
                "FaceAttend uses the front camera to capture enrollment frames. Nothing is recorded."
            },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(Spacing.lg))
        PrimaryButton("Allow camera", onRequest, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun CaptureStep(
    uiState: FaceEnrollmentUiState,
    detector: FaceDetector,
    captureController: FaceCaptureController,
    onQuality: (com.facerem.core.camera.FaceQualityStatus) -> Unit,
    onSubmit: () -> Unit,
    onRetake: () -> Unit,
) {
    val semantic = AppTheme.colors
    val accent = when {
        uiState.allPosesCaptured -> semantic.success
        uiState.quality.isValid -> semantic.success
        else -> semantic.warning
    }

    val animatedProgress by animateFloatAsState(
        targetValue = uiState.progress,
        animationSpec = spring(stiffness = Spring.StiffnessLow),
        label = "enrollment-progress",
    )

    Column {
        Spacer(Modifier.height(Spacing.md))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(0.78f)
                .clip(MaterialTheme.shapes.extraLarge)
                .background(MaterialTheme.colorScheme.surfaceContainerHigh)
                .border(1.dp, accent.copy(alpha = 0.35f), MaterialTheme.shapes.extraLarge),
        ) {
            if (uiState.isCameraActive) {
                FaceCameraPreview(
                    detector = detector,
                    pose = uiState.currentPose,
                    onQuality = onQuality,
                    modifier = Modifier.fillMaxSize(),
                    captureController = captureController,
                )
            }
            if (!uiState.allPosesCaptured) {
                FaceFramingOverlay(accent = accent, isActive = !uiState.isSubmitting)
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.85f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(
                            modifier = Modifier
                                .size(88.dp)
                                .clip(CircleShape)
                                .background(semantic.success.copy(alpha = 0.16f)),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(
                                Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = semantic.success,
                                modifier = Modifier.size(60.dp),
                            )
                        }
                        Spacer(Modifier.height(Spacing.md))
                        Text(
                            "Ready to submit",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(Spacing.lg))
        Text(
            if (uiState.allPosesCaptured) "All angles captured" else uiState.currentPose.instruction,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(Spacing.xs))
        Text(
            if (uiState.allPosesCaptured) "Submit to create the face profile." else uiState.quality.guidance,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(Spacing.lg))
        LinearProgressIndicator(
            progress = { animatedProgress },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(MaterialTheme.shapes.small),
        )
        Spacer(Modifier.height(Spacing.md))

        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.sm)) {
            ENROLLMENT_POSES.forEachIndexed { index, pose ->
                val captured = index < uiState.capturedPoses
                val iconScale by animateFloatAsState(
                    targetValue = if (captured) 1.15f else 1f,
                    animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
                    label = "badge-scale",
                )

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(12.dp))
                        .background(
                            if (captured) semantic.success.copy(alpha = 0.12f)
                            else MaterialTheme.colorScheme.surfaceContainerHigh,
                        )
                        .padding(horizontal = Spacing.xs, vertical = Spacing.xs),
                ) {
                    Icon(
                        if (captured) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked,
                        contentDescription = null,
                        tint = if (captured) semantic.success else MaterialTheme.colorScheme.outline,
                        modifier = Modifier
                            .size(18.dp)
                            .scale(iconScale),
                    )
                    Spacer(Modifier.width(Spacing.xs))
                    Text(
                        pose.name.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.labelSmall,
                        color = if (captured) semantic.success else MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = if (captured) FontWeight.Bold else FontWeight.Normal,
                    )
                }
            }
        }

        InlineMessage(text = uiState.errorMessage)

        Spacer(Modifier.height(Spacing.lg))
        PrimaryButton(
            text = "Submit enrollment",
            onClick = onSubmit,
            modifier = Modifier.fillMaxWidth(),
            enabled = uiState.allPosesCaptured,
            loading = uiState.isSubmitting,
        )
        Spacer(Modifier.height(Spacing.sm))
        SecondaryButton(
            text = "Start over",
            onClick = onRetake,
            modifier = Modifier.fillMaxWidth(),
            enabled = uiState.capturedPoses > 0 && !uiState.isSubmitting,
        )
    }
}

@Composable
private fun EnrollmentComplete(employeeName: String, onDone: () -> Unit) {
    val semantic = AppTheme.colors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = Spacing.xxl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(96.dp)
                .clip(CircleShape)
                .background(semantic.success.copy(alpha = 0.16f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.CheckCircle,
                contentDescription = null,
                tint = semantic.success,
                modifier = Modifier.size(68.dp),
            )
        }
        Spacer(Modifier.height(Spacing.lg))
        Text("Face profile created", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(Spacing.sm))
        Text(
            "${employeeName.ifBlank { "This employee" }} can now check in with the attendance scanner.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(Spacing.xl))
        PrimaryButton("Done", onDone, modifier = Modifier.fillMaxWidth())
    }
}

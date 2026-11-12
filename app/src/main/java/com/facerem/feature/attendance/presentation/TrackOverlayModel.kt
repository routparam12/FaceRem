package com.facerem.feature.attendance.presentation

import androidx.compose.ui.geometry.Rect
import com.facerem.core.camera.FaceQualityStatus
import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.RecognitionOutcome

/**
 * Name display style options for recognized employee names on the kiosk screen.
 */
enum class NameDisplayStyle {
    /** e.g. "John Doe" */
    FULL_NAME,

    /** e.g. "John D." */
    FIRST_NAME_LAST_INITIAL,

    /** e.g. "J. D." */
    INITIALS,
}

/**
 * Central configuration for scan screen overlays.
 */
object ScanOverlayConfig {
    /**
     * Display style for recognized employee names.
     * Easily changed here (e.g. for privacy regulations).
     */
    var NAME_DISPLAY_STYLE: NameDisplayStyle = NameDisplayStyle.FULL_NAME

    /** Hold duration on screen after a result before returning to scanning mode. */
    const val RESULT_HOLD_MILLIS: Long = 3000L

    /** Duration before a disappeared face is removed from the screen. */
    const val TRACK_FADE_OUT_MILLIS: Long = 1000L
}

/**
 * Formats a full name string according to the requested [NameDisplayStyle].
 */
fun formatEmployeeName(
    fullName: String,
    style: NameDisplayStyle = ScanOverlayConfig.NAME_DISPLAY_STYLE,
): String {
    val trimmed = fullName.trim()
    if (trimmed.isEmpty()) return ""
    return when (style) {
        NameDisplayStyle.FULL_NAME -> trimmed
        NameDisplayStyle.FIRST_NAME_LAST_INITIAL -> {
            val parts = trimmed.split("\\s+".toRegex()).filter { it.isNotBlank() }
            if (parts.size >= 2) {
                "${parts.first()} ${parts.last().first().uppercaseChar()}."
            } else {
                trimmed
            }
        }
        NameDisplayStyle.INITIALS -> {
            val parts = trimmed.split("\\s+".toRegex()).filter { it.isNotBlank() }
            parts.mapNotNull { it.firstOrNull()?.uppercaseChar()?.plus(".") }.joinToString(" ")
        }
    }
}

/**
 * Visual highlight colors for the face tracking overlay box and label badge.
 */
enum class OverlayColor {
    WHITE,
    BLUE,
    GREEN,
    RED,
    AMBER,
}

/**
 * Overlay states according to the kiosk scan specification.
 */
enum class TrackOverlayStatus {
    ANALYZING,
    CHALLENGE,
    RECOGNIZED,
    ALREADY_PRESENT,
    NOT_RECOGNIZED,
    LIVENESS_FAILED,
    QUALITY,
}

/**
 * Icon types so visual indicators never rely on color alone.
 */
enum class OverlayIconType {
    SEARCH,
    EYE,
    CHECK,
    CROSS,
    WARNING,
}

/**
 * UI state for a single tracked face's overlay badge and bounding box.
 */
data class TrackOverlayState(
    val status: TrackOverlayStatus,
    val color: OverlayColor,
    val primaryText: String,
    val secondaryText: String? = null,
    val badgeText: String? = null,
    val iconType: OverlayIconType,
    val showPinFallbackButton: Boolean = false,
)

/**
 * Pure function mapping server outcome, track role, challenge prompt, and quality status
 * to the exact overlay state and color.
 *
 * CRITICAL INVARIANT: [OverlayColor.RED] is returned ONLY when [serverOutcome] is
 * [RecognitionOutcome.NotRecognized]. Client quality verdicts, analyzing phase, and liveness
 * failures must NEVER produce RED.
 */
fun mapToTrackOverlayState(
    serverOutcome: RecognitionOutcome?,
    isPrimary: Boolean,
    challengePrompt: String? = null,
    clientQuality: FaceQualityStatus? = null,
    nameStyle: NameDisplayStyle = ScanOverlayConfig.NAME_DISPLAY_STYLE,
): TrackOverlayState {
    // 1. Final server outcome received
    if (serverOutcome != null) {
        return when (serverOutcome) {
            is RecognitionOutcome.NotRecognized -> TrackOverlayState(
                status = TrackOverlayStatus.NOT_RECOGNIZED,
                color = OverlayColor.RED,
                primaryText = "Not recognized",
                secondaryText = null,
                badgeText = null,
                iconType = OverlayIconType.CROSS,
                showPinFallbackButton = true,
            )

            is RecognitionOutcome.Rejected -> {
                val isLiveness = serverOutcome.code == "LIVENESS_FAILED"
                TrackOverlayState(
                    status = if (isLiveness) TrackOverlayStatus.LIVENESS_FAILED else TrackOverlayStatus.QUALITY,
                    color = OverlayColor.AMBER,
                    primaryText = "Try again",
                    secondaryText = serverOutcome.message.ifBlank {
                        if (isLiveness) "Liveness verification failed" else "Quality check failed"
                    },
                    badgeText = null,
                    iconType = OverlayIconType.WARNING,
                    showPinFallbackButton = false,
                )
            }

            is RecognitionOutcome.Recognized -> {
                if (serverOutcome.eventType == AttendanceEventType.ALREADY_PRESENT) {
                    val timeStr = serverOutcome.checkInLabel ?: serverOutcome.timeLabel
                    TrackOverlayState(
                        status = TrackOverlayStatus.ALREADY_PRESENT,
                        color = OverlayColor.GREEN,
                        primaryText = if (timeStr.isNotBlank()) "Already checked in $timeStr" else "Already checked in",
                        secondaryText = formatEmployeeName(serverOutcome.employeeName, nameStyle),
                        badgeText = "VERIFIED",
                        iconType = OverlayIconType.CHECK,
                        showPinFallbackButton = false,
                    )
                } else {
                    val formattedName = formatEmployeeName(serverOutcome.employeeName, nameStyle)
                    val lateStr = if (serverOutcome.lateMinutes > 0) " • ${serverOutcome.lateMinutes}m late" else ""
                    val secondary = "${serverOutcome.eventType.displayName} ${serverOutcome.timeLabel}$lateStr".trim()
                    TrackOverlayState(
                        status = TrackOverlayStatus.RECOGNIZED,
                        color = OverlayColor.GREEN,
                        primaryText = formattedName,
                        secondaryText = secondary.ifBlank { null },
                        badgeText = "VERIFIED",
                        iconType = OverlayIconType.CHECK,
                        showPinFallbackButton = false,
                    )
                }
            }
        }
    }

    // 2. Active server challenge underway (primary face only)
    if (isPrimary && challengePrompt != null) {
        return TrackOverlayState(
            status = TrackOverlayStatus.CHALLENGE,
            color = OverlayColor.BLUE,
            primaryText = challengePrompt,
            secondaryText = null,
            badgeText = null,
            iconType = OverlayIconType.EYE,
            showPinFallbackButton = false,
        )
    }

    // 3. Non-primary face: stays in ANALYZING with guidance
    if (!isPrimary) {
        return TrackOverlayState(
            status = TrackOverlayStatus.ANALYZING,
            color = OverlayColor.WHITE,
            primaryText = "One person at a time",
            secondaryText = null,
            badgeText = null,
            iconType = OverlayIconType.SEARCH,
            showPinFallbackButton = false,
        )
    }

    // 4. Primary face client quality guidance (coaching, never red)
    if (clientQuality != null && !clientQuality.isValid && clientQuality != FaceQualityStatus.NO_FACE) {
        return TrackOverlayState(
            status = TrackOverlayStatus.QUALITY,
            color = OverlayColor.AMBER,
            primaryText = "Try again",
            secondaryText = clientQuality.guidance,
            badgeText = null,
            iconType = OverlayIconType.WARNING,
            showPinFallbackButton = false,
        )
    }

    // 5. Default primary analyzing
    return TrackOverlayState(
        status = TrackOverlayStatus.ANALYZING,
        color = OverlayColor.WHITE,
        primaryText = "Analyzing…",
        secondaryText = null,
        badgeText = null,
        iconType = OverlayIconType.SEARCH,
        showPinFallbackButton = false,
    )
}

/**
 * Coordinate transform mapping upright camera frame coordinates to preview view coordinates.
 *
 * Accounts for front-camera horizontal mirroring, scale-to-fill aspect ratio (`FILL_CENTER`),
 * and centering offsets so overlays line up precisely with the physical face in the preview.
 */
fun mapFaceBoundsToView(
    faceRect: android.graphics.Rect,
    imageWidth: Int,
    imageHeight: Int,
    viewWidth: Float,
    viewHeight: Float,
    isFrontCamera: Boolean = true,
): Rect {
    if (imageWidth <= 0 || imageHeight <= 0 || viewWidth <= 0f || viewHeight <= 0f) {
        return Rect.Zero
    }

    val scale = maxOf(viewWidth / imageWidth.toFloat(), viewHeight / imageHeight.toFloat())
    val scaledWidth = imageWidth * scale
    val scaledHeight = imageHeight * scale
    val offsetX = (viewWidth - scaledWidth) / 2f
    val offsetY = (viewHeight - scaledHeight) / 2f

    // Mirror horizontally for front-facing camera preview
    val left = if (isFrontCamera) imageWidth - faceRect.right else faceRect.left
    val right = if (isFrontCamera) imageWidth - faceRect.left else faceRect.right

    val viewLeft = offsetX + left * scale
    val viewRight = offsetX + right * scale
    val viewTop = offsetY + faceRect.top * scale
    val viewBottom = offsetY + faceRect.bottom * scale

    return Rect(
        left = viewLeft.coerceIn(0f, viewWidth),
        top = viewTop.coerceIn(0f, viewHeight),
        right = viewRight.coerceIn(0f, viewWidth),
        bottom = viewBottom.coerceIn(0f, viewHeight),
    )
}

/**
 * Complete UI model for a tracked face on the kiosk screen.
 */
data class TrackedFaceUiModel(
    val trackId: Int,
    val bounds: Rect,
    val isPrimary: Boolean,
    val state: TrackOverlayState,
    val lastSeenTimestampMs: Long,
    val isLeaving: Boolean = false,
)


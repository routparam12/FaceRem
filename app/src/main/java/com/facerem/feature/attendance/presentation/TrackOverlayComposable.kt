package com.facerem.feature.attendance.presentation

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Pin
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.roundToInt

private val COLOR_WHITE = Color(0xFFFFFFFF)
private val COLOR_BLUE = Color(0xFF2979FF)
private val COLOR_GREEN = Color(0xFF00E676)
private val COLOR_RED = Color(0xFFFF1744)
private val COLOR_AMBER = Color(0xFFFFAB00)

fun OverlayColor.toComposeColor(): Color = when (this) {
    OverlayColor.WHITE -> COLOR_WHITE
    OverlayColor.BLUE -> COLOR_BLUE
    OverlayColor.GREEN -> COLOR_GREEN
    OverlayColor.RED -> COLOR_RED
    OverlayColor.AMBER -> COLOR_AMBER
}

/**
 * Renders smoothly-animated tracking boxes and state badges over all currently detected faces.
 */
@Composable
fun KioskFaceTrackOverlay(
    tracks: List<TrackedFaceUiModel>,
    onUsePinClicked: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(modifier = modifier.fillMaxSize()) {
        tracks.forEach { track ->
            key(track.trackId) {
                TrackedFaceItem(
                    track = track,
                    onUsePinClicked = onUsePinClicked,
                )
            }
        }
    }
}

@Composable
private fun TrackedFaceItem(
    track: TrackedFaceUiModel,
    onUsePinClicked: () -> Unit,
) {
    val density = LocalDensity.current

    // Smooth spring animation for the tracking bounding box
    val animatedLeft by animateFloatAsState(
        targetValue = track.bounds.left,
        animationSpec = spring(
            stiffness = Spring.StiffnessMediumLow,
            dampingRatio = Spring.DampingRatioNoBouncy,
        ),
        label = "boxLeft",
    )
    val animatedTop by animateFloatAsState(
        targetValue = track.bounds.top,
        animationSpec = spring(
            stiffness = Spring.StiffnessMediumLow,
            dampingRatio = Spring.DampingRatioNoBouncy,
        ),
        label = "boxTop",
    )
    val animatedRight by animateFloatAsState(
        targetValue = track.bounds.right,
        animationSpec = spring(
            stiffness = Spring.StiffnessMediumLow,
            dampingRatio = Spring.DampingRatioNoBouncy,
        ),
        label = "boxRight",
    )
    val animatedBottom by animateFloatAsState(
        targetValue = track.bounds.bottom,
        animationSpec = spring(
            stiffness = Spring.StiffnessMediumLow,
            dampingRatio = Spring.DampingRatioNoBouncy,
        ),
        label = "boxBottom",
    )

    // Smooth ~1s fade out when a face leaves the frame
    val animatedAlpha by animateFloatAsState(
        targetValue = if (track.isLeaving) 0f else 1f,
        animationSpec = tween(durationMillis = ScanOverlayConfig.TRACK_FADE_OUT_MILLIS.toInt()),
        label = "trackAlpha",
    )

    if (animatedAlpha <= 0.01f) return

    val boxWidth = (animatedRight - animatedLeft).coerceAtLeast(0f)
    val boxHeight = (animatedBottom - animatedTop).coerceAtLeast(0f)
    val stateColor = track.state.color.toComposeColor()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .graphicsLayer { alpha = animatedAlpha },
    ) {
        // 1. Rounded rectangle bounding box tracking the face
        Canvas(modifier = Modifier.fillMaxSize()) {
            if (boxWidth > 10f && boxHeight > 10f) {
                drawRoundRect(
                    color = stateColor,
                    topLeft = Offset(animatedLeft, animatedTop),
                    size = Size(boxWidth, boxHeight),
                    cornerRadius = CornerRadius(20.dp.toPx(), 20.dp.toPx()),
                    style = Stroke(width = 3.5.dp.toPx()),
                )
            }
        }

        // 2. Info / state badge positioned right under the bottom of the box
        val centerX = (animatedLeft + animatedRight) / 2f
        val badgeTopY = animatedBottom + with(density) { 12.dp.toPx() }

        Box(
            modifier = Modifier
                .offset {
                    IntOffset(
                        x = (centerX - with(density) { 140.dp.toPx() }).roundToInt(),
                        y = badgeTopY.roundToInt(),
                    )
                }
                .widthIn(min = 280.dp, max = 340.dp),
        ) {
            FaceBadgeCard(
                state = track.state,
                stateColor = stateColor,
                onUsePinClicked = onUsePinClicked,
            )
        }
    }
}

@Composable
private fun FaceBadgeCard(
    state: TrackOverlayState,
    stateColor: Color,
    onUsePinClicked: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(18.dp),
        color = Color(0xEE161618),
        border = BorderStroke(1.5.dp, stateColor),
        shadowElevation = 8.dp,
        modifier = Modifier.widthIn(min = 240.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Start,
            ) {
                // Icon ensuring accessible state communication (never color alone)
                when (state.iconType) {
                    OverlayIconType.CHECK -> Icon(
                        imageVector = Icons.Default.CheckCircle,
                        contentDescription = "Verified",
                        tint = stateColor,
                        modifier = Modifier.size(24.dp),
                    )

                    OverlayIconType.CROSS -> Icon(
                        imageVector = Icons.Default.Cancel,
                        contentDescription = "Not Recognized",
                        tint = stateColor,
                        modifier = Modifier.size(24.dp),
                    )

                    OverlayIconType.EYE -> Icon(
                        imageVector = Icons.Default.Visibility,
                        contentDescription = "Action Required",
                        tint = stateColor,
                        modifier = Modifier.size(24.dp),
                    )

                    OverlayIconType.WARNING -> Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Warning",
                        tint = stateColor,
                        modifier = Modifier.size(24.dp),
                    )

                    OverlayIconType.SEARCH -> Icon(
                        imageVector = Icons.Default.Face,
                        contentDescription = "Scanning",
                        tint = stateColor,
                        modifier = Modifier.size(24.dp),
                    )
                }

                Spacer(modifier = Modifier.width(10.dp))

                Column {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = state.primaryText,
                            style = MaterialTheme.typography.titleSmall.copy(
                                fontWeight = FontWeight.Bold,
                                fontSize = 15.sp,
                            ),
                            color = Color.White,
                        )

                        if (state.badgeText != null) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Box(
                                modifier = Modifier
                                    .background(
                                        color = COLOR_GREEN.copy(alpha = 0.2f),
                                        shape = RoundedCornerShape(6.dp),
                                    )
                                    .border(
                                        width = 1.dp,
                                        color = COLOR_GREEN,
                                        shape = RoundedCornerShape(6.dp),
                                    )
                                    .padding(horizontal = 6.dp, vertical = 2.dp),
                            ) {
                                Text(
                                    text = state.badgeText,
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        fontWeight = FontWeight.ExtraBold,
                                        fontSize = 10.sp,
                                    ),
                                    color = COLOR_GREEN,
                                )
                            }
                        }
                    }

                    if (state.secondaryText != null) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = state.secondaryText,
                            style = MaterialTheme.typography.bodySmall.copy(fontSize = 12.sp),
                            color = Color(0xFFDDDDDD),
                        )
                    }
                }
            }

            // Visible button for PIN fallback when face is unrecognised
            if (state.showPinFallbackButton) {
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedButton(
                    onClick = onUsePinClicked,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Color.White,
                    ),
                    border = BorderStroke(1.dp, COLOR_RED.copy(alpha = 0.7f)),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.widthIn(max = 260.dp),
                ) {
                    Icon(
                        imageVector = Icons.Default.Pin,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp),
                        tint = Color.White,
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Use Employee Code & PIN",
                        style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.SemiBold),
                    )
                }
            }
        }
    }
}


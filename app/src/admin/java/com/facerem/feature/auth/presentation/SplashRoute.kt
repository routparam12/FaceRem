package com.facerem.feature.auth.presentation

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.designsystem.component.BrandMark
import com.facerem.core.designsystem.component.brandBrush
import com.facerem.ui.theme.Spacing
import kotlinx.coroutines.delay

/** Minimum time the brand is shown so the splash never flickers on a fast cold start. */
private const val MINIMUM_BRAND_MILLIS = 1_100L

@Composable
fun SplashRoute(
    onNavigate: (String) -> Unit,
    viewModel: SplashViewModel = hiltViewModel(),
) {
    val destination by viewModel.destination.collectAsStateWithLifecycle()

    LaunchedEffect(destination) {
        val target = destination ?: return@LaunchedEffect
        delay(MINIMUM_BRAND_MILLIS)
        onNavigate(target)
    }

    SplashScreen()
}

@Composable
private fun SplashScreen() {
    val markScale = remember { Animatable(0.82f) }
    val contentAlpha = remember { Animatable(0f) }

    LaunchedEffect(Unit) {
        markScale.animateTo(1f, tween(durationMillis = 620))
    }
    LaunchedEffect(Unit) {
        delay(180)
        contentAlpha.animateTo(1f, tween(durationMillis = 520))
    }

    val pulse = rememberInfiniteTransition(label = "splash-pulse")
    val pulseAlpha by pulse.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.85f,
        animationSpec = infiniteRepeatable(
            animation = tween(1_400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "splash-pulse-alpha",
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(brandBrush()),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier.padding(horizontal = Spacing.xl),
        ) {
            BrandMark(
                modifier = Modifier.scale(markScale.value),
                size = 112.dp,
                contentColor = Color.White,
            )
            Spacer(Modifier.height(Spacing.xl))
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.alpha(contentAlpha.value),
            ) {
                Text(
                    text = "FaceAttend",
                    style = MaterialTheme.typography.displaySmall,
                    color = Color.White,
                )
                Spacer(Modifier.height(Spacing.sm))
                Text(
                    text = "Facial attendance for modern teams",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.82f),
                    textAlign = TextAlign.Center,
                )
            }
        }

        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(bottom = 56.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            LinearProgressIndicator(
                modifier = Modifier
                    .width(120.dp)
                    .height(3.dp)
                    .alpha(pulseAlpha),
                color = Color.White,
                trackColor = Color.White.copy(alpha = 0.25f),
            )
            Spacer(Modifier.height(Spacing.lg))
            Text(
                text = "Secure • Private • Multi-tenant",
                style = MaterialTheme.typography.labelSmall,
                color = Color.White.copy(alpha = 0.75f),
            )
        }
    }
}

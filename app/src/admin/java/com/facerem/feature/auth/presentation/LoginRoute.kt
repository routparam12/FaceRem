package com.facerem.feature.auth.presentation

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.PersonOutline
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.designsystem.component.AppTextField
import com.facerem.core.designsystem.component.BrandMark
import com.facerem.core.designsystem.component.InlineMessage
import com.facerem.core.designsystem.component.PasswordField
import com.facerem.core.designsystem.component.PrimaryButton
import com.facerem.core.designsystem.component.SecondaryButton
import com.facerem.ui.theme.Spacing

@Composable
fun LoginRoute(
    onAuthenticated: () -> Unit,
    onForgotPassword: () -> Unit,
    viewModel: LoginViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.authenticated) {
        if (uiState.authenticated) onAuthenticated()
    }

    LoginScreen(
        uiState = uiState,
        onOrganizationCodeChange = viewModel::onOrganizationCodeChange,
        onEmailChange = viewModel::onEmailChange,
        onPasswordChange = viewModel::onPasswordChange,
        onRememberMeChange = viewModel::onRememberMeChange,
        onSignIn = viewModel::signIn,
        onGuestMode = viewModel::continueAsGuest,
        onUseDemoCredentials = viewModel::prefillDemoCredentials,
        onForgotPassword = onForgotPassword,
    )
}

@Composable
private fun LoginScreen(
    uiState: LoginUiState,
    onOrganizationCodeChange: (String) -> Unit,
    onEmailChange: (String) -> Unit,
    onPasswordChange: (String) -> Unit,
    onRememberMeChange: (Boolean) -> Unit,
    onSignIn: () -> Unit,
    onGuestMode: () -> Unit,
    onUseDemoCredentials: () -> Unit,
    onForgotPassword: () -> Unit,
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(Spacing.xxl))
            BrandMark(size = 80.dp)
            Spacer(Modifier.height(Spacing.lg))
            Text("Welcome back", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(Spacing.xs))
            Text(
                "Sign in to your attendance workspace",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )

            Spacer(Modifier.height(Spacing.xl))

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        1.dp,
                        MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.35f),
                        MaterialTheme.shapes.extraLarge,
                    ),
                shape = MaterialTheme.shapes.extraLarge,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(Spacing.lg)) {
                    AppTextField(
                        value = uiState.organizationCode,
                        onValueChange = onOrganizationCodeChange,
                        label = "Organization code (optional)",
                        supportingText = "Leave empty for single-tenant account",
                        leadingIcon = Icons.Default.Apartment,
                        enabled = !uiState.isSubmitting,
                    )
                    Spacer(Modifier.height(Spacing.md))
                    AppTextField(
                        value = uiState.email,
                        onValueChange = onEmailChange,
                        label = "Work email",
                        errorText = uiState.emailError,
                        leadingIcon = Icons.Default.MailOutline,
                        keyboardType = KeyboardType.Email,
                        enabled = !uiState.isSubmitting,
                    )
                    Spacer(Modifier.height(Spacing.md))
                    PasswordField(
                        value = uiState.password,
                        onValueChange = onPasswordChange,
                        errorText = uiState.passwordError,
                        enabled = !uiState.isSubmitting,
                        imeAction = ImeAction.Done,
                    )

                    Spacer(Modifier.height(Spacing.xs))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = uiState.rememberMe, onCheckedChange = onRememberMeChange)
                            Text("Keep me signed in", style = MaterialTheme.typography.bodyMedium)
                        }
                        TextButton(onClick = onForgotPassword) { Text("Forgot?", fontWeight = FontWeight.SemiBold) }
                    }

                    InlineMessage(text = uiState.formError)

                    Spacer(Modifier.height(Spacing.md))
                    PrimaryButton(
                        text = "Sign in",
                        onClick = onSignIn,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = uiState.canSubmit,
                        loading = uiState.isSubmitting,
                    )

                    Spacer(Modifier.height(Spacing.xs))
                    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        TextButton(onClick = onUseDemoCredentials) { Text("Fill demo credentials") }
                    }
                }
            }

            Spacer(Modifier.height(Spacing.xl))

            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                HorizontalDivider(modifier = Modifier.weight(1f))
                Text(
                    "  OR  ",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                HorizontalDivider(modifier = Modifier.weight(1f))
            }

            Spacer(Modifier.height(Spacing.xl))

            // Prominent Guest Mode option at the bottom
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        1.dp,
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.3f),
                        RoundedCornerShape(24.dp),
                    ),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
            ) {
                Column(
                    modifier = Modifier.padding(Spacing.lg),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        "Want to explore without signing in?",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontWeight = FontWeight.Medium,
                    )
                    Spacer(Modifier.height(Spacing.sm))
                    SecondaryButton(
                        text = if (uiState.isGuestSubmitting) "Preparing demo workspace…" else "Continue as guest",
                        onClick = onGuestMode,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !uiState.isSubmitting && !uiState.isGuestSubmitting,
                        leadingIcon = Icons.Default.PersonOutline,
                    )
                }
            }

            Spacer(Modifier.height(Spacing.xl))
            Text(
                "By continuing you agree to the organization's biometric data policy.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(Spacing.xxl))
        }
    }
}

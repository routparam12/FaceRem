package com.facerem.feature.auth.presentation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.designsystem.component.AppTextField
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.InlineMessage
import com.facerem.core.designsystem.component.PrimaryButton
import com.facerem.core.designsystem.component.SecondaryButton
import com.facerem.ui.theme.Spacing

@Composable
fun ForgotPasswordRoute(
    onNavigateUp: () -> Unit,
    viewModel: ForgotPasswordViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = { AppTopBar(title = "Reset password", onNavigateUp = onNavigateUp) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .padding(horizontal = Spacing.screenHorizontal),
        ) {
            Spacer(Modifier.height(Spacing.lg))
            Text(
                "Enter the work email linked to your account. If it exists, we'll send a reset link.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(Spacing.xl))

            if (uiState.isSent) {
                Text("Check your inbox", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(Spacing.sm))
                Text(
                    "If an account exists for ${uiState.email}, a reset link is on its way. " +
                        "The link expires in 30 minutes.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(Spacing.xl))
                SecondaryButton("Back to sign in", onNavigateUp, modifier = Modifier.fillMaxWidth())
            } else {
                AppTextField(
                    value = uiState.email,
                    onValueChange = viewModel::onEmailChange,
                    label = "Work email",
                    errorText = uiState.emailError,
                    leadingIcon = Icons.Default.MailOutline,
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Done,
                    enabled = !uiState.isSubmitting,
                )
                InlineMessage(text = uiState.formError)
                Spacer(Modifier.height(Spacing.lg))
                PrimaryButton(
                    text = "Send reset link",
                    onClick = viewModel::submit,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = uiState.email.isNotBlank(),
                    loading = uiState.isSubmitting,
                )
            }
        }
    }
}

package com.facerem.feature.employees.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Work
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.ui.theme.Spacing

@Composable
fun AddEmployeeRoute(
    onNavigateUp: () -> Unit,
    onEmployeeCreated: (String) -> Unit,
    viewModel: AddEmployeeViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.createdEmployeeId) {
        uiState.createdEmployeeId?.let(onEmployeeCreated)
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Add employee",
                subtitle = "Face enrollment starts after saving",
                onNavigateUp = onNavigateUp,
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.screenHorizontal),
            verticalArrangement = Arrangement.spacedBy(Spacing.md),
        ) {
            SectionHeader(title = "Personal details")
            AppTextField(
                value = uiState.fullName,
                onValueChange = viewModel::onFullNameChange,
                label = "Full name",
                errorText = uiState.fieldErrors[AddEmployeeViewModel.FIELD_NAME],
                leadingIcon = Icons.Default.Person,
            )
            AppTextField(
                value = uiState.email,
                onValueChange = viewModel::onEmailChange,
                label = "Work email",
                errorText = uiState.fieldErrors[AddEmployeeViewModel.FIELD_EMAIL],
                leadingIcon = Icons.Default.MailOutline,
                keyboardType = KeyboardType.Email,
            )
            AppTextField(
                value = uiState.phone,
                onValueChange = viewModel::onPhoneChange,
                label = "Phone",
                errorText = uiState.fieldErrors[AddEmployeeViewModel.FIELD_PHONE],
                leadingIcon = Icons.Default.Phone,
                keyboardType = KeyboardType.Phone,
            )

            Spacer(Modifier.height(Spacing.sm))
            SectionHeader(title = "Employment")
            AppTextField(
                value = uiState.employeeCode,
                onValueChange = viewModel::onEmployeeCodeChange,
                label = "Employee code",
                errorText = uiState.fieldErrors[AddEmployeeViewModel.FIELD_CODE],
                supportingText = "Unique inside your organization",
                leadingIcon = Icons.Default.Badge,
            )
            AppTextField(
                value = uiState.jobTitle,
                onValueChange = viewModel::onJobTitleChange,
                label = "Job title",
                errorText = uiState.fieldErrors[AddEmployeeViewModel.FIELD_TITLE],
                leadingIcon = Icons.Default.Work,
                imeAction = ImeAction.Done,
            )

            ChoiceRow(
                title = "Department",
                options = uiState.departments,
                selected = uiState.department,
                onSelect = viewModel::onDepartmentChange,
            )
            ChoiceRow(
                title = "Branch",
                options = uiState.branches,
                selected = uiState.branch,
                onSelect = viewModel::onBranchChange,
            )
            ChoiceRow(
                title = "Shift",
                options = uiState.shifts,
                selected = uiState.shiftName,
                onSelect = viewModel::onShiftChange,
            )

            InlineMessage(text = uiState.formError)

            Spacer(Modifier.height(Spacing.sm))
            PrimaryButton(
                text = "Save and enroll face",
                onClick = viewModel::submit,
                modifier = Modifier.fillMaxWidth(),
                enabled = uiState.canSubmit,
                loading = uiState.isSubmitting,
            )
            Spacer(Modifier.height(Spacing.xxl))
        }
    }
}

@Composable
private fun ChoiceRow(
    title: String,
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    Column {
        Text(
            title,
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(Spacing.sm))
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            options.forEach { option ->
                FilterChip(
                    selected = option == selected,
                    onClick = { onSelect(option) },
                    label = { Text(option) },
                )
            }
        }
    }
}

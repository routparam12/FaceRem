package com.facerem.feature.employees.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.FaceRetouchingNatural
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Work
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.common.AppClock
import com.facerem.core.common.minutesToHoursLabel
import com.facerem.core.designsystem.component.AppTextField
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.AttendanceStatusPill
import com.facerem.core.designsystem.component.EnrollmentStatusPill
import com.facerem.core.designsystem.component.ErrorState
import com.facerem.core.designsystem.component.FullScreenLoader
import com.facerem.core.designsystem.component.InfoRow
import com.facerem.core.designsystem.component.PrimaryButton
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.feature.employees.domain.UpdateEmployee
import com.facerem.ui.theme.Spacing

@Composable
fun EmployeeDetailRoute(
    onNavigateUp: () -> Unit,
    onEnrollFace: (String) -> Unit,
    viewModel: EmployeeDetailViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = { AppTopBar(title = "Employee", onNavigateUp = onNavigateUp) },
    ) { padding ->
        when {
            uiState.isLoading -> FullScreenLoader(modifier = Modifier.padding(padding))

            uiState.employee == null -> ErrorState(
                title = "Employee unavailable",
                message = uiState.errorMessage ?: "This employee could not be loaded.",
                onRetry = viewModel::load,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            )

            else -> EmployeeDetailContent(
                contentPadding = padding,
                employee = requireNotNull(uiState.employee),
                attendance = uiState.recentAttendance,
                onEnrollFace = onEnrollFace,
                onUpdateEmployee = { update -> viewModel.updateEmployee(update) },
            )
        }
    }
}

@Composable
private fun EmployeeDetailContent(
    contentPadding: PaddingValues,
    employee: Employee,
    attendance: List<AttendanceRecord>,
    onEnrollFace: (String) -> Unit,
    onUpdateEmployee: (UpdateEmployee) -> Unit,
) {
    var showEditDialog by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding),
        contentPadding = PaddingValues(
            start = Spacing.screenHorizontal,
            end = Spacing.screenHorizontal,
            bottom = Spacing.xxl,
        ),
        verticalArrangement = Arrangement.spacedBy(Spacing.lg),
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                UserAvatar(name = employee.fullName, size = 64.dp)
                Spacer(Modifier.width(Spacing.lg))
                Column(modifier = Modifier.weight(1f)) {
                    Text(employee.fullName, style = MaterialTheme.typography.titleLarge)
                    Text(
                        employee.jobTitle.ifBlank { "No title" },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(Spacing.sm))
                    EnrollmentStatusPill(employee.faceEnrollment)
                }
            }
        }

        if (employee.faceEnrollment != FaceEnrollmentStatus.ENROLLED) {
            item {
                PrimaryButton(
                    text = "Enroll face profile",
                    onClick = { onEnrollFace(employee.id) },
                    modifier = Modifier.fillMaxWidth(),
                    leadingIcon = Icons.Default.FaceRetouchingNatural,
                )
            }
        } else {
            item {
                Text(
                    "Face profile active. Re-enrollment replaces the stored embedding; " +
                        "attendance history is never deleted.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.large,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                Column(modifier = Modifier.padding(Spacing.lg)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Information", style = MaterialTheme.typography.titleMedium)
                        TextButton(onClick = { showEditDialog = true }) {
                            Icon(Icons.Default.Edit, contentDescription = "Edit details", modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Edit")
                        }
                    }
                    Spacer(Modifier.height(Spacing.sm))
                    InfoRow("Employee code", employee.employeeCode, icon = Icons.Default.Badge)
                    InfoRow("Department", employee.department, icon = Icons.Default.Work)
                    InfoRow("Branch", employee.branch, icon = Icons.Default.Apartment)
                    InfoRow("Shift", employee.shiftName, icon = Icons.Default.Schedule)
                    InfoRow("Email", employee.email, icon = Icons.Default.MailOutline)
                    InfoRow("Phone", employee.phone.ifBlank { "Not set" }, icon = Icons.Default.Phone)
                    InfoRow(
                        "Status",
                        if (employee.isActive) "Active" else "Inactive",
                        icon = Icons.Default.CalendarMonth,
                    )
                }
            }
        }

        item { SectionHeader(title = "Recent attendance") }

        items(attendance, key = { it.id }) { record ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        AppClock.formatIsoAsReadable(record.date),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        buildString {
                            append(record.checkInTime ?: "—")
                            append(" → ")
                            append(record.checkOutTime ?: "—")
                            if (record.workedMinutes > 0) {
                                append(" • ${minutesToHoursLabel(record.workedMinutes)}")
                            }
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                AttendanceStatusPill(record.status)
            }
        }
    }

    if (showEditDialog) {
        var nameInput by remember { mutableStateOf(employee.fullName) }
        var titleInput by remember { mutableStateOf(employee.jobTitle) }
        var emailInput by remember { mutableStateOf(employee.email) }
        var phoneInput by remember { mutableStateOf(employee.phone) }
        var deptInput by remember { mutableStateOf(employee.department) }

        AlertDialog(
            onDismissRequest = { showEditDialog = false },
            title = { Text("Edit employee details") },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    AppTextField(
                        value = nameInput,
                        onValueChange = { nameInput = it },
                        label = "Full Name",
                        modifier = Modifier.fillMaxWidth(),
                    )
                    AppTextField(
                        value = titleInput,
                        onValueChange = { titleInput = it },
                        label = "Job Title",
                        modifier = Modifier.fillMaxWidth(),
                    )
                    AppTextField(
                        value = emailInput,
                        onValueChange = { emailInput = it },
                        label = "Email Address",
                        modifier = Modifier.fillMaxWidth(),
                    )
                    AppTextField(
                        value = phoneInput,
                        onValueChange = { phoneInput = it },
                        label = "Phone Number",
                        modifier = Modifier.fillMaxWidth(),
                    )
                    AppTextField(
                        value = deptInput,
                        onValueChange = { deptInput = it },
                        label = "Department",
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (nameInput.isNotBlank() && emailInput.isNotBlank()) {
                            onUpdateEmployee(
                                UpdateEmployee(
                                    fullName = nameInput.trim(),
                                    jobTitle = titleInput.trim(),
                                    email = emailInput.trim(),
                                    phone = phoneInput.trim(),
                                    department = deptInput.trim(),
                                ),
                            )
                            showEditDialog = false
                        }
                    },
                    enabled = nameInput.isNotBlank() && emailInput.isNotBlank(),
                ) {
                    Text("Save")
                }
            },
            dismissButton = {
                TextButton(onClick = { showEditDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }
}

package com.facerem.feature.employees.presentation

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.PersonAddAlt
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.app.navigation.BottomBarClearance
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.EmptyState
import com.facerem.core.designsystem.component.EnrollmentStatusPill
import com.facerem.core.designsystem.component.FullScreenLoader
import com.facerem.core.designsystem.component.GuestModeBanner
import com.facerem.core.designsystem.component.SearchBar
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.core.model.Employee
import com.facerem.ui.theme.Spacing

@Composable
fun EmployeesRoute(
    onOpenEmployee: (String) -> Unit,
    onAddEmployee: () -> Unit,
    viewModel: EmployeesViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            AppTopBar(
                title = "People",
                subtitle = "${uiState.employees.size} employees",
                actions = {
                    IconButton(onClick = onAddEmployee) {
                        Icon(Icons.Default.PersonAddAlt, contentDescription = "Add employee")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            Column(modifier = Modifier.padding(horizontal = Spacing.screenHorizontal)) {
                if (uiState.isGuest) {
                    GuestModeBanner()
                    Spacer(Modifier.height(Spacing.md))
                }
                SearchBar(
                    query = uiState.query,
                    onQueryChange = viewModel::onQueryChange,
                    placeholder = "Search name, code or department",
                )
                Spacer(Modifier.height(Spacing.md))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    EmployeeFilter.entries.forEach { filter ->
                        FilterChip(
                            selected = uiState.filter == filter,
                            onClick = { viewModel.onFilterChange(filter) },
                            label = { Text(filter.label) },
                        )
                    }
                }
                Spacer(Modifier.height(Spacing.sm))
            }

            when {
                uiState.isLoading -> FullScreenLoader(message = "Loading employees…")

                uiState.visibleEmployees.isEmpty() -> EmptyState(
                    title = "No employees match",
                    message = "Adjust the search or filter, or add a new employee to this organization.",
                    icon = Icons.Default.Groups,
                    actionText = "Add employee",
                    onAction = onAddEmployee,
                    modifier = Modifier.fillMaxWidth(),
                )

                else -> LazyColumn(
                    contentPadding = PaddingValues(
                        start = Spacing.screenHorizontal,
                        end = Spacing.screenHorizontal,
                        bottom = BottomBarClearance,
                    ),
                ) {
                    items(uiState.visibleEmployees, key = { it.id }) { employee ->
                        EmployeeRow(employee = employee, onClick = { onOpenEmployee(employee.id) })
                        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun EmployeeRow(employee: Employee, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = Spacing.md),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        UserAvatar(name = employee.fullName)
        Spacer(Modifier.width(Spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                employee.fullName,
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                "${employee.employeeCode} • ${employee.department}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(Spacing.sm))
        EnrollmentStatusPill(employee.faceEnrollment)
    }
}

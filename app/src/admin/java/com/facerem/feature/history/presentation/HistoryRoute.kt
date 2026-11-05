package com.facerem.feature.history.presentation

import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.EventNote
import androidx.compose.material.icons.filled.InsertChart
import androidx.compose.material3.FilterChip
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
import com.facerem.core.common.AppClock
import com.facerem.core.common.minutesToHoursLabel
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.AttendanceStatusPill
import com.facerem.core.designsystem.component.EmptyState
import com.facerem.core.designsystem.component.FullScreenLoader
import com.facerem.core.designsystem.component.SearchBar
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.ui.theme.Spacing

@Composable
fun HistoryRoute(
    onOpenReports: () -> Unit,
    viewModel: HistoryViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Attendance history",
                subtitle = "${uiState.visibleRecords.size} records",
                actions = {
                    IconButton(onClick = onOpenReports) {
                        Icon(Icons.Default.InsertChart, contentDescription = "Reports")
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
                SearchBar(
                    query = uiState.query,
                    onQueryChange = viewModel::onQueryChange,
                    placeholder = "Search employee",
                )
                Spacer(Modifier.height(Spacing.md))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    HistoryRange.entries.forEach { range ->
                        FilterChip(
                            selected = uiState.range == range,
                            onClick = { viewModel.onRangeChange(range) },
                            label = { Text(range.label) },
                        )
                    }
                }
                Spacer(Modifier.height(Spacing.sm))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    FilterChip(
                        selected = uiState.statusFilter == null,
                        onClick = { viewModel.onStatusFilterChange(null) },
                        label = { Text("All statuses") },
                    )
                    AttendanceStatus.entries.forEach { status ->
                        FilterChip(
                            selected = uiState.statusFilter == status,
                            onClick = { viewModel.onStatusFilterChange(status) },
                            label = { Text(status.displayName) },
                        )
                    }
                }
                Spacer(Modifier.height(Spacing.sm))
            }

            when {
                uiState.isLoading -> FullScreenLoader(message = "Loading attendance…")

                uiState.visibleRecords.isEmpty() -> EmptyState(
                    title = "No records",
                    message = "No attendance matches the current range and filters.",
                    icon = Icons.AutoMirrored.Filled.EventNote,
                    modifier = Modifier.fillMaxWidth(),
                )

                else -> LazyColumn(
                    contentPadding = PaddingValues(
                        start = Spacing.screenHorizontal,
                        end = Spacing.screenHorizontal,
                        bottom = BottomBarClearance,
                    ),
                    verticalArrangement = Arrangement.spacedBy(Spacing.md),
                ) {
                    uiState.groupedByDate.forEach { (date, records) ->
                        item(key = "header-$date") {
                            Text(
                                AppClock.formatIsoAsReadable(date),
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(top = Spacing.sm),
                            )
                        }
                        items(records, key = { it.id }) { record ->
                            HistoryRow(record)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryRow(record: AttendanceRecord) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        UserAvatar(name = record.employeeName, size = 40.dp)
        Spacer(Modifier.width(Spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                record.employeeName,
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                buildString {
                    append(record.checkInTime ?: "—")
                    append(" → ")
                    append(record.checkOutTime ?: "—")
                    if (record.workedMinutes > 0) append(" • ${minutesToHoursLabel(record.workedMinutes)}")
                    if (record.lateMinutes > 0) append(" • ${record.lateMinutes}m late")
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        AttendanceStatusPill(record.status)
    }
}

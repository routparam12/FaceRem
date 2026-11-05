package com.facerem.feature.reports.presentation

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.MoreTime
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.WorkHistory
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.facerem.core.common.grouped
import com.facerem.core.designsystem.component.AppTopBar
import com.facerem.core.designsystem.component.ErrorState
import com.facerem.core.designsystem.component.FullScreenLoader
import com.facerem.core.designsystem.component.GuestModeBanner
import com.facerem.core.designsystem.component.RateBar
import com.facerem.core.designsystem.component.SecondaryButton
import com.facerem.core.designsystem.component.SectionHeader
import com.facerem.core.designsystem.component.StatCard
import com.facerem.ui.theme.AppTheme
import com.facerem.ui.theme.Spacing

@Composable
fun ReportsRoute(
    onNavigateUp: () -> Unit,
    viewModel: ReportsViewModel = hiltViewModel(),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val semantic = AppTheme.colors

    LaunchedEffect(uiState.exportMessage) {
        val message = uiState.exportMessage ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(message)
        viewModel.dismissExportMessage()
    }

    Scaffold(
        topBar = {
            AppTopBar(
                title = "Reports",
                subtitle = uiState.summary?.periodLabel,
                onNavigateUp = onNavigateUp,
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        val summary = uiState.summary
        when {
            uiState.isLoading -> FullScreenLoader(modifier = Modifier.padding(padding))

            summary == null -> ErrorState(
                title = "Reports unavailable",
                message = uiState.errorMessage ?: "Please try again.",
                onRetry = viewModel::load,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            )

            else -> LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(
                    start = Spacing.screenHorizontal,
                    end = Spacing.screenHorizontal,
                    bottom = Spacing.xxl,
                ),
                verticalArrangement = Arrangement.spacedBy(Spacing.lg),
            ) {
                if (uiState.isGuest) {
                    item { GuestModeBanner() }
                }

                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = MaterialTheme.shapes.large,
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceContainer,
                        ),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                    ) {
                        Column(modifier = Modifier.padding(Spacing.lg)) {
                            RateBar(
                                label = "Average attendance rate",
                                rate = summary.averageAttendanceRate,
                                caption = summary.periodLabel,
                            )
                        }
                    }
                }

                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(Spacing.md)) {
                        StatCard(
                            label = "Hours worked",
                            value = summary.totalWorkedHours.grouped(),
                            icon = Icons.Default.WorkHistory,
                            accent = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.weight(1f),
                        )
                        StatCard(
                            label = "Overtime hours",
                            value = summary.totalOvertimeHours.grouped(),
                            icon = Icons.Default.MoreTime,
                            accent = semantic.info,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }

                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(Spacing.md)) {
                        StatCard(
                            label = "Late arrivals",
                            value = summary.lateArrivals.toString(),
                            icon = Icons.Default.Schedule,
                            accent = semantic.warning,
                            modifier = Modifier.weight(1f),
                        )
                        StatCard(
                            label = "Absences",
                            value = summary.absences.toString(),
                            icon = Icons.Default.EventBusy,
                            accent = MaterialTheme.colorScheme.error,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }

                item { SectionHeader(title = "By department") }

                items(summary.departmentBreakdown, key = { it.department }) { department ->
                    RateBar(
                        label = department.department,
                        rate = department.rate,
                        caption = "${department.headCount} people",
                    )
                }

                item {
                    Spacer(Modifier.height(Spacing.sm))
                    SecondaryButton(
                        text = "Export CSV",
                        onClick = viewModel::requestExport,
                        modifier = Modifier.fillMaxWidth(),
                        leadingIcon = Icons.Default.FileDownload,
                    )
                }
            }
        }
    }
}

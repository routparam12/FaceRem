package com.facerem.feature.dashboard.presentation

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.HowToReg
import androidx.compose.material.icons.filled.PersonAddAlt
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.facerem.core.common.AppClock
import com.facerem.core.designsystem.component.AttendanceStatusPill
import com.facerem.core.designsystem.component.UserAvatar
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.DashboardSummary
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.ui.theme.AppTheme
import com.facerem.ui.theme.Spacing

import com.facerem.ui.theme.Glass

enum class DashboardStatCategory(
    val title: String,
    val icon: ImageVector,
) {
    PRESENT("Present Today", Icons.Default.HowToReg),
    LATE("Late Arrivals", Icons.Default.Schedule),
    ABSENT("Absences & Leave", Icons.Default.EventBusy),
    FACE_ENROLLMENT("Pending Face Enrollment", Icons.Default.PersonAddAlt),
}

data class DetailItem(
    val id: String,
    val name: String,
    val code: String,
    val department: String,
    val secondaryInfo: String,
    val statusText: String,
    val statusColor: Color,
    val attendanceStatus: AttendanceStatus? = null,
    val faceStatus: FaceEnrollmentStatus? = null,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatDetailModalSheet(
    category: DashboardStatCategory,
    summary: DashboardSummary,
    employees: List<Employee>,
    attendanceRecords: List<AttendanceRecord>,
    onDismissRequest: () -> Unit,
    onEmployeeClick: ((String) -> Unit)? = null,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
) {
    val items = buildDetailItems(category, summary, employees, attendanceRecords)
    val accentColor = when (category) {
        DashboardStatCategory.PRESENT -> AppTheme.colors.success
        DashboardStatCategory.LATE -> AppTheme.colors.warning
        DashboardStatCategory.ABSENT -> MaterialTheme.colorScheme.error
        DashboardStatCategory.FACE_ENROLLMENT -> MaterialTheme.colorScheme.tertiary
    }

    ModalBottomSheet(
        onDismissRequest = onDismissRequest,
        sheetState = sheetState,
        containerColor = if (Glass.isActive) Color.White else MaterialTheme.colorScheme.surface,
        scrimColor = Color.Black.copy(alpha = 0.55f),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = Spacing.xxl),
        ) {
            // Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = Spacing.screenHorizontal, vertical = Spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(accentColor.copy(alpha = 0.16f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            category.icon,
                            contentDescription = null,
                            tint = accentColor,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                    Spacer(Modifier.width(Spacing.md))
                    Column {
                        Text(
                            category.title,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "${items.size} employee${if (items.size == 1) "" else "s"}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                IconButton(onClick = onDismissRequest) {
                    Icon(Icons.Default.Close, contentDescription = "Close")
                }
            }

            HorizontalDivider(
                modifier = Modifier.padding(vertical = Spacing.xs),
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f),
            )

            if (items.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = Spacing.xxl),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "No employees found in this category.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(
                        horizontal = Spacing.screenHorizontal,
                        vertical = Spacing.md,
                    ),
                    verticalArrangement = Arrangement.spacedBy(Spacing.sm),
                ) {
                    items(items, key = { it.id }) { item ->
                        DetailItemRow(
                            item = item,
                            onClick = if (onEmployeeClick != null) {
                                { onEmployeeClick(item.id) }
                            } else null,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailItemRow(
    item: DetailItem,
    onClick: (() -> Unit)?,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(
                if (Glass.isActive) Color(0xFFF1F5F9)
                else MaterialTheme.colorScheme.surfaceContainerHigh,
            )
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = Spacing.md, vertical = Spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        UserAvatar(name = item.name, size = 42.dp)
        Spacer(Modifier.width(Spacing.md))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                item.name,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                buildString {
                    append(item.code)
                    if (item.department.isNotBlank()) append(" • ${item.department}")
                    if (item.secondaryInfo.isNotBlank()) append(" • ${item.secondaryInfo}")
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(Spacing.xs))
        if (item.attendanceStatus != null) {
            AttendanceStatusPill(item.attendanceStatus)
        } else {
            Surface(
                shape = CircleShape,
                color = item.statusColor.copy(alpha = 0.15f),
            ) {
                Text(
                    item.statusText,
                    modifier = Modifier.padding(horizontal = Spacing.md, vertical = Spacing.xs),
                    style = MaterialTheme.typography.labelSmall,
                    color = item.statusColor,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

private fun buildDetailItems(
    category: DashboardStatCategory,
    summary: DashboardSummary,
    employees: List<Employee>,
    attendanceRecords: List<AttendanceRecord>,
): List<DetailItem> {
    val today = AppClock.todayIso()
    val todayRecords = attendanceRecords.filter { it.date == today }
    val recordMap = todayRecords.associateBy { it.employeeId }

    return when (category) {
        DashboardStatCategory.PRESENT -> {
            todayRecords
                .filter { it.status == AttendanceStatus.PRESENT || it.status == AttendanceStatus.HALF_DAY }
                .map { rec ->
                    DetailItem(
                        id = rec.employeeId,
                        name = rec.employeeName,
                        code = rec.employeeCode,
                        department = rec.department,
                        secondaryInfo = rec.checkInTime?.let { "In $it" }.orEmpty(),
                        statusText = rec.status.displayName,
                        statusColor = Color(0xFF10B981),
                        attendanceStatus = rec.status,
                    )
                }
        }

        DashboardStatCategory.LATE -> {
            todayRecords
                .filter { it.status == AttendanceStatus.LATE }
                .map { rec ->
                    DetailItem(
                        id = rec.employeeId,
                        name = rec.employeeName,
                        code = rec.employeeCode,
                        department = rec.department,
                        secondaryInfo = buildString {
                            rec.checkInTime?.let { append("In $it") }
                            if (rec.lateMinutes > 0) append(" (${rec.lateMinutes}m late)")
                        },
                        statusText = rec.status.displayName,
                        statusColor = Color(0xFFF59E0B),
                        attendanceStatus = rec.status,
                    )
                }
        }

        DashboardStatCategory.ABSENT -> {
            val absentRecords = todayRecords.filter {
                it.status == AttendanceStatus.ABSENT || it.status == AttendanceStatus.ON_LEAVE
            }
            val absentEmployeeIds = absentRecords.map { it.employeeId }.toSet()

            val itemsFromRecords = absentRecords.map { rec ->
                DetailItem(
                    id = rec.employeeId,
                    name = rec.employeeName,
                    code = rec.employeeCode,
                    department = rec.department,
                    secondaryInfo = "Not checked in",
                    statusText = rec.status.displayName,
                    statusColor = if (rec.status == AttendanceStatus.ON_LEAVE) Color(0xFF3B82F6) else Color(0xFFEF4444),
                    attendanceStatus = rec.status,
                )
            }

            val unrecordedEmployees = employees
                .filter { it.isActive && it.id !in recordMap && it.id !in absentEmployeeIds }
                .map { emp ->
                    DetailItem(
                        id = emp.id,
                        name = emp.fullName,
                        code = emp.employeeCode,
                        department = emp.department,
                        secondaryInfo = emp.jobTitle,
                        statusText = "Absent",
                        statusColor = Color(0xFFEF4444),
                        attendanceStatus = AttendanceStatus.ABSENT,
                    )
                }

            itemsFromRecords + unrecordedEmployees
        }

        DashboardStatCategory.FACE_ENROLLMENT -> {
            employees
                .filter { it.faceEnrollment != FaceEnrollmentStatus.ENROLLED }
                .map { emp ->
                    val color = if (emp.faceEnrollment == FaceEnrollmentStatus.EXPIRED) Color(0xFFEF4444) else Color(0xFFF59E0B)
                    DetailItem(
                        id = emp.id,
                        name = emp.fullName,
                        code = emp.employeeCode,
                        department = emp.department,
                        secondaryInfo = emp.jobTitle,
                        statusText = emp.faceEnrollment.displayName,
                        statusColor = color,
                        faceStatus = emp.faceEnrollment,
                    )
                }
        }
    }
}

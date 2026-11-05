package com.facerem.feature.history

import com.facerem.core.common.AppClock
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.feature.history.presentation.HistoryRange
import com.facerem.feature.history.presentation.HistoryUiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HistoryUiStateTest {

    private val today = record("r-today", daysAgo = 0, name = "Aarav Sharma", status = AttendanceStatus.PRESENT)
    private val threeDaysAgo = record("r-3", daysAgo = 3, name = "Priya Nair", status = AttendanceStatus.LATE)
    private val tenDaysAgo = record("r-10", daysAgo = 10, name = "Rahul Verma", status = AttendanceStatus.ABSENT)
    private val state = HistoryUiState(records = listOf(today, threeDaysAgo, tenDaysAgo))

    @Test
    fun `today range keeps only today's records`() {
        val visible = state.copy(range = HistoryRange.TODAY).visibleRecords
        assertEquals(listOf("r-today"), visible.map { it.id })
    }

    @Test
    fun `week range excludes records older than seven days`() {
        val visible = state.copy(range = HistoryRange.WEEK).visibleRecords
        assertEquals(setOf("r-today", "r-3"), visible.map { it.id }.toSet())
    }

    @Test
    fun `fortnight range includes everything seeded`() {
        val visible = state.copy(range = HistoryRange.FORTNIGHT).visibleRecords
        assertEquals(3, visible.size)
    }

    @Test
    fun `status filter narrows the range result`() {
        val visible = state.copy(
            range = HistoryRange.FORTNIGHT,
            statusFilter = AttendanceStatus.LATE,
        ).visibleRecords
        assertEquals(listOf("r-3"), visible.map { it.id })
    }

    @Test
    fun `query matches name case insensitively`() {
        val visible = state.copy(range = HistoryRange.FORTNIGHT, query = "priya").visibleRecords
        assertEquals(listOf("r-3"), visible.map { it.id })
    }

    @Test
    fun `query matches employee code`() {
        val visible = state.copy(range = HistoryRange.FORTNIGHT, query = "NW-r-10").visibleRecords
        assertEquals(listOf("r-10"), visible.map { it.id })
    }

    @Test
    fun `grouping is ordered newest date first`() {
        val grouped = state.copy(range = HistoryRange.FORTNIGHT).groupedByDate
        assertEquals(3, grouped.size)
        assertTrue(grouped[0].first > grouped[1].first)
        assertTrue(grouped[1].first > grouped[2].first)
    }

    private fun record(
        id: String,
        daysAgo: Int,
        name: String,
        status: AttendanceStatus,
    ) = AttendanceRecord(
        id = id,
        employeeId = "emp-$id",
        employeeName = name,
        employeeCode = "NW-$id",
        department = "Engineering",
        date = AppClock.isoDate(daysAgo),
        checkInTime = "09:05 AM",
        checkOutTime = "06:10 PM",
        status = status,
    )
}

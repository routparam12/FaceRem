package com.facerem.core.data.demo

import com.facerem.core.common.AppClock
import com.facerem.core.model.AttendanceEventType
import com.facerem.core.model.AttendanceRecord
import com.facerem.core.model.AttendanceStatus
import com.facerem.core.model.Branch
import com.facerem.core.model.DailyRate
import com.facerem.core.model.Department
import com.facerem.core.model.DepartmentRate
import com.facerem.core.model.Employee
import com.facerem.core.model.FaceEnrollmentStatus
import com.facerem.core.model.Organization
import com.facerem.core.model.RecognitionOutcome
import com.facerem.core.model.ReportSummary
import com.facerem.core.model.Role
import com.facerem.core.model.Shift
import com.facerem.core.model.SubscriptionPlan
import com.facerem.core.model.User
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.math.abs
import kotlin.random.Random
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * In-memory dataset that powers guest/demo mode and local UI development.
 *
 * This exists so the client can be exercised end to end before the FastAPI backend is wired in.
 * Every repository reads through this store today; when the real API lands, only the repository
 * implementations change. Nothing here is authoritative and none of it leaves the device.
 */
@Singleton
class DemoDataStore @Inject constructor() {

    val organization = Organization(
        id = DEMO_ORGANIZATION_ID,
        name = "Northwind Industries",
        plan = SubscriptionPlan.GROWTH,
        employeeCount = 48,
        branchCount = 3,
        timeZone = "Asia/Kolkata",
    )

    val guestUser = User(
        id = "guest-user",
        fullName = "Guest Reviewer",
        email = "guest@faceattend.demo",
        role = Role.ORGANIZATION_ADMIN,
        organizationId = DEMO_ORGANIZATION_ID,
        organizationName = organization.name,
        jobTitle = "Demo access",
    )

    private val mutableEmployees = MutableStateFlow(seedEmployees())
    val employees: StateFlow<List<Employee>> = mutableEmployees.asStateFlow()

    private val mutableAttendance = MutableStateFlow(seedAttendance(mutableEmployees.value))
    val attendance: StateFlow<List<AttendanceRecord>> = mutableAttendance.asStateFlow()

    val departments: List<Department> = listOf(
        Department("dep-eng", "Engineering", 16),
        Department("dep-ops", "Operations", 12),
        Department("dep-sales", "Sales", 9),
        Department("dep-hr", "People & HR", 6),
        Department("dep-fin", "Finance", 5),
    )

    val branches: List<Branch> = listOf(
        Branch("br-hq", "Head office", "Bengaluru", 28),
        Branch("br-north", "North plant", "Noida", 13),
        Branch("br-west", "West depot", "Pune", 7),
    )

    val shifts: List<Shift> = listOf(
        Shift("sh-general", "General shift", "09:00", "18:00", graceMinutes = 10),
        Shift("sh-morning", "Morning shift", "06:00", "14:00", graceMinutes = 10),
        Shift("sh-night", "Night shift", "22:00", "06:00", graceMinutes = 15),
    )

    fun signInWithCredentials(email: String): User = User(
        id = "user-admin",
        fullName = email.substringBefore('@')
            .split('.', '_', '-')
            .filter { it.isNotBlank() }
            .joinToString(" ") { part -> part.replaceFirstChar { it.uppercase() } }
            .ifBlank { "Organization Admin" },
        email = email,
        role = Role.ORGANIZATION_ADMIN,
        organizationId = organization.id,
        organizationName = organization.name,
        jobTitle = "Organization admin",
    )

    fun addEmployee(employee: Employee) {
        mutableEmployees.update { current -> current + employee }
    }

    fun updateEnrollment(employeeId: String, status: FaceEnrollmentStatus) {
        mutableEmployees.update { current ->
            current.map { if (it.id == employeeId) it.copy(faceEnrollment = status) else it }
        }
    }

    fun employeeById(id: String): Employee? = mutableEmployees.value.firstOrNull { it.id == id }

    fun attendanceFor(employeeId: String): List<AttendanceRecord> =
        mutableAttendance.value.filter { it.employeeId == employeeId }

    /**
     * Simulates the server-side recognition result. The real implementation posts a single frame
     * to `POST /api/v1/attendance/recognize` and the backend performs the organization-scoped
     * vector search; nothing about identity is ever decided on the device.
     */
    /**
     * Mirrors the server's scan rules so guest mode behaves like a real gate: the first scan of
     * the day checks someone in, further scans report that they are already present, and only a
     * scan well after check-in ends the day.
     *
     * The real window is four hours (`CHECKOUT_AFTER_MINUTES`). Demo mode shortens it to two
     * minutes so a reviewer can actually watch a check-out happen.
     */
    fun simulateRecognition(): RecognitionOutcome {
        val enrolled = mutableEmployees.value.filter { it.faceEnrollment == FaceEnrollmentStatus.ENROLLED }
        if (enrolled.isEmpty()) {
            return RecognitionOutcome.NotRecognized("No enrolled faces in this demo organization yet.")
        }
        // One in six attempts models the unknown-face path so that state can be reviewed.
        if (Random.nextInt(6) == 0) {
            return RecognitionOutcome.NotRecognized("Face not recognized. Ask an admin to enroll this person.")
        }

        val employee = enrolled.random()
        val today = AppClock.todayIso()
        val existing = mutableAttendance.value.firstOrNull { it.employeeId == employee.id && it.date == today }
        val timeLabel = AppClock.nowTimeLabel()
        val event = resolveDemoEvent(employee.id, existing)

        if (event == AttendanceEventType.ALREADY_PRESENT) {
            // Nothing is written, exactly as the server does for a repeat scan.
            return RecognitionOutcome.Recognized(
                employeeId = employee.id,
                employeeName = employee.fullName,
                employeeCode = employee.employeeCode,
                department = employee.department,
                eventType = event,
                timeLabel = timeLabel,
                confidence = Random.nextDouble(0.87, 0.99).toFloat(),
                status = existing?.status ?: AttendanceStatus.PRESENT,
                lateMinutes = existing?.lateMinutes ?: 0,
                checkInLabel = existing?.checkInTime,
                checkOutLabel = existing?.checkOutTime,
            )
        }

        val isCheckOut = event == AttendanceEventType.CHECK_OUT
        val lateMinutes = existing?.lateMinutes
            ?: if (Random.nextInt(4) == 0) Random.nextInt(5, 35) else 0
        val status = when {
            isCheckOut -> existing?.status ?: AttendanceStatus.PRESENT
            lateMinutes > 0 -> AttendanceStatus.LATE
            else -> AttendanceStatus.PRESENT
        }

        if (!isCheckOut) {
            checkInEpochMillis[employee.id] = System.currentTimeMillis()
        }

        val updated = existing?.copy(
            checkOutTime = if (isCheckOut) timeLabel else existing.checkOutTime,
            checkInTime = existing.checkInTime ?: timeLabel,
            status = status,
            workedMinutes = if (isCheckOut) Random.nextInt(430, 560) else existing.workedMinutes,
        ) ?: AttendanceRecord(
            id = "att-${employee.id}-$today",
            employeeId = employee.id,
            employeeName = employee.fullName,
            employeeCode = employee.employeeCode,
            department = employee.department,
            date = today,
            checkInTime = timeLabel,
            checkOutTime = null,
            status = status,
            lateMinutes = lateMinutes,
            workedMinutes = 0,
        )
        mutableAttendance.update { records -> records.filterNot { it.id == updated.id } + updated }

        return RecognitionOutcome.Recognized(
            employeeId = employee.id,
            employeeName = employee.fullName,
            employeeCode = employee.employeeCode,
            department = employee.department,
            eventType = event,
            timeLabel = timeLabel,
            confidence = Random.nextDouble(0.87, 0.99).toFloat(),
            status = status,
            lateMinutes = lateMinutes,
            checkInLabel = updated.checkInTime,
            checkOutLabel = updated.checkOutTime,
        )
    }

    /** Check-in times for scans made during this session, used to time the demo check-out. */
    private val checkInEpochMillis = mutableMapOf<String, Long>()

    private fun resolveDemoEvent(
        employeeId: String,
        existing: AttendanceRecord?,
    ): AttendanceEventType {
        if (existing?.checkInTime == null) return AttendanceEventType.CHECK_IN
        if (existing.checkOutTime != null) return AttendanceEventType.ALREADY_PRESENT

        // Seeded records have no session timestamp; treat them as a normal open day.
        val checkedInAt = checkInEpochMillis[employeeId] ?: return AttendanceEventType.ALREADY_PRESENT
        val elapsedMinutes = (System.currentTimeMillis() - checkedInAt) / 60_000
        return if (elapsedMinutes >= DEMO_CHECKOUT_AFTER_MINUTES) {
            AttendanceEventType.CHECK_OUT
        } else {
            AttendanceEventType.ALREADY_PRESENT
        }
    }

    fun weeklyRates(): List<DailyRate> = (5 downTo 0).map { daysAgo ->
        val label = AppClock.dayLabel(daysAgo)
        val seed = abs((label.hashCode() + daysAgo * 31)) % 18
        DailyRate(dayLabel = label, rate = (0.78f + seed / 100f).coerceAtMost(0.98f))
    }

    fun reportSummary(): ReportSummary = ReportSummary(
        periodLabel = AppClock.currentMonthLabel(),
        averageAttendanceRate = 0f,
        totalWorkedHours = 0,
        totalOvertimeHours = 0,
        lateArrivals = 0,
        absences = 0,
        departmentBreakdown = emptyList(),
    )

    private fun seedEmployees(): List<Employee> {
        val people = listOf(
            Triple("Aarav Sharma", "Engineering", "Senior Android Engineer"),
            Triple("Priya Nair", "People & HR", "HR Business Partner"),
            Triple("Rahul Verma", "Operations", "Shift Supervisor"),
            Triple("Ananya Iyer", "Sales", "Account Executive"),
            Triple("Vikram Singh", "Engineering", "Backend Engineer"),
            Triple("Meera Joshi", "Finance", "Financial Analyst"),
            Triple("Kabir Khan", "Operations", "Logistics Coordinator"),
            Triple("Sneha Reddy", "Engineering", "QA Engineer"),
            Triple("Arjun Mehta", "Sales", "Regional Manager"),
            Triple("Divya Pillai", "People & HR", "Recruiter"),
            Triple("Rohan Gupta", "Operations", "Machine Operator"),
            Triple("Isha Kulkarni", "Finance", "Payroll Specialist"),
        )
        val branchNames = listOf("Head office", "North plant", "West depot")
        val shiftNames = listOf("General shift", "Morning shift", "Night shift")
        return people.mapIndexed { index, (name, department, title) ->
            val enrollment = when {
                index % 7 == 6 -> FaceEnrollmentStatus.EXPIRED
                index % 5 == 4 -> FaceEnrollmentStatus.PENDING
                else -> FaceEnrollmentStatus.ENROLLED
            }
            Employee(
                id = "emp-${index + 1}",
                employeeCode = "NW-${(1001 + index)}",
                fullName = name,
                email = name.lowercase().replace(" ", ".") + "@northwind.demo",
                phone = "+91 98%06d".format((100000 + index * 4321) % 1000000),
                department = department,
                branch = branchNames[index % branchNames.size],
                jobTitle = title,
                shiftName = shiftNames[index % shiftNames.size],
                faceEnrollment = enrollment,
                isActive = index % 11 != 10,
            )
        }
    }

    private fun seedAttendance(employees: List<Employee>): List<AttendanceRecord> = buildList {
        for (daysAgo in 0..13) {
            val date = AppClock.isoDate(daysAgo)
            employees.forEachIndexed { index, employee ->
                val bucket = (index + daysAgo) % 10
                val status = when {
                    bucket == 9 -> AttendanceStatus.ABSENT
                    bucket == 8 -> AttendanceStatus.ON_LEAVE
                    bucket == 7 -> AttendanceStatus.LATE
                    bucket == 6 && daysAgo % 3 == 0 -> AttendanceStatus.HALF_DAY
                    else -> AttendanceStatus.PRESENT
                }
                val lateMinutes = if (status == AttendanceStatus.LATE) 8 + (index * 3) % 27 else 0
                val checkedIn = status != AttendanceStatus.ABSENT && status != AttendanceStatus.ON_LEAVE
                val openToday = daysAgo == 0 && index % 4 == 0
                add(
                    AttendanceRecord(
                        id = "att-${employee.id}-$date",
                        employeeId = employee.id,
                        employeeName = employee.fullName,
                        employeeCode = employee.employeeCode,
                        department = employee.department,
                        date = date,
                        checkInTime = if (checkedIn) AppClock.timeLabel(9, (lateMinutes + index) % 60) else null,
                        checkOutTime = when {
                            !checkedIn || openToday -> null
                            status == AttendanceStatus.HALF_DAY -> AppClock.timeLabel(13, (index * 7) % 60)
                            else -> AppClock.timeLabel(18, (index * 7) % 60)
                        },
                        status = status,
                        lateMinutes = lateMinutes,
                        overtimeMinutes = if (bucket == 3) 45 else 0,
                        workedMinutes = when {
                            !checkedIn -> 0
                            status == AttendanceStatus.HALF_DAY -> 240
                            openToday -> 0
                            else -> 505 - lateMinutes
                        },
                    ),
                )
            }
        }
    }

    companion object {
        const val DEMO_ORGANIZATION_ID = "org-demo"

        /** Shortened from the server's four hours so check-out is demoable. */
        private const val DEMO_CHECKOUT_AFTER_MINUTES = 2L
    }
}

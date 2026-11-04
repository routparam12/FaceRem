package com.facerem.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class RoleTest {

    @Test
    fun `parses canonical role strings correctly`() {
        assertEquals(Role.ORGANIZATION_ADMIN, Role.fromWireValue("ORGANIZATION_ADMIN"))
        assertEquals(Role.HR_ADMIN, Role.fromWireValue("HR_ADMIN"))
        assertEquals(Role.MANAGER, Role.fromWireValue("MANAGER"))
        assertEquals(Role.SUPER_ADMIN, Role.fromWireValue("SUPER_ADMIN"))
        assertEquals(Role.ATTENDANCE_DEVICE, Role.fromWireValue("ATTENDANCE_DEVICE"))
        assertEquals(Role.EMPLOYEE, Role.fromWireValue("EMPLOYEE"))
    }

    @Test
    fun `parses legacy ORG_ADMIN alias as ORGANIZATION_ADMIN`() {
        assertEquals(Role.ORGANIZATION_ADMIN, Role.fromWireValue("ORG_ADMIN"))
        assertEquals(Role.ORGANIZATION_ADMIN, Role.fromWireValue("org_admin"))
    }

    @Test
    fun `is case insensitive for all roles`() {
        assertEquals(Role.ORGANIZATION_ADMIN, Role.fromWireValue("organization_admin"))
        assertEquals(Role.HR_ADMIN, Role.fromWireValue("hr_admin"))
        assertEquals(Role.MANAGER, Role.fromWireValue("manager"))
    }

    @Test
    fun `unknown or null roles fall back safely to EMPLOYEE without crashing`() {
        assertEquals(Role.EMPLOYEE, Role.fromWireValue(null))
        assertEquals(Role.EMPLOYEE, Role.fromWireValue(""))
        assertEquals(Role.EMPLOYEE, Role.fromWireValue("   "))
        assertEquals(Role.EMPLOYEE, Role.fromWireValue("UNKNOWN_ROLE"))
        assertEquals(Role.EMPLOYEE, Role.fromWireValue("GUEST_OPERATOR"))
    }

    @Test
    fun `permissions match role hierarchies`() {
        assert(Role.ORGANIZATION_ADMIN.canManageEmployees)
        assert(Role.ORGANIZATION_ADMIN.canEnrollFaces)
        assert(Role.ORGANIZATION_ADMIN.canViewReports)

        assert(Role.HR_ADMIN.canManageEmployees)
        assert(Role.HR_ADMIN.canEnrollFaces)

        assert(Role.MANAGER.canManageEmployees)
        assert(!Role.MANAGER.canEnrollFaces)

        assert(!Role.EMPLOYEE.canManageEmployees)
        assert(!Role.EMPLOYEE.canEnrollFaces)
    }
}


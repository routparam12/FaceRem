package com.facerem.core.model

/**
 * Roles are defined by the server; the client only uses them to shape navigation.
 * Organization-facing navigation must never expose [SUPER_ADMIN] functionality.
 */
enum class Role(val displayName: String) {
    SUPER_ADMIN("Super admin"),
    ORGANIZATION_ADMIN("Organization admin"),
    HR_ADMIN("HR admin"),
    MANAGER("Manager"),
    EMPLOYEE("Employee"),
    ATTENDANCE_DEVICE("Attendance device"),
    ;

    val canManageEmployees: Boolean
        get() = this == ORGANIZATION_ADMIN || this == HR_ADMIN || this == MANAGER

    val canViewReports: Boolean
        get() = this == ORGANIZATION_ADMIN || this == HR_ADMIN || this == MANAGER

    val canEnrollFaces: Boolean
        get() = this == ORGANIZATION_ADMIN || this == HR_ADMIN

    companion object {
        fun fromWireValue(value: String?): Role {
            if (value.isNullOrBlank()) return EMPLOYEE
            if (value.equals("ORG_ADMIN", ignoreCase = true)) return ORGANIZATION_ADMIN
            return entries.firstOrNull { it.name.equals(value, ignoreCase = true) } ?: EMPLOYEE
        }
    }
}

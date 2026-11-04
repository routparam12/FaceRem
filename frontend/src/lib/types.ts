export type Role =
  | "SUPER_ADMIN"
  | "ORG_ADMIN"
  | "ORGANIZATION_ADMIN"
  | "HR_ADMIN"
  | "MANAGER"
  | "EMPLOYEE"
  | "ATTENDANCE_DEVICE";

export type AttendanceStatus = "PRESENT" | "LATE" | "ABSENT" | "ON_LEAVE";

export interface Me {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  organization_id: string | null;
  organization_name: string | null;
  employee_id: string | null;
}

export interface Employee {
  id: string;
  employee_code: string;
  full_name: string;
  email: string;
  department: string;
  job_title: string;
  is_active: boolean;
  face_enrolled: boolean;
}

export interface AttendanceRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  date: string;
  check_in_at: string | null;
  check_out_at: string | null;
  status: AttendanceStatus;
  late_minutes: number;
}

export interface Dashboard {
  organization_name: string;
  date: string;
  total_employees: number;
  present: number;
  late: number;
  not_checked_in: number;
  pending_enrollments: number;
}

/** ALREADY_PRESENT means the day was already recorded and the scan changed nothing. */
export type RecognitionEvent = "CHECK_IN" | "CHECK_OUT" | "ALREADY_PRESENT";

export interface RecognitionResult {
  employee_id: string;
  employee_code: string;
  full_name: string;
  department: string;
  event: RecognitionEvent;
  recorded_at: string;
  status: AttendanceStatus;
  late_minutes: number;
  match_confidence: number;
  liveness_score: number;
  check_in_at: string | null;
  check_out_at: string | null;
}

export const EVENT_LABELS: Record<RecognitionEvent, string> = {
  CHECK_IN: "Checked in",
  CHECK_OUT: "Checked out",
  ALREADY_PRESENT: "Already present",
};

export interface AuditEntry {
  id: string;
  action: string;
  actor_user_id: string | null;
  target_type: string;
  target_id: string;
  meta: Record<string, unknown>;
  created_at: string;
}

/** Roles that may manage people and enroll faces, mirroring the server's STAFF_ROLES. */
export const STAFF_ROLES: Role[] = ["ORG_ADMIN", "ORGANIZATION_ADMIN", "HR_ADMIN"];

export function canManagePeople(role: Role): boolean {
  return STAFF_ROLES.includes(role);
}

export function canRunScans(role: Role): boolean {
  return role === "ORG_ADMIN" || role === "ORGANIZATION_ADMIN" || role === "HR_ADMIN" || role === "ATTENDANCE_DEVICE";
}

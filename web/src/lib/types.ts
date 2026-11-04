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
  has_pin?: boolean;
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

export interface AttentionItem {
  category: "PROVISIONAL_EVENT" | "OFFLINE_KIOSK" | "UNENROLLED_EMPLOYEE" | string;
  title: string;
  description: string;
  target_id: string;
  action_url: string;
}

export interface Dashboard {
  organization_name: string;
  date: string;
  total_employees: number;
  present: number;
  late: number;
  not_checked_in: number;
  pending_enrollments: number;
  provisional_events_count?: number;
  offline_devices_count?: number;
  attention_items?: AttentionItem[];
}

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
  undo_token?: string | null;
  event_id?: string | null;
  provisional?: boolean;
}

export const EVENT_LABELS: Record<RecognitionEvent, string> = {
  CHECK_IN: "Checked in",
  CHECK_OUT: "Checked out",
  ALREADY_PRESENT: "Already present",
};

export interface AttendanceEventItem {
  id: string;
  organization_id?: string;
  employee_id: string;
  employee_name?: string | null;
  device_id: string;
  camera_id?: string | null;
  source_type: string;
  type: "CHECK_IN" | "CHECK_OUT" | string;
  occurred_at: string;
  confidence?: number;
  method: "FACE" | "PIN" | string;
  idempotency_key?: string | null;
  provisional: boolean;
  voided_at?: string | null;
  void_reason?: string | null;
}

export interface Device {
  id: string;
  organization_id: string;
  name: string;
  branch_id: string | null;
  mode: "AUTO" | "IN_ONLY" | "OUT_ONLY";
  status: "ACTIVE" | "REVOKED";
  registered_by: string;
  last_seen_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface Camera {
  id: string;
  organization_id: string;
  source_type: "ANDROID_KIOSK" | "EDGE_AGENT";
  device_id: string;
  name: string;
  branch_id: string | null;
  direction: "IN_ONLY" | "OUT_ONLY" | "AUTO";
  assurance: "HIGH" | "STANDARD";
  enabled: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface OrganizationSettings {
  id: string;
  name: string;
  slug: string;
  plan: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  actor_user_id: string | null;
  target_type: string;
  target_id: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export const STAFF_ROLES: Role[] = ["ORG_ADMIN", "ORGANIZATION_ADMIN", "HR_ADMIN"];

export function canManagePeople(role: Role): boolean {
  return STAFF_ROLES.includes(role);
}

export function canRunScans(role: Role): boolean {
  return role === "ORG_ADMIN" || role === "ORGANIZATION_ADMIN" || role === "HR_ADMIN" || role === "ATTENDANCE_DEVICE";
}

export function isOrgAdmin(role: Role): boolean {
  return role === "ORG_ADMIN" || role === "ORGANIZATION_ADMIN" || role === "SUPER_ADMIN";
}

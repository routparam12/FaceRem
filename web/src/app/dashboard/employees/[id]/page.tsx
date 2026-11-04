import Link from "next/link";

import EmployeeActions from "@/components/employee-actions";
import EnrollPanel from "@/components/enroll-panel";
import {
  Avatar,
  Card,
  EmptyState,
  EnrollmentPill,
  SectionTitle,
  StatusPill,
  formatDate,
  formatTime,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { AttendanceRecord, Employee, Me } from "@/lib/types";
import { canManagePeople } from "@/lib/types";

export default async function EmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [me, employee, attendance] = await Promise.all([
    apiGet<Me>("/api/v1/auth/me"),
    apiGet<Employee>(`/api/v1/employees/${id}`),
    apiGet<AttendanceRecord[]>("/api/v1/attendance"),
  ]);

  const history = attendance.filter((record) => record.employee_id === id).slice(0, 14);

  return (
    <div className="space-y-8">
      <Link
        href="/dashboard/employees"
        className="text-sm font-medium text-ink-500 hover:text-ink-800"
      >
        ← Back to people
      </Link>

      <div className="flex flex-wrap items-center gap-4">
        <Avatar name={employee.full_name} className="size-16 text-lg" />
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">{employee.full_name}</h1>
          <p className="mt-0.5 text-sm text-ink-500">
            {employee.job_title || "No job title"} · {employee.department}
          </p>
          <div className="mt-2 flex items-center gap-2">
            <EnrollmentPill enrolled={employee.face_enrolled} />
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                employee.is_active
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-rose-50 text-rose-700"
              }`}
            >
              {employee.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <SectionTitle>Details</SectionTitle>
          <dl className="divide-y divide-ink-200 text-sm">
            {[
              ["Employee code", employee.employee_code],
              ["Email", employee.email],
              ["Department", employee.department],
              ["Status", employee.is_active ? "Active" : "Inactive"],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-500">{label}</dt>
                <dd className="text-right font-medium text-ink-900">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        {canManagePeople(me.role) ? (
          <EnrollPanel employeeId={employee.id} enrolled={employee.face_enrolled} />
        ) : (
          <Card className="p-6">
            <SectionTitle>Face profile</SectionTitle>
            <p className="text-sm text-ink-600">
              Only an organization or HR admin can enroll or remove a face profile.
            </p>
          </Card>
        )}
      </div>

      {canManagePeople(me.role) && (
        <EmployeeActions employeeId={employee.id} isActive={employee.is_active} />
      )}

      <section>
        <SectionTitle>Recent attendance</SectionTitle>
        <Card>
          {history.length === 0 ? (
            <EmptyState
              title="No attendance yet"
              body="Records appear once this person is recognized by the scanner."
            />
          ) : (
            <ul className="divide-y divide-ink-200">
              {history.map((record) => (
                <li key={record.id} className="flex items-center gap-3 px-5 py-3">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-ink-900">{formatDate(record.date)}</p>
                    <p className="text-xs text-ink-500">
                      in {formatTime(record.check_in_at)} · out {formatTime(record.check_out_at)}
                    </p>
                  </div>
                  <StatusPill status={record.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  );
}

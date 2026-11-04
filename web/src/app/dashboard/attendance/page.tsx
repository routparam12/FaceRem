import AttendanceEventList from "@/components/attendance-event-list";
import { Avatar, Card, EmptyState, StatusPill, formatDate, formatTime } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { AttendanceEventItem, AttendanceRecord, Me } from "@/lib/types";
import { canManagePeople } from "@/lib/types";

export default async function AttendancePage() {
  const [me, records, events] = await Promise.all([
    apiGet<Me>("/api/v1/auth/me"),
    apiGet<AttendanceRecord[]>("/api/v1/attendance"),
    apiGet<AttendanceEventItem[]>("/api/v1/attendance/events?limit=100"),
  ]);

  const byDate = records.reduce<Record<string, AttendanceRecord[]>>((groups, record) => {
    (groups[record.date] ??= []).push(record);
    return groups;
  }, {});
  const dates = Object.keys(byDate).sort().reverse();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Attendance Center</h1>
        <p className="mt-1 text-sm text-ink-500">
          Real-time event stream from registered kiosks and daily verified check-in summaries.
        </p>
      </div>

      {/* Section 1: Raw Attendance Event Stream (Audit & Moderation) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-ink-900">Live Attendance Event Stream</h2>
            <p className="text-xs text-ink-500">
              Immutable biometric and PIN scans captured across all active cameras.
            </p>
          </div>
        </div>

        <AttendanceEventList events={events} canManage={canManagePeople(me.role)} />
      </section>

      {/* Section 2: Daily Employee Rollup Summaries */}
      <section className="space-y-3 pt-6 border-t border-ink-200">
        <div>
          <h2 className="text-base font-bold text-ink-900">Daily Attendance Summaries</h2>
          <p className="text-xs text-ink-500">
            Calculated daily records reflecting check-in, check-out, and lateness penalties.
          </p>
        </div>

        {dates.length === 0 ? (
          <Card>
            <EmptyState
              title="Nothing recorded yet"
              body="Attendance summaries appear here once employees complete their check-ins."
            />
          </Card>
        ) : (
          <div className="space-y-6">
            {dates.map((date) => (
              <section key={date}>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-ink-500">
                  {formatDate(date)}
                </h3>
                <Card>
                  <ul className="divide-y divide-ink-200">
                    {byDate[date].map((record) => (
                      <li key={record.id} className="flex items-center gap-3 px-5 py-3.5">
                        <Avatar name={record.employee_name} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-ink-900">
                            {record.employee_name}
                          </p>
                          <p className="truncate text-xs text-ink-500">
                            in {formatTime(record.check_in_at)} · out {formatTime(record.check_out_at)}
                            {record.late_minutes > 0 && ` · ${record.late_minutes}m late`}
                          </p>
                        </div>
                        <StatusPill status={record.status} />
                      </li>
                    ))}
                  </ul>
                </Card>
              </section>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

import Link from "next/link";

import {
  Avatar,
  Banner,
  ButtonLink,
  Card,
  EmptyState,
  SectionTitle,
  StatCard,
  StatusPill,
  formatTime,
} from "@/components/ui";
import { ApiError, apiGet } from "@/lib/api";
import type { AttendanceRecord, Dashboard, Me } from "@/lib/types";
import { canRunScans } from "@/lib/types";

export default async function OverviewPage() {
  const me = await apiGet<Me>("/api/v1/auth/me");

  let summary: Dashboard | null = null;
  try {
    summary = await apiGet<Dashboard>("/api/v1/dashboard");
  } catch (error) {
    if (!(error instanceof ApiError) || error.code !== "FORBIDDEN") throw error;
  }

  const today = new Date().toISOString().slice(0, 10);
  const records = await apiGet<AttendanceRecord[]>(`/api/v1/attendance?on=${today}`);

  const attentionItems = summary?.attention_items ?? [];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">
            {summary?.organization_name ?? me.organization_name ?? "Your workspace"}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            {new Date().toLocaleDateString([], {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>
        {canRunScans(me.role) && <ButtonLink href="/dashboard/scan">Open scanner</ButtonLink>}
      </div>

      {summary ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Present today"
            value={summary.present}
            caption={`of ${summary.total_employees} employees`}
            tone="success"
          />
          <StatCard label="Late arrivals" value={summary.late} tone="warning" />
          <StatCard label="Not checked in" value={summary.not_checked_in} tone="danger" />
          <StatCard
            label="Awaiting enrollment"
            value={summary.pending_enrollments}
            caption="face profile missing"
          />
        </div>
      ) : (
        <Banner tone="info">
          Your role can see your own attendance, but not organization-wide totals.
        </Banner>
      )}

      {/* Attention List: Provisional Events, Offline Kiosks, Unenrolled Staff */}
      {attentionItems.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-amber-900 flex items-center gap-2">
              <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
              Needs Attention ({attentionItems.length})
            </h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {attentionItems.map((item, idx) => (
              <Card key={idx} className="p-4 border-l-4 border-l-amber-500 bg-amber-50/30">
                <div className="flex flex-col justify-between h-full space-y-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-100 px-2 py-0.5 rounded">
                      {item.category.replace(/_/g, " ")}
                    </span>
                    <h3 className="mt-2 text-sm font-semibold text-ink-900 line-clamp-1">
                      {item.title}
                    </h3>
                    <p className="mt-1 text-xs text-ink-600 line-clamp-2">
                      {item.description}
                    </p>
                  </div>
                  <div className="pt-2">
                    <Link
                      href={item.action_url}
                      className="text-xs font-semibold text-brand-700 hover:text-brand-900 inline-flex items-center gap-1"
                    >
                      Resolve issue →
                    </Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Today's Activity */}
      <section>
        <SectionTitle
          action={
            <Link
              href="/dashboard/attendance"
              className="text-sm font-medium text-brand-700 hover:text-brand-800"
            >
              See all
            </Link>
          }
        >
          Today&apos;s activity
        </SectionTitle>

        <Card>
          {records.length === 0 ? (
            <EmptyState
              title="No check-ins yet today"
              body="Records appear here as soon as someone is recognized by the scanner."
            />
          ) : (
            <ul className="divide-y divide-ink-200">
              {records.map((record) => (
                <li key={record.id} className="flex items-center gap-3 px-5 py-3.5">
                  <Avatar name={record.employee_name} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {record.employee_name}
                    </p>
                    <p className="text-xs text-ink-500">
                      Check in: {record.check_in_at ? formatTime(record.check_in_at) : "—"}
                      {record.check_out_at && ` · Check out: ${formatTime(record.check_out_at)}`}
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

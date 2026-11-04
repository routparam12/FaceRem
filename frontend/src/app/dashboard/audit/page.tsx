import { redirect } from "next/navigation";

import { Card, EmptyState, Pill } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { AuditEntry, Me } from "@/lib/types";

function tone(action: string): string {
  if (action.includes("not_recognized") || action.includes("failed")) {
    return "bg-danger-bg text-danger-fg";
  }
  if (action.startsWith("face.")) return "bg-info-bg text-info-fg";
  if (action.startsWith("attendance.")) return "bg-success-bg text-success-fg";
  return "bg-ink-100 text-ink-700";
}

export default async function AuditPage() {
  const me = await apiGet<Me>("/api/v1/auth/me");
  if (me.role !== "ORG_ADMIN" && me.role !== "ORGANIZATION_ADMIN") redirect("/dashboard");

  const entries = await apiGet<AuditEntry[]>("/api/v1/audit-logs?limit=100");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Audit log</h1>
        <p className="mt-1 text-sm text-ink-500">
          Every biometric and authentication action, scoped to your organization. Passwords, tokens
          and embeddings are never recorded here.
        </p>
      </div>

      <Card>
        {entries.length === 0 ? (
          <EmptyState title="No entries" body="Actions appear here as people use the system." />
        ) : (
          <ul className="divide-y divide-ink-200">
            {entries.map((entry) => (
              <li key={entry.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <Pill tone={tone(entry.action)}>{entry.action}</Pill>
                <span className="text-xs text-ink-500">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
                {entry.target_id && (
                  <span className="text-xs text-ink-400">
                    {entry.target_type}:{entry.target_id.slice(0, 8)}
                  </span>
                )}
                {Object.keys(entry.meta ?? {}).length > 0 && (
                  <code className="ml-auto truncate text-xs text-ink-500">
                    {JSON.stringify(entry.meta)}
                  </code>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

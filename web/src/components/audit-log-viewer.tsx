"use client";

import { useState } from "react";

import { Card, EmptyState, Pill } from "@/components/ui";
import type { AuditEntry } from "@/lib/types";

function tone(action: string): string {
  if (action.includes("failed") || action.includes("revoked") || action.includes("deleted")) {
    return "bg-rose-100 text-rose-800";
  }
  if (action.startsWith("face.")) return "bg-blue-100 text-blue-800";
  if (action.startsWith("attendance.")) return "bg-emerald-100 text-emerald-800";
  if (action.startsWith("device.") || action.startsWith("camera.")) return "bg-purple-100 text-purple-800";
  return "bg-ink-100 text-ink-700";
}

export default function AuditLogViewer({ entries }: { entries: AuditEntry[] }) {
  const [filterCategory, setFilterCategory] = useState("ALL");
  const [search, setSearch] = useState("");
  const [selectedMeta, setSelectedMeta] = useState<Record<string, unknown> | null>(null);

  const filtered = entries.filter((entry) => {
    if (filterCategory === "AUTH" && !entry.action.startsWith("auth.")) return false;
    if (filterCategory === "DEVICE" && !entry.action.startsWith("device.") && !entry.action.startsWith("camera.")) return false;
    if (filterCategory === "BIOMETRIC" && !entry.action.startsWith("face.")) return false;
    if (filterCategory === "ATTENDANCE" && !entry.action.startsWith("attendance.")) return false;

    if (search.trim()) {
      const q = search.toLowerCase();
      const act = entry.action.toLowerCase();
      const tgt = (entry.target_id || "").toLowerCase();
      if (!act.includes(q) && !tgt.includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-200 bg-white p-3 shadow-xs">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search action or target ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-ink-200 px-3 py-1.5 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-hidden"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-ink-500">Category:</label>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-700"
          >
            <option value="ALL">All Events</option>
            <option value="AUTH">Authentication & 2FA</option>
            <option value="DEVICE">Devices & Cameras</option>
            <option value="BIOMETRIC">Biometric / Face</option>
            <option value="ATTENDANCE">Attendance Events</option>
          </select>
        </div>
      </div>

      <Card className="overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            title="No audit entries match filter"
            body="Security audit logs track all tenant configuration and authentication events."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-ink-200 bg-ink-50 text-ink-500 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Target</th>
                  <th className="py-3 px-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {filtered.map((entry) => {
                  const metaCount = Object.keys(entry.meta ?? {}).length;
                  return (
                    <tr key={entry.id} className="hover:bg-ink-50/60">
                      <td className="py-3 px-4 font-mono text-ink-600 whitespace-nowrap">
                        {new Date(entry.created_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <Pill tone={tone(entry.action)}>{entry.action}</Pill>
                      </td>

                      <td className="py-3 px-4 font-mono text-ink-500 whitespace-nowrap">
                        {entry.actor_user_id ? `usr:${entry.actor_user_id.slice(0, 8)}` : "system"}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap font-mono text-ink-600">
                        {entry.target_type ? `${entry.target_type}:${(entry.target_id || "").slice(0, 8)}` : "—"}
                      </td>

                      <td className="py-3 px-4">
                        {metaCount > 0 ? (
                          <button
                            type="button"
                            onClick={() => setSelectedMeta(entry.meta)}
                            className="font-mono text-[11px] text-brand-700 hover:underline max-w-[200px] truncate block"
                          >
                            {JSON.stringify(entry.meta)}
                          </button>
                        ) : (
                          <span className="text-ink-400">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Meta JSON View Modal */}
      {selectedMeta && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-ink-900">Audit Event Metadata</h3>
            <pre className="rounded-xl bg-ink-900 p-4 font-mono text-xs text-white overflow-x-auto max-h-80">
              {JSON.stringify(selectedMeta, null, 2)}
            </pre>
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedMeta(null)}
                className="rounded-lg bg-ink-100 px-4 py-2 text-xs font-semibold text-ink-900 hover:bg-ink-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


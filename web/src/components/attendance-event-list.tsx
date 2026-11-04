"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Banner, Button, Card, EmptyState, Field } from "@/components/ui";
import type { AttendanceEventItem } from "@/lib/types";

export default function AttendanceEventList({
  events: initialEvents,
  canManage,
}: {
  events: AttendanceEventItem[];
  canManage: boolean;
}) {
  const router = useRouter();
  const [events, setEvents] = useState(initialEvents);
  const [filterType, setFilterType] = useState<string>("ALL");
  const [filterMethod, setFilterMethod] = useState<string>("ALL");
  const [filterProvisionalOnly, setFilterProvisionalOnly] = useState(false);
  const [search, setSearch] = useState("");

  // Void Modal State
  const [voidingEventId, setVoidingEventId] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [voidPending, setVoidPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Confirm State
  const [confirmPendingId, setConfirmPendingId] = useState<string | null>(null);

  const filteredEvents = events.filter((ev) => {
    if (filterType !== "ALL" && ev.type !== filterType) return false;
    if (filterMethod !== "ALL" && ev.method !== filterMethod) return false;
    if (filterProvisionalOnly && !ev.provisional) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      const name = (ev.employee_name || "").toLowerCase();
      const id = ev.employee_id.toLowerCase();
      if (!name.includes(q) && !id.includes(q)) return false;
    }
    return true;
  });

  async function handleConfirm(eventId: string) {
    setConfirmPendingId(eventId);
    setActionError(null);
    try {
      const res = await fetch(`/api/proxy/api/v1/attendance/events/${eventId}/confirm`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to confirm provisional event.");
      }
      setEvents((prev) =>
        prev.map((e) => (e.id === eventId ? { ...e, provisional: false } : e)),
      );
      router.refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error confirming event.");
    } finally {
      setConfirmPendingId(null);
    }
  }

  async function handleVoid(event: React.FormEvent) {
    event.preventDefault();
    if (!voidingEventId || voidReason.trim().length < 3) return;
    setVoidPending(true);
    setActionError(null);

    try {
      const res = await fetch(`/api/proxy/api/v1/attendance/events/${voidingEventId}/void`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: voidReason.trim() }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to void attendance event.");
      }
      setEvents((prev) =>
        prev.map((e) =>
          e.id === voidingEventId
            ? { ...e, voided_at: new Date().toISOString(), void_reason: voidReason.trim() }
            : e,
        ),
      );
      setVoidingEventId(null);
      setVoidReason("");
      router.refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error voiding event.");
    } finally {
      setVoidPending(false);
    }
  }

  return (
    <div className="space-y-4">
      {actionError && <Banner tone="danger">{actionError}</Banner>}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-200 bg-white p-3 shadow-xs">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search employee name or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-ink-200 px-3 py-1.5 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-hidden"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-ink-500">Direction:</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-700"
          >
            <option value="ALL">All Directions</option>
            <option value="CHECK_IN">Check In</option>
            <option value="CHECK_OUT">Check Out</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-ink-500">Method:</label>
          <select
            value={filterMethod}
            onChange={(e) => setFilterMethod(e.target.value)}
            className="rounded-lg border border-ink-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-700"
          >
            <option value="ALL">All Methods</option>
            <option value="FACE">Face Scan</option>
            <option value="PIN">Code + PIN</option>
          </select>
        </div>

        <label className="flex items-center gap-1.5 cursor-pointer text-xs font-medium text-ink-700 select-none">
          <input
            type="checkbox"
            checked={filterProvisionalOnly}
            onChange={(e) => setFilterProvisionalOnly(e.target.checked)}
            className="rounded border-ink-300 text-brand-600 focus:ring-brand-500 size-3.5"
          />
          Provisional Only
        </label>
      </div>

      {/* Events Table */}
      <Card className="overflow-hidden">
        {filteredEvents.length === 0 ? (
          <EmptyState
            title="No matching attendance events"
            body="Events appear in real-time as employees scan at registered kiosk cameras."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-ink-200 bg-ink-50 text-ink-500 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Time</th>
                  <th className="py-3 px-4">Employee</th>
                  <th className="py-3 px-4">Direction</th>
                  <th className="py-3 px-4">Method</th>
                  <th className="py-3 px-4">Source / Camera</th>
                  <th className="py-3 px-4">Status</th>
                  {canManage && <th className="py-3 px-4 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {filteredEvents.map((ev) => {
                  const isVoided = !!ev.voided_at;
                  const isProvisional = ev.provisional && !isVoided;
                  const timeStr = new Date(ev.occurred_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  });
                  const dateStr = new Date(ev.occurred_at).toLocaleDateString([], {
                    month: "short",
                    day: "numeric",
                  });

                  return (
                    <tr
                      key={ev.id}
                      className={
                        isVoided
                          ? "bg-rose-50/40 opacity-70"
                          : isProvisional
                            ? "bg-amber-50/40"
                            : "hover:bg-ink-50/60"
                      }
                    >
                      <td className="py-3 px-4 font-mono text-ink-600 whitespace-nowrap">
                        <span className="font-semibold text-ink-900">{timeStr}</span>
                        <span className="block text-[11px] text-ink-400">{dateStr}</span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <p className="font-semibold text-ink-900">
                          {ev.employee_name || "Unknown Staff"}
                        </p>
                        <p className="text-[11px] font-mono text-ink-400 truncate max-w-[140px]">
                          {ev.employee_id}
                        </p>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 font-bold uppercase tracking-wide text-[10px] ${
                            ev.type === "CHECK_IN"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-blue-100 text-blue-800"
                          }`}
                        >
                          {ev.type === "CHECK_IN" ? "Check In" : "Check Out"}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 font-medium text-ink-700">
                          {ev.method === "FACE" ? "👤 Face Scan" : "🔢 PIN Fallback"}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap text-ink-600 font-mono text-[11px]">
                        {ev.camera_id ? `cam:${ev.camera_id.slice(0, 8)}` : `dev:${ev.device_id.slice(0, 8)}`}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        {isVoided ? (
                          <span
                            className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-800"
                            title={`Reason: ${ev.void_reason || "Voided by admin"}`}
                          >
                            VOIDED
                          </span>
                        ) : isProvisional ? (
                          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800 animate-pulse">
                            PROVISIONAL
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                            VERIFIED
                          </span>
                        )}
                        {ev.void_reason && (
                          <p className="text-[10px] text-rose-700 line-clamp-1 max-w-[120px] mt-0.5">
                            {ev.void_reason}
                          </p>
                        )}
                      </td>

                      {canManage && (
                        <td className="py-3 px-4 text-right whitespace-nowrap space-x-1">
                          {isProvisional && (
                            <button
                              type="button"
                              onClick={() => handleConfirm(ev.id)}
                              disabled={confirmPendingId === ev.id}
                              className="rounded bg-emerald-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-emerald-700"
                            >
                              {confirmPendingId === ev.id ? "…" : "Confirm"}
                            </button>
                          )}
                          {!isVoided && (
                            <button
                              type="button"
                              onClick={() => {
                                setVoidingEventId(ev.id);
                                setVoidReason("");
                              }}
                              className="rounded border border-rose-300 px-2 py-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-50"
                            >
                              Void
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Mandatory Reason Void Modal */}
      {voidingEventId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-ink-900">Void Attendance Event</h3>
            <p className="mt-1 text-xs text-ink-500">
              Voiding retracts this attendance scan from daily summaries while preserving the event
              record for security audits. A mandatory audit explanation is required.
            </p>

            <form onSubmit={handleVoid} className="mt-4 space-y-4">
              <Field
                label="Mandatory Reason for Voiding"
                required
                autoFocus
                placeholder="e.g. Accidental scan during gate maintenance"
                value={voidReason}
                onChange={(e) => setVoidReason(e.target.value)}
              />

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setVoidingEventId(null)}
                  disabled={voidPending}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="danger"
                  disabled={voidPending || voidReason.trim().length < 3}
                >
                  {voidPending ? "Voiding…" : "Confirm Void"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


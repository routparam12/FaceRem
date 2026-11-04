"use client";

import { useEffect, useState } from "react";

import { Banner, Button, Card, EmptyState, Field } from "@/components/ui";
import type { Device } from "@/lib/types";

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Enrollment Code State
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [enrollmentCode, setEnrollmentCode] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<Date | null>(null);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(600);
  const [codePending, setCodePending] = useState(false);

  // Edit Device State
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [editName, setEditName] = useState("");
  const [editMode, setEditMode] = useState<"AUTO" | "IN_ONLY" | "OUT_ONLY">("AUTO");
  const [editPending, setEditPending] = useState(false);

  // Revoke Device State
  const [revokingDevice, setRevokingDevice] = useState<Device | null>(null);
  const [revokePending, setRevokePending] = useState(false);

  async function loadDevices() {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/api/v1/devices");
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to load devices");
      }
      setDevices(data.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error fetching devices");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDevices();
  }, []);

  // Countdown timer for enrollment code
  useEffect(() => {
    if (!expiresAt) return;
    const interval = setInterval(() => {
      const diff = Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000));
      setSecondsRemaining(diff);
      if (diff <= 0) {
        clearInterval(interval);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  async function handleGenerateCode() {
    setCodePending(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/api/v1/devices/enrollment-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to generate code.");
      }
      setEnrollmentCode(data.data.code);
      const exp = new Date(data.data.expires_at);
      setExpiresAt(exp);
      setSecondsRemaining(Math.max(0, Math.floor((exp.getTime() - Date.now()) / 1000)));
      setShowCodeModal(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not issue enrollment code.");
    } finally {
      setCodePending(false);
    }
  }

  async function handleUpdateDevice(e: React.FormEvent) {
    e.preventDefault();
    if (!editingDevice || !editName.trim()) return;
    setEditPending(true);
    try {
      const res = await fetch(`/api/proxy/api/v1/devices/${editingDevice.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editName.trim(), mode: editMode }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to update device");
      }
      setEditingDevice(null);
      loadDevices();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error updating device");
    } finally {
      setEditPending(false);
    }
  }

  async function handleRevokeDevice() {
    if (!revokingDevice) return;
    setRevokePending(true);
    try {
      const res = await fetch(`/api/proxy/api/v1/devices/${revokingDevice.id}/revoke`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to revoke device");
      }
      setRevokingDevice(null);
      loadDevices();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error revoking device");
    } finally {
      setRevokePending(false);
    }
  }

  function formatCountdown(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">Kiosk Devices</h1>
          <p className="mt-1 text-sm text-ink-500">
            Registered Android kiosks and entrance tablets authorized to record attendance.
          </p>
        </div>
        <Button onClick={handleGenerateCode} disabled={codePending}>
          {codePending ? "Generating…" : "+ Register New Kiosk"}
        </Button>
      </div>

      {error && <Banner tone="danger">{error}</Banner>}

      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-ink-500">Loading registered kiosks…</div>
        ) : devices.length === 0 ? (
          <EmptyState
            title="No kiosk devices registered"
            body="Click '+ Register New Kiosk' to generate an enrollment code for your tablet."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-ink-200 bg-ink-50 text-ink-500 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Device Name</th>
                  <th className="py-3 px-4">Mode</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Last Seen</th>
                  <th className="py-3 px-4">Registered</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {devices.map((device) => {
                  const isRevoked = device.status === "REVOKED";
                  const lastSeen = device.last_seen_at
                    ? new Date(device.last_seen_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "Never";

                  return (
                    <tr
                      key={device.id}
                      className={isRevoked ? "bg-ink-50/50 opacity-60" : "hover:bg-ink-50/60"}
                    >
                      <td className="py-3 px-4 whitespace-nowrap">
                        <p className="font-semibold text-ink-900">{device.name}</p>
                        <p className="text-[11px] font-mono text-ink-400">{device.id}</p>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap font-medium text-ink-700">
                        <span className="rounded bg-ink-100 px-2 py-0.5 text-[10px] font-semibold text-ink-800">
                          {device.mode}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            isRevoked
                              ? "bg-rose-100 text-rose-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {device.status}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap text-ink-600 font-mono text-[11px]">
                        {lastSeen}
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap text-ink-500">
                        {new Date(device.created_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </td>

                      <td className="py-3 px-4 text-right whitespace-nowrap space-x-1">
                        {!isRevoked && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingDevice(device);
                                setEditName(device.name);
                                setEditMode(device.mode);
                              }}
                              className="rounded border border-ink-200 px-2 py-1 text-[11px] font-medium text-ink-700 hover:bg-ink-50"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => setRevokingDevice(device)}
                              className="rounded border border-rose-200 px-2 py-1 text-[11px] font-medium text-rose-700 hover:bg-rose-50"
                            >
                              Revoke
                            </button>
                          </>
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

      {/* 10-Minute Enrollment Code Modal */}
      {showCodeModal && enrollmentCode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl space-y-5 text-center">
            <span className="grid size-12 place-items-center rounded-full bg-brand-50 text-2xl mx-auto">
              📱
            </span>

            <div>
              <h3 className="text-xl font-bold text-ink-900">Device Enrollment Code</h3>
              <p className="mt-1 text-xs text-ink-500">
                Launch the FaceRem app on the kiosk tablet and enter this code to bind the device.
              </p>
            </div>

            <div className="rounded-2xl border-2 border-brand-500 bg-brand-50/40 p-6">
              <span className="block font-mono text-4xl font-extrabold tracking-widest text-brand-900">
                {enrollmentCode}
              </span>
              <p className="mt-2 text-xs font-semibold text-brand-700">
                Expires in:{" "}
                <span className={secondsRemaining < 60 ? "text-rose-600 animate-pulse" : ""}>
                  {formatCountdown(secondsRemaining)}
                </span>
              </p>
            </div>

            <div className="rounded-lg bg-ink-50 p-3 text-left text-xs text-ink-600 space-y-1">
              <p className="font-semibold text-ink-900">Security Note:</p>
              <p>• Code is single-use and invalid after 10 minutes.</p>
              <p>• Upon verification, the tablet receives a dedicated cryptographic device token.</p>
            </div>

            <Button onClick={() => setShowCodeModal(false)} className="w-full">
              Done
            </Button>
          </div>
        </div>
      )}

      {/* Edit Device Modal */}
      {editingDevice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-ink-900">Edit Kiosk Device</h3>
            <form onSubmit={handleUpdateDevice} className="mt-4 space-y-4">
              <Field
                label="Device Name"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />

              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">
                  Operating Direction Mode
                </label>
                <select
                  value={editMode}
                  onChange={(e) => setEditMode(e.target.value as "AUTO" | "IN_ONLY" | "OUT_ONLY")}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                >
                  <option value="AUTO">AUTO (Bi-directional toggle)</option>
                  <option value="IN_ONLY">IN_ONLY (Entrance only)</option>
                  <option value="OUT_ONLY">OUT_ONLY (Exit only)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setEditingDevice(null)}
                  disabled={editPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={editPending || !editName.trim()}>
                  {editPending ? "Saving…" : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Revoke Confirmation Modal */}
      {revokingDevice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-rose-900">Revoke Kiosk Device?</h3>
            <p className="text-xs text-ink-600">
              Are you sure you want to revoke <strong>{revokingDevice.name}</strong>? Its API token
              will be permanently invalidated, preventing any further attendance scans from this
              device.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setRevokingDevice(null)}
                disabled={revokePending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleRevokeDevice}
                disabled={revokePending}
              >
                {revokePending ? "Revoking…" : "Revoke Device"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


"use client";

import { useEffect, useState } from "react";

import { Banner, Button, Card, EmptyState, Field } from "@/components/ui";
import type { Camera, Device } from "@/lib/types";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Camera Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [addName, setAddName] = useState("");
  const [addDeviceId, setAddDeviceId] = useState("");
  const [addSourceType, setAddSourceType] = useState<"ANDROID_KIOSK" | "EDGE_AGENT">("ANDROID_KIOSK");
  const [addDirection, setAddDirection] = useState<"AUTO" | "IN_ONLY" | "OUT_ONLY">("AUTO");
  const [addAssurance, setAddAssurance] = useState<"HIGH" | "STANDARD">("HIGH");
  const [addPending, setAddPending] = useState(false);

  // Edit Camera Modal
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [editName, setEditName] = useState("");
  const [editDirection, setEditDirection] = useState<"AUTO" | "IN_ONLY" | "OUT_ONLY">("AUTO");
  const [editAssurance, setEditAssurance] = useState<"HIGH" | "STANDARD">("HIGH");
  const [editEnabled, setEditEnabled] = useState(true);
  const [editPending, setEditPending] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [camRes, devRes] = await Promise.all([
        fetch("/api/proxy/api/v1/cameras"),
        fetch("/api/proxy/api/v1/devices"),
      ]);
      const camData = await camRes.json();
      const devData = await devRes.json();

      if (!camRes.ok || !camData.success) {
        throw new Error(camData.error?.message || "Failed to load cameras");
      }
      setCameras(camData.data);
      if (devData.success) {
        setDevices(devData.data);
        if (devData.data.length > 0 && !addDeviceId) {
          setAddDeviceId(devData.data[0].id);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error fetching cameras");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleAddCamera(e: React.FormEvent) {
    e.preventDefault();
    if (!addName.trim() || !addDeviceId) return;
    setAddPending(true);
    setError(null);

    try {
      const res = await fetch("/api/proxy/api/v1/cameras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: addDeviceId,
          name: addName.trim(),
          source_type: addSourceType,
          direction: addDirection,
          assurance: addAssurance,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to register camera");
      }
      setShowAddModal(false);
      setAddName("");
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error creating camera");
    } finally {
      setAddPending(false);
    }
  }

  async function handleUpdateCamera(e: React.FormEvent) {
    e.preventDefault();
    if (!editingCamera || !editName.trim()) return;
    setEditPending(true);
    setError(null);

    try {
      const res = await fetch(`/api/proxy/api/v1/cameras/${editingCamera.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim(),
          direction: editDirection,
          assurance: editAssurance,
          enabled: editEnabled,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to update camera");
      }
      setEditingCamera(null);
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error updating camera");
    } finally {
      setEditPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">Cameras</h1>
          <p className="mt-1 text-sm text-ink-500">
            Camera-independent ingestion streams (Android front/rear cameras, RTSP streams, edge agents).
          </p>
        </div>
        <Button onClick={() => setShowAddModal(true)} disabled={devices.length === 0}>
          + Add Camera
        </Button>
      </div>

      {error && <Banner tone="danger">{error}</Banner>}

      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-ink-500">Loading cameras…</div>
        ) : cameras.length === 0 ? (
          <EmptyState
            title="No cameras registered"
            body="Register a camera associated with one of your active kiosk devices."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-ink-200 bg-ink-50 text-ink-500 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Camera Name</th>
                  <th className="py-3 px-4">Source Type</th>
                  <th className="py-3 px-4">Direction</th>
                  <th className="py-3 px-4">Assurance</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {cameras.map((camera) => (
                  <tr
                    key={camera.id}
                    className={!camera.enabled ? "bg-ink-50/50 opacity-60" : "hover:bg-ink-50/60"}
                  >
                    <td className="py-3 px-4 whitespace-nowrap">
                      <p className="font-semibold text-ink-900">{camera.name}</p>
                      <p className="text-[11px] font-mono text-ink-400">
                        dev:{camera.device_id.slice(0, 8)}
                      </p>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="rounded bg-ink-100 px-2 py-0.5 text-[10px] font-semibold text-ink-800">
                        {camera.source_type}
                      </span>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="font-semibold text-ink-700">{camera.direction}</span>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          camera.assurance === "HIGH"
                            ? "bg-purple-100 text-purple-800"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {camera.assurance}
                      </span>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          camera.enabled
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-ink-200 text-ink-600"
                        }`}
                      >
                        {camera.enabled ? "ENABLED" : "DISABLED"}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingCamera(camera);
                          setEditName(camera.name);
                          setEditDirection(camera.direction);
                          setEditAssurance(camera.assurance);
                          setEditEnabled(camera.enabled);
                        }}
                        className="rounded border border-ink-200 px-2 py-1 text-[11px] font-medium text-ink-700 hover:bg-ink-50"
                      >
                        Configure
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Add Camera Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-ink-900">Add Camera Source</h3>
            <form onSubmit={handleAddCamera} className="mt-4 space-y-4">
              <Field
                label="Camera Name"
                required
                placeholder="e.g. North Gate Entrance Cam"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
              />

              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">
                  Host Device Binding
                </label>
                <select
                  value={addDeviceId}
                  onChange={(e) => setAddDeviceId(e.target.value)}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                >
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.id.slice(0, 8)})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">
                  Ingestion Source Type
                </label>
                <select
                  value={addSourceType}
                  onChange={(e) => setAddSourceType(e.target.value as "ANDROID_KIOSK" | "EDGE_AGENT")}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                >
                  <option value="ANDROID_KIOSK">ANDROID_KIOSK (Built-in Camera)</option>
                  <option value="EDGE_AGENT">EDGE_AGENT (RTSP / Network Stream)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 mb-1">
                    Direction
                  </label>
                  <select
                    value={addDirection}
                    onChange={(e) => setAddDirection(e.target.value as "AUTO" | "IN_ONLY" | "OUT_ONLY")}
                    className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                  >
                    <option value="AUTO">AUTO</option>
                    <option value="IN_ONLY">IN_ONLY</option>
                    <option value="OUT_ONLY">OUT_ONLY</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 mb-1">
                    Assurance Level
                  </label>
                  <select
                    value={addAssurance}
                    onChange={(e) => setAddAssurance(e.target.value as "HIGH" | "STANDARD")}
                    className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                  >
                    <option value="HIGH">HIGH (Challenge Liveness)</option>
                    <option value="STANDARD">STANDARD (Provisional without Liveness)</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowAddModal(false)}
                  disabled={addPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={addPending || !addName.trim()}>
                  {addPending ? "Adding…" : "Add Camera"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Camera Modal */}
      {editingCamera && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-ink-900">Configure Camera</h3>
            <form onSubmit={handleUpdateCamera} className="mt-4 space-y-4">
              <Field
                label="Camera Name"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-ink-700 mb-1">
                    Direction
                  </label>
                  <select
                    value={editDirection}
                    onChange={(e) => setEditDirection(e.target.value as "AUTO" | "IN_ONLY" | "OUT_ONLY")}
                    className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                  >
                    <option value="AUTO">AUTO</option>
                    <option value="IN_ONLY">IN_ONLY</option>
                    <option value="OUT_ONLY">OUT_ONLY</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-ink-700 mb-1">
                    Assurance Level
                  </label>
                  <select
                    value={editAssurance}
                    onChange={(e) => setEditAssurance(e.target.value as "HIGH" | "STANDARD")}
                    className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                  >
                    <option value="HIGH">HIGH</option>
                    <option value="STANDARD">STANDARD</option>
                  </select>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-ink-700 pt-1">
                <input
                  type="checkbox"
                  checked={editEnabled}
                  onChange={(e) => setEditEnabled(e.target.checked)}
                  className="rounded border-ink-300 text-brand-600 focus:ring-brand-500 size-4"
                />
                Enabled (Actively accepting attendance observations)
              </label>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setEditingCamera(null)}
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
    </div>
  );
}


"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Banner, Button, Card, Field, SectionTitle } from "@/components/ui";
import type { Employee } from "@/lib/types";

export default function EmployeeActions({
  employeeId,
  isActive,
  employee,
}: {
  employeeId: string;
  isActive: boolean;
  employee?: Employee;
}) {
  const router = useRouter();

  // Edit Profile Modal State
  const [isEditing, setIsEditing] = useState(false);
  const [editPending, setEditPending] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccess, setEditSuccess] = useState<string | null>(null);

  const [fullName, setFullName] = useState(employee?.full_name ?? "");
  const [email, setEmail] = useState(employee?.email ?? "");
  const [phone, setPhone] = useState(employee?.phone ?? "");
  const [jobTitle, setJobTitle] = useState(employee?.job_title ?? "");
  const [department, setDepartment] = useState(employee?.department ?? "");
  const [branch, setBranch] = useState(employee?.branch ?? "");
  const [shiftName, setShiftName] = useState(employee?.shift_name ?? "");

  // Fallback PIN State
  const [pin, setPin] = useState("");
  const [pinPending, setPinPending] = useState(false);
  const [pinMessage, setPinMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  // Status Toggle State
  const [statusPending, setStatusPending] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

  async function handleUpdateProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!fullName.trim() || !email.trim()) return;
    setEditPending(true);
    setEditError(null);

    try {
      const res = await fetch(`/api/proxy/api/v1/employees/${employeeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          phone: phone.trim() || null,
          job_title: jobTitle.trim() || null,
          department: department.trim() || null,
          branch: branch.trim() || null,
          shift_name: shiftName.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to update employee profile.");
      }
      setEditSuccess("Employee profile updated successfully.");
      setIsEditing(false);
      router.refresh();
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : "Error updating employee.");
    } finally {
      setEditPending(false);
    }
  }

  async function handleSetPin(event: React.FormEvent) {
    event.preventDefault();
    if (!pin.trim()) return;
    setPinPending(true);
    setPinMessage(null);

    try {
      const res = await fetch(`/api/proxy/api/v1/employees/${employeeId}/pin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pin.trim() }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to set PIN");
      }
      setPinMessage({ tone: "success", text: "Fallback PIN configured successfully." });
      setPin("");
    } catch (err: unknown) {
      setPinMessage({
        tone: "danger",
        text: err instanceof Error ? err.message : "Error setting PIN.",
      });
    } finally {
      setPinPending(false);
    }
  }

  async function handleToggleStatus() {
    setStatusPending(true);
    setStatusError(null);

    try {
      const res = await fetch(`/api/proxy/api/v1/employees/${employeeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !isActive }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to update employee status.");
      }
      router.refresh();
    } catch (err: unknown) {
      setStatusError(err instanceof Error ? err.message : "Error updating status.");
    } finally {
      setStatusPending(false);
    }
  }

  return (
    <>
      <Card className="p-6 space-y-6">
        <div>
          <div className="flex items-center justify-between">
            <SectionTitle>Profile & Information</SectionTitle>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                if (employee) {
                  setFullName(employee.full_name);
                  setEmail(employee.email);
                  setPhone(employee.phone ?? "");
                  setJobTitle(employee.job_title);
                  setDepartment(employee.department);
                  setBranch(employee.branch ?? "");
                  setShiftName(employee.shift_name ?? "");
                }
                setEditError(null);
                setIsEditing(true);
              }}
            >
              Edit Details
            </Button>
          </div>
          <p className="mt-1 text-sm text-ink-600">
            Modify employee name, designation, department, branch, or shift assignments.
          </p>
          {editSuccess && (
            <div className="mt-3">
              <Banner tone="info">{editSuccess}</Banner>
            </div>
          )}
        </div>

        <div className="border-t border-ink-100 pt-6">
          <SectionTitle>Security & Fallback PIN</SectionTitle>
          <p className="mt-1 text-sm text-ink-600">
            Employees without accounts authenticate via face scan. When a scan fails, they can check
            in using their Employee Code + PIN.
          </p>

          {pinMessage && (
            <div className="mt-3">
              <Banner tone={pinMessage.tone === "success" ? "info" : "danger"}>
                {pinMessage.text}
              </Banner>
            </div>
          )}

          <form onSubmit={handleSetPin} className="mt-4 space-y-3">
            <Field
              label="Set / Reset 4-6 Digit PIN"
              type="password"
              maxLength={6}
              placeholder="••••"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={pinPending || pin.trim().length < 4}>
                {pinPending ? "Saving…" : "Save Fallback PIN"}
              </Button>
            </div>
          </form>
        </div>

        <div className="border-t border-ink-100 pt-6">
          <SectionTitle>Employment Status</SectionTitle>
          <p className="mt-1 text-sm text-ink-600">
            Deactivated employees cannot scan or record attendance. Their historical attendance records
            remain intact for compliance and reporting.
          </p>

          {statusError && (
            <div className="mt-3">
              <Banner tone="danger">{statusError}</Banner>
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm font-medium text-ink-900">
              Account status:{" "}
              <span
                className={
                  isActive
                    ? "font-semibold text-emerald-700"
                    : "font-semibold text-rose-700"
                }
              >
                {isActive ? "Active" : "Deactivated"}
              </span>
            </span>
            <Button
              variant={isActive ? "danger" : "primary"}
              onClick={handleToggleStatus}
              disabled={statusPending}
            >
              {statusPending
                ? "Updating…"
                : isActive
                  ? "Deactivate Employee"
                  : "Reactivate Employee"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Edit Employee Details Modal */}
      {isEditing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 backdrop-blur-xs p-4">
          <div className="glass-panel w-full max-w-lg p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-ink-900">Edit Employee Details</h3>
            <p className="mt-1 text-xs text-ink-500">
              Update employee master records. Changes are tracked in the organization audit trail.
            </p>

            {editError && (
              <div className="mt-3">
                <Banner tone="danger">{editError}</Banner>
              </div>
            )}

            <form onSubmit={handleUpdateProfile} className="mt-4 space-y-3">
              <Field
                label="Full Name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
              <Field
                label="Email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Field
                label="Phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <Field
                label="Job Title"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <Field
                  label="Department"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                />
                <Field
                  label="Branch"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                />
              </div>
              <Field
                label="Shift Name"
                value={shiftName}
                onChange={(e) => setShiftName(e.target.value)}
              />

              <div className="flex justify-end gap-2 pt-3">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setIsEditing(false)}
                  disabled={editPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={editPending || !fullName.trim() || !email.trim()}>
                  {editPending ? "Saving Changes…" : "Save Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

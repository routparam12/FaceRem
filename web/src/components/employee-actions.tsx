"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Banner, Button, Card, Field, SectionTitle } from "@/components/ui";

export default function EmployeeActions({
  employeeId,
  isActive,
}: {
  employeeId: string;
  isActive: boolean;
}) {
  const router = useRouter();
  const [pin, setPin] = useState("");
  const [pinPending, setPinPending] = useState(false);
  const [pinMessage, setPinMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  const [statusPending, setStatusPending] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);

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
    <Card className="p-6 space-y-6">
      <div>
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
  );
}


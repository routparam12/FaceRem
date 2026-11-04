"use client";

import { useEffect, useState } from "react";

import { Banner, Button, Card, Field, SectionTitle } from "@/components/ui";
import type { OrganizationSettings } from "@/lib/types";

const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Toronto",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Australia/Sydney",
  "Pacific/Auckland",
];

export default function OrganizationSettingsPage() {
  const [org, setOrg] = useState<OrganizationSettings | null>(null);
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [customTimezone, setCustomTimezone] = useState("");
  const [useCustomTz, setUseCustomTz] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  async function loadOrg() {
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/api/v1/organization");
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to load organization settings");
      }
      setOrg(data.data);
      setName(data.data.name);
      const tz = data.data.timezone || "UTC";
      if (COMMON_TIMEZONES.includes(tz)) {
        setTimezone(tz);
        setUseCustomTz(false);
      } else {
        setUseCustomTz(true);
        setCustomTimezone(tz);
      }
    } catch (err: unknown) {
      setMessage({
        tone: "danger",
        text: err instanceof Error ? err.message : "Error loading organization settings",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOrg();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage(null);

    const targetTz = useCustomTz ? customTimezone.trim() : timezone;
    if (!targetTz) {
      setMessage({ tone: "danger", text: "Please specify a valid timezone." });
      setSaving(false);
      return;
    }

    try {
      const res = await fetch("/api/proxy/api/v1/organization", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          timezone: targetTz,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to save organization settings");
      }
      setMessage({ tone: "success", text: "Organization configuration saved successfully." });
      loadOrg();
    } catch (err: unknown) {
      setMessage({
        tone: "danger",
        text: err instanceof Error ? err.message : "Error saving settings",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Organization Settings</h1>
        <p className="mt-1 text-sm text-ink-500">
          Configure tenant identity, billing subscription tier, and primary IANA attendance timezone.
        </p>
      </div>

      {message && (
        <Banner tone={message.tone === "success" ? "info" : "danger"}>
          {message.text}
        </Banner>
      )}

      {loading ? (
        <Card className="p-8 text-center text-sm text-ink-500">
          Loading organization details…
        </Card>
      ) : (
        <form onSubmit={handleSave} className="space-y-6">
          <Card className="p-6 space-y-5">
            <SectionTitle>General Information</SectionTitle>

            <Field
              label="Organization Name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-ink-100 text-xs">
              <div>
                <span className="font-semibold text-ink-500">Tenant Slug</span>
                <p className="mt-0.5 font-mono text-ink-900">{org?.slug}</p>
              </div>
              <div>
                <span className="font-semibold text-ink-500">Subscription Plan</span>
                <p className="mt-0.5 font-semibold text-brand-700 uppercase">{org?.plan}</p>
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-5">
            <SectionTitle>Timezone Configuration</SectionTitle>
            <p className="text-xs text-ink-600">
              Daily lateness cutoffs, grace periods, and shift boundaries are calculated relative to
              this IANA timezone identifier.
            </p>

            {!useCustomTz ? (
              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">
                  Primary IANA Timezone
                </label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900 focus:border-brand-500 focus:outline-hidden"
                >
                  {COMMON_TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setUseCustomTz(true)}
                  className="mt-2 text-xs text-brand-700 hover:underline"
                >
                  Enter custom IANA timezone…
                </button>
              </div>
            ) : (
              <div>
                <Field
                  label="Custom IANA Timezone Identifier"
                  required
                  placeholder="e.g. Europe/Stockholm or Asia/Dubai"
                  value={customTimezone}
                  onChange={(e) => setCustomTimezone(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setUseCustomTz(false)}
                  className="mt-2 text-xs text-brand-700 hover:underline"
                >
                  ← Select from standard timezone list
                </button>
              </div>
            )}
          </Card>

          <div className="flex justify-end">
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? "Saving…" : "Save Settings"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}


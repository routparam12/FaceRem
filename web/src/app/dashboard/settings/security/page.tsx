"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";

import { Banner, Button, Card, Field, SectionTitle } from "@/components/ui";

interface SetupData {
  secret: string;
  provisioning_uri: string;
}

export default function SecuritySettingsPage() {
  const [step, setStep] = useState<"initial" | "scanning" | "completed">("initial");
  const [setupData, setSetupData] = useState<SetupData | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleStartSetup() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/api/v1/auth/totp/setup", {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Failed to start 2FA setup");
      }
      setSetupData(data.data);

      // Generate QR Code locally in the browser — never calls third-party APIs
      const url = await QRCode.toDataURL(data.data.provisioning_uri, {
        width: 256,
        margin: 2,
        color: { dark: "#0f172a", light: "#ffffff" },
      });
      setQrDataUrl(url);
      setStep("scanning");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred starting 2FA setup.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/proxy/api/v1/auth/totp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error?.message || "Invalid verification code.");
      }
      setRecoveryCodes(data.data.recovery_codes || []);
      setStep("completed");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopyRecoveryCodes() {
    navigator.clipboard.writeText(recoveryCodes.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Security Settings</h1>
        <p className="mt-1 text-sm text-ink-500">
          Manage two-factor authentication (TOTP) and account recovery codes.
        </p>
      </div>

      {error && <Banner tone="danger">{error}</Banner>}

      {step === "initial" && (
        <Card className="p-6">
          <div className="space-y-4">
            <div className="flex items-start gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand-50 text-2xl">
                🔐
              </span>
              <div>
                <h3 className="text-base font-semibold text-ink-900">
                  Two-Factor Authentication (TOTP)
                </h3>
                <p className="mt-1 text-sm text-ink-600">
                  Protect your administrator account with a time-based one-time password (TOTP).
                  Mandatory for production environments. Compatible with Google Authenticator,
                  1Password, Bitwarden, or Apple Passwords.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-ink-100 flex justify-end">
              <Button onClick={handleStartSetup} disabled={loading}>
                {loading ? "Generating secret…" : "Configure Two-Factor Auth"}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {step === "scanning" && setupData && (
        <Card className="p-6 space-y-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-700">
              Step 1 of 2
            </span>
            <h2 className="mt-1 text-lg font-bold text-ink-900">
              Scan QR Code in your Authenticator App
            </h2>
            <p className="mt-1 text-sm text-ink-600">
              Open your authenticator app and scan this QR code. The QR code is generated entirely
              inside your browser for maximum privacy.
            </p>
          </div>

          <div className="flex flex-col items-center justify-center p-4 rounded-xl border border-ink-200 bg-white shadow-xs">
            {qrDataUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={qrDataUrl}
                alt="TOTP Provisioning QR Code"
                className="size-56 rounded-lg"
              />
            ) : (
              <div className="size-56 animate-pulse bg-ink-100 rounded-lg" />
            )}
            <div className="mt-4 text-center">
              <p className="text-xs text-ink-500">Manual entry secret key:</p>
              <code className="mt-1 block rounded bg-ink-100 px-3 py-1 font-mono text-xs font-semibold text-ink-900 tracking-wider">
                {setupData.secret}
              </code>
            </div>
          </div>

          <form onSubmit={handleVerify} className="space-y-4 pt-4 border-t border-ink-100">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-brand-700">
                Step 2 of 2
              </span>
              <h3 className="mt-1 text-sm font-bold text-ink-900">
                Enter the 6-digit confirmation code
              </h3>
            </div>

            <Field
              label="Verification code"
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              autoComplete="one-time-code"
            />

            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep("initial")}
                className="text-xs font-medium text-ink-500 hover:text-ink-700"
              >
                Cancel
              </button>
              <Button type="submit" disabled={loading || code.trim().length < 6}>
                {loading ? "Verifying…" : "Activate 2FA"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {step === "completed" && (
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-emerald-100 text-emerald-800 text-lg">
              ✓
            </span>
            <div>
              <h2 className="text-lg font-bold text-ink-900">
                Two-Factor Authentication is Active!
              </h2>
              <p className="text-xs text-ink-500">
                Your account is now protected with time-based verification codes.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 space-y-3">
            <div className="flex items-start gap-2">
              <span className="text-amber-800 text-sm">⚠️</span>
              <div>
                <h4 className="text-sm font-semibold text-amber-900">
                  Save your Emergency Recovery Codes
                </h4>
                <p className="text-xs text-amber-800 mt-0.5">
                  If you ever lose access to your authenticator device, each recovery code can be used
                  exactly once to sign in. These codes are not displayed again.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 rounded-lg bg-white p-3 font-mono text-xs font-semibold text-ink-900 border border-amber-200">
              {recoveryCodes.map((rc, idx) => (
                <div key={idx} className="p-1 text-center bg-ink-50 rounded">
                  {rc}
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={handleCopyRecoveryCodes} className="text-xs">
                {copied ? "✓ Copied to clipboard" : "Copy recovery codes"}
              </Button>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <Button onClick={() => setStep("initial")}>
              Done
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}


"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Banner, Button, Field } from "@/components/ui";

const DEMO = { email: "hr@northwind.demo", password: "demo12345" };

export default function LoginForm({ sessionExpired }: { sessionExpired: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [is2faStep, setIs2faStep] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      if (is2faStep && challengeToken) {
        // Step 2: verify 2FA code (authenticator app or recovery code)
        const response = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            challenge_token: challengeToken,
            code: totpCode,
          }),
        });
        const body = await response.json();
        if (!response.ok || !body.ok) {
          setError(body.message ?? "Invalid authentication code.");
          return;
        }
        router.replace("/dashboard");
        router.refresh();
        return;
      }

      // Step 1: primary email + password
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, organization_slug: organization }),
      });
      const body = await response.json();

      if (!response.ok || !body.ok) {
        setError(body.message ?? "Sign in failed.");
        return;
      }

      if (body.totp_required && body.challenge_token) {
        setChallengeToken(body.challenge_token);
        setIs2faStep(true);
        return;
      }

      // The session lives in httpOnly cookies, so a refresh makes it visible
      router.replace("/dashboard");
      router.refresh();
    } catch {
      setError("Could not reach the attendance service.");
    } finally {
      setPending(false);
    }
  }

  if (is2faStep) {
    return (
      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-4">
          <p className="text-sm font-semibold text-brand-900">Two-Factor Authentication Required</p>
          <p className="mt-1 text-xs text-brand-700">
            Enter the 6-digit verification code from your authenticator app (Google Authenticator, Authy) or an 8-character recovery code.
          </p>
        </div>

        <Field
          label="Verification or recovery code"
          required
          autoFocus
          value={totpCode}
          onChange={(event) => setTotpCode(event.target.value)}
          placeholder="123456 or ABCDEF12"
          autoComplete="one-time-code"
        />

        {error && <Banner tone="danger">{error}</Banner>}

        <Button type="submit" className="w-full" disabled={pending || !totpCode.trim()}>
          {pending ? "Verifying…" : "Confirm Sign In"}
        </Button>

        <button
          type="button"
          onClick={() => {
            setIs2faStep(false);
            setChallengeToken(null);
            setTotpCode("");
            setError(null);
          }}
          className="w-full text-center text-xs font-medium text-ink-500 hover:text-ink-700"
        >
          ← Back to password sign in
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8 space-y-4">
      {sessionExpired && <Banner tone="warning">Your session expired. Please sign in again.</Banner>}

      <Field
        label="Organization code"
        hint="Optional — leave empty for a single-tenant account"
        value={organization}
        onChange={(event) => setOrganization(event.target.value)}
        placeholder="northwind"
        autoComplete="organization"
      />
      <Field
        label="Work email"
        type="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@company.com"
        autoComplete="username"
      />
      <Field
        label="Password"
        type="password"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        autoComplete="current-password"
      />

      {error && <Banner tone="danger">{error}</Banner>}

      <Button type="submit" className="w-full" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </Button>

      <button
        type="button"
        onClick={() => {
          setEmail(DEMO.email);
          setPassword(DEMO.password);
          setOrganization("northwind");
        }}
        className="w-full text-center text-sm font-medium text-brand-700 hover:text-brand-800"
      >
        Fill demo HR credentials
      </button>
    </form>
  );
}

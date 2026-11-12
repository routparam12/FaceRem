import { redirect } from "next/navigation";

import LoginForm from "@/components/login-form";
import { Wordmark } from "@/components/ui";
import { getAccessToken } from "@/lib/session";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ expired?: string }>;
}) {
  const { expired } = await searchParams;
  if (!expired && (await getAccessToken())) redirect("/dashboard");

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="glass-panel w-full max-w-md p-8 sm:p-10 shadow-2xl">
        <Wordmark className="mb-8" />
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Welcome back</h1>
        <p className="mt-1.5 text-sm text-ink-600">
          Sign in to your organization&apos;s attendance workspace.
        </p>
        <div className="mt-6">
          <LoginForm sessionExpired={Boolean(expired)} />
        </div>
      </div>
      <p className="mt-6 text-center text-xs font-medium text-ink-600/80">
        FaceAttend Console · Zero-Trust Biometrics · Multi-tenant
      </p>
    </main>
  );
}

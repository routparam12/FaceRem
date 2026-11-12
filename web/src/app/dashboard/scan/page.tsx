import { redirect } from "next/navigation";

import Scanner from "@/components/scanner";
import { Banner } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";
import { canRunScans } from "@/lib/types";

export default async function ScanPage() {
  const me = await apiGet<Me>("/api/v1/auth/me");
  if (process.env.NEXT_PUBLIC_ENABLE_WEB_SCANNER !== "1" || !canRunScans(me.role)) {
    redirect("/dashboard");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Attendance scanner</h1>
        <p className="mt-1 text-sm text-ink-500">
          Recognition runs on the server, scoped to {me.organization_name ?? "your organization"}.
        </p>
      </div>

      <Banner tone="warning">
        This browser scanner has no liveness detection — a held-up photo would pass. Production
        kiosks should use the Android client, where the on-device SDK produces a liveness score the
        server enforces.
      </Banner>

      <Scanner />
    </div>
  );
}

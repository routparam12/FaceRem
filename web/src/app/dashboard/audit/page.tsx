import { redirect } from "next/navigation";

import AuditLogViewer from "@/components/audit-log-viewer";
import { apiGet } from "@/lib/api";
import type { AuditEntry, Me } from "@/lib/types";
import { isOrgAdmin } from "@/lib/types";

export default async function AuditPage() {
  const me = await apiGet<Me>("/api/v1/auth/me");
  if (!isOrgAdmin(me.role)) redirect("/dashboard");

  const entries = await apiGet<AuditEntry[]>("/api/v1/audit-logs?limit=150");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Security Audit Log</h1>
        <p className="mt-1 text-sm text-ink-500">
          Read-only audit trail of tenant operations, biometric lifecycle updates, device bindings, and sign-ins.
          Passwords, biometric embeddings, and PINs are strictly redacted.
        </p>
      </div>

      <AuditLogViewer entries={entries} />
    </div>
  );
}

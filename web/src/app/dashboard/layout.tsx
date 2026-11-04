import Nav from "@/components/nav";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // Loading the principal here also validates the session for every nested page.
  const me = await apiGet<Me>("/api/v1/auth/me");

  return (
    <div className="min-h-dvh bg-ink-50/40">
      <Nav me={me} />
      <div className="lg:pl-64">
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}

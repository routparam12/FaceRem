"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Avatar, Wordmark, cx } from "@/components/ui";
import type { Me } from "@/lib/types";
import { canManagePeople, canRunScans } from "@/lib/types";

export default function Nav({ me }: { me: Me }) {
  const pathname = usePathname();
  const router = useRouter();

  // The server enforces these rules; hiding the links just avoids dead ends.
  const links = [
    { href: "/dashboard", label: "Overview", show: true },
    { href: "/dashboard/employees", label: "People", show: true },
    { href: "/dashboard/scan", label: "Scan", show: canRunScans(me.role) },
    { href: "/dashboard/attendance", label: "Attendance", show: true },
    { href: "/dashboard/audit", label: "Audit log", show: me.role === "ORG_ADMIN" || me.role === "ORGANIZATION_ADMIN" },
  ].filter((link) => link.show);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-ink-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
        <Link href="/dashboard">
          <Wordmark />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((link) => {
            const active =
              link.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-100",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-ink-900">{me.full_name}</p>
            <p className="text-xs text-ink-500">
              {me.role.replace("_", " ").toLowerCase()}
              {me.organization_name ? ` · ${me.organization_name}` : ""}
            </p>
          </div>
          <Avatar name={me.full_name} />
          <button
            onClick={signOut}
            className="rounded-lg px-2.5 py-2 text-sm font-medium text-ink-600 hover:bg-ink-100 hover:text-ink-900"
          >
            Sign out
          </button>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto border-t border-ink-200 px-4 py-2 md:hidden">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium text-ink-600"
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

export function ManageGate({ me, children }: { me: Me; children: React.ReactNode }) {
  return canManagePeople(me.role) ? <>{children}</> : null;
}

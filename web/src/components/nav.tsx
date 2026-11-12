"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import ThemeToggle from "@/components/theme-toggle";
import { Avatar, Wordmark, cx } from "@/components/ui";
import type { Me } from "@/lib/types";
import { canManagePeople, canRunScans, isOrgAdmin } from "@/lib/types";

export default function Nav({ me }: { me: Me }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isWebScannerEnabled = process.env.NEXT_PUBLIC_ENABLE_WEB_SCANNER === "1";

  const navSections = [
    {
      title: "Core",
      items: [
        { href: "/dashboard", label: "Dashboard", icon: "📊", show: true },
        { href: "/dashboard/employees", label: "Employees", icon: "👥", show: true },
        { href: "/dashboard/attendance", label: "Attendance", icon: "⏱️", show: true },
      ],
    },
    {
      title: "Hardware & Ingestion",
      items: [
        { href: "/dashboard/devices", label: "Kiosk Devices", icon: "📱", show: canManagePeople(me.role) },
        { href: "/dashboard/cameras", label: "Cameras", icon: "📷", show: canManagePeople(me.role) },
        { href: "/dashboard/scan", label: "Web Scanner", icon: "👁️", show: isWebScannerEnabled && canRunScans(me.role) },
      ],
    },
    {
      title: "Administration",
      items: [
        { href: "/dashboard/reports", label: "Reports & Export", icon: "📥", show: true },
        { href: "/dashboard/audit", label: "Audit Log", icon: "🛡️", show: isOrgAdmin(me.role) },
        { href: "/dashboard/settings", label: "Organization", icon: "⚙️", show: isOrgAdmin(me.role) },
        { href: "/dashboard/settings/security", label: "Security & 2FA", icon: "🔐", show: true },
      ],
    },
  ];

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  return (
    <>
      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 sm:px-6 backdrop-blur-[18px] shadow-[var(--glass-shadow)] transition-colors">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="grid size-9 place-items-center rounded-lg text-ink-600 hover:bg-white/60 lg:hidden"
            aria-label="Toggle navigation"
          >
            <span className="text-xl">☰</span>
          </button>
          <Link href="/dashboard" className="flex items-center gap-2">
            <Wordmark />
          </Link>
          {me.organization_name && (
            <span className="hidden items-center gap-1.5 rounded-full border border-[var(--glass-border)] bg-white/50 px-3 py-0.5 text-xs font-semibold text-ink-700 shadow-2xs backdrop-blur-xs sm:inline-flex">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              {me.organization_name}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />

          <div className="hidden text-right sm:block">
            <p className="text-sm font-semibold text-ink-900">{me.full_name}</p>
            <p className="text-xs uppercase tracking-wide text-ink-500">
              {me.role.replace(/_/g, " ")}
            </p>
          </div>
          <Avatar name={me.full_name} />
          <button
            onClick={signOut}
            className="rounded-lg border border-ink-200/80 bg-white/60 px-3 py-1.5 text-xs font-semibold text-ink-700 shadow-xs backdrop-blur-xs transition hover:bg-white hover:text-ink-900"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Sidebar (Desktop) */}
      <aside className="fixed inset-y-0 left-0 top-16 z-20 hidden w-64 border-r border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-[18px] shadow-[var(--glass-shadow)] transition-colors lg:block">
        <div className="flex h-full flex-col justify-between overflow-y-auto px-4 py-6">
          <div className="space-y-6">
            {navSections.map((section) => {
              const visibleItems = section.items.filter((item) => item.show);
              if (visibleItems.length === 0) return null;
              return (
                <div key={section.title}>
                  <p className="px-2 text-xs font-bold uppercase tracking-wider text-ink-400">
                    {section.title}
                  </p>
                  <div className="mt-2 space-y-1">
                    {visibleItems.map((item) => {
                      const active =
                        item.href === "/dashboard"
                          ? pathname === "/dashboard"
                          : pathname.startsWith(item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          className={cx(
                            "flex items-center gap-3 rounded-full px-3.5 py-2 text-sm font-medium transition-colors",
                            active
                              ? "glass-pill font-semibold shadow-xs"
                              : "text-ink-600 hover:bg-white/60 hover:text-ink-900",
                          )}
                        >
                          <span className="text-base">{item.icon}</span>
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-2xl border border-[var(--glass-border)] bg-white/40 p-3.5 text-xs text-ink-600 shadow-2xs backdrop-blur-xs">
            <p className="font-semibold text-ink-900">Kiosk-First Biometrics</p>
            <p className="mt-0.5 text-ink-500">Zero-Trust Server Recognition</p>
          </div>
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 top-16 z-40 bg-ink-900/30 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            className="h-full w-64 border-r border-[var(--glass-border)] bg-[var(--glass-bg)] p-4 shadow-2xl backdrop-blur-[24px]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-6">
              {navSections.map((section) => (
                <div key={section.title}>
                  <p className="px-2 text-xs font-bold uppercase tracking-wider text-ink-400">
                    {section.title}
                  </p>
                  <div className="mt-2 space-y-1">
                    {section.items
                      .filter((item) => item.show)
                      .map((item) => (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setMobileMenuOpen(false)}
                          className={cx(
                            "flex items-center gap-3 rounded-full px-3.5 py-2 text-sm font-medium transition-colors",
                            pathname === item.href
                              ? "glass-pill font-semibold shadow-xs"
                              : "text-ink-600 hover:bg-white/60",
                          )}
                        >
                          <span>{item.icon}</span>
                          {item.label}
                        </Link>
                      ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function ManageGate({ me, children }: { me: Me; children: React.ReactNode }) {
  return canManagePeople(me.role) ? <>{children}</> : null;
}

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import type { AttendanceStatus } from "@/lib/types";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** The product mark: a face-scan reticle, matching the Android launcher icon. */
export function BrandMark({ className = "size-9" }: { className?: string }) {
  return (
    <span
      className={cx(
        className,
        "inline-flex items-center justify-center rounded-[28%]",
        "bg-gradient-to-br from-brand-600 to-violet-600 text-white shadow-xs",
      )}
    >
      <svg viewBox="0 0 36 36" fill="none" className="size-[62%]" aria-hidden="true">
        <g
          stroke="currentColor"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 12V7a3 3 0 0 1 3-3h5" />
          <path d="M24 4h5a3 3 0 0 1 3 3v5" />
          <path d="M32 24v5a3 3 0 0 1-3 3h-5" />
          <path d="M12 32H7a3 3 0 0 1-3-3v-5" />
          <path d="M13.5 21.5a6 6 0 0 0 9 0" />
        </g>
        <circle cx="13.5" cy="15" r="1.8" fill="currentColor" />
        <circle cx="22.5" cy="15" r="1.8" fill="currentColor" />
      </svg>
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cx("flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="text-lg font-semibold tracking-tight text-ink-900">FaceAttend</span>
    </span>
  );
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white shadow-xs hover:bg-brand-700 disabled:bg-ink-300",
  secondary: "border border-ink-200/80 bg-white/70 backdrop-blur-xs text-ink-800 hover:bg-white shadow-xs disabled:text-ink-400",
  danger: "border border-danger/30 bg-danger-bg text-danger-fg hover:bg-danger/15 shadow-xs",
  ghost: "text-ink-600 hover:bg-white/60 hover:text-ink-900",
};

export function Button({
  variant = "primary",
  className,
  ...props
}: ComponentProps<"button"> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4",
        "text-sm font-semibold transition-colors disabled:cursor-not-allowed",
        buttonStyles[variant],
        className,
      )}
    />
  );
}

export function ButtonLink({
  href,
  variant = "primary",
  className,
  children,
}: {
  href: string;
  variant?: ButtonVariant;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cx(
        "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4",
        "text-sm font-semibold transition-colors",
        buttonStyles[variant],
        className,
      )}
    >
      {children}
    </Link>
  );
}

export function Field({
  label,
  hint,
  error,
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink-700">{label}</span>
      <input
        {...props}
        aria-invalid={error ? true : undefined}
        className={cx(
          "h-11 w-full rounded-xl border px-3.5 text-sm text-ink-900",
          "bg-[var(--glass-input-bg)] placeholder:text-ink-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/20",
          error ? "border-danger" : "border-ink-200/90",
        )}
      />
      {(error || hint) && (
        <span className={cx("mt-1.5 block text-xs", error ? "text-danger" : "text-ink-500")}>
          {error ?? hint}
        </span>
      )}
    </label>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx("glass-panel overflow-hidden", className)}>{children}</div>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-base font-semibold text-ink-900">{children}</h2>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  caption,
  tone = "brand",
}: {
  label: string;
  value: string | number;
  caption?: string;
  tone?: "brand" | "success" | "warning" | "danger";
}) {
  const tones = {
    brand: "text-brand-600",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
  } as const;
  return (
    <Card className="p-5">
      <p className="text-sm font-medium text-ink-500">{label}</p>
      <p className="mt-1 text-3xl font-bold tracking-tight text-ink-900">{value}</p>
      {caption && <p className={cx("mt-1 text-xs font-semibold", tones[tone])}>{caption}</p>}
    </Card>
  );
}

const statusTones: Record<AttendanceStatus, string> = {
  PRESENT: "bg-success-bg text-success-fg border border-emerald-300/40",
  LATE: "bg-warning-bg text-warning-fg border border-amber-300/40",
  ABSENT: "bg-danger-bg text-danger-fg border border-rose-300/40",
  ON_LEAVE: "bg-info-bg text-info-fg border border-sky-300/40",
};

export function Pill({ children, tone }: { children: ReactNode; tone: string }) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-2xs", tone)}>
      {children}
    </span>
  );
}

export function StatusPill({ status }: { status: AttendanceStatus }) {
  return <Pill tone={statusTones[status]}>{status.replace("_", " ").toLowerCase()}</Pill>;
}

export function EnrollmentPill({ enrolled }: { enrolled: boolean }) {
  return (
    <Pill tone={enrolled ? "bg-success-bg text-success-fg border border-emerald-300/40" : "bg-warning-bg text-warning-fg border border-amber-300/40"}>
      {enrolled ? "Face enrolled" : "Enrollment pending"}
    </Pill>
  );
}

export function Avatar({ name, className = "size-9" }: { name: string; className?: string }) {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
  return (
    <span
      className={cx(
        className,
        "inline-flex shrink-0 items-center justify-center rounded-full",
        "bg-brand-100 text-xs font-bold text-brand-800 shadow-2xs",
      )}
    >
      {initials || "?"}
    </span>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="text-sm font-semibold text-ink-800">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-ink-500">{body}</p>
    </div>
  );
}

export function Banner({ tone, children }: { tone: "warning" | "danger" | "info"; children: ReactNode }) {
  const tones = {
    warning: "bg-warning-bg text-warning-fg border border-amber-300/50",
    danger: "bg-danger-bg text-danger-fg border border-rose-300/50",
    info: "bg-info-bg text-info-fg border border-sky-300/50",
  } as const;
  return <div className={cx("rounded-xl px-3.5 py-2.5 text-sm shadow-2xs", tones[tone])}>{children}</div>;
}

export function formatTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

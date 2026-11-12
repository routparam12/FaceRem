import Link from "next/link";

import ThemeToggle from "@/components/theme-toggle";
import { BrandMark, ButtonLink, Card, Wordmark } from "@/components/ui";

const capabilities = [
  {
    title: "Attendance in one look",
    body: "The camera detects a face on device and checks frame quality. Recognition happens on your organization's server — never on the handset.",
  },
  {
    title: "Tenant isolation by construction",
    body: "Every employee, record and face profile belongs to one organization, and face search is filtered to that organization before any matching runs.",
  },
  {
    title: "Roles that match your org chart",
    body: "Org admins, HR, managers, employees and kiosk devices each get exactly the access they need — enforced on the server, not in the UI.",
  },
  {
    title: "Built for biometric data",
    body: "Consent is recorded, embeddings are stored instead of photographs, and removing a face profile never deletes attendance history.",
  },
];

const steps = [
  { n: "01", title: "Add your people", body: "Import employees with codes, departments, branches and shifts." },
  { n: "02", title: "Enroll faces once", body: "Three quick angles with consent recorded against each profile." },
  { n: "03", title: "Check in with a glance", body: "A kiosk or phone scans, the server verifies, the record is written." },
];

export default function LandingPage() {
  return (
    <div className="relative min-h-dvh text-ink-900">
      <header className="sticky top-0 z-30 w-full border-b border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-[18px] saturate-[140%]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Wordmark />
          <nav className="flex items-center gap-3">
            <Link
              href="#how"
              className="hidden rounded-full px-3 py-1.5 text-sm font-medium text-ink-600 transition hover:text-ink-900 sm:block"
            >
              How it works
            </Link>
            <ThemeToggle />
            <ButtonLink href="/login" variant="secondary">
              Sign in
            </ButtonLink>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 pt-10 pb-20 sm:pt-20">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <span className="glass-pill inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-brand-700">
              <span className="size-1.5 rounded-full bg-brand-500 animate-pulse" />
              Multi-tenant attendance platform
            </span>
            <h1 className="mt-5 text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
              Facial attendance for modern teams.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink-600">
              Enroll a face once, then let people check in and out with a glance. Shift-aware
              records, department reporting and an audit trail — for offices, campuses, factories
              and multi-branch organizations.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/login">Open the console</ButtonLink>
              <ButtonLink href="#how" variant="secondary">
                See how it works
              </ButtonLink>
            </div>
            <p className="mt-5 text-sm text-ink-500">
              Demo tenant available — sign in with{" "}
              <code className="rounded-md border border-[var(--glass-border)] bg-[var(--glass-input-bg)] px-2 py-0.5 font-mono text-xs font-medium text-ink-800 shadow-2xs">
                hr@northwind.demo
              </code>
            </p>
          </div>

          <Card className="overflow-hidden p-0 shadow-lg">
            <div className="flex items-center gap-3 border-b border-[var(--glass-border)] bg-white/30 px-5 py-4 dark:bg-ink-900/20">
              <BrandMark className="size-10" />
              <div>
                <p className="text-sm font-semibold text-ink-900">FaceAttend Architecture</p>
                <p className="text-xs text-ink-500">Enterprise Biometric Operations</p>
              </div>
            </div>
            <dl className="grid grid-cols-2 divide-x divide-y divide-[var(--glass-border)]">
              {[
                ["Passive & Active", "Liveness"],
                ["Sub-second", "Matching"],
                ["Zero-Trust", "Multi-tenant"],
                ["Tamper-proof", "Audit trail"],
              ].map(([label, value]) => (
                <div key={label} className="px-5 py-6">
                  <dt className="text-xs font-semibold uppercase tracking-wider text-brand-600">{label}</dt>
                  <dd className="mt-1 text-2xl font-bold tracking-tight text-ink-900">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="border-t border-[var(--glass-border)] bg-white/20 px-5 py-3 text-xs text-ink-500 dark:bg-ink-900/10">
              Hardware-accelerated edge and server biometric pipeline.
            </p>
          </Card>
        </div>
      </section>

      <section className="relative mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-6 sm:grid-cols-2">
          {capabilities.map((item) => (
            <Card
              key={item.title}
              className="p-6 shadow-md transition-transform duration-200 hover:-translate-y-0.5"
            >
              <h3 className="text-base font-semibold text-ink-900">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-600">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl px-6 py-20">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-600">Workflow</span>
          <h2 className="text-3xl font-bold tracking-tight text-ink-900">How it works</h2>
        </div>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          {steps.map((step) => (
            <Card
              key={step.n}
              className="p-6 shadow-sm transition-transform duration-200 hover:-translate-y-0.5"
            >
              <span className="glass-pill inline-flex size-8 items-center justify-center font-mono text-xs font-bold text-brand-600">
                {step.n}
              </span>
              <h3 className="mt-3 text-base font-semibold text-ink-900">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{step.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <footer className="border-t border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-[18px]">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-ink-500 sm:flex-row sm:items-center sm:justify-between">
          <Wordmark />
          <p>Biometric data is handled with consent, retention limits and a full audit trail.</p>
        </div>
      </footer>
    </div>
  );
}

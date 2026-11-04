"use client";

import { useState } from "react";

import { Button, Card, Field } from "@/components/ui";

export default function ReportsPage() {
  // Attendance Events Filter
  const [startDate, setStartDate] = useState(
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
  );
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState("");

  // Monthly Summary Filter
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState(currentMonth);

  function downloadEventsCsv() {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (method) params.set("method", method);

    const url = `/api/proxy/api/v1/reports/attendance-events.csv?${params.toString()}`;
    window.location.href = url;
  }

  function downloadMonthlySummaryCsv() {
    const params = new URLSearchParams();
    params.set("year", String(year));
    params.set("month", String(month));

    const url = `/api/proxy/api/v1/reports/monthly-summary.csv?${params.toString()}`;
    window.location.href = url;
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">Reports & Data Export</h1>
        <p className="mt-1 text-sm text-ink-500">
          Export verified attendance records and payroll metrics as UTF-8 BOM CSV files.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Report 1: Raw Attendance Events */}
        <Card className="p-6 space-y-5">
          <div className="flex items-start gap-4">
            <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-blue-50 text-2xl">
              📋
            </span>
            <div>
              <h2 className="text-base font-bold text-ink-900">Attendance Events Stream</h2>
              <p className="mt-1 text-xs text-ink-600">
                Granular record of every biometric and PIN scan event with camera timestamps,
                assurance ratings, verification statuses, and void reasons.
              </p>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-ink-100">
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Start Date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <Field
                label="End Date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink-700 mb-1">
                Authentication Method
              </label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
              >
                <option value="">All Verification Methods</option>
                <option value="FACE">Face Scan Only</option>
                <option value="PIN">Employee PIN Fallback Only</option>
              </select>
            </div>

            <div className="pt-2 flex justify-end">
              <Button onClick={downloadEventsCsv}>
                Download Events CSV
              </Button>
            </div>
          </div>
        </Card>

        {/* Report 2: Monthly Attendance Summary */}
        <Card className="p-6 space-y-5">
          <div className="flex items-start gap-4">
            <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-emerald-50 text-2xl">
              📊
            </span>
            <div>
              <h2 className="text-base font-bold text-ink-900">Monthly Payroll & Lateness Rollup</h2>
              <p className="mt-1 text-xs text-ink-600">
                Aggregated monthly attendance per employee: total days present, days late,
                unexcused absences, total work hours, and accumulated late penalties.
              </p>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-ink-100">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">Year</label>
                <select
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                >
                  {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-700 mb-1">Month</label>
                <select
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                  className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-xs font-medium text-ink-900"
                >
                  {[
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December",
                  ].map((mName, idx) => (
                    <option key={idx + 1} value={idx + 1}>
                      {mName}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="pt-8 flex justify-end">
              <Button onClick={downloadMonthlySummaryCsv}>
                Download Monthly Summary CSV
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Security Compliance Card */}
      <Card className="p-6 bg-ink-50/50">
        <div className="flex items-start gap-3">
          <span className="text-lg">🛡️</span>
          <div className="text-xs text-ink-600 space-y-1">
            <p className="font-semibold text-ink-900">Security & Integrity Standards:</p>
            <p>
              • <strong>Formula Injection Defense:</strong> All exported values beginning with dangerous
              characters (<code className="font-mono bg-ink-200 px-1 rounded">=</code>,{" "}
              <code className="font-mono bg-ink-200 px-1 rounded">+</code>,{" "}
              <code className="font-mono bg-ink-200 px-1 rounded">-</code>,{" "}
              <code className="font-mono bg-ink-200 px-1 rounded">@</code>) are automatically prefixed
              with a single quote (<code className="font-mono bg-ink-200 px-1 rounded">&apos;</code>) to
              neutralize spreadsheet command execution attacks in Excel and LibreOffice.
            </p>
            <p>
              • <strong>UTF-8 BOM Header:</strong> Files include a UTF-8 Byte Order Mark (
              <code className="font-mono bg-ink-200 px-1 rounded">\ufeff</code>) to ensure non-Latin employee
              names render accurately across legacy desktop applications.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}


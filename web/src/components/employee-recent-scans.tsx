"use client";

import { useEffect, useState } from "react";

import { Card, EmptyState, SectionTitle } from "@/components/ui";

interface ScanPhoto {
  id: string;
  event_id: string;
  timestamp: string;
  size_bytes: number;
}

export default function EmployeeRecentScans({ employeeId }: { employeeId: string }) {
  const [photos, setPhotos] = useState<ScanPhoto[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/proxy/api/v1/employees/${employeeId}/recent-scans`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) {
          setPhotos(data);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [employeeId]);

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <SectionTitle>Recent Kiosk Verification Scans</SectionTitle>
          <p className="text-xs text-ink-500">
            Audit photos captured automatically at the kiosk during check-in/out. Kept for a rolling 7-day retention period.
          </p>
        </div>
        <span className="glass-pill px-2.5 py-0.5 text-xs font-semibold text-brand-700">
          Last 7 Days
        </span>
      </div>

      {loading ? (
        <Card className="p-8 text-center text-sm text-ink-500">Loading audit captures…</Card>
      ) : photos.length === 0 ? (
        <Card>
          <EmptyState
            title="No scan photos in last 7 days"
            body="New verification captures will appear here automatically when this person checks in or out at a kiosk."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {photos.map((photo) => {
            const dateObj = new Date(photo.timestamp);
            const timeLabel = dateObj.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
            const dateLabel = dateObj.toLocaleDateString([], { month: "short", day: "numeric" });

            return (
              <Card key={photo.id} className="overflow-hidden p-0 shadow-sm transition hover:shadow-md">
                <div className="relative aspect-square w-full bg-ink-100 overflow-hidden">
                  <img
                    src={`/api/proxy/api/v1/employees/${employeeId}/recent-scans/${photo.id}`}
                    alt="Kiosk scan capture"
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                  <div className="absolute top-1.5 right-1.5 rounded-full bg-ink-900/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur-xs">
                    Kiosk
                  </div>
                </div>
                <div className="p-2.5 text-center">
                  <p className="text-xs font-semibold text-ink-900">{timeLabel}</p>
                  <p className="text-[10px] text-ink-500">{dateLabel}</p>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}


import { androidBuild } from "@/lib/android-build";
import { Card, cx } from "@/components/ui";

function AndroidIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M17.6 9.48l1.84-3.18a.38.38 0 0 0-.14-.52.38.38 0 0 0-.52.14l-1.86 3.22a11.4 11.4 0 0 0-9.84 0L5.22 5.92a.38.38 0 0 0-.52-.14.38.38 0 0 0-.14.52L6.4 9.48A10.78 10.78 0 0 0 1 18h22a10.78 10.78 0 0 0-5.4-8.52M7 15.25a1.25 1.25 0 1 1 1.25-1.25A1.25 1.25 0 0 1 7 15.25m10 0A1.25 1.25 0 1 1 18.25 14 1.25 1.25 0 0 1 17 15.25" />
    </svg>
  );
}

/** The download block, used on the landing page and inside the console. */
export default function AndroidDownload({ compact = false }: { compact?: boolean }) {
  const build = androidBuild();

  const meta = [build.version && `Version ${build.version}`, build.sizeLabel, `Android ${build.minAndroid}+`]
    .filter(Boolean)
    .join(" · ");

  if (compact) {
    return (
      <Card className="p-5">
        <div className="flex items-center gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-ink-900 text-white">
            <AndroidIcon className="size-6" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink-900">Android app</p>
            <p className="truncate text-xs text-ink-500">
              {build.url ? meta : "Not published yet"}
            </p>
          </div>
          <DownloadAction url={build.url} compact />
        </div>
      </Card>
    );
  }

  return (
    <section id="app" className="border-y border-ink-200 bg-ink-50">
      <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 lg:grid-cols-2">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-ink-700 ring-1 ring-ink-200">
            <AndroidIcon className="size-3.5" />
            Android
          </span>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-ink-900">
            Put the scanner on the wall
          </h2>
          <p className="mt-3 max-w-md text-ink-600">
            Mount a tablet by the door and the app runs hands-free: someone steps up, is
            recognised, and walks on. The same build works on a phone for enrolling faces
            and checking the day&apos;s attendance.
          </p>
          <div className="mt-7">
            <DownloadAction url={build.url} />
          </div>
          {build.url && meta && <p className="mt-3 text-xs text-ink-500">{meta}</p>}
          <p className="mt-5 max-w-md text-xs leading-relaxed text-ink-500">
            The app is distributed directly rather than through the Play Store, so Android
            will ask you to allow installation from this source the first time.
          </p>
        </div>

        <Card className="p-6">
          <ol className="space-y-5">
            {[
              ["Install on the device", "A phone for enrolling people, or a tablet for the gate."],
              ["Sign in with your work account", "The app only ever sees your own organization."],
              ["Enrol faces, then scan", "Recognition runs on your server — never on the device."],
            ].map(([title, body], index) => (
              <li key={title} className="flex gap-4">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand-700">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink-900">{title}</p>
                  <p className="mt-0.5 text-sm text-ink-600">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </section>
  );
}

/**
 * A real link when there is a build, and a plain disabled state when there is not —
 * rather than a button that looks ready and leads to a 404.
 */
function DownloadAction({ url, compact = false }: { url: string | null; compact?: boolean }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors";
  const size = compact ? "h-9 px-3 text-xs" : "h-12 px-5 text-sm";

  if (!url) {
    return (
      <span
        className={cx(base, size, "cursor-not-allowed bg-ink-200 text-ink-500")}
        title="Set ANDROID_APK_URL to make the app downloadable"
      >
        Download APK
      </span>
    );
  }

  return (
    <a
      href={url}
      download
      className={cx(base, size, "bg-ink-900 text-white shadow-sm hover:bg-ink-800")}
    >
      Download APK
    </a>
  );
}


import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">404 - Page Not Found</h2>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
        The requested resource could not be found.
      </p>
      <Link
        href="/dashboard"
        className="mt-6 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Return to Dashboard
      </Link>
    </div>
  );
}


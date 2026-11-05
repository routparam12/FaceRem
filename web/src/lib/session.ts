import { cookies } from "next/headers";

export const ACCESS_COOKIE = "fa_access";
export const REFRESH_COOKIE = "fa_refresh";

/**
 * Session cookies are httpOnly, so the access token is never readable from JavaScript.
 * This is the reason the browser talks to this app's route handlers instead of FastAPI:
 * a token in localStorage is one XSS away from being exfiltrated.
 */
export function cookieOptions(maxAgeSeconds: number) {
  const isProduction = process.env.NODE_ENV === "production";
  const explicitOverride = process.env.COOKIE_SECURE;
  const secure =
    explicitOverride !== undefined
      ? explicitOverride === "1" || explicitOverride.toLowerCase() === "true"
      : isProduction;

  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}

export async function getAccessToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(ACCESS_COOKIE)?.value ?? null;
}

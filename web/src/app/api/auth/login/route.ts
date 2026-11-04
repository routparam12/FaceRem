import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";
import { ACCESS_COOKIE, REFRESH_COOKIE, cookieOptions } from "@/lib/session";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  totp_required?: boolean;
  challenge_token?: string;
}

const ACCESS_MAX_AGE = 30 * 60;
const REFRESH_MAX_AGE = 14 * 24 * 60 * 60;

export async function POST(request: Request) {
  const payload = await request.json();

  try {
    // Step 2: TOTP / Recovery Code Verification
    if (payload.challenge_token && payload.code) {
      const tokens = await apiFetch<TokenPair>("/api/v1/auth/totp/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_token: payload.challenge_token,
          code: payload.code.trim(),
        }),
      });

      const response = NextResponse.json({ ok: true });
      response.cookies.set(ACCESS_COOKIE, tokens.access_token, cookieOptions(ACCESS_MAX_AGE));
      response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, cookieOptions(REFRESH_MAX_AGE));
      return response;
    }

    // Step 1: Standard Email / Password Sign In
    const tokens = await apiFetch<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: payload.email,
        password: payload.password,
        organization_slug: payload.organization_slug || null,
        totp_code: payload.totp_code || null,
      }),
    });

    if (tokens.totp_required && tokens.challenge_token) {
      return NextResponse.json({
        ok: true,
        totp_required: true,
        challenge_token: tokens.challenge_token,
      });
    }

    // Tokens go straight into httpOnly cookies and are never returned to JavaScript.
    const response = NextResponse.json({ ok: true });
    response.cookies.set(ACCESS_COOKIE, tokens.access_token, cookieOptions(ACCESS_MAX_AGE));
    response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, cookieOptions(REFRESH_MAX_AGE));
    return response;
  } catch (error) {
    if (error instanceof ApiError) {
      return NextResponse.json({ ok: false, message: error.message }, { status: error.status });
    }
    return NextResponse.json(
      { ok: false, message: "Could not reach the attendance service." },
      { status: 502 },
    );
  }
}

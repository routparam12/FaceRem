import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

/**
 * Authenticated BFF proxy for browser-initiated requests.
 * Attaches the httpOnly session access token so it is never exposed in JavaScript.
 * Strictly enforces an endpoint allowlist and validates Same-Origin CSRF protection.
 */
const ALLOWED: Record<string, RegExp[]> = {
  GET: [
    /^api\/v1\/devices$/,
    /^api\/v1\/cameras$/,
    /^api\/v1\/employees$/,
    /^api\/v1\/employees\/[\w-]+$/,
    /^api\/v1\/attendance\/events$/,
    /^api\/v1\/organization$/,
    /^api\/v1\/reports\/attendance-events\.csv$/,
    /^api\/v1\/reports\/monthly-summary\.csv$/,
  ],
  POST: [
    /^api\/v1\/employees$/,
    /^api\/v1\/employees\/[\w-]+\/face\/enroll$/,
    /^api\/v1\/employees\/[\w-]+\/pin$/,
    /^api\/v1\/attendance\/recognize$/,
    /^api\/v1\/attendance\/events\/[\w-]+\/void$/,
    /^api\/v1\/attendance\/events\/[\w-]+\/confirm$/,
    /^api\/v1\/devices\/enrollment-code$/,
    /^api\/v1\/devices\/[\w-]+\/revoke$/,
    /^api\/v1\/cameras$/,
    /^api\/v1\/auth\/totp\/setup$/,
    /^api\/v1\/auth\/totp\/verify$/,
  ],
  PATCH: [
    /^api\/v1\/employees\/[\w-]+$/,
    /^api\/v1\/devices\/[\w-]+$/,
    /^api\/v1\/cameras\/[\w-]+$/,
    /^api\/v1\/organization$/,
  ],
  DELETE: [
    /^api\/v1\/employees\/[\w-]+\/face$/,
  ],
};

function validateCsrf(request: Request): boolean {
  if (["GET", "HEAD"].includes(request.method)) return true;

  const host = request.headers.get("host");
  if (!host) return false;

  const origin = request.headers.get("origin");
  if (origin) {
    try {
      const originHost = new URL(origin).host;
      return originHost === host;
    } catch {
      return false;
    }
  }

  // When Origin is absent, allow only if Sec-Fetch-Site is "same-origin"
  const secFetchSite = request.headers.get("sec-fetch-site");
  if (secFetchSite === "same-origin") {
    return true;
  }

  return false;
}

async function forward(
  request: Request,
  path: string[],
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
) {
  if (!validateCsrf(request)) {
    return NextResponse.json(
      { success: false, error: { code: "CSRF_ERROR", message: "Cross-site request forgery detected." } },
      { status: 403 },
    );
  }

  const target = path.join("/");
  const allowedList = ALLOWED[method] ?? [];
  if (!allowedList.some((pattern) => pattern.test(target))) {
    return NextResponse.json(
      { success: false, error: { code: "FORBIDDEN", message: "This endpoint is not proxied." } },
      { status: 403 },
    );
  }

  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json(
      { success: false, error: { code: "UNAUTHORIZED", message: "Your session has ended." } },
      { status: 401 },
    );
  }

  const url = new URL(request.url);
  const targetUrl = `${API_BASE_URL}/${target}${url.search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const upstream = await fetch(targetUrl, {
    method,
    headers,
    body: ["GET", "DELETE"].includes(method) ? undefined : await request.arrayBuffer(),
  });

  const responseContentType = upstream.headers.get("content-type") ?? "application/json";
  const upstreamHeaders: Record<string, string> = {
    "Content-Type": responseContentType,
  };
  const disposition = upstream.headers.get("content-disposition");
  if (disposition) {
    upstreamHeaders["Content-Disposition"] = disposition;
  }

  return new NextResponse(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: upstreamHeaders,
  });
}

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path, "GET");
}

export async function POST(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path, "POST");
}

export async function PUT(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path, "PUT");
}

export async function PATCH(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path, "PATCH");
}

export async function DELETE(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path, "DELETE");
}

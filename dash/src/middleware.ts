import { NextResponse, type NextRequest } from "next/server";

/**
 * Feature-flag gated routing for the v2 dashboard.
 *
 * When NEXT_PUBLIC_DASH_V2 === "true":
 *   - /pipeline|/agents|/audit|/mcp|/settings|/admin -> 302 redirect to /v2/<path>
 *   - /v2/* passes through normally
 *
 * When the flag is unset / "false":
 *   - /v2/* is rewritten to /404 (hidden until ready)
 *   - legacy routes pass through untouched
 *
 * NEXT_PUBLIC_* is baked into the client bundle at build time, but middleware
 * executes on the Vercel Edge runtime with full access to process.env, so
 * reading it here is safe and deterministic per deploy.
 */

const LEGACY_PATHS: ReadonlySet<string> = new Set([
  "/pipeline",
  "/agents",
  "/audit",
  "/mcp",
  "/settings",
  "/admin",
]);

const isFlagOn = (): boolean =>
  process.env.NEXT_PUBLIC_DASH_V2 === "true";

export function middleware(req: NextRequest): NextResponse {
  const { pathname } = req.nextUrl;
  const flagOn = isFlagOn();

  // Flag ON: redirect legacy routes to their /v2 counterparts.
  if (flagOn && LEGACY_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL(`/v2${pathname}`, req.url), 302);
  }

  // Flag OFF: hide /v2/* behind a 404 rewrite.
  if (!flagOn && pathname.startsWith("/v2")) {
    return NextResponse.rewrite(new URL("/404", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/pipeline",
    "/agents",
    "/audit",
    "/mcp",
    "/settings",
    "/admin",
    "/v2/:path*",
  ],
};

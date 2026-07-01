import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "@/i18n/routing";
import { decodeAccessToken, isExpired } from "@/lib/auth/jwt";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/config";

const intlMiddleware = createMiddleware(routing);

// Paths considered "inside the dashboard" — everything else (landing,
// /login, /api/*) is public. Adjust as Phase 7+ adds more protected routes.
const PROTECTED_PREFIXES = ["/dashboard", "/ru/dashboard"];
const LOGIN_PATH = "/login";

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

function isLoginPath(pathname: string): boolean {
  return pathname === LOGIN_PATH || pathname === "/ru/login";
}

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  const payload = accessToken ? decodeAccessToken(accessToken) : null;
  const hasValidAccess = payload !== null && !isExpired(payload);
  // Even if the access token expired, a live refresh token means the
  // dashboard layout can silently refresh on first load instead of bouncing
  // the person back to /login.
  const hasSession = hasValidAccess || Boolean(refreshToken);

  if (isProtectedPath(pathname) && !hasSession) {
    const loginUrl = new URL(LOGIN_PATH, request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isLoginPath(pathname) && hasValidAccess) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return intlMiddleware(request);
}

export const config = {
  // Skip static files, Next internals, and our own BFF API routes — those
  // handle their own auth checks per-route.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};

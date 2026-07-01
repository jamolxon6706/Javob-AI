/**
 * Server-side config for the Next.js BFF (Backend-for-Frontend) layer.
 *
 * The dashboard never calls FastAPI directly from the browser for
 * authenticated requests — it goes through Next.js Route Handlers under
 * /api/* which read the HttpOnly cookies set by FastAPI's /auth/verify and
 * forward them as `Authorization: Bearer <token>`. This mirrors the comment
 * in apps/api/src/javobai/auth/cookies.py: "FastAPI side still uses the
 * existing HTTPBearer dependency — we don't add a second auth code path."
 *
 * INTERNAL_API_BASE_URL is server-only (no NEXT_PUBLIC_ prefix) because the
 * browser must never talk to FastAPI directly — only this server can.
 */
export const API_BASE_URL =
  process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";

// Must match apps/api/src/javobai/auth/cookies.py
export const ACCESS_COOKIE = "javobai_access";
export const REFRESH_COOKIE = "javobai_refresh";

/**
 * Phase 8 — the one narrow, documented exception to "the browser never talks
 * to FastAPI directly" (see javobai/ws/router.py's docstring for the full
 * rationale): a persistent WebSocket can't be proxied through a Next.js
 * Route Handler, so the inbox opens this connection straight from the
 * browser. It carries no JWT — only a one-time ticket minted by
 * POST /auth/ws-ticket (itself called through the normal cookie-authed BFF
 * proxy), so exposing this origin doesn't leak the access token.
 *
 * In production, infra/nginx/nginx.conf proxies `/ws/` on the public domain
 * straight to the api container, so this can — and should — be set to a
 * same-origin path (e.g. `wss://app.javobai.uz/ws/inbox`) instead of a
 * separate host.
 */
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/inbox";

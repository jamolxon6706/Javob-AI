# @javobai/web — Dashboard

The tenant-facing dashboard for JavobAI. Next.js 16 (App Router, Turbopack),
TypeScript strict, Tailwind 4, `next-intl` (uz default + ru).

## Getting started

From the repo root (this app depends on `@javobai/ui` and
`@javobai/shared-types` via the pnpm workspace):

```bash
pnpm install
cp ../../.env.example ../../.env   # then fill in real values
pnpm --filter web dev
```

Open [http://localhost:3000](http://localhost:3000). You'll be redirected to
`/login` unless you have a valid session cookie from the API.

The dev server expects `apps/api` running on `http://localhost:8000` (or
whatever `INTERNAL_API_BASE_URL` points to).

## Architecture

See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md#phase-6--dashboard-foundation)
for the full write-up (Phase 8's inbox realtime transport is documented at
[`#phase-8--operator-inbox`](../../docs/ARCHITECTURE.md#phase-8--operator-inbox)).
Short version:

- **Auth is cookie-based and BFF-proxied.** The browser never holds a JWT or
  calls FastAPI directly for REST calls. `src/app/api/auth/*` and
  `src/app/api/proxy/*` are Next.js Route Handlers that forward to FastAPI
  server-side and relay `Set-Cookie` back to the browser.
- **One narrow exception:** the Phase 8 inbox opens a websocket
  (`src/lib/ws/use-inbox-socket.ts`) straight from the browser to the API,
  because a persistent connection can't be proxied through a Route Handler.
  It carries a one-time ticket (minted via the normal proxy), never the JWT.
- **`src/proxy.ts`** (Next.js 16's renamed `middleware.ts`) handles locale
  routing (`next-intl`) and redirects unauthenticated requests away from
  `/dashboard/*`. It only *decodes* JWT claims (no signature check) to avoid
  an unnecessary redirect when a silent refresh would do — the actual
  verification happens once, in FastAPI.
- **i18n**: `uz` is the default locale with no URL prefix
  (`/dashboard`); `ru` is prefixed (`/ru/dashboard`). Message bundles live in
  `messages/uz.json` / `messages/ru.json`.
- **Login flow** (`src/components/auth/`) is split into a router-agnostic
  state machine hook (`use-login-flow.ts`) and presentational steps
  (`PhoneStep`, `OtpStep`), so the flow itself is unit-testable without an
  App Router test harness.

## Scripts

```bash
pnpm dev         # next dev (Turbopack)
pnpm build       # next build
pnpm typecheck   # tsc --noEmit
pnpm test        # vitest run
```

## Environment variables

| Variable | Purpose |
|---|---|
| `INTERNAL_API_BASE_URL` | Server-only FastAPI origin the BFF route handlers call. **Not** prefixed `NEXT_PUBLIC_` — the browser must never reach FastAPI directly for REST calls. |
| `NEXT_PUBLIC_WS_URL` | Phase 8 only. Where the browser opens the inbox websocket directly (see above). Same-origin `/ws/inbox` path in production (nginx proxies it to the api container), `ws://localhost:8000/ws/inbox` in dev. |

See the repo-root `.env.example` for the full list (shared with `apps/api`).


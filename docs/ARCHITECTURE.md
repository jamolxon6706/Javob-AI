# JavobAI — Architecture

> Living document. Update after every 3-4 phases.

## Overview

JavobAI is a multi-tenant B2B SaaS that provides an omnichannel AI auto-responder
for Uzbekistan SMBs. It connects Telegram, WhatsApp, Instagram, and Facebook into
one AI brain with RAG-grounded responses in Uzbek and Russian.

## Monorepo Layout

```
javobai/
  apps/
    web/         # Next.js 16 (App Router) — landing + dashboard
    api/         # FastAPI core engine
    worker/      # ARQ workers (queue consumers, scheduled jobs)
  packages/
    shared-types/ # TS types shared between web and generated API client
    ui/           # Shared React components / design tokens
  infra/
    docker-compose.yml  # postgres+pgvector, redis, api, worker, web
    nginx/              # Reverse proxy + SSL config
    Dockerfile.api  Dockerfile.web  Dockerfile.worker
  docs/
    ARCHITECTURE.md  API.md  DEPLOY.md
  .github/workflows/ci.yml
```

## Runtime Architecture

```
Inbound webhook (FastAPI)
  → verify signature
  → 200 OK in <1s
  → push job to Redis queue
  → Worker normalizes to UnifiedMessage
  → CoreEngine decision pipeline
  → Outbound dispatcher (per-platform adapter, window/rate aware)
  → reply
```

## Core Engine Decision Pipeline

Single source of truth, fully tested:

1. **Dedup** — Redis SETNX on `platform:message_id`
2. **Stop-words / business-hours / operator-active check**
3. **Rule engine** — keyword/trigger → fixed action
4. **RAG** — embed query (bge-m3, local) → pgvector cosine search over tenant FAQs
   - `score >= 0.85` → return FAQ answer directly (**FREE PATH**, no LLM)
   - `0.65 <= score < 0.85` → LLM answer grounded on top-k FAQ chunks
   - `score < 0.65` → agentic action OR human handoff
5. **Agentic layer** — if intent matches a registered Action (order_status, booking), call tenant tool with function-calling
6. **Confidence gate** — low confidence or sensitive topic → handoff queue

## Unified Message Contract

Every platform adapter produces and consumes this shape:

```python
class UnifiedMessage(BaseModel):
    tenant_id: str
    platform: Platform            # telegram | whatsapp | instagram | facebook
    channel_id: str
    kind: MessageKind             # dm | comment | comment_reply
    external_user_id: str
    conversation_id: str
    text: str
    media: list[MediaItem]
    lang_hint: str | None
    raw: dict                     # original platform payload
    received_at: datetime
```

## Technology Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Frontend    | Next.js 16, TypeScript, Tailwind 4  |
| Backend     | FastAPI, SQLAlchemy 2.0 async, Alembic |
| Queue       | Redis + ARQ                         |
| Database    | PostgreSQL 16 + pgvector            |
| Embeddings  | BAAI/bge-m3 (local, 1024-dim)       |
| LLM         | Groq (llama-3.3-70b) → optional Gemini/Claude escalation |
| Auth        | Phone + OTP → JWT (access + refresh) |
| Payments    | CLICK, Payme (UZS)                  |
| Deploy      | AWS Lightsail, Docker Compose, Nginx |

## Phase 5 — Outbound dispatcher

The dispatcher (`apps/worker/src/worker/services/dispatcher.py`) is the single
gateway between the engine and the platform adapter. Every outbound reply goes
through this pipeline, in this exact order:

```
EngineReply
   │
   ▼
1. Empty-reply check                              → reason="empty_reply"
2. Meta 24h window check (Telegram exempt)        → reason="window_expired"
   └─ mark conversation waiting_operator + emit handoff:{tenant} event
3. Per-conversation anti-runaway (try_acquire)    → reason="rate_limited"
   └─ push to DLQ + emit handoff event
4. Per-channel back-pressure (blocking acquire)   → (waits)
5. Send via platform adapter                      → reason="send_failed" on raise
   └─ push to DLQ
6. Persist outbound Message row
7. If reply.source == "handoff": mark conversation + emit handoff event
```

### Why two rate-limiters

| Bucket | Key | Algorithm | Purpose |
|--------|-----|-----------|---------|
| Channel-level | `ratelimit:{channel_id}` | blocking fixed-window, 20/s | Respect the platform's per-bot/per-number send limit (Telegram, WhatsApp) |
| Per-conversation | `ratelimit:conv:{tenant_id}:{conversation_id}` | non-blocking fixed-window, 3/min | Stop a runaway customer / integration loop from burning through the LLM quota and spamming one user |

The per-conversation limit is non-blocking because the inbound pipeline must
never stall — a refusal becomes a DLQ entry plus a handoff event so a human
can step in. The channel-level limit IS blocking because the platform itself
will 429-throttle us if we exceed it; backing off is the only correct response.

### Messaging window

`conversations.window_expires_at` is refreshed on every inbound message
(`+24h`). Telegram is exempt — there is no Meta-style 24h customer-service
window. WhatsApp / Instagram / Facebook replies outside the window are blocked
and the conversation is flagged for operator pickup. Phase 9 introduces
template sending as the "needs_template" reason for out-of-window replies.

### Dead-letter queue

When a send fails permanently (adapter exhausted its own retries), the
dispatcher pushes a JSON entry to a Redis list:

```
LPUSH dlq:outbound '{"tenant_id":..., "conversation_id":..., "reason":"send_failed", ...}'
LTRIM dlq:outbound 0 999
```

Same for per-conversation rate-limit refusals (`reason="rate_limited"`).
Bounded by `dlq_max_entries` (default 1000) so a runaway tenant can't fill
Redis. A drain task (Phase 13) will surface these to the operator dashboard.

### Handoff events (Redis pub/sub)

Whenever the dispatcher marks a conversation for handoff, it publishes a JSON
event on a per-tenant channel:

```
PUBLISH handoff:{tenant_id} '{
  "event_id": "uuid",
  "conversation_id": "...",
  "channel_id": "...",
  "external_user_id": "...",
  "platform": "whatsapp",
  "reason": "out_of_window" | "low_confidence" | "rate_limited",
  "rag_score": 0.42,
  "timestamp": "ISO-8601"
}'
```

Phase 8 (operator inbox + WebSocket transport) will subscribe to these
channels and push new-handoff notifications to the operator's browser tab in
real time. For now the publisher is wired and tested; subscribers come in
Phase 8.

### Structured result

`OutboundDispatcher.send()` returns an `OutboundResult` instead of a bool:

```python
@dataclass(frozen=True)
class OutboundResult:
    reason: Literal["sent", "empty_reply", "window_expired", "rate_limited", "send_failed"]
    handoff: Literal["low_confidence", "out_of_window", "rate_limited", "needs_template"] | None
```

Phase 13 analytics groups by `reason` to compute the "AI auto-resolved vs
handoff" funnel; `handoff` gives the operator inbox a stable reason label.

## Phase 6 — Dashboard foundation

`apps/web` is the tenant-facing dashboard: Next.js 16 (App Router, Turbopack),
`next-intl` for uz (default, no URL prefix) + ru, and phone+OTP auth matching
the API exactly.

### BFF (Backend-for-Frontend) auth pattern

The browser never talks to FastAPI directly for authenticated requests. JWTs
live in HttpOnly cookies set by FastAPI (`javobai.auth.cookies`); the web app
cannot read them with JavaScript, and by design it never gets the JWT secret
to verify them either. Instead:

```
Browser → /api/auth/* (Next.js Route Handler) → FastAPI /auth/*
                                                     │
                                            relays Set-Cookie back
```

- `/api/auth/request-otp`, `/api/auth/verify` — thin proxies; FastAPI's
  Set-Cookie headers are read via `response.headers.getSetCookie()` and
  re-attached individually (a plain fetch() merges multiple Set-Cookie
  headers, which breaks when access + refresh are both set).
- `/api/auth/refresh` — reads the refresh cookie server-side, calls FastAPI,
  relays the rotated pair. FastAPI rotates refresh tokens (old one revoked in
  Redis on every use), so refreshing must happen through a route handler, not
  a Server Component — RSC rendering can't mutate response cookies.
- `/api/proxy/[...path]` — generic authenticated forward (`Authorization:
  Bearer <access_token>` from the cookie) for dashboard data calls. Phase 6
  only exercises it implicitly; Phase 7's FAQ/channel CRUD screens will be
  the first real callers.
- Server Components (`lib/api/server.ts`) call FastAPI directly when they
  already run server-side (e.g. the dashboard layout fetching `/tenants/me`)
  — no need to loop back through our own `/api/proxy`.

`proxy.ts` (see below) does a **non-verifying** JWT decode (`jose.decodeJwt`,
no signature check) purely to decide redirect-vs-render. The web app has no
way to verify signatures since it never holds `JWT_SECRET`; the only place a
token is cryptographically checked is `javobai.auth.deps.get_current_user` in
FastAPI. If `proxy.ts` ever let an unverified claim drive anything other than
a redirect, that would be a real boundary violation — it doesn't.

### Next.js 16 surprises hit during this phase

Two Next.js 16 breaking changes broke the build silently (no error until
`next build`, since `next dev` and `tsc` don't exercise the same code path):

1. **`middleware.ts` → `proxy.ts`.** Next.js 16 renamed the file convention;
   `middleware.ts` is still accepted but logs a deprecation warning and (in
   this project's testing) the file's logic did not take effect in the
   production build. File renamed, default export renamed `middleware` →
   `proxy`, logic unchanged. Runs on Node.js now, not Edge — fine here since
   the JWT decode doesn't need Edge-only APIs anyway.
2. **`next-intl@3.26`'s `createNextIntlPlugin()` targets the wrong Turbopack
   config shape.** It injects `experimental.turbo.resolveAlias`, which was
   the pre-16 location; Next 16 moved Turbopack config to a top-level
   `turbopack` key and dropped `experimental.turbo` entirely, so the alias
   silently never applied and `next-intl` couldn't resolve its request
   config at runtime ("Couldn't find next-intl config file"), surfacing only
   during static page generation. Fixed by skipping the plugin and setting
   the alias directly: `turbopack.resolveAlias["next-intl/config"]`.

Also removed a stray duplicate `pnpm-workspace.yaml` + `pnpm-lock.yaml` that
had been sitting inside `apps/web/` since Phase 0 — harmless for `pnpm`
itself, but it confused Turbopack's workspace-root detection and produced a
misleading warning during `next build`.

### i18n routing

`localePrefix: "as-needed"` — `uz` (default) has no URL prefix
(`/dashboard`), `ru` is prefixed (`/ru/dashboard`). `next-intl@3.26` predates
the `hasLocale()` helper (added in v4), so it's reimplemented locally in
`i18n/routing.ts` as a simple type guard.

### Component structure

Login is split into a state-machine hook (`use-login-flow.ts`, no Next.js
router dependency) and two presentational steps (`PhoneStep`, `OtpStep`),
specifically so the flow logic can be unit-tested with `renderHook()`
without needing an App Router test harness for `next/navigation`. The
`LoginFlow` component is the only place that wires the hook to
`router.replace()`.

## Phase 8 — Operator Inbox

Builds the human side of the Phase 5 handoff queue: a unified inbox across
channels, an operator reply path that silences the bot, an AI copilot, and a
realtime transport so none of this requires polling-and-praying.

### Realtime transport: ticket + websocket, not the session cookie

`GET /ws/inbox` can't be reached the way every other authenticated dashboard
call is — through `/api/proxy/[...path]`, which attaches `Authorization:
Bearer <token>` server-side (see Phase 6's BFF pattern above). A persistent
WebSocket can't be proxied through a Next.js Route Handler, so the browser
has to open it directly against the API. That's a real exception to "the
browser never talks to FastAPI directly," so it's scoped as narrowly as
possible:

1. Browser calls `POST /api/proxy/auth/ws-ticket` (normal cookie-authed
   proxy) → FastAPI's `auth.router.create_ws_ticket` mints a random
   `secrets.token_urlsafe(32)`, stores `{user_id, tenant_id, name}` in Redis
   under `ws_ticket:{ticket}` with a 60s TTL, returns the ticket. No JWT
   leaves the server.
2. Browser opens `new WebSocket(`${NEXT_PUBLIC_WS_URL}?ticket=...`)`.
   `javobai.ws.router.ws_inbox` reads the ticket via the same `get_redis`
   dependency every other route uses (kept as a FastAPI dependency rather
   than a raw connection specifically so this handler stays unit-testable
   against the existing `mock_redis` fixture), deletes it (single-use), and
   accepts the connection scoped to that tenant.
3. A second long-lived task (`javobai.ws.router._listen`, started in
   `main.py`'s lifespan) psubscribes to Redis `handoff:*` (Phase 5) and
   `events:*` (this phase) and fans every message out to that tenant's
   connected sockets via `javobai.ws.manager.ConnectionManager`.

In production, `infra/nginx/nginx.conf` proxies `/ws/` on the public domain
straight to the `api` container, so `NEXT_PUBLIC_WS_URL` can be a
same-origin path (`wss://app.javobai.uz/ws/inbox`) instead of a second
public hostname — the browser never learns of a separate API origin, which
keeps the spirit of the Phase 6 decision even though the literal mechanism
(direct browser connection) differs.

### What's realtime and what isn't

`javobai.events.publish_event` writes to `events:{tenant_id}` only from the
API process — operator-sent replies and conversation status changes
(resolve/assign), since those originate in the API itself. Inbound
customer/bot messages are **not** published there: that would mean touching
`apps/worker`'s `OutboundDispatcher` / inbound task, both of which have
exact-call-count unit tests on their Redis interactions (`test_dispatcher.py`
mocks `dlq_redis` with bare `MagicMock`, so an unconditional new `await
redis.publish(...)` on the plain success path would raise `TypeError: object
MagicMock can't be used in 'await' expression` the moment those tests ran).
Given that, the inbox instead short-polls `GET /inbox/conversations` (6s) and
`GET /inbox/{id}/messages` (4s) for inbound traffic, while handoff creation,
operator replies, and presence are genuinely instant over the socket. Revisit
once Phase 13 gives the worker a proper observability event bus to publish
through without touching the dispatcher's tested paths.

### Operator reply silences the bot

`POST /inbox/{id}/reply` sends via the channel adapter directly (Telegram
only for now — `javobai.inbox.router._send_telegram`, mirroring
`apps/worker`'s adapter rather than importing it, since `apps/api` and
`apps/worker` are separate Python packages/venvs with no shared dependency
today), persists the message with `source="operator"`, and sets
`conversations.status = "open"` + `bot_silenced_until = now + 30min`. The
column already existed from Phase 1's schema — `worker.engine.core`'s
`is_bot_active()` check (Phase 5) already respects it, so no worker change
was needed to make the bot actually go quiet.

### Copilot doesn't run the RAG pipeline

`POST /inbox/{id}/copilot` calls Groq directly with the conversation history
and up to 15 of the tenant's FAQs pasted in as context — it does **not** run
`apps/worker`'s `bge-m3` vector search. Loading that embedding model into the
API process just for an operator-assist feature that only needs to be
"good enough" (not exact, like the customer-facing RAG path) wasn't worth the
memory/startup cost. Revisit if a tenant's FAQ list grows past what fits in
one prompt.

### Presence (collision indicator) is in-memory, single-instance

`javobai.ws.manager.ConnectionManager` keeps "who's looking at this
conversation" in a process-local dict, not Redis. Correct today (one API
instance); if the API is ever scaled horizontally, two operators on
different instances won't see each other's presence. The handoff/message
fan-out already goes through Redis pub/sub and scales fine — only the
presence map would need to move (e.g. a per-conversation Redis set with
short-TTL heartbeats) to scale past one instance.

## Decisions

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | ARQ over Celery | ARQ is async-native (Python asyncio), simpler for FastAPI + Redis stack | 2026-06-15 |
| 2 | pgvector over Qdrant | Fewer infra components; pgvector good enough for <1M embeddings; can migrate later | 2026-06-15 |
| 3 | bge-m3 embeddings | Multilingual (Uzbek + Russian), 1024-dim, runs locally, free | 2026-06-15 |
| 4 | Groq as primary LLM provider | Fast inference, generous free tier for MVP, OpenAI-compatible API | 2026-06-15 |
| 5 | pnpm workspaces | Fast, disk-efficient, workspace protocol for internal packages | 2026-06-15 |
| 6 | Two rate-limiter buckets (channel + per-conversation) | Channel-level back-pressure is blocking (the platform will 429); per-conversation is non-blocking (refusal becomes DLQ + handoff event) | 2026-06-26 |
| 7 | DLQ is a bounded Redis list, not a separate DB table | Avoids a 2nd write path; sufficient for short-lived operational failures; Phase 13 analytics will surface them | 2026-06-26 |
| 8 | Handoff events on Redis pub/sub (not Postgres NOTIFY) | Already have Redis connected; Phase 8 WebSocket fan-out is a natural fit; Postgres NOTIFY is per-database, harder to shard | 2026-06-26 |
| 9 | `OutboundResult` is a frozen dataclass, not a Pydantic model | Pure value object crossing an internal boundary; Pydantic adds overhead with no gain | 2026-06-26 |
| 10 | BFF route handlers proxy all auth + authenticated calls; browser never holds the JWT secret or talks to FastAPI directly | Cookie-based auth requires a server-side hop to relay Set-Cookie and attach Bearer headers; keeps `JWT_SECRET` out of the web app entirely | 2026-06-27 |
| 11 | `proxy.ts` (Next 16's renamed `middleware.ts`) decodes JWTs without verifying signatures | Only used for redirect-vs-render UX; the web app never holds `JWT_SECRET`, so verification is impossible and unnecessary here — FastAPI is the sole point of cryptographic verification | 2026-06-27 |
| 12 | Manual `turbopack.resolveAlias` instead of `next-intl`'s `createNextIntlPlugin()` | The plugin (next-intl@3.26) injects the pre-Next.js-16 `experimental.turbo` config shape, which Next 16 dropped; the alias silently never applied. Setting it directly under the new top-level `turbopack` key is the Next-16-native fix | 2026-06-27 |
| 13 | Login flow logic extracted into `useLoginFlow` hook, decoupled from `next/navigation` | Lets the phone→OTP→verify state machine be unit-tested with `renderHook()` without an App Router test harness; the component layer only wires in the redirect | 2026-06-27 |
| 14 | Inbox realtime: one-time ticket + direct browser↔API websocket, instead of relaying through a Route Handler | Persistent WebSockets can't be proxied through Next.js Route Handlers; the ticket (not the JWT) is the only thing exposed to the browser, and nginx puts it back on the same origin in production | 2026-06-29 |
| 15 | Inbound customer/bot messages are not pushed over the Phase 8 websocket; the inbox short-polls for them instead | Wiring `apps/worker`'s dispatcher/inbound task to publish would touch code with exact-call-count Redis mocks in its existing tests; handoff + operator-reply + presence — the parts that actually need to feel instant — are still fully realtime | 2026-06-29 |
| 16 | Operator copilot pastes FAQs into the LLM prompt directly instead of running the bge-m3 RAG search | Avoids loading the embedding model into the API process for an assistive (not customer-facing) feature; revisit if a tenant's FAQ list outgrows one prompt | 2026-06-29 |
| 17 | Inbox presence (collision indicator) lives in an in-process map, not Redis | Simplest reversible option for a single API instance; only this map — not the Redis-backed handoff/message fan-out — would need to change to scale to multiple instances | 2026-06-29 |
| 18 | WhatsApp inbound now goes through `arq.enqueue_job(...)` instead of a raw `redis.rpush` to a hand-rolled key | The rpush key was never read by the ARQ worker (it listens on ARQ's own internal queue format), so inbound WhatsApp messages were silently dropped before this fix; matches the pattern every other channel already used | 2026-06-30 |
| 19 | WhatsApp/Meta tasks now build `CoreEngine` via `ctx["core_engine"]` + `engine.process(msg, conn)`, not `CoreEngine(db=..., redis=...)` + `.decide()` | The latter interface was never implemented on `CoreEngine` (no `db`/`redis` constructor args, no `.decide()` method) — every WhatsApp/IG/FB message would have raised `TypeError` at the engine call; Telegram's `tasks/inbound.py` already had the correct interface, so both channels were brought in line with it | 2026-06-30 |
| 20 | WhatsApp normalizer now emits the canonical `worker.engine.unified.UnifiedMessage`, not its own local `UnifiedMessage`/`MediaAttachment` classes | `CoreEngine` and `OutboundDispatcher` only accept the canonical type (same one Telegram/Meta produce); the WhatsApp-local class was structurally similar but a different Pydantic model, so it would have failed type validation the moment it reached the engine | 2026-06-30 |
| 21 | `meta_extra: dict \| None` added as a declared field on `UnifiedMessage` | `adapters/meta/normalizer.py` was already setting it and `instagram_dispatcher.py` was already reading it for comment_id/post_id context, but Pydantic v2's default `extra="ignore"` was silently dropping it since it wasn't declared — IG comment replies could never resolve which comment to reply to | 2026-06-30 |
| 22 | IG/FB comment events (`changes` field, not just `messaging`) are now ingested by the webhook | `_ingest_meta_events` only ever read `entry.messaging` despite the route's own docstring claiming comment support, and despite the normalizer/dispatcher already having comment-handling code paths; Phase 10's comment→DM flow was unreachable until this fix | 2026-06-30 |
| 23 | `reactflow` added to `apps/web/package.json` dependencies | `flows/[id]/page.tsx` already imports and uses it for the visual flow canvas, but the package was missing from `package.json` — `pnpm install` / CI would have failed the moment that route was hit | 2026-06-30 |

## Known Gaps (as of 2026-06-30 merge/audit pass)

These are real, not yet fixed — flagged here rather than silently left for a future session to rediscover:

- **Flow execution is not wired in.** `worker/services/flow_engine.py` and `flow_trigger.py` exist and can presumably execute a saved flow JSON, but nothing in `tasks/inbound.py`, `tasks/whatsapp.py`, or `tasks/meta.py` ever calls them. A tenant can build and save a flow in the dashboard, but it will never actually run against a real customer message. Phase 11's flow-builder UI is real and functional; the runtime half is not connected.
- **No tests for `engine/core.py`, the action framework (`action_executor.py`), or flow execution.** Operating principle #6 ("RAG, window-tracking, and dispatcher logic MUST be tested") was followed for RAG/window/dispatcher but not for the core decision pipeline itself or the Phase 11 additions.
- **WhatsApp template registry is a stub.** Outside the 24h window, `send_text` raises `TemplateRequiredError` and the message is just dropped/logged — there's no DB-backed per-tenant approved-template table to look up and send instead, despite Phase 9's task list calling for one.

## Phase Progress

- [x] Phase 0 — Repo skeleton & infra
- [x] Phase 1 — Backend core: DB, migration, auth, tenant
- [x] Phase 2 — Telegram adapter + webhook ingestion + queue
- [x] Phase 3 — RAG core (local embeddings)
- [x] Phase 4 — LLM fallback + model router + guardrails
- [x] Phase 5 — Outbound dispatcher, 24h window, rate-limit, handoff
- [x] Phase 6 — Dashboard foundation (Next.js, auth, i18n)
- [x] Phase 7 — Dashboard modules
- [x] Phase 8 — Inbox (operator panel) + copilot + realtime
- [x] Phase 9 — WhatsApp Cloud API adapter (inbound pipeline fixed 2026-06-30; template registry still a stub)
- [x] Phase 10 — Instagram + Facebook adapters (comment ingestion + engine wiring fixed 2026-06-30)
- [~] Phase 11 — Agentic actions + flow builder (actions wired into `core.py`; flow builder UI works; flow *execution* not connected — see Known Gaps)
- [x] Phase 12 — Growth layer: contacts, broadcast, drip, catalog, opt-in (full test coverage)
- [ ] Phase 13 — Analytics + observability + AI QA
- [ ] Phase 14 — Billing (CLICK / Payme) + plans
- [ ] Phase 15 — Landing page
- [ ] Phase 16 — Security, deploy, launch

---

## Phase 12 — Growth Layer (Contacts, Broadcast, Drip, Catalog, Opt-in)

### What was added

**Backend (`apps/api/src/javobai/growth/`)**
- `router.py` — full REST API for all growth features (40+ endpoints)
- `schemas.py` — Pydantic schemas for all request/response bodies

**New DB models**
- `DripSequence`, `DripStep`, `DripEnrollment` — drip sequence engine
- `Product` — conversational commerce catalog
- `CampaignRecipient` — per-contact delivery tracking (delivered/read/clicked)
- `OptInLink` — click-to-chat / QR entry points with public redirect

**Migration** `012_growth_layer.py`
- Extends `contacts` with consent/double opt-in columns
- Extends `campaigns` with delivery metric counters
- Creates 5 new tables

**Frontend (`apps/web/src/components/campaigns/`)**
- `CampaignsClient` — tabbed UI: Campaigns | Segments | Products | Drip
- Full i18n for uz + ru

### Compliance rules
- Broadcasts only send to contacts with `opt_in == True`
- Opt-out sets `opt_in = False` + records `opt_out_at` timestamp
- Delete is soft (contact record kept, marketing consent removed)
- Double opt-in flow columns present; enforcement is platform-side

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

## Decisions

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | ARQ over Celery | ARQ is async-native (Python asyncio), simpler for FastAPI + Redis stack | 2026-06-15 |
| 2 | pgvector over Qdrant | Fewer infra components; pgvector good enough for <1M embeddings; can migrate later | 2026-06-15 |
| 3 | bge-m3 embeddings | Multilingual (Uzbek + Russian), 1024-dim, runs locally, free | 2026-06-15 |
| 4 | Groq as primary LLM provider | Fast inference, generous free tier for MVP, OpenAI-compatible API | 2026-06-15 |
| 5 | pnpm workspaces | Fast, disk-efficient, workspace protocol for internal packages | 2026-06-15 |

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

## Phase Progress

- [x] Phase 0 — Repo skeleton & infra
- [x] Phase 1 — Backend core: DB, migration, auth, tenant
- [x] Phase 2 — Telegram adapter + webhook ingestion + queue
- [x] Phase 3 — RAG core (local embeddings)
- [x] Phase 4 — LLM fallback + model router + guardrails
- [x] Phase 5 — Outbound dispatcher, 24h window, rate-limit, handoff
- [ ] Phase 6 — Dashboard foundation (Next.js, auth, i18n)
- [ ] Phase 7 — Dashboard modules
- [ ] Phase 8 — Inbox (operator panel) + copilot + realtime
- [ ] Phase 9 — WhatsApp Cloud API adapter
- [ ] Phase 10 — Instagram + Facebook adapters
- [ ] Phase 11 — Agentic actions + flow builder
- [ ] Phase 12 — Growth layer: contacts, broadcast, drip
- [ ] Phase 13 — Analytics + observability + AI QA
- [ ] Phase 14 — Billing (CLICK / Payme) + plans
- [ ] Phase 15 — Landing page
- [ ] Phase 16 — Security, deploy, launch

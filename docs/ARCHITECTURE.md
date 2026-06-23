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

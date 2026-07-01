# JavobAI - Omnichannel AI Auto-responder SaaS

## PROJECT BRIEF
You are the lead engineer building "JavobAI" — an omnichannel AI auto-responder SaaS for Uzbekistan small/medium businesses. It connects Telegram, WhatsApp, Instagram and Facebook into ONE AI brain that:
  - instantly answers customer DMs and post comments in Uzbek and Russian,
  - grounds answers in the tenant's own knowledge base (RAG), not generic data,
  - escalates to a human operator with full context when unsure,
  - takes real actions (order status, booking) via agentic tool-calling,
  - runs marketing automations (broadcasts, drip, abandoned-cart) on opted-in users.

Differentiators vs ManyChat/Respond.io: full Uzbek+Russian UI & AI, local payments (CLICK/Payme) in UZS, Telegram as a first-class channel.

This is a multi-tenant B2B SaaS. Build it production-grade, incrementally, phase by phase. Do NOT scaffold everything at once.

## OPERATING PRINCIPLES
HOW YOU WORK:
1. Work in small, verifiable increments. After each meaningful unit, run it / test it, then make a git commit with a clear conventional-commit message (feat:, fix:, chore:, docs:).
2. Before writing code for a phase, restate the phase goal in 2-3 lines and list the files you will create/modify. Then build.
3. Never run destructive commands (rm -rf, DROP DATABASE, force-push) without stating it and asking first.
4. Keep secrets in .env (never commit). Maintain .env.example with every key.
5. Type everything: TypeScript strict mode on the frontend; Python type hints + Pydantic models on the backend. No `any`, no untyped dicts crossing boundaries.
6. Write a test for every non-trivial backend service (pytest) and key frontend logic (vitest). RAG, window-tracking, and dispatcher logic MUST be tested.
7. All user-facing strings go through i18n (uz + ru). No hardcoded UI copy.
8. Update /docs as you go: README per package + an ARCHITECTURE.md you keep current.
9. If a decision is ambiguous, pick the simplest reversible option, note it in ARCHITECTURE.md under "Decisions", and continue. Don't block.
10. Match the existing code style of the repo once it exists. Read before you write.

## ARCHITECTURE & MONOREPO
MONOREPO LAYOUT (pnpm workspace + uv/poetry for python):

javobai/
  apps/
    web/                 # Next.js 15 (App Router) — landing + dashboard
    api/                 # FastAPI core engine
    worker/              # ARQ workers (queue consumers, scheduled jobs)
  packages/
    shared-types/        # TS types shared between web and generated API client
    ui/                  # shared React components / design tokens
  infra/
    docker-compose.yml   # postgres+pgvector, redis, api, worker, web
    nginx/               # reverse proxy + SSL config for Lightsail
    Dockerfile.api  Dockerfile.web  Dockerfile.worker
  docs/
    ARCHITECTURE.md  API.md  DEPLOY.md
  .github/workflows/ci.yml

RUNTIME ARCHITECTURE:
  Inbound webhook (FastAPI) → verify signature → 200 OK in <1s → push to Redis
  queue → Worker normalizes to UnifiedMessage → CoreEngine decides
  (Rule → RAG → LLM → Action → Handoff) → Outbound dispatcher (per-platform
  adapter, window/rate aware) → reply.

CORE ENGINE DECISION PIPELINE (single source of truth, fully tested):
  1. Dedup (Redis SETNX on platform+message_id)
  2. Stop-words / business-hours / operator-active check
  3. Rule engine (keyword/trigger → fixed action)
  4. RAG: embed query (bge-m3, local) → pgvector cosine search over tenant FAQs
        score >= 0.85         -> return FAQ answer (no LLM)  [FREE PATH]
        0.65 <= score < 0.85  -> LLM answer grounded on top-k FAQ chunks (RAG)
        score < 0.65          -> either agentic action OR human handoff
  5. Agentic layer: if intent matches a registered Action (order_status, booking),
        call the tenant tool with function-calling and return result.
  6. Confidence gate: if low confidence or sensitive topic -> handoff queue.

UNIFIED MESSAGE (the contract every adapter produces/consumes):
  tenant_id, platform, channel_id, kind(dm|comment|comment_reply),
  external_user_id, conversation_id, text, media[], lang_hint, raw, received_at
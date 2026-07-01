# ARCHITECTURE

## MONOREPO LAYOUT (pnpm workspace + uv/poetry for python):

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

## RUNTIME ARCHITECTURE:
  Inbound webhook (FastAPI) → verify signature → 200 OK in <1s → push to Redis
  queue → Worker normalizes to UnifiedMessage → CoreEngine decides
  (Rule → RAG → LLM → Action → Handoff) → Outbound dispatcher (per-platform
  adapter, window/rate aware) → reply.

## CORE ENGINE DECISION PIPELINE (single source of truth, fully tested):
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

## UNIFIED MESSAGE (the contract every adapter produces/consumes):
  tenant_id, platform, channel_id, kind(dm|comment|comment_reply), 
  external_user_id, conversation_id, text, media[], lang_hint, raw, received_at

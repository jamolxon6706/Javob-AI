"""ARQ worker entry point."""
import logging

from arq.connections import RedisSettings

from worker.engine.core import CoreEngine
from worker.services.dispatcher import OutboundDispatcher
from worker.services.embeddings import EmbeddingService
from worker.services.llm import LLMService
from worker.services.ratelimit import RateLimiter
from worker.services.rag import RAGService
from worker.settings import worker_settings
from worker.tasks.embed import embed_faq_job, probe_embed_job
from worker.tasks.inbound import process_inbound_message

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:  # type: ignore[type-arg]
    import asyncpg  # type: ignore[import-untyped]
    import pgvector.asyncpg  # type: ignore[import-untyped]
    import redis.asyncio as redis_asyncio

    logger.info("JavobAI worker starting — loading embedding model (%s)...", worker_settings.embeddings_model)
    emb = EmbeddingService()
    emb.load(worker_settings.embeddings_model)
    ctx["embedding"] = emb
    logger.info("Embedding model loaded (dim=%d)", EmbeddingService.DIM)

    async def _init_conn(conn: object) -> None:
        await pgvector.asyncpg.register_vector(conn)  # type: ignore[arg-type]

    pool = await asyncpg.create_pool(
        worker_settings.asyncpg_url,
        min_size=2,
        max_size=10,
        init=_init_conn,
    )
    ctx["db_pool"] = pool
    logger.info("DB pool ready (%s)", worker_settings.asyncpg_url.split("@")[-1])

    ctx["rag"] = RAGService()
    ctx["llm"] = LLMService(
        groq_api_key=worker_settings.groq_api_key,
        groq_model=worker_settings.groq_model,
        groq_base_url=worker_settings.groq_base_url,
        google_api_key=worker_settings.google_api_key,
        gemini_model=worker_settings.gemini_fallback_model,
        timeout=worker_settings.llm_timeout_seconds,
    )
    ctx["core_engine"] = CoreEngine(emb, ctx["rag"], ctx["llm"])

    rate_limit_redis = redis_asyncio.from_url(worker_settings.redis_url)  # type: ignore[no-untyped-call]
    ctx["rate_limit_redis"] = rate_limit_redis
    ctx["dispatcher"] = OutboundDispatcher(
        RateLimiter(rate_limit_redis, limit=worker_settings.outbound_rate_limit_per_second),
        dlq_redis=rate_limit_redis,
        dlq_key=worker_settings.dlq_outbound_key,
        dlq_max_entries=worker_settings.dlq_max_entries,
        per_conversation_limit=worker_settings.outbound_rate_limit_per_conversation_per_minute,
        per_conversation_window_seconds=60,
    )
    logger.info("JavobAI worker started")


async def shutdown(ctx: dict) -> None:  # type: ignore[type-arg]
    pool = ctx.get("db_pool")
    if pool is not None:
        await pool.close()
    rate_limit_redis = ctx.get("rate_limit_redis")
    if rate_limit_redis is not None:
        await rate_limit_redis.aclose()
    logger.info("JavobAI worker shut down")


class WorkerConfig:
    functions = [process_inbound_message, embed_faq_job, probe_embed_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(worker_settings.redis_url)
    max_jobs = 10
    job_timeout = 60

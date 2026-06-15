"""ARQ worker entry point."""
import logging

from arq.connections import RedisSettings

from worker.engine.core import CoreEngine
from worker.services.embeddings import EmbeddingService
from worker.services.rag import RAGService
from worker.settings import worker_settings
from worker.tasks.embed import embed_faq_job, probe_embed_job
from worker.tasks.inbound import process_inbound_message

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:  # type: ignore[type-arg]
    import asyncpg  # type: ignore[import-untyped]
    import pgvector.asyncpg  # type: ignore[import-untyped]

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
    ctx["core_engine"] = CoreEngine(emb, ctx["rag"])
    logger.info("JavobAI worker started")


async def shutdown(ctx: dict) -> None:  # type: ignore[type-arg]
    pool = ctx.get("db_pool")
    if pool is not None:
        await pool.close()
    logger.info("JavobAI worker shut down")


class WorkerConfig:
    functions = [process_inbound_message, embed_faq_job, probe_embed_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(worker_settings.redis_url)
    max_jobs = 10
    job_timeout = 60

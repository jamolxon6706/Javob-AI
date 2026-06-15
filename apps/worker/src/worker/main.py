"""ARQ worker entry point."""
import logging

from arq.connections import RedisSettings

from worker.settings import worker_settings
from worker.tasks.inbound import process_inbound_message

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:  # type: ignore[type-arg]
    logger.info("JavobAI worker started")


async def shutdown(ctx: dict) -> None:  # type: ignore[type-arg]
    logger.info("JavobAI worker shutting down")


class WorkerConfig:
    functions = [process_inbound_message]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(worker_settings.redis_url)
    max_jobs = 10
    job_timeout = 60

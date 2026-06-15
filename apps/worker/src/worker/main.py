"""ARQ worker entry point. Add job functions here as the project grows."""
import logging

from arq import cron
from arq.connections import RedisSettings

from .settings import worker_settings

logger = logging.getLogger(__name__)


async def process_inbound_message(ctx: dict, payload: dict) -> None:  # type: ignore[type-arg]
    """Placeholder: normalize and route an inbound platform message."""
    logger.info("process_inbound_message received: %s", payload.get("platform"))


async def startup(ctx: dict) -> None:  # type: ignore[type-arg]
    logger.info("Worker started")


async def shutdown(ctx: dict) -> None:  # type: ignore[type-arg]
    logger.info("Worker shutting down")


class WorkerConfig:
    functions = [process_inbound_message]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(worker_settings.redis_url)
    max_jobs = 10
    job_timeout = 60

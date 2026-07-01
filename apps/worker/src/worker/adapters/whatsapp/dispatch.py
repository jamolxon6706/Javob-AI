"""Pushes validated, deduped WhatsApp webhook payloads onto the ARQ queue
for the worker to normalize and run through the CoreEngine. Kept separate
from the router so the router stays a thin HTTP layer.
"""
from __future__ import annotations

import logging

from redis.asyncio import Redis

from worker.adapters.whatsapp.schemas import WAWebhookPayload

logger = logging.getLogger(__name__)

QUEUE_FUNCTION_NAME = "process_whatsapp_webhook"


async def enqueue_inbound_webhook(
    redis: Redis, payload: WAWebhookPayload, *, allowed_message_ids: set[str]
) -> None:
    """Hands the raw (validated) payload to ARQ. We pass `allowed_message_ids`
    so the worker re-applies the same dedup filter defensively, in case this
    payload also contains already-seen ids mixed with new ones."""
    from arq import create_pool
    from arq.connections import RedisSettings

    # In production this pool is created once at worker/app startup and
    # injected via DI; created inline here for clarity of the enqueue call.
    pool = await create_pool(RedisSettings.from_dsn(redis.connection_pool.connection_kwargs.get("dsn", "redis://redis:6379/0")))
    try:
        await pool.enqueue_job(
            QUEUE_FUNCTION_NAME,
            payload.model_dump(mode="json"),
            list(allowed_message_ids),
        )
    finally:
        await pool.close()

    logger.info(
        "Enqueued WhatsApp webhook with %d new message(s)", len(allowed_message_ids)
    )

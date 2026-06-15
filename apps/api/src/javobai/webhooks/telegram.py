import logging

from arq import ArqRedis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.crypto import decrypt_dict
from javobai.db.models import Channel
from javobai.db.session import get_db
from javobai.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_DEDUP_TTL = 86400  # 24 hours


class _TelegramUpdate(BaseModel):
    update_id: int
    model_config = {"extra": "allow"}


async def _get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq  # type: ignore[no-any-return]


@router.post("/telegram/{channel_id}", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    channel_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    """
    Receives a Telegram Update, verifies the secret token, deduplicates,
    and enqueues a process_inbound_message job. Always returns 200 in <1s
    so Telegram doesn't retry unnecessarily.
    """
    # 1. Look up channel
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.is_active == True)  # noqa: E712
    )
    channel = result.scalar_one_or_none()
    if not channel or not channel.credentials_encrypted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown channel")

    # 2. Verify secret token
    try:
        creds = decrypt_dict(channel.credentials_encrypted)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad credentials")

    expected_secret = creds.get("webhook_secret", "")
    if not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    # 3. Parse update_id for dedup (read body as JSON)
    try:
        body = await request.json()
        update_id: int = body.get("update_id", 0)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # 4. Dedup — SETNX returns 1 if key was set (first time), 0 if already exists
    dedup_key = f"tg:dedup:{channel_id}:{update_id}"
    is_new = await redis.setnx(dedup_key, "1")
    if not is_new:
        logger.debug("Duplicate update %d for channel %s — skipping", update_id, channel_id)
        return {"ok": True}
    await redis.expire(dedup_key, _DEDUP_TTL)

    # 5. Enqueue
    arq: ArqRedis = await _get_arq(request)
    await arq.enqueue_job(
        "process_inbound_message",
        {
            "platform": "telegram",
            "tenant_id": channel.tenant_id,
            "channel_id": channel_id,
            "credentials_encrypted": channel.credentials_encrypted,
            "update": body,
        },
    )
    logger.info("Enqueued update %d for channel %s", update_id, channel_id)
    return {"ok": True}

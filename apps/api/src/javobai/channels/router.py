import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant
from javobai.config import settings
from javobai.crypto import decrypt_dict, encrypt_dict
from javobai.db.models import Channel
from javobai.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

TG_API = "https://api.telegram.org/bot{token}/{method}"


async def _tg_get_me(bot_token: str) -> dict:  # type: ignore[type-arg]
    url = TG_API.format(token=bot_token, method="getMe")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bot token — Telegram rejected it",
        )
    return resp.json()["result"]


async def _tg_set_webhook(bot_token: str, webhook_url: str, secret_token: str) -> None:
    url = TG_API.format(token=bot_token, method="setWebhook")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={
                "url": webhook_url,
                "secret_token": secret_token,
                "allowed_updates": ["message", "edited_message", "channel_post"],
            },
        )
    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"setWebhook failed: {data.get('description', 'unknown error')}",
        )


class TelegramOnboardIn(BaseModel):
    bot_token: str


class ChannelOut(BaseModel):
    id: str
    platform: str
    bot_username: str | None = None
    is_active: bool
    webhook_url: str


@router.post("/telegram", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def onboard_telegram(
    body: TelegramOnboardIn,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> ChannelOut:
    """
    Connect a Telegram bot to this tenant:
    1. Verify the token with getMe
    2. Create / reuse a Channel record
    3. Encrypt credentials and store
    4. Register webhook with Telegram
    """
    bot_info = await _tg_get_me(body.bot_token)
    bot_username: str = bot_info.get("username", "")
    bot_id: int = bot_info.get("id", 0)

    # Reuse existing channel if the same bot was previously connected
    result = await db.execute(
        select(Channel).where(
            Channel.tenant_id == tenant.id, Channel.platform == "telegram"
        )
    )
    channel = result.scalar_one_or_none()

    webhook_secret = secrets.token_hex(32)

    if channel is None:
        channel = Channel(tenant_id=tenant.id, platform="telegram")
        db.add(channel)
        await db.flush()  # get channel.id

    # Encrypt credentials
    creds = {
        "bot_token": body.bot_token,
        "bot_id": bot_id,
        "bot_username": bot_username,
        "webhook_secret": webhook_secret,
    }
    channel.credentials_encrypted = encrypt_dict(creds)
    channel.is_active = True
    await db.flush()

    # Register webhook with Telegram
    webhook_url = f"{settings.api_base_url}/webhooks/telegram/{channel.id}"
    await _tg_set_webhook(body.bot_token, webhook_url, webhook_secret)
    logger.info("Registered Telegram webhook for channel %s (bot: @%s)", channel.id, bot_username)

    return ChannelOut(
        id=channel.id,
        platform="telegram",
        bot_username=bot_username,
        is_active=True,
        webhook_url=webhook_url,
    )


@router.get("", response_model=list[ChannelOut])
async def list_channels(
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> list[ChannelOut]:
    result = await db.execute(
        select(Channel).where(Channel.tenant_id == tenant.id)
    )
    channels = result.scalars().all()
    out: list[ChannelOut] = []
    for ch in channels:
        username: str | None = None
        if ch.credentials_encrypted:
            try:
                creds = decrypt_dict(ch.credentials_encrypted)
                username = creds.get("bot_username")
            except Exception:
                pass
        out.append(ChannelOut(
            id=ch.id,
            platform=ch.platform,
            bot_username=username,
            is_active=ch.is_active,
            webhook_url=f"{settings.api_base_url}/webhooks/{ch.platform}/{ch.id}",
        ))
    return out

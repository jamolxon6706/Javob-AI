"""Tracks the WhatsApp 24-hour customer-service window per conversation.

Per Meta policy: a business may send free-form messages for 24h after the
customer's last inbound message. Outside that window, only approved
templates may be sent. Telegram has no such restriction (handled separately
in the generic dispatcher from Phase 5); this module is WhatsApp-specific
but follows the same Redis-key pattern.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from worker.settings import settings

_KEY_PREFIX = "wa:window"


def _key(channel_id: str, external_user_id: str) -> str:
    return f"{_KEY_PREFIX}:{channel_id}:{external_user_id}"


async def mark_inbound(
    redis: Redis, channel_id: str, external_user_id: str, *, now: datetime | None = None
) -> datetime:
    """Call this every time we receive an inbound message. Opens/extends
    the window and returns the new expiry timestamp (UTC)."""
    now = now or datetime.now(timezone.utc)
    # BUG FIX: settings.WA_FREE_WINDOW_HOURS does not exist on WorkerSettings
    # (AttributeError on every call) — the real, already-used-elsewhere
    # setting for this 24h window is message_window_hours.
    window_hours = settings.message_window_hours
    expires_at = now + timedelta(hours=window_hours)
    ttl_seconds = window_hours * 3600
    await redis.set(_key(channel_id, external_user_id), expires_at.isoformat(), ex=ttl_seconds)
    return expires_at


async def is_window_open(
    redis: Redis, channel_id: str, external_user_id: str, *, now: datetime | None = None
) -> bool:
    now = now or datetime.now(timezone.utc)
    raw = await redis.get(_key(channel_id, external_user_id))
    if raw is None:
        return False
    expires_at = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
    return now < expires_at


async def window_expires_at(
    redis: Redis, channel_id: str, external_user_id: str
) -> datetime | None:
    raw = await redis.get(_key(channel_id, external_user_id))
    if raw is None:
        return None
    return datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)

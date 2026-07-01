"""
ARQ worker task: process_meta_message

Consumes jobs pushed by the IG/FB webhook router.
Resolves channel credentials, normalizes the raw event into the canonical
UnifiedMessage, runs it through the shared CoreEngine, and sends the reply
via the IG/FB dispatcher.
"""
from __future__ import annotations

import logging
from typing import Any

from worker.adapters.meta.client import MetaGraphClient, MetaPermissionError
from worker.adapters.meta.facebook_dispatcher import FacebookDispatcher
from worker.adapters.meta.instagram_dispatcher import InstagramDispatcher
from worker.adapters.meta.normalizer import parse_comment_change, parse_messaging_event
from worker.crypto import decrypt_dict
from worker.engine.core import CoreEngine
from worker.services.conversation import (
    extend_window,
    get_or_create_contact,
    get_or_create_conversation,
    is_bot_active,
    save_message,
)
from worker.services.dispatcher import OutboundDispatcher
from worker.services.sentiment import detect_sentiment
from worker.settings import worker_settings

logger = logging.getLogger(__name__)


async def process_meta_message(
    ctx: dict[str, Any],
    um_data: dict[str, Any],
) -> None:
    """ARQ job entry point for IG and FB messages and comments."""
    redis = ctx["redis"]
    engine: CoreEngine = ctx["core_engine"]
    dispatcher: OutboundDispatcher = ctx["dispatcher"]
    pool = ctx["db_pool"]

    kind = um_data.get("kind", "dm")
    platform = um_data.get("platform", "instagram")
    channel_id = um_data.get("channel_id")
    page_id = um_data.get("page_id", "")
    raw = um_data.get("raw", {})

    async with pool.acquire() as lookup_conn:
        channel_row = await lookup_conn.fetchrow(
            "SELECT id, tenant_id, credentials FROM channels WHERE id = $1 AND is_active = true",
            channel_id,
        )

    if not channel_row:
        logger.error("Channel %s not found or inactive", channel_id)
        return

    tenant_id = str(channel_row["tenant_id"])

    try:
        creds = decrypt_dict(channel_row["credentials"])
    except Exception:
        creds = {"access_token": "", "page_id": ""}

    access_token: str = creds.get("access_token", "")
    resolved_page_id: str = creds.get("page_id", page_id)

    client = MetaGraphClient(access_token, worker_settings.meta_app_secret)

    if kind == "comment":
        um = parse_comment_change(raw, tenant_id, channel_id, platform, resolved_page_id)
    else:
        um = parse_messaging_event(raw, tenant_id, channel_id, platform, resolved_page_id)

    if um is None:
        logger.info("Meta %s event for channel %s produced no UnifiedMessage (echo/own-page)",
                    kind, channel_id)
        return

    async with pool.acquire() as conn:
        contact_id = await get_or_create_contact(
            conn, um.tenant_id, um.platform, um.external_user_id
        )
        conversation = await get_or_create_conversation(
            conn, um.tenant_id, um.channel_id, contact_id
        )
        await save_message(
            conn,
            conversation_id=conversation.id,
            tenant_id=um.tenant_id,
            direction="inbound",
            content=um.text,
            sentiment=detect_sentiment(um.text) if um.text.strip() else None,
        )
        await extend_window(conn, conversation.id, hours=worker_settings.message_window_hours)

        if not is_bot_active(conversation):
            logger.info(
                "tenant=%s conversation=%s status=%s — operator handling, bot skipped",
                um.tenant_id, conversation.id, conversation.status,
            )
            return

        reply = await engine.process(um, conn)

        if platform == "instagram":
            meta_dispatcher = InstagramDispatcher(client, redis)

            async def _send(text: str) -> None:
                await meta_dispatcher.send_reply(um, text, public_reply=False)
        else:
            fb_dispatcher = FacebookDispatcher(client, redis, resolved_page_id)

            async def _send(text: str) -> None:
                await fb_dispatcher.send_reply(um, text)

        try:
            await dispatcher.send(conn, um, reply, conversation, _send)
        except MetaPermissionError as e:
            logger.error("Meta permission error for channel %s: missing=%s", channel_id, e.missing)
        except Exception as e:
            logger.exception("Meta dispatch error: %s", e)
            raise

"""ARQ worker job consuming WhatsApp webhook payloads pushed by the API."""
from __future__ import annotations

import logging
from typing import Any

from worker.adapters.whatsapp.adapter import TemplateRequiredError, WhatsAppAdapter
from worker.adapters.whatsapp.normalizer import normalize_change
from worker.adapters.whatsapp.schemas import WAWebhookPayload
from worker.adapters.whatsapp.window import mark_inbound
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


async def process_whatsapp_webhook(
    ctx: dict[str, Any],
    raw_payload: dict[str, Any],
    allowed_message_ids: list[str],
) -> None:
    """ARQ job entry point for WhatsApp messages.

    Mirrors the Telegram path in tasks/inbound.py: persist the inbound
    message, extend the 24h window, run it through the shared CoreEngine,
    then send via OutboundDispatcher (which itself enforces the window,
    rate-limits, persistence, and handoff bookkeeping).
    """
    redis = ctx["redis"]
    engine: CoreEngine = ctx["core_engine"]
    dispatcher: OutboundDispatcher = ctx["dispatcher"]
    pool = ctx["db_pool"]
    payload = WAWebhookPayload.model_validate(raw_payload)
    allowed = set(allowed_message_ids)

    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages" or not change.value.messages:
                continue  # statuses (delivered/read) handled elsewhere
            phone_number_id = change.value.metadata.phone_number_id

            async with pool.acquire() as lookup_conn:
                channel_row = await lookup_conn.fetchrow(
                    """
                    SELECT id, tenant_id, credentials FROM channels
                    WHERE external_id = $1 AND platform = 'whatsapp' AND is_active = true
                    LIMIT 1
                    """,
                    phone_number_id,
                )

            if not channel_row:
                logger.error("No channel for phone_number_id=%s", phone_number_id)
                continue

            try:
                creds = decrypt_dict(channel_row["credentials"])
            except Exception:
                logger.error("Could not decrypt credentials for channel %s", channel_row["id"])
                continue

            access_token = creds.get("access_token", "")
            tenant_id = str(channel_row["tenant_id"])
            channel_id = str(channel_row["id"])

            unified_messages = await normalize_change(
                change.value.messages,
                tenant_id=tenant_id,
                channel_id=channel_id,
                allowed_message_ids=allowed,
            )

            adapter = WhatsAppAdapter(
                phone_number_id=phone_number_id,
                access_token=access_token,
                redis=redis,
            )

            for unified in unified_messages:
                await mark_inbound(redis, channel_id, unified.external_user_id)

                async with pool.acquire() as conn:
                    contact_id = await get_or_create_contact(
                        conn, unified.tenant_id, unified.platform, unified.external_user_id
                    )
                    conversation = await get_or_create_conversation(
                        conn, unified.tenant_id, unified.channel_id, contact_id
                    )
                    await save_message(
                        conn,
                        conversation_id=conversation.id,
                        tenant_id=unified.tenant_id,
                        direction="inbound",
                        content=unified.text,
                        sentiment=detect_sentiment(unified.text) if unified.text.strip() else None,
                    )
                    await extend_window(
                        conn, conversation.id, hours=worker_settings.message_window_hours
                    )

                    if not is_bot_active(conversation):
                        logger.info(
                            "tenant=%s conversation=%s status=%s — operator handling, bot skipped",
                            unified.tenant_id,
                            conversation.id,
                            conversation.status,
                        )
                        continue

                    reply = await engine.process(unified, conn)

                    async def _send(text: str, _adapter: WhatsAppAdapter = adapter,
                                     _channel_id: str = channel_id, _to: str = unified.external_user_id) -> None:
                        await _adapter.send_text(channel_id=_channel_id, to=_to, text=text)

                    try:
                        await dispatcher.send(conn, unified, reply, conversation, _send)
                    except TemplateRequiredError:
                        logger.warning(
                            "WA window closed before reply to %s", unified.external_user_id
                        )

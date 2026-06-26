import logging

from worker.adapters.telegram import send_message
from worker.crypto import decrypt_dict
from worker.engine.core import CoreEngine
from worker.engine.normalizer import normalize_telegram
from worker.engine.unified import UnifiedMessage
from worker.services.conversation import (
    extend_window,
    get_or_create_contact,
    get_or_create_conversation,
    is_bot_active,
    save_message,
)
from worker.services.dispatcher import OutboundDispatcher
from worker.settings import worker_settings

logger = logging.getLogger(__name__)


async def process_inbound_message(ctx: dict, payload: dict) -> None:  # type: ignore[type-arg]
    """
    Normalize an inbound platform message and route through the CoreEngine.
    Phase 3/4: RAG + LLM grounding. Phase 5: persistence, 24h window, handoff, dispatch.
    """
    platform: str = payload.get("platform", "")

    if platform == "telegram":
        msg = _handle_telegram(payload)
        if msg is None:
            logger.debug("Skipping non-message Telegram update")
            return
        await _process(ctx, msg)
    else:
        logger.warning("Unknown platform: %s", platform)


def _handle_telegram(payload: dict) -> UnifiedMessage | None:  # type: ignore[type-arg]
    return normalize_telegram(
        payload["update"],
        tenant_id=payload["tenant_id"],
        channel_id=payload["channel_id"],
        credentials_encrypted=payload["credentials_encrypted"],
    )


async def _process(ctx: dict, msg: UnifiedMessage) -> None:  # type: ignore[type-arg]
    if not msg.chat_id or not msg.credentials_encrypted:
        return

    try:
        creds = decrypt_dict(msg.credentials_encrypted)
        bot_token: str = creds["bot_token"]
    except (ValueError, KeyError) as exc:
        logger.error("Cannot decrypt credentials for channel %s: %s", msg.channel_id, exc)
        return

    engine: CoreEngine = ctx["core_engine"]
    dispatcher: OutboundDispatcher = ctx["dispatcher"]
    pool = ctx["db_pool"]

    async with pool.acquire() as conn:
        contact_id = await get_or_create_contact(
            conn, msg.tenant_id, msg.platform, msg.external_user_id
        )
        conversation = await get_or_create_conversation(
            conn, msg.tenant_id, msg.channel_id, contact_id
        )

        await save_message(
            conn,
            conversation_id=conversation.id,
            tenant_id=msg.tenant_id,
            direction="inbound",
            content=msg.text,
            platform_msg_id=msg.platform_msg_id,
        )
        await extend_window(conn, conversation.id, hours=worker_settings.message_window_hours)

        if not is_bot_active(conversation):
            logger.info(
                "tenant=%s conversation=%s status=%s — operator handling, bot skipped",
                msg.tenant_id,
                conversation.id,
                conversation.status,
            )
            return

        reply = await engine.process(msg, conn)

        async def _send(text: str) -> None:
            await send_message(bot_token, msg.chat_id, text)  # type: ignore[arg-type]

        result = await dispatcher.send(conn, msg, reply, conversation, _send)

    logger.info(
        "tenant=%s channel=%s conv=%s source=%s reason=%s handoff=%s",
        msg.tenant_id, msg.channel_id, conversation.id, reply.source,
        result.reason, result.handoff,
    )

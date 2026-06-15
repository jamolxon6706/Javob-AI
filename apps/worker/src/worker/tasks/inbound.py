import logging

from worker.adapters.telegram import send_message
from worker.crypto import decrypt_dict
from worker.engine.normalizer import normalize_telegram
from worker.engine.unified import UnifiedMessage

logger = logging.getLogger(__name__)


async def process_inbound_message(ctx: dict, payload: dict) -> None:  # type: ignore[type-arg]
    """
    Normalize an inbound platform message and route it through the CoreEngine.

    Phase 2: echo mode — replies with the same text.
    Phase 3+: RAG → LLM → Action → Handoff.
    """
    platform: str = payload.get("platform", "")

    if platform == "telegram":
        msg = _handle_telegram(payload)
        if msg is None:
            logger.debug("Skipping non-message Telegram update")
            return
        await _echo(msg)
    else:
        logger.warning("Unknown platform: %s", platform)


def _handle_telegram(payload: dict) -> UnifiedMessage | None:  # type: ignore[type-arg]
    return normalize_telegram(
        payload["update"],
        tenant_id=payload["tenant_id"],
        channel_id=payload["channel_id"],
        credentials_encrypted=payload["credentials_encrypted"],
    )


async def _echo(msg: UnifiedMessage) -> None:
    """Temporary Phase-2 echo. Replace with CoreEngine in Phase 3."""
    if not msg.text or not msg.chat_id or not msg.credentials_encrypted:
        return
    try:
        creds = decrypt_dict(msg.credentials_encrypted)
        bot_token: str = creds["bot_token"]
    except (ValueError, KeyError) as exc:
        logger.error("Cannot decrypt credentials for channel %s: %s", msg.channel_id, exc)
        return

    reply = f"Echo: {msg.text}"
    await send_message(bot_token, msg.chat_id, reply)
    logger.info("Echoed message to chat %s on channel %s", msg.chat_id, msg.channel_id)

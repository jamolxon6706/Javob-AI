"""Converts a parsed WAWebhookPayload into one or more UnifiedMessage
objects, which is the only thing the CoreEngine ever consumes.

NOTE: this produces `worker.engine.unified.UnifiedMessage` — the single
canonical contract shared by every adapter (Telegram, Meta, WhatsApp) and
consumed by CoreEngine / OutboundDispatcher. It does NOT use the separate
`UnifiedMessage` defined in `worker.adapters.whatsapp.schemas`, which is a
different, incompatible Pydantic model kept around only for typing the raw
WhatsApp media attachment shape.
"""
from __future__ import annotations

import logging
from uuid import UUID

from worker.adapters.whatsapp.schemas import (
    WAMediaBody,
    WAMessage,
    WAWebhookPayload,
)
from worker.adapters.whatsapp.stt import transcribe_audio
from worker.adapters.whatsapp.media import download_media
from worker.engine.unified import MediaItem, UnifiedMessage

logger = logging.getLogger(__name__)

_MEDIA_TYPES = {"image", "audio", "video", "document", "sticker"}


async def normalize_payload(
    payload: WAWebhookPayload,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    allowed_message_ids: set[str] | None = None,
) -> list[UnifiedMessage]:
    """A single webhook delivery can contain multiple entries/changes/messages
    (Meta batches them). We flatten everything into UnifiedMessages and let
    the worker process one job per message.

    `allowed_message_ids`, when provided, restricts processing to message IDs
    the webhook layer hasn't already seen (defense-in-depth dedup — the
    webhook itself filters before enqueueing, this is a second check in case
    a payload is replayed directly into the worker).

    NOTE: callers that resolve one phone_number_id at a time (the worker task
    iterates entries/changes itself to look up the right channel) should use
    `normalize_change` instead, to avoid re-normalizing messages belonging to
    other phone numbers in the same batched payload.
    """
    out: list[UnifiedMessage] = []

    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue  # statuses (delivered/read) handled elsewhere
            value = change.value
            for wa_msg in value.messages:
                if allowed_message_ids is not None and wa_msg.id not in allowed_message_ids:
                    continue
                unified = await _normalize_message(
                    wa_msg, tenant_id=tenant_id, channel_id=channel_id
                )
                if unified is not None:
                    out.append(unified)

    return out


async def normalize_change(
    change_value_messages: list[WAMessage],
    *,
    tenant_id: UUID,
    channel_id: UUID,
    allowed_message_ids: set[str] | None = None,
) -> list[UnifiedMessage]:
    """Normalize just the messages from a single WAChange.value.messages list
    (i.e. messages for one phone_number_id), avoiding cross-contamination
    when a webhook batch contains entries for multiple WhatsApp numbers.
    """
    out: list[UnifiedMessage] = []
    for wa_msg in change_value_messages:
        if allowed_message_ids is not None and wa_msg.id not in allowed_message_ids:
            continue
        unified = await _normalize_message(wa_msg, tenant_id=tenant_id, channel_id=channel_id)
        if unified is not None:
            out.append(unified)
    return out


async def _normalize_message(
    wa_msg: WAMessage, *, tenant_id: UUID, channel_id: UUID
) -> UnifiedMessage | None:
    text = ""
    media: list[MediaItem] = []

    if wa_msg.type == "text" and wa_msg.text is not None:
        text = wa_msg.text.body

    elif wa_msg.type in _MEDIA_TYPES:
        media_body: WAMediaBody | None = getattr(wa_msg, wa_msg.type, None)
        if media_body is None:
            logger.warning("Unsupported/empty media body for type=%s", wa_msg.type)
            return None

        # Download so downstream steps (RAG/LLM, "Add to FAQ", audit) have a
        # durable reference instead of Meta's short-lived media URL.
        local_path = await download_media(media_body.id)

        if wa_msg.type == "audio":
            transcript = await transcribe_audio(local_path)
            text = transcript or ""
        elif media_body.caption:
            text = media_body.caption

        media_type = wa_msg.type if wa_msg.type in ("image", "video", "audio", "document") else "document"
        media.append(
            MediaItem(
                type=media_type,  # type: ignore[arg-type]
                url=local_path or "",
                mime_type=media_body.mime_type,
            )
        )

    else:
        logger.info("Ignoring unsupported WhatsApp message type=%s", wa_msg.type)
        return None

    external_user_id = wa_msg.from_
    return UnifiedMessage(
        tenant_id=str(tenant_id),
        platform="whatsapp",
        channel_id=str(channel_id),
        kind="dm",
        external_user_id=external_user_id,
        conversation_id=f"{channel_id}:{external_user_id}",
        text=text,
        media=media,
        raw=wa_msg.model_dump(by_alias=True),
        external_message_id=wa_msg.id,
    )

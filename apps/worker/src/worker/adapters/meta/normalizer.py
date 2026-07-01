"""
Meta webhook normalizer.
Parses raw Instagram / Facebook Messenger webhook payloads
into the shared UnifiedMessage schema.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from worker.engine.unified import MediaItem, UnifiedMessage

logger = logging.getLogger(__name__)


def parse_meta_webhook(
    raw: dict[str, Any],
    tenant_id: UUID,
    channel_id: UUID,
    platform: str,  # "instagram" | "facebook"
) -> list[UnifiedMessage]:
    """
    Parse one Meta webhook payload (may contain multiple entries/changes).
    Returns a list of UnifiedMessage (usually 1, but batched sends can have more).
    """
    messages: list[UnifiedMessage] = []

    for entry in raw.get("entry", []):
        page_id = entry.get("id", "")

        # ── Instagram: messaging (DM) ──────────────────────────────────────
        for msg_event in entry.get("messaging", []):
            um = parse_messaging_event(
                msg_event, tenant_id, channel_id, platform, page_id
            )
            if um:
                messages.append(um)

        # ── Instagram / Facebook: feed changes (comments) ──────────────────
        for change in entry.get("changes", []):
            if change.get("field") in ("comments", "feed"):
                um = parse_comment_change(
                    change.get("value", {}),
                    tenant_id,
                    channel_id,
                    platform,
                    page_id,
                )
                if um:
                    messages.append(um)

    return messages


def parse_messaging_event(
    event: dict[str, Any],
    tenant_id: UUID,
    channel_id: UUID,
    platform: str,
    page_id: str,
) -> UnifiedMessage | None:
    sender_id = event.get("sender", {}).get("id", "")
    recipient_id = event.get("recipient", {}).get("id", "")
    timestamp_ms = event.get("timestamp", 0)

    # Skip echoes (messages sent by the page itself)
    if sender_id == page_id:
        return None

    msg = event.get("message", {})
    if not msg or msg.get("is_echo"):
        return None

    text = msg.get("text", "")
    media: list[MediaItem] = []

    # Attachments (images, audio, video, files)
    for att in msg.get("attachments", []):
        att_type = att.get("type", "")
        url = att.get("payload", {}).get("url", "")
        if url:
            media.append(MediaItem(type=att_type, url=url))

    mid = msg.get("mid", f"{platform}_{sender_id}_{timestamp_ms}")

    return UnifiedMessage(
        tenant_id=tenant_id,
        platform=platform,
        channel_id=channel_id,
        kind="dm",
        external_user_id=sender_id,
        conversation_id=f"{platform}:{page_id}:{sender_id}",
        text=text,
        media=media,
        lang_hint=None,
        raw=event,
        received_at=datetime.utcfromtimestamp(timestamp_ms / 1000),
        external_message_id=mid,
    )


def parse_comment_change(
    value: dict[str, Any],
    tenant_id: UUID,
    channel_id: UUID,
    platform: str,
    page_id: str,
) -> UnifiedMessage | None:
    item = value.get("item", "")
    verb = value.get("verb", "")

    # Only handle new comments, not edits/removes
    if verb != "add" or item not in ("comment", "post"):
        return None

    comment_id = value.get("comment_id") or value.get("id", "")
    from_data = value.get("from", {})
    sender_id = from_data.get("id", "")
    sender_name = from_data.get("name", "")

    # Skip own-page comments
    if sender_id == page_id:
        return None

    text = value.get("message", "")
    post_id = value.get("post_id", "")
    created_time = value.get("created_time", 0)

    return UnifiedMessage(
        tenant_id=tenant_id,
        platform=platform,
        channel_id=channel_id,
        kind="comment",
        external_user_id=sender_id,
        conversation_id=f"{platform}:{page_id}:comment:{comment_id}",
        text=text,
        media=[],
        lang_hint=None,
        raw=value,
        received_at=datetime.utcfromtimestamp(created_time)
        if created_time
        else datetime.utcnow(),
        external_message_id=comment_id,
        # Store extra context for the dispatcher
        meta_extra={
            "comment_id": comment_id,
            "post_id": post_id,
            "sender_name": sender_name,
            "page_id": page_id,
        },
    )

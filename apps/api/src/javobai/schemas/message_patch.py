"""
UnifiedMessage schema — the single contract every platform adapter produces.

PATCH for Faza 10: adds `meta_extra` (IG/FB comment metadata) and
`external_message_id` (for dedup).

Merge these fields into your existing app/schemas/message.py.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    type: str           # "image" | "audio" | "video" | "file"
    url: str
    mime_type: Optional[str] = None


class UnifiedMessage(BaseModel):
    # Core identity
    tenant_id: UUID
    platform: str                   # "telegram" | "whatsapp" | "instagram" | "facebook"
    channel_id: UUID
    kind: str                       # "dm" | "comment" | "comment_reply"

    # Routing
    external_user_id: str
    conversation_id: str            # stable ID for threading (e.g. "ig:page:user")

    # Content
    text: str = ""
    media: list[MediaItem] = Field(default_factory=list)
    lang_hint: Optional[str] = None

    # Dedup
    external_message_id: Optional[str] = None   # ← NEW in Faza 10

    # Meta-specific extras (comment_id, post_id, page_id, sender_name)
    meta_extra: Optional[dict[str, Any]] = None  # ← NEW in Faza 10

    # Raw payload (kept for debugging / audit)
    raw: Optional[Any] = None
    received_at: datetime = Field(default_factory=datetime.utcnow)

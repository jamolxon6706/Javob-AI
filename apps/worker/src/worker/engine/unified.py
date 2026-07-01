from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

Platform = Literal["telegram", "whatsapp", "instagram", "facebook"]
MessageKind = Literal["dm", "comment", "comment_reply"]


class MediaItem(BaseModel):
    type: Literal["image", "video", "audio", "document"]
    url: str
    mime_type: str | None = None


class UnifiedMessage(BaseModel):
    tenant_id: str
    platform: Platform
    channel_id: str
    kind: MessageKind
    external_user_id: str
    conversation_id: str
    text: str
    media: list[MediaItem] = []
    lang_hint: str | None = None
    raw: dict = {}  # type: ignore[type-arg]
    received_at: datetime = None  # type: ignore[assignment]
    external_message_id: str = ""

    def model_post_init(self, __context):
        if self.received_at is None:
            object.__setattr__(self, "received_at", datetime.now(timezone.utc))

    # Routing helpers (not part of the contract, stripped before storage)
    credentials_encrypted: str | None = None
    chat_id: str | None = None
    platform_msg_id: str | None = None
    # Extra per-platform routing context (e.g. IG/FB comment_id, post_id) that
    # outbound dispatchers need but isn't part of the core cross-platform
    # contract. Without this declared as a real field, Pydantic's default
    # extra="ignore" behavior silently drops it, breaking IG comment replies.
    meta_extra: dict | None = None  # type: ignore[type-arg]

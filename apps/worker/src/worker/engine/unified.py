from datetime import datetime
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
    received_at: datetime

    # Routing helpers (not part of the contract, stripped before storage)
    credentials_encrypted: str | None = None
    chat_id: str | None = None
    platform_msg_id: str | None = None

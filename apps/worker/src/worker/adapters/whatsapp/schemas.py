"""Pydantic models for WhatsApp Cloud API webhook payloads and the
internal UnifiedMessage contract this adapter produces.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# NOTE: this file used to also define a second, incompatible UnifiedMessage /
# MediaAttachment pair. Those classes were never imported or used anywhere in
# the codebase (normalizer.py has always produced worker.engine.unified.
# UnifiedMessage, the one canonical contract shared by every adapter and
# consumed by CoreEngine / OutboundDispatcher). They were removed to avoid the
# risk of code accidentally importing the wrong UnifiedMessage in future.
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Raw WhatsApp Cloud API webhook payload (subset we actually parse).
# Full schema: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks
# --------------------------------------------------------------------------- #
class WAProfile(BaseModel):
    name: str | None = None


class WAContact(BaseModel):
    profile: WAProfile | None = None
    wa_id: str


class WATextBody(BaseModel):
    body: str


class WAMediaBody(BaseModel):
    id: str
    mime_type: str | None = None
    caption: str | None = None
    sha256: str | None = None


class WAMessage(BaseModel):
    id: str
    from_: str = Field(alias="from")
    timestamp: str
    type: str
    text: WATextBody | None = None
    image: WAMediaBody | None = None
    audio: WAMediaBody | None = None
    video: WAMediaBody | None = None
    document: WAMediaBody | None = None
    sticker: WAMediaBody | None = None

    @field_validator("timestamp")
    @classmethod
    def _must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("WhatsApp timestamp must be a unix epoch string")
        return v

    model_config = {"populate_by_name": True}


class WAStatus(BaseModel):
    """Delivery/read receipts for messages we sent (template/outbound)."""

    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str
    recipient_id: str


class WAMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WAValue(BaseModel):
    messaging_product: Literal["whatsapp"]
    metadata: WAMetadata
    contacts: list[WAContact] = Field(default_factory=list)
    messages: list[WAMessage] = Field(default_factory=list)
    statuses: list[WAStatus] = Field(default_factory=list)


class WAChange(BaseModel):
    value: WAValue
    field: str


class WAEntry(BaseModel):
    id: str
    changes: list[WAChange]


class WAWebhookPayload(BaseModel):
    object: Literal["whatsapp_business_account"]
    entry: list[WAEntry]

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ContactOut(BaseModel):
    id: str
    platform: str
    external_user_id: str
    name: str | None
    phone: str | None


class LastMessageOut(BaseModel):
    content: str | None
    direction: str
    source: str | None
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    channel_id: str
    platform: str
    # open | waiting_operator | resolved | bot_silenced
    status: str
    contact: ContactOut
    last_message: LastMessageOut | None
    assigned_operator_id: str | None
    bot_silenced_until: datetime | None
    window_expires_at: datetime | None
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    # inbound | outbound
    direction: str
    content: str | None
    # rule | faq | llm | action | operator
    source: str | None
    rag_score: float | None
    created_at: datetime


class ReplyIn(BaseModel):
    text: str


class CopilotOut(BaseModel):
    summary: str
    suggestion: str


class AddToFaqIn(BaseModel):
    question: str
    answer: str | None = None


class AddToFaqOut(BaseModel):
    id: str
    question: str
    answer: str

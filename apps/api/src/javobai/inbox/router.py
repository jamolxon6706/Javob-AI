"""
Phase 8 — operator inbox (ARCHITECTURE.md Phase 8).

Realtime transport (websocket + presence) lives in javobai.ws; this module is
the plain REST surface the dashboard's inbox screen reads and writes:

  GET  /inbox                                    — conversation list, handoff queue pinned
  GET  /inbox/{id}/messages                       — full history for one conversation
  POST /inbox/{id}/reply                          — operator sends a message; silences bot 30 min
  POST /inbox/{id}/resolve                        — mark a conversation resolved
  POST /inbox/{id}/assign                         — operator claims a conversation
  POST /inbox/{id}/copilot                        — AI-suggested reply + one-line summary
  POST /inbox/{id}/messages/{message_id}/add-to-faq — turn a good answer into a reusable FAQ
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant, CurrentUser
from javobai.config import settings
from javobai.crypto import decrypt_dict
from javobai.db.models import FAQ, Channel, Contact, Conversation, Message, Tenant
from javobai.db.session import get_db
from javobai.events import publish_event
from javobai.inbox.schemas import (
    AddToFaqIn,
    AddToFaqOut,
    ContactOut,
    ConversationOut,
    CopilotOut,
    LastMessageOut,
    MessageOut,
    ReplyIn,
)
from javobai.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inbox", tags=["inbox"])

# Phase 8 acceptance: "when an operator sends, the bot goes silent in that
# conversation for 30 min".
OPERATOR_SILENCE_MINUTES = 30

TG_API = "https://api.telegram.org/bot{token}/{method}"

_COPILOT_SYSTEM_PROMPT = (
    "You are an agent copilot for a customer-support team at a small business "
    "in Uzbekistan. You receive the recent conversation history and the "
    "tenant's FAQ knowledge base. Reply with STRICT JSON only — no markdown "
    "fences, no extra text — in exactly this shape: "
    '{"summary": "one short sentence describing what the customer needs, in '
    'the customer\'s own language (Uzbek or Russian)", "suggestion": "a short, '
    "ready-to-send reply drafted in the customer's language, grounded only in "
    'the FAQ context where it is relevant; if nothing in the FAQs covers the '
    "question, write a polite holding reply instead of inventing facts\"}"
)


async def _send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    url = TG_API.format(token=bot_token, method="sendMessage")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": chat_id, "text": text})
    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram send failed: {data.get('description', 'unknown error')}",
        )


def _conv_out(
    conv: Conversation,
    platform: str,
    contact: Contact | None,
    last_content: str | None,
    last_direction: str | None,
    last_source: str | None,
    last_created_at: datetime | None,
) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        channel_id=conv.channel_id,
        platform=platform,
        status=conv.status,
        contact=ContactOut(
            id=contact.id if contact else "",
            platform=contact.platform if contact else platform,
            external_user_id=contact.external_user_id if contact else "",
            name=contact.name if contact else None,
            phone=contact.phone if contact else None,
        ),
        last_message=(
            LastMessageOut(
                content=last_content,
                direction=last_direction or "",
                source=last_source,
                created_at=last_created_at,
            )
            if last_created_at is not None
            else None
        ),
        assigned_operator_id=conv.assigned_operator_id,
        bot_silenced_until=conv.bot_silenced_until,
        window_expires_at=conv.window_expires_at,
        updated_at=conv.updated_at,
    )


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"),
    channel_id: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list[ConversationOut]:
    """
    All channels in one list, most recently updated first — with the handoff
    queue (status == waiting_operator) pinned to the top regardless of
    recency, per Phase 8's acceptance criteria.
    """
    last_msg_rn = select(
        Message.conversation_id.label("conversation_id"),
        Message.content.label("content"),
        Message.direction.label("direction"),
        Message.source.label("source"),
        Message.created_at.label("created_at"),
        func.row_number()
        .over(partition_by=Message.conversation_id, order_by=Message.created_at.desc())
        .label("rn"),
    ).where(Message.tenant_id == tenant.id).subquery("lm")
    last_msg = select(last_msg_rn).where(last_msg_rn.c.rn == 1).subquery("last_msg")

    query = (
        select(
            Conversation,
            Channel.platform,
            Contact,
            last_msg.c.content,
            last_msg.c.direction,
            last_msg.c.source,
            last_msg.c.created_at,
        )
        .join(Channel, Channel.id == Conversation.channel_id)
        .outerjoin(Contact, Contact.id == Conversation.contact_id)
        .outerjoin(last_msg, last_msg.c.conversation_id == Conversation.id)
        .where(Conversation.tenant_id == tenant.id)
    )
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        query = query.where(Conversation.status.in_(statuses))
    if channel_id:
        query = query.where(Conversation.channel_id == channel_id)

    query = query.order_by(
        case((Conversation.status == "waiting_operator", 0), else_=1),
        Conversation.updated_at.desc(),
    ).limit(limit)

    rows = (await db.execute(query)).all()
    return [_conv_out(*row) for row in rows]


async def _get_conversation_or_404(
    conversation_id: str, tenant: Tenant, db: AsyncSession
) -> tuple[Conversation, Channel, Contact | None]:
    result = await db.execute(
        select(Conversation, Channel, Contact)
        .join(Channel, Channel.id == Conversation.channel_id)
        .outerjoin(Contact, Contact.id == Conversation.contact_id)
        .where(Conversation.id == conversation_id, Conversation.tenant_id == tenant.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conv, channel, contact = row
    return conv, channel, contact


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, le=200),
) -> list[MessageOut]:
    await _get_conversation_or_404(conversation_id, tenant, db)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.tenant_id == tenant.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    msgs = list(result.scalars().all())
    msgs.reverse()  # oldest first for a natural chat-reading order
    return [
        MessageOut(
            id=m.id,
            conversation_id=m.conversation_id,
            direction=m.direction,
            content=m.content,
            source=m.source,
            rag_score=m.rag_score,
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.post(
    "/{conversation_id}/reply", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
async def reply(
    conversation_id: str,
    body: ReplyIn,
    tenant: CurrentTenant,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> MessageOut:
    if not body.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply text is empty")

    conv, channel, contact = await _get_conversation_or_404(conversation_id, tenant, db)

    if channel.platform == "telegram":
        if not channel.credentials_encrypted or not contact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Channel not connected"
            )
        creds = decrypt_dict(channel.credentials_encrypted)
        await _send_telegram(creds["bot_token"], contact.external_user_id, body.text)
    else:
        # Phase 9/10 will add WhatsApp/IG/FB sends. Telegram-only for now,
        # matching the rest of the Phase 0-8 codebase.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operator replies are not yet supported on {channel.platform}",
        )

    message = Message(
        conversation_id=conv.id,
        tenant_id=tenant.id,
        direction="outbound",
        content=body.text,
        source="operator",
    )
    db.add(message)

    conv.status = "open"
    conv.assigned_operator_id = user.id
    conv.bot_silenced_until = datetime.now(UTC) + timedelta(minutes=OPERATOR_SILENCE_MINUTES)
    await db.flush()

    await publish_event(
        redis,
        tenant.id,
        {
            "type": "message.created",
            "conversation_id": conv.id,
            "message": {
                "id": message.id,
                "direction": "outbound",
                "content": body.text,
                "source": "operator",
                "created_at": message.created_at.isoformat(),
            },
        },
    )
    await publish_event(
        redis,
        tenant.id,
        {
            "type": "conversation.updated",
            "conversation_id": conv.id,
            "status": conv.status,
            "bot_silenced_until": conv.bot_silenced_until.isoformat(),
        },
    )

    return MessageOut(
        id=message.id,
        conversation_id=conv.id,
        direction="outbound",
        content=body.text,
        source="operator",
        rag_score=None,
        created_at=message.created_at,
    )


@router.post("/{conversation_id}/resolve", response_model=ConversationOut)
async def resolve_conversation(
    conversation_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ConversationOut:
    conv, channel, contact = await _get_conversation_or_404(conversation_id, tenant, db)
    conv.status = "resolved"
    await db.flush()
    await db.refresh(conv)
    await publish_event(
        redis,
        tenant.id,
        {"type": "conversation.updated", "conversation_id": conv.id, "status": conv.status},
    )
    return _conv_out(conv, channel.platform, contact, None, None, None, None)


@router.post("/{conversation_id}/assign", response_model=ConversationOut)
async def assign_conversation(
    conversation_id: str,
    tenant: CurrentTenant,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ConversationOut:
    """An operator claims a handoff — clears the queue badge for everyone else."""
    conv, channel, contact = await _get_conversation_or_404(conversation_id, tenant, db)
    conv.assigned_operator_id = user.id
    if conv.status == "waiting_operator":
        conv.status = "bot_silenced"
    await db.flush()
    await db.refresh(conv)
    await publish_event(
        redis,
        tenant.id,
        {
            "type": "conversation.updated",
            "conversation_id": conv.id,
            "status": conv.status,
            "assigned_operator_id": user.id,
        },
    )
    return _conv_out(conv, channel.platform, contact, None, None, None, None)


@router.post("/{conversation_id}/copilot", response_model=CopilotOut)
async def copilot(
    conversation_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CopilotOut:
    """
    AI-suggested reply + one-line summary for the operator's current conversation.

    Decision (docs/ARCHITECTURE.md §Decisions): unlike apps/worker's RAG path,
    this does NOT run a vector search — it feeds the model the tenant's FAQs
    directly (capped at 15) instead of loading the bge-m3 embedding model into
    the API process. Simplest reversible option for a feature that only needs
    to be "good enough", not exact; revisit if tenants grow large FAQ bases.
    """
    conv, _channel, _contact = await _get_conversation_or_404(conversation_id, tenant, db)

    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI copilot is not configured for this environment",
        )

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.tenant_id == tenant.id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    msgs = list(msg_result.scalars().all())
    msgs.reverse()
    if not msgs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation has no messages yet"
        )

    faq_result = await db.execute(
        select(FAQ).where(FAQ.tenant_id == tenant.id, FAQ.is_active == True).limit(15)  # noqa: E712
    )
    faqs = faq_result.scalars().all()

    history = "\n".join(
        f"{'Customer' if m.direction == 'inbound' else 'Agent'}: {m.content}"
        for m in msgs
        if m.content
    )
    faq_context = "\n".join(f"Q: {f.question}\nA: {f.answer}" for f in faqs) or "(no FAQs yet)"
    user_content = f"FAQ knowledge base:\n{faq_context}\n\nConversation so far:\n{history}"

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_model,
                    "messages": [
                        {"role": "system", "content": _COPILOT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.error("Copilot LLM call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Copilot is temporarily unavailable"
        ) from exc

    return CopilotOut(
        summary=str(parsed.get("summary", "")), suggestion=str(parsed.get("suggestion", ""))
    )


@router.post(
    "/{conversation_id}/messages/{message_id}/add-to-faq",
    response_model=AddToFaqOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_faq(
    conversation_id: str,
    message_id: str,
    body: AddToFaqIn,
    request: Request,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AddToFaqOut:
    """Turn a good answer in the inbox into a reusable FAQ (Phase 8 'Add to FAQ')."""
    await _get_conversation_or_404(conversation_id, tenant, db)
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.tenant_id == tenant.id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    answer = body.answer or message.content or ""
    if not answer.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer is empty")

    faq = FAQ(tenant_id=tenant.id, question=body.question, answer=answer)
    db.add(faq)
    await db.flush()
    await request.app.state.arq.enqueue_job("embed_faq_job", faq.id)
    return AddToFaqOut(id=faq.id, question=faq.question, answer=faq.answer)

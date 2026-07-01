"""Tests for the Phase 8 operator inbox API (list, history, reply, resolve, assign,
copilot, add-to-faq) and the websocket auth ticket endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.crypto import encrypt_dict
from javobai.db.models import Channel, Contact, Conversation, FAQ, Message


async def _seed_conversation(
    db: AsyncSession,
    tenant_id: str,
    *,
    platform: str = "telegram",
    status: str = "open",
    external_user_id: str = "555000111",
    updated_at: datetime | None = None,
) -> tuple[Channel, Contact, Conversation]:
    channel = Channel(
        tenant_id=tenant_id,
        platform=platform,
        credentials_encrypted=encrypt_dict({"bot_token": "123:TEST"}) if platform == "telegram" else None,
        is_active=True,
    )
    db.add(channel)
    await db.flush()

    contact = Contact(
        tenant_id=tenant_id, external_user_id=external_user_id, platform=platform, name="Ali Valiyev"
    )
    db.add(contact)
    await db.flush()

    conversation = Conversation(
        tenant_id=tenant_id, channel_id=channel.id, contact_id=contact.id, status=status
    )
    db.add(conversation)
    await db.flush()
    if updated_at is not None:
        conversation.updated_at = updated_at
        await db.flush()

    return channel, contact, conversation


async def _seed_message(
    db: AsyncSession,
    conversation: Conversation,
    tenant_id: str,
    *,
    direction: str,
    content: str,
    source: str | None = None,
    created_at: datetime | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id, tenant_id=tenant_id, direction=direction, content=content, source=source
    )
    db.add(message)
    await db.flush()
    if created_at is not None:
        # SQLite's CURRENT_TIMESTAMP only has 1s resolution, so messages seeded
        # back-to-back in a test can tie — give tests an explicit override.
        message.created_at = created_at
        await db.flush()
    return message


async def _tenant_id(client: AsyncClient) -> str:
    r = await client.get("/tenants/me")
    assert r.status_code == 200
    return r.json()["id"]  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_list_conversations_empty(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/inbox")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_conversations_pins_waiting_operator(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    now = datetime.now(timezone.utc)

    _, _, older_waiting = await _seed_conversation(
        db, tenant_id, status="waiting_operator", external_user_id="111", updated_at=now - timedelta(hours=2)
    )
    _, _, newer_open = await _seed_conversation(
        db, tenant_id, status="open", external_user_id="222", updated_at=now
    )
    await _seed_message(db, older_waiting, tenant_id, direction="inbound", content="Buyurtmam qayerda?")
    await _seed_message(db, newer_open, tenant_id, direction="inbound", content="Salom")

    r = await auth_client.get("/inbox")
    assert r.status_code == 200
    conversations = r.json()
    ids = [c["id"] for c in conversations]
    # waiting_operator pinned to the top despite being older — checked relatively,
    # since other tests sharing this in-memory DB may add unrelated conversations.
    assert ids.index(older_waiting.id) < ids.index(newer_open.id)
    pinned = next(c for c in conversations if c["id"] == older_waiting.id)
    assert pinned["status"] == "waiting_operator"
    assert pinned["last_message"]["content"] == "Buyurtmam qayerda?"


@pytest.mark.asyncio
async def test_list_conversations_filters_by_status(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, resolved_conv = await _seed_conversation(db, tenant_id, status="resolved", external_user_id="333")
    _, _, open_conv = await _seed_conversation(db, tenant_id, status="open", external_user_id="444")

    r = await auth_client.get("/inbox", params={"status": "open"})
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert open_conv.id in ids
    assert resolved_conv.id not in ids


@pytest.mark.asyncio
async def test_list_messages_returns_chronological_history(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id)
    now = datetime.now(timezone.utc)
    await _seed_message(db, conv, tenant_id, direction="inbound", content="1-savol", created_at=now)
    await _seed_message(
        db, conv, tenant_id, direction="outbound", content="1-javob", source="faq", created_at=now + timedelta(seconds=1)
    )

    r = await auth_client.get(f"/inbox/{conv.id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert [m["content"] for m in msgs] == ["1-savol", "1-javob"]
    assert msgs[1]["source"] == "faq"


@pytest.mark.asyncio
async def test_messages_unknown_conversation_404(auth_client: AsyncClient) -> None:
    r = await auth_client.get("/inbox/does-not-exist/messages")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reply_sends_via_telegram_and_silences_bot(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, contact, conv = await _seed_conversation(db, tenant_id, status="waiting_operator")

    with patch("javobai.inbox.router._send_telegram", new=AsyncMock()) as send_mock:
        r = await auth_client.post(f"/inbox/{conv.id}/reply", json={"text": "Bugun yetkazib beramiz"})

    assert r.status_code == 201
    body = r.json()
    assert body["direction"] == "outbound"
    assert body["source"] == "operator"
    send_mock.assert_awaited_once()
    args = send_mock.await_args.args
    assert args[1] == contact.external_user_id
    assert args[2] == "Bugun yetkazib beramiz"

    await db.refresh(conv)
    assert conv.status == "open"
    assert conv.bot_silenced_until is not None
    silenced_until = conv.bot_silenced_until
    if silenced_until.tzinfo is None:  # SQLite (test DB) drops tz info; Postgres keeps it
        silenced_until = silenced_until.replace(tzinfo=timezone.utc)
    assert silenced_until > datetime.now(timezone.utc) + timedelta(minutes=25)


@pytest.mark.asyncio
async def test_reply_empty_text_rejected(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id)
    r = await auth_client.post(f"/inbox/{conv.id}/reply", json={"text": "   "})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reply_unsupported_platform_returns_400(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id, platform="whatsapp")
    r = await auth_client.post(f"/inbox/{conv.id}/reply", json={"text": "Salom"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_resolve_conversation(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id, status="waiting_operator")
    r = await auth_client.post(f"/inbox/{conv.id}/resolve")
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_assign_conversation_claims_handoff(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id, status="waiting_operator")
    r = await auth_client.post(f"/inbox/{conv.id}/assign")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "bot_silenced"
    assert body["assigned_operator_id"]


@pytest.mark.asyncio
async def test_copilot_returns_503_when_groq_not_configured(auth_client: AsyncClient, db: AsyncSession) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id)
    await _seed_message(db, conv, tenant_id, direction="inbound", content="Salom")
    r = await auth_client.post(f"/inbox/{conv.id}/copilot")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_add_to_faq_creates_faq_and_enqueues_embed(
    auth_client: AsyncClient, db: AsyncSession, mock_arq: AsyncMock
) -> None:
    tenant_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_id)
    message = await _seed_message(
        db, conv, tenant_id, direction="outbound", content="Ish vaqtimiz 9:00-18:00", source="operator"
    )

    r = await auth_client.post(
        f"/inbox/{conv.id}/messages/{message.id}/add-to-faq",
        json={"question": "Ish vaqtingiz qanday?"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["question"] == "Ish vaqtingiz qanday?"
    assert body["answer"] == "Ish vaqtimiz 9:00-18:00"

    mock_arq.enqueue_job.assert_awaited_once()
    call_args = mock_arq.enqueue_job.call_args
    assert call_args[0][0] == "embed_faq_job"
    assert call_args[0][1] == body["id"]

    faq_result = await db.get(FAQ, body["id"])
    assert faq_result is not None


@pytest.mark.asyncio
async def test_inbox_tenant_isolation(
    auth_client: AsyncClient, second_auth_client: AsyncClient, db: AsyncSession
) -> None:
    tenant_a_id = await _tenant_id(auth_client)
    _, _, conv = await _seed_conversation(db, tenant_a_id, status="waiting_operator")

    list_resp = await second_auth_client.get("/inbox")
    assert list_resp.json() == []

    msgs_resp = await second_auth_client.get(f"/inbox/{conv.id}/messages")
    assert msgs_resp.status_code == 404

    resolve_resp = await second_auth_client.post(f"/inbox/{conv.id}/resolve")
    assert resolve_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_ws_ticket(auth_client: AsyncClient, mock_redis: object) -> None:
    r = await auth_client.post("/auth/ws-ticket")
    assert r.status_code == 200
    ticket = r.json()["ticket"]
    assert ticket

    stored = await mock_redis.get(f"ws_ticket:{ticket}")  # type: ignore[attr-defined]
    assert stored is not None

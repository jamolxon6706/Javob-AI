"""Tests for the Phase 13 analytics + AI eval harness API.

Seeded conversations/messages use a *fresh, isolated* tenant per test
(via `_new_tenant`) rather than the shared `auth_client`/`second_auth_client`
fixtures — those two tenants are reused across the whole test session (see
conftest.py's module-level SQLite engine), and other files (test_inbox.py,
test_rules.py) assert an *empty* state on them. Seeding data there would
make this file's alphabetically-early collection order silently break
those tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.crypto import encrypt_dict
from javobai.db.models import Channel, Contact, Conversation, EvalCase, FAQ, Message


async def _new_tenant(client: AsyncClient) -> AsyncClient:
    """Register a brand-new tenant on `client` and return it, authenticated."""
    phone = f"+998{uuid.uuid4().int % 900_000_000 + 100_000_000:09d}"
    r = await client.post("/auth/request-otp", json={"phone": phone})
    assert r.status_code == 200, r.text
    otp = r.json()["otp"]
    r = await client.post("/auth/verify", json={"phone": phone, "otp": otp})
    assert r.status_code == 200, r.text
    client.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return client


async def _second_client_same_app(client: AsyncClient) -> AsyncClient:
    """A second AsyncClient hitting the same ASGI app/dependency overrides as `client`."""
    from javobai.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _tenant_id(client: AsyncClient) -> str:
    r = await client.get("/tenants/me")
    assert r.status_code == 200
    return r.json()["id"]  # type: ignore[no-any-return]


async def _seed_conversation(
    db: AsyncSession,
    tenant_id: str,
    *,
    platform: str = "telegram",
    external_user_id: str = "555000111",
    handoff_reason: str | None = None,
) -> Conversation:
    channel = Channel(
        tenant_id=tenant_id,
        platform=platform,
        credentials_encrypted=encrypt_dict({"bot_token": "123:TEST"}),
        is_active=True,
    )
    db.add(channel)
    await db.flush()

    contact = Contact(tenant_id=tenant_id, external_user_id=external_user_id, platform=platform)
    db.add(contact)
    await db.flush()

    conversation = Conversation(
        tenant_id=tenant_id, channel_id=channel.id, contact_id=contact.id, status="open",
        handoff_reason=handoff_reason,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _seed_message(
    db: AsyncSession,
    conversation: Conversation,
    tenant_id: str,
    *,
    direction: str,
    content: str | None,
    source: str | None = None,
    sentiment: str | None = None,
    latency_ms: int | None = None,
    created_at: datetime | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        direction=direction,
        content=content,
        source=source,
        sentiment=sentiment,
        latency_ms=latency_ms,
    )
    db.add(message)
    await db.flush()
    if created_at is not None:
        message.created_at = created_at
        await db.flush()
    return message


@pytest.mark.asyncio
async def test_overview_empty_defaults(client: AsyncClient) -> None:
    c = await _new_tenant(client)
    r = await c.get("/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_messages"] == 0
    assert body["reply_rate"] == 0.0
    assert body["handoff_rate"] == 0.0
    assert body["avg_response_time_ms"] is None


@pytest.mark.asyncio
async def test_overview_computes_reply_and_handoff_rate(client: AsyncClient, db: AsyncSession) -> None:
    c = await _new_tenant(client)
    tenant_id = await _tenant_id(c)
    conv = await _seed_conversation(db, tenant_id, handoff_reason="low_confidence")
    now = datetime.now(timezone.utc)

    await _seed_message(db, conv, tenant_id, direction="inbound", content="Salom", created_at=now)
    await _seed_message(
        db, conv, tenant_id, direction="outbound", content="Assalomu alaykum!",
        source="faq", latency_ms=120, created_at=now,
    )
    await _seed_message(db, conv, tenant_id, direction="inbound", content="Yordam kerak", created_at=now)
    await _seed_message(
        db, conv, tenant_id, direction="outbound", content="Operator sizga tez orada yordam beradi.",
        source="handoff", latency_ms=80, created_at=now,
    )

    r = await c.get("/analytics/overview", params={"days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["outbound_messages"] == 2
    assert body["inbound_messages"] == 2
    assert body["by_source"]["faq"] == 1
    assert body["by_source"]["handoff"] == 1
    assert body["reply_rate"] == 0.5
    assert body["handoff_rate"] == 0.5
    assert body["avg_response_time_ms"] == 100.0
    assert body["by_handoff_reason"].get("low_confidence") == 1


@pytest.mark.asyncio
async def test_overview_counts_angry_sentiment(client: AsyncClient, db: AsyncSession) -> None:
    c = await _new_tenant(client)
    tenant_id = await _tenant_id(c)
    conv = await _seed_conversation(db, tenant_id)
    await _seed_message(db, conv, tenant_id, direction="inbound", content="ужасно!!!", sentiment="angry")
    await _seed_message(db, conv, tenant_id, direction="inbound", content="Salom", sentiment="neutral")

    r = await c.get("/analytics/overview")
    assert r.status_code == 200
    assert r.json()["angry_count"] == 1


@pytest.mark.asyncio
async def test_overview_scoped_to_tenant(client: AsyncClient, db: AsyncSession) -> None:
    c1 = await _new_tenant(client)
    c2 = await _new_tenant(await _second_client_same_app(client))
    tenant_a = await _tenant_id(c1)
    conv_a = await _seed_conversation(db, tenant_a, external_user_id="a-user")
    await _seed_message(db, conv_a, tenant_a, direction="inbound", content="A savoli")

    r = await c1.get("/analytics/overview")
    assert r.json()["inbound_messages"] == 1

    r2 = await c2.get("/analytics/overview")
    assert r2.json()["inbound_messages"] == 0
    await c2.aclose()


@pytest.mark.asyncio
async def test_timeseries_buckets_by_day(client: AsyncClient, db: AsyncSession) -> None:
    c = await _new_tenant(client)
    tenant_id = await _tenant_id(c)
    conv = await _seed_conversation(db, tenant_id)
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)

    await _seed_message(db, conv, tenant_id, direction="inbound", content="bugun", created_at=today)
    await _seed_message(db, conv, tenant_id, direction="inbound", content="kecha", created_at=yesterday)

    r = await c.get("/analytics/timeseries", params={"days": 7})
    assert r.status_code == 200
    points = r.json()["points"]
    dates = {p["date"] for p in points}
    assert today.date().isoformat() in dates
    assert yesterday.date().isoformat() in dates


@pytest.mark.asyncio
async def test_top_questions_and_faq_gaps(client: AsyncClient, db: AsyncSession) -> None:
    c = await _new_tenant(client)
    tenant_id = await _tenant_id(c)
    normal_conv = await _seed_conversation(db, tenant_id, external_user_id="u1")
    handoff_conv = await _seed_conversation(db, tenant_id, external_user_id="u2")

    await _seed_message(db, normal_conv, tenant_id, direction="inbound", content="Ish vaqtingiz qachon?")
    await _seed_message(db, normal_conv, tenant_id, direction="inbound", content="Ish vaqtingiz qachon?")
    await _seed_message(db, handoff_conv, tenant_id, direction="inbound", content="Pulimni qaytaring")
    await _seed_message(
        db, handoff_conv, tenant_id, direction="outbound",
        content="Operator sizga tez orada yordam beradi.", source="handoff",
    )

    r = await c.get("/analytics/top-questions", params={"days": 30})
    assert r.status_code == 200
    body = r.json()
    top_texts = [q["text"] for q in body["top_questions"]]
    assert "Ish vaqtingiz qachon?" in top_texts
    gap_texts = [q["text"] for q in body["faq_gaps"]]
    assert "Pulimni qaytaring" in gap_texts
    assert "Ish vaqtingiz qachon?" not in gap_texts


@pytest.mark.asyncio
async def test_eval_case_crud(client: AsyncClient) -> None:
    c = await _new_tenant(client)
    r = await c.post(
        "/analytics/eval-cases",
        json={"question": "Yetkazib berish qancha turadi?", "expected_answer_contains": "bepul"},
    )
    assert r.status_code == 201
    case = r.json()
    case_id = case["id"]

    r = await c.get("/analytics/eval-cases")
    assert r.status_code == 200
    assert any(c_["id"] == case_id for c_ in r.json())

    r = await c.patch(f"/analytics/eval-cases/{case_id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    r = await c.delete(f"/analytics/eval-cases/{case_id}")
    assert r.status_code == 204

    r = await c.get("/analytics/eval-cases")
    assert all(c_["id"] != case_id for c_ in r.json())


@pytest.mark.asyncio
async def test_eval_case_requires_an_expectation(client: AsyncClient) -> None:
    c = await _new_tenant(client)
    r = await c.post("/analytics/eval-cases", json={"question": "Salom qanday?"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_trigger_eval_run_requires_active_cases(client: AsyncClient) -> None:
    c = await _new_tenant(client)
    r = await c.post("/analytics/eval-cases/run")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_trigger_eval_run_enqueues_job(client: AsyncClient, db: AsyncSession) -> None:
    c = await _new_tenant(client)
    tenant_id = await _tenant_id(c)
    faq = FAQ(tenant_id=tenant_id, question="Yetkazib berish narxi?", answer="Bepul")
    db.add(faq)
    await db.flush()
    case = EvalCase(tenant_id=tenant_id, question="Yetkazib berish qancha?", expected_faq_id=faq.id)
    db.add(case)
    await db.flush()

    r = await c.post("/analytics/eval-cases/run")
    assert r.status_code == 200
    assert r.json()["queued"] is True


@pytest.mark.asyncio
async def test_quality_empty_when_no_runs(client: AsyncClient) -> None:
    c = await _new_tenant(client)
    r = await c.get("/analytics/quality")
    assert r.status_code == 200
    body = r.json()
    assert body["latest_run"] is None
    assert body["history"] == []

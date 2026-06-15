"""
Tests for the Telegram webhook endpoint:
- Invalid secret → 403
- Missing secret → 403
- Valid request → 200, job enqueued once
- Duplicate update_id → 200, job NOT enqueued again (dedup)
- Unknown channel → 403
"""
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.crypto import encrypt_dict
from javobai.db.models import Channel, Tenant


async def _seed_channel(db: AsyncSession) -> tuple[Channel, str]:
    """Create a tenant + Telegram channel with a known webhook secret."""
    tenant = Tenant(name="Test Co", slug=f"test-co-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()

    secret = "test_webhook_secret_32chars_xxxxx"
    creds = {
        "bot_token": "123:TEST_TOKEN",
        "bot_id": 123,
        "bot_username": "testbot",
        "webhook_secret": secret,
    }
    channel = Channel(
        tenant_id=tenant.id,
        platform="telegram",
        credentials_encrypted=encrypt_dict(creds),
        is_active=True,
    )
    db.add(channel)
    await db.flush()
    return channel, secret


def _make_update(update_id: int = 100001) -> dict:  # type: ignore[type-arg]
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "from": {"id": 999, "first_name": "Ali", "is_bot": False, "language_code": "uz"},
            "chat": {"id": 999, "type": "private"},
            "date": 1718000000,
            "text": "Salom!",
        },
    }


@pytest.mark.asyncio
async def test_webhook_invalid_secret(client: AsyncClient, db: AsyncSession) -> None:
    channel, _ = await _seed_channel(db)

    r = await client.post(
        f"/webhooks/telegram/{channel.id}",
        json=_make_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_missing_secret(client: AsyncClient, db: AsyncSession) -> None:
    channel, _ = await _seed_channel(db)

    r = await client.post(f"/webhooks/telegram/{channel.id}", json=_make_update())
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_valid_enqueues_job(
    client: AsyncClient, db: AsyncSession, mock_arq: AsyncMock
) -> None:
    channel, secret = await _seed_channel(db)

    r = await client.post(
        f"/webhooks/telegram/{channel.id}",
        json=_make_update(update_id=200001),
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    mock_arq.enqueue_job.assert_awaited_once()
    call_args = mock_arq.enqueue_job.call_args
    assert call_args[0][0] == "process_inbound_message"
    payload = call_args[0][1]
    assert payload["platform"] == "telegram"
    assert payload["tenant_id"] == channel.tenant_id
    assert payload["channel_id"] == channel.id


@pytest.mark.asyncio
async def test_webhook_dedup_same_update_id(
    client: AsyncClient, db: AsyncSession, mock_arq: AsyncMock
) -> None:
    channel, secret = await _seed_channel(db)
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret}
    update = _make_update(update_id=300001)

    r1 = await client.post(f"/webhooks/telegram/{channel.id}", json=update, headers=headers)
    r2 = await client.post(f"/webhooks/telegram/{channel.id}", json=update, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    # enqueue_job called exactly once (dedup blocked second request)
    assert mock_arq.enqueue_job.await_count == 1


@pytest.mark.asyncio
async def test_webhook_unknown_channel(client: AsyncClient) -> None:
    r = await client.post(
        "/webhooks/telegram/nonexistent-channel-id",
        json=_make_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "any"},
    )
    assert r.status_code == 403

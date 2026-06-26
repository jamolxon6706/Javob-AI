"""
Conversation repository unit tests (mocked asyncpg connection, no real DB).
Covers find-or-create contact/conversation, message persistence, the 24h
window refresh, the handoff flag, and the operator-active guardrail.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker.services.conversation import (
    ConversationState,
    extend_window,
    get_or_create_contact,
    get_or_create_conversation,
    is_bot_active,
    mark_handoff,
    save_message,
)


@pytest.mark.asyncio
async def test_get_or_create_contact_returns_id() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={"id": "contact-1"})
    contact_id = await get_or_create_contact(conn, "tenant-1", "telegram", "user-1")
    assert contact_id == "contact-1"
    conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_conversation_returns_state() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "conv-1",
            "status": "open",
            "window_expires_at": None,
            "bot_silenced_until": None,
        }
    )
    state = await get_or_create_conversation(conn, "tenant-1", "channel-1", "contact-1")
    assert state == ConversationState(
        id="conv-1", status="open", window_expires_at=None, bot_silenced_until=None
    )


@pytest.mark.asyncio
async def test_save_message_executes_insert() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()
    await save_message(
        conn, conversation_id="conv-1", tenant_id="tenant-1", direction="inbound", content="hi"
    )
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_extend_window_executes_update() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()
    await extend_window(conn, "conv-1", hours=24)
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_handoff_executes_update() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock()
    await mark_handoff(conn, "conv-1")
    conn.execute.assert_awaited_once()


def test_is_bot_active_open_status() -> None:
    state = ConversationState(id="c1", status="open", window_expires_at=None, bot_silenced_until=None)
    assert is_bot_active(state) is True


def test_is_bot_active_waiting_operator() -> None:
    state = ConversationState(
        id="c1", status="waiting_operator", window_expires_at=None, bot_silenced_until=None
    )
    assert is_bot_active(state) is False


def test_is_bot_active_bot_silenced_status() -> None:
    state = ConversationState(
        id="c1", status="bot_silenced", window_expires_at=None, bot_silenced_until=None
    )
    assert is_bot_active(state) is False


def test_is_bot_active_silenced_until_future() -> None:
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    state = ConversationState(id="c1", status="open", window_expires_at=None, bot_silenced_until=future)
    assert is_bot_active(state) is False


def test_is_bot_active_silenced_until_past() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    state = ConversationState(id="c1", status="open", window_expires_at=None, bot_silenced_until=past)
    assert is_bot_active(state) is True

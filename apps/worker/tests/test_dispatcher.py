"""
OutboundDispatcher unit tests (Phase 5):

  - 24h window enforcement (Telegram exempt, Meta enforced)
  - per-channel blocking rate-limit
  - per-conversation anti-runaway rate-limit (try_acquire)
  - DLQ push on per-conversation RL and permanent send failure
  - handoff event publish on window_expired / low_confidence / rate_limited
  - empty reply is a no-op

All collaborators are mocked (Redis, asyncpg conn, send_fn, mark_handoff,
save_message) — no real network or DB.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.engine.core import EngineReply
from worker.engine.unified import UnifiedMessage
from worker.services.conversation import ConversationState
from worker.services.dispatcher import OutboundDispatcher
from worker.services.ratelimit import RateLimiter


def _msg(platform: str = "telegram", conversation_id: str = "tg:channel-1:user-1") -> UnifiedMessage:
    return UnifiedMessage(
        tenant_id="tenant-1",
        platform=platform,  # type: ignore[arg-type]
        channel_id="channel-1",
        kind="dm",
        external_user_id="user-1",
        conversation_id=conversation_id,
        text="hi",
        received_at=datetime.now(tz=timezone.utc),
    )


def _conversation(window_expires_at: datetime | None = None) -> ConversationState:
    return ConversationState(
        id="conv-1", status="open", window_expires_at=window_expires_at, bot_silenced_until=None
    )


def _make_dispatcher(*, per_conv_limit: int = 3, dlq_redis: object | None = None) -> OutboundDispatcher:
    """Real RateLimiter mocks so per-channel acquire is also tracked."""
    channel_limiter = MagicMock(spec=RateLimiter)
    channel_limiter.acquire = AsyncMock()
    # share a fake Redis between channel & per-conversation limiters.
    # Use MagicMock (not AsyncMock) so int comparison with _limit works on incr() return.
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    channel_limiter._redis = redis
    return OutboundDispatcher(
        channel_limiter,
        dlq_redis=dlq_redis if dlq_redis is not None else redis,
        dlq_key="dlq:test",
        dlq_max_entries=100,
        per_conversation_limit=per_conv_limit,
        per_conversation_window_seconds=60,
    )


# ──────────────────────── existing paths ────────────────────────


@pytest.mark.asyncio
async def test_send_telegram_ignores_window_check() -> None:
    """Telegram has no 24h window restriction — always sendable."""
    dispatcher = _make_dispatcher()
    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)

    with patch("worker.services.dispatcher.save_message", AsyncMock()) as save_msg:
        result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    assert result.reason == "sent"
    assert result.handoff is None
    send_fn.assert_awaited_once_with("answer")
    save_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_empty_reply_skips() -> None:
    dispatcher = _make_dispatcher()
    send_fn = AsyncMock()
    reply = EngineReply(text="", source=None, rag_score=None)

    result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)
    assert result.reason == "empty_reply"
    assert result.handoff is None
    send_fn.assert_not_called()


@pytest.mark.asyncio
async def test_send_whatsapp_window_expired_marks_handoff_and_skips_send() -> None:
    dispatcher = _make_dispatcher()
    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)
    expired = datetime.now(timezone.utc) - timedelta(hours=1)

    with patch("worker.services.dispatcher.mark_handoff", AsyncMock()) as handoff:
        result = await dispatcher.send(
            object(), _msg(platform="whatsapp"), reply, _conversation(window_expires_at=expired), send_fn
        )

    assert result.reason == "window_expired"
    assert result.handoff == "out_of_window"
    send_fn.assert_not_called()
    handoff.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_whatsapp_within_window_sends() -> None:
    dispatcher = _make_dispatcher()
    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    with patch("worker.services.dispatcher.save_message", AsyncMock()):
        result = await dispatcher.send(
            object(), _msg(platform="whatsapp"), reply, _conversation(window_expires_at=future), send_fn
        )

    assert result.reason == "sent"
    send_fn.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_handoff_reply_marks_conversation_and_emits_event() -> None:
    dlq_redis = AsyncMock()
    dispatcher = _make_dispatcher(dlq_redis=dlq_redis)
    send_fn = AsyncMock()
    reply = EngineReply(text="Operator sizga tez orada yordam beradi.", source="handoff", rag_score=None)

    with (
        patch("worker.services.dispatcher.save_message", AsyncMock()),
        patch("worker.services.dispatcher.mark_handoff", AsyncMock()) as handoff,
    ):
        result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    assert result.reason == "sent"
    assert result.handoff == "low_confidence"
    handoff.assert_awaited_once()
    # handoff event published exactly once on per-tenant channel
    dlq_redis.publish.assert_awaited_once()
    channel, payload = dlq_redis.publish.await_args.args
    assert channel == "handoff:tenant-1"
    body = json.loads(payload)
    assert body["reason"] == "low_confidence"
    assert body["conversation_id"] == "conv-1"


@pytest.mark.asyncio
async def test_send_calls_channel_rate_limiter_with_channel_id() -> None:
    channel_limiter = MagicMock(spec=RateLimiter)
    channel_limiter.acquire = AsyncMock()
    # _redis is read by the inner RateLimiter instance for incr/expire/ttl.
    # Use a plain MagicMock with async methods so attr access on it stays int-typed.
    inner_redis = MagicMock()
    inner_redis.incr = AsyncMock(return_value=1)
    inner_redis.expire = AsyncMock()
    channel_limiter._redis = inner_redis
    dispatcher = OutboundDispatcher(
        channel_limiter, dlq_redis=None, per_conversation_limit=10
    )
    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)

    with patch("worker.services.dispatcher.save_message", AsyncMock()):
        await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    channel_limiter.acquire.assert_awaited_once_with("channel-1")


# ──────────────────────── Phase 5 additions ────────────────────────


@pytest.mark.asyncio
async def test_send_per_conversation_rate_limit_skips_and_dlqs() -> None:
    """A 4th reply inside the per-conversation window is refused without blocking."""
    dlq_redis = AsyncMock()
    dispatcher = _make_dispatcher(per_conv_limit=3, dlq_redis=dlq_redis)
    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)

    # Force the per-conversation limiter to refuse this attempt.
    dispatcher._per_conv_limiter.try_acquire = AsyncMock(return_value=False)  # type: ignore[method-assign]

    result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    assert result.reason == "rate_limited"
    assert result.handoff == "rate_limited"
    send_fn.assert_not_called()
    # DLQ received exactly one entry with the right reason.
    dlq_redis.lpush.assert_awaited_once()
    dlq_redis.ltrim.assert_awaited_once()
    key, payload_json = dlq_redis.lpush.await_args.args
    assert key == "dlq:test"
    assert json.loads(payload_json)["reason"] == "rate_limited"
    # Handoff event published
    dlq_redis.publish.assert_awaited_once()
    assert dlq_redis.publish.await_args.args[0] == "handoff:tenant-1"


@pytest.mark.asyncio
async def test_send_send_failure_dlqs_and_does_not_mark_handoff() -> None:
    """A permanent send failure should land in DLQ, not in the handoff queue."""
    dlq_redis = AsyncMock()
    dispatcher = _make_dispatcher(dlq_redis=dlq_redis)
    send_fn = AsyncMock(side_effect=RuntimeError("telegram 400: chat not found"))
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)

    with patch("worker.services.dispatcher.save_message", AsyncMock()) as save_msg:
        result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    assert result.reason == "send_failed"
    assert result.handoff is None  # a send failure is not a handoff
    save_msg.assert_not_called()
    dlq_redis.lpush.assert_awaited_once()
    assert json.loads(dlq_redis.lpush.await_args.args[1])["reason"] == "send_failed"


@pytest.mark.asyncio
async def test_send_no_dlq_when_redis_not_configured() -> None:
    """dlq_redis=None should skip DLQ silently — useful for dry-run / unit tests."""
    channel_limiter = MagicMock(spec=RateLimiter)
    channel_limiter.acquire = AsyncMock()
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    channel_limiter._redis = redis
    dispatcher = OutboundDispatcher(
        channel_limiter, dlq_redis=None, per_conversation_limit=10
    )
    dispatcher._per_conv_limiter.try_acquire = AsyncMock(return_value=False)  # type: ignore[method-assign]

    send_fn = AsyncMock()
    reply = EngineReply(text="answer", source="faq", rag_score=0.9)
    result = await dispatcher.send(object(), _msg(), reply, _conversation(), send_fn)

    assert result.reason == "rate_limited"
    assert result.handoff == "rate_limited"  # reason still set for telemetry
    send_fn.assert_not_called()
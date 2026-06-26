"""
Phase 5 events tests: DLQ push + handoff pub/sub publisher.
All Redis calls are mocked — no real network.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from worker.services.events import handoff_channel, publish_handoff, push_to_dlq


@pytest.mark.asyncio
async def test_push_to_dlq_lpush_then_ltrim() -> None:
    redis = AsyncMock()
    await push_to_dlq(redis, "dlq:test", {"reason": "rate_limited"}, max_entries=50)

    redis.lpush.assert_awaited_once()
    redis.ltrim.assert_awaited_once_with("dlq:test", 0, 49)
    key, payload = redis.lpush.await_args.args
    assert key == "dlq:test"
    body = json.loads(payload)
    assert body["reason"] == "rate_limited"
    assert "queued_at" in body  # stamped server-side


@pytest.mark.asyncio
async def test_push_to_dlq_swallows_errors() -> None:
    """A broken Redis must not crash the inbound pipeline."""
    redis = AsyncMock()
    redis.lpush.side_effect = RuntimeError("redis down")
    # Should not raise
    await push_to_dlq(redis, "dlq:test", {"reason": "send_failed"}, max_entries=50)


def test_handoff_channel_format() -> None:
    assert handoff_channel("tenant-1") == "handoff:tenant-1"
    assert handoff_channel("abc", prefix="ops") == "ops:abc"


@pytest.mark.asyncio
async def test_publish_handoff_uses_per_tenant_channel_and_event_id() -> None:
    redis = AsyncMock()
    await publish_handoff(
        redis,
        "tenant-1",
        {
            "conversation_id": "conv-1",
            "channel_id": "channel-1",
            "external_user_id": "user-1",
            "platform": "whatsapp",
            "reason": "out_of_window",
            "rag_score": 0.42,
        },
    )

    redis.publish.assert_awaited_once()
    channel, payload = redis.publish.await_args.args
    assert channel == "handoff:tenant-1"
    body = json.loads(payload)
    assert body["reason"] == "out_of_window"
    assert body["conversation_id"] == "conv-1"
    assert body["rag_score"] == 0.42
    assert "event_id" in body and "timestamp" in body


@pytest.mark.asyncio
async def test_publish_handoff_swallows_errors() -> None:
    redis = AsyncMock()
    redis.publish.side_effect = RuntimeError("redis down")
    # Best-effort: must not raise
    await publish_handoff(redis, "tenant-1", {"conversation_id": "c", "reason": "rate_limited"})
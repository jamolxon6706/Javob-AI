"""
Phase 5 outbound-event side effects (ARCHITECTURE.md §Phase 5):

  - DLQ push: when a platform adapter exhausts its retry budget, we record the
    failure in a Redis list so an operator (or a future drain task) can inspect
    it. The list is bounded by `dlq_max_entries` to avoid unbounded growth.

  - Handoff event publish: when the engine + dispatcher decide a conversation
    needs a human, we publish a JSON event on a per-tenant Redis pub/sub channel.
    Phase 8 (operator dashboard) will subscribe; for now the publisher is wired
    and unit-tested with a fake Redis.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def push_to_dlq(redis: object, key: str, payload: dict[str, Any], max_entries: int) -> None:
    """
    Append a JSON payload to the DLQ list and trim to the most recent `max_entries`.

    Uses LPUSH + LTRIM so the list always contains the newest items first; popping
    for replay happens with LRANGE / RPOP in a future drain task.
    """
    payload = {**payload, "queued_at": datetime.now(timezone.utc).isoformat()}
    try:
        await redis.lpush(key, json.dumps(payload, ensure_ascii=False))  # type: ignore[attr-defined]
        await redis.ltrim(key, 0, max_entries - 1)  # type: ignore[attr-defined]
        logger.warning("DLQ push key=%s reason=%s", key, payload.get("reason"))
    except Exception as exc:  # noqa: BLE001 — DLQ must never crash the inbound pipeline
        logger.error("DLQ push failed key=%s err=%s", key, exc)


def handoff_channel(tenant_id: str, prefix: str = "handoff") -> str:
    """Per-tenant pub/sub channel name, e.g. `handoff:tenant-1`."""
    return f"{prefix}:{tenant_id}"


async def publish_handoff(redis: object, tenant_id: str, event: dict[str, Any]) -> None:
    """
    Publish a handoff event on the per-tenant channel.

    Event schema (kept stable for Phase 8):
      {
        "event_id": "<uuid>",
        "conversation_id": "...",
        "channel_id": "...",
        "external_user_id": "...",
        "reason": "low_confidence" | "out_of_window" | "rate_limited" | "needs_template",
        "rag_score": 0.42 | None,
        "timestamp": "<iso8601>"
      }
    """
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    channel = handoff_channel(tenant_id)
    try:
        await redis.publish(channel, json.dumps(payload, ensure_ascii=False))  # type: ignore[attr-defined]
        logger.info("Handoff published channel=%s conversation=%s reason=%s",
                    channel, event.get("conversation_id"), event.get("reason"))
    except Exception as exc:  # noqa: BLE001 — pub/sub is best-effort, not blocking
        logger.error("Handoff publish failed channel=%s err=%s", channel, exc)
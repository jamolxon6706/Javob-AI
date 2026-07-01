"""
Phase 8 — generic per-tenant event bus on top of Redis pub/sub.

Reuses the same `{prefix}:{tenant_id}` channel convention as Phase 5's
`handoff:{tenant_id}` (see apps/worker/src/worker/services/events.py), but on
a separate `events:{tenant_id}` channel so the two producers (API process for
operator-originated events, worker process for handoff events) never collide.

The API publishes here when something happens that the operator dashboard
should see live without a page refresh: an operator-sent reply, or a
conversation status change (resolve, assign, operator takeover).

Decision (see docs/ARCHITECTURE.md §Decisions): inbound customer/bot messages
are NOT published here in Phase 8. Wiring that would mean touching
apps/worker's OutboundDispatcher / inbound task, both of which have exact-call
unit tests asserting today's Redis interaction counts; re-publishing every
bot reply risks breaking those for limited day-1 benefit. The inbox instead
short-polls GET /inbox/conversations for inbound traffic. Revisit once a
worker-side observability event bus exists (Phase 13).

`javobai.ws.router`'s background listener psubscribes to `events:*` and
`handoff:*` and fans both out to connected dashboard websockets.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def events_channel(tenant_id: str) -> str:
    return f"events:{tenant_id}"


async def publish_event(redis: Redis, tenant_id: str, event: dict[str, Any]) -> None:
    """Publish an event on the tenant's channel. Best-effort: never raises."""
    payload = {"timestamp": datetime.now(UTC).isoformat(), **event}
    body = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        await redis.publish(events_channel(tenant_id), body)
    except Exception as exc:  # noqa: BLE001 — realtime push is best-effort, not load-bearing
        logger.warning("publish_event failed tenant=%s err=%s", tenant_id, exc)

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from worker.engine.core import EngineReply
from worker.engine.unified import UnifiedMessage
from worker.services.conversation import ConversationState, mark_handoff, save_message
from worker.services.events import publish_handoff, push_to_dlq
from worker.services.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

# Platforms whose APIs enforce a 24h customer-service messaging window (Meta policy).
# Telegram has no such restriction.
WINDOW_ENFORCED_PLATFORMS = {"whatsapp", "instagram", "facebook"}

# Reasons we record in the OutboundResult. Stable set — Phase 13 analytics will
# group by these.
OutboundReason = Literal[
    "sent",
    "empty_reply",
    "window_expired",
    "rate_limited",
    "send_failed",
]

# Handoff reasons pushed to the per-tenant pub/sub channel. Phase 8 UX uses these.
HandoffReason = Literal[
    "low_confidence",       # engine produced a handoff reply
    "out_of_window",        # Meta platform window expired
    "rate_limited",         # per-conversation anti-runaway triggered
    "needs_template",       # reserved for Phase 9 (out-of-window templates)
]

SendFn = Callable[[str], Awaitable[object]]


@dataclass(frozen=True)
class OutboundResult:
    """What actually happened to this outbound message."""
    reason: OutboundReason
    handoff: HandoffReason | None = None  # set iff a handoff event was emitted


class OutboundDispatcher:
    """
    Outbound leg of the pipeline (ARCHITECTURE.md Phase 5).

    Enforces, in order:
      1. Non-empty reply check.
      2. 24h messaging window for Meta platforms (Telegram is exempt).
      3. Per-conversation anti-runaway rate-limit (non-blocking; refusal DLQs).
      4. Channel-level rate-limit (blocking; back-pressure on platform).
      5. Send via the caller-supplied `send_fn`, persisting the outbound Message row.
      6. On permanent send failure: push to DLQ.
      7. If the reply was a handoff, mark the conversation and publish the event.

    Returns an `OutboundResult` so callers (and Phase 13 analytics) know exactly
    what happened without re-parsing logs.
    """

    def __init__(
        self,
        rate_limiter: RateLimiter,
        *,
        dlq_redis: object | None = None,
        dlq_key: str = "dlq:outbound",
        dlq_max_entries: int = 1000,
        per_conversation_limit: int = 3,
        per_conversation_window_seconds: int = 60,
    ) -> None:
        self._rate_limiter = rate_limiter
        # Reuse the same Redis connection for the per-conversation bucket.
        # (RateLimiter stores redis as `object`; the inner type is Redis.)
        self._per_conv_limiter = RateLimiter(
            rate_limiter._redis,
            limit=per_conversation_limit,
            window_seconds=per_conversation_window_seconds,
        )
        self._dlq_redis = dlq_redis
        self._dlq_key = dlq_key
        self._dlq_max_entries = dlq_max_entries

    async def send(
        self,
        conn: object,  # asyncpg.Connection
        msg: UnifiedMessage,
        reply: EngineReply,
        conversation: ConversationState,
        send_fn: SendFn,
    ) -> OutboundResult:
        if not reply.text:
            return OutboundResult(reason="empty_reply")

        # 1) Meta 24h window
        if msg.platform in WINDOW_ENFORCED_PLATFORMS and _window_expired(conversation):
            logger.warning(
                "tenant=%s conversation=%s 24h window expired — routing to operator",
                msg.tenant_id, conversation.id,
            )
            await mark_handoff(conn, conversation.id)
            await self._emit_handoff(msg, conversation, reason="out_of_window", rag_score=reply.rag_score)
            return OutboundResult(reason="window_expired", handoff="out_of_window")

        # 2) Per-conversation anti-runaway (non-blocking). Keyed by conversation_id
        # so two customers on the same channel don't share a bucket.
        per_conv_key = f"conv:{msg.tenant_id}:{msg.conversation_id}"
        if not await self._per_conv_limiter.try_acquire(per_conv_key):
            logger.warning(
                "tenant=%s conversation=%s per-conversation rate-limit hit — skipping reply",
                msg.tenant_id, conversation.id,
            )
            await self._dlq_push(msg, conversation, reason="rate_limited",
                                 detail="per-conversation rate limit exceeded")
            await self._emit_handoff(msg, conversation, reason="rate_limited", rag_score=reply.rag_score)
            return OutboundResult(reason="rate_limited", handoff="rate_limited")

        # 3) Channel-level back-pressure (blocking).
        await self._rate_limiter.acquire(msg.channel_id)

        # 4) Send — adapter may raise after its own internal retries.
        try:
            await send_fn(reply.text)
        except Exception as exc:  # noqa: BLE001 — DLQ catches anything the adapter gave up on
            logger.error(
                "tenant=%s conversation=%s send failed permanently: %s",
                msg.tenant_id, conversation.id, exc,
            )
            await self._dlq_push(msg, conversation, reason="send_failed", detail=str(exc))
            return OutboundResult(reason="send_failed")

        # 5) Persist the outbound message + flag handoff if this was one.
        await save_message(
            conn,
            conversation_id=conversation.id,
            tenant_id=msg.tenant_id,
            direction="outbound",
            content=reply.text,
            source=reply.source,
            rag_score=reply.rag_score,
        )

        if reply.source == "handoff":
            await mark_handoff(conn, conversation.id)
            await self._emit_handoff(msg, conversation, reason="low_confidence", rag_score=reply.rag_score)
            return OutboundResult(reason="sent", handoff="low_confidence")

        return OutboundResult(reason="sent")

    async def _dlq_push(self, msg: UnifiedMessage, conversation: ConversationState,
                        *, reason: str, detail: str) -> None:
        if self._dlq_redis is None:
            return
        await push_to_dlq(
            self._dlq_redis,
            self._dlq_key,
            {
                "tenant_id": msg.tenant_id,
                "channel_id": msg.channel_id,
                "conversation_id": conversation.id,
                "platform": msg.platform,
                "external_user_id": msg.external_user_id,
                "reason": reason,
                "detail": detail,
            },
            self._dlq_max_entries,
        )

    async def _emit_handoff(self, msg: UnifiedMessage, conversation: ConversationState,
                            *, reason: HandoffReason, rag_score: float | None) -> None:
        if self._dlq_redis is None:
            return
        await publish_handoff(
            self._dlq_redis,
            msg.tenant_id,
            {
                "conversation_id": conversation.id,
                "channel_id": msg.channel_id,
                "external_user_id": msg.external_user_id,
                "platform": msg.platform,
                "reason": reason,
                "rag_score": rag_score,
            },
        )


def _window_expired(conversation: ConversationState) -> bool:
    if conversation.window_expires_at is None:
        return True
    return datetime.now(timezone.utc) > conversation.window_expires_at
from __future__ import annotations

import asyncio


class RateLimiter:
    """
    Fixed-window rate limiter backed by Redis, one bucket per key.

    Used by OutboundDispatcher in two modes:
      - `acquire` (blocking): channel-level — back-pressure on the platform's send rate.
      - `try_acquire` (non-blocking): per-conversation — refuse the 4th auto-reply in
        a minute to the same customer so an integration loop can't burn through quota.
    """

    def __init__(self, redis: object, limit: int = 20, window_seconds: int = 1) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    async def acquire(self, key: str) -> None:
        """Block until a send slot for `key` is available in the current window."""
        full_key = f"ratelimit:{key}"
        while True:
            count = await self._redis.incr(full_key)  # type: ignore[attr-defined]
            if count == 1:
                await self._redis.expire(full_key, self._window)  # type: ignore[attr-defined]
            if count <= self._limit:
                return
            ttl = await self._redis.ttl(full_key)  # type: ignore[attr-defined]
            await asyncio.sleep(max(ttl, 0) + 0.05)

    async def try_acquire(self, key: str) -> bool:
        """
        Non-blocking variant. Returns True if a slot was taken, False if the window
        is full. Callers MUST handle the False case (skip + log + DLQ if needed) —
        never block here, because the inbound pipeline should not stall on a
        runaway-customer burst.
        """
        full_key = f"ratelimit:{key}"
        count = await self._redis.incr(full_key)  # type: ignore[attr-defined]
        if count == 1:
            await self._redis.expire(full_key, self._window)  # type: ignore[attr-defined]
        return bool(count <= self._limit)
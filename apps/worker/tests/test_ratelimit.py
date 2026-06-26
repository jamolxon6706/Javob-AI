"""RateLimiter unit tests (mocked Redis, no network)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from worker.services.ratelimit import RateLimiter


@pytest.mark.asyncio
async def test_acquire_under_limit_returns_immediately() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 1
    limiter = RateLimiter(redis, limit=5, window_seconds=1)
    await limiter.acquire("channel-1")
    redis.expire.assert_awaited_once_with("ratelimit:channel-1", 1)


@pytest.mark.asyncio
async def test_acquire_does_not_reset_ttl_after_first_increment() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 3
    limiter = RateLimiter(redis, limit=5, window_seconds=1)
    await limiter.acquire("channel-1")
    redis.expire.assert_not_called()


@pytest.mark.asyncio
async def test_acquire_over_limit_waits_then_succeeds() -> None:
    redis = AsyncMock()
    redis.incr.side_effect = [6, 1]  # first call over the limit=5, second call resets
    redis.ttl.return_value = 0
    limiter = RateLimiter(redis, limit=5, window_seconds=1)
    await limiter.acquire("channel-1")
    assert redis.incr.await_count == 2


# ──────────────── Phase 5: non-blocking try_acquire ────────────────


@pytest.mark.asyncio
async def test_try_acquire_under_limit_returns_true_and_sets_ttl() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 1
    limiter = RateLimiter(redis, limit=3, window_seconds=60)
    accepted = await limiter.try_acquire("conv:tenant-1:conv-42")
    assert accepted is True
    redis.expire.assert_awaited_once_with("ratelimit:conv:tenant-1:conv-42", 60)


@pytest.mark.asyncio
async def test_try_acquire_over_limit_returns_false_immediately() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 4  # already over the 3/min budget
    limiter = RateLimiter(redis, limit=3, window_seconds=60)
    accepted = await limiter.try_acquire("conv:tenant-1:conv-42")
    assert accepted is False
    # No sleep, no extra round-trip — non-blocking by contract.
    redis.ttl.assert_not_called()


@pytest.mark.asyncio
async def test_try_acquire_subsequent_increments_do_not_reset_ttl() -> None:
    redis = AsyncMock()
    redis.incr.return_value = 2
    limiter = RateLimiter(redis, limit=3, window_seconds=60)
    await limiter.try_acquire("conv:tenant-1:conv-42")
    redis.expire.assert_not_called()

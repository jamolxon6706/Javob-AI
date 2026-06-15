from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from javobai.config import settings

_pool: aioredis.ConnectionPool | None = None


def get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(settings.redis_url, decode_responses=False)
    return _pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:  # type: ignore[type-arg]
    client: aioredis.Redis = aioredis.Redis(connection_pool=get_pool())  # type: ignore[type-arg]
    try:
        yield client
    finally:
        await client.aclose()

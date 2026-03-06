from __future__ import annotations

import os
from functools import lru_cache

import redis.asyncio as aioredis


@lru_cache(maxsize=1)
def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            _redis_url(),
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None

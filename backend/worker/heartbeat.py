from __future__ import annotations

import asyncio
import time

import structlog

from shared.constants import HEARTBEAT_INTERVAL_SEC, REDIS_HEARTBEAT_KEY, REDIS_WORKER_META_PREFIX
from shared.redis_client import get_redis

logger = structlog.get_logger()


async def start_heartbeat(worker_id: str, stop_event: asyncio.Event) -> None:
    redis = await get_redis()
    meta_key = f"{REDIS_WORKER_META_PREFIX}{worker_id}"

    await redis.hset(meta_key, mapping={"worker_id": worker_id, "current_job_id": ""})

    while not stop_event.is_set():
        try:
            await redis.zadd(REDIS_HEARTBEAT_KEY, {worker_id: time.time()})
        except Exception:
            logger.exception("heartbeat_failed", worker_id=worker_id)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL_SEC)
            break
        except asyncio.TimeoutError:
            pass

    await redis.zrem(REDIS_HEARTBEAT_KEY, worker_id)
    await redis.delete(meta_key)
    logger.info("heartbeat_stopped", worker_id=worker_id)


async def set_current_job(worker_id: str, job_id: str | None) -> None:
    redis = await get_redis()
    meta_key = f"{REDIS_WORKER_META_PREFIX}{worker_id}"
    await redis.hset(meta_key, "current_job_id", job_id or "")

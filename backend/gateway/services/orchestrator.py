from __future__ import annotations

import asyncio
import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.services import job_service, queue_service
from shared.constants import (
    HEARTBEAT_TIMEOUT_SEC,
    JobStatus,
    REDIS_HEARTBEAT_KEY,
    REDIS_WORKER_META_PREFIX,
    WorkerStatus,
)
from shared.redis_client import get_redis

logger = structlog.get_logger()


async def get_live_workers() -> list[dict]:
    redis = await get_redis()
    now = time.time()
    all_workers = await redis.zrangebyscore(
        REDIS_HEARTBEAT_KEY, "-inf", "+inf", withscores=True
    )
    workers = []
    for worker_id, last_hb in all_workers:
        age = now - last_hb
        status = WorkerStatus.ALIVE if age < HEARTBEAT_TIMEOUT_SEC else WorkerStatus.DEAD
        meta_raw = await redis.hgetall(f"{REDIS_WORKER_META_PREFIX}{worker_id}")
        workers.append({
            "id": worker_id,
            "status": status,
            "last_heartbeat_age_sec": round(age, 1),
            "current_job_id": meta_raw.get("current_job_id"),
        })
    return workers


async def detect_dead_workers() -> list[str]:
    redis = await get_redis()
    cutoff = time.time() - HEARTBEAT_TIMEOUT_SEC
    dead = await redis.zrangebyscore(REDIS_HEARTBEAT_KEY, "-inf", cutoff)
    for wid in dead:
        logger.warning("dead_worker_detected", worker_id=wid)
    return dead


async def reclaim_and_requeue(session: AsyncSession) -> int:
    """Reclaim stuck messages from dead consumers and reset job state."""
    reclaimed = await queue_service.reclaim_dead_messages()
    count = 0
    for msg in reclaimed:
        job_id = msg.get("job_id")
        if not job_id:
            continue
        job = await job_service.get_job(session, job_id)
        if job and job.status == JobStatus.PROCESSING:
            if job.attempts >= 3:
                await job_service.update_job_status(
                    session, job_id, status=JobStatus.DEAD_LETTER,
                    error="Max retries exceeded after worker failure",
                )
                logger.error("job_dead_lettered", job_id=job_id, attempts=job.attempts)
            else:
                await job_service.update_job_status(
                    session, job_id, status=JobStatus.QUEUED,
                    progress=0, increment_attempts=True,
                )
                logger.info("job_requeued", job_id=job_id, attempt=job.attempts + 1)
            count += 1
    return count


async def run_orchestrator_loop(get_session_fn) -> None:
    """Background loop: detect dead workers and reclaim stuck jobs every 10s."""
    while True:
        try:
            await detect_dead_workers()
            async for session in get_session_fn():
                await reclaim_and_requeue(session)
                break
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("orchestrator_loop_error")
        await asyncio.sleep(10)

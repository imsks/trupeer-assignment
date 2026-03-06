from __future__ import annotations

import json
import structlog

from shared.constants import (
    DEAD_MESSAGE_IDLE_MS,
    REDIS_CONSUMER_GROUP,
    REDIS_STREAM_JOBS,
)
from shared.redis_client import get_redis

logger = structlog.get_logger()


async def ensure_consumer_group() -> None:
    redis = await get_redis()
    try:
        await redis.xgroup_create(
            REDIS_STREAM_JOBS, REDIS_CONSUMER_GROUP, id="0", mkstream=True
        )
        logger.info("consumer_group_created", stream=REDIS_STREAM_JOBS, group=REDIS_CONSUMER_GROUP)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass  # group already exists
        else:
            raise


async def enqueue_job(job_id: str, job_type: str, metadata: dict | None = None) -> str:
    redis = await get_redis()
    payload = {"job_id": job_id, "job_type": job_type}
    if metadata:
        payload["metadata"] = json.dumps(metadata)

    msg_id = await redis.xadd(REDIS_STREAM_JOBS, payload)
    logger.info("job_enqueued", job_id=job_id, job_type=job_type, stream_msg_id=msg_id)
    return msg_id


async def reclaim_dead_messages(consumer_name: str = "gateway-reclaimer") -> list[dict]:
    """Reclaim messages from dead consumers using XAUTOCLAIM."""
    redis = await get_redis()
    reclaimed = []
    try:
        result = await redis.xautoclaim(
            REDIS_STREAM_JOBS,
            REDIS_CONSUMER_GROUP,
            consumer_name,
            min_idle_time=DEAD_MESSAGE_IDLE_MS,
            count=10,
        )
        if result and len(result) >= 2:
            messages = result[1]
            for msg_id, data in messages:
                reclaimed.append({"msg_id": msg_id, **data})
                logger.warning("job_reclaimed", msg_id=msg_id, job_id=data.get("job_id"))
    except Exception:
        logger.exception("reclaim_failed")
    return reclaimed


async def get_stream_info() -> dict:
    redis = await get_redis()
    try:
        info = await redis.xinfo_stream(REDIS_STREAM_JOBS)
        groups = await redis.xinfo_groups(REDIS_STREAM_JOBS)
        return {"stream": info, "consumer_groups": groups}
    except Exception:
        return {"stream": None, "consumer_groups": []}

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from gateway.db import get_session
from gateway.services import job_service
from shared.constants import JOB_PROGRESS_CHANNEL_PREFIX, JobStatus
from shared.redis_client import get_redis

router = APIRouter(tags=["sse"])


@router.get("/jobs/{job_id}/status")
async def stream_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    job = await job_service.get_job(session, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        channel = f"{JOB_PROGRESS_CHANNEL_PREFIX}{job_id}"
        await pubsub.subscribe(channel)

        try:
            current = await job_service.get_job(session, job_id)
            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": job_id,
                    "status": current.status,
                    "progress": current.progress,
                }),
            }

            if current.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER):
                return

            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and msg["type"] == "message":
                    data = json.loads(msg["data"])
                    yield {"event": "status", "data": json.dumps(data)}
                    if data.get("status") in (
                        JobStatus.COMPLETED,
                        JobStatus.FAILED,
                        JobStatus.DEAD_LETTER,
                    ):
                        return
                else:
                    yield {"event": "ping", "data": ""}
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return EventSourceResponse(event_generator())


@router.get("/pipelines/{pipeline_id}/status")
async def stream_pipeline_status(
    pipeline_id: str,
    session: AsyncSession = Depends(get_session),
):
    jobs = await job_service.get_pipeline_jobs(session, pipeline_id)
    if not jobs:
        raise HTTPException(404, f"Pipeline {pipeline_id} not found")

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        channels = [f"{JOB_PROGRESS_CHANNEL_PREFIX}{j.id}" for j in jobs]
        for ch in channels:
            await pubsub.subscribe(ch)

        try:
            for j in jobs:
                yield {
                    "event": "step_status",
                    "data": json.dumps({
                        "job_id": j.id,
                        "step": j.pipeline_step,
                        "status": j.status,
                        "progress": j.progress,
                    }),
                }

            completed_count = sum(1 for j in jobs if j.status in (JobStatus.COMPLETED, JobStatus.FAILED))
            while completed_count < len(jobs):
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    data = json.loads(msg["data"])
                    yield {"event": "step_status", "data": json.dumps(data)}
                    if data.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED):
                        completed_count += 1
                else:
                    yield {"event": "ping", "data": ""}
                await asyncio.sleep(0.5)

            yield {
                "event": "pipeline_complete",
                "data": json.dumps({"pipeline_id": pipeline_id}),
            }
        finally:
            for ch in channels:
                await pubsub.unsubscribe(ch)
            await pubsub.aclose()

    return EventSourceResponse(event_generator())

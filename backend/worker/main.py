from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal

import structlog

from shared.constants import (
    JOB_PROGRESS_CHANNEL_PREFIX,
    JobStatus,
    JobType,
    MINIO_OUTPUT_PREFIX,
    REDIS_CONSUMER_GROUP,
    REDIS_STREAM_JOBS,
)
from shared.redis_client import close_redis, get_redis
from shared.storage_client import ensure_bucket, get_bucket, get_s3_client
from worker.config import get_tmp_dir, get_worker_id
from worker.heartbeat import set_current_job, start_heartbeat
from worker.processors import ExtractProcessor, OverlayProcessor, TranscodeProcessor

logger = structlog.get_logger()

PROCESSOR_MAP = {
    JobType.OVERLAY: OverlayProcessor,
    JobType.TRANSCODE: TranscodeProcessor,
    JobType.EXTRACT: ExtractProcessor,
}


async def publish_progress(job_id: str, status: str, progress: int = 0, error: str = "") -> None:
    redis = await get_redis()
    channel = f"{JOB_PROGRESS_CHANNEL_PREFIX}{job_id}"
    await redis.publish(channel, json.dumps({
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "error": error,
    }))


async def download_from_minio(key: str, local_path: str) -> None:
    async with get_s3_client() as s3:
        await s3.download_file(get_bucket(), key, local_path)


async def upload_to_minio(local_path: str, key: str) -> None:
    await ensure_bucket()
    async with get_s3_client() as s3:
        await s3.upload_file(local_path, get_bucket(), key)


async def check_output_exists(key: str) -> bool:
    """Idempotency check -- skip processing if output already exists."""
    async with get_s3_client() as s3:
        try:
            await s3.head_object(Bucket=get_bucket(), Key=key)
            return True
        except Exception:
            return False


async def process_job(worker_id: str, job_id: str, job_type: str, metadata: dict) -> None:
    work_dir = os.path.join(get_tmp_dir(), job_id)
    os.makedirs(work_dir, exist_ok=True)

    try:
        await set_current_job(worker_id, job_id)
        await publish_progress(job_id, JobStatus.PROCESSING, progress=5)

        processor_cls = PROCESSOR_MAP.get(job_type)
        if not processor_cls:
            raise ValueError(f"Unknown job type: {job_type}")

        processor = processor_cls(job_id, work_dir)
        output_key = f"{MINIO_OUTPUT_PREFIX}/{job_id}/{processor.output_filename()}"

        if await check_output_exists(output_key):
            logger.info("output_already_exists", job_id=job_id, key=output_key)
            await publish_progress(job_id, JobStatus.COMPLETED, progress=100)
            return

        input_key = metadata.get("input_path", f"inputs/{job_id}/input.mp4")
        local_input = os.path.join(work_dir, "input.mp4")
        await download_from_minio(input_key, local_input)
        await publish_progress(job_id, JobStatus.PROCESSING, progress=20)

        extra_kwargs = {}
        if job_type == JobType.OVERLAY:
            subtitle_key = metadata.get("subtitle_path", f"inputs/{job_id}/subtitle.srt")
            local_subtitle = os.path.join(work_dir, "subtitle.srt")
            await download_from_minio(subtitle_key, local_subtitle)
            extra_kwargs["subtitle_path"] = local_subtitle

        await publish_progress(job_id, JobStatus.PROCESSING, progress=30)

        output_path = await processor.execute(local_input, **extra_kwargs)
        await publish_progress(job_id, JobStatus.PROCESSING, progress=80)

        await upload_to_minio(output_path, output_key)
        await publish_progress(job_id, JobStatus.COMPLETED, progress=100)

        logger.info("job_completed", job_id=job_id, output_key=output_key)

    except Exception as e:
        logger.exception("job_failed", job_id=job_id)
        await publish_progress(job_id, JobStatus.FAILED, progress=0, error=str(e)[:500])
        raise
    finally:
        await set_current_job(worker_id, None)
        shutil.rmtree(work_dir, ignore_errors=True)


async def consumer_loop(worker_id: str, stop_event: asyncio.Event) -> None:
    redis = await get_redis()

    try:
        await redis.xgroup_create(REDIS_STREAM_JOBS, REDIS_CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise

    logger.info("consumer_started", worker_id=worker_id, stream=REDIS_STREAM_JOBS)

    while not stop_event.is_set():
        try:
            messages = await redis.xreadgroup(
                REDIS_CONSUMER_GROUP,
                worker_id,
                {REDIS_STREAM_JOBS: ">"},
                count=1,
                block=2000,
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                for msg_id, data in stream_messages:
                    job_id = data.get("job_id", "")
                    job_type = data.get("job_type", "")
                    raw_meta = data.get("metadata", "{}")

                    try:
                        metadata = json.loads(raw_meta) if raw_meta else {}
                    except json.JSONDecodeError:
                        metadata = {}

                    logger.info("job_claimed", worker_id=worker_id, job_id=job_id, msg_id=msg_id)

                    try:
                        await process_job(worker_id, job_id, job_type, metadata)
                        await redis.xack(REDIS_STREAM_JOBS, REDIS_CONSUMER_GROUP, msg_id)
                        logger.info("job_acked", job_id=job_id, msg_id=msg_id)
                    except Exception:
                        logger.exception("job_processing_error", job_id=job_id)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("consumer_loop_error")
            await asyncio.sleep(2)

    logger.info("consumer_stopped", worker_id=worker_id)


async def main() -> None:
    worker_id = get_worker_id()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: stop_event.set())

    logger.info("worker_starting", worker_id=worker_id)

    heartbeat_task = asyncio.create_task(start_heartbeat(worker_id, stop_event))
    consumer_task = asyncio.create_task(consumer_loop(worker_id, stop_event))

    await asyncio.gather(heartbeat_task, consumer_task)

    await close_redis()
    logger.info("worker_shutdown_complete", worker_id=worker_id)


if __name__ == "__main__":
    asyncio.run(main())

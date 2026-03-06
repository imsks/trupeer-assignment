from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.models.job import Job
from shared.constants import JobStatus, JobType


async def create_job(
    session: AsyncSession,
    *,
    job_type: JobType,
    input_path: str,
    subtitle_path: Optional[str] = None,
    params: Optional[dict] = None,
    pipeline_id: Optional[str] = None,
    pipeline_step: Optional[int] = None,
) -> Job:
    job = Job(
        job_type=job_type,
        status=JobStatus.PENDING,
        input_path=input_path,
        subtitle_path=subtitle_path,
        params=json.dumps(params) if params else None,
        pipeline_id=pipeline_id,
        pipeline_step=pipeline_step,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> Optional[Job]:
    return await session.get(Job, job_id)


async def list_jobs(
    session: AsyncSession,
    *,
    status: Optional[JobStatus] = None,
    pipeline_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Job.status == status)
    if pipeline_id:
        stmt = stmt.where(Job.pipeline_id == pipeline_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    *,
    status: JobStatus,
    progress: int = 0,
    worker_id: Optional[str] = None,
    output_path: Optional[str] = None,
    error: Optional[str] = None,
    increment_attempts: bool = False,
) -> Optional[Job]:
    values: dict = {"status": status, "progress": progress}
    if worker_id is not None:
        values["worker_id"] = worker_id
    if output_path is not None:
        values["output_path"] = output_path
    if error is not None:
        values["error"] = error

    stmt = update(Job).where(Job.id == job_id).values(**values)
    await session.execute(stmt)

    if increment_attempts:
        await session.execute(
            update(Job).where(Job.id == job_id).values(attempts=Job.attempts + 1)
        )

    await session.commit()
    return await get_job(session, job_id)


async def get_pipeline_jobs(session: AsyncSession, pipeline_id: str) -> list[Job]:
    stmt = (
        select(Job)
        .where(Job.pipeline_id == pipeline_id)
        .order_by(Job.pipeline_step)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

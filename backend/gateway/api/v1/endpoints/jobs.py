from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_session
from gateway.schemas.job import JobOutputResponse, JobResponse
from gateway.services import job_service, queue_service, storage_service
from shared.constants import JobStatus, JobType

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def submit_job(
    job_type: JobType = Form(...),
    video: UploadFile = File(...),
    subtitle: Optional[UploadFile] = File(None),
    params: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
):
    if job_type == JobType.OVERLAY and subtitle is None:
        raise HTTPException(400, "Overlay jobs require a subtitle (.srt) file")

    job = await job_service.create_job(session, job_type=job_type, input_path="")

    input_key = await storage_service.upload_input_file(
        job.id, video.file, video.filename or "input.mp4"
    )
    subtitle_key = None
    if subtitle:
        subtitle_key = await storage_service.upload_subtitle_file(
            job.id, subtitle.file, subtitle.filename or "subtitle.srt"
        )

    job = await job_service.update_job_status(
        session, job.id, status=JobStatus.QUEUED, progress=0
    )

    from sqlalchemy import update as sa_update
    from gateway.models.job import Job
    stmt = sa_update(Job).where(Job.id == job.id).values(
        input_path=input_key,
        subtitle_path=subtitle_key,
    )
    await session.execute(stmt)
    await session.commit()
    await session.refresh(job)

    await queue_service.enqueue_job(
        job.id, job_type,
        metadata={"input_path": input_key, "subtitle_path": subtitle_key},
    )
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = None,
    pipeline_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    return await job_service.list_jobs(
        session, status=status, pipeline_id=pipeline_id, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    job = await job_service.get_job(session, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return job


@router.get("/{job_id}/output", response_model=JobOutputResponse)
async def get_job_output(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    job = await job_service.get_job(session, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(409, f"Job is not completed yet (status: {job.status})")

    key = job.output_path or await storage_service.get_output_key(job_id)
    if not key:
        raise HTTPException(404, "Output file not found")

    url = await storage_service.generate_presigned_download(key)
    return JobOutputResponse(job_id=job_id, download_url=url)

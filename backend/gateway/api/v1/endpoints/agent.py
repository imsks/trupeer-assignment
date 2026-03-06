from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db import get_session
from gateway.schemas.agent import AgentExecuteResponse, AgentPlanResponse, AgentRequest
from gateway.services import agent_service, job_service, queue_service, storage_service
from shared.constants import JobStatus

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/plan", response_model=AgentPlanResponse)
async def plan_pipeline(request: AgentRequest):
    """Parse a natural language instruction into an execution plan without running it."""
    steps = await agent_service.parse_instruction(request.instruction)
    if not steps:
        raise HTTPException(422, "Could not parse instruction into valid media operations")
    return AgentPlanResponse(
        instruction=request.instruction,
        steps=steps,
        estimated_duration_seconds=len(steps) * 30,
        requires_confirmation=True,
    )


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_pipeline(
    instruction: str,
    video: UploadFile = File(...),
    subtitle: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
):
    """Parse instruction, create pipeline jobs, and begin execution."""
    steps = await agent_service.parse_instruction(instruction)
    if not steps:
        raise HTTPException(422, "Could not parse instruction into valid media operations")

    pipeline_id = str(uuid.uuid4())

    first_input_key = await storage_service.upload_input_file(
        pipeline_id, video.file, video.filename or "input.mp4"
    )
    subtitle_key = None
    if subtitle:
        subtitle_key = await storage_service.upload_subtitle_file(
            pipeline_id, subtitle.file, subtitle.filename or "subtitle.srt"
        )

    job_ids = []
    prev_output_key = first_input_key

    for step in steps:
        job = await job_service.create_job(
            session,
            job_type=step.job_type,
            input_path=prev_output_key,
            subtitle_path=subtitle_key if step.job_type.value == "overlay" else None,
            params=step.params,
            pipeline_id=pipeline_id,
            pipeline_step=step.step_index,
        )
        job_ids.append(job.id)

        if step.depends_on is None:
            await job_service.update_job_status(
                session, job.id, status=JobStatus.QUEUED
            )
            meta = {"input_path": prev_output_key}
            if subtitle_key and step.job_type.value == "overlay":
                meta["subtitle_path"] = subtitle_key
            await queue_service.enqueue_job(job.id, step.job_type, metadata=meta)

        prev_output_key = f"outputs/{job.id}/result"

    return AgentExecuteResponse(
        pipeline_id=pipeline_id,
        instruction=instruction,
        steps=steps,
        job_ids=job_ids,
    )

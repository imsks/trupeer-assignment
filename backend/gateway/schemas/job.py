from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from shared.constants import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    params: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus
    progress: int = 0
    attempts: int = 0
    input_path: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    pipeline_step: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobStatusEvent(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    message: str = ""


class JobOutputResponse(BaseModel):
    job_id: str
    download_url: str
    expires_in_seconds: int = Field(default=3600)


class PipelineStatusResponse(BaseModel):
    pipeline_id: str
    total_steps: int
    completed_steps: int
    current_step: Optional[int] = None
    status: str
    jobs: list[JobResponse]

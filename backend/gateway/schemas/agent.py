from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from shared.constants import JobType


class PipelineStep(BaseModel):
    step_index: int
    job_type: JobType
    params: dict = {}
    depends_on: Optional[int] = None


class AgentRequest(BaseModel):
    instruction: str
    confirm: bool = False


class AgentPlanResponse(BaseModel):
    instruction: str
    steps: list[PipelineStep]
    estimated_duration_seconds: Optional[int] = None
    requires_confirmation: bool = True


class AgentExecuteResponse(BaseModel):
    pipeline_id: str
    instruction: str
    steps: list[PipelineStep]
    job_ids: list[str]

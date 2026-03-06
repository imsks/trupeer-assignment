from __future__ import annotations

from fastapi import APIRouter

from gateway.services import orchestrator, queue_service

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("")
async def list_workers():
    workers = await orchestrator.get_live_workers()
    return {"workers": workers, "total": len(workers)}


@router.get("/stream-info")
async def stream_info():
    return await queue_service.get_stream_info()

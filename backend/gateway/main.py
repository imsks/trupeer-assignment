from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.api.v1.router import router as v1_router
from gateway.db import close_db, init_db
from gateway.services.orchestrator import run_orchestrator_loop
from gateway.services.queue_service import ensure_consumer_group
from shared.redis_client import close_redis
from shared.storage_client import ensure_bucket

logger = structlog.get_logger()

_orchestrator_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator_task

    logger.info("gateway_starting")
    await init_db()
    await ensure_bucket()
    await ensure_consumer_group()

    from gateway.db import get_session
    _orchestrator_task = asyncio.create_task(run_orchestrator_loop(get_session))
    logger.info("orchestrator_started")

    yield

    logger.info("gateway_shutting_down")
    if _orchestrator_task:
        _orchestrator_task.cancel()
        try:
            await _orchestrator_task
        except asyncio.CancelledError:
            pass
    await close_redis()
    await close_db()


app = FastAPI(
    title="Media Pipeline Gateway",
    description="Distributed media processing engine with ffmpeg workers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

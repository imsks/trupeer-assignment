from fastapi import APIRouter

from gateway.api.v1.endpoints import agent, jobs, sse, workers

router = APIRouter(prefix="/api/v1")
router.include_router(jobs.router)
router.include_router(workers.router)
router.include_router(agent.router)
router.include_router(sse.router)

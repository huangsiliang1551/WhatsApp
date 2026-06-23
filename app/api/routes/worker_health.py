from fastapi import APIRouter

from app.core.settings import get_settings
from app.services.worker_health import get_worker_health

router = APIRouter()


@router.get(
    "/api/worker/health",
    summary="Worker health check",
    description="Returns health status of the background worker process.",
    tags=["monitoring"],
)
async def worker_health() -> dict:
    settings = get_settings()
    return await get_worker_health(settings)

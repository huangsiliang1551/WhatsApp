from fastapi import APIRouter, Depends

from app.api.deps import get_queue_service, require_permission
from app.core.auth import RequestActor
from app.schemas.queue import QueueName
from app.services.queue_service import QueueService
from app.worker import get_worker_health

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.get(
    "/stats",
    summary="Get queue stats",
    description="Get queue statistics including job counts and processing rates.",
    tags=["queue"],
)
async def get_queue_stats(
    queue_service: QueueService = Depends(get_queue_service),
    actor: RequestActor = Depends(require_permission("operations.queue")),
) -> dict[str, object]:
    _ = actor
    try:
        return queue_service.get_stats().model_dump()
    except Exception:
        # Redis unavailable, return empty stats
        return {}


@router.get(
    "/dead-letter",
    summary="List dead letter jobs",
    description="List dead letter queue jobs with optional queue name filter.",
    tags=["queue"],
)
async def list_dead_letter_jobs(
    queue: str | None = None,
    queue_service: QueueService = Depends(get_queue_service),
    actor: RequestActor = Depends(require_permission("operations.queue")),
) -> list[dict[str, object]]:
    _ = actor
    queue_name: QueueName | None = queue if queue in ("ai_generation",) else None  # type: ignore[assignment]
    return [job.model_dump() for job in queue_service.list_dead_letter_jobs(queue_name=queue_name)]


@router.post(
    "/dead-letter/{job_id}/requeue",
    summary="Requeue dead letter job",
    description="Requeue a specific dead letter job for reprocessing.",
    tags=["queue"],
)
async def requeue_dead_letter_job(
    job_id: str,
    queue_service: QueueService = Depends(get_queue_service),
    actor: RequestActor = Depends(require_permission("operations.queue")),
) -> dict[str, object]:
    _ = actor
    updated = queue_service.requeue_dead_letter(job_id)
    if updated is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Dead letter job '{job_id}' not found.")
    return updated.model_dump()


@router.post(
    "/dead-letter/requeue-all",
    summary="Requeue all dead letter jobs",
    description="Requeue all dead letter jobs for reprocessing.",
    tags=["queue"],
)
async def requeue_all_dead_letter_jobs(
    queue: str | None = None,
    queue_service: QueueService = Depends(get_queue_service),
    actor: RequestActor = Depends(require_permission("operations.queue")),
) -> dict[str, int]:
    _ = actor
    queue_name: QueueName | None = queue if queue in ("ai_generation",) else None  # type: ignore[assignment]
    count = queue_service.requeue_all_dead_letters(queue_name=queue_name)
    return {"requeued_count": count}


@router.get(
    "/health",
    summary="Worker health",
    description="Get worker process health status.",
    tags=["queue"],
)
async def worker_health(
    actor: RequestActor = Depends(require_permission("operations.queue")),
) -> dict[str, object]:
    _ = actor
    return get_worker_health()

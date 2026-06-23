from fastapi import APIRouter, Depends, Response

from app.api.deps import require_permission
from app.core.auth import RequestActor
from app.core.metrics import build_metrics_summary, render_metrics

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus metrics endpoint",
    description="Returns Prometheus-formatted application metrics.",
    tags=["monitoring"],
)
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@router.get(
    "/api/metrics/summary",
    summary="Metrics summary",
    description="Returns a JSON summary of key application metrics.",
    tags=["monitoring"],
)
async def metrics_summary(
    actor: RequestActor = Depends(require_permission("monitoring.view")),
) -> dict[str, object]:
    _ = actor
    return build_metrics_summary().model_dump()

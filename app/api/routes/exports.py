import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.exports import ExportCreateRequest, ExportCreateResponse, ExportStatusResponse
from app.services.export_service import ExportService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/exports", tags=["exports"])


def _get_export_service(session: Session = Depends(get_db_session)) -> ExportService:
    return ExportService(session=session)


@router.post(
    "",
    summary="Create export",
    description="Create an async data export job. Supported types: conversations, templates, tickets, customers, users, audit_logs. Files expire after 24 hours.",
    tags=["exports"],
)
async def create_export(
    payload: ExportCreateRequest,
    export_service: ExportService = Depends(_get_export_service),
    actor: RequestActor = Depends(require_permission("reports.export")),
) -> ExportCreateResponse:
    if payload.account_id:
        actor.require_account_access(payload.account_id)
    try:
        result = await export_service.create_export(
            export_type=payload.type,
            filters=payload.filters or {},
            columns=payload.columns,
        )
        return ExportCreateResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{export_id}",
    summary="Get export status",
    description="Check the status of an export job.",
    tags=["exports"],
)
async def get_export_status(
    export_id: str,
    export_service: ExportService = Depends(_get_export_service),
    actor: RequestActor = Depends(require_permission("reports.export")),
) -> ExportStatusResponse:
    status = export_service.get_export_status(export_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found.")
    return ExportStatusResponse(**status)


@router.get(
    "/{export_id}/download",
    summary="Download export file",
    description="Download the generated CSV export file.",
    tags=["exports"],
)
async def download_export(
    export_id: str,
    export_service: ExportService = Depends(_get_export_service),
    actor: RequestActor = Depends(require_permission("reports.export")),
) -> FileResponse:
    status = export_service.get_export_status(export_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Export '{export_id}' not found.")
    if status.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Export '{export_id}' is still processing.")
    file_path = export_service.get_export_file_path(export_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"Export file '{export_id}' not found.")
    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        filename=f"{export_id}.csv",
    )

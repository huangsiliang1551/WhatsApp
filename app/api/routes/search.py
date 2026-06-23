from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_search_service(session: Session = Depends(get_db_session)) -> SearchService:
    return SearchService(session=session)


@router.get(
    "",
    summary="Global search",
    description="Search across conversations, customers, templates, and tickets. Supports filtering by type and account.",
    tags=["search"],
)
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(default=None, description="Comma-separated types: conversation,customer,template,ticket"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results per type"),
    account_id: str | None = Query(default=None, description="Filter by account"),
    search_service: SearchService = Depends(_get_search_service),
    actor: RequestActor = Depends(require_permission("operations.view")),
) -> dict:
    types_list = [t.strip() for t in type.split(",")] if type else None
    return await search_service.search(
        query=q,
        types=types_list,
        limit=limit,
        account_id=account_id,
    )

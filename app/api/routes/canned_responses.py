from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.canned_response_service import CannedResponseService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/canned-responses", tags=["canned-responses"])


class CreateCannedResponseRequest(BaseModel):
    account_id: str | None = None
    title: str
    content: str
    category: str
    variables: list[str] | None = None


class UpdateCannedResponseRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    variables: list[str] | None = None
    is_active: bool | None = None


@router.get(
    "",
    summary="List canned responses",
    description="List canned responses with optional account, category and search filters.",
)
async def list_canned_responses(
    account_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("canned_responses.view")),
) -> list[dict]:
    if account_id:
        actor.require_account_access(account_id)
    service = CannedResponseService(db_session)
    return await service.list_responses(account_id=account_id, category=category, is_active=is_active, search=search)


@router.post(
    "",
    summary="Create canned response",
    description="Create a new canned response.",
)
async def create_canned_response(
    payload: CreateCannedResponseRequest,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("canned_responses.create")),
) -> dict:
    if payload.account_id:
        actor.require_account_access(payload.account_id)
    service = CannedResponseService(db_session)
    return await service.create_response(
        account_id=payload.account_id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
        variables=payload.variables,
        created_by=actor.actor_id,
    )


@router.put(
    "/{response_id}",
    summary="Update canned response",
    description="Update an existing canned response.",
)
async def update_canned_response(
    response_id: str,
    payload: UpdateCannedResponseRequest,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("canned_responses.edit")),
) -> dict:
    service = CannedResponseService(db_session)
    try:
        return await service.update_response(
            response_id=response_id,
            title=payload.title,
            content=payload.content,
            category=payload.category,
            variables=payload.variables,
            is_active=payload.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/{response_id}",
    summary="Delete canned response",
    description="Delete a canned response.",
)
async def delete_canned_response(
    response_id: str,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("canned_responses.delete")),
) -> dict:
    service = CannedResponseService(db_session)
    try:
        await service.delete_response(response_id=response_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": response_id, "deleted": True}

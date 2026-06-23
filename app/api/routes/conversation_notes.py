from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.conversation_note_service import ConversationNoteService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/conversations/{account_id}/{conversation_id}/notes", tags=["conversations"])


class CreateNoteRequest(BaseModel):
    content: str = Field(min_length=1)
    agent_id: str | None = None
    agent_name: str | None = None


class UpdateNoteRequest(BaseModel):
    content: str = Field(min_length=1)


@router.post(
    "",
    summary="Create conversation note",
    description="Create an internal note for a conversation. Notes are not sent to the customer.",
)
async def create_note(
    account_id: str,
    conversation_id: str,
    payload: CreateNoteRequest,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.notes")),
) -> dict:
    actor.require_account_access(account_id)
    service = ConversationNoteService(db_session)
    return await service.create_note(
        account_id=account_id,
        conversation_id=conversation_id,
        content=payload.content,
        agent_id=payload.agent_id or actor.actor_id,
        agent_name=payload.agent_name or actor.display_name,
    )


@router.get(
    "",
    summary="List conversation notes",
    description="List internal notes for a conversation.",
)
async def list_notes(
    account_id: str,
    conversation_id: str,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.notes")),
) -> list[dict]:
    actor.require_account_access(account_id)
    service = ConversationNoteService(db_session)
    return await service.list_notes(
        account_id=account_id,
        conversation_id=conversation_id,
    )


@router.put(
    "/{note_id}",
    summary="Update conversation note",
    description="Update the content of an existing internal note.",
)
async def update_note(
    account_id: str,
    conversation_id: str,
    note_id: str,
    payload: UpdateNoteRequest,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.notes")),
) -> dict:
    actor.require_account_access(account_id)
    service = ConversationNoteService(db_session)
    try:
        return await service.update_note(
            note_id=note_id,
            account_id=account_id,
            conversation_id=conversation_id,
            content=payload.content,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/{note_id}",
    summary="Delete conversation note",
    description="Delete an internal note.",
)
async def delete_note(
    account_id: str,
    conversation_id: str,
    note_id: str,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.notes")),
) -> dict:
    actor.require_account_access(account_id)
    service = ConversationNoteService(db_session)
    try:
        await service.delete_note(
            note_id=note_id,
            account_id=account_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": note_id, "deleted": True}

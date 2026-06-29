from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import Conversation
from app.services.data_scope_filter_service import DataScopeFilterService
from app.services.conversation_note_service import ConversationNoteService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateNoteRequest(BaseModel):
    content: str = Field(min_length=1)
    agent_id: str | None = None
    agent_name: str | None = None


class UpdateNoteRequest(BaseModel):
    content: str = Field(min_length=1)


def _ensure_conversation_scope(
    db_session: Session,
    actor: RequestActor,
    *,
    account_id: str,
    conversation_id: str,
) -> None:
    actor.require_account_access(account_id)
    if actor.is_super_admin:
        return
    stmt = select(Conversation.id).where(
        Conversation.account_id == account_id,
        Conversation.external_conversation_id == conversation_id,
    )
    stmt = DataScopeFilterService(db_session).filter_conversations(stmt, actor)
    if db_session.scalar(stmt.limit(1)) is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")


@router.post(
    "/{account_id}/{conversation_id}/notes",
    summary="Create conversation note",
    description="Create an internal note for a conversation. Notes are not sent to the customer.",
)
@router.post(
    "/{account_id}:{conversation_id}/notes",
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
    _ensure_conversation_scope(
        db_session,
        actor,
        account_id=account_id,
        conversation_id=conversation_id,
    )
    service = ConversationNoteService(db_session)
    return await service.create_note(
        account_id=account_id,
        conversation_id=conversation_id,
        content=payload.content,
        agent_id=payload.agent_id or actor.actor_id,
        agent_name=payload.agent_name or actor.display_name,
    )


@router.get(
    "/{account_id}/{conversation_id}/notes",
    summary="List conversation notes",
    description="List internal notes for a conversation.",
)
@router.get(
    "/{account_id}:{conversation_id}/notes",
    summary="List conversation notes",
    description="List internal notes for a conversation.",
)
async def list_notes(
    account_id: str,
    conversation_id: str,
    db_session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("conversations.notes")),
) -> list[dict]:
    _ensure_conversation_scope(
        db_session,
        actor,
        account_id=account_id,
        conversation_id=conversation_id,
    )
    service = ConversationNoteService(db_session)
    return await service.list_notes(
        account_id=account_id,
        conversation_id=conversation_id,
    )


@router.put(
    "/{account_id}/{conversation_id}/notes/{note_id}",
    summary="Update conversation note",
    description="Update the content of an existing internal note.",
)
@router.put(
    "/{account_id}:{conversation_id}/notes/{note_id}",
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
    _ensure_conversation_scope(
        db_session,
        actor,
        account_id=account_id,
        conversation_id=conversation_id,
    )
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
    "/{account_id}/{conversation_id}/notes/{note_id}",
    summary="Delete conversation note",
    description="Delete an internal note.",
)
@router.delete(
    "/{account_id}:{conversation_id}/notes/{note_id}",
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
    _ensure_conversation_scope(
        db_session,
        actor,
        account_id=account_id,
        conversation_id=conversation_id,
    )
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

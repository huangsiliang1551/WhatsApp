from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, ConversationNote

logger = structlog.get_logger()


class ConversationNoteService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def create_note(
        self,
        account_id: str,
        conversation_id: str,
        content: str,
        agent_id: str,
        agent_name: str | None = None,
    ) -> dict:
        if not agent_name:
            agent = self._session.execute(
                select(Agent).where(Agent.agent_key == agent_id, Agent.account_id == account_id)
            ).scalar_one_or_none()
            if agent:
                agent_name = agent.display_name

        note = ConversationNote(
            id=str(uuid4()),
            account_id=account_id,
            conversation_id=conversation_id,
            content=content,
            agent_id=agent_id,
            agent_name=agent_name,
        )
        self._session.add(note)
        self._session.commit()

        return {
            "id": note.id,
            "conversation_id": note.conversation_id,
            "account_id": note.account_id,
            "content": note.content,
            "agent_id": note.agent_id,
            "agent_name": note.agent_name,
            "created_at": note.created_at.isoformat() if note.created_at else datetime.now(UTC).isoformat(),
        }

    async def list_notes(
        self,
        account_id: str,
        conversation_id: str,
    ) -> list[dict]:
        rows = self._session.execute(
            select(ConversationNote)
            .where(
                ConversationNote.account_id == account_id,
                ConversationNote.conversation_id == conversation_id,
            )
            .order_by(ConversationNote.created_at.desc())
        ).scalars().all()

        return [
            {
                "id": n.id,
                "conversation_id": n.conversation_id,
                "account_id": n.account_id,
                "content": n.content,
                "agent_id": n.agent_id,
                "agent_name": n.agent_name,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ]

    async def delete_note(
        self,
        note_id: str,
        account_id: str,
        conversation_id: str,
    ) -> None:
        note = self._session.execute(
            select(ConversationNote)
            .where(
                ConversationNote.id == note_id,
                ConversationNote.account_id == account_id,
                ConversationNote.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()
        if note is None:
            raise LookupError(f"Note '{note_id}' not found.")
        self._session.delete(note)
        self._session.commit()

    async def update_note(
        self,
        note_id: str,
        account_id: str,
        conversation_id: str,
        content: str,
    ) -> dict:
        note = self._session.execute(
            select(ConversationNote)
            .where(
                ConversationNote.id == note_id,
                ConversationNote.account_id == account_id,
                ConversationNote.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()
        if note is None:
            raise LookupError(f"Note '{note_id}' not found.")
        note.content = content
        note.updated_at = datetime.now(UTC)
        self._session.commit()

        return {
            "id": note.id,
            "conversation_id": note.conversation_id,
            "account_id": note.account_id,
            "content": note.content,
            "agent_id": note.agent_id,
            "agent_name": note.agent_name,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        }

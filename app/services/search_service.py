from __future__ import annotations

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from app.db.models import Conversation, H5Site, Message, MessageTemplate, Ticket


class SearchResults:
    conversations: list[dict]
    customers: list[dict]
    templates: list[dict]
    tickets: list[dict]


class SearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
        account_id: str | None = None,
        agency_id: str | None = None,
    ) -> dict:
        if not query or not query.strip():
            return {"conversations": [], "customers": [], "templates": [], "tickets": []}

        q = query.strip()
        q_like = f"%{q}%"
        types_set = set(types or ["conversation", "customer", "template", "ticket"])
        result: dict[str, list[dict]] = {
            "conversations": [],
            "customers": [],
            "templates": [],
            "tickets": [],
        }

        # Resolve agency account scope
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
        else:
            agency_account_ids = None

        if "conversation" in types_set:
            stmt = (
                select(Conversation)
                .where(
                    or_(
                        Conversation.external_conversation_id.ilike(q_like),
                        Conversation.customer_id.ilike(q_like),
                    )
                )
                .limit(limit)
            )
            if account_id:
                stmt = stmt.where(Conversation.account_id == account_id)
            if agency_account_ids is not None:
                stmt = stmt.where(Conversation.account_id.in_(agency_account_ids))
            rows = self._session.execute(stmt).scalars().all()
            result["conversations"] = [
                {
                    "id": c.external_conversation_id,
                    "account_id": c.account_id,
                    "customer_id": c.customer_id,
                    "preview": c.external_conversation_id or "",
                    "mode": c.management_mode or "ai_managed",
                    "updated_at": c.updated_at.isoformat() if c.updated_at else "",
                }
                for c in rows
            ]

        if "customer" in types_set:
            from app.db.models import AppUser
            stmt = (
                select(AppUser)
                .where(
                    or_(
                        AppUser.display_name.ilike(q_like),
                        AppUser.public_user_id.ilike(q_like),
                    )
                )
                .limit(limit)
            )
            if account_id:
                stmt = stmt.where(AppUser.account_id == account_id)
            if agency_account_ids is not None:
                stmt = stmt.where(AppUser.account_id.in_(agency_account_ids))
            rows = self._session.execute(stmt).scalars().all()
            result["customers"] = [
                {
                    "id": u.id,
                    "public_user_id": u.public_user_id or "",
                    "display_name": u.display_name or "",
                    "phone": "",
                }
                for u in rows
            ]

        if "template" in types_set:
            stmt = (
                select(MessageTemplate)
                .where(
                    or_(
                        MessageTemplate.name.ilike(q_like),
                        MessageTemplate.category.ilike(q_like),
                    )
                )
                .limit(limit)
            )
            if account_id:
                stmt = stmt.where(MessageTemplate.account_id == account_id)
            if agency_id:
                stmt = stmt.where(
                    (MessageTemplate.agency_id == agency_id) | (MessageTemplate.agency_id.is_(None))
                )
            rows = self._session.execute(stmt).scalars().all()
            result["templates"] = [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status or "",
                    "language": t.language or "",
                }
                for t in rows
            ]

        if "ticket" in types_set:
            stmt = (
                select(Ticket)
                .where(
                    or_(
                        Ticket.title.ilike(q_like),
                        Ticket.ticket_no.ilike(q_like),
                    )
                )
                .limit(limit)
            )
            if account_id:
                stmt = stmt.where(Ticket.account_id == account_id)
            if agency_account_ids is not None:
                stmt = stmt.where(Ticket.account_id.in_(agency_account_ids))
            rows = self._session.execute(stmt).scalars().all()
            result["tickets"] = [
                {
                    "id": t.id,
                    "subject": t.title or "",
                    "status": t.status or "open",
                    "priority": t.priority or "medium",
                }
                for t in rows
            ]

        return result

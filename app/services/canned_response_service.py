from __future__ import annotations

from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CannedResponse

logger = structlog.get_logger()


class CannedResponseService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def list_responses(
        self,
        account_id: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[dict]:
        query = select(CannedResponse)
        if account_id:
            query = query.where(
                (CannedResponse.account_id == account_id) | (CannedResponse.account_id.is_(None))
            )
        if category:
            query = query.where(CannedResponse.category == category)
        if is_active is not None:
            query = query.where(CannedResponse.is_active == is_active)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                CannedResponse.title.ilike(search_term)
                | CannedResponse.content.ilike(search_term)
            )
        query = query.order_by(CannedResponse.category, CannedResponse.title)
        rows = self._session.execute(query).scalars().all()
        return [self._serialize(r) for r in rows]

    async def create_response(
        self,
        account_id: str | None,
        title: str,
        content: str,
        category: str,
        variables: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict:
        resp = CannedResponse(
            id=str(uuid4()),
            account_id=account_id,
            title=title,
            content=content,
            category=category,
            variables=variables or [],
            is_active=True,
            created_by=created_by,
        )
        self._session.add(resp)
        self._session.commit()
        return self._serialize(resp)

    async def update_response(
        self,
        response_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        category: str | None = None,
        variables: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict:
        resp = self._session.execute(
            select(CannedResponse).where(CannedResponse.id == response_id)
        ).scalar_one_or_none()
        if resp is None:
            raise LookupError(f"Canned response '{response_id}' not found.")
        if title is not None:
            resp.title = title
        if content is not None:
            resp.content = content
        if category is not None:
            resp.category = category
        if variables is not None:
            resp.variables = variables
        if is_active is not None:
            resp.is_active = is_active
        self._session.commit()
        return self._serialize(resp)

    async def delete_response(self, response_id: str) -> None:
        resp = self._session.execute(
            select(CannedResponse).where(CannedResponse.id == response_id)
        ).scalar_one_or_none()
        if resp is None:
            raise LookupError(f"Canned response '{response_id}' not found.")
        self._session.delete(resp)
        self._session.commit()

    @staticmethod
    def _serialize(r: CannedResponse) -> dict:
        return {
            "id": r.id,
            "account_id": r.account_id,
            "title": r.title,
            "content": r.content,
            "category": r.category,
            "variables": r.variables or [],
            "is_active": r.is_active,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

"""Deploy history CRUD service."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DeployHistory, H5Site


class DeployHistoryService:
    """Record and query deployment history for H5 sites."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_history(self, site_id: str, limit: int = 50, offset: int = 0, agency_id: str | None = None) -> list[dict]:
        """List deploy history for a site, newest first."""
        query = (
            select(DeployHistory)
            .where(DeployHistory.site_id == site_id)
        )
        if agency_id:
            query = query.join(H5Site, DeployHistory.site_id == H5Site.id).where(H5Site.agency_id == agency_id)
        query = query.order_by(DeployHistory.created_at.desc()).offset(offset).limit(limit)
        return [
            {
                "id": h.id,
                "site_id": h.site_id,
                "action": h.action,
                "status": h.status,
                "details": h.details,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in self._session.scalars(query).all()
        ]

    def create_history(
        self,
        site_id: str,
        action: str,
        status: str,
        details: dict | None = None,
        created_by: str | None = None,
    ) -> dict:
        """Record a new deploy history entry."""
        entry = DeployHistory(
            id=str(uuid4()),
            site_id=site_id,
            action=action,
            status=status,
            details=details or {},
            created_by=created_by,
        )
        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return {
            "id": entry.id,
            "site_id": entry.site_id,
            "action": entry.action,
            "status": entry.status,
            "details": entry.details,
            "created_by": entry.created_by,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }

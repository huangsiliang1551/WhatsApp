from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import H5Site, Notification


class NotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_notification(
        self,
        account_id: str,
        type: str,
        category: str,
        title: str,
        message: str | None = None,
        severity: str = "info",
        user_id: str | None = None,
        action_url: str | None = None,
        metadata: dict | None = None,
    ) -> Notification:
        notification = Notification(
            id=str(uuid4()),
            account_id=account_id,
            user_id=user_id,
            type=type,
            category=category,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            metadata_json=metadata,
        )
        self._session.add(notification)
        self._session.commit()
        return notification

    def list_notifications(
        self,
        account_id: str | None = None,
        user_id: str | None = None,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
        agency_id: str | None = None,
    ) -> tuple[list[Notification], int]:
        query = select(Notification)
        if account_id:
            query = query.where(Notification.account_id == account_id)
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
            query = query.where(Notification.account_id.in_(agency_account_ids))
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        if unread_only:
            query = query.where(Notification.is_read == False)

        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0

        items = (
            self._session.execute(
                query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    def mark_as_read(self, notification_ids: list[str]) -> int:
        from datetime import UTC, datetime
        stmt = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(is_read=True, read_at=datetime.now(UTC).replace(tzinfo=None))
        )
        result = self._session.execute(stmt)
        self._session.commit()
        return result.rowcount

    def mark_all_as_read(self, account_id: str, user_id: str | None = None) -> int:
        from datetime import UTC, datetime
        query = update(Notification).where(
            Notification.account_id == account_id,
            Notification.is_read == False,
        )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        result = self._session.execute(
            query.values(is_read=True, read_at=datetime.now(UTC).replace(tzinfo=None))
        )
        self._session.commit()
        return result.rowcount

    def get_unread_count(self, account_id: str, user_id: str | None = None) -> int:
        query = select(func.count(Notification.id)).where(
            Notification.account_id == account_id,
            Notification.is_read == False,
        )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        return self._session.scalar(query) or 0

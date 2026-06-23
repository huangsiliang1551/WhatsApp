from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MemberNotification, utc_now
from app.schemas.h5_member_messages import (
    H5MemberMessageReadAllResponse,
    H5MemberMessageResponse,
)
from app.services.h5_member_auth_service import H5MemberContext


class H5MemberNotificationService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def list_notifications(
        self,
        *,
        context: H5MemberContext,
    ) -> list[H5MemberMessageResponse]:
        notifications = self._session.scalars(
            select(MemberNotification)
            .where(
                MemberNotification.account_id == context.account_id,
                MemberNotification.user_id == context.user.id,
            )
            .order_by(MemberNotification.created_at.desc(), MemberNotification.id.desc())
        ).all()
        return [self._serialize_notification(item) for item in notifications]

    async def get_notification(
        self,
        *,
        context: H5MemberContext,
        message_id: str,
    ) -> H5MemberMessageResponse:
        notification = self._require_notification(context=context, message_id=message_id)
        return self._serialize_notification(notification)

    async def mark_notification_read(
        self,
        *,
        context: H5MemberContext,
        message_id: str,
    ) -> H5MemberMessageResponse:
        notification = self._require_notification(context=context, message_id=message_id)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = utc_now()
            self._session.add(notification)
            self._session.commit()
            self._session.refresh(notification)
        return self._serialize_notification(notification)

    async def mark_all_notifications_read(
        self,
        *,
        context: H5MemberContext,
    ) -> H5MemberMessageReadAllResponse:
        notifications = self._session.scalars(
            select(MemberNotification).where(
                MemberNotification.account_id == context.account_id,
                MemberNotification.user_id == context.user.id,
                MemberNotification.is_read.is_(False),
            )
        ).all()
        if not notifications:
            return H5MemberMessageReadAllResponse(updated=0)

        now = utc_now()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
            self._session.add(notification)
        self._session.commit()
        return H5MemberMessageReadAllResponse(updated=len(notifications))

    async def count_unread_notifications(
        self,
        *,
        context: H5MemberContext,
    ) -> int:
        notifications = self._session.scalars(
            select(MemberNotification.id).where(
                MemberNotification.account_id == context.account_id,
                MemberNotification.user_id == context.user.id,
                MemberNotification.is_read.is_(False),
            )
        ).all()
        return len(notifications)

    def _require_notification(
        self,
        *,
        context: H5MemberContext,
        message_id: str,
    ) -> MemberNotification:
        notification = self._session.scalars(
            select(MemberNotification).where(
                MemberNotification.id == message_id,
                MemberNotification.account_id == context.account_id,
                MemberNotification.user_id == context.user.id,
            )
        ).first()
        if notification is None:
            raise LookupError(f"Message '{message_id}' was not found.")
        return notification

    @staticmethod
    def _serialize_notification(notification: MemberNotification) -> H5MemberMessageResponse:
        return H5MemberMessageResponse(
            id=notification.id,
            category=notification.category,
            title=notification.title,
            body_text=notification.body_text,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )

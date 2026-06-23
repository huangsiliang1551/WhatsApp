from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_notification_service,
)
from app.schemas.h5_member_messages import (
    H5MemberMessageReadAllResponse,
    H5MemberMessageResponse,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_notification_service import H5MemberNotificationService

router = APIRouter(prefix="/api/h5", tags=["h5-messages"])


@router.get(
    "/messages",
    summary="List H5 messages",
    description="List notifications/messages for the authenticated H5 member.",
    tags=["h5-messages"],
)
async def list_h5_member_messages(
    notification_service: H5MemberNotificationService = Depends(get_h5_member_notification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5MemberMessageResponse]:
    return await notification_service.list_notifications(context=context)


@router.post(
    "/messages/read-all",
    summary="Mark all messages read",
    description="Mark all notifications as read for the authenticated H5 member.",
    tags=["h5-messages"],
)
async def mark_all_h5_member_messages_read(
    notification_service: H5MemberNotificationService = Depends(get_h5_member_notification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberMessageReadAllResponse:
    return await notification_service.mark_all_notifications_read(context=context)


@router.get(
    "/messages/{message_id}",
    summary="Get message detail",
    description="Get a specific notification/message detail for the authenticated H5 member.",
    tags=["h5-messages"],
)
async def get_h5_member_message_detail(
    message_id: str,
    notification_service: H5MemberNotificationService = Depends(get_h5_member_notification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberMessageResponse:
    try:
        return await notification_service.get_notification(context=context, message_id=message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/messages/{message_id}/read",
    summary="Mark message read",
    description="Mark a specific notification as read for the authenticated H5 member.",
    tags=["h5-messages"],
)
async def mark_h5_member_message_read(
    message_id: str,
    notification_service: H5MemberNotificationService = Depends(get_h5_member_notification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberMessageResponse:
    try:
        return await notification_service.mark_notification_read(context=context, message_id=message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

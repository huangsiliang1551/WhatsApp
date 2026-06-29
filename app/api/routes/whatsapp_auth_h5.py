from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings
from app.schemas.whatsapp_auth import (
    WhatsAppAutoBindConsumeRequest,
    WhatsAppAutoBindConsumeResponse,
    WhatsAppAuthConsumeRequest,
    WhatsAppAuthSessionResponse,
    WhatsAppAuthStartRequest,
)
from app.services.h5_member_auth_service import H5AuthError, H5MemberAuthService, H5MemberContext
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSessionError,
    WhatsAppAuthSessionService,
)
from app.services.whatsapp_auto_bind_invite_service import (
    WhatsAppAutoBindError,
    WhatsAppAutoBindInviteService,
)
from app.services.whatsapp_identity_service import WhatsAppBindingConflictError

router = APIRouter(prefix="/api/h5/auth/whatsapp", tags=["h5-whatsapp-auth"])


def _build_service(session: Session, settings: Settings) -> WhatsAppAuthSessionService:
    return WhatsAppAuthSessionService(session=session, settings=settings)


async def _resolve_optional_h5_context(
    *,
    request: Request,
    session: Session,
    settings: Settings,
) -> H5MemberContext | None:
    session_token = request.cookies.get(settings.h5_member_session_cookie_name)
    if not session_token:
        return None
    try:
        return await H5MemberAuthService(session=session, settings=settings).resolve_context(
            session_token=session_token
        )
    except (H5AuthError, LookupError, PermissionError):
        return None


def _serialize_session(model) -> WhatsAppAuthSessionResponse:
    return WhatsAppAuthSessionResponse(
        id=model.id,
        account_id=model.account_id,
        site_id=model.site_id,
        user_id=model.user_id,
        session_type=model.session_type,
        status=model.status,
        selected_waba_id=model.selected_waba_id,
        selected_phone_number_id=model.selected_phone_number_id,
        selected_display_phone_number=model.selected_display_phone_number,
        command_text=model.command_text,
        wa_link=model.wa_link,
        expires_at=model.expires_at,
        confirmed_at=model.confirmed_at,
        failure_code=model.failure_code,
        failure_reason=model.failure_reason,
    )


@router.post("/start", response_model=WhatsAppAuthSessionResponse)
async def start_whatsapp_auth_session(
    payload: WhatsAppAuthStartRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppAuthSessionResponse:
    service = _build_service(session, settings)
    try:
        if payload.session_type == "bind":
            context = await _resolve_optional_h5_context(
                request=request,
                session=session,
                settings=settings,
            )
            if context is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": "auth_required", "message": "H5 member authentication is required."},
                )
            auth_session = service.start_bind_session(site_id=context.site.id, user_id=context.user.id)
        else:
            auth_session = service.start_login_session(site_key=(payload.site_key or "").strip())
    except WhatsAppAuthSessionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    session.refresh(auth_session)
    return _serialize_session(auth_session)


@router.get("/sessions/{session_id}", response_model=WhatsAppAuthSessionResponse)
async def get_whatsapp_auth_session(
    session_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppAuthSessionResponse:
    service = _build_service(session, settings)
    try:
        auth_session = service.get_session(session_id=session_id)
    except WhatsAppAuthSessionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return _serialize_session(auth_session)


@router.post("/sessions/{session_id}/consume", response_model=WhatsAppAuthSessionResponse)
async def consume_whatsapp_auth_session(
    session_id: str,
    payload: WhatsAppAuthConsumeRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppAuthSessionResponse:
    service = _build_service(session, settings)
    try:
        auth_session = service.consume_auth_command(
            command_text=payload.command_text,
            wa_id=payload.wa_id,
            inbound_phone_number_id=payload.inbound_phone_number_id,
            inbound_waba_id=payload.inbound_waba_id,
            inbound_message_id=payload.inbound_message_id,
        )
    except WhatsAppBindingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except WhatsAppAuthSessionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    if auth_session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "session_mismatch", "message": "Command token does not match the requested session."},
        )
    session.commit()
    session.refresh(auth_session)
    return _serialize_session(auth_session)


@router.post("/auto-bind/consume", response_model=WhatsAppAutoBindConsumeResponse)
async def consume_whatsapp_auto_bind_invite(
    payload: WhatsAppAutoBindConsumeRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppAutoBindConsumeResponse:
    context = await _resolve_optional_h5_context(
        request=request,
        session=session,
        settings=settings,
    )
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth_required", "message": "H5 member authentication is required."},
        )
    service = WhatsAppAutoBindInviteService(session=session, settings=settings)
    try:
        invite = service.consume_invite(
            token=payload.token,
            current_user_id=context.user.id,
            current_site_id=context.site.id,
        )
    except WhatsAppBindingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except WhatsAppAutoBindError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return WhatsAppAutoBindConsumeResponse(
        status="bound",
        site_id=invite.site_id,
        public_user_id=context.user.public_user_id,
        wa_id=invite.wa_id,
        invite_id=invite.id,
    )

from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from structlog.contextvars import bind_contextvars
from sqlalchemy.orm import Session

from app.core.auth import (
    ACTOR_ACCOUNT_IDS_HEADER,
    ACTOR_ID_HEADER,
    ACTOR_NAME_HEADER,
    ACTOR_ROLE_HEADER,
    RequestActor,
    ActorRole,
    build_local_dev_actor,
    parse_account_ids,
)
from app.core.permission_resolution import get_builtin_role_permissions, resolve_role_permissions
from app.core.settings import Settings, get_settings
from app.db.session import get_sessionmaker
from app.providers.factory import (
    get_ecommerce_provider,
    get_messaging_provider,
    get_meta_management_provider,
    get_template_registry_provider,
)
from app.providers.task_proof_storage.base import TaskProofStorageProvider
from app.providers.task_proof_storage.local_provider import LocalTaskProofStorageProvider
from app.services.conversation_service import ConversationService
from app.services.ecommerce_service import EcommerceService
from app.services.h5_member_auth_service import H5MemberAuthService, H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from app.services.h5_member_fragment_service import H5MemberFragmentService
from app.services.h5_member_notification_service import H5MemberNotificationService
from app.services.h5_member_verification_service import H5MemberVerificationService
from app.services.h5_member_whatsapp_binding_service import H5MemberWhatsAppBindingService
from app.services.launch_readiness_service import LaunchReadinessService
from app.services.media_asset_service import MediaAssetService
from app.services.meta_account_registry import MetaAccountRegistry
from app.services.platform_member_whatsapp_binding_service import PlatformMemberWhatsAppBindingService
from app.services.platform_member_verification_service import PlatformMemberVerificationService
from app.services.platform_service import PlatformService
from app.services.platform_withdrawal_service import PlatformWithdrawalService
from app.providers.messaging.base import MessagingProvider
from app.providers.meta_management.base import MetaManagementProvider
from app.services.queue_service import QueueService
from app.services.support_knowledge_service import SupportKnowledgeService
from app.services.task_service import TaskService
from app.services.template_service import TemplateService
from app.providers.template_registry.base import TemplateRegistryProvider
from app.providers.translation.factory import get_translation_provider
from app.services.runtime_state import RuntimeStateStore
from app.services.review_service import ReviewService
from app.services.task_proof_storage_service import TaskProofStorageService
from app.services.task_submission_service import TaskSubmissionService
from app.services.translation_service import TranslationService
from app.services.ticket_service import TicketService
from app.services.whatsapp_analytics_service import WhatsAppAnalyticsService


SessionFactory = Callable[[], Session]


def get_db_session_factory() -> SessionFactory:
    """Return a session factory callable (overridable in tests).

    SSE endpoints that create fresh sessions in async generators
    must use this instead of ``get_sessionmaker()`` directly so that
    tests can inject their own SQLite file-backed factory.
    """
    return get_sessionmaker()


def get_db_session() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session_with_isolation(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Generator[Session, None, None]:
    """Get DB session with automatic data isolation filtering.

    For agent/agent_member users (JWT-authenticated), this stores the
    agency_id on request.state so routes can apply filters.
    """
    session = get_sessionmaker()()
    try:
        # Check if this is an agent request via JWT (Authorization header)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            from app.api.routes.agent_auth import _decode_agent_jwt

            token = auth_header[7:]
            payload = _decode_agent_jwt(token, settings.admin_jwt_secret)
            if payload and payload.get("user_type") in ("agent", "agent_member"):
                from app.core.agent_middleware import AgentDataIsolationMiddleware

                # Store middleware on request.state for route use
                request.state.agent_isolation = AgentDataIsolationMiddleware(
                    session, payload.get("sub", ""),
                )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _build_request_actor(
    request: Request,
    settings: Settings,
    session: Session,
    *,
    require_bearer_token: bool,
) -> RequestActor:
    auth_header = request.headers.get("Authorization", "")
    token_present = auth_header.startswith("Bearer ")
    actor_id = None if token_present else request.headers.get(ACTOR_ID_HEADER)
    role_value = None if token_present else request.headers.get(ACTOR_ROLE_HEADER)
    display_name = None if token_present else request.headers.get(ACTOR_NAME_HEADER)
    account_scope = None if token_present else request.headers.get(ACTOR_ACCOUNT_IDS_HEADER)

    # Decode JWT to extract agency_id and verify role
    agency_id = None
    jwt_user_type: str | None = None
    jwt_subject: str | None = None
    permission_role: str | None = None
    jwt_payload: dict[str, Any] | None = None
    if token_present:
        token = auth_header[7:]
        from app.api.routes.agent_auth import _decode_agent_jwt

        jwt_payload = _decode_agent_jwt(token, settings.admin_jwt_secret)
        if jwt_payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            )

        agency_id = jwt_payload.get("agency_id")
        jwt_subject = jwt_payload.get("sub")
        jwt_user_type = jwt_payload.get("user_type") or jwt_payload.get("role")
        permission_role = jwt_payload.get("role")
        display_name = (
            jwt_payload.get("display_name")
            or jwt_payload.get("username")
            or jwt_subject
        )
        actor_id = str(jwt_subject) if jwt_subject is not None else None
        if isinstance(jwt_payload.get("account_ids"), list):
            account_scope = ",".join(str(value) for value in jwt_payload.get("account_ids", []))

        # JWT 解码成功后，身份以 JWT 为准，不信任 header actor/role
        if jwt_user_type:
            jwt_role_map = {
                "super_admin": "super_admin",
                "admin": "super_admin",
                "agent": "agent",
                "agent_member": "agent_member",
            }
            mapped_role = jwt_role_map.get(jwt_user_type)
            if mapped_role is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Unsupported JWT user_type '{jwt_user_type}'.",
                )
            role_value = mapped_role
    elif require_bearer_token and settings.auth_required:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required.",
        )

    if not actor_id or not role_value:
        if settings.test_mode or not settings.auth_required:
            actor = build_local_dev_actor()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"Missing request actor headers. Expected '{ACTOR_ID_HEADER}' "
                    f"and '{ACTOR_ROLE_HEADER}'."
                ),
            )
    else:
        try:
            role = ActorRole(role_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported actor role '{role_value}'.",
            ) from exc
        actor = RequestActor(
            actor_id=actor_id,
            display_name=display_name,
            role=role,
            account_ids=parse_account_ids(account_scope),
            agency_id=agency_id,
            permission_role=permission_role,
            resolved_permissions=get_builtin_role_permissions(role),
        )

        # Fill account_ids from H5Site when agency_id is available but account_ids is empty
        if agency_id and not actor.account_ids:
            from app.db.models import H5Site
            from sqlalchemy import select
            ids = list(session.scalars(
                select(H5Site.account_id).where(
                    H5Site.agency_id == agency_id,
                    H5Site.account_id.isnot(None),
                ).distinct()
            ).all())
            if ids:
                actor.account_ids = ids

        if (
            agency_id
            and jwt_user_type in {"agent", "agent_member"}
            and role in {ActorRole.AGENT, ActorRole.AGENT_MEMBER}
        ):
            if role == ActorRole.AGENT_MEMBER and jwt_subject:
                from app.db.models import AgencyMember, Agent
                from sqlalchemy import select

                agent_row = session.execute(
                    select(Agent).where(
                        Agent.id == jwt_subject,
                        Agent.user_type == "agent_member",
                    )
                ).scalar_one_or_none()
                if agent_row is None or not agent_row.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found or inactive.",
                    )

                db_role = session.execute(
                    select(AgencyMember.role).where(
                        AgencyMember.agency_id == agency_id,
                        AgencyMember.user_id == jwt_subject,
                    )
                ).scalar_one_or_none()
                if db_role is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Agency membership not found for this token.",
                    )
                actor.permission_role = db_role

            dynamic_permissions = resolve_role_permissions(
                session,
                user_type=jwt_user_type,
                agency_id=agency_id,
                role_name=actor.permission_role,
            )
            if dynamic_permissions is not None:
                actor.resolved_permissions = dynamic_permissions
                actor.permissions_source = "dynamic"

    request.state.request_actor = actor
    bind_contextvars(actor_id=actor.actor_id, actor_role=actor.role.value)
    return actor


def require_permission(permission_code: str):
    def dependency(actor: RequestActor = Depends(get_request_actor)) -> RequestActor:
        actor.require_permission(permission_code)
        return actor

    return dependency


def get_request_actor(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> RequestActor:
    return _build_request_actor(
        request,
        settings,
        session,
        require_bearer_token=False,
    )


def get_strict_request_actor(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
) -> RequestActor:
    return _build_request_actor(
        request,
        settings,
        session,
        require_bearer_token=True,
    )


def get_runtime_state_service(session: Session = Depends(get_db_session)) -> RuntimeStateStore:
    return RuntimeStateStore(session)


def get_translation_service(settings: Settings = Depends(get_settings)) -> TranslationService:
    return TranslationService(
        settings=settings,
        provider=get_translation_provider(settings),
    )


def get_queue_service(settings: Settings = Depends(get_settings)) -> QueueService:
    return QueueService(settings)


def get_messaging_service(settings: Settings = Depends(get_settings)) -> MessagingProvider:
    return get_messaging_provider(settings)


def get_meta_management_service(
    settings: Settings = Depends(get_settings),
) -> MetaManagementProvider:
    return get_meta_management_provider(settings)


def get_template_registry_service(
    settings: Settings = Depends(get_settings),
) -> TemplateRegistryProvider:
    return get_template_registry_provider(settings)


def get_support_knowledge_service(
    session: Session = Depends(get_db_session),
) -> SupportKnowledgeService:
    return SupportKnowledgeService(session=session)


def get_meta_account_registry(
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    settings: Settings = Depends(get_settings),
    meta_management_provider: MetaManagementProvider = Depends(get_meta_management_service),
) -> MetaAccountRegistry:
    return MetaAccountRegistry(
        session=session,
        runtime_state=runtime_state,
        settings=settings,
        meta_management_provider=meta_management_provider,
    )


def get_launch_readiness_service(
    settings: Settings = Depends(get_settings),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
) -> LaunchReadinessService:
    return LaunchReadinessService(
        settings=settings,
        runtime_state=runtime_state,
        meta_account_registry=meta_account_registry,
    )


def get_conversation_service(
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    settings: Settings = Depends(get_settings),
    messaging_provider: MessagingProvider = Depends(get_messaging_service),
) -> ConversationService:
    return ConversationService(
        runtime_state=runtime_state,
        translation_service=translation_service,
        settings=settings,
        messaging_provider=messaging_provider,
    )


def get_template_service(
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    messaging_provider: MessagingProvider = Depends(get_messaging_service),
    template_registry_provider: TemplateRegistryProvider = Depends(get_template_registry_service),
) -> TemplateService:
    return TemplateService(
        session=session,
        runtime_state=runtime_state,
        translation_service=translation_service,
        messaging_provider=messaging_provider,
        template_registry_provider=template_registry_provider,
    )


def get_media_asset_service(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_db_session),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    messaging_provider: MessagingProvider = Depends(get_messaging_service),
) -> MediaAssetService:
    return MediaAssetService(
        storage_root=settings.media_storage_root,
        session=session,
        runtime_state=runtime_state,
        translation_service=translation_service,
        messaging_provider=messaging_provider,
    )


def get_whatsapp_analytics_service(
    session: Session = Depends(get_db_session),
) -> WhatsAppAnalyticsService:
    return WhatsAppAnalyticsService(session=session)


def get_platform_service(
    session: Session = Depends(get_db_session),
) -> PlatformService:
    return PlatformService(session=session)


def get_platform_member_verification_service(
    session: Session = Depends(get_db_session),
) -> PlatformMemberVerificationService:
    return PlatformMemberVerificationService(session=session)


def get_platform_member_whatsapp_binding_service(
    session: Session = Depends(get_db_session),
) -> PlatformMemberWhatsAppBindingService:
    return PlatformMemberWhatsAppBindingService(session=session)


def get_platform_withdrawal_service(
    session: Session = Depends(get_db_session),
) -> PlatformWithdrawalService:
    return PlatformWithdrawalService(session=session)


def get_task_service(
    session: Session = Depends(get_db_session),
) -> TaskService:
    return TaskService(session=session)


def get_h5_member_auth_service(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> H5MemberAuthService:
    return H5MemberAuthService(session=session, settings=settings)


def get_h5_member_commerce_service(
    session: Session = Depends(get_db_session),
) -> H5MemberCommerceService:
    return H5MemberCommerceService(session=session)


def get_h5_member_notification_service(
    session: Session = Depends(get_db_session),
) -> H5MemberNotificationService:
    return H5MemberNotificationService(session=session)


def get_h5_member_verification_service(
    session: Session = Depends(get_db_session),
) -> H5MemberVerificationService:
    return H5MemberVerificationService(session=session)


def get_h5_member_fragment_service(
    session: Session = Depends(get_db_session),
) -> H5MemberFragmentService:
    return H5MemberFragmentService(session=session)


def get_h5_member_whatsapp_binding_service(
    session: Session = Depends(get_db_session),
) -> H5MemberWhatsAppBindingService:
    return H5MemberWhatsAppBindingService(session=session)


async def get_current_h5_member_context(
    request: Request,
    auth_service: H5MemberAuthService = Depends(get_h5_member_auth_service),
    settings: Settings = Depends(get_settings),
) -> H5MemberContext:
    session_token = request.cookies.get(settings.h5_member_session_cookie_name)
    try:
        return await auth_service.resolve_context(session_token=session_token)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="H5 member authentication is required.",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def get_task_proof_storage_provider(
    settings: Settings = Depends(get_settings),
) -> TaskProofStorageProvider:
    proof_root = Path(settings.task_proof_storage_root).expanduser()
    return LocalTaskProofStorageProvider(str(proof_root))


def get_task_proof_storage_service(
    session: Session = Depends(get_db_session),
    proof_storage_provider: TaskProofStorageProvider = Depends(get_task_proof_storage_provider),
) -> TaskProofStorageService:
    return TaskProofStorageService(
        session=session,
        provider=proof_storage_provider,
    )


def get_task_submission_service(
    session: Session = Depends(get_db_session),
    proof_storage_service: TaskProofStorageService = Depends(get_task_proof_storage_service),
) -> TaskSubmissionService:
    return TaskSubmissionService(
        session=session,
        proof_storage_service=proof_storage_service,
    )


def get_review_service(
    session: Session = Depends(get_db_session),
    task_submission_service: TaskSubmissionService = Depends(get_task_submission_service),
) -> ReviewService:
    return ReviewService(
        session=session,
        submission_service=task_submission_service,
    )


def get_ticket_service(
    session: Session = Depends(get_db_session),
) -> TicketService:
    return TicketService(session=session)


def get_ecommerce_service(
    settings: Settings = Depends(get_settings),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
) -> EcommerceService:
    return EcommerceService(
        provider=get_ecommerce_provider(settings),
        runtime_state=runtime_state,
    )

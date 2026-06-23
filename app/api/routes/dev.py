from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_queue_service,
    get_request_actor,
    get_runtime_state_service,
    get_translation_service,
)
from app.core.auth import RequestActor
from app.core.metrics import message_processing_failures_total
from app.core.settings import Settings, get_settings
from app.schemas.mock_message import MockInboundMessage
from app.services.chat import handle_mock_inbound_message
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.services.translation_service import TranslationService

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post(
    "/mock/inbound-message",
    summary="Mock inbound message",
    description="Simulates an inbound WhatsApp message for testing. Disabled in production.",
    tags=["dev"],
)
async def mock_inbound_message(
    payload: MockInboundMessage,
    settings: Settings = Depends(get_settings),
    runtime_state_store: RuntimeStateStore = Depends(get_runtime_state_service),
    translation_service: TranslationService = Depends(get_translation_service),
    queue_service: QueueService = Depends(get_queue_service),
    actor: RequestActor = Depends(get_request_actor),
) -> dict[str, object]:
    actor.require_permission("dev.mock")
    if settings.app_env == "production" and not settings.test_mode:
        raise HTTPException(status_code=403, detail="Mock inbound endpoint is disabled in production.")
    actor.require_account_access(payload.account_id)
    try:
        return await handle_mock_inbound_message(
            payload=payload,
            settings=settings,
            runtime_state_store=runtime_state_store,
            translation_service=translation_service,
            queue_service=queue_service,
        )
    except ValueError as exc:
        message_processing_failures_total.labels(
            provider="mock",
            stage="mock_inbound",
        ).inc()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        message_processing_failures_total.labels(
            provider="mock",
            stage="mock_inbound",
        ).inc()
        raise

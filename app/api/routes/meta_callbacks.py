from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_meta_account_registry
from app.providers.meta_management.base import MetaManagementProviderError
from app.schemas.meta_accounts import EmbeddedSignupCallbackRequest
from app.services.meta_account_registry import MetaAccountConflictError, MetaAccountRegistry

router = APIRouter(prefix="/webhooks/meta/embedded-signup", tags=["meta-callbacks"])


@router.post(
    "/session/{session_id}",
    summary="Embedded signup callback",
    description="Receives Meta embedded signup callback for a WABA session.",
    tags=["meta-callbacks"],
)
async def receive_embedded_signup_callback(
    session_id: str,
    payload: EmbeddedSignupCallbackRequest,
    meta_account_registry: MetaAccountRegistry = Depends(get_meta_account_registry),
) -> dict[str, object]:
    try:
        session = (
            await meta_account_registry.ingest_embedded_signup_callback(
                session_id=session_id,
                payload=payload,
                actor_type="system",
                actor_id=None,
                require_launch_state=True,
            )
        )
        response = session.model_dump()
        response["launch_context"] = None
        return response
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetaAccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MetaManagementProviderError as exc:
        status_code = 502
        if exc.remote_status_code is not None and 400 <= exc.remote_status_code < 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

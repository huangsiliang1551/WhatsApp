"""
AIP-003: API routes for AI Provider Configuration management.

11 endpoints supporting full CRUD, reorder, test connection, and account overrides.
All endpoints require SETTINGS_READ or SETTINGS_MANAGE permissions.
IMPORTANT: Static paths (/reorder, /account-overrides) must be declared
before parameterized paths (/{config_id}) to avoid route conflicts.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_actor, require_permission
from app.core.auth import RequestActor
from app.db.models import AccountAIProviderOverride as AccountAIProviderOverrideModel
from app.schemas.ai_providers import (
    AIProviderConfigResponse,
    AccountAIProviderOverrideResponse,
    CreateAIProviderConfigRequest,
    UpdateAIProviderConfigRequest,
    ReorderRequest,
    SetAccountOverrideRequest,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.ai_provider_config_service import AIProviderConfigService

router = APIRouter(prefix="/api/ai-providers", tags=["ai-providers"])


def _to_config_response(config) -> AIProviderConfigResponse:
    return AIProviderConfigResponse(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type,
        api_base_url=config.api_base_url,
        has_api_key=bool(config.api_key_encrypted),
        model=config.model,
        priority=config.priority,
        is_enabled=config.is_enabled,
        timeout_seconds=config.timeout_seconds,
        use_responses_api=config.use_responses_api,
        metadata_json=config.metadata_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _get_service(session: Session = Depends(get_db_session)) -> AIProviderConfigService:
    return AIProviderConfigService(session)


# ── List / Create (no path params) ──────────────────────────────────────


@router.get("")
async def list_providers(
    include_disabled: bool = False,
    actor: RequestActor = Depends(require_permission("ai_providers.view")),
    service: AIProviderConfigService = Depends(_get_service),
) -> list[AIProviderConfigResponse]:
    configs = service.list_configs(include_disabled=include_disabled)
    return [_to_config_response(c) for c in configs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: CreateAIProviderConfigRequest,
    actor: RequestActor = Depends(require_permission("ai_providers.create")),
    service: AIProviderConfigService = Depends(_get_service),
) -> AIProviderConfigResponse:
    config = service.create_config(data)
    return _to_config_response(config)


# ── Static paths (must be before /{config_id}) ──────────────────────────


@router.put("/reorder")
async def reorder_providers(
    data: ReorderRequest,
    actor: RequestActor = Depends(require_permission("ai_providers.edit")),
    service: AIProviderConfigService = Depends(_get_service),
) -> dict:
    try:
        service.reorder_configs(data.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/account-overrides")
async def list_account_overrides(
    actor: RequestActor = Depends(require_permission("ai_providers.view")),
    service: AIProviderConfigService = Depends(_get_service),
) -> list[AccountAIProviderOverrideResponse]:
    configs = service.list_configs(include_disabled=True)
    config_map = {c.id: c for c in configs}
    stmt = select(AccountAIProviderOverrideModel).where(
        AccountAIProviderOverrideModel.is_active.is_(True)
    )
    session = service._session
    overrides = list(session.scalars(stmt).all())
    results: list[AccountAIProviderOverrideResponse] = []
    for ov in overrides:
        cfg = config_map.get(ov.provider_config_id)
        results.append(
            AccountAIProviderOverrideResponse(
                account_id=ov.account_id,
                provider_config_id=ov.provider_config_id,
                provider_name=cfg.name if cfg else None,
                model=cfg.model if cfg else None,
                is_active=ov.is_active,
            )
        )
    return results


@router.put("/account-overrides/{account_id}")
async def set_account_override(
    account_id: str,
    data: SetAccountOverrideRequest,
    actor: RequestActor = Depends(require_permission("ai_providers.override")),
    service: AIProviderConfigService = Depends(_get_service),
) -> AccountAIProviderOverrideResponse:
    try:
        override = service.set_account_override(account_id, data.provider_config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        cfg = service.get_config(data.provider_config_id)
        provider_name = cfg.name
        model = cfg.model
    except ValueError:
        provider_name = None
        model = None
    return AccountAIProviderOverrideResponse(
        account_id=override.account_id,
        provider_config_id=override.provider_config_id,
        provider_name=provider_name,
        model=model,
        is_active=override.is_active,
    )


@router.delete("/account-overrides/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_account_override(
    account_id: str,
    actor: RequestActor = Depends(require_permission("ai_providers.override")),
    service: AIProviderConfigService = Depends(_get_service),
) -> None:
    service.clear_account_override(account_id)


# ── Parameterized paths (/{config_id}) ──────────────────────────────────


@router.get("/{config_id}")
async def get_provider(
    config_id: str,
    actor: RequestActor = Depends(require_permission("ai_providers.view")),
    service: AIProviderConfigService = Depends(_get_service),
) -> AIProviderConfigResponse:
    try:
        config = service.get_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_config_response(config)


@router.patch("/{config_id}")
async def update_provider(
    config_id: str,
    data: UpdateAIProviderConfigRequest,
    actor: RequestActor = Depends(require_permission("ai_providers.edit")),
    service: AIProviderConfigService = Depends(_get_service),
) -> AIProviderConfigResponse:
    try:
        config = service.update_config(config_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_config_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    config_id: str,
    actor: RequestActor = Depends(require_permission("ai_providers.delete")),
    service: AIProviderConfigService = Depends(_get_service),
) -> None:
    try:
        service.delete_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{config_id}/test")
async def test_provider_connection(
    config_id: str,
    request_body: TestConnectionRequest,
    actor: RequestActor = Depends(require_permission("ai_providers.test")),
    service: AIProviderConfigService = Depends(_get_service),
) -> TestConnectionResponse:
    request_body.config_id = config_id
    return await service.test_connection(request_body)

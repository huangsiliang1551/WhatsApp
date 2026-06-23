"""API routes for Translation Provider Configuration management.

Supports CRUD, test connection. Static path (/test) declared before parameterized paths.
"""

import asyncio
import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_actor, require_permission
from app.core.auth import RequestActor
from app.db.models import TranslationProviderConfig
from app.schemas.translation_providers import (
    TranslationProviderConfigResponse,
    CreateTranslationProviderConfigRequest,
    UpdateTranslationProviderConfigRequest,
    TestConnectionRequest,
    TestConnectionResponse,
    RegionPingRequest,
    RegionPingResponse,
    RegionPingResult,
    TMTRegionInfo,
)
from app.services.translation_provider_config_service import TranslationProviderConfigService

router = APIRouter(prefix="/api/translation-providers", tags=["translation-providers"])


def _to_config_response(config: TranslationProviderConfig) -> TranslationProviderConfigResponse:
    return TranslationProviderConfigResponse(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type,
        region=config.region,
        has_secret=bool(config.secret_id_encrypted and config.secret_key_encrypted),
        priority=config.priority,
        is_enabled=config.is_enabled,
        timeout_seconds=config.timeout_seconds,
        metadata_json=config.metadata_json,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _get_service(session: Session = Depends(get_db_session)) -> TranslationProviderConfigService:
    return TranslationProviderConfigService(session)


# ── List / Create ──


@router.get("")
async def list_providers(
    include_disabled: bool = False,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> list[TranslationProviderConfigResponse]:
    configs = service.list_configs(include_disabled=include_disabled)
    return [_to_config_response(c) for c in configs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: CreateTranslationProviderConfigRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> TranslationProviderConfigResponse:
    config = service.create_config(data)
    return _to_config_response(config)


# ── TMT Regions & Ping ──
# IMPORTANT: Static paths must be declared BEFORE parameterized paths (/{config_id})
# to prevent FastAPI from matching "regions"/"ping-regions" as config_id values.


@router.get("/regions")
async def list_tmt_regions() -> list[TMTRegionInfo]:
    """Return the list of supported TMT regions."""
    from app.providers.translation.tencent_provider import TencentCloudTranslationProvider

    return [TMTRegionInfo(**r) for r in TencentCloudTranslationProvider.get_supported_regions()]


@router.post("/ping-regions")


async def ping_tmt_regions(
    request_body: RegionPingRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> RegionPingResponse:
    """Ping all TMT regions to test latency, returning sorted results."""
    from app.core.encryption import decrypt_key
    from app.providers.translation.tencent_tmt_errors import TMT_REGIONS

    secret_id: str | None = None
    secret_key: str | None = None
    timeout = request_body.timeout_seconds

    if request_body.config_id:
        config = service.get_config(request_body.config_id)
        if config.secret_id_encrypted:
            secret_id = decrypt_key(config.secret_id_encrypted)
        if config.secret_key_encrypted:
            secret_key = decrypt_key(config.secret_key_encrypted)
    else:
        secret_id = request_body.secret_id
        secret_key = request_body.secret_key

    if not secret_id or not secret_key:
        return RegionPingResponse(results=[])

    async def _ping_region(region_info: dict) -> RegionPingResult:
        region = region_info["region"]
        label = region_info["label"]
        endpoint = region_info["endpoint"]

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Make a lightweight OPTIONS or GET request to measure TCP latency
                # Use the TMT endpoint to check connectivity
                resp = await client.get(f"https://{endpoint}/", timeout=timeout)
                elapsed = int((time.monotonic() - start) * 1000)
                # Even a non-200 response means the endpoint is reachable
                if resp.status_code >= 100:
                    return RegionPingResult(
                        region=region,
                        label=label,
                        latency_ms=elapsed,
                        status="ok",
                    )
                else:
                    return RegionPingResult(
                        region=region,
                        label=label,
                        latency_ms=elapsed,
                        status="error",
                        error=f"HTTP {resp.status_code}",
                    )
        except httpx.TimeoutException:
            return RegionPingResult(
                region=region,
                label=label,
                status="timeout",
                error="连接超时",
            )
        except Exception as exc:
            return RegionPingResult(
                region=region,
                label=label,
                status="error",
                error=str(exc)[:200],
            )

    # Ping all regions concurrently
    tasks = [_ping_region(r) for r in TMT_REGIONS]
    results = await asyncio.gather(*tasks)

    # Sort by latency (fastest first), errors at the end
    results.sort(key=lambda r: (
        1 if r.status != "ok" else 0,
        r.latency_ms or 99999,
    ))

    return RegionPingResponse(results=results)


# ── Per-config paths ──


@router.get("/{config_id}")
async def get_provider(
    config_id: str,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> TranslationProviderConfigResponse:
    try:
        config = service.get_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_config_response(config)


@router.patch("/{config_id}")
async def update_provider(
    config_id: str,
    data: UpdateTranslationProviderConfigRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> TranslationProviderConfigResponse:
    try:
        config = service.update_config(config_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_config_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    config_id: str,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> None:
    try:
        service.delete_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ── Test Connection ──


@router.post("/{config_id}/test")
async def test_provider_connection(
    config_id: str,
    request_body: TestConnectionRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    service: TranslationProviderConfigService = Depends(_get_service),
) -> TestConnectionResponse:
    request_body.config_id = config_id
    return await _run_test_connection(request_body, service)


async def _run_test_connection(
    request: TestConnectionRequest,
    service: TranslationProviderConfigService,
) -> TestConnectionResponse:
    """Execute a test translation via Tencent Cloud TMT API."""
    from app.core.encryption import decrypt_key

    secret_id: str | None = None
    secret_key: str | None = None
    region: str | None = None
    timeout: int = request.timeout_seconds

    if request.config_id:
        config = service.get_config(request.config_id)
        if config.secret_id_encrypted:
            secret_id = decrypt_key(config.secret_id_encrypted)
        if config.secret_key_encrypted:
            secret_key = decrypt_key(config.secret_key_encrypted)
        region = config.region or "ap-guangzhou"
        timeout = config.timeout_seconds
    else:
        secret_id = request.secret_id
        secret_key = request.secret_key
        region = request.region or "ap-guangzhou"

    if not secret_id or not secret_key:
        return TestConnectionResponse(
            status="error",
            error_type="auth_failed",
            message="SecretId and SecretKey are required.",
        )

    # Build the Tencent Cloud TMT provider and test
    from app.providers.translation.tencent_provider import TencentCloudTranslationProvider

    provider = TencentCloudTranslationProvider(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        timeout_seconds=timeout,
    )

    start = time.monotonic()
    try:
        result = await provider.translate_text("Hello", "en", "zh")
        elapsed = int((time.monotonic() - start) * 1000)
        return TestConnectionResponse(
            status="ok",
            latency_ms=elapsed,
            source_text="Hello",
            translated_text=result,
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        # Try to extract error code from the exception message
        err_msg = str(exc)
        err_code: str | None = None
        friendly_msg: str | None = None

        from app.providers.translation.tencent_tmt_errors import (
            get_tmt_error_prompt,
            get_tmt_error_prompt_with_code,
        )

        # Parse error code from various error message formats
        if "error:" in err_msg:
            # Format: "Tencent Cloud TMT error: ErrorCode - ErrorMsg. FriendlyMsg"
            parts = err_msg.split("error:")[1].strip()
            code_part = parts.split("-")[0].strip()
            if code_part:
                err_code = code_part
                friendly_msg = get_tmt_error_prompt_with_code(err_code)
        elif "[" in err_msg and "]" in err_msg:
            start_idx = err_msg.find("[")
            end_idx = err_msg.find("]")
            if start_idx >= 0 and end_idx > start_idx:
                err_code = err_msg[start_idx + 1:end_idx]
                friendly_msg = get_tmt_error_prompt_with_code(err_code)

        return TestConnectionResponse(
            status="error",
            latency_ms=elapsed,
            error_type="request",
            error_code=err_code,
            error_friendly_message=friendly_msg,
            message=str(exc),
        )

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_media_asset_service, get_runtime_state_service, require_permission
from app.core.auth import RequestActor
from app.schemas.media_assets import (
    MediaAssetCreateRequest,
    MediaAssetDetailResponse,
    MediaAssetSyncRequest,
    MediaAssetSyncResponse,
    MediaAssetType,
    MediaAssetUpdateRequest,
    MediaAssetView,
)
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.media_asset_service import MediaAssetService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/media/assets", tags=["media-assets"])


def _raise_media_route_value_error(exc: ValueError) -> None:
    detail = str(exc)
    if ("access_token" in detail and "requires" in detail) or "access token" in detail.lower():
        raise HTTPException(status_code=503, detail=detail) from exc
    raise HTTPException(status_code=409, detail=detail) from exc


def _require_existing_account(
    *,
    account_id: str | None,
    actor: RequestActor,
    runtime_state: RuntimeStateStore,
) -> None:
    if account_id is None:
        return
    actor.require_account_access(account_id)
    if runtime_state.get_account_model(account_id) is None:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' was not found.")


@router.get(
    "",
    summary="List media assets",
    description="List media assets with optional filters for account, WABA, type, and tags.",
    tags=["media-assets"],
)
async def list_media_assets(
    account_id: str | None = None,
    waba_id: str | None = None,
    phone_number_id: str | None = None,
    asset_type: MediaAssetType | None = None,
    is_active: bool | None = True,
    query: str | None = None,
    tag: str | None = None,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("media.view")),
) -> list[MediaAssetView]:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await media_asset_service.list_assets(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            asset_type=asset_type,
            is_active=is_active,
            query=query,
            tag=tag,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "",
    summary="Create media asset",
    description="Create a new media asset record.",
    tags=["media-assets"],
)
async def create_media_asset(
    payload: MediaAssetCreateRequest,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("media.upload")),
) -> MediaAssetView:
    _require_existing_account(account_id=payload.account_id, actor=actor, runtime_state=runtime_state)
    try:
        return await media_asset_service.create_asset(
            payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=payload.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="media_asset.create",
        target_type="media_asset",
        target_id=None,
        payload={"name": payload.name, "asset_type": payload.asset_type},
    )


@router.post(
    "/upload",
    summary="Upload media asset",
    description="Upload a media file and create an asset record.",
    tags=["media-assets"],
)
async def upload_media_asset(
    file: UploadFile = File(...),
    account_id: str = Form(...),
    waba_id: str | None = Form(default=None),
    phone_number_id: str | None = Form(default=None),
    name: str | None = Form(default=None),
    asset_type: MediaAssetType | None = Form(default=None),
    mime_type: str | None = Form(default=None),
    source: str | None = Form(default=None),
    tags: list[str] | None = Form(default=None),
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("media.upload")),
) -> MediaAssetView:
    _require_existing_account(account_id=account_id, actor=actor, runtime_state=runtime_state)
    try:
        file_bytes = await file.read()
        return await media_asset_service.upload_asset_file(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            name=name,
            asset_type=asset_type,
            mime_type=mime_type,
            source=source,
            tags=tags or [],
            file_name=file.filename,
            content_type=file.content_type,
            file_bytes=file_bytes,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        await file.close()

    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="media_asset.upload",
        target_type="media_asset",
        target_id=None,
        payload={"file_name": file.filename, "asset_type": str(asset_type) if asset_type else None},
    )


@router.get(
    "/{asset_id}",
    summary="Get media asset detail",
    description="Get detailed information about a specific media asset.",
    tags=["media-assets"],
)
async def get_media_asset_detail(
    asset_id: str,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    actor: RequestActor = Depends(require_permission("media.view")),
) -> MediaAssetDetailResponse:
    try:
        return await media_asset_service.get_asset_detail(
            asset_id=asset_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch(
    "/{asset_id}",
    summary="Update media asset",
    description="Update an existing media asset's metadata.",
    tags=["media-assets"],
)
async def update_media_asset(
    asset_id: str,
    payload: MediaAssetUpdateRequest,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("media.upload")),
) -> MediaAssetView:
    try:
        detail = await media_asset_service.get_asset_detail(
            asset_id=asset_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
        actor.require_account_access(detail.asset.account_id)
        return await media_asset_service.update_asset(
            asset_id=asset_id,
            payload=payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MediaProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MediaProviderUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=detail.asset.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="media_asset.update",
        target_type="media_asset",
        target_id=asset_id,
        payload={"fields": payload.model_dump(exclude_none=True)},
    )


@router.post(
    "/{asset_id}/sync",
    summary="Sync media asset",
    description="Sync a media asset with the external messaging provider.",
    tags=["media-assets"],
)
async def sync_media_asset(
    asset_id: str,
    payload: MediaAssetSyncRequest,
    media_asset_service: MediaAssetService = Depends(get_media_asset_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("media.upload")),
) -> MediaAssetSyncResponse:
    try:
        detail = await media_asset_service.get_asset_detail(
            asset_id=asset_id,
            allowed_account_ids=None if actor.is_super_admin else set(actor.account_ids),
        )
        actor.require_account_access(detail.asset.account_id)
        return await media_asset_service.sync_asset(
            asset_id=asset_id,
            payload=payload,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MediaProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MediaProviderUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_media_route_value_error(exc)

    runtime_state.add_audit_log(
        account_id=detail.asset.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="media_asset.sync",
        target_type="media_asset",
        target_id=asset_id,
        payload={},
    )

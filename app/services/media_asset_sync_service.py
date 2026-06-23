from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import MediaAsset, MediaAssetEvent, MediaAssetProviderSync, WhatsAppPhoneNumber, utc_now
from app.providers.messaging.base import MessagingProvider
from app.schemas.messaging import MediaAssetSyncRequest as ProviderMediaAssetSyncRequest
from app.schemas.messaging import MediaAssetSyncResult
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.runtime_state import RuntimeStateStore


@dataclass(slots=True)
class PreparedMediaAssetReference:
    asset: MediaAsset
    provider_sync: MediaAssetProviderSync
    meta_media_id: str
    provider_media_id: str
    phone_number_id: str
    waba_id: str | None
    reused_existing: bool


class MediaAssetSyncService:
    def __init__(
        self,
        *,
        session: Session,
        runtime_state: RuntimeStateStore,
        messaging_provider: MessagingProvider,
    ) -> None:
        self._session = session
        self._runtime_state = runtime_state
        self._messaging_provider = messaging_provider

    async def ensure_provider_reference(
        self,
        *,
        asset: MediaAsset,
        account_id: str,
        target_phone_number_id: str | None,
        actor_type: str,
        actor_id: str | None,
        usage_context: str,
        force_resync: bool = False,
        context_payload: dict[str, object] | None = None,
    ) -> PreparedMediaAssetReference:
        provider_phone_number_id = self._resolve_provider_phone_number_id(
            asset=asset,
            target_phone_number_id=target_phone_number_id,
        )
        phone_number = self._resolve_phone_number(
            account_id=account_id,
            provider_phone_number_id=provider_phone_number_id,
        )
        existing_sync = self._find_provider_sync(
            asset_id=asset.id,
            provider_name=self._messaging_provider.provider_name,
            phone_number_id=provider_phone_number_id,
        )
        if existing_sync is None:
            existing_sync = self._promote_legacy_asset_reference_if_available(
                asset=asset,
                provider_name=self._messaging_provider.provider_name,
                provider_phone_number_id=provider_phone_number_id,
            )

        if (
            existing_sync is not None
            and (getattr(existing_sync, "provider_media_id", None) or existing_sync.meta_media_id)
            and existing_sync.sync_status in {"linked", "reused", "synced"}
            and not force_resync
        ):
            existing_provider_media_id = (
                getattr(existing_sync, "provider_media_id", None) or existing_sync.meta_media_id
            )
            resolved_existing_waba_id = (
                existing_sync.waba_id or self._resolve_phone_waba_id(phone_number) or asset.waba_id
            )
            existing_sync.sync_status = "reused"
            existing_sync.last_synced_at = existing_sync.last_synced_at or utc_now()
            existing_sync.last_error_code = None
            existing_sync.last_error_message = None
            self._session.add(existing_sync)
            self._session.add(
                self._build_media_asset_event(
                    account_id=account_id,
                    asset_id=asset.id,
                    waba_id=resolved_existing_waba_id,
                    phone_number_id=provider_phone_number_id,
                    event_type="media_asset_sync_reused",
                    meta_media_id=existing_sync.meta_media_id,
                    created_by=actor_id,
                    payload={
                        "provider": self._messaging_provider.provider_name,
                        "storage_key": asset.storage_key,
                        "storage_url": asset.storage_url,
                        "usage_context": usage_context,
                        "provider_media_id": existing_provider_media_id,
                        "meta_media_id": existing_sync.meta_media_id,
                        **(context_payload or {}),
                    },
                )
            )
            self._runtime_state.add_audit_log(
                account_id=account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="media_asset_sync_reused",
                target_type="media_asset",
                target_id=asset.id,
                payload={
                    "provider": self._messaging_provider.provider_name,
                    "waba_id": resolved_existing_waba_id,
                    "phone_number_id": provider_phone_number_id,
                    "provider_media_id": existing_provider_media_id,
                    "meta_media_id": existing_sync.meta_media_id,
                    "storage_key": asset.storage_key,
                    "storage_url": asset.storage_url,
                    "usage_context": usage_context,
                    **(context_payload or {}),
                },
            )
            self._session.flush()
            return PreparedMediaAssetReference(
                asset=asset,
                provider_sync=existing_sync,
                meta_media_id=existing_sync.meta_media_id,
                provider_media_id=existing_provider_media_id,
                phone_number_id=provider_phone_number_id,
                waba_id=resolved_existing_waba_id,
                reused_existing=True,
            )

        provider_waba_id = self._resolve_phone_waba_id(phone_number) or asset.waba_id
        sync_exception: Exception | None = None
        try:
            existing_provider_media_id = (
                getattr(existing_sync, "provider_media_id", None) or existing_sync.meta_media_id
                if existing_sync is not None
                else None
            )
            sync_result = await self._messaging_provider.sync_media_asset(
                ProviderMediaAssetSyncRequest(
                    account_id=account_id,
                    asset_id=asset.id,
                    asset_name=asset.name,
                    asset_type=asset.asset_type,
                    mime_type=asset.mime_type,
                    phone_number_id=provider_phone_number_id,
                    access_token=(
                        phone_number.waba_account.access_token
                        if phone_number.waba_account is not None
                        else None
                    ),
                    waba_id=provider_waba_id,
                    storage_key=asset.storage_key,
                    storage_url=asset.storage_url,
                    existing_provider_media_id=existing_provider_media_id,
                    metadata={
                        "usage_context": usage_context,
                        **(context_payload or {}),
                    },
                )
            )
        except Exception as exc:
            sync_exception = exc
            sync_result = MediaAssetSyncResult(
                provider_name=self._messaging_provider.provider_name,
                phone_number_id=provider_phone_number_id,
                waba_id=provider_waba_id,
                provider_media_id=None,
                meta_media_id=None,
                sync_status="failed",
                error_code="sync_exception",
                error_message=str(exc),
                raw_response={"exception_type": exc.__class__.__name__},
            )

        provider_sync = existing_sync or MediaAssetProviderSync(
            account_id=account_id,
            asset_id=asset.id,
            provider_name=self._messaging_provider.provider_name,
            phone_number_id=provider_phone_number_id,
        )
        previous_provider_media_id = (
            getattr(existing_sync, "provider_media_id", None) or existing_sync.meta_media_id
            if existing_sync is not None
            else None
        )
        previous_last_synced_at = existing_sync.last_synced_at if existing_sync is not None else None
        previous_sync_status = existing_sync.sync_status if existing_sync is not None else None
        sync_provider_media_id = sync_result.provider_media_id
        is_successful_sync = sync_result.sync_status in {"reused", "synced"} and bool(sync_provider_media_id)
        has_reusable_previous_reference = bool(previous_provider_media_id) and previous_sync_status in {
            "linked",
            "reused",
            "synced",
        }
        persisted_provider_media_id = (
            sync_provider_media_id
            if sync_provider_media_id is not None
            else previous_provider_media_id
            if not is_successful_sync
            else None
        )
        resolved_sync_waba_id = (
            sync_result.waba_id
            or (existing_sync.waba_id if existing_sync is not None else None)
            or provider_waba_id
        )
        provider_sync.waba_id = resolved_sync_waba_id
        provider_sync.provider_media_id = persisted_provider_media_id
        provider_sync.meta_media_id = persisted_provider_media_id
        provider_sync.sync_status = (
            sync_result.sync_status
            if is_successful_sync or not has_reusable_previous_reference
            else previous_sync_status
        )
        provider_sync.last_synced_at = utc_now() if is_successful_sync else previous_last_synced_at
        provider_sync.last_error_code = sync_result.error_code
        provider_sync.last_error_message = sync_result.error_message
        provider_sync.raw_response = sync_result.raw_response
        self._session.add(provider_sync)

        event_type = (
            "media_asset_sync_succeeded"
            if sync_result.sync_status in {"reused", "synced"}
            else "media_asset_sync_failed"
        )
        self._session.add(
            self._build_media_asset_event(
                account_id=account_id,
                asset_id=asset.id,
                waba_id=resolved_sync_waba_id,
                phone_number_id=provider_phone_number_id,
                event_type=event_type,
                meta_media_id=persisted_provider_media_id,
                created_by=actor_id,
                payload={
                    "provider": sync_result.provider_name,
                    "sync_status": sync_result.sync_status,
                    "error_code": sync_result.error_code,
                    "error_message": sync_result.error_message,
                    "provider_media_id": sync_provider_media_id,
                    "failed_provider_media_id": (
                        sync_provider_media_id
                        if sync_result.sync_status not in {"reused", "synced"}
                        else None
                    ),
                    "last_known_provider_media_id": previous_provider_media_id,
                    "last_known_meta_media_id": previous_provider_media_id,
                    "storage_key": asset.storage_key,
                    "storage_url": asset.storage_url,
                    "usage_context": usage_context,
                    **(context_payload or {}),
                },
            )
        )
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=event_type,
            target_type="media_asset",
            target_id=asset.id,
                payload={
                    "provider": sync_result.provider_name,
                    "waba_id": resolved_sync_waba_id,
                    "phone_number_id": provider_phone_number_id,
                    "provider_media_id": sync_provider_media_id,
                    "meta_media_id": sync_provider_media_id,
                    "failed_provider_media_id": (
                        sync_provider_media_id
                        if sync_result.sync_status not in {"reused", "synced"}
                    else None
                ),
                "last_known_provider_media_id": previous_provider_media_id,
                "last_known_meta_media_id": previous_provider_media_id,
                "sync_status": sync_result.sync_status,
                "error_code": sync_result.error_code,
                "error_message": sync_result.error_message,
                "storage_key": asset.storage_key,
                "storage_url": asset.storage_url,
                "usage_context": usage_context,
                **(context_payload or {}),
            },
        )
        self._session.flush()
        if sync_result.sync_status not in {"reused", "synced"} or not sync_provider_media_id:
            detail = (
                sync_result.error_message
                or f"Media asset '{asset.id}' could not be synchronized for provider use."
            )
            if isinstance(sync_exception, RuntimeError):
                raise MediaProviderUpstreamError(detail) from sync_exception
            if (
                isinstance(sync_exception, ValueError)
                and "access_token" in detail
                and "requires" in detail
            ):
                raise MediaProviderConfigError(detail) from sync_exception
            raise ValueError(detail)
        return PreparedMediaAssetReference(
            asset=asset,
            provider_sync=provider_sync,
            meta_media_id=sync_provider_media_id,
            provider_media_id=sync_provider_media_id,
            phone_number_id=provider_phone_number_id,
            waba_id=resolved_sync_waba_id,
            reused_existing=sync_result.sync_status == "reused",
        )

    async def sync_asset(
        self,
        *,
        asset_id: str,
        account_id: str,
        target_phone_number_id: str | None,
        actor_type: str,
        actor_id: str | None,
        force_resync: bool,
    ) -> PreparedMediaAssetReference:
        asset = self._require_asset(asset_id=asset_id)
        if asset.account_id != account_id:
            raise PermissionError(
                f"Media asset '{asset.id}' does not belong to account '{account_id}'."
            )
        return await self.ensure_provider_reference(
            asset=asset,
            account_id=account_id,
            target_phone_number_id=target_phone_number_id,
            actor_type=actor_type,
            actor_id=actor_id,
            usage_context="manual_sync",
            force_resync=force_resync,
        )

    def _require_asset(self, *, asset_id: str) -> MediaAsset:
        asset = self._session.scalars(
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.phone_number).selectinload(
                    WhatsAppPhoneNumber.waba_account
                ),
                selectinload(MediaAsset.provider_syncs),
            )
            .where(MediaAsset.id == asset_id)
        ).first()
        if asset is None:
            raise LookupError(f"Media asset '{asset_id}' was not found.")
        return asset

    def _find_provider_sync(
        self,
        *,
        asset_id: str,
        provider_name: str,
        phone_number_id: str,
    ) -> MediaAssetProviderSync | None:
        return self._session.scalars(
            select(MediaAssetProviderSync).where(
                MediaAssetProviderSync.asset_id == asset_id,
                MediaAssetProviderSync.provider_name == provider_name,
                MediaAssetProviderSync.phone_number_id == phone_number_id,
            )
        ).first()

    def _promote_legacy_asset_reference_if_available(
        self,
        *,
        asset: MediaAsset,
        provider_name: str,
        provider_phone_number_id: str,
    ) -> MediaAssetProviderSync | None:
        bound_phone_number = self._resolve_bound_asset_phone_number(asset)
        asset_scope_phone_number_id = (
            bound_phone_number.phone_number_id
            if bound_phone_number is not None
            else None
        )
        if not asset.meta_media_id or asset_scope_phone_number_id != provider_phone_number_id:
            return None
        sync_record = MediaAssetProviderSync(
            account_id=asset.account_id,
            asset_id=asset.id,
            provider_name=provider_name,
            waba_id=asset.waba_id or self._resolve_phone_waba_id(bound_phone_number),
            phone_number_id=provider_phone_number_id,
            provider_media_id=asset.meta_media_id,
            meta_media_id=asset.meta_media_id,
            sync_status=asset.meta_media_status or "linked",
            last_synced_at=utc_now(),
            raw_response={
                "source": "legacy_asset_snapshot",
                "reference_mode": "promoted_to_phone_scoped_provider_reference",
            },
        )
        self._session.add(sync_record)
        asset.meta_media_id = None
        asset.meta_media_status = None
        self._session.add(asset)
        self._session.flush()
        return sync_record

    def _resolve_provider_phone_number_id(
        self,
        *,
        asset: MediaAsset,
        target_phone_number_id: str | None,
    ) -> str:
        bound_asset_phone_number_id = self._resolve_bound_asset_phone_number_id(asset)
        provider_phone_number_id = (
            target_phone_number_id
            or bound_asset_phone_number_id
            or self._resolve_existing_provider_phone_number_id(asset)
        )
        if not provider_phone_number_id:
            raise ValueError(
                f"Media asset '{asset.id}' requires phone_number_id because it is account scoped."
            )
        if (
            bound_asset_phone_number_id
            and bound_asset_phone_number_id != provider_phone_number_id
        ):
            raise ValueError(
                f"Media asset '{asset.id}' is bound to Phone-Number-ID '{bound_asset_phone_number_id}', "
                f"not '{provider_phone_number_id}'."
            )
        return provider_phone_number_id

    @staticmethod
    def _resolve_bound_asset_phone_number_id(asset: MediaAsset) -> str | None:
        bound_phone_number = MediaAssetSyncService._resolve_bound_asset_phone_number(asset)
        if bound_phone_number is not None and bound_phone_number.phone_number_id:
            return bound_phone_number.phone_number_id
        return None

    @staticmethod
    def _resolve_bound_asset_phone_number(asset: MediaAsset) -> WhatsAppPhoneNumber | None:
        phone_number = asset.phone_number
        if phone_number is None or asset.phone_number_id is None:
            return None
        if getattr(phone_number, "account_id", None) != asset.account_id:
            return None
        if getattr(phone_number, "id", None) != asset.phone_number_id:
            return None
        waba_account = getattr(phone_number, "waba_account", None)
        if waba_account is not None and getattr(waba_account, "account_id", None) != asset.account_id:
            return None
        return phone_number

    @staticmethod
    def _resolve_existing_provider_phone_number_id(asset: MediaAsset) -> str | None:
        for sync in sorted(
            asset.provider_syncs,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        ):
            if sync.phone_number_id:
                return sync.phone_number_id
        return None

    @staticmethod
    def _resolve_phone_waba_id(phone_number: WhatsAppPhoneNumber | None) -> str | None:
        if phone_number is None:
            return None
        if phone_number.waba_id:
            return phone_number.waba_id
        if phone_number.waba_account is not None:
            return phone_number.waba_account.waba_id
        return None

    def _resolve_phone_number(
        self,
        *,
        account_id: str,
        provider_phone_number_id: str,
    ) -> WhatsAppPhoneNumber:
        phone_number = self._session.scalars(
            select(WhatsAppPhoneNumber)
            .options(selectinload(WhatsAppPhoneNumber.waba_account))
            .where(
                WhatsAppPhoneNumber.phone_number_id == provider_phone_number_id,
                WhatsAppPhoneNumber.waba_account.has(account_id=account_id),
            )
        ).first()
        if phone_number is None:
            raise ValueError(
                f"Phone number '{provider_phone_number_id}' for account '{account_id}' was not found."
            )
        return phone_number

    @staticmethod
    def _build_media_asset_event(
        *,
        account_id: str,
        asset_id: str,
        waba_id: str | None,
        phone_number_id: str | None,
        event_type: str,
        meta_media_id: str | None,
        created_by: str | None,
        payload: dict[str, object] | None,
    ) -> MediaAssetEvent:
        payload_provider_media_id = (
            payload.get("provider_media_id")
            if isinstance(payload, dict)
            else None
        )
        event_values: dict[str, object | None] = {
            "account_id": account_id,
            "asset_id": asset_id,
            "phone_number_id": phone_number_id,
            "event_type": event_type,
            "meta_media_id": meta_media_id,
            "created_by": created_by,
            "payload": payload,
        }
        if hasattr(MediaAssetEvent, "waba_id"):
            event_values["waba_id"] = waba_id
        if hasattr(MediaAssetEvent, "provider_media_id"):
            event_values["provider_media_id"] = payload_provider_media_id or meta_media_id
        return MediaAssetEvent(**event_values)

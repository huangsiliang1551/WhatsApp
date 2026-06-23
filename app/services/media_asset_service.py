import mimetypes
import re
from asyncio import to_thread
from pathlib import Path
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.metrics import business_outbound_messages_total, message_processing_failures_total
from app.db.models import (
    H5Site,
    MediaAsset,
    MediaAssetEvent,
    MediaAssetProviderSync,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
)
from app.providers.messaging.base import MessagingProvider
from app.schemas.media_assets import (
    MediaAssetCreateRequest,
    MediaAssetDetailResponse,
    MediaAssetEventView,
    MediaAssetProviderSyncView,
    MediaAssetSyncRequest,
    MediaAssetSyncResponse,
    MediaAssetSendRequest,
    MediaAssetSendResponse,
    MediaAssetType,
    MediaAssetUpdateRequest,
    MediaAssetUsageSummary,
    MediaAssetView,
)
from app.services.media_asset_errors import MediaProviderConfigError, MediaProviderUpstreamError
from app.services.messaging_dispatch import build_outbound_dispatch_request
from app.services.meta_scope_validation import MetaScopeValidator
from app.services.media_asset_sync_service import MediaAssetSyncService
from app.services.runtime_state import RuntimeStateStore
from app.services.translation_service import TranslationService


class MediaAssetService:
    def __init__(
        self,
        *,
        storage_root: str,
        session: Session,
        runtime_state: RuntimeStateStore,
        translation_service: TranslationService,
        messaging_provider: MessagingProvider,
    ) -> None:
        self._storage_root = self._resolve_storage_root(storage_root)
        self._session = session
        self._runtime_state = runtime_state
        self._translation_service = translation_service
        self._messaging_provider = messaging_provider
        self._meta_scope_validator = MetaScopeValidator(session)
        self._sync_service = MediaAssetSyncService(
            session=session,
            runtime_state=runtime_state,
            messaging_provider=messaging_provider,
        )

    async def list_assets(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        asset_type: MediaAssetType | None,
        is_active: bool | None,
        query: str | None,
        tag: str | None,
        allowed_account_ids: set[str] | None,
        agency_id: str | None = None,
    ) -> list[MediaAssetView]:
        self._validate_account_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        resolved_scope = self._meta_scope_validator.validate_phone_number_scope(
            phone_number_id=phone_number_id,
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            enforce_waba_match=False,
        )
        if (
            resolved_scope is not None
            and waba_id is not None
            and resolved_scope.waba_id is not None
            and resolved_scope.waba_id != waba_id
            and not self._has_historical_asset_scope(
                account_id=account_id or resolved_scope.account_id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
            )
        ):
            raise ValueError(
                f"Phone-Number-ID '{phone_number_id}' belongs to WABA '{resolved_scope.waba_id}', "
                f"not '{waba_id}'."
            )
        statement = (
            select(MediaAsset)
            .options(
                selectinload(MediaAsset.phone_number).selectinload(
                    WhatsAppPhoneNumber.waba_account
                ),
                selectinload(MediaAsset.provider_syncs),
                selectinload(MediaAsset.events),
            )
            .order_by(MediaAsset.updated_at.desc(), MediaAsset.created_at.desc(), MediaAsset.id.desc())
        )
        if account_id is not None:
            statement = statement.where(MediaAsset.account_id == account_id)
        elif allowed_account_ids is not None:
            statement = statement.where(MediaAsset.account_id.in_(allowed_account_ids))
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
            statement = statement.where(MediaAsset.account_id.in_(agency_account_ids))
        if waba_id is not None:
            statement = statement.where(
                or_(
                    MediaAsset.waba_id == waba_id,
                    MediaAsset.provider_syncs.any(MediaAssetProviderSync.waba_id == waba_id),
                    MediaAsset.events.any(MediaAssetEvent.waba_id == waba_id),
                )
            )
        if phone_number_id is not None:
            statement = statement.where(
                or_(
                    MediaAsset.phone_number.has(WhatsAppPhoneNumber.phone_number_id == phone_number_id),
                    MediaAsset.provider_syncs.any(
                        MediaAssetProviderSync.phone_number_id == phone_number_id
                    ),
                    MediaAsset.events.any(MediaAssetEvent.phone_number_id == phone_number_id),
                )
            )
        if asset_type is not None:
            statement = statement.where(MediaAsset.asset_type == asset_type)
        if is_active is not None:
            statement = statement.where(MediaAsset.is_active == is_active)
        assets = self._session.scalars(statement).all()
        if query:
            search_value = query.strip().lower()
            if search_value:
                assets = [
                    asset
                    for asset in assets
                    if self._asset_matches_query(asset, search_value)
                ]
        if tag:
            tag_value = tag.strip().lower()
            if tag_value:
                assets = [
                    asset
                    for asset in assets
                    if any(str(item).lower() == tag_value for item in (asset.tags_json or []))
                ]
        return [self._serialize_asset(asset) for asset in assets]

    async def upload_asset_file(
        self,
        *,
        account_id: str,
        waba_id: str | None,
        phone_number_id: str | None,
        name: str | None,
        asset_type: MediaAssetType | None,
        mime_type: str | None,
        source: str | None,
        tags: list[str],
        file_name: str | None,
        content_type: str | None,
        file_bytes: bytes,
        actor_type: str,
        actor_id: str | None,
    ) -> MediaAssetView:
        normalized_account_id = account_id.strip()
        if not normalized_account_id:
            raise ValueError("Media asset upload requires account_id.")
        if not file_bytes:
            raise ValueError("Media asset upload received an empty file.")
        if self._runtime_state.get_account_model(normalized_account_id) is None:
            raise LookupError(f"Account '{normalized_account_id}' was not found.")
        phone_number = self._resolve_phone_number(
            account_id=normalized_account_id,
            provider_phone_number_id=phone_number_id,
        )
        resolved_waba_id = self._resolve_waba_scope(
            account_id=normalized_account_id,
            requested_waba_id=waba_id,
            phone_number=phone_number,
        )
        resolved_name = self._resolve_uploaded_name(name=name, file_name=file_name)
        resolved_mime_type = self._resolve_uploaded_mime_type(
            provided_mime_type=mime_type,
            detected_content_type=content_type,
            file_name=file_name,
        )
        resolved_asset_type = self._resolve_uploaded_asset_type(
            explicit_asset_type=asset_type,
            mime_type=resolved_mime_type,
        )
        storage_path = self._build_storage_path(
            account_id=normalized_account_id,
            phone_number_id=phone_number_id,
            file_name=file_name,
            mime_type=resolved_mime_type,
        )
        await self._write_storage_file(storage_path=storage_path, file_bytes=file_bytes)

        asset = MediaAsset(
            account_id=normalized_account_id,
            waba_id=resolved_waba_id,
            phone_number_id=phone_number.id if phone_number is not None else None,
            name=resolved_name,
            asset_type=resolved_asset_type,
            mime_type=resolved_mime_type,
            file_size=len(file_bytes),
            storage_key=str(storage_path),
            storage_url=None,
            meta_media_id=None,
            meta_media_status=None,
            source=(source or "").strip() or "upload",
            tags_json=tags,
            created_by=actor_id,
            is_active=True,
        )
        self._session.add(asset)
        try:
            self._session.flush()
            self._session.add(
                self._build_media_asset_event(
                    account_id=normalized_account_id,
                    asset_id=asset.id,
                    waba_id=resolved_waba_id,
                    phone_number_id=phone_number_id,
                    event_type="media_asset_uploaded",
                    meta_media_id=None,
                    created_by=actor_id,
                    payload={
                        "asset_type": resolved_asset_type,
                        "mime_type": resolved_mime_type,
                        "file_name": file_name,
                        "file_size": len(file_bytes),
                        "storage_key": str(storage_path),
                        "source": asset.source,
                        "tags": tags,
                    },
                )
            )
            self._runtime_state.add_audit_log(
                account_id=normalized_account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="media_asset_uploaded",
                target_type="media_asset",
                target_id=asset.id,
                payload={
                    "name": resolved_name,
                    "waba_id": resolved_waba_id,
                    "phone_number_id": phone_number_id,
                    "asset_type": resolved_asset_type,
                    "mime_type": resolved_mime_type,
                    "file_size": len(file_bytes),
                    "storage_key": str(storage_path),
                    "source": asset.source,
                    "tags": tags,
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            await self._delete_storage_file(storage_path)
            raise
        self._session.refresh(asset)
        return self._serialize_asset(asset)

    async def create_asset(
        self,
        payload: MediaAssetCreateRequest,
        *,
        actor_type: str,
        actor_id: str | None,
    ) -> MediaAssetView:
        if self._runtime_state.get_account_model(payload.account_id) is None:
            raise LookupError(f"Account '{payload.account_id}' was not found.")
        phone_number = self._resolve_phone_number(
            account_id=payload.account_id,
            provider_phone_number_id=payload.phone_number_id,
        )
        resolved_waba_id = self._resolve_waba_scope(
            account_id=payload.account_id,
            requested_waba_id=payload.waba_id,
            phone_number=phone_number,
        )
        provider_media_id = payload.resolved_provider_media_id
        provider_media_status = payload.resolved_provider_media_status
        legacy_meta_media_id = payload.__dict__.get("meta_media_id")
        legacy_meta_media_status = payload.__dict__.get("meta_media_status")
        reference_mode = "phone_scoped_provider_reference" if provider_media_id else "storage_reference"
        asset = MediaAsset(
            account_id=payload.account_id,
            waba_id=resolved_waba_id,
            phone_number_id=phone_number.id if phone_number is not None else None,
            name=payload.name,
            asset_type=payload.asset_type,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            storage_key=payload.storage_key,
            storage_url=payload.storage_url,
            meta_media_id=None,
            meta_media_status=None,
            source=payload.source,
            tags_json=payload.tags,
            created_by=actor_id,
            is_active=True,
        )
        self._session.add(asset)
        self._session.flush()
        if provider_media_id and payload.phone_number_id:
            self._session.add(
                MediaAssetProviderSync(
                    account_id=payload.account_id,
                    asset_id=asset.id,
                    provider_name=self._messaging_provider.provider_name,
                    waba_id=asset.waba_id,
                    phone_number_id=payload.phone_number_id,
                    provider_media_id=provider_media_id,
                    meta_media_id=provider_media_id,
                    sync_status=provider_media_status or "linked",
                    last_synced_at=None,
                    raw_response={
                        "source": "manual_asset_create",
                        "reference_mode": reference_mode,
                        "legacy_meta_media_id_provided": legacy_meta_media_id is not None,
                    },
                )
            )
        self._session.add(
            self._build_media_asset_event(
                account_id=payload.account_id,
                asset_id=asset.id,
                waba_id=asset.waba_id,
                phone_number_id=payload.phone_number_id,
                event_type="media_asset_created",
                meta_media_id=provider_media_id,
                created_by=actor_id,
                payload={
                    "asset_type": payload.asset_type,
                    "mime_type": payload.mime_type,
                    "storage_url": payload.storage_url,
                    "storage_key": payload.storage_key,
                    "provider_media_id": provider_media_id,
                    "provider_media_status": provider_media_status,
                    "meta_media_id": legacy_meta_media_id,
                    "meta_media_status": legacy_meta_media_status,
                    "reference_mode": reference_mode,
                    "source": payload.source,
                    "tags": payload.tags,
                },
            )
        )
        self._runtime_state.add_audit_log(
            account_id=payload.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="media_asset_created",
            target_type="media_asset",
            target_id=asset.id,
            payload={
                "name": payload.name,
                "waba_id": asset.waba_id,
                "phone_number_id": payload.phone_number_id,
                "asset_type": payload.asset_type,
                "mime_type": payload.mime_type,
                "provider_media_id": provider_media_id,
                "provider_media_status": provider_media_status,
                "meta_media_id": legacy_meta_media_id,
                "meta_media_status": legacy_meta_media_status,
                "reference_mode": reference_mode,
                "storage_url": payload.storage_url,
            },
        )
        self._session.commit()
        self._session.refresh(asset)
        return self._serialize_asset(asset)

    async def update_asset(
        self,
        *,
        asset_id: str,
        payload: MediaAssetUpdateRequest,
        actor_type: str,
        actor_id: str | None,
    ) -> MediaAssetView:
        asset = self._require_asset(asset_id)
        changed_fields: dict[str, dict[str, object | None]] = {}
        current_phone_number_id = (
            asset.phone_number.phone_number_id
            if asset.phone_number is not None
            else None
        )
        current_tags = list(asset.tags_json or [])
        field_names = payload.model_fields_set
        snapshot_phone_number_id = current_phone_number_id

        if "name" in field_names and payload.name != asset.name:
            changed_fields["name"] = {"from": asset.name, "to": payload.name}
            asset.name = payload.name

        if "tags" in field_names and payload.tags != current_tags:
            changed_fields["tags"] = {"from": current_tags, "to": payload.tags}
            asset.tags_json = payload.tags or []

        if "is_active" in field_names and payload.is_active != asset.is_active:
            changed_fields["is_active"] = {"from": asset.is_active, "to": payload.is_active}
            asset.is_active = bool(payload.is_active)

        if "phone_number_id" in field_names or "waba_id" in field_names:
            next_phone_number_id = (
                payload.phone_number_id
                if "phone_number_id" in field_names
                else current_phone_number_id
            )
            phone_number = self._resolve_phone_number(
                account_id=asset.account_id,
                provider_phone_number_id=next_phone_number_id,
            )
            resolved_waba_id = self._resolve_waba_scope(
                account_id=asset.account_id,
                requested_waba_id=(
                    payload.waba_id if "waba_id" in field_names else asset.waba_id
                ),
                phone_number=phone_number,
            )
            next_phone_db_id = phone_number.id if phone_number is not None else None
            snapshot_phone_number_id = next_phone_number_id
            if current_phone_number_id != next_phone_number_id:
                changed_fields["phone_number_id"] = {
                    "from": current_phone_number_id,
                    "to": next_phone_number_id,
                }
                asset.phone_number_id = next_phone_db_id
            if asset.waba_id != resolved_waba_id:
                changed_fields["waba_id"] = {"from": asset.waba_id, "to": resolved_waba_id}
                asset.waba_id = resolved_waba_id

        if not changed_fields:
            return self._serialize_asset(asset)

        current_snapshot = {
            "name": asset.name,
            "tags": list(asset.tags_json or []),
            "waba_id": asset.waba_id,
            "phone_number_id": snapshot_phone_number_id,
            "is_active": asset.is_active,
        }
        self._session.add(
            self._build_media_asset_event(
                account_id=asset.account_id,
                asset_id=asset.id,
                waba_id=asset.waba_id,
                phone_number_id=snapshot_phone_number_id,
                event_type="media_asset_updated",
                meta_media_id=asset.meta_media_id,
                created_by=actor_id,
                payload={
                    "changes": changed_fields,
                    "current": current_snapshot,
                },
            )
        )
        audit_action = "media_asset_updated"
        if set(changed_fields) == {"is_active"}:
            audit_action = (
                "media_asset_reactivated" if asset.is_active else "media_asset_deactivated"
            )
        self._runtime_state.add_audit_log(
            account_id=asset.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=audit_action,
            target_type="media_asset",
            target_id=asset.id,
            payload={
                "changes": changed_fields,
                "current": current_snapshot,
            },
        )
        self._session.commit()
        return self._serialize_asset(self._require_asset(asset.id))

    async def get_asset_detail(
        self,
        *,
        asset_id: str,
        allowed_account_ids: set[str] | None,
    ) -> MediaAssetDetailResponse:
        asset = self._require_asset(asset_id)
        self._ensure_asset_account_allowed(asset=asset, allowed_account_ids=allowed_account_ids)
        events = self._session.scalars(
            select(MediaAssetEvent)
            .where(MediaAssetEvent.asset_id == asset.id)
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
        ).all()
        provider_syncs = self._session.scalars(
            select(MediaAssetProviderSync)
            .where(MediaAssetProviderSync.asset_id == asset.id)
            .order_by(
                MediaAssetProviderSync.updated_at.desc(),
                MediaAssetProviderSync.created_at.desc(),
                MediaAssetProviderSync.id.desc(),
            )
        ).all()
        return MediaAssetDetailResponse(
            asset=self._serialize_asset(asset),
            usage=self._build_usage_summary(events),
            provider_syncs=[self._serialize_provider_sync(item) for item in provider_syncs],
            events=[self._serialize_event(event) for event in events],
        )

    async def sync_asset(
        self,
        *,
        asset_id: str,
        payload: MediaAssetSyncRequest,
        actor_type: str,
        actor_id: str | None,
    ) -> MediaAssetSyncResponse:
        asset = self._require_asset(asset_id)
        try:
            reference = await self._sync_service.sync_asset(
                asset_id=asset_id,
                account_id=asset.account_id,
                target_phone_number_id=payload.phone_number_id,
                actor_type=actor_type,
                actor_id=actor_id,
                force_resync=payload.force_resync,
            )
        except ValueError:
            self._session.commit()
            raise
        self._session.commit()
        return MediaAssetSyncResponse(
            asset_id=asset.id,
            account_id=asset.account_id,
            provider_name=reference.provider_sync.provider_name,
            waba_id=reference.waba_id,
            phone_number_id=reference.phone_number_id,
            provider_media_id=reference.provider_media_id,
            meta_media_id=reference.meta_media_id,
            sync_status=reference.provider_sync.sync_status,
            last_error_code=reference.provider_sync.last_error_code,
            last_error_message=reference.provider_sync.last_error_message,
            reused_existing=reference.reused_existing,
            synced_at=(
                reference.provider_sync.last_synced_at.isoformat()
                if reference.provider_sync.last_synced_at is not None
                else None
            ),
        )

    async def send_asset_to_conversation(
        self,
        *,
        account_id: str,
        conversation_id: str,
        payload: MediaAssetSendRequest,
        actor_type: str,
        actor_id: str | None,
    ) -> MediaAssetSendResponse:
        conversation = await self._runtime_state.get_conversation_model(
            account_id=account_id,
            conversation_id=conversation_id,
        )
        self._runtime_state.ensure_conversation_messaging_available(conversation)
        agent_id = payload.agent_id
        self._ensure_agent_can_reply(conversation=conversation, agent_id=agent_id)
        sent_by_agent_id = self._runtime_state.resolve_agent_storage_id(
            account_id=account_id,
            agent_id=agent_id,
        )
        asset = self._require_asset(payload.asset_id)
        if asset.account_id != account_id:
            raise ValueError(
                f"Media asset '{payload.asset_id}' does not belong to account '{account_id}'."
            )
        if not asset.is_active:
            raise ValueError(f"Media asset '{payload.asset_id}' is inactive.")
        conversation_phone_number = conversation.phone_number
        conversation_phone_number_id = self._resolve_provider_phone_number_id_from_conversation(
            conversation
        )
        external_conversation_id = conversation.external_conversation_id
        internal_conversation_id = conversation.id
        asset_phone_number_id = self._resolve_current_asset_provider_phone_number_id(asset)
        if (
            asset_phone_number_id is not None
            and conversation_phone_number_id is not None
            and asset_phone_number_id != conversation_phone_number_id
        ):
            raise ValueError(
                "Media asset phone_number_id does not match the conversation phone number."
            )
        try:
            prepared_reference = await self._sync_service.ensure_provider_reference(
                asset=asset,
                account_id=account_id,
                target_phone_number_id=conversation_phone_number_id,
                actor_type=actor_type,
                actor_id=actor_id,
                usage_context="manual_operator_send",
                context_payload={
                    "conversation_id": conversation_id,
                    "external_conversation_id": external_conversation_id,
                    "internal_conversation_id": internal_conversation_id,
                },
            )
        except ValueError:
            self._session.commit()
            raise
        resolved_waba_id = (
            prepared_reference.waba_id
            or self._resolve_phone_waba_id(conversation_phone_number)
            or asset.waba_id
        )
        provider_media_id = prepared_reference.provider_media_id
        meta_media_id = prepared_reference.meta_media_id

        source_caption = (payload.caption or "").strip() or None
        delivered_caption = source_caption
        translated = False
        if source_caption:
            source_language = self._translation_service.detect_language(text=source_caption)
            delivered_caption, translated = await self._translation_service.translate_outbound_for_customer(
                text=source_caption,
                source_language=source_language,
                target_language=conversation.customer_language,
            )
        else:
            source_language = None

        dispatch_request = build_outbound_dispatch_request(
            provider=self._messaging_provider,
            conversation=conversation,
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=conversation.customer_id,
            text=delivered_caption,
            message_type=asset.asset_type,
            media_asset_id=provider_media_id,
            media_url=None,
            media_caption=delivered_caption,
            mime_type=asset.mime_type,
            file_name=payload.file_name,
            metadata={
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "mime_type": asset.mime_type,
                "storage_key": asset.storage_key,
                "waba_id": resolved_waba_id,
                "phone_number_id": prepared_reference.phone_number_id,
                "provider_media_id": provider_media_id,
                "meta_media_id": meta_media_id,
                "storage_url": asset.storage_url,
                "translated": translated,
            },
        )
        try:
            dispatch_result = await self._messaging_provider.send_outbound(dispatch_request)
        except Exception as exc:
            business_outbound_messages_total.labels(
                provider=self._messaging_provider.provider_name,
                delivery_mode="manual_operator_media_send",
                outcome="failed",
            ).inc()
            message_processing_failures_total.labels(
                provider=self._messaging_provider.provider_name,
                stage="manual_operator_media_send",
            ).inc()
            self._session.add(
                self._build_media_asset_event(
                    account_id=account_id,
                    asset_id=asset.id,
                    waba_id=resolved_waba_id,
                    phone_number_id=conversation_phone_number_id,
                    event_type="media_asset_send_failed",
                    meta_media_id=prepared_reference.meta_media_id,
                    created_by=actor_id or agent_id,
                    payload={
                        "conversation_id": conversation_id,
                        "external_conversation_id": external_conversation_id,
                        "internal_conversation_id": internal_conversation_id,
                        "caption": source_caption,
                        "error": str(exc),
                        "provider": self._messaging_provider.provider_name,
                        "waba_id": resolved_waba_id,
                        "phone_number_id": prepared_reference.phone_number_id,
                        "provider_media_id": provider_media_id,
                        "meta_media_id": meta_media_id,
                        "sync_status": prepared_reference.provider_sync.sync_status,
                    },
                )
            )
            self._runtime_state.add_audit_log(
                account_id=account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="media_asset_send_failed",
                target_type="media_asset",
                target_id=asset.id,
                payload={
                    "conversation_id": conversation_id,
                    "external_conversation_id": external_conversation_id,
                    "internal_conversation_id": internal_conversation_id,
                    "caption": source_caption,
                    "error": str(exc),
                    "provider": self._messaging_provider.provider_name,
                    "waba_id": resolved_waba_id,
                    "phone_number_id": prepared_reference.phone_number_id,
                    "provider_media_id": provider_media_id,
                    "meta_media_id": meta_media_id,
                    "sync_status": prepared_reference.provider_sync.sync_status,
                },
            )
            self._session.commit()
            detail = f"Media asset send failed: {exc}"
            if isinstance(exc, RuntimeError):
                raise MediaProviderUpstreamError(detail) from exc
            if isinstance(exc, ValueError) and "access_token" in str(exc) and "requires" in str(exc):
                raise MediaProviderConfigError(detail) from exc
            raise ValueError(detail) from exc

        business_outbound_messages_total.labels(
            provider=dispatch_result.provider_name,
            delivery_mode="manual_operator_media_send",
            outcome="accepted",
        ).inc()
        message = await self._runtime_state.record_outbound_message(
            account_id=account_id,
            conversation_id=conversation_id,
            recipient_id=conversation.customer_id,
            text=delivered_caption or asset.name,
            language_code=conversation.customer_language if translated else source_language,
            translated_text=source_caption if translated else None,
            translated_language_code=source_language if translated else None,
            delivery_mode="manual_operator_media_send",
            ai_generated=False,
            payload={
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_type": asset.asset_type,
                "mime_type": asset.mime_type,
                "storage_key": asset.storage_key,
                "storage_url": asset.storage_url,
                "waba_id": resolved_waba_id,
                "phone_number_id": prepared_reference.phone_number_id,
                "provider_media_id": provider_media_id,
                "meta_media_id": meta_media_id,
                "operator_caption": source_caption,
                "delivered_caption": delivered_caption,
                "translated": translated,
                "agent_id": agent_id,
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "provider_accepted": dispatch_result.accepted,
            },
            message_type=asset.asset_type,
            sent_by_agent_id=sent_by_agent_id,
            provider_message_id=dispatch_result.provider_message_id,
        )
        self._session.add(
            self._build_media_asset_event(
                account_id=account_id,
                asset_id=asset.id,
                waba_id=resolved_waba_id,
                phone_number_id=conversation_phone_number_id,
                event_type="media_asset_sent",
                meta_media_id=prepared_reference.meta_media_id,
                created_by=actor_id or agent_id,
                payload={
                    "conversation_id": conversation_id,
                    "external_conversation_id": external_conversation_id,
                    "internal_conversation_id": internal_conversation_id,
                    "message_id": message.id,
                    "provider": dispatch_result.provider_name,
                    "provider_message_id": dispatch_result.provider_message_id,
                    "storage_key": asset.storage_key,
                    "storage_url": asset.storage_url,
                    "waba_id": resolved_waba_id,
                    "provider_media_id": provider_media_id,
                    "meta_media_id": meta_media_id,
                    "caption": delivered_caption,
                    "translated": translated,
                    "sync_status": prepared_reference.provider_sync.sync_status,
                },
            )
        )
        self._runtime_state.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="media_asset_sent",
            target_type="media_asset",
            target_id=asset.id,
            payload={
                "conversation_id": conversation_id,
                "external_conversation_id": external_conversation_id,
                "internal_conversation_id": internal_conversation_id,
                "message_id": message.id,
                "provider": dispatch_result.provider_name,
                "provider_message_id": dispatch_result.provider_message_id,
                "waba_id": resolved_waba_id,
                "phone_number_id": conversation_phone_number_id,
                "storage_key": asset.storage_key,
                "storage_url": asset.storage_url,
                "provider_media_id": provider_media_id,
                "meta_media_id": meta_media_id,
                "translated": translated,
                "sync_status": prepared_reference.provider_sync.sync_status,
            },
        )
        self._session.commit()
        return MediaAssetSendResponse(
            account_id=account_id,
            conversation_id=external_conversation_id,
            external_conversation_id=external_conversation_id,
            internal_conversation_id=internal_conversation_id,
            asset_id=asset.id,
            waba_id=resolved_waba_id,
            phone_number_id=conversation_phone_number_id,
            provider_media_id=provider_media_id,
            message_type=asset.asset_type,
            caption=source_caption,
            delivered_caption=delivered_caption,
            translated=translated,
            message_id=message.id,
            provider=dispatch_result.provider_name,
            provider_message_id=dispatch_result.provider_message_id,
        )

    def _require_asset(self, asset_id: str) -> MediaAsset:
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

    def _resolve_phone_number(
        self,
        *,
        account_id: str,
        provider_phone_number_id: str | None,
    ) -> WhatsAppPhoneNumber | None:
        if provider_phone_number_id is None:
            return None
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

    def _resolve_waba_scope(
        self,
        *,
        account_id: str,
        requested_waba_id: str | None,
        phone_number: WhatsAppPhoneNumber | None,
    ) -> str | None:
        phone_waba_id = self._resolve_phone_waba_id(phone_number)
        if requested_waba_id is None:
            return phone_waba_id
        if phone_waba_id is not None and phone_waba_id != requested_waba_id:
            raise ValueError(
                f"WABA '{requested_waba_id}' does not match phone number '{phone_number.phone_number_id}'."
            )
        waba_account = self._session.scalars(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == requested_waba_id,
            )
        ).first()
        if waba_account is None:
            raise ValueError(
                f"WABA '{requested_waba_id}' for account '{account_id}' was not found."
            )
        return requested_waba_id

    @staticmethod
    def _resolve_phone_waba_id(phone_number: WhatsAppPhoneNumber | None) -> str | None:
        if phone_number is None:
            return None
        if phone_number.waba_id:
            return phone_number.waba_id
        if phone_number.waba_account is not None:
            return phone_number.waba_account.waba_id
        return None

    @staticmethod
    def _resolve_provider_phone_number_id_from_conversation(conversation: object) -> str | None:
        phone_number = getattr(conversation, "phone_number", None)
        provider_phone_number_id = getattr(phone_number, "phone_number_id", None)
        if isinstance(provider_phone_number_id, str) and provider_phone_number_id:
            return provider_phone_number_id
        return None

    def _ensure_agent_can_reply(
        self,
        conversation: object,
        agent_id: str | None,
    ) -> None:
        if agent_id is None:
            return
        management_mode = str(getattr(conversation, "management_mode"))
        assigned_agent = getattr(conversation, "assigned_agent", None)
        assigned_agent_id = self._runtime_state.get_public_agent_id(
            assigned_agent,
            fallback=getattr(conversation, "assigned_agent_id"),
        )
        if management_mode not in {"human_managed", "paused"}:
            raise PermissionError(
                "Manual operator media sends require the conversation to be in human_managed or paused mode."
            )
        if assigned_agent_id != agent_id:
            raise PermissionError(
                f"Agent '{agent_id}' cannot reply to this conversation; it is assigned to '{assigned_agent_id}'."
            )

    @staticmethod
    def _resolve_storage_root(storage_root: str) -> Path:
        path = Path(storage_root).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    @staticmethod
    def _resolve_uploaded_name(*, name: str | None, file_name: str | None) -> str:
        candidate = (name or "").strip() or (file_name or "").strip()
        if candidate:
            return candidate[:255]
        return f"asset-{uuid4().hex[:12]}"

    @staticmethod
    def _resolve_uploaded_mime_type(
        *,
        provided_mime_type: str | None,
        detected_content_type: str | None,
        file_name: str | None,
    ) -> str:
        for candidate in (provided_mime_type, detected_content_type):
            normalized = (candidate or "").strip().lower()
            if normalized and normalized != "application/octet-stream":
                return normalized
        guessed_mime_type, _ = mimetypes.guess_type(file_name or "")
        if guessed_mime_type:
            return guessed_mime_type.lower()
        fallback = (provided_mime_type or detected_content_type or "").strip().lower()
        return fallback or "application/octet-stream"

    @staticmethod
    def _resolve_uploaded_asset_type(
        *,
        explicit_asset_type: MediaAssetType | None,
        mime_type: str,
    ) -> MediaAssetType:
        inferred_asset_type: MediaAssetType
        if mime_type.startswith("image/"):
            inferred_asset_type = "image"
        elif mime_type.startswith("audio/"):
            inferred_asset_type = "audio"
        elif mime_type.startswith("video/"):
            inferred_asset_type = "video"
        else:
            inferred_asset_type = "document"
        if explicit_asset_type is not None and explicit_asset_type != inferred_asset_type:
            raise ValueError(
                f"Uploaded file mime_type '{mime_type}' does not match asset_type '{explicit_asset_type}'."
            )
        return explicit_asset_type or inferred_asset_type

    def _build_storage_path(
        self,
        *,
        account_id: str,
        phone_number_id: str | None,
        file_name: str | None,
        mime_type: str,
    ) -> Path:
        scope_directory = self._sanitize_storage_segment(phone_number_id or "_shared")
        target_directory = self._storage_root / self._sanitize_storage_segment(account_id) / scope_directory
        extension = self._resolve_storage_extension(file_name=file_name, mime_type=mime_type)
        target_path = target_directory / f"{uuid4().hex}{extension}"
        resolved_target_path = target_path.resolve()
        if self._storage_root not in resolved_target_path.parents:
            raise ValueError("Media asset upload resolved outside the storage root.")
        return resolved_target_path

    @staticmethod
    def _resolve_storage_extension(*, file_name: str | None, mime_type: str) -> str:
        suffix = Path(file_name or "").suffix.strip().lower()
        if suffix and len(suffix) <= 16 and re.fullmatch(r"\.[a-z0-9]+", suffix):
            return suffix
        guessed_extension = mimetypes.guess_extension(mime_type, strict=False)
        if guessed_extension:
            return guessed_extension.lower()
        return ".bin"

    @staticmethod
    def _sanitize_storage_segment(value: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
        return sanitized.strip(".-") or "asset"

    @staticmethod
    async def _write_storage_file(*, storage_path: Path, file_bytes: bytes) -> None:
        await to_thread(storage_path.parent.mkdir, parents=True, exist_ok=True)
        await to_thread(storage_path.write_bytes, file_bytes)

    @staticmethod
    async def _delete_storage_file(storage_path: Path) -> None:
        if storage_path.exists():
            await to_thread(storage_path.unlink)

    def _serialize_asset(self, asset: MediaAsset) -> MediaAssetView:
        resolved_waba_id = self._resolve_asset_waba_id(asset)
        resolved_phone_number_id = self._resolve_asset_provider_phone_number_id(asset)
        return MediaAssetView(
            asset_id=asset.id,
            account_id=asset.account_id,
            waba_id=resolved_waba_id,
            phone_number_id=resolved_phone_number_id,
            name=asset.name,
            asset_type=asset.asset_type,
            mime_type=asset.mime_type,
            file_size=asset.file_size,
            storage_key=asset.storage_key,
            storage_url=asset.storage_url,
            legacy_meta_media_id=asset.meta_media_id,
            legacy_meta_media_status=asset.meta_media_status,
            meta_media_id=asset.meta_media_id,
            meta_media_status=asset.meta_media_status,
            provider_references=[
                MediaAssetService._serialize_provider_sync(sync)
                for sync in asset.provider_syncs
            ],
            source=asset.source,
            tags=list(asset.tags_json or []),
            created_by=asset.created_by,
            is_active=asset.is_active,
            created_at=asset.created_at.isoformat(),
            updated_at=asset.updated_at.isoformat(),
        )

    @staticmethod
    def _serialize_event(event: MediaAssetEvent) -> MediaAssetEventView:
        payload_provider_media_id = (
            event.payload.get("provider_media_id")
            if isinstance(event.payload, dict)
            else None
        )
        return MediaAssetEventView(
            id=event.id,
            account_id=event.account_id,
            asset_id=event.asset_id,
            waba_id=getattr(event, "waba_id", None),
            phone_number_id=event.phone_number_id,
            event_type=event.event_type,
            provider_media_id=(
                getattr(event, "provider_media_id", None)
                or payload_provider_media_id
                or event.meta_media_id
            ),
            meta_media_id=event.meta_media_id,
            created_by=event.created_by,
            payload=event.payload,
            created_at=event.created_at.isoformat(),
        )

    @staticmethod
    def _serialize_provider_sync(sync: MediaAssetProviderSync) -> MediaAssetProviderSyncView:
        return MediaAssetProviderSyncView(
            id=sync.id,
            account_id=sync.account_id,
            asset_id=sync.asset_id,
            provider_name=sync.provider_name,
            waba_id=sync.waba_id,
            phone_number_id=sync.phone_number_id,
            provider_media_id=getattr(sync, "provider_media_id", None) or sync.meta_media_id,
            meta_media_id=sync.meta_media_id,
            sync_status=sync.sync_status,
            last_synced_at=sync.last_synced_at.isoformat() if sync.last_synced_at is not None else None,
            last_error_code=sync.last_error_code,
            last_error_message=sync.last_error_message,
            raw_response=sync.raw_response,
            created_at=sync.created_at.isoformat(),
            updated_at=sync.updated_at.isoformat(),
        )

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

    def _asset_matches_query(self, asset: MediaAsset, search_value: str) -> bool:
        resolved_waba_id = self._resolve_asset_waba_id(asset)
        resolved_phone_number_id = self._resolve_asset_provider_phone_number_id(asset)
        haystacks = [
            asset.name,
            asset.mime_type,
            asset.storage_key,
            asset.storage_url,
            asset.meta_media_id,
            asset.meta_media_status,
            asset.source,
            resolved_waba_id,
            resolved_phone_number_id,
            asset.phone_number.display_phone_number if asset.phone_number is not None else None,
        ]
        haystacks.extend(
            (getattr(sync, "provider_media_id", None) or sync.meta_media_id)
            for sync in asset.provider_syncs
            if getattr(sync, "provider_media_id", None) or sync.meta_media_id
        )
        haystacks.extend(sync.sync_status for sync in asset.provider_syncs if sync.sync_status)
        haystacks.extend(str(item) for item in (asset.tags_json or []))
        return any(
            search_value in value.lower()
            for value in haystacks
            if isinstance(value, str) and value
        )

    @staticmethod
    def _build_usage_summary(events: list[MediaAssetEvent]) -> MediaAssetUsageSummary:
        sent_event_types = {"media_asset_sent", "media_asset_template_sent"}
        failed_event_types = {"media_asset_send_failed", "media_asset_template_send_failed"}
        sync_event_types = {"media_asset_sync_succeeded", "media_asset_sync_reused"}
        sync_failed_event_types = {"media_asset_sync_failed"}
        delivered_status_event_types = {
            "media_asset_status_delivered",
            "media_asset_template_status_delivered",
        }
        read_status_event_types = {
            "media_asset_status_read",
            "media_asset_template_status_read",
        }
        provider_failed_status_event_types = {
            "media_asset_status_failed",
            "media_asset_template_status_failed",
        }

        def first_timestamp(event_types: set[str] | None = None) -> str | None:
            for event in events:
                if event_types is None or event.event_type in event_types:
                    return event.created_at.isoformat()
            return None

        return MediaAssetUsageSummary(
            total_events=len(events),
            sync_count=sum(1 for event in events if event.event_type in sync_event_types),
            sync_failed_count=sum(1 for event in events if event.event_type in sync_failed_event_types),
            send_count=sum(1 for event in events if event.event_type == "media_asset_sent"),
            send_failed_count=sum(
                1 for event in events if event.event_type == "media_asset_send_failed"
            ),
            template_send_count=sum(
                1 for event in events if event.event_type == "media_asset_template_sent"
            ),
            template_send_failed_count=sum(
                1
                for event in events
                if event.event_type == "media_asset_template_send_failed"
            ),
            delivered_status_count=sum(
                1 for event in events if event.event_type in delivered_status_event_types
            ),
            read_status_count=sum(
                1 for event in events if event.event_type in read_status_event_types
            ),
            provider_failed_status_count=sum(
                1 for event in events if event.event_type in provider_failed_status_event_types
            ),
            last_event_at=first_timestamp(),
            last_synced_at=first_timestamp(sync_event_types),
            last_sync_failed_at=first_timestamp(sync_failed_event_types),
            last_sent_at=first_timestamp(sent_event_types),
            last_failed_at=first_timestamp(failed_event_types),
            last_delivered_at=first_timestamp(delivered_status_event_types),
            last_read_at=first_timestamp(read_status_event_types),
            last_provider_failed_at=first_timestamp(provider_failed_status_event_types),
        )

    @staticmethod
    def _ensure_asset_account_allowed(
        *,
        asset: MediaAsset,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if allowed_account_ids is None or asset.account_id in allowed_account_ids:
            return
        raise PermissionError(
            f"Media asset '{asset.id}' does not belong to an accessible account scope."
        )

    def _resolve_asset_provider_phone_number_id(self, asset: MediaAsset) -> str | None:
        binding_event = self._resolve_latest_asset_binding_event(asset)
        if binding_event is not None:
            return binding_event.phone_number_id
        for sync in sorted(
            asset.provider_syncs,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        ):
            if sync.phone_number_id:
                return sync.phone_number_id
        bound_phone_number = MediaAssetService._resolve_bound_asset_phone_number(asset)
        if bound_phone_number is not None and bound_phone_number.phone_number_id:
            return bound_phone_number.phone_number_id
        return None

    def _resolve_current_asset_provider_phone_number_id(self, asset: MediaAsset) -> str | None:
        binding_event = self._resolve_latest_asset_binding_event(asset)
        if binding_event is not None:
            return binding_event.phone_number_id
        return self._resolve_asset_snapshot_provider_phone_number_id(asset)

    def _resolve_asset_snapshot_provider_phone_number_id(self, asset: MediaAsset) -> str | None:
        binding_event = self._resolve_latest_asset_binding_event(asset)
        if binding_event is not None and binding_event.phone_number_id:
            return binding_event.phone_number_id
        bound_phone_number = MediaAssetService._resolve_bound_asset_phone_number(asset)
        if bound_phone_number is not None and bound_phone_number.phone_number_id:
            return bound_phone_number.phone_number_id
        return None

    def _resolve_latest_asset_binding_event(self, asset: MediaAsset) -> MediaAssetEvent | None:
        if asset.events:
            binding_events = [
                event
                for event in asset.events
                if event.event_type in {"media_asset_created", "media_asset_uploaded", "media_asset_updated"}
            ]
            if binding_events:
                return max(binding_events, key=lambda item: (item.created_at, item.id))
        return self._session.scalars(
            select(MediaAssetEvent)
            .where(
                MediaAssetEvent.asset_id == asset.id,
                MediaAssetEvent.event_type.in_(
                    ("media_asset_created", "media_asset_uploaded", "media_asset_updated")
                ),
            )
            .order_by(MediaAssetEvent.created_at.desc(), MediaAssetEvent.id.desc())
            .limit(1)
        ).first()

    @staticmethod
    def _resolve_asset_waba_id(asset: MediaAsset) -> str | None:
        if asset.waba_id:
            return asset.waba_id
        if asset.phone_number_id is None:
            return None
        for sync in sorted(
            asset.provider_syncs,
            key=lambda item: (item.updated_at, item.created_at, item.id),
            reverse=True,
        ):
            if sync.waba_id:
                return sync.waba_id
        bound_phone_number = MediaAssetService._resolve_bound_asset_phone_number(asset)
        if bound_phone_number is not None:
            resolved_phone_waba_id = MediaAssetService._resolve_phone_waba_id(bound_phone_number)
            if resolved_phone_waba_id:
                return resolved_phone_waba_id
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

    def _has_historical_asset_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
    ) -> bool:
        return self._session.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.account_id == account_id,
                or_(
                    (
                        (MediaAsset.waba_id == waba_id)
                        & MediaAsset.phone_number.has(
                            WhatsAppPhoneNumber.phone_number_id == phone_number_id
                        )
                    ),
                    MediaAsset.provider_syncs.any(
                        (MediaAssetProviderSync.waba_id == waba_id)
                        & (MediaAssetProviderSync.phone_number_id == phone_number_id)
                    ),
                    MediaAsset.events.any(
                        (MediaAssetEvent.waba_id == waba_id)
                        & (MediaAssetEvent.phone_number_id == phone_number_id)
                    ),
                ),
            )
            .limit(1)
        ).first() is not None

    def _validate_account_waba_scope(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        if account_id is None or waba_id is None:
            return

        current_waba = self._session.scalars(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == waba_id,
            )
        ).first()
        if current_waba is not None:
            return

        if self._has_historical_waba_scope(account_id=account_id, waba_id=waba_id):
            return

        owner_query = select(WhatsAppBusinessAccount.account_id).where(
            WhatsAppBusinessAccount.waba_id == waba_id
        )
        if allowed_account_ids is not None:
            owner_query = owner_query.where(
                WhatsAppBusinessAccount.account_id.in_(allowed_account_ids)
            )
        owner_account_id = self._session.execute(owner_query.limit(1)).scalar_one_or_none()
        if owner_account_id is not None and owner_account_id != account_id:
            raise ValueError(
                f"WABA '{waba_id}' belongs to account '{owner_account_id}', not '{account_id}'."
            )

    def _has_historical_waba_scope(
        self,
        *,
        account_id: str,
        waba_id: str,
    ) -> bool:
        return self._session.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.account_id == account_id,
                or_(
                    MediaAsset.waba_id == waba_id,
                    MediaAsset.provider_syncs.any(MediaAssetProviderSync.waba_id == waba_id),
                    MediaAsset.events.any(MediaAssetEvent.waba_id == waba_id),
                ),
            )
            .limit(1)
        ).first() is not None

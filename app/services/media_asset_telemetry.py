from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    MediaAsset,
    MediaAssetEvent,
    Message,
    TemplateSendLog,
    WhatsAppPhoneNumber,
)
from app.schemas.messaging import ProviderStatusUpdate


STATUS_EVENT_TYPES: dict[str, tuple[str, str]] = {
    "DELIVERED": ("media_asset_status_delivered", "media_asset_template_status_delivered"),
    "READ": ("media_asset_status_read", "media_asset_template_status_read"),
    "FAILED": ("media_asset_status_failed", "media_asset_template_status_failed"),
}


class MediaAssetTelemetryRecorder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_provider_status_update(
        self,
        *,
        account_id: str,
        update: ProviderStatusUpdate,
        message: Message | None,
        conversation: Conversation | None,
        template_send_log: TemplateSendLog | None,
    ) -> None:
        status_key = update.external_status.upper()
        event_names = STATUS_EVENT_TYPES.get(status_key)
        if event_names is None:
            return

        if message is not None:
            asset_id = self._pick_payload_string(message.payload, "asset_id")
            if asset_id is not None and self._asset_exists(asset_id):
                message_provider_media_id = self._pick_payload_string(
                    message.payload, "provider_media_id"
                )
                message_meta_media_id = self._pick_payload_string(
                    message.payload, "meta_media_id"
                )
                resolved_message_provider_media_id = (
                    message_provider_media_id or message_meta_media_id
                )
                message_provider_reference_source = self._resolve_provider_reference_source(
                    provider_media_id=message_provider_media_id,
                    legacy_meta_media_id=message_meta_media_id,
                )
                self._session.add(
                    MediaAssetEvent(
                        account_id=account_id,
                        asset_id=asset_id,
                        waba_id=self._resolve_waba_id(
                            asset_id=asset_id,
                            update=update,
                            message=message,
                            conversation=conversation,
                            template_send_log=None,
                        ),
                        phone_number_id=self._resolve_phone_number_id(
                            update=update,
                            asset_id=asset_id,
                            message=message,
                            conversation=conversation,
                        ),
                        event_type=event_names[0],
                        provider_media_id=resolved_message_provider_media_id,
                        meta_media_id=message_meta_media_id,
                        created_by=message.sent_by_agent_id,
                        payload={
                            **self._build_conversation_identity_payload(conversation),
                            "message_id": message.id,
                            "provider": update.provider_name,
                            "provider_message_id": update.provider_message_id,
                            "external_status": status_key,
                            "occurred_at": update.occurred_at,
                            "error_code": update.error_code,
                            "asset_type": self._pick_payload_string(message.payload, "asset_type"),
                            "provider_media_id": resolved_message_provider_media_id,
                            "meta_media_id": message_meta_media_id,
                            "provider_media_reference_source": (
                                message_provider_reference_source
                            ),
                            "legacy_meta_media_id_used_as_provider_reference": (
                                message_provider_reference_source == "legacy_meta_media_id"
                            ),
                            "source": "manual_operator_send",
                        },
                    )
                )

        if (
            template_send_log is not None
            and template_send_log.header_media_asset_id is not None
            and self._asset_exists(template_send_log.header_media_asset_id)
        ):
            template_provider_media_id = template_send_log.header_media_provider_media_id
            template_meta_media_id = template_send_log.header_media_meta_media_id
            resolved_template_provider_media_id = (
                template_provider_media_id or template_meta_media_id
            )
            template_provider_reference_source = self._resolve_provider_reference_source(
                provider_media_id=template_provider_media_id,
                legacy_meta_media_id=template_meta_media_id,
            )
            self._session.add(
                MediaAssetEvent(
                    account_id=account_id,
                    asset_id=template_send_log.header_media_asset_id,
                    waba_id=self._resolve_waba_id(
                        asset_id=template_send_log.header_media_asset_id,
                        update=update,
                        message=message,
                        conversation=conversation,
                        template_send_log=template_send_log,
                    ),
                    phone_number_id=self._resolve_template_send_log_phone_number_id(
                        account_id=account_id,
                        update=update,
                        template_send_log=template_send_log,
                        message=message,
                        conversation=conversation,
                    ),
                    event_type=event_names[1],
                    provider_media_id=resolved_template_provider_media_id,
                    meta_media_id=template_meta_media_id,
                    created_by=None,
                    payload={
                        **self._build_conversation_identity_payload(conversation),
                        "template_send_log_id": template_send_log.id,
                        "template_id": template_send_log.template_id,
                        "template_name": template_send_log.template_name,
                        "provider": update.provider_name,
                        "provider_message_id": update.provider_message_id,
                        "external_status": status_key,
                        "occurred_at": update.occurred_at,
                        "error_code": update.error_code,
                        "provider_media_id": resolved_template_provider_media_id,
                        "meta_media_id": template_meta_media_id,
                        "provider_media_reference_source": (
                            template_provider_reference_source
                        ),
                        "legacy_meta_media_id_used_as_provider_reference": (
                            template_provider_reference_source
                            == "legacy_meta_media_id"
                        ),
                        "source": "template_header_send",
                    },
                )
            )

    @staticmethod
    def _build_conversation_identity_payload(
        conversation: Conversation | None,
    ) -> dict[str, str | None]:
        external_conversation_id = (
            conversation.external_conversation_id if conversation is not None else None
        )
        internal_conversation_id = conversation.id if conversation is not None else None
        return {
            "conversation_id": external_conversation_id,
            "external_conversation_id": external_conversation_id,
            "internal_conversation_id": internal_conversation_id,
        }

    def _asset_exists(self, asset_id: str) -> bool:
        return self._session.get(MediaAsset, asset_id) is not None

    @staticmethod
    def _resolve_provider_reference_source(
        *,
        provider_media_id: str | None,
        legacy_meta_media_id: str | None,
    ) -> str | None:
        if provider_media_id:
            return "provider_media_id"
        if legacy_meta_media_id:
            return "legacy_meta_media_id"
        return None

    @staticmethod
    def _pick_payload_string(payload: dict[str, object] | None, key: str) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        return value if isinstance(value, str) and value else None

    @classmethod
    def _pick_nested_payload_string(
        cls,
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        direct_value = cls._pick_payload_string(payload, key)
        if direct_value is not None:
            return direct_value
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            metadata_value = cls._pick_payload_string(metadata, key)
            if metadata_value is not None:
                return metadata_value
        for candidate_key in ("provider_payload", "raw_payload"):
            candidate = payload.get(candidate_key)
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._pick_nested_payload_string(candidate, key)
            if nested_value is not None:
                return nested_value
        return None

    def _resolve_phone_number_id(
        self,
        *,
        update: ProviderStatusUpdate | None = None,
        asset_id: str | None,
        message: Message,
        conversation: Conversation | None,
    ) -> str | None:
        update_phone_number_id = self._resolve_update_payload_phone_number_id(update)
        if update_phone_number_id is not None:
            return update_phone_number_id
        if isinstance(message.payload, dict):
            payload_phone_number_id = self._pick_nested_payload_string(
                message.payload,
                "phone_number_id",
            )
            if payload_phone_number_id:
                return payload_phone_number_id
        if message.phone_number is not None:
            return message.phone_number.phone_number_id
        if asset_id is not None:
            asset = self._session.get(MediaAsset, asset_id)
            if asset is not None and asset.phone_number is not None:
                return asset.phone_number.phone_number_id
        if conversation is not None and conversation.phone_number is not None:
            return conversation.phone_number.phone_number_id
        return None

    def _resolve_template_send_log_phone_number_id(
        self,
        *,
        account_id: str,
        update: ProviderStatusUpdate | None = None,
        template_send_log: TemplateSendLog,
        message: Message | None,
        conversation: Conversation | None,
    ) -> str | None:
        update_phone_number_id = self._resolve_update_payload_phone_number_id(update)
        if update_phone_number_id is not None:
            return update_phone_number_id
        if message is not None:
            resolved_from_message = self._resolve_phone_number_id(
                update=update,
                asset_id=None,
                message=message,
                conversation=conversation,
            )
            if resolved_from_message is not None:
                return resolved_from_message
        if not template_send_log.phone_number_id:
            return None
        phone_number = self._session.get(WhatsAppPhoneNumber, template_send_log.phone_number_id)
        if phone_number is not None:
            return phone_number.phone_number_id
        return template_send_log.phone_number_id

    def _resolve_waba_id(
        self,
        *,
        asset_id: str,
        update: ProviderStatusUpdate | None = None,
        message: Message | None,
        conversation: Conversation | None,
        template_send_log: TemplateSendLog | None,
    ) -> str | None:
        update_waba_id = self._resolve_update_payload_waba_id(update)
        if update_waba_id is not None:
            return update_waba_id
        if message is not None:
            payload_waba_id = self._pick_nested_payload_string(message.payload, "waba_id")
            if payload_waba_id:
                return payload_waba_id
        if template_send_log is not None and template_send_log.waba_id:
            return template_send_log.waba_id
        asset = self._session.get(MediaAsset, asset_id)
        if asset is not None:
            if asset.waba_id:
                return asset.waba_id
            if asset.phone_number is not None:
                if asset.phone_number.waba_id:
                    return asset.phone_number.waba_id
                if asset.phone_number.waba_account is not None:
                    return asset.phone_number.waba_account.waba_id
        if message is not None and message.phone_number is not None:
            message_waba_id = message.phone_number.waba_id or (
                message.phone_number.waba_account.waba_id
                if message.phone_number.waba_account is not None
                else None
            )
            if message_waba_id:
                return message_waba_id
        if conversation is not None and conversation.phone_number is not None:
            conversation_waba_id = conversation.phone_number.waba_id or (
                conversation.phone_number.waba_account.waba_id
                if conversation.phone_number.waba_account is not None
                else None
            )
            if conversation_waba_id:
                return conversation_waba_id
        return None

    def _resolve_update_payload_phone_number_id(
        self,
        update: ProviderStatusUpdate | None,
    ) -> str | None:
        if update is None:
            return None
        if update.phone_number_id:
            return update.phone_number_id
        return self._pick_nested_payload_string(update.payload, "phone_number_id")

    def _resolve_update_payload_waba_id(
        self,
        update: ProviderStatusUpdate | None,
    ) -> str | None:
        if update is None:
            return None
        if update.waba_id:
            return update.waba_id
        return self._pick_nested_payload_string(update.payload, "waba_id")

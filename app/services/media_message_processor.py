import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import WhatsAppPhoneNumber, WhatsAppBusinessAccount
from app.providers.messaging.base import MessagingProvider
from app.schemas.media_assets import MediaAssetType
from app.schemas.mock_message import NormalizedMessage
from app.services.media_asset_service import MediaAssetService

logger = structlog.get_logger(__name__)

# Supported media types mapped to MediaAssetType
MEDIA_TYPE_MAP: dict[str, MediaAssetType] = {
    "image": "image",
    "audio": "audio",
    "video": "video",
    "document": "document",
    "sticker": "image",  # stickers stored as images
}


class MediaMessageProcessor:
    """Processes inbound media messages by downloading and storing media assets."""

    def __init__(
        self,
        *,
        session: Session,
        messaging_provider: MessagingProvider,
        media_asset_service: MediaAssetService,
    ) -> None:
        self._session = session
        self._messaging_provider = messaging_provider
        self._media_asset_service = media_asset_service

    async def process_inbound_media(
        self,
        normalized: NormalizedMessage,
    ) -> None:
        """Download and store inbound media if the message contains media.

        This is a best-effort operation: failures are logged but not raised,
        so media processing issues do not block the main message flow.
        """
        asset_type = MEDIA_TYPE_MAP.get(normalized.message_type)
        if asset_type is None:
            logger.debug(
                "media_message_processor_skipped_non_media_type",
                message_type=normalized.message_type,
            )
            return

        metadata = normalized.metadata or {}
        provider_media_id = metadata.get("provider_media_id")
        if not provider_media_id or not isinstance(provider_media_id, str):
            logger.debug(
                "media_message_processor_missing_provider_media_id",
                conversation_id=normalized.conversation_id,
                message_type=normalized.message_type,
            )
            return

        mime_type = str(metadata.get("mime_type", "application/octet-stream"))
        file_name = str(metadata.get("file_name", f"media-{provider_media_id}"))

        try:
            phone_number = self._resolve_phone_number(
                account_id=normalized.account_id,
                phone_number_id=normalized.phone_number_id,
            )
            waba_account = phone_number.waba_account if phone_number is not None else None
            access_token = waba_account.access_token if waba_account is not None else None
            waba_id = normalized.waba_id or (
                waba_account.waba_id if waba_account is not None else None
            )
            resolved_phone_number_id = (
                phone_number.phone_number_id if phone_number is not None else None
            )

            if not access_token:
                logger.warning(
                    "media_message_processor_no_access_token",
                    account_id=normalized.account_id,
                    waba_id=waba_id,
                    phone_number_id=resolved_phone_number_id,
                )
                return

            download_result = await self._messaging_provider.download_media(
                media_id=provider_media_id,
                access_token=access_token,
                waba_id=waba_id,
                phone_number_id=resolved_phone_number_id,
            )
            downloaded_file_name, file_bytes, downloaded_mime_type = download_result

            resolved_mime_type = mime_type if mime_type != "application/octet-stream" else downloaded_mime_type

            await self._media_asset_service.upload_asset_file(
                account_id=normalized.account_id,
                waba_id=waba_id,
                phone_number_id=resolved_phone_number_id,
                name=file_name,
                asset_type=asset_type,
                mime_type=resolved_mime_type,
                source="webhook_media_download",
                tags=["inbound", normalized.message_type],
                file_name=downloaded_file_name,
                content_type=resolved_mime_type,
                file_bytes=file_bytes,
                actor_type="system",
                actor_id=None,
            )

            logger.info(
                "media_message_processor_downloaded_and_stored",
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
                message_type=normalized.message_type,
                provider_media_id=provider_media_id,
                file_size=len(file_bytes),
                mime_type=resolved_mime_type,
            )
        except Exception:
            logger.exception(
                "media_message_processor_failed",
                account_id=normalized.account_id,
                conversation_id=normalized.conversation_id,
                message_type=normalized.message_type,
                provider_media_id=provider_media_id,
            )

    def _resolve_phone_number(
        self,
        *,
        account_id: str,
        phone_number_id: str | None,
    ) -> WhatsAppPhoneNumber | None:
        if not phone_number_id:
            return None
        result = self._session.execute(
            select(WhatsAppPhoneNumber)
            .options(selectinload(WhatsAppPhoneNumber.waba_account))
            .where(
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
                WhatsAppPhoneNumber.waba_account.has(
                    WhatsAppBusinessAccount.account_id == account_id
                ),
            )
        )
        return result.scalars().first()

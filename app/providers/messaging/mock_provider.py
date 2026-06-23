from uuid import uuid4

from app.providers.messaging.base import MessagingProvider
from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.schemas.mock_message import MockInboundMessage, NormalizedMessage


class MockMessagingProvider(MessagingProvider):
    provider_name = "mock"

    async def normalize_inbound(self, payload: object) -> list[NormalizedMessage]:
        if not isinstance(payload, MockInboundMessage):
            raise TypeError("MockMessagingProvider expects a MockInboundMessage payload.")

        return [
            NormalizedMessage(
                account_id=payload.account_id,
                provider=self.provider_name,
                conversation_id=payload.conversation_id,
                user_id=payload.user_id,
                text=payload.text,
                message_type=payload.message_type,
                waba_id=payload.waba_id,
                phone_number_id=payload.phone_number_id,
                external_message_id=payload.external_message_id,
                metadata=dict(payload.metadata),
            )
        ]

    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        del payload
        return []

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        return OutboundDispatchResult(
            provider_name=self.provider_name,
            provider_message_id=f"mock-wa-{uuid4()}",
            accepted=True,
            external_status="accepted",
            raw_response={
                "message_type": payload.message_type,
                "recipient_id": payload.recipient_id,
                "template_name": payload.template_name,
            },
        )

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        provider_media_id = payload.resolved_existing_provider_media_id or f"mock-media-{uuid4()}"
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            provider_media_id=provider_media_id,
            meta_media_id=provider_media_id,
            sync_status="reused" if payload.resolved_existing_provider_media_id else "synced",
            raw_response={
                "asset_id": payload.asset_id,
                "asset_name": payload.asset_name,
                "asset_type": payload.asset_type,
                "storage_key": payload.storage_key,
                "storage_url": payload.storage_url,
            },
        )

    async def download_media(
        self,
        *,
        media_id: str,
        access_token: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> tuple[str, bytes, str]:
        """Mock download_media returns dummy content based on media_id."""
        mime_type_map: dict[str, tuple[bytes, str]] = {
            "mock-image": (b"mock-image-bytes", "image/png"),
            "mock-audio": (b"mock-audio-bytes", "audio/ogg"),
            "mock-video": (b"mock-video-bytes", "video/mp4"),
            "mock-document": (b"mock-document-bytes", "application/pdf"),
            "mock-sticker": (b"mock-sticker-bytes", "image/webp"),
        }
        if media_id in mime_type_map:
            file_bytes, mime_type = mime_type_map[media_id]
            return f"{media_id}.{mime_type.split('/')[-1]}", file_bytes, mime_type
        return f"{media_id}.bin", b"mock-binary-content", "application/octet-stream"

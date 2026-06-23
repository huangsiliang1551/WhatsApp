from abc import ABC, abstractmethod

from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.schemas.mock_message import NormalizedMessage


class MessagingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def normalize_inbound(self, payload: object) -> list[NormalizedMessage]:
        raise NotImplementedError

    @abstractmethod
    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        raise NotImplementedError

    @abstractmethod
    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        raise NotImplementedError

    @abstractmethod
    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        raise NotImplementedError

    @abstractmethod
    async def download_media(
        self,
        *,
        media_id: str,
        access_token: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> tuple[str, bytes, str]:
        """Download a media file from the messaging provider.

        Args:
            media_id: The provider's media ID to download.
            access_token: Access token for authentication.
            waba_id: Optional WABA ID for scope context.
            phone_number_id: Optional phone number ID for scope context.

        Returns:
            Tuple of (file_name, file_bytes, mime_type).
        """
        raise NotImplementedError

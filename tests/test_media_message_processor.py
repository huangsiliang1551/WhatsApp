"""Tests for MediaMessageProcessor (BE2-012)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
)
from app.providers.messaging.base import MessagingProvider
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.schemas.media_assets import MediaAssetView
from app.schemas.mock_message import NormalizedMessage
from app.services.media_asset_service import MediaAssetService
from app.services.media_message_processor import (
    MEDIA_TYPE_MAP,
    MediaMessageProcessor,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_media_asset_service() -> MagicMock:
    """Create a mock MediaAssetService that records upload calls."""
    service = MagicMock(spec=MediaAssetService)
    service.upload_asset_file = AsyncMock(
        return_value=MediaAssetView(
            asset_id="asset-1",
            account_id="test-account",
            name="test-media",
            asset_type="image",
            mime_type="image/png",
            file_size=100,
            storage_key="2026/06/12/asset-1.png",
            source="webhook_media_download",
            tags=["inbound", "image"],
            is_active=True,
            created_at="2026-06-12T00:00:00Z",
            updated_at="2026-06-12T00:00:00Z",
        )
    )
    return service


@pytest.fixture
def mock_provider() -> MockMessagingProvider:
    return MockMessagingProvider()


@pytest.fixture
def processor(
    db_session_factory: sessionmaker[Session],
    mock_provider: MockMessagingProvider,
    mock_media_asset_service: MagicMock,
) -> MediaMessageProcessor:
    session = db_session_factory()
    waba = WhatsAppBusinessAccount(
        account_id="test-account",
        waba_id="waba-1",
        access_token="mock-access-token",
        portfolio_id=None,
        onboarding_mode="manual",
        token_source="manual",
        is_active=True,
    )
    session.add(waba)
    session.flush()
    phone = WhatsAppPhoneNumber(
        account_id="test-account",
        waba_account_id=waba.id,
        waba_id=waba.waba_id,
        phone_number_id="pn-1",
        display_phone_number="+15550000001",
    )
    session.add(phone)
    session.commit()
    return MediaMessageProcessor(
        session=session,
        messaging_provider=mock_provider,
        media_asset_service=mock_media_asset_service,
    )


def _make_normalized(
    message_type: str = "text",
    provider_media_id: str | None = None,
    **overrides: object,
) -> NormalizedMessage:
    """Helper to build a NormalizedMessage for test scenarios."""
    metadata: dict[str, object] = {}
    if provider_media_id is not None:
        metadata["provider_media_id"] = provider_media_id
        metadata["mime_type"] = overrides.pop("mime_type", "application/octet-stream")
        metadata["file_name"] = overrides.pop("file_name", f"media-{provider_media_id}")

    kwargs: dict[str, object] = {
        "account_id": "test-account",
        "provider": "mock",
        "conversation_id": "wa:pn-1:user-1",
        "user_id": "user-1",
        "text": "",
        "message_type": message_type,
        "waba_id": None,  # DB-resolved when not set
        "phone_number_id": "pn-1",
        "external_message_id": "ext-msg-1",
        "metadata": metadata,
    }
    kwargs.update(overrides)
    return NormalizedMessage(**kwargs)  # type: ignore[arg-type]


class TestMediaMessageProcessorUnit:
    """Unit tests for MediaMessageProcessor with mocked dependencies."""

    @pytest.mark.parametrize(
        ("media_type", "expected_asset_type", "mock_media_id"),
        [
            ("image", "image", "mock-image"),
            ("audio", "audio", "mock-audio"),
            ("video", "video", "mock-video"),
            ("document", "document", "mock-document"),
            ("sticker", "image", "mock-sticker"),
        ],
    )
    async def test_process_inbound_media_downloads_and_stores(
        self,
        processor: MediaMessageProcessor,
        mock_media_asset_service: MagicMock,
        media_type: str,
        expected_asset_type: str,
        mock_media_id: str,
    ) -> None:
        """Each supported media type is downloaded and stored via media_asset_service."""
        normalized = _make_normalized(
            message_type=media_type,
            provider_media_id=mock_media_id,
        )

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_awaited_once()
        call_kwargs = mock_media_asset_service.upload_asset_file.call_args.kwargs
        assert call_kwargs["account_id"] == "test-account"
        assert call_kwargs["asset_type"] == expected_asset_type
        assert call_kwargs["source"] == "webhook_media_download"
        assert call_kwargs["tags"] == ["inbound", media_type]
        assert isinstance(call_kwargs["file_bytes"], bytes)
        assert len(call_kwargs["file_bytes"]) > 0

    async def test_process_inbound_media_skips_text_message(
        self,
        processor: MediaMessageProcessor,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Text messages are skipped without any download attempt."""
        normalized = _make_normalized(message_type="text")

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_not_awaited()

    async def test_process_inbound_media_skips_unknown_type(
        self,
        processor: MediaMessageProcessor,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Unknown message types are silently skipped."""
        normalized = _make_normalized(
            message_type="location",
            provider_media_id="mock-image",
        )

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_not_awaited()

    async def test_process_inbound_media_skips_missing_provider_media_id(
        self,
        processor: MediaMessageProcessor,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Image message without provider_media_id is skipped."""
        normalized = _make_normalized(message_type="image")

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_not_awaited()

    async def test_process_inbound_media_logs_but_does_not_raise_on_error(
        self,
        processor: MediaMessageProcessor,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Download failures are logged but not raised (best-effort)."""
        mock_media_asset_service.upload_asset_file.side_effect = RuntimeError("disk full")
        normalized = _make_normalized(
            message_type="image",
            provider_media_id="mock-image",
        )

        # Should not raise
        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_awaited_once()

    async def test_process_inbound_media_without_access_token_returns_early(
        self,
        db_session_factory: sessionmaker[Session],
        mock_provider: MockMessagingProvider,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """When no WABA access_token is found, the processor returns early without uploading."""
        session = db_session_factory()
        waba = WhatsAppBusinessAccount(
            account_id="test-account",
            waba_id="waba-no-token",
            access_token=None,
            portfolio_id=None,
            onboarding_mode="manual",
            token_source="manual",
            is_active=True,
        )
        session.add(waba)
        session.flush()
        phone = WhatsAppPhoneNumber(
            account_id="test-account",
            waba_account_id=waba.id,
            waba_id=waba.waba_id,
            phone_number_id="pn-no-token",
            display_phone_number="+15550000001",
        )
        session.add(phone)
        session.commit()

        processor = MediaMessageProcessor(
            session=session,
            messaging_provider=mock_provider,
            media_asset_service=mock_media_asset_service,
        )
        normalized = _make_normalized(
            message_type="image",
            provider_media_id="mock-image",
            phone_number_id="pn-no-token",
        )

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_not_awaited()


class TestMediaMessageProcessorWithDB:
    """Integration-style tests that set up WABA + PhoneNumber in DB."""

    @pytest.fixture
    def setup_waba_phone(self, db_session_factory: sessionmaker[Session]) -> Session:
        session = db_session_factory()
        waba = WhatsAppBusinessAccount(
            account_id="test-account",
            waba_id="waba-media-test",
            access_token="mock-access-token-123",
            portfolio_id=None,
            onboarding_mode="manual",
            token_source="manual",
            is_active=True,
        )
        session.add(waba)
        session.flush()

        phone = WhatsAppPhoneNumber(
            account_id="test-account",
            waba_account_id=waba.id,
            waba_id=waba.waba_id,
            phone_number_id="pn-media-test",
            display_phone_number="+15550000001",
        )
        session.add(phone)
        session.commit()
        return session

    async def test_process_inbound_media_resolves_phone_number_from_db(
        self,
        setup_waba_phone: Session,
        mock_provider: MockMessagingProvider,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Processor resolves WABA access_token via DB phone_number relationship."""
        processor = MediaMessageProcessor(
            session=setup_waba_phone,
            messaging_provider=mock_provider,
            media_asset_service=mock_media_asset_service,
        )
        normalized = _make_normalized(
            message_type="image",
            provider_media_id="mock-image",
            phone_number_id="pn-media-test",
        )

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_awaited_once()
        call_kwargs = mock_media_asset_service.upload_asset_file.call_args.kwargs
        assert call_kwargs["account_id"] == "test-account"
        assert call_kwargs["waba_id"] == "waba-media-test"
        assert call_kwargs["phone_number_id"] == "pn-media-test"

    async def test_process_inbound_media_uses_waba_id_from_normalized(
        self,
        setup_waba_phone: Session,
        mock_provider: MockMessagingProvider,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """When normalized.waba_id is set, it takes precedence over DB-resolved waba_id."""
        processor = MediaMessageProcessor(
            session=setup_waba_phone,
            messaging_provider=mock_provider,
            media_asset_service=mock_media_asset_service,
        )
        normalized = _make_normalized(
            message_type="image",
            provider_media_id="mock-image",
            phone_number_id="pn-media-test",
            waba_id="custom-waba-override",
        )

        await processor.process_inbound_media(normalized)

        mock_media_asset_service.upload_asset_file.assert_awaited_once()
        call_kwargs = mock_media_asset_service.upload_asset_file.call_args.kwargs
        assert call_kwargs["waba_id"] == "custom-waba-override"

    async def test_process_inbound_media_multiple_media_types_all_succeed(
        self,
        setup_waba_phone: Session,
        mock_provider: MockMessagingProvider,
        mock_media_asset_service: MagicMock,
    ) -> None:
        """Processing multiple media messages in sequence works."""
        processor = MediaMessageProcessor(
            session=setup_waba_phone,
            messaging_provider=mock_provider,
            media_asset_service=mock_media_asset_service,
        )

        for media_type, media_id in [
            ("image", "mock-image"),
            ("audio", "mock-audio"),
            ("document", "mock-document"),
        ]:
            normalized = _make_normalized(
                message_type=media_type,
                provider_media_id=media_id,
                phone_number_id="pn-media-test",
            )
            await processor.process_inbound_media(normalized)

        assert mock_media_asset_service.upload_asset_file.await_count == 3


class TestMediaTypeMap:
    """Verify MEDIA_TYPE_MAP covers expected types."""

    def test_all_supported_types_mapped(self) -> None:
        assert MEDIA_TYPE_MAP["image"] == "image"
        assert MEDIA_TYPE_MAP["audio"] == "audio"
        assert MEDIA_TYPE_MAP["video"] == "video"
        assert MEDIA_TYPE_MAP["document"] == "document"
        assert MEDIA_TYPE_MAP["sticker"] == "image"

    def test_unsupported_type_not_mapped(self) -> None:
        assert MEDIA_TYPE_MAP.get("text") is None
        assert MEDIA_TYPE_MAP.get("location") is None
        assert MEDIA_TYPE_MAP.get("unknown") is None

import hashlib
import hmac
from pathlib import Path
from urllib.parse import urlparse
from collections.abc import Mapping

import httpx
import structlog

from app.providers.messaging.base import MessagingProvider
from app.schemas.messaging import (
    MediaAssetSyncRequest,
    MediaAssetSyncResult,
    OutboundDispatchRequest,
    OutboundDispatchResult,
    ProviderStatusUpdate,
)
from app.schemas.mock_message import NormalizedMessage
from app.schemas.whatsapp_webhook import (
    WhatsAppWebhookAudioContent,
    WhatsAppWebhookButtonContent,
    WhatsAppWebhookContact,
    WhatsAppWebhookDocumentContent,
    WhatsAppWebhookImageContent,
    WhatsAppWebhookInteractiveContent,
    WhatsAppWebhookLocationContent,
    WhatsAppWebhookMessage,
    WhatsAppWebhookOrderContent,
    WhatsAppWebhookPayload,
    WhatsAppWebhookReactionContent,
    WhatsAppWebhookReferralContent,
    WhatsAppWebhookSharedContact,
    WhatsAppWebhookStickerContent,
    WhatsAppWebhookStatus,
    WhatsAppWebhookSystemContent,
    WhatsAppWebhookVideoContent,
)

logger = structlog.get_logger(__name__)


class WhatsAppProvider(MessagingProvider):
    provider_name = "whatsapp"

    def __init__(
        self,
        *,
        api_base: str = "https://graph.facebook.com",
        api_version: str = "v20.0",
        timeout_seconds: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def normalize_inbound(self, payload: object) -> list[NormalizedMessage]:
        if not isinstance(payload, WhatsAppWebhookPayload):
            raise TypeError("WhatsAppProvider expects a WhatsAppWebhookPayload payload.")

        normalized_messages: list[NormalizedMessage] = []
        for entry in payload.entry:
            waba_id = entry.id
            for change in entry.changes:
                if change.field != "messages":
                    continue

                metadata = change.value.metadata
                phone_number_id = metadata.phone_number_id if metadata is not None else None
                display_phone_number = (
                    metadata.display_phone_number if metadata is not None else None
                )
                contacts_by_wa_id = self._index_contacts(change.value.contacts)

                for message in change.value.messages:
                    message_text, message_metadata = self._normalize_message_content(message)
                    if message_text is None:
                        continue
                    contact_metadata = self._build_contact_metadata(
                        contacts_by_wa_id=contacts_by_wa_id,
                        user_id=message.from_,
                    )
                    context_metadata = self._build_context_metadata(message)
                    referral_metadata = self._build_referral_metadata(message.referral)

                    normalized_messages.append(
                        NormalizedMessage(
                            account_id="",
                            provider=self.provider_name,
                            conversation_id=self._build_conversation_id(
                                phone_number_id=phone_number_id,
                                user_id=message.from_,
                            ),
                            user_id=message.from_,
                            text=message_text,
                            message_type=message.type,
                            waba_id=waba_id,
                            phone_number_id=phone_number_id,
                            external_message_id=message.id,
                            metadata={
                                "display_phone_number": display_phone_number,
                                "timestamp": message.timestamp,
                                **contact_metadata,
                                **context_metadata,
                                **referral_metadata,
                                **message_metadata,
                            },
                        )
                    )

        return normalized_messages

    async def normalize_status_updates(self, payload: object) -> list[ProviderStatusUpdate]:
        if not isinstance(payload, WhatsAppWebhookPayload):
            raise TypeError("WhatsAppProvider expects a WhatsAppWebhookPayload payload.")

        updates: list[ProviderStatusUpdate] = []
        for entry in payload.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue

                metadata = change.value.metadata
                phone_number_id = metadata.phone_number_id if metadata is not None else None
                for status in change.value.statuses:
                    updates.append(
                        ProviderStatusUpdate(
                            provider_name=self.provider_name,
                            waba_id=entry.id,
                            phone_number_id=phone_number_id,
                            provider_message_id=status.id,
                            external_status=status.status,
                            recipient_id=status.recipient_id,
                            occurred_at=status.timestamp,
                            error_code=self._extract_status_error_code(status.errors),
                            payload=self._build_status_payload(status),
                        )
                    )

        return updates

    async def send_outbound(self, payload: OutboundDispatchRequest) -> OutboundDispatchResult:
        if not payload.phone_number_id:
            raise ValueError("WhatsApp outbound send requires phone_number_id.")
        if not payload.access_token:
            raise ValueError("WhatsApp outbound send requires access_token.")

        request_body = self._build_outbound_request_body(payload)
        endpoint = f"{self._api_base}/{self._api_version}/{payload.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {payload.access_token}"}
        response_json = await self._post_json(endpoint=endpoint, headers=headers, body=request_body)
        provider_message_id = self._extract_provider_message_id(response_json)
        return OutboundDispatchResult(
            provider_name=self.provider_name,
            provider_message_id=provider_message_id,
            accepted=True,
            external_status="accepted",
            raw_response=response_json,
        )

    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:
        existing_provider_media_id = payload.resolved_existing_provider_media_id
        if existing_provider_media_id:
            return MediaAssetSyncResult(
                provider_name=self.provider_name,
                phone_number_id=payload.phone_number_id,
                waba_id=payload.waba_id,
                provider_media_id=existing_provider_media_id,
                sync_status="reused",
                raw_response={"asset_id": payload.asset_id},
            )
        if not payload.phone_number_id:
            raise ValueError("WhatsApp media sync requires phone_number_id.")
        if not payload.access_token:
            raise ValueError("WhatsApp media sync requires access_token.")
        if not payload.storage_key and not payload.storage_url:
            raise ValueError("WhatsApp media sync requires storage_key or storage_url.")

        file_name, file_bytes = await self._load_media_upload_bytes(payload)
        endpoint = f"{self._api_base}/{self._api_version}/{payload.phone_number_id}/media"
        headers = {"Authorization": f"Bearer {payload.access_token}"}
        response_json = await self._post_multipart(
            endpoint=endpoint,
            headers=headers,
            data={
                "messaging_product": "whatsapp",
                "type": payload.mime_type,
            },
            files={
                "file": (file_name, file_bytes, payload.mime_type),
            },
        )
        meta_media_id = self._extract_media_id(response_json)
        if not meta_media_id:
            raise ValueError("WhatsApp media sync did not return a media id.")
        return MediaAssetSyncResult(
            provider_name=self.provider_name,
            phone_number_id=payload.phone_number_id,
            waba_id=payload.waba_id,
            provider_media_id=meta_media_id,
            sync_status="synced",
            raw_response=response_json,
        )

    async def download_media(
        self,
        *,
        media_id: str,
        access_token: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> tuple[str, bytes, str]:
        """Download a media file from the Meta Graph API.

        Uses two-step API:
        1. GET /{api_version}/{media_id} to get the download URL
        2. GET {download_url} to get the file bytes
        """
        media_info_endpoint = f"{self._api_base}/{self._api_version}/{media_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        media_info = await self._get_request(endpoint=media_info_endpoint, headers=headers)
        media_info_json = media_info.json()
        download_url = media_info_json.get("url")
        if not download_url or not isinstance(download_url, str):
            raise RuntimeError(f"WhatsApp media download did not return a download URL for media_id '{media_id}'.")
        mime_type = str(media_info_json.get("mime_type", "application/octet-stream"))
        file_name = str(media_info_json.get("file_name", f"media-{media_id}"))

        file_response = await self._get_request(endpoint=download_url, headers=headers)
        return file_name, file_response.content, mime_type

    @staticmethod
    def build_signature(app_secret: str, body: bytes) -> str:
        digest = hmac.new(
            key=app_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    @classmethod
    def verify_signature(
        cls,
        *,
        signature_header: str | None,
        app_secret: str | None,
        body: bytes,
    ) -> bool:
        if not app_secret:
            return False
        if not signature_header:
            return False
        expected_signature = cls.build_signature(app_secret=app_secret, body=body)
        return hmac.compare_digest(expected_signature, signature_header)

    @staticmethod
    def verify_challenge(
        *,
        mode: str,
        verify_token: str,
        challenge: str,
        expected_verify_token: str,
    ) -> str:
        if mode != "subscribe":
            raise ValueError("Unsupported webhook mode.")
        if verify_token != expected_verify_token:
            raise ValueError("Webhook verify token mismatch.")
        return challenge

    @staticmethod
    def _build_conversation_id(*, phone_number_id: str | None, user_id: str) -> str:
        if phone_number_id:
            return f"wa:{phone_number_id}:{user_id}"
        return f"wa:{user_id}"

    async def _get_request(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            try:
                response = await self._client.get(endpoint, headers=dict(headers))
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                self._raise_request_error(exc, endpoint=endpoint)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(endpoint, headers=dict(headers))
                response.raise_for_status()
                return response
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            self._raise_request_error(exc, endpoint=endpoint)

    async def _post_json(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        body: dict[str, object],
    ) -> dict[str, object]:
        if self._client is not None:
            try:
                response = await self._client.post(endpoint, headers=dict(headers), json=body)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                self._raise_request_error(exc, endpoint=endpoint)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(endpoint, headers=dict(headers), json=body)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            self._raise_request_error(exc, endpoint=endpoint)

    async def _post_multipart(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        data: Mapping[str, str],
        files: Mapping[str, tuple[str, bytes, str]],
    ) -> dict[str, object]:
        if self._client is not None:
            try:
                response = await self._client.post(
                    endpoint,
                    headers=dict(headers),
                    data=dict(data),
                    files=dict(files),
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                self._raise_request_error(exc, endpoint=endpoint)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    endpoint,
                    headers=dict(headers),
                    data=dict(data),
                    files=dict(files),
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            self._raise_request_error(exc, endpoint=endpoint)

    async def _load_media_upload_bytes(
        self,
        payload: MediaAssetSyncRequest,
    ) -> tuple[str, bytes]:
        if payload.storage_key:
            return self._load_media_upload_bytes_from_path(payload)
        if payload.storage_url:
            return await self._load_media_upload_bytes_from_url(payload)
        raise ValueError("WhatsApp media sync requires storage_key or storage_url.")

    def _load_media_upload_bytes_from_path(
        self,
        payload: MediaAssetSyncRequest,
    ) -> tuple[str, bytes]:
        if not payload.storage_key:
            raise ValueError("WhatsApp media sync requires storage_key.")
        path = Path(payload.storage_key).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        if not path.exists() or not path.is_file():
            raise ValueError(f"WhatsApp media sync could not find file '{path}'.")
        return path.name, path.read_bytes()

    async def _load_media_upload_bytes_from_url(
        self,
        payload: MediaAssetSyncRequest,
    ) -> tuple[str, bytes]:
        if not payload.storage_url:
            raise ValueError("WhatsApp media sync requires storage_url.")

        if self._client is not None:
            try:
                response = await self._client.get(payload.storage_url)
                response.raise_for_status()
                return self._extract_upload_file_name(payload.storage_url, payload.asset_name), response.content
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                self._raise_request_error(exc, endpoint=payload.storage_url)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(payload.storage_url)
                response.raise_for_status()
                return self._extract_upload_file_name(payload.storage_url, payload.asset_name), response.content
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            self._raise_request_error(exc, endpoint=payload.storage_url)

    @staticmethod
    def _raise_request_error(exc: httpx.HTTPStatusError | httpx.RequestError, *, endpoint: str) -> None:
        if isinstance(exc, httpx.HTTPStatusError):
            logger.warning(
                "whatsapp_provider_request_http_error",
                endpoint=endpoint,
                status_code=exc.response.status_code,
            )
            raise RuntimeError(
                f"WhatsApp provider request failed with status {exc.response.status_code}."
            ) from exc

        logger.warning(
            "whatsapp_provider_request_failed",
            endpoint=endpoint,
            error=str(exc),
        )
        raise RuntimeError("WhatsApp provider request failed.") from exc

    def _build_outbound_request_body(self, payload: OutboundDispatchRequest) -> dict[str, object]:
        if payload.message_type == "template":
            if not payload.template_name:
                raise ValueError("WhatsApp template send requires template_name.")
            if not payload.template_language:
                raise ValueError("WhatsApp template send requires template_language.")
            return {
                "messaging_product": "whatsapp",
                "to": payload.recipient_id,
                "type": "template",
                "template": {
                    "name": payload.template_name,
                    "language": {"code": payload.template_language},
                    "components": self._build_template_components(payload),
                },
            }

        if payload.message_type in {"image", "audio", "video", "document"}:
            media_payload = self._build_media_payload(payload)
            return {
                "messaging_product": "whatsapp",
                "to": payload.recipient_id,
                "type": payload.message_type,
                payload.message_type: media_payload,
            }

        if payload.message_type == "interactive":
            if not payload.interactive_payload:
                raise ValueError("WhatsApp interactive send requires interactive_payload.")
            return {
                "messaging_product": "whatsapp",
                "to": payload.recipient_id,
                "type": "interactive",
                "interactive": payload.interactive_payload,
            }

        return {
            "messaging_product": "whatsapp",
            "to": payload.recipient_id,
            "type": "text",
            "text": {"body": payload.text},
        }

    @staticmethod
    def _build_status_payload(status: WhatsAppWebhookStatus) -> dict[str, object]:
        payload = status.model_dump(mode="json")
        conversation = getattr(status, "conversation", None)
        pricing = getattr(status, "pricing", None)

        conversation_id = getattr(conversation, "id", None)
        if conversation_id:
            payload["conversation_id"] = conversation_id

        expiration_timestamp = getattr(conversation, "expiration_timestamp", None)
        if expiration_timestamp:
            payload["conversation_expiration_timestamp"] = expiration_timestamp

        origin = getattr(conversation, "origin", None)
        origin_type = getattr(origin, "type", None)
        if origin_type:
            payload["conversation_origin_type"] = origin_type

        category = getattr(pricing, "category", None)
        if category:
            payload["conversation_category"] = category

        pricing_model = getattr(pricing, "pricing_model", None)
        if pricing_model:
            payload["pricing_model"] = pricing_model

        billable = getattr(pricing, "billable", None)
        if billable is not None:
            payload["billable"] = billable

        return payload

    @staticmethod
    def _build_template_components(payload: OutboundDispatchRequest) -> list[dict[str, object]]:
        components: list[dict[str, object]] = []
        if payload.template_header_media_type:
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        WhatsAppProvider._build_template_header_media_parameter(payload),
                    ],
                }
            )
        if payload.template_variables:
            components.append(
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value}
                        for _, value in payload.template_variables.items()
                    ],
                }
            )
        return components

    @staticmethod
    def _build_template_header_media_parameter(
        payload: OutboundDispatchRequest,
    ) -> dict[str, object]:
        media_reference = payload.media_url or payload.media_asset_id
        if not media_reference or not payload.template_header_media_type:
            raise ValueError("Template header media requires media reference and media type.")

        media_payload: dict[str, object] = (
            {"link": media_reference}
            if payload.media_url
            else {"id": media_reference}
        )
        if payload.template_header_media_type == "document" and payload.file_name:
            media_payload["filename"] = payload.file_name
        return {
            "type": payload.template_header_media_type,
            payload.template_header_media_type: media_payload,
        }

    @staticmethod
    def _build_media_payload(payload: OutboundDispatchRequest) -> dict[str, object]:
        media_reference = payload.media_url or payload.media_asset_id
        if not media_reference:
            raise ValueError("WhatsApp media send requires media_url or media_asset_id.")

        media_payload: dict[str, object] = (
            {"link": media_reference}
            if payload.media_url
            else {"id": media_reference}
        )
        if payload.media_caption:
            media_payload["caption"] = payload.media_caption
        if payload.file_name and payload.message_type == "document":
            media_payload["filename"] = payload.file_name
        return media_payload

    @staticmethod
    def _extract_provider_message_id(response_json: Mapping[str, object]) -> str | None:
        messages = response_json.get("messages")
        if not isinstance(messages, list) or not messages:
            return None
        first_message = messages[0]
        if not isinstance(first_message, Mapping):
            return None
        message_id = first_message.get("id")
        return str(message_id) if message_id is not None else None

    @staticmethod
    def _extract_media_id(response_json: Mapping[str, object]) -> str | None:
        media_id = response_json.get("id")
        return str(media_id) if media_id is not None else None

    @staticmethod
    def _extract_upload_file_name(storage_url: str, asset_name: str) -> str:
        parsed = urlparse(storage_url)
        file_name = Path(parsed.path).name
        return file_name or asset_name

    def _normalize_message_content(
        self,
        message: WhatsAppWebhookMessage,
    ) -> tuple[str | None, dict[str, object]]:
        if message.type == "text" and message.text is not None:
            return message.text.body, {"has_meaningful_text": True}
        if message.type == "button" and message.button is not None:
            return self._normalize_button_content(message.button)
        if message.type == "interactive" and message.interactive is not None:
            return self._normalize_interactive_content(message.interactive)
        if message.type == "image" and message.image is not None:
            return self._normalize_image_content(message.image)
        if message.type == "audio" and message.audio is not None:
            return self._normalize_audio_content(message.audio)
        if message.type == "video" and message.video is not None:
            return self._normalize_video_content(message.video)
        if message.type == "document" and message.document is not None:
            return self._normalize_document_content(message.document)
        if message.type == "sticker" and message.sticker is not None:
            return self._normalize_sticker_content(message.sticker)
        if message.type == "reaction" and message.reaction is not None:
            return self._normalize_reaction_content(message.reaction)
        if message.type == "location" and message.location is not None:
            return self._normalize_location_content(message.location)
        if message.type == "order" and message.order is not None:
            return self._normalize_order_content(message.order)
        if message.type == "system" and message.system is not None:
            return self._normalize_system_content(message.system)
        if message.type == "contacts" and message.contacts:
            return self._normalize_contacts_content(message.contacts)
        message_type = message.type.strip() if message.type else "unknown"
        return (
            f"[{message_type} message]",
            {
                "unsupported_message_type": message_type,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _index_contacts(
        contacts: list[WhatsAppWebhookContact],
    ) -> dict[str, WhatsAppWebhookContact]:
        indexed: dict[str, WhatsAppWebhookContact] = {}
        for contact in contacts:
            if contact.wa_id:
                indexed[contact.wa_id] = contact
        return indexed

    @staticmethod
    def _build_contact_metadata(
        *,
        contacts_by_wa_id: dict[str, WhatsAppWebhookContact],
        user_id: str,
    ) -> dict[str, object]:
        contact = contacts_by_wa_id.get(user_id)
        if contact is None:
            return {}
        profile_name = contact.profile.name if contact.profile is not None else None
        return {
            "contact_wa_id": contact.wa_id,
            "contact_profile_name": profile_name,
        }

    @staticmethod
    def _build_context_metadata(
        message: WhatsAppWebhookMessage,
    ) -> dict[str, object]:
        context = message.context
        if context is None:
            return {}

        context_payload = context.model_dump(
            mode="json",
            exclude_none=True,
            by_alias=True,
        )
        if not context_payload:
            return {}

        replied_to_message_id = context.id.strip() if context.id else None
        replied_to_user_id = context.from_.strip() if context.from_ else None
        referred_product = context.referred_product
        referred_catalog_id = (
            referred_product.catalog_id.strip()
            if referred_product is not None and referred_product.catalog_id
            else None
        )
        referred_product_retailer_id = (
            referred_product.product_retailer_id.strip()
            if referred_product is not None and referred_product.product_retailer_id
            else None
        )

        return {
            "context_reply_to_message_id": replied_to_message_id,
            "context_reply_to_user_id": replied_to_user_id,
            "context_forwarded": context.forwarded,
            "context_frequently_forwarded": context.frequently_forwarded,
            "context_referred_product_catalog_id": referred_catalog_id,
            "context_referred_product_retailer_id": referred_product_retailer_id,
            "context_payload": context_payload,
        }

    @staticmethod
    def _build_referral_metadata(
        referral: WhatsAppWebhookReferralContent | None,
    ) -> dict[str, object]:
        if referral is None:
            return {}
        referral_payload = referral.model_dump(mode="json", exclude_none=True)
        if not referral_payload:
            return {}
        return {
            "referral_source_url": referral.source_url,
            "referral_source_type": referral.source_type,
            "referral_source_id": referral.source_id,
            "referral_headline": referral.headline,
            "referral_body": referral.body,
            "referral_media_type": referral.media_type,
            "referral_image_url": referral.image_url,
            "referral_video_url": referral.video_url,
            "referral_thumbnail_url": referral.thumbnail_url,
            "referral_ctwa_clid": referral.ctwa_clid,
            "referral_payload": referral_payload,
        }

    @staticmethod
    def _normalize_button_content(
        button: WhatsAppWebhookButtonContent,
    ) -> tuple[str | None, dict[str, object]]:
        button_text = button.text.strip() if button.text else None
        button_payload = button.payload.strip() if button.payload else None
        return (
            button_text or button_payload,
            {
                "button_text": button_text,
                "button_payload": button_payload,
                "has_meaningful_text": bool(button_text or button_payload),
            },
        )

    @staticmethod
    def _normalize_interactive_content(
        interactive: WhatsAppWebhookInteractiveContent,
    ) -> tuple[str | None, dict[str, object]]:
        reply = None
        if interactive.type == "button_reply" and interactive.button_reply is not None:
            reply = interactive.button_reply
        elif interactive.type == "list_reply" and interactive.list_reply is not None:
            reply = interactive.list_reply
        elif interactive.type == "nfm_reply" and interactive.nfm_reply is not None:
            flow_name = interactive.nfm_reply.name.strip() if interactive.nfm_reply.name else None
            flow_body = interactive.nfm_reply.body.strip() if interactive.nfm_reply.body else None
            return (
                flow_body or flow_name or "[flow reply]",
                {
                    "interactive_type": interactive.type,
                    "interactive_flow_name": flow_name,
                    "interactive_flow_body": flow_body,
                    "interactive_flow_response": interactive.nfm_reply.response_json,
                    "has_meaningful_text": bool(flow_body or flow_name),
                },
            )

        reply_title = reply.title.strip() if reply is not None and reply.title else None
        reply_id = reply.id.strip() if reply is not None and reply.id else None
        interactive_text = reply_title or reply_id
        if interactive_text is None:
            return (
                "[interactive message]",
                {
                    "interactive_type": interactive.type,
                    "has_meaningful_text": False,
                },
            )
        return (
            interactive_text,
            {
                "interactive_type": interactive.type,
                "interactive_reply_id": reply_id,
                "interactive_reply_title": reply_title,
                "has_meaningful_text": interactive_text is not None,
            },
        )

    @staticmethod
    def _normalize_image_content(
        image: WhatsAppWebhookImageContent,
    ) -> tuple[str, dict[str, object]]:
        caption = image.caption.strip() if image.caption else None
        return (
            caption or "[image attachment]",
            {
                "media_kind": "image",
                "provider_media_id": image.id,
                "media_id": image.id,
                "mime_type": image.mime_type,
                "sha256": image.sha256,
                "caption": caption,
                "has_meaningful_text": bool(caption),
            },
        )

    @staticmethod
    def _normalize_audio_content(
        audio: WhatsAppWebhookAudioContent,
    ) -> tuple[str, dict[str, object]]:
        return (
            "[voice message]" if audio.voice else "[audio attachment]",
            {
                "media_kind": "audio",
                "provider_media_id": audio.id,
                "media_id": audio.id,
                "mime_type": audio.mime_type,
                "sha256": audio.sha256,
                "voice": audio.voice,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_video_content(
        video: WhatsAppWebhookVideoContent,
    ) -> tuple[str, dict[str, object]]:
        caption = video.caption.strip() if video.caption else None
        return (
            caption or "[video attachment]",
            {
                "media_kind": "video",
                "provider_media_id": video.id,
                "media_id": video.id,
                "mime_type": video.mime_type,
                "sha256": video.sha256,
                "caption": caption,
                "has_meaningful_text": bool(caption),
            },
        )

    @staticmethod
    def _normalize_document_content(
        document: WhatsAppWebhookDocumentContent,
    ) -> tuple[str, dict[str, object]]:
        caption = document.caption.strip() if document.caption else None
        fallback_text = document.filename.strip() if document.filename else "[document attachment]"
        return (
            caption or fallback_text,
            {
                "media_kind": "document",
                "provider_media_id": document.id,
                "media_id": document.id,
                "mime_type": document.mime_type,
                "sha256": document.sha256,
                "file_name": document.filename,
                "caption": caption,
                "has_meaningful_text": bool(caption),
            },
        )

    @staticmethod
    def _normalize_sticker_content(
        sticker: WhatsAppWebhookStickerContent,
    ) -> tuple[str, dict[str, object]]:
        return (
            "[sticker message]",
            {
                "media_kind": "sticker",
                "provider_media_id": sticker.id,
                "media_id": sticker.id,
                "mime_type": sticker.mime_type,
                "sha256": sticker.sha256,
                "animated": sticker.animated,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_reaction_content(
        reaction: WhatsAppWebhookReactionContent,
    ) -> tuple[str, dict[str, object]]:
        emoji = reaction.emoji.strip() if reaction.emoji else None
        return (
            emoji or "[reaction message]",
            {
                "reaction_to_message_id": reaction.message_id,
                "emoji": emoji,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_location_content(
        location: WhatsAppWebhookLocationContent,
    ) -> tuple[str, dict[str, object]]:
        name = location.name.strip() if location.name else None
        address = location.address.strip() if location.address else None
        location_text = name or address or "[location message]"
        return (
            location_text,
            {
                "location_name": name,
                "location_address": address,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "url": location.url,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_order_content(
        order: WhatsAppWebhookOrderContent,
    ) -> tuple[str, dict[str, object]]:
        product_items = [
            {
                "product_retailer_id": (
                    item.product_retailer_id.strip() if item.product_retailer_id else None
                ),
                "quantity": item.quantity,
                "item_price": item.item_price,
                "currency": item.currency.strip() if item.currency else None,
            }
            for item in order.product_items
        ]
        return (
            "[order message]",
            {
                "order_catalog_id": (
                    order.catalog_id.strip() if order.catalog_id else None
                ),
                "order_product_count": len(product_items),
                "order_product_items": product_items,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_contacts_content(
        contacts: list[WhatsAppWebhookSharedContact],
    ) -> tuple[str, dict[str, object]]:
        summarized_contacts: list[dict[str, object]] = []
        display_names: list[str] = []
        for contact in contacts:
            formatted_name = (
                contact.name.formatted_name.strip()
                if contact.name is not None and contact.name.formatted_name
                else None
            )
            first_name = (
                contact.name.first_name.strip()
                if contact.name is not None and contact.name.first_name
                else None
            )
            last_name = (
                contact.name.last_name.strip()
                if contact.name is not None and contact.name.last_name
                else None
            )
            resolved_name = formatted_name or " ".join(
                part for part in (first_name, last_name) if part
            ).strip() or None
            if resolved_name:
                display_names.append(resolved_name)
            summarized_contacts.append(
                {
                    "formatted_name": formatted_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "birthday": contact.birthday,
                    "organization": (
                        {
                            "company": contact.org.company,
                            "department": contact.org.department,
                            "title": contact.org.title,
                        }
                        if contact.org is not None
                        else None
                    ),
                    "phones": [
                        {
                            "phone": item.phone,
                            "type": item.type,
                            "wa_id": item.wa_id,
                        }
                        for item in contact.phones
                    ],
                    "emails": [
                        {
                            "email": item.email,
                            "type": item.type,
                        }
                        for item in contact.emails
                    ],
                    "urls": [
                        {
                            "url": item.url,
                            "type": item.type,
                        }
                        for item in contact.urls
                    ],
                    "addresses": [
                        {
                            "street": item.street,
                            "city": item.city,
                            "state": item.state,
                            "zip": item.zip,
                            "country": item.country,
                            "country_code": item.country_code,
                            "type": item.type,
                        }
                        for item in contact.addresses
                    ],
                }
            )

        return (
            display_names[0] if len(display_names) == 1 else "[contacts message]",
            {
                "shared_contacts": summarized_contacts,
                "shared_contact_count": len(summarized_contacts),
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _normalize_system_content(
        system: WhatsAppWebhookSystemContent,
    ) -> tuple[str, dict[str, object]]:
        body = system.body.strip() if system.body else None
        identity = system.identity.strip() if system.identity else None
        new_wa_id = system.new_wa_id.strip() if system.new_wa_id else None
        wa_id = system.wa_id.strip() if system.wa_id else None
        system_type = system.type.strip() if system.type else None
        return (
            body or "[system message]",
            {
                "system_type": system_type,
                "system_identity": identity,
                "system_new_wa_id": new_wa_id,
                "system_wa_id": wa_id,
                "has_meaningful_text": False,
            },
        )

    @staticmethod
    def _extract_status_error_code(errors: list[object]) -> str | None:
        if not errors:
            return None
        first_error = errors[0]
        code = getattr(first_error, "code", None)
        if code is not None:
            return str(code)
        if not isinstance(first_error, Mapping):
            return None
        code = first_error.get("code")
        return str(code) if code is not None else None

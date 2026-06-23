from app.providers.messaging.base import MessagingProvider
from app.schemas.messaging import OutboundDispatchRequest


def build_outbound_dispatch_request(
    *,
    provider: MessagingProvider,
    conversation: object,
    account_id: str,
    conversation_id: str,
    recipient_id: str,
    text: str | None,
    message_type: str = "text",
    template_name: str | None = None,
    template_language: str | None = None,
    template_variables: dict[str, str] | None = None,
    template_header_media_type: str | None = None,
    media_asset_id: str | None = None,
    media_url: str | None = None,
    media_caption: str | None = None,
    mime_type: str | None = None,
    file_name: str | None = None,
    interactive_payload: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
) -> OutboundDispatchRequest:
    phone_number = getattr(conversation, "phone_number", None)
    waba_account = getattr(phone_number, "waba_account", None) if phone_number is not None else None
    phone_number_id = getattr(phone_number, "phone_number_id", None)

    if provider.provider_name == "whatsapp" and not phone_number_id:
        raise ValueError(
            "WhatsApp outbound dispatch requires a conversation bound to phone_number_id."
        )

    return OutboundDispatchRequest(
        account_id=account_id,
        conversation_id=conversation_id,
        recipient_id=recipient_id,
        text=text,
        message_type=message_type,
        phone_number_id=phone_number_id,
        access_token=(
            getattr(waba_account, "access_token", None)
            if provider.provider_name == "whatsapp"
            else None
        ),
        waba_id=getattr(waba_account, "waba_id", None),
        template_name=template_name,
        template_language=template_language,
        template_variables=template_variables or {},
        template_header_media_type=template_header_media_type,
        media_asset_id=media_asset_id,
        media_url=media_url,
        media_caption=media_caption,
        mime_type=mime_type,
        file_name=file_name,
        interactive_payload=interactive_payload or {},
        metadata=metadata or {},
    )

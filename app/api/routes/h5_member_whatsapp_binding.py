from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_whatsapp_binding_service,
)
from app.schemas.h5_member_whatsapp_binding import H5MemberWhatsAppBindingResponse
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_whatsapp_binding_service import H5MemberWhatsAppBindingService

router = APIRouter(prefix="/api/h5", tags=["h5-whatsapp-binding"])


@router.get(
    "/whatsapp-binding",
    summary="Get WhatsApp binding",
    description="Get current WhatsApp binding status for the authenticated H5 member.",
    tags=["h5-whatsapp-binding"],
)
async def get_h5_member_whatsapp_binding(
    binding_service: H5MemberWhatsAppBindingService = Depends(get_h5_member_whatsapp_binding_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberWhatsAppBindingResponse:
    return await binding_service.get_binding(context=context)


@router.post(
    "/whatsapp-binding/start",
    summary="Start WhatsApp binding",
    description="Initiate WhatsApp binding process for the authenticated H5 member.",
    tags=["h5-whatsapp-binding"],
)
async def start_h5_member_whatsapp_binding(
    binding_service: H5MemberWhatsAppBindingService = Depends(get_h5_member_whatsapp_binding_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberWhatsAppBindingResponse:
    return await binding_service.start_binding(context=context)

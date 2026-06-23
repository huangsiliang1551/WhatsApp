from datetime import datetime

from app.schemas.h5_member_base import H5MemberCamelModel


class H5MemberWhatsAppBindingResponse(H5MemberCamelModel):
    is_bound: bool
    binding_status: str = "not_started"
    request_id: str | None = None
    phone_number: str | None = None
    requested_at: datetime | None = None
    start_count: int = 0
    last_updated_at: datetime | None = None

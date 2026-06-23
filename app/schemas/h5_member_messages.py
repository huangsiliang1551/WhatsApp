from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.h5_member_base import H5MemberCamelModel


class H5MemberMessageResponse(H5MemberCamelModel):
    id: str
    category: str
    title: str
    body_text: str
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class H5MemberMessageReadAllResponse(H5MemberCamelModel):
    updated: int = Field(ge=0)

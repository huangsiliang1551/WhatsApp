from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: str
    account_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    actor_type: str
    actor_id: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    payload: dict[str, object] | None = None
    created_at: datetime

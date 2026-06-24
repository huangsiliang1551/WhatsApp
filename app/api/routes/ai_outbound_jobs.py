"""AI Outbound Job API 路由（spec 10.5）。

提供创建前政策校验。窗口内允许 service_window；窗口外必须 approved template。
未 opt-in / AI 不可用 / 模板未审核均返回 skipped_policy。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    RequestActor,
    get_transactional_db_session,
    require_permission,
)
from app.services.ai_outbound_job_service import AIOutboundJobService


router = APIRouter(prefix="/api/ai-outbound-jobs", tags=["ai-outbound-jobs"])


class AIOutboundJobCreate(BaseModel):
    account_id: str = Field(min_length=1)
    agency_id: str | None = None
    site_id: str | None = None
    ai_agent_id: str
    user_id: str | None = None
    member_profile_id: str | None = None
    conversation_id: str | None = None
    waba_id: str | None = None
    phone_number_id: str | None = None
    recipient_wa_id: str | None = None
    trigger_type: str
    generated_text: str | None = None
    send_payload_json: dict[str, Any] | None = None
    template_id: str | None = None
    template_name: str | None = None
    template_language: str | None = None
    opt_in: bool = True
    scheduled_at: str | None = None
    source_entry_link_id: str | None = None
    metadata_json: dict[str, Any] | None = None


@router.post("")
async def create_ai_outbound_job(
    payload: AIOutboundJobCreate,
    session: Session = Depends(get_transactional_db_session),
    actor: RequestActor = Depends(require_permission("conversations.ai.view")),
) -> dict[str, Any]:
    actor.require_account_access(payload.account_id)
    svc = AIOutboundJobService(session)
    job = svc.create_job(
        account_id=payload.account_id,
        agency_id=payload.agency_id,
        site_id=payload.site_id,
        ai_agent_id=payload.ai_agent_id,
        user_id=payload.user_id,
        member_profile_id=payload.member_profile_id,
        conversation_id=payload.conversation_id,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        recipient_wa_id=payload.recipient_wa_id,
        trigger_type=payload.trigger_type,
        generated_text=payload.generated_text,
        send_payload_json=payload.send_payload_json,
        template_id=payload.template_id,
        template_name=payload.template_name,
        template_language=payload.template_language,
        opt_in=payload.opt_in,
        scheduled_at=payload.scheduled_at,
        source_entry_link_id=payload.source_entry_link_id,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    return {
        "id": job.id,
        "status": job.status,
        "message_policy": job.message_policy,
        "error_message": job.error_message,
        "template_id": job.template_id,
        "template_name": job.template_name,
        "owner_staff_user_id_snapshot": job.owner_staff_user_id_snapshot,
        "ai_assignment_id_snapshot": job.ai_assignment_id_snapshot,
    }

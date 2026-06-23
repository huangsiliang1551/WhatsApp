"""Batch operations API — IV-BE-002.

Endpoints:
  POST /api/batch/tags               — batch update tags
  POST /api/batch/assign-conversations — batch assign conversations
  POST /api/batch/send-template       — batch send template
  POST /api/batch/import-products     — batch import products (CSV)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.batch_service import BatchService

router = APIRouter(prefix="/api/batch", tags=["batch"])


class BatchTagsRequest(BaseModel):
    entity_type: str  # conversation / customer / ticket
    entity_ids: list[str]
    add_tags: list[str] = []
    remove_tags: list[str] = []


class BatchAssignRequest(BaseModel):
    conversation_ids: list[str]
    agent_id: str


class BatchSendTemplateRequest(BaseModel):
    entity_type: str
    entity_ids: list[str]
    template_id: str
    variables: dict[str, str] = {}


class BatchImportProductsRequest(BaseModel):
    csv_data: str  # CSV content as string
    account_id: str


@router.post("/tags", summary="批量修改标签")
def batch_tags(
    body: BatchTagsRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("batch.tags")),
) -> dict[str, Any]:
    svc = BatchService(session)
    return svc.batch_update_tags(
        entity_type=body.entity_type,
        entity_ids=body.entity_ids,
        add_tags=body.add_tags,
        remove_tags=body.remove_tags,
    )


@router.post("/assign-conversations", summary="批量分配会话")
def batch_assign(
    body: BatchAssignRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("batch.assign")),
) -> dict[str, Any]:
    svc = BatchService(session)
    return svc.batch_assign_conversations(
        conversation_ids=body.conversation_ids,
        agent_id=body.agent_id,
    )


@router.post("/send-template", summary="批量发送模板")
def batch_send_template(
    body: BatchSendTemplateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("batch.send_template")),
) -> dict[str, Any]:
    svc = BatchService(session)
    return svc.batch_send_template(
        entity_type=body.entity_type,
        entity_ids=body.entity_ids,
        template_id=body.template_id,
        variables=body.variables,
    )


@router.post("/import-products", summary="批量导入商品")
def batch_import_products(
    body: BatchImportProductsRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("batch.import")),
) -> dict[str, Any]:
    svc = BatchService(session)
    return svc.batch_import_products(
        csv_data=body.csv_data,
        account_id=body.account_id,
    )

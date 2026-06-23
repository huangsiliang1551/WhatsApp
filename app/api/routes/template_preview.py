"""Template preview API — IV-BE-005.

Endpoints:
  GET  /api/templates/variables         — list system variables
  POST /api/templates/preview           — preview with custom variables
  POST /api/templates/preview-mock      — preview with mock data
"""

from __future__ import annotations

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.services.template_preview_service import TemplatePreviewService

router = APIRouter(prefix="/api/templates", tags=["templates"])


class PreviewRequest(BaseModel):
    content: str
    variables: dict[str, str] = {}


@router.get("/variables", summary="系统变量列表")
def list_variables():
    svc = TemplatePreviewService()
    return {"variables": svc.get_variables()}


@router.post("/preview", summary="模板预览")
def preview(body: PreviewRequest):
    svc = TemplatePreviewService()
    result = svc.preview(body.content, body.variables)
    return {
        "original": body.content,
        "preview": result,
    }


@router.post("/preview-mock", summary="Mock 数据预览")
def preview_mock(content: str = Body(..., embed=True)):
    svc = TemplatePreviewService()
    result = svc.preview_with_mock(content)
    return {
        "original": content,
        "preview": result,
    }

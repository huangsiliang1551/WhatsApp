from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.h5_translation_service import H5TranslationService

router = APIRouter(prefix="/api/h5/sites", tags=["h5-translations"])


class TranslateKeyRequest(BaseModel):
    translation_key: str
    source_text: str


class BatchTranslateRequest(BaseModel):
    translations: dict[str, str]  # key -> source_text


@router.get("/{site_id}/translations/{language_code}")
async def get_translations(
    site_id: str,
    language_code: str,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5TranslationService(session)
    translations = svc.get_translations(site_id, language_code)
    return {
        "site_id": site_id,
        "language_code": language_code,
        "translations": translations,
        "total": len(translations),
    }


@router.post("/{site_id}/translations/{language_code}")
async def translate_key(
    site_id: str,
    language_code: str,
    payload: TranslateKeyRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5TranslationService(session)
    try:
        translated = svc.translate_key(
            site_id=site_id,
            language_code=language_code,
            translation_key=payload.translation_key,
            source_text=payload.source_text,
        )
        return {
            "site_id": site_id,
            "language_code": language_code,
            "translation_key": payload.translation_key,
            "translated_text": translated,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{site_id}/translations/{language_code}/batch")
async def batch_translate(
    site_id: str,
    language_code: str,
    payload: BatchTranslateRequest,
    actor: RequestActor = Depends(require_permission("settings.translation")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5TranslationService(session)
    try:
        result = svc.batch_translate(
            site_id=site_id,
            language_code=language_code,
            translations=payload.translations,
        )
        return {
            "site_id": site_id,
            "language_code": language_code,
            "translations": result,
            "total": len(result),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

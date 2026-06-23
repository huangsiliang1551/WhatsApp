from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.h5_language_service import H5LanguageService

router = APIRouter(prefix="/api/h5/languages", tags=["h5-languages"])


class CreateLanguageRequest(BaseModel):
    language_code: str
    display_name: str
    flag_emoji: str | None = None


COMMON_LANGUAGES: list[dict] = [
    {"code": "zh-CN", "name": "简体中文", "emoji": "🇨🇳"},
    {"code": "zh-TW", "name": "繁体中文", "emoji": "🇹🇼"},
    {"code": "en-US", "name": "English (US)", "emoji": "🇺🇸"},
    {"code": "en-GB", "name": "English (UK)", "emoji": "🇬🇧"},
    {"code": "ja-JP", "name": "日本語", "emoji": "🇯🇵"},
    {"code": "ko-KR", "name": "한국어", "emoji": "🇰🇷"},
    {"code": "es-ES", "name": "Español", "emoji": "🇪🇸"},
    {"code": "es-MX", "name": "Español (MX)", "emoji": "🇲🇽"},
    {"code": "fr-FR", "name": "Français", "emoji": "🇫🇷"},
    {"code": "de-DE", "name": "Deutsch", "emoji": "🇩🇪"},
    {"code": "pt-BR", "name": "Português (BR)", "emoji": "🇧🇷"},
    {"code": "pt-PT", "name": "Português (PT)", "emoji": "🇵🇹"},
    {"code": "it-IT", "name": "Italiano", "emoji": "🇮🇹"},
    {"code": "ru-RU", "name": "Русский", "emoji": "🇷🇺"},
    {"code": "ar-SA", "name": "العربية", "emoji": "🇸🇦"},
    {"code": "hi-IN", "name": "हिन्दी", "emoji": "🇮🇳"},
    {"code": "th-TH", "name": "ไทย", "emoji": "🇹🇭"},
    {"code": "vi-VN", "name": "Tiếng Việt", "emoji": "🇻🇳"},
    {"code": "id-ID", "name": "Bahasa Indonesia", "emoji": "🇮🇩"},
    {"code": "ms-MY", "name": "Bahasa Melayu", "emoji": "🇲🇾"},
    {"code": "tl-PH", "name": "Filipino", "emoji": "🇵🇭"},
    {"code": "tr-TR", "name": "Türkçe", "emoji": "🇹🇷"},
    {"code": "nl-NL", "name": "Nederlands", "emoji": "🇳🇱"},
    {"code": "pl-PL", "name": "Polski", "emoji": "🇵🇱"},
    {"code": "sv-SE", "name": "Svenska", "emoji": "🇸🇪"},
    {"code": "da-DK", "name": "Dansk", "emoji": "🇩🇰"},
    {"code": "fi-FI", "name": "Suomi", "emoji": "🇫🇮"},
    {"code": "nb-NO", "name": "Norsk", "emoji": "🇳🇴"},
    {"code": "cs-CZ", "name": "Čeština", "emoji": "🇨🇿"},
    {"code": "hu-HU", "name": "Magyar", "emoji": "🇭🇺"},
    {"code": "ro-RO", "name": "Română", "emoji": "🇷🇴"},
    {"code": "uk-UA", "name": "Українська", "emoji": "🇺🇦"},
    {"code": "el-GR", "name": "Ελληνικά", "emoji": "🇬🇷"},
    {"code": "he-IL", "name": "עברית", "emoji": "🇮🇱"},
    {"code": "bn-IN", "name": "বাংলা", "emoji": "🇧🇩"},
    {"code": "ta-IN", "name": "தமிழ்", "emoji": "🇮🇳"},
    {"code": "te-IN", "name": "తెలుగు", "emoji": "🇮🇳"},
    {"code": "mr-IN", "name": "मराठी", "emoji": "🇮🇳"},
    {"code": "gu-IN", "name": "ગુજરાતી", "emoji": "🇮🇳"},
    {"code": "kn-IN", "name": "ಕನ್ನಡ", "emoji": "🇮🇳"},
    {"code": "ml-IN", "name": "മലയാളം", "emoji": "🇮🇳"},
    {"code": "pa-IN", "name": "ਪੰਜਾਬੀ", "emoji": "🇮🇳"},
    {"code": "ur-PK", "name": "اردو", "emoji": "🇵🇰"},
    {"code": "ne-NP", "name": "नेपाली", "emoji": "🇳🇵"},
    {"code": "si-LK", "name": "සිංහල", "emoji": "🇱🇰"},
    {"code": "km-KH", "name": "ភាសាខ្មែរ", "emoji": "🇰🇭"},
    {"code": "lo-LA", "name": "ລາວ", "emoji": "🇱🇦"},
    {"code": "my-MM", "name": "မြန်မာဘာသာ", "emoji": "🇲🇲"},
    {"code": "mn-MN", "name": "Монгол", "emoji": "🇲🇳"},
    {"code": "ka-GE", "name": "ქართული", "emoji": "🇬🇪"},
    {"code": "hy-AM", "name": "Հայերեն", "emoji": "🇦🇲"},
    {"code": "az-AZ", "name": "Azərbaycan dili", "emoji": "🇦🇿"},
    {"code": "uz-UZ", "name": "Oʻzbek", "emoji": "🇺🇿"},
    {"code": "kk-KZ", "name": "Қазақ тілі", "emoji": "🇰🇿"},
    {"code": "af-ZA", "name": "Afrikaans", "emoji": "🇿🇦"},
    {"code": "sw-KE", "name": "Kiswahili", "emoji": "🇰🇪"},
]


class UpdateLanguageRequest(BaseModel):
    display_name: str | None = None
    flag_emoji: str | None = None
    is_enabled: bool | None = None


def _lang_to_dict(lang: object) -> dict:
    return {
        "id": getattr(lang, "id"),
        "language_code": getattr(lang, "language_code"),
        "display_name": getattr(lang, "display_name"),
        "flag_emoji": getattr(lang, "flag_emoji"),
        "is_enabled": getattr(lang, "is_enabled"),
        "is_default": getattr(lang, "is_default"),
        "created_at": getattr(lang, "created_at").isoformat() if getattr(lang, "created_at") else None,
    }


@router.get("")
async def list_languages(
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5LanguageService(session)
    items = svc.list_languages()
    return {"items": [_lang_to_dict(l) for l in items], "total": len(items)}


@router.post("", status_code=201)
async def create_language(
    payload: CreateLanguageRequest,
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5LanguageService(session)
    try:
        lang = svc.create_language(
            language_code=payload.language_code,
            display_name=payload.display_name,
            flag_emoji=payload.flag_emoji,
        )
        return _lang_to_dict(lang)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{language_id}")
async def update_language(
    language_id: str,
    payload: UpdateLanguageRequest,
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5LanguageService(session)
    try:
        kwargs = payload.model_dump(exclude_unset=True)
        lang = svc.update_language(language_id, **kwargs)
        return _lang_to_dict(lang)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{language_id}", status_code=204)
async def delete_language(
    language_id: str,
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> None:
    svc = H5LanguageService(session)
    try:
        svc.delete_language(language_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{language_id}/set-default")
async def set_default_language(
    language_id: str,
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = H5LanguageService(session)
    try:
        svc.set_default_language(language_id)
        return {"status": "ok"}
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/batch-init", status_code=201)
async def batch_init_languages(
    actor: RequestActor = Depends(require_permission("settings.languages")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Initialize common languages in bulk (57 languages). Only adds languages that don't exist."""
    from app.db.models import H5Language

    svc = H5LanguageService(session)
    created = 0
    skipped = 0

    for lang_data in COMMON_LANGUAGES:
        existing = session.execute(
            __import__("sqlalchemy").select(H5Language).where(
                H5Language.language_code == lang_data["code"]
            )
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        try:
            svc.create_language(
                language_code=lang_data["code"],
                display_name=lang_data["name"],
                flag_emoji=lang_data["emoji"],
            )
            created += 1
        except Exception:
            skipped += 1

    return {
        "message": f"Languages initialized: {created} created, {skipped} skipped",
        "created": created,
        "skipped": skipped,
        "total": len(COMMON_LANGUAGES),
    }

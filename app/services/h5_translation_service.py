from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Translation


class H5TranslationService:
    def __init__(self, session: Session, ai_provider: object | None = None) -> None:
        self._session = session
        self._ai_provider = ai_provider

    def get_translations(self, site_id: str, language_code: str) -> dict[str, str]:
        """获取站点指定语言的所有翻译（key -> text）"""
        rows = self._session.scalars(
            select(H5Translation).where(
                H5Translation.site_id == site_id,
                H5Translation.language_code == language_code,
            )
        ).all()
        return {t.translation_key: t.translated_text for t in rows}

    def translate_key(
        self,
        site_id: str,
        language_code: str,
        translation_key: str,
        source_text: str,
    ) -> str:
        """翻译单个 key：查表优先，未命中则 AI 兜底并缓存"""
        # 1. 查预翻译表
        existing = self._session.scalar(
            select(H5Translation).where(
                H5Translation.site_id == site_id,
                H5Translation.language_code == language_code,
                H5Translation.translation_key == translation_key,
            )
        )
        if existing:
            return existing.translated_text

        # 2. AI 兜底翻译
        if not self._ai_provider:
            raise ValueError("No AI provider configured for translation.")

        translated = self._ai_translate(source_text, language_code)

        # 3. 缓存到翻译表
        translation = H5Translation(
            id=str(uuid4()),
            site_id=site_id,
            language_code=language_code,
            translation_key=translation_key,
            translated_text=translated,
            is_ai_translated=True,
        )
        self._session.add(translation)
        self._session.commit()

        return translated

    def batch_translate(
        self,
        site_id: str,
        language_code: str,
        translations: dict[str, str],
    ) -> dict[str, str]:
        """批量翻译 key -> source_text"""
        result: dict[str, str] = {}
        for key, source_text in translations.items():
            result[key] = self.translate_key(site_id, language_code, key, source_text)
        return result

    def _ai_translate(self, source_text: str, target_language: str) -> str:
        """调用 AI 进行翻译（兼容 openai/deepseek provider 接口）"""
        prompt = (
            f"Translate the following text to {target_language}. "
            f"Only return the translated text, no explanation.\n\nText: {source_text}"
        )
        if hasattr(self._ai_provider, "generate_reply"):
            import asyncio

            from app.providers.ai.base import AIConversationTurn, AIReplyRequest

            request = AIReplyRequest(
                conversation_id="translation",
                account_id="",
                recipient_id="",
                inbox_message="",
                language_code=target_language,
                conversation_history=[AIConversationTurn(role="user", content=prompt)],
            )
            result = asyncio.run(self._ai_provider.generate_reply(request))
            return result
        if hasattr(self._ai_provider, "generate"):
            return self._ai_provider.generate(prompt)
        raise ValueError(f"AI provider {type(self._ai_provider).__name__} not supported.")

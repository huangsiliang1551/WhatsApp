import asyncio
import re

import structlog

from app.core.metrics import translation_operations_total
from app.core.settings import Settings
from app.providers.translation.base import TranslationProvider
from sqlalchemy.orm import Session

logger = structlog.get_logger()

CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")
JAPANESE_PATTERN = re.compile(r"[\u3040-\u30ff]")
KOREAN_PATTERN = re.compile(r"[\uac00-\ud7a3]")
ARABIC_PATTERN = re.compile(r"[\u0600-\u06ff]")
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04ff]")


class TranslationService:
    def __init__(self, settings: Settings, provider: TranslationProvider, session: Session | None = None) -> None:
        self._settings = settings
        self._provider = provider
        self._session = session

    def _record_translation_usage(self, count: int = 1) -> None:
        if self._session is None:
            return
        try:
            from app.services.ai_usage_service import AiUsageService
            svc = AiUsageService(self._session)
            svc.record_translation_usage(translation_count=count)
            self._session.flush()
        except Exception:
            pass

    def detect_language(self, text: str, language_hint: str | None = None) -> str:
        if language_hint:
            return language_hint
        lowered = text.lower()
        # 日语假名优先于汉字检测，因日语汉字也匹配中文字符集
        if JAPANESE_PATTERN.search(text):
            return "ja"
        if CHINESE_PATTERN.search(text):
            return "zh-CN"
        if KOREAN_PATTERN.search(text):
            return "ko"
        if ARABIC_PATTERN.search(text):
            return "ar"
        if CYRILLIC_PATTERN.search(text):
            return "ru"
        if any(token in lowered for token in ("hola", "gracias", "pedido", "envio", "cliente")):
            return "es"
        if any(token in lowered for token in ("bonjour", "merci", "commande", "livraison")):
            return "fr"
        if any(token in lowered for token in ("olá", "obrigado", "pedido", "entrega")):
            return "pt"
        if any(token in lowered for token in ("hallo", "danke", "bestellung", "lieferung")):
            return "de"
        return "en"

    async def translate_conversation_view(
        self,
        text: str,
        source_language: str,
        *,
        force: bool = False,
    ) -> tuple[str | None, str | None, bool]:
        target_language = self._settings.console_language
        if self._provider.provider_name == "noop":
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction="conversation_view",
                outcome="skipped",
            ).inc()
            return None, None, False
        if (
            not force
            and not self._settings.auto_translate_on_conversation_open
            and not self._settings.auto_translate_on_human_handover
        ) or source_language == target_language:
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction="conversation_view",
                outcome="skipped",
            ).inc()
            return None, None, False

        translated_text = await self._translate_with_fallback(
            text=text,
            source_language=source_language,
            target_language=target_language,
            direction="conversation_view",
        )
        if translated_text == text:
            return None, None, False
        return translated_text, target_language, True

    async def batch_translate_conversation_view(
        self,
        texts: list[str],
        source_languages: list[str],
        *,
        force: bool = False,
    ) -> list[tuple[str | None, str | None, bool]]:
        """批量翻译多条入站消息为控制台语言，合并为单次 AI 请求。

        Args:
            texts: 待翻译文本列表
            source_languages: 每条文本的源语言列表（与 texts 一一对应）
            force: 是否跳过 auto_translate_* 开关检查

        Returns:
            [(translated_text, target_language, was_translated), ...] 与输入顺序一致
        """
        if not texts:
            return []

        target_language = self._settings.console_language

        if self._provider.provider_name == "noop":
            return [(None, None, False)] * len(texts)

        if not force and not self._settings.auto_translate_on_conversation_open:
            return [(None, None, False)] * len(texts)

        # 按源语言分组，同语言一起批量翻译
        groups: dict[str, list[int]] = {}
        for i, src in enumerate(source_languages):
            if src == target_language:
                continue  # 同语言跳过
            groups.setdefault(src, []).append(i)

        if not groups:
            return [(None, None, False)] * len(texts)

        # 结果数组，默认全部跳过
        results: list[tuple[str | None, str | None, bool]] = [
            (None, None, False) for _ in texts
        ]

        # 对每个语言组批量翻译
        for src_lang, indices in groups.items():
            group_texts = [texts[i] for i in indices]
            try:
                translated_list = await self._provider.batch_translate_text(
                    texts=group_texts,
                    source_language=src_lang,
                    target_language=target_language,
                )
                for j, idx in enumerate(indices):
                    t = translated_list[j] if j < len(translated_list) else ""
                    if t and t != texts[idx]:
                        results[idx] = (t, target_language, True)
                        translation_operations_total.labels(
                            provider=self._provider.provider_name,
                            direction="conversation_view",
                            outcome="translated",
                        ).inc()
                    else:
                        translation_operations_total.labels(
                            provider=self._provider.provider_name,
                            direction="conversation_view",
                            outcome="skipped",
                        ).inc()
            except Exception:
                # 批量失败，回退逐条翻译
                async def _one(text: str) -> str:
                    return await self._translate_with_fallback(
                        text=text,
                        source_language=src_lang,
                        target_language=target_language,
                        direction="conversation_view",
                    )
                translated_list = await asyncio.gather(*[_one(texts[i]) for i in indices])
                for j, idx in enumerate(indices):
                    t = translated_list[j] if j < len(translated_list) else ""
                    if t and t != texts[idx]:
                        results[idx] = (t, target_language, True)

        return results

    async def translate_outbound_preview(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> tuple[str, str, bool]:
        """翻译发送预览：不检查 auto_translate_* 开关，总是执行翻译。

        Returns:
            (original_text, translated_text, was_translated)
        """
        if source_language == target_language:
            return text, text, False
        if self._provider.provider_name == "noop":
            return text, text, False

        translated_text = await self._translate_with_fallback(
            text=text,
            source_language=source_language,
            target_language=target_language,
            direction="outbound_operator",
        )
        return text, translated_text, translated_text != text

    async def translate_outbound_for_customer(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> tuple[str, bool]:
        if self._provider.provider_name == "noop":
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction="outbound_operator",
                outcome="skipped",
            ).inc()
            return text, False
        if (
            not self._settings.auto_translate_operator_outbound
            or source_language == target_language
            or target_language in {"", "und", "unknown"}
        ):
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction="outbound_operator",
                outcome="skipped",
            ).inc()
            return text, False

        translated_text = await self._translate_with_fallback(
            text=text,
            source_language=source_language,
            target_language=target_language,
            direction="outbound_operator",
        )
        return translated_text, translated_text != text

    async def _translate_with_fallback(
        self,
        text: str,
        source_language: str,
        target_language: str,
        direction: str,
    ) -> str:
        try:
            translated_text = await self._provider.translate_text(
                text=text,
                source_language=source_language,
                target_language=target_language,
            )
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction=direction,
                outcome="translated",
            ).inc()
            self._record_translation_usage(count=1)
            return translated_text
        except Exception as exc:
            logger.warning(
                "translation_fallback_used",
                provider=self._provider.provider_name,
                source_language=source_language,
                target_language=target_language,
                error=str(exc),
            )
            translation_operations_total.labels(
                provider=self._provider.provider_name,
                direction=direction,
                outcome="fallback",
            ).inc()
            return text

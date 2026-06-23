import asyncio
import json
import re

import structlog
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.providers.translation.base import TranslationProvider

logger = structlog.get_logger()

# 匹配 JSON 数组，容忍 markdown 代码块包裹
_JSON_ARRAY_PATTERN = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


class OpenAICompatibleTranslationProvider(TranslationProvider):
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        base_url: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        if source_language == target_language:
            return text

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a translation engine for a WhatsApp customer support console. "
                            "Translate accurately, preserve intent, names, numbers, emojis, URLs, and formatting. "
                            "Return only the translated text with no explanation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Translate from {source_language} to {target_language}.\n\n"
                            f"Text:\n{text}"
                        ),
                    },
                ],
            )
        except (APITimeoutError, OpenAIError) as exc:
            logger.warning(
                "translation_provider_error",
                provider=self.provider_name,
                source_language=source_language,
                target_language=target_language,
                error=str(exc),
            )
            raise

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise RuntimeError("Translation provider returned an empty response.")
        return content.strip()

    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        """批量翻译多条文本为单次 LLM 请求，AI 返回结构化 JSON 后拆分。

        JSON 解析失败时回退逐条翻译（asyncio.gather）。
        """
        if not texts:
            return []
        if source_language == target_language:
            return list(texts)

        # 构造批量翻译 prompt
        indexed_lines = "\n".join(
            f"[{i}] {text}" for i, text in enumerate(texts)
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a translation engine for a WhatsApp customer support console. "
                            "Translate each message from {source_lang} to {target_lang} accurately. "
                            "Preserve intent, names, numbers, emojis, URLs, and formatting. "
                            "Return ONLY a JSON array where each element is "
                            '{{"i":<index>,"t":"<translated text>"}}. '
                            "No explanation, no markdown, just the JSON array."
                        ).format(source_lang=source_language, target_lang=target_language),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Translate each of the following messages from "
                            f"{source_language} to {target_language}.\n\n{indexed_lines}"
                        ),
                    },
                ],
            )
        except (APITimeoutError, OpenAIError) as exc:
            logger.warning(
                "translation_batch_provider_error",
                provider=self.provider_name,
                source_language=source_language,
                target_language=target_language,
                count=len(texts),
                error=str(exc),
            )
            raise

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise RuntimeError("Translation provider returned an empty response.")

        # 解析 JSON 响应
        try:
            parsed = self._parse_batch_json(content, len(texts))
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "translation_batch_json_parse_failed",
                provider=self.provider_name,
                error=str(exc),
                raw_preview=content[:200],
            )
            # 回退：逐条并��翻译
            return await self._fallback_batch_translate(texts, source_language, target_language)

    def _parse_batch_json(self, content: str, expected_count: int) -> list[str]:
        """从 LLM 响应中提取 JSON 数组并按 index 排序返回译文列表。"""
        content = content.strip()
        # 去除可能的 markdown 代码块包裹
        match = _JSON_ARRAY_PATTERN.search(content)
        json_str = match.group(0) if match else content

        items: list[dict] = json.loads(json_str)
        if not isinstance(items, list):
            raise ValueError("Expected a JSON array")

        # 构建 index → text 映射
        index_map: dict[int, str] = {}
        for item in items:
            idx = item.get("i")
            text = item.get("t", "")
            if isinstance(idx, int) and isinstance(text, str):
                index_map[idx] = text

        # 按原始顺序返回
        result: list[str] = []
        for i in range(expected_count):
            result.append(index_map.get(i, ""))
        return result

    async def _fallback_batch_translate(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        """批量 JSON 解析失败时的逐条翻译回退。"""
        async def _one(text: str) -> str:
            try:
                return await self.translate_text(text, source_language, target_language)
            except Exception:
                return text  # 单条失败返回原文

        return await asyncio.gather(*[_one(t) for t in texts])

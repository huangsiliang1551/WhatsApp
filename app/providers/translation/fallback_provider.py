from app.providers.translation.base import TranslationProvider


class FallbackTranslationProvider(TranslationProvider):
    provider_name = "fallback"

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        if source_language == target_language:
            return text
        return f"[auto-translated {source_language}->{target_language}] {text}"

    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        if not texts:
            return []
        if source_language == target_language:
            return list(texts)
        return [
            f"[auto-translated {source_language}->{target_language}] {t}"
            for t in texts
        ]

from app.providers.translation.base import TranslationProvider


class NoopTranslationProvider(TranslationProvider):
    provider_name = "noop"

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        del source_language, target_language
        return text

    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        del source_language, target_language
        return list(texts)

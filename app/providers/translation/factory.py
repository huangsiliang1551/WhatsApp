"""Factory for creating translation provider instances.

Supports DB-stored configs (Tencent Cloud) with default selection, then
falls back to env-based config, then to AI (LLM) translation, and finally
to NoopTranslationProvider.
"""

from sqlalchemy import select

from app.core.encryption import decrypt_key
from app.core.settings import Settings
from app.db.models import TranslationProviderConfig
from app.providers.ai.base import AIProvider
from app.providers.translation.base import TranslationProvider
from app.providers.translation.llm_provider import OpenAICompatibleTranslationProvider
from app.providers.translation.noop_provider import NoopTranslationProvider
from app.providers.translation.tencent_provider import TencentCloudTranslationProvider


def get_translation_provider(
    settings: Settings,
    ai_provider: AIProvider | None = None,
    session_factory=None,
) -> TranslationProvider:
    """Resolve the translation provider chain.

    Priority:
    1. If live_translation disabled → NoopTranslationProvider
    2. DB configs enabled → build chain from DB-stored TranslationProviderConfig
       - Use default (is_default=true) as primary if found
       - Otherwise use the first enabled config
       - Append AI LLM fallback if available
    3. DB empty → fall back to env-based config (backward compatible)
    4. Final fallback → NoopTranslationProvider
    """
    if not settings.live_translation_enabled:
        return NoopTranslationProvider()

    # Attempt DB-based configs
    db_provider: TranslationProvider | None = None
    if settings.ai_config_db_enabled and session_factory is not None:
        try:
            with session_factory() as session:
                stmt = (
                    select(TranslationProviderConfig)
                    .where(TranslationProviderConfig.is_enabled.is_(True))
                    .order_by(TranslationProviderConfig.priority.asc())
                )
                configs: list[TranslationProviderConfig] = list(session.scalars(stmt).all())

                if configs:
                    # Pick default first, else the highest-priority (first)
                    default = next(
                        (c for c in configs if c.metadata_json and c.metadata_json.get("is_default")),
                        configs[0],
                    )

                    if default.provider_type == "tencent_cloud" and default.secret_id_encrypted and default.secret_key_encrypted:
                        secret_id = decrypt_key(default.secret_id_encrypted)
                        secret_key = decrypt_key(default.secret_key_encrypted)
                        db_provider = TencentCloudTranslationProvider(
                            secret_id=secret_id,
                            secret_key=secret_key,
                            region=default.region or "ap-guangzhou",
                            timeout_seconds=default.timeout_seconds,
                        )
        except Exception:
            import structlog
            logger = structlog.get_logger()
            logger.warning("translation_db_config_fallback", exc_info=True)

    if db_provider is not None:
        # Chain: DB provider → AI LLM fallback
        llm_provider = _build_llm_fallback_provider(settings)
        if llm_provider is not None:
            return _FallbackToAITranslationProvider(db_provider, llm_provider)
        return db_provider

    # Fallback to env-based config
    env_provider = _get_env_translation_provider(settings)
    if env_provider is not None:
        return env_provider

    return NoopTranslationProvider()


def _build_llm_fallback_provider(settings: Settings) -> OpenAICompatibleTranslationProvider | None:
    """Build an LLM-based translation provider from env settings as fallback."""
    provider_name = settings.resolve_translation_provider_name()

    if provider_name == "deepseek" and settings.deepseek_api_key:
        return OpenAICompatibleTranslationProvider(
            provider_name="deepseek",
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_api_base,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )

    if provider_name == "openai" and settings.openai_api_key:
        return OpenAICompatibleTranslationProvider(
            provider_name="openai",
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=None,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )

    return None


def _get_env_translation_provider(settings: Settings) -> TranslationProvider | None:
    """Original env-based translation provider resolution."""
    provider_name = settings.resolve_translation_provider_name()

    if provider_name in ("fallback", "mock"):
        from app.providers.translation.fallback_provider import FallbackTranslationProvider

        return FallbackTranslationProvider()

    if provider_name == "deepseek" and settings.deepseek_api_key:
        return OpenAICompatibleTranslationProvider(
            provider_name="deepseek",
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_api_base,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )

    if provider_name == "openai" and settings.openai_api_key:
        return OpenAICompatibleTranslationProvider(
            provider_name="openai",
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=None,
            timeout_seconds=settings.llm_request_timeout_seconds,
        )

    return None


class _FallbackToAITranslationProvider(TranslationProvider):
    """Wraps a primary translation provider with AI LLM fallback.

    If the primary provider fails (timeout, auth error, etc.),
    the AI provider handles the translation request.
    """

    provider_name = "translation_fallback_chain"

    def __init__(
        self,
        primary: TranslationProvider,
        fallback: TranslationProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        try:
            return await self._primary.translate_text(text, source_language, target_language)
        except Exception:
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "translation_primary_failed_falling_back_to_ai",
                primary=self._primary.provider_name,
                fallback=self._fallback.provider_name,
                source_language=source_language,
                target_language=target_language,
                exc_info=True,
            )
            return await self._fallback.translate_text(text, source_language, target_language)

    async def batch_translate_text(
        self,
        texts: list[str],
        source_language: str,
        target_language: str,
    ) -> list[str]:
        try:
            return await self._primary.batch_translate_text(texts, source_language, target_language)
        except Exception:
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "translation_primary_batch_failed_falling_back_to_ai",
                primary=self._primary.provider_name,
                fallback=self._fallback.provider_name,
                source_language=source_language,
                target_language=target_language,
                exc_info=True,
            )
            return await self._fallback.batch_translate_text(texts, source_language, target_language)

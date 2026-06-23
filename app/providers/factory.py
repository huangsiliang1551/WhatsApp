"""Factory functions for creating provider instances.

Centralizes provider instantiation, including the dynamic AI provider chain that
selects from DB-stored configs when available (with account-level override support)
or falls back to .env-based configuration for backward compatibility.
"""

from sqlalchemy import select

from app.core.settings import Settings
from app.db.models import AIProviderConfig
from app.providers.ai.base import AIProvider
from app.providers.ai.deepseek_provider import DeepSeekProvider
from app.providers.ai.fallback_provider import FallbackAIProvider
from app.providers.ai.generic_provider import GenericOpenAICompatibleProvider
from app.providers.ai.mock_provider import MockAIProvider
from app.providers.ai.openai_provider import OpenAIProvider
from app.providers.ecommerce.base import EcommerceProvider
from app.providers.ecommerce.mock_provider import MockEcommerceProvider
from app.providers.messaging.base import MessagingProvider
from app.providers.messaging.mock_provider import MockMessagingProvider
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.providers.meta_management.base import MetaManagementProvider
from app.providers.meta_management.mock_provider import MockMetaManagementProvider
from app.providers.meta_management.whatsapp_provider import WhatsAppMetaManagementProvider
from app.providers.template_registry.base import TemplateRegistryProvider
from app.providers.template_registry.mock_provider import MockTemplateRegistryProvider
from app.providers.template_registry.whatsapp_provider import WhatsAppTemplateRegistryProvider
from app.core.encryption import decrypt_key
from app.db.session import get_sessionmaker
from app.services.ai_provider_cache import get_provider_cache


def get_ai_provider(
    settings: Settings,
    account_id: str | None = None,
) -> AIProvider:
    """Resolve the AI provider chain for the given account.

    Priority:
    1. test_mode → MockAIProvider
    2. DB configs enabled → build chain from AIProviderConfig + account override
    3. DB empty → fall back to .env-based config (backward compatible)
    4. Final fallback → MockAIProvider
    """
    provider_name = settings.ai_provider.lower()

    if settings.test_mode or provider_name == "mock":
        return MockAIProvider(model="mock-ai")

    # Attempt DB-based configs
    if settings.ai_config_db_enabled:
        try:
            session_factory = get_sessionmaker()
            with session_factory() as session:
                cache = get_provider_cache()
                chain_configs = cache.get_active_chain(session)

                if chain_configs:
                    # Check account-level override
                    override_config: AIProviderConfig | None = None
                    if account_id:
                        override_config = cache.get_account_override(session, account_id)

                    providers: list[AIProvider] = []

                    if override_config:
                        providers.append(_build_from_config(override_config))
                        remaining = [c for c in chain_configs if c.id != override_config.id]
                        providers.extend(_build_from_config(c) for c in remaining)
                    else:
                        providers.extend(_build_from_config(c) for c in chain_configs)

                    # Always append MockAIProvider as final fallback
                    providers.append(MockAIProvider(model="mock-ai"))

                    if len(providers) == 1:
                        return providers[0]
                    return FallbackAIProvider(providers=providers)
        except Exception:
            # If DB is unreachable or configs fail to load, fall through to .env path
            import structlog
            logger = structlog.get_logger()
            logger.warning("ai_provider_db_config_fallback", exc_info=True)

    # Fallback to .env-based config (original behavior, backward compatible)
    return _get_env_ai_provider(settings)


def _build_from_config(config: AIProviderConfig) -> AIProvider:
    """Build an AIProvider instance from a stored AIProviderConfig row."""
    api_key = ""
    if config.api_key_encrypted:
        try:
            api_key = decrypt_key(config.api_key_encrypted)
        except Exception:
            api_key = ""

    return GenericOpenAICompatibleProvider(
        display_name=config.name,
        model=config.model,
        api_key=api_key,
        base_url=config.api_base_url,
        timeout_seconds=config.timeout_seconds,
        use_responses_api=config.use_responses_api,
    )


def _get_env_ai_provider(settings: Settings) -> AIProvider:
    """Original .env-based provider resolution (backward compatible)."""
    provider_name = settings.ai_provider.lower()

    # Build fallback chain: [primary, secondary, final_fallback]
    providers: list[AIProvider] = []

    if provider_name == "deepseek":
        if settings.deepseek_api_key:
            providers.append(
                DeepSeekProvider(
                    model=settings.deepseek_model,
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_api_base,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                )
            )
        # Try OpenAI as secondary fallback if key is available
        if settings.openai_api_key:
            providers.append(
                OpenAIProvider(
                    model=settings.openai_model,
                    api_key=settings.openai_api_key,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                )
            )
    else:
        # Primary: OpenAI
        if settings.openai_api_key:
            providers.append(
                OpenAIProvider(
                    model=settings.openai_model,
                    api_key=settings.openai_api_key,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                )
            )
        # Secondary: DeepSeek as fallback if key is available
        if settings.deepseek_api_key and provider_name != "deepseek":
            providers.append(
                DeepSeekProvider(
                    model=settings.deepseek_model,
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_api_base,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                )
            )

    # Final fallback: always add MockAIProvider
    providers.append(MockAIProvider(model="mock-ai"))

    if len(providers) == 1:
        # Only MockAIProvider — no real providers configured
        return providers[0]

    return FallbackAIProvider(providers=providers)


def get_ecommerce_provider(settings: Settings) -> EcommerceProvider:
    provider_name = settings.ecommerce_provider.lower()

    if provider_name == "mock":
        return MockEcommerceProvider()

    raise ValueError(f"Unsupported ecommerce provider '{settings.ecommerce_provider}'.")


def get_messaging_provider(settings: Settings) -> MessagingProvider:
    provider_name = settings.messaging_provider.lower()

    if provider_name == "mock":
        return MockMessagingProvider()
    if provider_name == "whatsapp":
        return WhatsAppProvider(
            api_base=settings.meta_graph_api_base,
            api_version=settings.meta_graph_api_version,
            timeout_seconds=settings.messaging_request_timeout_seconds,
        )

    raise ValueError(f"Unsupported messaging provider '{settings.messaging_provider}'.")


def get_meta_management_provider(settings: Settings) -> MetaManagementProvider:
    provider_name = (
        settings.meta_management_provider.lower()
        if settings.meta_management_provider
        else settings.messaging_provider.lower()
    )

    if provider_name == "mock":
        return MockMetaManagementProvider()
    if provider_name == "whatsapp":
        return WhatsAppMetaManagementProvider(
            api_base=settings.meta_graph_api_base,
            api_version=settings.meta_graph_api_version,
            app_id=settings.meta_app_id,
            app_secret=settings.meta_app_secret,
            subscribed_fields=settings.meta_webhook_subscribed_fields,
            timeout_seconds=settings.messaging_request_timeout_seconds,
        )

    raise ValueError(f"Unsupported meta management provider '{provider_name}'.")


def get_template_registry_provider(settings: Settings) -> TemplateRegistryProvider:
    provider_name = (
        settings.template_registry_provider.lower()
        if settings.template_registry_provider
        else settings.messaging_provider.lower()
    )

    if provider_name == "mock":
        return MockTemplateRegistryProvider()
    if provider_name == "whatsapp":
        return WhatsAppTemplateRegistryProvider(
            api_base=settings.meta_graph_api_base,
            api_version=settings.meta_graph_api_version,
            timeout_seconds=settings.messaging_request_timeout_seconds,
        )

    raise ValueError(f"Unsupported template registry provider '{provider_name}'.")

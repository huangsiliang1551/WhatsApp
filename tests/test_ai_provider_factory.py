"""AIP-004: Unit tests for the refactored get_ai_provider factory function.

Tests verify:
- .env fallback when DB is empty (backward compatible)
- test_mode returns MockAIProvider
- _build_from_config creates GenericOpenAICompatibleProvider
- _get_env_ai_provider builds correct providers from env settings

NOTE: DB-based path tests are covered by config_service and API integration tests,
since the factory's get_sessionmaker() connects to real Postgres (not test SQLite).
"""

import pytest

from app.core.settings import Settings
from app.db.models import AIProviderConfig
from app.providers.factory import get_ai_provider, _build_from_config
from app.providers.ai.mock_provider import MockAIProvider
from app.providers.ai.fallback_provider import FallbackAIProvider
from app.providers.ai.generic_provider import GenericOpenAICompatibleProvider
from app.core.encryption import encrypt_key


def _make_config(
    name: str = "test",
    priority: int = 0,
    is_enabled: bool = True,
    api_key_encrypted: str | None = None,
    model: str = "gpt-4",
    provider_type: str = "openai",
    api_base_url: str | None = None,
    timeout_seconds: int = 30,
    use_responses_api: bool = False,
) -> AIProviderConfig:
    """Create an in-memory AIProviderConfig (not saved to DB) for unit tests."""
    config = AIProviderConfig(
        name=name,
        provider_type=provider_type,
        api_base_url=api_base_url,
        api_key_encrypted=api_key_encrypted,
        model=model,
        priority=priority,
        is_enabled=is_enabled,
        timeout_seconds=timeout_seconds,
        use_responses_api=use_responses_api,
    )
    return config


def test_factory_falls_back_to_env_when_db_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DB config is disabled, factory falls back to .env (original behavior)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    monkeypatch.setenv("AI_CONFIG_DB_ENABLED", "false")

    settings = Settings(test_mode=False, ai_provider="openai")
    provider = get_ai_provider(settings, account_id=None)
    assert not isinstance(provider, MockAIProvider)


def test_factory_falls_back_to_env_deepseek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DeepSeek via .env should work when DB config disabled."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-env")
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.setenv("AI_CONFIG_DB_ENABLED", "false")

    settings = Settings(test_mode=False, ai_provider="deepseek")
    provider = get_ai_provider(settings)
    assert not isinstance(provider, MockAIProvider)


def test_factory_returns_mock_when_no_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With DB disabled and no API keys, factory should return MockAIProvider."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("AI_CONFIG_DB_ENABLED", "false")

    settings = Settings(test_mode=False, ai_provider="openai")
    provider = get_ai_provider(settings)
    assert isinstance(provider, MockAIProvider)


def test_factory_test_mode_returns_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """test_mode=True should always return MockAIProvider directly."""
    monkeypatch.setenv("AI_CONFIG_DB_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    settings = Settings(test_mode=True, ai_provider="openai")
    provider = get_ai_provider(settings)
    assert isinstance(provider, MockAIProvider)
    assert provider.provider_name == "mock"


def test_build_from_config_creates_generic_provider() -> None:
    """_build_from_config should create a GenericOpenAICompatibleProvider."""
    encrypted_key = encrypt_key("sk-real-key")
    config = _make_config(
        name="my-provider",
        api_key_encrypted=encrypted_key,
        model="gpt-5",
        api_base_url="https://custom.api.com/v1",
        timeout_seconds=45,
        use_responses_api=True,
    )
    provider = _build_from_config(config)
    assert isinstance(provider, GenericOpenAICompatibleProvider)
    assert provider.model == "gpt-5"


def test_build_from_config_handles_missing_key() -> None:
    """_build_from_config should handle missing encrypted key gracefully."""
    config = _make_config(
        name="no-key-provider",
        api_key_encrypted=None,
        model="llama-3",
    )
    provider = _build_from_config(config)
    assert isinstance(provider, GenericOpenAICompatibleProvider)
    assert provider.model == "llama-3"

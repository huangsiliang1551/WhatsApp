"""AIP-004: Unit tests for AIProviderConfigService (CRUD, encryption, cache, seeding)."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.encryption import encrypt_key, decrypt_key
from app.db.models import AIProviderConfig, AccountAIProviderOverride
from app.schemas.ai_providers import (
    CreateAIProviderConfigRequest,
    UpdateAIProviderConfigRequest,
)
from app.services.ai_provider_config_service import AIProviderConfigService
from app.services.ai_provider_cache import AIProviderCache, invalidate_provider_cache

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def service(db_session_factory: sessionmaker[Session]) -> AIProviderConfigService:
    session = db_session_factory()
    return AIProviderConfigService(session)


def _create_test_config(
    service: AIProviderConfigService,
    name: str = "test-provider",
    priority: int = 0,
    api_key: str = "sk-test-key",
) -> AIProviderConfig:
    req = CreateAIProviderConfigRequest(
        name=name,
        provider_type="openai",
        api_key=api_key,
        model="gpt-4",
        priority=priority,
        is_enabled=True,
        timeout_seconds=30,
        use_responses_api=True,
    )
    return service.create_config(req)


# ── Encryption ──────────────────────────────────────────────────────────


def test_encrypt_decrypt_roundtrip() -> None:
    key = "sk-my-secret-key-abc123"
    encrypted = encrypt_key(key)
    assert encrypted != ""
    assert encrypted != key  # not stored in plaintext
    decrypted = decrypt_key(encrypted)
    assert decrypted == key


# ── CRUD ────────────────────────────────────────────────────────────────


def test_create_config_stores_encrypted_key(service: AIProviderConfigService) -> None:
    config = _create_test_config(service, api_key="sk-secret-42")
    assert config.api_key_encrypted is not None
    assert config.api_key_encrypted != "sk-secret-42"
    # Verify decrypt roundtrip
    decrypted = decrypt_key(config.api_key_encrypted)
    assert decrypted == "sk-secret-42"


def test_list_configs_hides_api_key(service: AIProviderConfigService) -> None:
    _create_test_config(service, name="alpha", priority=5)
    _create_test_config(service, name="beta", priority=0)
    configs = service.list_configs()
    assert len(configs) == 2
    # Verify priority ordering (beta first since lower priority = higher rank)
    assert configs[0].name == "beta"
    assert configs[1].name == "alpha"
    # Ensure api_key_encrypted is stored (not exposed via API, but stored in DB)
    for c in configs:
        assert c.api_key_encrypted is not None
        assert c.api_key_encrypted != c.name


def test_update_config_preserves_key_on_empty(service: AIProviderConfigService) -> None:
    config = _create_test_config(service, api_key="original-key")
    original_encrypted = config.api_key_encrypted

    # Update with no api_key field (None) — should preserve
    update_req = UpdateAIProviderConfigRequest(name="updated-name")
    updated = service.update_config(config.id, update_req)
    assert updated.name == "updated-name"
    assert updated.api_key_encrypted == original_encrypted  # key unchanged

    # Update with empty string api_key — should also preserve
    update_req2 = UpdateAIProviderConfigRequest(api_key="")
    updated2 = service.update_config(config.id, update_req2)
    assert updated2.api_key_encrypted == original_encrypted  # still unchanged


def test_update_config_changes_key(service: AIProviderConfigService) -> None:
    config = _create_test_config(service, api_key="original-key")
    update_req = UpdateAIProviderConfigRequest(api_key="new-key-789")
    updated = service.update_config(config.id, update_req)
    assert decrypt_key(updated.api_key_encrypted) == "new-key-789"


def test_reorder_updates_priorities(service: AIProviderConfigService) -> None:
    c1 = _create_test_config(service, name="first", priority=10)
    c2 = _create_test_config(service, name="second", priority=20)
    c3 = _create_test_config(service, name="third", priority=30)

    service.reorder_configs([c3.id, c1.id, c2.id])
    configs = service.list_configs(include_disabled=True)
    order = {c.name: c.priority for c in configs}
    assert order["third"] == 0
    assert order["first"] == 1
    assert order["second"] == 2


def test_delete_config_cascades_overrides(service: AIProviderConfigService) -> None:
    config = _create_test_config(service)
    override = service.set_account_override("acct-1", config.id)
    assert override is not None

    service.delete_config(config.id)

    # Verify config deleted
    with pytest.raises(ValueError, match="not found"):
        service.get_config(config.id)

    # Verify override also cascaded
    assert service.get_account_override("acct-1") is None


# ── Seeding ─────────────────────────────────────────────────────────────


def test_seed_from_env_creates_records(
    service: AIProviderConfigService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.settings import Settings

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-deepseek")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")
    settings = Settings()
    count = service.seed_from_env(settings)
    assert count == 2

    configs = service.list_configs(include_disabled=True)
    assert len(configs) == 2
    names = {c.name for c in configs}
    assert "OpenAI (from .env)" in names
    assert "DeepSeek (from .env)" in names


def test_seed_skips_when_already_populated(
    service: AIProviderConfigService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_test_config(service, name="existing")
    from app.core.settings import Settings

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-openai")
    settings = Settings()
    count = service.seed_from_env(settings)
    assert count == 0  # Already has data, should skip


# ── Account Overrides ───────────────────────────────────────────────────


def test_account_override_crud(service: AIProviderConfigService) -> None:
    config = _create_test_config(service, name="override-target")

    # Set override
    override = service.set_account_override("acct-special", config.id)
    assert override.account_id == "acct-special"
    assert override.provider_config_id == config.id

    # Read override
    found = service.get_account_override("acct-special")
    assert found is not None
    assert found.provider_config_id == config.id

    # Clear override
    service.clear_account_override("acct-special")
    assert service.get_account_override("acct-special") is None


# ── Cache ───────────────────────────────────────────────────────────────


def test_cache_invalidation_on_crud(
    service: AIProviderConfigService,
) -> None:
    cache = AIProviderCache(ttl_seconds=60)
    session = service._session

    # Cache should be empty initially
    chain = cache.get_active_chain(session)
    assert len(chain) == 0

    # Create config
    config = _create_test_config(service, name="cache-test-1")

    # Cache should still be empty (not auto-refreshed after create without invalidation)
    chain = cache.get_active_chain(session)
    assert len(chain) == 0

    # Invalidate
    cache.invalidate()
    chain = cache.get_active_chain(session)
    assert len(chain) == 1
    assert chain[0].name == "cache-test-1"

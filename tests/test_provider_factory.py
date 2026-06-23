from app.core.settings import Settings
from app.providers.factory import (
    get_messaging_provider,
    get_meta_management_provider,
    get_template_registry_provider,
)
from app.providers.queue.factory import get_queue_provider


def test_messaging_provider_uses_mock_by_default() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=True,
        MESSAGING_PROVIDER="mock",
    )

    provider = get_messaging_provider(settings)

    assert provider.provider_name == "mock"


def test_meta_management_provider_falls_back_to_messaging_provider() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=True,
        MESSAGING_PROVIDER="mock",
        META_MANAGEMENT_PROVIDER="",
    )

    provider = get_meta_management_provider(settings)

    assert provider.provider_name == "mock"


def test_whatsapp_providers_use_configured_graph_base_and_version() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=False,
        MESSAGING_PROVIDER="whatsapp",
        META_MANAGEMENT_PROVIDER="whatsapp",
        TEMPLATE_REGISTRY_PROVIDER="whatsapp",
        META_APP_ID="app-factory-1",
        META_APP_SECRET="secret-factory-1",
        META_GRAPH_API_BASE="https://graph.example.com",
        META_GRAPH_API_VERSION="v99.0",
    )

    messaging_provider = get_messaging_provider(settings)
    meta_management_provider = get_meta_management_provider(settings)
    template_registry_provider = get_template_registry_provider(settings)

    assert messaging_provider.provider_name == "whatsapp"
    assert meta_management_provider.provider_name == "whatsapp"
    assert template_registry_provider.provider_name == "whatsapp"
    assert messaging_provider._api_base == "https://graph.example.com"
    assert messaging_provider._api_version == "v99.0"
    assert meta_management_provider._api_base == "https://graph.example.com"
    assert meta_management_provider._api_version == "v99.0"
    assert meta_management_provider._app_id == "app-factory-1"
    assert meta_management_provider._app_secret == "secret-factory-1"
    assert template_registry_provider._api_base == "https://graph.example.com"
    assert template_registry_provider._api_version == "v99.0"


def test_meta_management_provider_injects_meta_app_credentials_for_embedded_signup() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=False,
        MESSAGING_PROVIDER="mock",
        META_MANAGEMENT_PROVIDER="whatsapp",
        META_GRAPH_API_BASE="https://graph.example.com",
        META_GRAPH_API_VERSION="v99.0",
        META_APP_ID="meta-app-id-1",
        META_APP_SECRET="meta-app-secret-1",
    )

    provider = get_meta_management_provider(settings)

    assert provider.provider_name == "whatsapp"
    assert provider._api_base == "https://graph.example.com"
    assert provider._api_version == "v99.0"
    assert provider._app_id == "meta-app-id-1"
    assert provider._app_secret == "meta-app-secret-1"


def test_queue_provider_uses_memory_in_test_mode() -> None:
    settings = Settings(
        _env_file=None,
        TEST_MODE=True,
        QUEUE_PROVIDER="redis",
    )

    provider = get_queue_provider(settings)

    assert provider.provider_name == "memory"

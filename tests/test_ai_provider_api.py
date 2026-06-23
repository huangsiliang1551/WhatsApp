"""AIP-004: Integration tests for AI Provider Config API endpoints.

Tests the 11 CRUD + action endpoints under /api/ai-providers.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings
from app.db.models import AIProviderConfig
from app.schemas.ai_providers import CreateAIProviderConfigRequest
from app.services.ai_provider_config_service import AIProviderConfigService
from app.core.encryption import encrypt_key

_ADMIN_HEADERS = {
    "X-Actor-Id": "aip-test-admin",
    "X-Actor-Role": "super_admin",
}
_READONLY_HEADERS = {
    "X-Actor-Id": "aip-test-reader",
    "X-Actor-Role": "readonly",
}


def _seed_config(
    db_session_factory: sessionmaker[Session],
    name: str = "api-test-provider",
    priority: int = 0,
) -> str:
    session = db_session_factory()
    service = AIProviderConfigService(session)
    config = service.create_config(
        CreateAIProviderConfigRequest(
            name=name,
            provider_type="openai",
            api_key="sk-test-api-key",
            model="gpt-4",
            priority=priority,
            is_enabled=True,
            timeout_seconds=30,
            use_responses_api=True,
        )
    )
    config_id = config.id
    session.close()
    return config_id


class TestAIProviderAPI:
    """Test suite for AI provider config API endpoints."""

    def test_api_create_provider(self, client: TestClient) -> None:
        """POST /api/ai-providers should create and return a config with has_api_key."""
        payload = {
            "name": "created-by-api",
            "provider_type": "openai",
            "api_key": "sk-api-created",
            "model": "gpt-5",
            "priority": 0,
        }
        resp = client.post("/api/ai-providers", json=payload, headers=_ADMIN_HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "created-by-api"
        assert data["has_api_key"] is True
        assert "api_key" not in data  # never exposed as top-level key
        assert data["model"] == "gpt-5"

    def test_api_list_providers_masks_keys(self, client: TestClient) -> None:
        """GET /api/ai-providers should return has_api_key: true, never the raw key."""
        # Create a config first
        payload = {
            "name": "list-test-provider",
            "provider_type": "deepseek",
            "api_key": "sk-list-secret",
            "model": "deepseek-chat",
            "priority": 0,
        }
        client.post("/api/ai-providers", json=payload, headers=_ADMIN_HEADERS)

        resp = client.get("/api/ai-providers", headers=_ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for provider in data:
            assert "has_api_key" in provider
            assert "api_key" not in provider  # check dict keys, not substring
            assert "api_key_encrypted" not in provider

    def test_api_update_provider(self, client: TestClient) -> None:
        """PATCH /api/ai-providers/{id} should update specified fields."""
        # Create
        create_resp = client.post(
            "/api/ai-providers",
            json={
                "name": "before-update",
                "provider_type": "openai",
                "api_key": "sk-before",
                "model": "gpt-4",
                "priority": 0,
            },
            headers=_ADMIN_HEADERS,
        )
        config_id = create_resp.json()["id"]

        # Update
        update_resp = client.patch(
            f"/api/ai-providers/{config_id}",
            json={"name": "after-update", "model": "gpt-5"},
            headers=_ADMIN_HEADERS,
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "after-update"
        assert data["model"] == "gpt-5"
        assert data["has_api_key"] is True

    def test_api_delete_provider(self, client: TestClient) -> None:
        """DELETE /api/ai-providers/{id} should return 204 and remove config."""
        create_resp = client.post(
            "/api/ai-providers",
            json={
                "name": "to-be-deleted",
                "provider_type": "openai",
                "api_key": "sk-delete",
                "model": "gpt-4",
                "priority": 0,
            },
            headers=_ADMIN_HEADERS,
        )
        config_id = create_resp.json()["id"]

        delete_resp = client.delete(
            f"/api/ai-providers/{config_id}", headers=_ADMIN_HEADERS
        )
        assert delete_resp.status_code == 204

        # Verify gone
        get_resp = client.get(f"/api/ai-providers/{config_id}", headers=_ADMIN_HEADERS)
        assert get_resp.status_code == 404

    def test_api_reorder_providers(self, client: TestClient) -> None:
        """PUT /api/ai-providers/reorder should update priorities."""
        a = client.post(
            "/api/ai-providers",
            json={
                "name": "reorder-a",
                "provider_type": "openai",
                "api_key": "sk-a",
                "model": "gpt-4",
                "priority": 10,
            },
            headers=_ADMIN_HEADERS,
        ).json()
        b = client.post(
            "/api/ai-providers",
            json={
                "name": "reorder-b",
                "provider_type": "openai",
                "api_key": "sk-b",
                "model": "gpt-4",
                "priority": 20,
            },
            headers=_ADMIN_HEADERS,
        ).json()

        # Reorder: swap priority
        reorder_resp = client.put(
            "/api/ai-providers/reorder",
            json={"ordered_ids": [b["id"], a["id"]]},
            headers=_ADMIN_HEADERS,
        )
        assert reorder_resp.status_code == 200
        assert reorder_resp.json()["status"] == "ok"

        # Verify order changed
        list_resp = client.get("/api/ai-providers", headers=_ADMIN_HEADERS)
        configs = list_resp.json()
        # b should come before a now
        b_index = next(i for i, c in enumerate(configs) if c["id"] == b["id"])
        a_index = next(i for i, c in enumerate(configs) if c["id"] == a["id"])
        assert b_index < a_index

    def test_api_test_connection(self, client: TestClient) -> None:
        """POST /api/ai-providers/{id}/test should return connection result structure."""
        # Create a config via API
        create_resp = client.post(
            "/api/ai-providers",
            json={
                "name": "test-connection-provider",
                "provider_type": "openai",
                "api_key": "sk-test-conn",
                "model": "gpt-4",
                "priority": 0,
            },
            headers=_ADMIN_HEADERS,
        )
        assert create_resp.status_code == 201
        config_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/ai-providers/{config_id}/test",
            json={},
            headers=_ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "error")

    def test_api_requires_settings_manage_permission(self, client: TestClient) -> None:
        """Endpoints should reject insufficient permissions."""
        # readonly user should not be able to create
        resp = client.post(
            "/api/ai-providers",
            json={
                "name": "perm-test",
                "provider_type": "openai",
                "api_key": "sk-perm",
                "model": "gpt-4",
                "priority": 0,
            },
            headers=_READONLY_HEADERS,
        )
        assert resp.status_code == 403

    def test_api_account_override_lifecycle(self, client: TestClient) -> None:
        """Full lifecycle: create config → set override → read → clear."""
        # Create a config
        create_resp = client.post(
            "/api/ai-providers",
            json={
                "name": "override-provider",
                "provider_type": "openai",
                "api_key": "sk-override",
                "model": "gpt-4",
                "priority": 0,
            },
            headers=_ADMIN_HEADERS,
        )
        config_id = create_resp.json()["id"]

        # Set override for account
        override_resp = client.put(
            f"/api/ai-providers/account-overrides/test-account-1",
            json={"provider_config_id": config_id},
            headers=_ADMIN_HEADERS,
        )
        assert override_resp.status_code == 200
        override_data = override_resp.json()
        assert override_data["account_id"] == "test-account-1"
        assert override_data["provider_config_id"] == config_id

        # List overrides
        list_resp = client.get(
            "/api/ai-providers/account-overrides", headers=_ADMIN_HEADERS
        )
        assert list_resp.status_code == 200
        overrides = list_resp.json()
        assert any(o["account_id"] == "test-account-1" for o in overrides)

        # Clear override
        clear_resp = client.delete(
            f"/api/ai-providers/account-overrides/test-account-1",
            headers=_ADMIN_HEADERS,
        )
        assert clear_resp.status_code == 204

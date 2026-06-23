"""Tests for HOTFIX-008: DELETE /api/platform/users/{user_id}"""

from fastapi.testclient import TestClient


def _actor_headers(
    actor_id: str,
    role: str,
    *,
    account_ids: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }
    if account_ids is not None:
        headers["X-Actor-Account-Ids"] = account_ids
    return headers


def _create_user(
    client: TestClient,
    headers: dict[str, str],
    *,
    account_id: str | None = None,
    public_user_id: str,
    display_name: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_user_id": public_user_id,
        "display_name": display_name,
        "language_code": "zh-CN",
    }
    if account_id is not None:
        payload["account_id"] = account_id
    response = client.post("/api/platform/users", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestDeletePlatformUser:
    """Tests for DELETE /api/platform/users/{user_id}."""

    def test_delete_existing_user_returns_204(self, client: TestClient) -> None:
        """Deleting an existing user returns 204 No Content."""
        super_admin_headers = _actor_headers("admin-1", "super_admin")
        user = _create_user(
            client,
            super_admin_headers,
            account_id="test-account-008",
            public_user_id="delete-test-user-1",
            display_name="Delete Test User 1",
        )
        user_id = user["id"]
        resp = client.delete(f"/api/platform/users/{user_id}", headers=super_admin_headers)
        assert resp.status_code == 204

    def test_delete_user_removes_user(self, client: TestClient) -> None:
        """User is no longer listed after deletion."""
        super_admin_headers = _actor_headers("admin-1", "super_admin")
        user = _create_user(
            client,
            super_admin_headers,
            account_id="test-account-008",
            public_user_id="delete-test-user-2",
            display_name="Delete Test User 2",
        )
        user_id = user["id"]
        # Delete the user
        resp = client.delete(f"/api/platform/users/{user_id}", headers=super_admin_headers)
        assert resp.status_code == 204
        # Verify user is gone from list
        list_resp = client.get("/api/platform/users", headers=super_admin_headers)
        assert list_resp.status_code == 200
        user_ids = [u["id"] for u in list_resp.json()]
        assert user_id not in user_ids

    def test_delete_nonexistent_user_returns_404(self, client: TestClient) -> None:
        """Deleting a non-existent user returns 404."""
        super_admin_headers = _actor_headers("admin-1", "super_admin")
        resp = client.delete("/api/platform/users/nonexistent-id", headers=super_admin_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_delete_user_requires_manage_permission(self, client: TestClient) -> None:
        """Deleting a user without USERS_MANAGE permission returns 403."""
        read_only_headers = _actor_headers("reader-1", "readonly", account_ids="*")
        # Create user first
        super_admin_headers = _actor_headers("admin-1", "super_admin")
        user = _create_user(
            client,
            super_admin_headers,
            account_id="test-account-008",
            public_user_id="delete-test-user-3",
            display_name="Delete Test User 3",
        )
        user_id = user["id"]
        # Try to delete with read-only permissions
        resp = client.delete(f"/api/platform/users/{user_id}", headers=read_only_headers)
        assert resp.status_code == 403

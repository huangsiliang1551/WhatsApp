"""Tests for Canned Responses API (BFX-004)."""

from fastapi.testclient import TestClient


class TestCannedResponses:
    def test_create_canned_response(self, client: TestClient) -> None:
        resp = client.post(
            "/api/canned-responses",
            json={
                "title": "Greeting",
                "content": "Hello {{customer_name}}, how can I help you?",
                "category": "greeting",
                "variables": ["customer_name"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Greeting"
        assert "id" in data

    def test_list_canned_responses(self, client: TestClient) -> None:
        client.post(
            "/api/canned-responses",
            json={
                "title": "Farewell",
                "content": "Goodbye!",
                "category": "farewell",
                "variables": [],
                "is_active": True,
            },
        )
        resp = client.get("/api/canned-responses")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_canned_response_by_id(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/canned-responses",
            json={
                "title": "Test Get",
                "content": "Get test content",
                "category": "test",
                "variables": [],
                "is_active": True,
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        resp = client.get(f"/api/canned-responses?search={created['id']}")
        assert resp.status_code == 200

    def test_update_canned_response(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/canned-responses",
            json={
                "title": "Original Title",
                "content": "Original content",
                "category": "test",
                "variables": [],
                "is_active": True,
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        resp = client.put(
            f"/api/canned-responses/{created['id']}",
            json={
                "title": "Updated Title",
                "content": "Updated content",
                "category": "test",
                "variables": ["var1"],
                "is_active": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"

    def test_delete_canned_response(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/canned-responses",
            json={
                "title": "To Delete",
                "content": "Will be deleted",
                "category": "test",
                "variables": [],
                "is_active": True,
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        resp = client.delete(f"/api/canned-responses/{created['id']}")
        assert resp.status_code == 200

    def test_list_by_category(self, client: TestClient) -> None:
        client.post(
            "/api/canned-responses",
            json={
                "title": "Category Test",
                "content": "Category filter content",
                "category": "filter-test",
                "variables": [],
                "is_active": True,
            },
        )
        resp = client.get("/api/canned-responses?category=filter-test")
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["category"] == "filter-test" for item in data)

    def test_canned_response_requires_title(self, client: TestClient) -> None:
        resp = client.post(
            "/api/canned-responses",
            json={
                "content": "Missing title",
                "category": "test",
                "variables": [],
                "is_active": True,
            },
        )
        assert resp.status_code == 422

    def test_canned_response_requires_content(self, client: TestClient) -> None:
        resp = client.post(
            "/api/canned-responses",
            json={
                "title": "Missing Content",
                "category": "test",
                "variables": [],
                "is_active": True,
            },
        )
        assert resp.status_code == 422

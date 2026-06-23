from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestGlobalSearch:
    def test_search_returns_all_sections(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=test")
        assert resp.status_code == 200
        data = resp.json()
        for section in ("conversations", "customers", "templates", "tickets"):
            assert section in data
            assert isinstance(data[section], list)

    def test_search_requires_query(self, client: TestClient) -> None:
        resp = client.get("/api/search")
        assert resp.status_code == 422

    def test_search_empty_query(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=")
        assert resp.status_code == 422

    def test_search_with_type_filter(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=test&type=templates")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["templates"], list)
        assert data["conversations"] == []
        assert data["customers"] == []
        assert data["tickets"] == []

    def test_search_with_limit(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=test&limit=3")
        assert resp.status_code == 200
        for section in ("conversations", "customers", "templates", "tickets"):
            assert len(resp.json()[section]) <= 3

    def test_search_limit_max(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=test&limit=100")
        assert resp.status_code == 422  # limited to 50

    def test_search_with_account_filter(self, client: TestClient) -> None:
        resp = client.get("/api/search?q=test&account_id=test-account")
        assert resp.status_code == 200

    def test_search_response_time(self, client: TestClient) -> None:
        import time
        t0 = time.monotonic()
        client.get("/api/search?q=test")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 3000

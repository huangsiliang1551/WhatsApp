from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestExports:
    def test_create_export_returns_task(self, client: TestClient) -> None:
        resp = client.post("/api/exports", json={"type": "conversations"})
        assert resp.status_code == 200
        data = resp.json()
        assert "export_id" in data
        assert "status" in data
        assert "estimated_rows" in data

    def test_create_export_invalid_type(self, client: TestClient) -> None:
        resp = client.post("/api/exports", json={"type": "invalid_type"})
        assert resp.status_code == 400

    def test_create_export_with_filters(self, client: TestClient) -> None:
        resp = client.post("/api/exports", json={
            "type": "conversations",
            "filters": {"status": "open"},
        })
        assert resp.status_code == 200

    def test_create_export_with_columns(self, client: TestClient) -> None:
        resp = client.post("/api/exports", json={
            "type": "templates",
            "columns": ["template_id", "name", "status"],
        })
        assert resp.status_code == 200

    def test_get_export_status(self, client: TestClient) -> None:
        create_resp = client.post("/api/exports", json={"type": "conversations"})
        export_id = create_resp.json()["export_id"]
        resp = client.get(f"/api/exports/{export_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["export_id"] == export_id

    def test_get_export_status_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/exports/nonexistent")
        assert resp.status_code == 404

    def test_download_export(self, client: TestClient) -> None:
        create_resp = client.post("/api/exports", json={"type": "conversations"})
        export_id = create_resp.json()["export_id"]
        resp = client.get(f"/api/exports/{export_id}/download")
        assert resp.status_code in (200, 400)  # 400 if still processing
        if resp.status_code == 200:
            assert "text/csv" in resp.headers.get("content-type", "")

    def test_download_export_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/exports/nonexistent/download")
        assert resp.status_code == 404

    def test_create_all_export_types(self, client: TestClient) -> None:
        for export_type in ("templates", "tickets", "audit_logs"):
            resp = client.post("/api/exports", json={"type": export_type})
            assert resp.status_code == 200, f"Failed for type '{export_type}': {resp.text}"

    def test_create_export_with_account_filter(self, client: TestClient) -> None:
        resp = client.post("/api/exports", json={
            "type": "conversations",
            "account_id": "test-account",
        })
        assert resp.status_code == 200

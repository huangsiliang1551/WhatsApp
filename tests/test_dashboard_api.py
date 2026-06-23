from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestDashboardSummary:
    def test_summary_returns_all_sections(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "system_health" in data
        assert "conversation_summary" in data
        assert "message_stats" in data
        assert "ai_performance" in data
        assert "queue_status" in data
        assert "account_count" in data
        assert "agent_online_count" in data

    def test_summary_system_health_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        data = resp.json()
        health = data["system_health"]
        for field in ("app_healthy", "worker_healthy", "db_healthy", "redis_healthy", "queue_healthy", "last_check"):
            assert field in health

    def test_summary_conversation_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        data = resp.json()
        conv = data["conversation_summary"]
        for field in ("total_open", "ai_managed", "human_managed", "paused", "handover_recommended"):
            assert field in conv
            assert isinstance(conv[field], int)

    def test_summary_message_stats_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        data = resp.json()
        msgs = data["message_stats"]
        for field in ("today_inbound", "today_outbound", "today_total", "yesterday_total", "change_percent"):
            assert field in msgs

    def test_summary_ai_performance_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        data = resp.json()
        ai = data["ai_performance"]
        for field in ("reply_rate", "fallback_rate", "handover_rate", "avg_response_seconds"):
            assert field in ai

    def test_summary_queue_status_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/summary")
        data = resp.json()
        queue = data["queue_status"]
        for field in ("pending", "processing", "failed", "dead_letter"):
            assert field in queue

    def test_summary_response_time(self, client: TestClient) -> None:
        import time
        t0 = time.monotonic()
        client.get("/api/dashboard/summary")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 5000, f"Dashboard summary took {elapsed:.0f}ms, expected <5000ms"


class TestDashboardTodo:
    def test_todo_returns_items(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/todo")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "high_priority_count" in data
        assert isinstance(data["items"], list)

    def test_todo_item_has_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/todo")
        data = resp.json()
        if data["items"]:
            item = data["items"][0]
            for field in ("type", "label", "count", "priority", "action_path"):
                assert field in item


class TestDashboardMessageTrend:
    def test_message_trend_returns_points(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/message-trend?hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert isinstance(data["points"], list)

    def test_message_trend_point_has_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/message-trend?hours=24")
        data = resp.json()
        if data["points"]:
            point = data["points"][0]
            for field in ("hour", "inbound", "outbound", "template"):
                assert field in point

    def test_message_trend_default_hours(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/message-trend")
        assert resp.status_code == 200

    def test_message_trend_7d(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/message-trend?hours=168")
        assert resp.status_code == 200

    def test_message_trend_30d(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/message-trend?hours=720")
        assert resp.status_code == 200


class TestDashboardAiPerformance:
    def test_ai_performance_returns_structure(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/ai-performance?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "days" in data
        assert "daily" in data
        assert "summary" in data
        assert data["days"] == 7

    def test_ai_performance_daily_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/ai-performance?days=7")
        data = resp.json()
        if data["daily"]:
            day = data["daily"][0]
            for field in ("date", "total_requests", "ai_replies", "fallbacks", "handovers", "reply_rate", "fallback_rate", "handover_rate"):
                assert field in day

    def test_ai_performance_summary_fields(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/ai-performance?days=7")
        data = resp.json()
        summary = data["summary"]
        for field in ("avg_reply_rate", "avg_fallback_rate", "avg_handover_rate", "total_requests"):
            assert field in summary

    def test_ai_performance_default_days(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/ai-performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7

    def test_ai_performance_30d(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/ai-performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 30

    def test_top_intents_returns_structure(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/top-intents?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_top_intents_default_limit(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/top-intents")
        assert resp.status_code == 200

    def test_top_intents_with_limit(self, client: TestClient) -> None:
        resp = client.get("/api/dashboard/top-intents?days=30&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5

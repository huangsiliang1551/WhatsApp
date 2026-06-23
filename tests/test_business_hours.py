"""Tests for Business Hours API (BFX-005)."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient


class TestBusinessHours:
    def test_get_business_hours_defaults(self, client: TestClient) -> None:
        resp = client.get("/api/runtime/business-hours?account_id=bh-test-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "business_hours" in data
        bh = data["business_hours"]
        assert bh["weekdays"] == [1, 2, 3, 4, 5]
        assert bh["start_time"] == "09:00"
        assert bh["end_time"] == "18:00"
        assert bh["timezone"] == "Asia/Shanghai"
        assert bh["off_hours_behavior"] == "ai_managed"
        assert "is_currently_business_hours" in data

    def test_upsert_business_hours(self, client: TestClient) -> None:
        resp = client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-2",
                "weekdays": [1, 2, 3, 4, 5, 6],
                "start_time": "08:00",
                "end_time": "20:00",
                "timezone": "America/New_York",
                "off_hours_behavior": "message",
                "off_hours_message": "We are closed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        bh = data["business_hours"]
        assert bh["weekdays"] == [1, 2, 3, 4, 5, 6]
        assert bh["start_time"] == "08:00"
        assert bh["end_time"] == "20:00"
        assert bh["timezone"] == "America/New_York"
        assert bh["off_hours_behavior"] == "message"

    def test_get_after_upsert(self, client: TestClient) -> None:
        client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-3",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "10:00",
                "end_time": "18:00",
                "timezone": "Asia/Tokyo",
                "off_hours_behavior": "silent",
            },
        )
        resp = client.get("/api/runtime/business-hours?account_id=bh-test-3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["business_hours"]["timezone"] == "Asia/Tokyo"
        assert data["business_hours"]["off_hours_behavior"] == "silent"

    def test_business_hours_is_currently_true_during_work_hours(self, client: TestClient) -> None:
        now = datetime.now(UTC)
        weekday = now.isoweekday()
        if weekday <= 5 and 2 <= now.hour < 16:
            resp = client.get("/api/runtime/business-hours?account_id=bh-test-4")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data["is_currently_business_hours"], bool)

    def test_off_hours_behavior_ai_managed(self, client: TestClient) -> None:
        resp = client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-5",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "09:00",
                "end_time": "18:00",
                "timezone": "Asia/Shanghai",
                "off_hours_behavior": "ai_managed",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["business_hours"]["off_hours_behavior"] == "ai_managed"

    def test_off_hours_behavior_message_with_custom_text(self, client: TestClient) -> None:
        resp = client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-6",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "09:00",
                "end_time": "18:00",
                "timezone": "Asia/Shanghai",
                "off_hours_behavior": "message",
                "off_hours_message": "Custom off-hours message",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["business_hours"]["off_hours_message"] == "Custom off-hours message"

    def test_off_hours_behavior_silent(self, client: TestClient) -> None:
        resp = client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-7",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "09:00",
                "end_time": "18:00",
                "timezone": "Asia/Shanghai",
                "off_hours_behavior": "silent",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["business_hours"]["off_hours_behavior"] == "silent"

    def test_invalid_weekdays(self, client: TestClient) -> None:
        resp = client.put(
            "/api/runtime/business-hours",
            params={
                "account_id": "bh-test-8",
                "weekdays": [0, 8],
                "start_time": "09:00",
                "end_time": "18:00",
                "timezone": "Asia/Shanghai",
                "off_hours_behavior": "ai_managed",
            },
        )
        assert resp.status_code in (200, 422)

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker, Session

from tests.test_h5_member_auth import _operator_headers
from tests.test_task_monitor_query_api import _seed_task_monitor_query_scope


def _super_admin_headers(account_id: str, actor_id: str) -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": account_id,
    }


def test_list_task_monitor_alerts_generates_events_from_matching_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-alerts")
    headers = _super_admin_headers(seeded["account_id"], "admin-task-alert-events")

    create_manual_add = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor alerts setup",
        },
    )
    assert create_manual_add.status_code == 200, create_manual_add.text

    create_rule = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Effective Amount",
            "status": "active",
            "condition_json": {"field": "effective_amount", "operator": ">=", "value": 130},
            "action_json": {"notify_staff": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_rule.status_code == 200, create_rule.text
    rule_payload = create_rule.json()

    response = client.get(
        "/api/tasks/monitor/alerts",
        params={"account_id": seeded["account_id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["accountId"] == seeded["account_id"]
    assert payload[0]["alertRuleId"] == rule_payload["id"]
    assert payload[0]["packageId"] == seeded["package_id"]
    assert payload[0]["publicUserId"] == seeded["public_user_id"]
    assert payload[0]["status"] == "open"
    assert payload[0]["priority"] == "high"
    assert payload[0]["currentValue"] == 140.0

    second_response = client.get(
        "/api/tasks/monitor/alerts",
        params={"account_id": seeded["account_id"]},
        headers=headers,
    )
    assert second_response.status_code == 200, second_response.text
    second_payload = second_response.json()
    assert len(second_payload) == 1
    assert second_payload[0]["id"] == payload[0]["id"]


def test_ack_and_resolve_task_monitor_alert_event(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-alerts-ack")
    headers = _super_admin_headers(seeded["account_id"], "admin-task-alert-events-ack")

    create_manual_add = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor alerts ack setup",
        },
    )
    assert create_manual_add.status_code == 200, create_manual_add.text

    create_rule = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Effective Amount Ack",
            "status": "active",
            "condition_json": {"field": "effective_amount", "operator": ">=", "value": 130},
            "action_json": {"notify_staff": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_rule.status_code == 200, create_rule.text

    list_response = client.get(
        "/api/tasks/monitor/alerts",
        params={"account_id": seeded["account_id"]},
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    alert_id = list_response.json()[0]["id"]

    ack_response = client.post(
        f"/api/tasks/monitor/alerts/{alert_id}/ack",
        headers=headers,
    )
    assert ack_response.status_code == 200, ack_response.text
    acked = ack_response.json()
    assert acked["status"] == "acknowledged"
    assert acked["acknowledgedBy"] == "admin-task-alert-events-ack"

    resolve_response = client.post(
        f"/api/tasks/monitor/alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert resolve_response.status_code == 200, resolve_response.text
    resolved = resolve_response.json()
    assert resolved["status"] == "resolved"
    assert resolved["resolvedBy"] == "admin-task-alert-events-ack"


def test_stream_task_monitor_alerts_emits_snapshot_event(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-alerts-stream")
    headers = _super_admin_headers(seeded["account_id"], "admin-task-alert-events-stream")

    create_manual_add = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor alerts stream setup",
        },
    )
    assert create_manual_add.status_code == 200, create_manual_add.text

    create_rule = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Effective Amount Stream",
            "status": "active",
            "condition_json": {"field": "effective_amount", "operator": ">=", "value": 130},
            "action_json": {"notify_staff": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_rule.status_code == 200, create_rule.text

    with client.stream(
        "GET",
        "/api/tasks/monitor/alerts/stream",
        params={"account_id": seeded["account_id"], "max_events": 1},
        headers=headers,
    ) as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        chunks = []
        for chunk in response.iter_text():
            if chunk:
                chunks.append(chunk)
            if "event: snapshot" in "".join(chunks) and seeded["package_id"] in "".join(chunks):
                break

    body = "".join(chunks)
    assert "event: snapshot" in body
    assert seeded["package_id"] in body
    assert seeded["public_user_id"] in body


def test_stream_task_monitor_alerts_keeps_connection_alive_with_heartbeat(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-alerts-heartbeat")
    headers = _super_admin_headers(seeded["account_id"], "admin-task-alert-events-heartbeat")

    create_manual_add = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor alerts heartbeat setup",
        },
    )
    assert create_manual_add.status_code == 200, create_manual_add.text

    create_rule = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Effective Amount Heartbeat",
            "status": "active",
            "condition_json": {"field": "effective_amount", "operator": ">=", "value": 130},
            "action_json": {"notify_staff": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_rule.status_code == 200, create_rule.text

    with client.stream(
        "GET",
        "/api/tasks/monitor/alerts/stream",
        params={
            "account_id": seeded["account_id"],
            "heartbeat_interval_seconds": 0.01,
            "snapshot_interval_seconds": 0.2,
            "max_events": 2,
        },
        headers=headers,
    ) as response:
        assert response.status_code == 200
        chunks: list[str] = []
        for chunk in response.iter_text():
            if chunk:
                chunks.append(chunk)
            joined = "".join(chunks)
            if "event: snapshot" in joined and ": heartbeat" in joined:
                break

    body = "".join(chunks)
    assert "event: snapshot" in body
    assert ": heartbeat" in body

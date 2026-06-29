from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account


def _seed_task_monitor_scope(
    db_session_factory: sessionmaker[Session],
    *,
    suffix: str = "",
) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(
            account_id=f"acct-task-monitor-api{suffix}",
            display_name=f"Task Monitor API{suffix}",
        )
        session.add(account)
        session.commit()
        return {"account_id": account.account_id}


def test_create_and_list_task_monitor_saved_views(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "staff-task-monitor-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/monitor-saved-views",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Risk Tasks",
            "filter_json": {"risk_tag": "high"},
            "sort_json": [{"field": "actual_day_amount", "order": "desc"}],
            "columns_json": ["public_user_id", "task_balance", "risk_tags"],
            "refresh_seconds": 15,
            "sound_enabled": True,
            "is_default": True,
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["ownerStaffId"] == "staff-task-monitor-api"
    assert created["soundEnabled"] is True

    list_response = client.get(
        "/api/tasks/monitor-saved-views",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["name"] == "High Risk Tasks"


def test_update_and_delete_task_monitor_saved_view(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory, suffix="-edit")
    headers = {
        "X-Actor-Id": "staff-task-monitor-edit",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/monitor-saved-views",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "Default View",
            "filter_json": {"status": "running"},
            "sort_json": [{"field": "created_at", "order": "desc"}],
            "columns_json": ["public_user_id", "status"],
            "refresh_seconds": 10,
            "sound_enabled": False,
            "is_default": True,
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    update_response = client.patch(
        f"/api/tasks/monitor-saved-views/{created['id']}",
        headers=headers,
        json={
            "name": "Escalation View",
            "filter_json": {"status": "failed"},
            "sort_json": [{"field": "actual_day_system_amount", "order": "desc"}],
            "columns_json": ["public_user_id", "failure_reason", "status"],
            "refresh_seconds": 30,
            "sound_enabled": True,
            "is_default": True,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "Escalation View"
    assert updated["filterJson"] == {"status": "failed"}
    assert updated["soundEnabled"] is True

    list_response = client.get(
        "/api/tasks/monitor-saved-views",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Escalation View"

    delete_response = client.delete(
        f"/api/tasks/monitor-saved-views/{created['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    final_list_response = client.get(
        "/api/tasks/monitor-saved-views",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert final_list_response.status_code == 200, final_list_response.text
    assert final_list_response.json() == []


def test_task_monitor_saved_views_are_isolated_per_staff_owner(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory, suffix="-owner-scope")
    owner_headers = {
        "X-Actor-Id": "staff-task-monitor-owner-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }
    other_headers = {
        "X-Actor-Id": "staff-task-monitor-owner-b",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/monitor-saved-views",
        headers=owner_headers,
        json={
            "account_id": seeded["account_id"],
            "name": "Owner A View",
            "filter_json": {"has_manual_add": True},
            "sort_json": [{"field": "effective_amount", "order": "desc"}],
            "columns_json": ["public_user_id", "effective_amount"],
            "refresh_seconds": 15,
            "sound_enabled": True,
            "is_default": True,
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    owner_list_response = client.get(
        "/api/tasks/monitor-saved-views",
        headers=owner_headers,
        params={"account_id": seeded["account_id"]},
    )
    assert owner_list_response.status_code == 200, owner_list_response.text
    assert [row["name"] for row in owner_list_response.json()] == ["Owner A View"]

    other_list_response = client.get(
        "/api/tasks/monitor-saved-views",
        headers=other_headers,
        params={"account_id": seeded["account_id"]},
    )
    assert other_list_response.status_code == 200, other_list_response.text
    assert other_list_response.json() == []

    other_update_response = client.patch(
        f"/api/tasks/monitor-saved-views/{created['id']}",
        headers=other_headers,
        json={
            "name": "Owner B Hijack",
            "filter_json": {"status": "active"},
            "sort_json": [{"field": "created_at", "order": "desc"}],
            "columns_json": ["public_user_id"],
            "refresh_seconds": 30,
            "sound_enabled": False,
            "is_default": False,
        },
    )
    assert other_update_response.status_code == 404, other_update_response.text

    other_delete_response = client.delete(
        f"/api/tasks/monitor-saved-views/{created['id']}",
        headers=other_headers,
    )
    assert other_delete_response.status_code == 404, other_delete_response.text


def test_create_and_list_task_alert_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "admin-task-alert-api",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "High Amount Alert",
            "status": "active",
            "condition_json": {"field": "actual_day_amount", "operator": ">=", "value": 2000},
            "action_json": {"notify_staff": True, "require_manual_review": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["name"] == "High Amount Alert"
    assert created["priority"] == "high"

    list_response = client.get(
        "/api/tasks/alert-rules",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["actionJson"]["notify_staff"] is True


def test_update_and_delete_task_alert_rule(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory, suffix="-rule-edit")
    headers = {
        "X-Actor-Id": "admin-task-alert-edit",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/alert-rules",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "name": "Original Alert",
            "status": "active",
            "condition_json": {"field": "actual_day_amount", "operator": ">=", "value": 2000},
            "action_json": {"notify_staff": True},
            "sound_enabled": False,
            "priority": "normal",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    update_response = client.patch(
        f"/api/tasks/alert-rules/{created['id']}",
        headers=headers,
        json={
            "name": "Critical Alert",
            "status": "paused",
            "condition_json": {"field": "actual_day_amount", "operator": ">=", "value": 5000},
            "action_json": {"notify_staff": True, "require_manual_review": True},
            "sound_enabled": True,
            "priority": "high",
            "metadata_json": {"channel": "ops"},
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "Critical Alert"
    assert updated["status"] == "paused"
    assert updated["priority"] == "high"
    assert updated["metadataJson"] == {"channel": "ops"}

    list_response = client.get(
        "/api/tasks/alert-rules",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Critical Alert"

    delete_response = client.delete(
        f"/api/tasks/alert-rules/{created['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    final_list_response = client.get(
        "/api/tasks/alert-rules",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert final_list_response.status_code == 200, final_list_response.text
    assert final_list_response.json() == []


def test_task_monitor_documented_alias_routes_remain_available(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_scope(db_session_factory, suffix="-aliases")
    operator_headers = {
        "X-Actor-Id": "staff-task-monitor-aliases",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }
    admin_headers = {
        "X-Actor-Id": "admin-task-alert-aliases",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_view_response = client.post(
        "/api/tasks/monitor/saved-views",
        headers=operator_headers,
        json={
            "account_id": seeded["account_id"],
            "name": "Alias View",
            "filter_json": {"status": "active"},
            "sort_json": [{"field": "created_at", "order": "desc"}],
            "columns_json": ["public_user_id", "status"],
            "refresh_seconds": 20,
            "sound_enabled": False,
            "is_default": True,
        },
    )
    assert create_view_response.status_code == 200, create_view_response.text

    list_view_response = client.get(
        "/api/tasks/monitor/saved-views",
        headers=operator_headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_view_response.status_code == 200, list_view_response.text
    assert list_view_response.json()[0]["name"] == "Alias View"

    create_rule_response = client.post(
        "/api/tasks/monitor/alert-rules",
        headers=admin_headers,
        json={
            "account_id": seeded["account_id"],
            "name": "Alias Alert Rule",
            "status": "active",
            "condition_json": {"field": "actual_day_amount", "operator": ">=", "value": 1000},
            "action_json": {"notify_staff": True},
            "sound_enabled": True,
            "priority": "high",
        },
    )
    assert create_rule_response.status_code == 200, create_rule_response.text

    list_rule_response = client.get(
        "/api/tasks/monitor/alert-rules",
        headers=admin_headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_rule_response.status_code == 200, list_rule_response.text
    assert list_rule_response.json()[0]["name"] == "Alias Alert Rule"

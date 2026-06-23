from fastapi.testclient import TestClient


def test_task_template_and_instance_minimum_closure(client: TestClient) -> None:
    headers = {
        "X-Actor-Id": "operator-task-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "task-account-1",
    }

    site_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "task-account-1",
            "site_key": "task-site-1",
            "domain": "task.example.com",
            "brand_name": "Task Site",
        },
        headers=headers,
    )
    assert site_response.status_code == 200
    site = site_response.json()

    user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": "task-user-1",
            "registration_site_id": site["id"],
            "display_name": "Task User",
            "language_code": "zh-CN",
            "identities": [
                {
                    "identity_type": "phone",
                    "identity_value": "+8613900000001",
                    "is_verified": True,
                    "is_primary": True,
                }
            ],
        },
        headers=headers,
    )
    assert user_response.status_code == 200
    user = user_response.json()

    audience_rule_response = client.post(
        "/api/platform/audience-rules",
        json={
            "rule_key": "task-rule-1",
            "name": "Task Rule 1",
            "scope_type": "task_template",
            "status": "active",
            "rules_json": {"site_keys": ["task-site-1"]},
        },
        headers=headers,
    )
    assert audience_rule_response.status_code == 200
    audience_rule = audience_rule_response.json()

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": "task-account-1",
            "task_key": "shopping-first-order",
            "name": "首单购物任务",
            "title": "完成首单购物",
            "description": "用于第一期购物任务闭环。",
            "task_type": "shopping",
            "status": "active",
            "audience_rule_set_id": audience_rule["id"],
            "reward_amount": "12.50",
            "reward_points": 20,
            "claim_timeout_seconds": 7200,
            "auto_review_enabled": True,
        },
        headers=headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()
    assert template["task_key"] == "shopping-first-order"
    assert template["claim_timeout_seconds"] == 7200

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": "task-account-1",
            "template_id": template["id"],
            "user_id": user["id"],
            "site_id": site["id"],
            "review_required": True,
        },
        headers=headers,
    )
    assert instance_response.status_code == 200
    instance = instance_response.json()
    assert instance["status"] == "available"
    assert instance["review_required"] is True
    assert instance["public_user_id"] == "task-user-1"

    claim_response = client.post(
        f"/api/tasks/instances/{instance['id']}/claim",
        json={},
        headers=headers,
    )
    assert claim_response.status_code == 200
    claimed = claim_response.json()
    assert claimed["status"] == "claimed"
    assert claimed["claimed_at"] is not None
    assert claimed["claim_deadline_at"] is not None

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={"target_type": "task_instance", "target_id": instance["id"]},
        headers=headers,
    )
    assert audit_response.status_code == 200
    assert [item["action"] for item in audit_response.json()] == [
        "task_instance_claimed",
        "task_instance_created",
    ]


def test_anonymous_user_cannot_receive_task_instance(client: TestClient) -> None:
    headers = {
        "X-Actor-Id": "operator-task-2",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "task-account-2",
    }
    admin_headers = {
        "X-Actor-Id": "admin-task-2",
        "X-Actor-Role": "super_admin",
    }

    user_response = client.post(
        "/api/platform/users",
        json={
            "account_id": "task-account-2",
            "public_user_id": "anon-task-user",
            "display_name": "Anonymous User",
            "language_code": "zh-CN",
            "is_anonymous": True,
        },
        headers=admin_headers,
    )
    assert user_response.status_code == 200
    user = user_response.json()

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": "task-account-2",
            "task_key": "daily-check-in",
            "name": "每日连续任务",
            "title": "今日打卡",
            "task_type": "daily",
            "status": "draft",
            "claim_timeout_seconds": 3600,
        },
        headers=headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": "task-account-2",
            "template_id": template["id"],
            "user_id": user["id"],
        },
        headers=headers,
    )
    assert instance_response.status_code == 409
    assert "Anonymous users cannot receive formal task instances." in instance_response.json()["detail"]

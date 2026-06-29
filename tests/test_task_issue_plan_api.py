from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5Site, TaskIssuePlan, TaskIssuePlanDayRule, TaskProductPool


def _seed_task_issue_plan_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-plan-api", display_name="Task Plan API")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-plan-api",
            domain="task-plan-api.example.com",
            brand_name="Task Plan API",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Plan Pool",
            code="plan-pool",
            pool_type="general",
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Existing Official Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            require_previous_batch_completed=True,
            max_unfinished_batches=1,
            after_last_rule_mode="repeat_last",
            growth_package_count_step=1,
            growth_amount_step=Decimal("50.00"),
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.15"),
        )
        session.add(plan)
        session.flush()

        session.add(
            TaskIssuePlanDayRule(
                account_id=account.account_id,
                site_id=site.id,
                plan_id=plan.id,
                day_no=1,
                package_count=2,
                day_total_amount=Decimal("200.00"),
                tolerance_amount=Decimal("5.00"),
                amount_allocation_mode="average",
                package_amounts_json=["100.00", "100.00"],
                product_pool_id=pool.id,
                product_count_mode="fixed",
                product_count_fixed=2,
                reward_ratio=Decimal("0.11"),
                issue_time_of_day="09:00",
                elapsed_delay_hours=None,
                status="active",
            )
        )
        session.commit()
        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "pool_id": pool.id,
            "plan_id": plan.id,
        }


def test_create_and_list_task_issue_plans(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/issue-plans",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Growth Plan",
            "plan_type": "official",
            "status": "active",
            "claim_gate": "certified_member",
            "issue_anchor": "certified_at",
            "issue_mode": "calendar_day",
            "require_previous_batch_completed": True,
            "max_unfinished_batches": 1,
            "after_last_rule_mode": "arithmetic_growth",
            "growth_package_count_step": 2,
            "growth_amount_step": "80.00",
            "default_product_pool_id": seeded["pool_id"],
            "default_tolerance_amount": "10.00",
            "default_reward_ratio": "0.20",
            "day_rules": [
                {
                    "day_no": 1,
                    "package_count": 3,
                    "day_total_amount": "300.00",
                    "tolerance_amount": "10.00",
                    "amount_allocation_mode": "average",
                    "package_amounts_json": ["100.00", "100.00", "100.00"],
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "range",
                    "product_count_min": 1,
                    "product_count_max": 3,
                    "reward_ratio": "0.20",
                    "issue_time_of_day": "10:00",
                    "status": "active",
                }
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["name"] == "Growth Plan"
    assert created["dayRules"][0]["dayNo"] == 1
    assert created["dayRules"][0]["packageAmountsJson"] == ["100.00", "100.00", "100.00"]

    create_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_issue_plan",
            "target_id": created["id"],
        },
    )
    assert create_audit_response.status_code == 200, create_audit_response.text
    create_logs = create_audit_response.json()
    create_matching = [item for item in create_logs if item["action"] == "task_issue_plan_created"]
    assert len(create_matching) == 1
    assert create_matching[0]["payload"]["plan_type"] == "official"
    assert create_matching[0]["payload"]["status"] == "active"
    assert create_matching[0]["payload"]["day_rule_count"] == 1

    list_response = client.get(
        "/api/tasks/issue-plans",
        headers=headers,
        params={"account_id": seeded["account_id"]},
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 2
    names = {item["name"] for item in listed}
    assert names == {"Existing Official Plan", "Growth Plan"}


def test_cross_account_task_issue_plan_create_is_forbidden(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-forbidden",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-other-scope",
    }

    response = client.post(
        "/api/tasks/issue-plans",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Forbidden Plan",
            "plan_type": "official",
            "status": "active",
            "claim_gate": "certified_member",
            "issue_anchor": "certified_at",
            "issue_mode": "calendar_day",
            "require_previous_batch_completed": True,
            "max_unfinished_batches": 1,
            "after_last_rule_mode": "repeat_last",
            "growth_package_count_step": 1,
            "default_product_pool_id": seeded["pool_id"],
            "default_tolerance_amount": "5.00",
            "default_reward_ratio": "0.10",
            "day_rules": [],
        },
    )
    assert response.status_code == 403


def test_create_task_issue_plan_rejects_duplicate_day_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        "/api/tasks/issue-plans",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Duplicate Days Plan",
            "plan_type": "official",
            "status": "active",
            "claim_gate": "certified_member",
            "issue_anchor": "certified_at",
            "issue_mode": "calendar_day",
            "require_previous_batch_completed": True,
            "max_unfinished_batches": 1,
            "after_last_rule_mode": "repeat_last",
            "growth_package_count_step": 1,
            "default_product_pool_id": seeded["pool_id"],
            "default_tolerance_amount": "5.00",
            "default_reward_ratio": "0.10",
            "day_rules": [
                {
                    "day_no": 1,
                    "package_count": 2,
                    "day_total_amount": "200.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "package_amounts_json": ["100.00", "100.00"],
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 2,
                    "reward_ratio": "0.10",
                    "status": "active",
                },
                {
                    "day_no": 1,
                    "package_count": 3,
                    "day_total_amount": "300.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "package_amounts_json": ["100.00", "100.00", "100.00"],
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 3,
                    "reward_ratio": "0.10",
                    "status": "active",
                },
            ],
        },
    )

    assert response.status_code == 409, response.text
    assert "day_no" in response.json()["detail"]


def test_create_task_issue_plan_rejects_manual_amount_mismatch(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        "/api/tasks/issue-plans",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Broken Manual Plan",
            "plan_type": "official",
            "status": "active",
            "claim_gate": "certified_member",
            "issue_anchor": "certified_at",
            "issue_mode": "calendar_day",
            "require_previous_batch_completed": True,
            "max_unfinished_batches": 1,
            "after_last_rule_mode": "repeat_last",
            "growth_package_count_step": 1,
            "default_product_pool_id": seeded["pool_id"],
            "default_tolerance_amount": "5.00",
            "default_reward_ratio": "0.10",
            "day_rules": [
                {
                    "day_no": 1,
                    "package_count": 2,
                    "day_total_amount": "200.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "manual",
                    "package_amounts_json": ["80.00", "100.00"],
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 2,
                    "reward_ratio": "0.10",
                    "status": "active",
                }
            ],
        },
    )

    assert response.status_code == 409, response.text
    assert "day_total_amount" in response.json()["detail"]


def test_create_task_issue_plan_rejects_invalid_range_product_count(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        "/api/tasks/issue-plans",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "name": "Invalid Range Plan",
            "plan_type": "official",
            "status": "active",
            "claim_gate": "certified_member",
            "issue_anchor": "certified_at",
            "issue_mode": "calendar_day",
            "require_previous_batch_completed": True,
            "max_unfinished_batches": 1,
            "after_last_rule_mode": "repeat_last",
            "growth_package_count_step": 1,
            "default_product_pool_id": seeded["pool_id"],
            "default_tolerance_amount": "5.00",
            "default_reward_ratio": "0.10",
            "day_rules": [
                {
                    "day_no": 1,
                    "package_count": 2,
                    "day_total_amount": "200.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "package_amounts_json": ["100.00", "100.00"],
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "range",
                    "product_count_min": 3,
                    "product_count_max": 1,
                    "reward_ratio": "0.10",
                    "status": "active",
                }
            ],
        },
    )

    assert response.status_code == 409, response.text
    assert "product_count" in response.json()["detail"]


def test_task_issue_plan_detail_update_enable_disable_and_preview(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-detail",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    detail_response = client.get(f"/api/tasks/issue-plans/{seeded['plan_id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detailed = detail_response.json()
    assert detailed["id"] == seeded["plan_id"]
    assert detailed["status"] == "active"

    update_response = client.patch(
        f"/api/tasks/issue-plans/{seeded['plan_id']}",
        headers=headers,
        json={
            "name": "Updated Official Plan",
            "default_reward_ratio": "0.25",
            "metadata_json": {"source": "api-update"},
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "Updated Official Plan"
    assert updated["defaultRewardRatio"] == "0.2500"
    assert updated["metadataJson"] == {"source": "api-update"}

    update_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_issue_plan",
            "target_id": seeded["plan_id"],
        },
    )
    assert update_audit_response.status_code == 200, update_audit_response.text
    update_logs = update_audit_response.json()
    update_matching = [item for item in update_logs if item["action"] == "task_issue_plan_updated"]
    assert len(update_matching) == 1
    assert update_matching[0]["payload"]["status"] == "active"

    disable_response = client.post(f"/api/tasks/issue-plans/{seeded['plan_id']}/disable", headers=headers)
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["status"] == "disabled"

    disable_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_issue_plan",
            "target_id": seeded["plan_id"],
        },
    )
    assert disable_audit_response.status_code == 200, disable_audit_response.text
    disable_logs = disable_audit_response.json()
    disable_matching = [item for item in disable_logs if item["action"] == "task_issue_plan_disabled"]
    assert len(disable_matching) == 1

    enable_response = client.post(f"/api/tasks/issue-plans/{seeded['plan_id']}/enable", headers=headers)
    assert enable_response.status_code == 200, enable_response.text
    assert enable_response.json()["status"] == "active"

    enable_audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_issue_plan",
            "target_id": seeded["plan_id"],
        },
    )
    assert enable_audit_response.status_code == 200, enable_audit_response.text
    enable_logs = enable_audit_response.json()
    enable_matching = [item for item in enable_logs if item["action"] == "task_issue_plan_enabled"]
    assert len(enable_matching) == 1

    preview_response = client.post(
        f"/api/tasks/issue-plans/{seeded['plan_id']}/preview",
        headers=headers,
        json={"start_day_no": 1, "end_day_no": 3},
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert [item["dayNo"] for item in preview["dayRules"]] == [1, 2, 3]


def test_task_issue_plan_generate_days_persists_missing_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_issue_plan_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-plan-generate",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    generate_response = client.post(
        f"/api/tasks/issue-plans/{seeded['plan_id']}/generate-days",
        headers=headers,
        json={"start_day_no": 2, "end_day_no": 4},
    )
    assert generate_response.status_code == 200, generate_response.text
    generated = generate_response.json()
    assert [item["dayNo"] for item in generated["dayRules"]] == [1, 2, 3, 4]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_issue_plan",
            "target_id": seeded["plan_id"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    logs = audit_response.json()
    matching = [item for item in logs if item["action"] == "task_issue_plan_days_generated"]
    assert len(matching) == 1
    assert matching[0]["payload"]["start_day_no"] == 2
    assert matching[0]["payload"]["end_day_no"] == 4

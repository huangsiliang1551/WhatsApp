from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5Site, TaskIssuePlan, TaskSystemConfig


def _seed_task_system_config_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-config-api", display_name="Task Config API")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-config-api",
            domain="task-config-api.example.com",
            brand_name="Task Config API",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        newbie_plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Newbie Plan",
            plan_type="newbie",
            status="active",
        )
        official_plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Official Plan",
            plan_type="official",
            status="active",
        )
        session.add_all([newbie_plan, official_plan])
        session.commit()
        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "newbie_plan_id": newbie_plan.id,
            "official_plan_id": official_plan.id,
        }


def _operator_headers(account_id: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "operator-task-config-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": account_id,
    }


def test_get_task_system_config_returns_defaults_when_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)

    response = client.get(
        "/api/tasks/system-config",
        headers=_operator_headers(seeded["account_id"]),
        params={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["accountId"] == seeded["account_id"]
    assert payload["siteId"] == seeded["site_id"]
    assert payload["status"] == "active"
    assert payload["whatsappBindingRewardAmount"] == "20.00"
    assert payload["certifiedRechargeThreshold"] == "50.00"
    assert payload["maxActivePackagesPerUser"] == 1
    assert payload["createdAt"] is None
    assert payload["updatedAt"] is None


def test_get_task_system_config_falls_back_to_account_scope_when_site_config_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)
    with db_session_factory() as session:
        session.add(
            TaskSystemConfig(
                account_id=seeded["account_id"],
                site_id=None,
                whatsapp_binding_reward_amount="45.00",
                certified_recharge_threshold="120.00",
                max_active_packages_per_user=4,
            )
        )
        session.commit()

    response = client.get(
        "/api/tasks/system-config",
        headers=_operator_headers(seeded["account_id"]),
        params={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["accountId"] == seeded["account_id"]
    assert payload["siteId"] == seeded["site_id"]
    assert payload["whatsappBindingRewardAmount"] == "45.00"
    assert payload["certifiedRechargeThreshold"] == "120.00"
    assert payload["maxActivePackagesPerUser"] == 4


def test_upsert_task_system_config_persists_and_reads_back(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)
    payload = {
        "account_id": seeded["account_id"],
        "site_id": seeded["site_id"],
        "status": "active",
        "whatsapp_binding_reward_enabled": True,
        "whatsapp_binding_reward_amount": "28.50",
        "whatsapp_binding_reward_wallet_type": "task_balance",
        "whatsapp_binding_reward_currency": "USD",
        "certified_member_enabled": True,
        "certified_recharge_threshold": "88.00",
        "certified_recharge_scope": "real_recharge",
        "auto_certify_on_recharge": False,
        "newbie_task_enabled": True,
        "newbie_plan_id": seeded["newbie_plan_id"],
        "newbie_auto_popup": False,
        "official_plan_id": seeded["official_plan_id"],
        "show_task_balance_transfer_prompt": True,
        "min_task_balance_transfer_prompt_amount": "12.50",
        "max_active_batches_per_user": 2,
        "max_active_packages_per_user": 3,
        "metadata_json": {"source": "test"},
    }

    update_response = client.put(
        "/api/tasks/system-config",
        headers=_operator_headers(seeded["account_id"]),
        json=payload,
    )

    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["whatsappBindingRewardAmount"] == "28.50"
    assert updated["certifiedRechargeThreshold"] == "88.00"
    assert updated["newbiePlanId"] == seeded["newbie_plan_id"]
    assert updated["officialPlanId"] == seeded["official_plan_id"]
    assert updated["maxActiveBatchesPerUser"] == 2
    assert updated["maxActivePackagesPerUser"] == 3
    assert updated["metadataJson"] == {"source": "test"}
    assert updated["createdAt"] is not None
    assert updated["updatedAt"] is not None

    get_response = client.get(
        "/api/tasks/system-config",
        headers=_operator_headers(seeded["account_id"]),
        params={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
        },
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["whatsappBindingRewardAmount"] == "28.50"
    assert fetched["officialPlanId"] == seeded["official_plan_id"]
    assert fetched["maxActivePackagesPerUser"] == 3

    with db_session_factory() as session:
        config = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == seeded["account_id"],
            TaskSystemConfig.site_id == seeded["site_id"],
        ).one()
        assert str(config.whatsapp_binding_reward_amount) == "28.50"
        assert str(config.certified_recharge_threshold) == "88.00"


def test_cross_account_task_system_config_access_is_forbidden(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)

    response = client.get(
        "/api/tasks/system-config",
        headers=_operator_headers("acct-task-config-other"),
        params={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
        },
    )

    assert response.status_code == 403


def test_patch_task_system_config_and_list_audit_logs(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)
    headers = _operator_headers(seeded["account_id"])

    patch_response = client.patch(
        "/api/tasks/system-config",
        headers=headers,
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "status": "active",
            "whatsapp_binding_reward_enabled": True,
            "whatsapp_binding_reward_amount": "31.00",
            "whatsapp_binding_reward_wallet_type": "task_balance",
            "whatsapp_binding_reward_currency": "USD",
            "certified_member_enabled": True,
            "certified_recharge_threshold": "66.00",
            "certified_recharge_scope": "real_recharge",
            "auto_certify_on_recharge": True,
            "newbie_task_enabled": True,
            "newbie_auto_popup": True,
            "show_task_balance_transfer_prompt": True,
            "min_task_balance_transfer_prompt_amount": "2.50",
            "max_active_batches_per_user": 1,
            "max_active_packages_per_user": 2,
            "metadata_json": {"updated_by": "patch"},
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["whatsappBindingRewardAmount"] == "31.00"

    audit_response = client.get(
        "/api/tasks/system-config/audit-logs",
        headers=headers,
        params={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    logs = audit_response.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "task_system_config_updated"


def test_upsert_account_level_task_system_config_reuses_single_default_scope_row(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_system_config_scope(db_session_factory)
    with db_session_factory() as session:
        session.add(
            TaskSystemConfig(
                account_id=seeded["account_id"],
                site_id=None,
                whatsapp_binding_reward_amount="21.00",
            )
        )
        session.commit()

    response = client.put(
        "/api/tasks/system-config",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "account_id": seeded["account_id"],
            "site_id": None,
            "status": "active",
            "whatsapp_binding_reward_enabled": True,
            "whatsapp_binding_reward_amount": "55.00",
            "whatsapp_binding_reward_wallet_type": "task_balance",
            "whatsapp_binding_reward_currency": "USD",
            "certified_member_enabled": True,
            "certified_recharge_threshold": "66.00",
            "certified_recharge_scope": "real_recharge",
            "auto_certify_on_recharge": True,
            "newbie_task_enabled": True,
            "newbie_auto_popup": True,
            "show_task_balance_transfer_prompt": True,
            "min_task_balance_transfer_prompt_amount": "1.00",
            "max_active_batches_per_user": 1,
            "max_active_packages_per_user": 2,
            "metadata_json": {"deduped": True},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["whatsappBindingRewardAmount"] == "55.00"

    with db_session_factory() as session:
        rows = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == seeded["account_id"],
            TaskSystemConfig.site_id.is_(None),
        ).all()
        assert len(rows) == 1
        assert str(rows[0].whatsapp_binding_reward_amount) == "55.00"

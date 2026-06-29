from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    AppUser,
    H5Site,
    MemberProfile,
    MemberVerificationRequest,
    TaskProductGenerationRun,
    TaskSystemConfig,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskProductPool,
    TaskProductPoolItem,
    UserTag,
    UserTagAssignment,
    WalletAccount,
    WalletLedgerEntry,
)


def _seed_task_quota_api_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-quota-api", display_name="Task Quota API")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-quota-api",
            domain="task-quota-api.example.com",
            brand_name="Task Quota API",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account.account_id,
            public_user_id="task-quota-api-user",
            registration_site_id=site.id,
            display_name="Task Quota API User",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="API Pool",
            pool_type="general",
            status="active",
        )
        session.add_all([user, pool])
        session.flush()

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="API Official Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            growth_package_count_step=1,
            growth_amount_step=Decimal("50.00"),
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.15"),
        )
        session.add(plan)
        session.flush()

        day_rule = TaskIssuePlanDayRule(
            account_id=account.account_id,
            site_id=site.id,
            plan_id=plan.id,
            day_no=1,
            package_count=2,
            day_total_amount=Decimal("200.00"),
            tolerance_amount=Decimal("5.00"),
            amount_allocation_mode="average",
            package_amounts_json=[],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=2,
            reward_ratio=Decimal("0.11"),
        )
        session.add(day_rule)
        session.commit()

        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "user_id": user.id,
            "pool_id": pool.id,
            "plan_id": plan.id,
        }


def test_create_and_list_task_quotas(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/quotas",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "user_id": seeded["user_id"],
            "day_no": 3,
            "package_count": 3,
            "day_total_amount": "300.00",
            "tolerance_amount": "8.00",
            "amount_allocation_mode": "average",
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "range",
            "product_count_min": 1,
            "product_count_max": 3,
            "reward_ratio": "0.20",
            "created_by": "operator-task-quota-api",
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["packageAmountsJson"] == ["100.00", "100.00", "100.00"]

    list_response = client.get(
        "/api/tasks/quotas",
        params={"account_id": seeded["account_id"], "user_id": seeded["user_id"]},
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["accountId"] == seeded["account_id"]
    assert listed[0]["dayNo"] == 3

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "member_task_day_quota",
            "target_id": created["id"],
        },
        headers=headers,
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "member_task_day_quota_created"]
    assert len(matching) == 1
    assert matching[0]["payload"]["user_id"] == seeded["user_id"]
    assert matching[0]["payload"]["day_no"] == 3
    assert matching[0]["payload"]["package_count"] == 3
    assert matching[0]["payload"]["day_total_amount"] == "300.00"


def test_issue_task_quota_from_plan(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-issue",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    issue_response = client.post(
        "/api/tasks/quotas/issue-from-plan",
        json={
            "plan_id": seeded["plan_id"],
            "user_id": seeded["user_id"],
            "day_no": 1,
            "created_by": "operator-task-quota-issue",
        },
        headers=headers,
    )
    assert issue_response.status_code == 200, issue_response.text
    issued = issue_response.json()
    assert issued["planId"] == seeded["plan_id"]
    assert issued["packageAmountsJson"] == ["100.00", "100.00"]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "member_task_day_quota",
            "target_id": issued["id"],
        },
        headers=headers,
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "member_task_day_quota_issued_from_plan"]
    assert len(matching) == 1
    assert matching[0]["payload"]["user_id"] == seeded["user_id"]
    assert matching[0]["payload"]["plan_id"] == seeded["plan_id"]
    assert matching[0]["payload"]["day_no"] == 1


def test_create_task_quota_accepts_camel_case_payload(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-api-camel",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/quotas",
        json={
            "accountId": seeded["account_id"],
            "siteId": seeded["site_id"],
            "userId": seeded["user_id"],
            "dayNo": 4,
            "packageCount": 2,
            "dayTotalAmount": "120.00",
            "toleranceAmount": "3.00",
            "amountAllocationMode": "average",
            "productPoolId": seeded["pool_id"],
            "productCountMode": "fixed",
            "productCountFixed": 1,
            "rewardRatio": "0.10",
            "createdBy": "operator-task-quota-api-camel",
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["accountId"] == seeded["account_id"]
    assert created["dayNo"] == 4
    assert created["packageAmountsJson"] == ["60.00", "60.00"]


def test_issue_task_quota_from_plan_returns_409_before_schedule_window(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-schedule",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    with db_session_factory() as session:
        user = session.get(AppUser, seeded["user_id"])
        assert user is not None
        member_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=user.id,
            member_no="10000011",
            password_hash="quota-api-password-hash",
            password_salt="quota-api-password-salt",
        )
        session.add(member_profile)
        session.flush()
        session.add(
            MemberVerificationRequest(
                account_id=seeded["account_id"],
                member_profile_id=member_profile.id,
                request_type="identity",
                status="approved",
                reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
            )
        )
        day_rule = session.query(TaskIssuePlanDayRule).filter(
            TaskIssuePlanDayRule.plan_id == seeded["plan_id"],
            TaskIssuePlanDayRule.day_no == 1,
        ).one()
        day_rule.issue_time_of_day = "12:00"
        session.add(day_rule)
        session.commit()

    monkeypatch.setattr(
        "app.services.member_task_quota_service.utc_now",
        lambda: datetime.fromisoformat("2026-06-20T10:00:00"),
    )

    issue_response = client.post(
        "/api/tasks/quotas/issue-from-plan",
        json={
            "plan_id": seeded["plan_id"],
            "user_id": seeded["user_id"],
            "day_no": 1,
            "created_by": "operator-task-quota-schedule",
        },
        headers=headers,
    )
    assert issue_response.status_code == 409, issue_response.text
    assert "schedule window has not been reached" in issue_response.json()["detail"]


def test_cross_account_task_quota_create_is_forbidden(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-forbidden",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-other-scope",
    }

    create_response = client.post(
        "/api/tasks/quotas",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "user_id": seeded["user_id"],
            "day_no": 5,
            "package_count": 2,
            "day_total_amount": "200.00",
            "amount_allocation_mode": "average",
            "product_pool_id": seeded["pool_id"],
        },
        headers=headers,
    )
    assert create_response.status_code == 403


def test_member_day_quota_detail_update_and_cancel_alias_routes(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-alias",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/member-day-quotas",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "user_id": seeded["user_id"],
            "plan_id": seeded["plan_id"],
            "day_no": 6,
            "package_count": 2,
            "day_total_amount": "180.00",
            "tolerance_amount": "5.00",
            "amount_allocation_mode": "average",
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "fixed",
            "product_count_fixed": 1,
            "reward_ratio": "0.18",
            "created_by": "operator-task-quota-alias",
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    detail_response = client.get(f"/api/tasks/member-day-quotas/{created['id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    detailed = detail_response.json()
    assert detailed["id"] == created["id"]
    assert detailed["dayNo"] == 6

    update_response = client.patch(
        f"/api/tasks/member-day-quotas/{created['id']}",
        json={
            "tolerance_amount": "9.00",
            "reward_ratio": "0.22",
            "metadata_json": {"source": "manual-adjust"},
        },
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["toleranceAmount"] == "9.00"
    assert updated["rewardRatio"] == "0.2200"
    assert updated["metadataJson"] == {"source": "manual-adjust"}

    update_audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "member_task_day_quota",
            "target_id": created["id"],
        },
        headers=headers,
    )
    assert update_audit_response.status_code == 200, update_audit_response.text
    update_items = update_audit_response.json()
    updated_matching = [item for item in update_items if item["action"] == "member_task_day_quota_updated"]
    assert len(updated_matching) == 1
    assert updated_matching[0]["payload"]["day_no"] == 6
    assert updated_matching[0]["payload"]["plan_id"] == seeded["plan_id"]

    cancel_response = client.post(
        f"/api/tasks/member-day-quotas/{created['id']}/cancel",
        json={"reason": "operator_cancelled"},
        headers=headers,
    )
    assert cancel_response.status_code == 200, cancel_response.text
    cancelled = cancel_response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["metadataJson"]["cancel_reason"] == "operator_cancelled"

    cancel_audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "member_task_day_quota",
            "target_id": created["id"],
        },
        headers=headers,
    )
    assert cancel_audit_response.status_code == 200, cancel_audit_response.text
    cancel_items = cancel_audit_response.json()
    cancelled_matching = [item for item in cancel_items if item["action"] == "member_task_day_quota_cancelled"]
    assert len(cancelled_matching) == 1
    assert cancelled_matching[0]["payload"]["reason"] == "operator_cancelled"


def test_member_day_quota_batch_create_alias_route(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-batch",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        "/api/tasks/member-day-quotas/batch-create",
        json={
            "items": [
                {
                    "account_id": seeded["account_id"],
                    "site_id": seeded["site_id"],
                    "user_id": seeded["user_id"],
                    "plan_id": seeded["plan_id"],
                    "day_no": 7,
                    "package_count": 2,
                    "day_total_amount": "220.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 1,
                    "reward_ratio": "0.10",
                    "created_by": "operator-task-quota-batch",
                },
                {
                    "account_id": seeded["account_id"],
                    "site_id": seeded["site_id"],
                    "user_id": seeded["user_id"],
                    "plan_id": seeded["plan_id"],
                    "day_no": 8,
                    "package_count": 2,
                    "day_total_amount": "260.00",
                    "tolerance_amount": "6.00",
                    "amount_allocation_mode": "average",
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 2,
                    "reward_ratio": "0.12",
                    "created_by": "operator-task-quota-batch",
                },
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 2
    assert [item["dayNo"] for item in payload] == [7, 8]

    for item in payload:
        audit_response = client.get(
            "/api/runtime/audit-logs",
            params={
                "account_id": seeded["account_id"],
                "target_type": "member_task_day_quota",
                "target_id": item["id"],
            },
            headers=headers,
        )
        assert audit_response.status_code == 200, audit_response.text
        logs = audit_response.json()
        matching = [entry for entry in logs if entry["action"] == "member_task_day_quota_created"]
        assert len(matching) == 1
        assert matching[0]["payload"]["batch_create"] is True


def test_member_day_quota_batch_preview_alias_route(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-batch-preview",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        "/api/tasks/member-day-quotas/batch-preview",
        json={
            "items": [
                {
                    "account_id": seeded["account_id"],
                    "site_id": seeded["site_id"],
                    "user_id": seeded["user_id"],
                    "plan_id": seeded["plan_id"],
                    "day_no": 7,
                    "package_count": 2,
                    "day_total_amount": "220.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 1,
                    "reward_ratio": "0.10",
                    "created_by": "operator-task-quota-batch-preview",
                },
                {
                    "account_id": seeded["account_id"],
                    "site_id": seeded["site_id"],
                    "user_id": seeded["user_id"],
                    "plan_id": seeded["plan_id"],
                    "day_no": 8,
                    "package_count": 2,
                    "day_total_amount": "220.00",
                    "tolerance_amount": "5.00",
                    "amount_allocation_mode": "average",
                    "product_pool_id": seeded["pool_id"],
                    "product_count_mode": "fixed",
                    "product_count_fixed": 1,
                    "reward_ratio": "0.10",
                    "created_by": "operator-task-quota-batch-preview",
                },
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["userCount"] == 2
    assert payload["totalQuotaCount"] == 2
    assert payload["packageAmounts"] == ["110.00", "110.00"]
    assert payload["computedTotalAmount"] == "220.00"
    assert payload["totalBatchAmount"] == "440.00"
    assert payload["rewardRatio"] == "0.10"
    assert payload["productPoolId"] == seeded["pool_id"]


def test_member_day_quota_batch_preview_supports_selector_filters(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-selector-preview",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    with db_session_factory() as session:
        primary_user = session.get(AppUser, seeded["user_id"])
        assert primary_user is not None

        primary_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=primary_user.id,
            member_no="20000011",
            password_hash="selector-preview-primary-hash",
            password_salt="selector-preview-primary-salt",
            current_owner_staff_user_id="staff-a",
        )
        secondary_user = AppUser(
            account_id=seeded["account_id"],
            public_user_id="task-quota-selector-preview-2",
            registration_site_id=seeded["site_id"],
            display_name="Selector Preview User 2",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        tertiary_user = AppUser(
            account_id=seeded["account_id"],
            public_user_id="task-quota-selector-preview-3",
            registration_site_id=seeded["site_id"],
            display_name="Selector Preview User 3",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        session.add_all([primary_profile, secondary_user, tertiary_user])
        session.flush()

        secondary_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=secondary_user.id,
            member_no="20000012",
            password_hash="selector-preview-secondary-hash",
            password_salt="selector-preview-secondary-salt",
            current_owner_staff_user_id="staff-a",
        )
        tertiary_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=tertiary_user.id,
            member_no="20000013",
            password_hash="selector-preview-tertiary-hash",
            password_salt="selector-preview-tertiary-salt",
            current_owner_staff_user_id="staff-b",
        )
        vip_tag = UserTag(tag_key="selector-preview-vip", name="Selector Preview VIP")
        session.add_all([secondary_profile, tertiary_profile, vip_tag])
        session.flush()
        vip_tag_id = vip_tag.id

        session.add(
            TaskSystemConfig(
                account_id=seeded["account_id"],
                site_id=None,
                certified_member_enabled=True,
                certified_recharge_threshold=Decimal("100.00"),
                certified_recharge_scope="real_recharge",
                auto_certify_on_recharge=True,
            )
        )
        session.add(
            MemberVerificationRequest(
                account_id=seeded["account_id"],
                member_profile_id=primary_profile.id,
                request_type="identity",
                status="approved",
                reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
            )
        )
        session.add_all(
            [
                UserTagAssignment(user_id=primary_user.id, tag_id=vip_tag.id, assigned_by="operator"),
                UserTagAssignment(user_id=secondary_user.id, tag_id=vip_tag.id, assigned_by="operator"),
            ]
        )

        wallets = {
            primary_user.id: WalletAccount(account_id=seeded["account_id"], user_id=primary_user.id),
            secondary_user.id: WalletAccount(account_id=seeded["account_id"], user_id=secondary_user.id),
            tertiary_user.id: WalletAccount(account_id=seeded["account_id"], user_id=tertiary_user.id),
        }
        session.add_all(wallets.values())
        session.flush()
        session.add_all(
            [
                WalletLedgerEntry(
                    account_id=seeded["account_id"],
                    wallet_account_id=wallets[primary_user.id].id,
                    user_id=primary_user.id,
                    ledger_type="recharge",
                    transaction_type="recharge",
                    direction="credit",
                    amount=Decimal("150.00"),
                    cash_amount=Decimal("150.00"),
                    status="paid",
                    is_real_recharge=True,
                    reference_type="selector_preview",
                    reference_id="selector-preview-primary",
                ),
                WalletLedgerEntry(
                    account_id=seeded["account_id"],
                    wallet_account_id=wallets[secondary_user.id].id,
                    user_id=secondary_user.id,
                    ledger_type="recharge",
                    transaction_type="recharge",
                    direction="credit",
                    amount=Decimal("40.00"),
                    cash_amount=Decimal("40.00"),
                    status="paid",
                    is_real_recharge=True,
                    reference_type="selector_preview",
                    reference_id="selector-preview-secondary",
                ),
                WalletLedgerEntry(
                    account_id=seeded["account_id"],
                    wallet_account_id=wallets[tertiary_user.id].id,
                    user_id=tertiary_user.id,
                    ledger_type="recharge",
                    transaction_type="recharge",
                    direction="credit",
                    amount=Decimal("180.00"),
                    cash_amount=Decimal("180.00"),
                    status="paid",
                    is_real_recharge=True,
                    reference_type="selector_preview",
                    reference_id="selector-preview-tertiary",
                ),
            ]
        )
        session.commit()

    response = client.post(
        "/api/tasks/member-day-quotas/batch-preview",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "day_no": 9,
            "package_count": 2,
            "day_total_amount": "220.00",
            "tolerance_amount": "5.00",
            "amount_allocation_mode": "average",
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "fixed",
            "product_count_fixed": 1,
            "reward_ratio": "0.10",
            "created_by": "operator-task-quota-selector-preview",
            "owner_staff_user_id": "staff-a",
            "certified_status": "certified",
            "min_total_real_recharge": "100.00",
            "max_total_real_recharge": "200.00",
            "tag_ids": [vip_tag_id],
            "user_ids": [seeded["user_id"], "not-matched-user"],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["userCount"] == 1
    assert payload["totalQuotaCount"] == 1
    assert payload["packageAmounts"] == ["110.00", "110.00"]
    assert payload["computedTotalAmount"] == "220.00"
    assert payload["totalBatchAmount"] == "220.00"


def test_member_day_quota_batch_create_supports_selector_filters(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-selector-create",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    with db_session_factory() as session:
        primary_user = session.get(AppUser, seeded["user_id"])
        assert primary_user is not None
        primary_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=primary_user.id,
            member_no="20000021",
            password_hash="selector-create-primary-hash",
            password_salt="selector-create-primary-salt",
            current_owner_staff_user_id="staff-a",
        )
        secondary_user = AppUser(
            account_id=seeded["account_id"],
            public_user_id="task-quota-selector-create-2",
            registration_site_id=seeded["site_id"],
            display_name="Selector Create User 2",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        session.add_all([primary_profile, secondary_user])
        session.flush()

        secondary_profile = MemberProfile(
            account_id=seeded["account_id"],
            user_id=secondary_user.id,
            member_no="20000022",
            password_hash="selector-create-secondary-hash",
            password_salt="selector-create-secondary-salt",
            current_owner_staff_user_id="staff-a",
        )
        secondary_user_id = secondary_user.id
        vip_tag = UserTag(tag_key="selector-create-vip", name="Selector Create VIP")
        session.add_all([secondary_profile, vip_tag])
        session.flush()
        vip_tag_id = vip_tag.id

        session.add(
            TaskSystemConfig(
                account_id=seeded["account_id"],
                site_id=None,
                certified_member_enabled=True,
                certified_recharge_threshold=Decimal("100.00"),
                certified_recharge_scope="real_recharge",
                auto_certify_on_recharge=True,
            )
        )
        session.add(
            MemberVerificationRequest(
                account_id=seeded["account_id"],
                member_profile_id=primary_profile.id,
                request_type="identity",
                status="approved",
                reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
            )
        )
        session.add_all(
            [
                UserTagAssignment(user_id=primary_user.id, tag_id=vip_tag.id, assigned_by="operator"),
                UserTagAssignment(user_id=secondary_user.id, tag_id=vip_tag.id, assigned_by="operator"),
            ]
        )

        wallets = {
            primary_user.id: WalletAccount(account_id=seeded["account_id"], user_id=primary_user.id),
            secondary_user.id: WalletAccount(account_id=seeded["account_id"], user_id=secondary_user.id),
        }
        session.add_all(wallets.values())
        session.flush()
        session.add_all(
            [
                WalletLedgerEntry(
                    account_id=seeded["account_id"],
                    wallet_account_id=wallets[primary_user.id].id,
                    user_id=primary_user.id,
                    ledger_type="recharge",
                    transaction_type="recharge",
                    direction="credit",
                    amount=Decimal("150.00"),
                    cash_amount=Decimal("150.00"),
                    status="paid",
                    is_real_recharge=True,
                    reference_type="selector_create",
                    reference_id="selector-create-primary",
                ),
                WalletLedgerEntry(
                    account_id=seeded["account_id"],
                    wallet_account_id=wallets[secondary_user.id].id,
                    user_id=secondary_user.id,
                    ledger_type="recharge",
                    transaction_type="recharge",
                    direction="credit",
                    amount=Decimal("40.00"),
                    cash_amount=Decimal("40.00"),
                    status="paid",
                    is_real_recharge=True,
                    reference_type="selector_create",
                    reference_id="selector-create-secondary",
                ),
            ]
        )
        session.commit()

    response = client.post(
        "/api/tasks/member-day-quotas/batch-create",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "day_no": 10,
            "package_count": 2,
            "day_total_amount": "220.00",
            "tolerance_amount": "5.00",
            "amount_allocation_mode": "average",
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "fixed",
            "product_count_fixed": 1,
            "reward_ratio": "0.10",
            "created_by": "operator-task-quota-selector-create",
            "owner_staff_user_id": "staff-a",
            "certified_status": "uncertified",
            "max_total_real_recharge": "99.99",
                "tag_ids": [vip_tag_id],
                "user_ids": [seeded["user_id"], secondary_user_id],
            },
            headers=headers,
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["userId"] == secondary_user_id
    assert payload[0]["dayNo"] == 10
    assert payload[0]["packageAmountsJson"] == ["110.00", "110.00"]


def test_generate_task_batch_for_quota_writes_member_task_batch_generated_audit_log(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-generate",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    with db_session_factory() as session:
        session.add_all(
            [
                TaskProductPoolItem(
                    account_id=seeded["account_id"],
                    pool_id=seeded["pool_id"],
                    product_id="quota-generate-product-1",
                    product_name="Quota Generate Product 1",
                    image_url="https://example.com/quota-generate-1.png",
                    price=Decimal("50.00"),
                    currency="USD",
                    product_description="Quota Generate Product 1",
                    status="active",
                    sort_order=1,
                ),
                TaskProductPoolItem(
                    account_id=seeded["account_id"],
                    pool_id=seeded["pool_id"],
                    product_id="quota-generate-product-2",
                    product_name="Quota Generate Product 2",
                    image_url="https://example.com/quota-generate-2.png",
                    price=Decimal("50.00"),
                    currency="USD",
                    product_description="Quota Generate Product 2",
                    status="active",
                    sort_order=2,
                ),
            ]
        )
        session.commit()

    create_response = client.post(
        "/api/tasks/member-day-quotas",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "user_id": seeded["user_id"],
            "plan_id": seeded["plan_id"],
            "day_no": 11,
            "package_count": 1,
            "day_total_amount": "100.00",
            "tolerance_amount": "5.00",
            "amount_allocation_mode": "manual",
            "package_amounts": ["100.00"],
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "fixed",
            "product_count_fixed": 2,
            "reward_ratio": "0.10",
            "created_by": "operator-task-quota-generate",
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    quota_id = create_response.json()["id"]

    generate_response = client.post(
        f"/api/tasks/member-day-quotas/{quota_id}/generate-batch",
        headers=headers,
    )
    assert generate_response.status_code == 200, generate_response.text
    generated = generate_response.json()
    assert generated["quotaId"] == quota_id
    assert generated["status"] == "success"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "member_task_day_quota",
            "target_id": quota_id,
        },
        headers=headers,
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "member_task_batch_generated"]
    assert len(matching) == 1
    assert matching[0]["payload"]["run_id"] == generated["id"]


def test_retry_generation_run_writes_task_generation_run_retried_audit_log(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_quota_api_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-quota-retry-run",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    create_response = client.post(
        "/api/tasks/member-day-quotas",
        json={
            "account_id": seeded["account_id"],
            "site_id": seeded["site_id"],
            "user_id": seeded["user_id"],
            "plan_id": seeded["plan_id"],
            "day_no": 12,
            "package_count": 1,
            "day_total_amount": "100.00",
            "tolerance_amount": "5.00",
            "amount_allocation_mode": "manual",
            "package_amounts": ["100.00"],
            "product_pool_id": seeded["pool_id"],
            "product_count_mode": "fixed",
            "product_count_fixed": 2,
            "reward_ratio": "0.10",
            "created_by": "operator-task-quota-retry-run",
        },
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    quota_id = create_response.json()["id"]

    failed_generate_response = client.post(
        f"/api/tasks/member-day-quotas/{quota_id}/generate-batch",
        headers=headers,
    )
    assert failed_generate_response.status_code == 409, failed_generate_response.text

    with db_session_factory() as session:
        failed_run = session.query(TaskProductGenerationRun).filter(
            TaskProductGenerationRun.quota_id == quota_id,
            TaskProductGenerationRun.status == "failed",
        ).one()
        failed_run_id = failed_run.id
        session.add_all(
            [
                TaskProductPoolItem(
                    account_id=seeded["account_id"],
                    pool_id=seeded["pool_id"],
                    product_id="quota-retry-product-1",
                    product_name="Quota Retry Product 1",
                    image_url="https://example.com/quota-retry-1.png",
                    price=Decimal("50.00"),
                    currency="USD",
                    product_description="Quota Retry Product 1",
                    status="active",
                    sort_order=1,
                ),
                TaskProductPoolItem(
                    account_id=seeded["account_id"],
                    pool_id=seeded["pool_id"],
                    product_id="quota-retry-product-2",
                    product_name="Quota Retry Product 2",
                    image_url="https://example.com/quota-retry-2.png",
                    price=Decimal("50.00"),
                    currency="USD",
                    product_description="Quota Retry Product 2",
                    status="active",
                    sort_order=2,
                ),
            ]
        )
        session.commit()

    retry_response = client.post(
        f"/api/tasks/generation-runs/{failed_run_id}/retry",
        headers=headers,
    )
    assert retry_response.status_code == 200, retry_response.text
    retried = retry_response.json()
    assert retried["quotaId"] == quota_id
    assert retried["status"] == "success"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": seeded["account_id"],
            "target_type": "task_product_generation_run",
            "target_id": failed_run_id,
        },
        headers=headers,
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "task_generation_run_retried"]
    assert len(matching) == 1
    assert matching[0]["payload"]["result_run_id"] == retried["id"]

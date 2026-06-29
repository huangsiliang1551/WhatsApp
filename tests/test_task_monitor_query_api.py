from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, TaskPackageInstance, WalletAccount, WalletLedgerEntry, WithdrawalRequest, utc_now
from tests.test_h5_member_auth import _operator_headers
from tests.test_task_manual_add_service import _seed_manual_add_scope


def _seed_task_monitor_query_scope(
    db_session_factory: sessionmaker[Session],
    *,
    suffix: str = "",
) -> dict[str, str]:
    seeded = _seed_manual_add_scope(db_session_factory, suffix=suffix)

    with db_session_factory() as session:
        package = session.get(TaskPackageInstance, seeded["package_id"])
        assert package is not None
        user = session.get(AppUser, package.user_id)
        assert user is not None

        wallet = WalletAccount(
            account_id=package.account_id,
            user_id=package.user_id,
            system_balance=Decimal("120.00"),
            system_cash_balance=Decimal("120.00"),
            system_bonus_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            system_cash_frozen=Decimal("0.00"),
            system_bonus_frozen=Decimal("0.00"),
            task_balance=Decimal("0.00"),
            currency="USD",
            withdraw_threshold=Decimal("100.00"),
        )
        session.add(wallet)
        session.flush()

        session.add(
            WalletLedgerEntry(
                account_id=package.account_id,
                wallet_account_id=wallet.id,
                user_id=package.user_id,
                ledger_type="recharge",
                transaction_type="manual_recharge",
                direction="credit",
                amount=Decimal("120.00"),
                currency="USD",
                status="paid",
                source_type="manual_real_recharge",
                fund_type="cash",
                cash_amount=Decimal("120.00"),
                bonus_amount=Decimal("0.00"),
                task_amount=Decimal("0.00"),
                balance_before=Decimal("0.00"),
                balance_after=Decimal("120.00"),
                cash_balance_before=Decimal("0.00"),
                cash_balance_after=Decimal("120.00"),
                bonus_balance_before=Decimal("0.00"),
                bonus_balance_after=Decimal("0.00"),
                task_balance_before=Decimal("0.00"),
                task_balance_after=Decimal("0.00"),
                operator_id="staff-task-monitor-query",
                operator_type="operator",
                idempotency_key=f"task-monitor-query-recharge{suffix}",
                display_category="recharge",
                display_title="Recharge",
                is_bonus=False,
                is_real_recharge=True,
            )
        )

        session.add(
            WithdrawalRequest(
                account_id=package.account_id,
                wallet_account_id=wallet.id,
                user_id=package.user_id,
                request_no=f"WD-TASK-MONITOR{suffix or '-1'}",
                amount=Decimal("30.00"),
                cash_amount=Decimal("30.00"),
                bonus_amount=Decimal("0.00"),
                actual_payout_amount=Decimal("30.00"),
                withdraw_account_type="bank",
                currency="USD",
                status="paid",
                reviewed_at=utc_now(),
                paid_at=utc_now(),
            )
        )
        session.commit()

        return {
            "account_id": package.account_id,
            "package_id": package.id,
            "user_id": package.user_id,
            "public_user_id": user.public_user_id,
            "pool_item_3_id": seeded["pool_item_3_id"],
            "pool_item_4_id": seeded["pool_item_4_id"],
        }


def test_task_monitor_query_filters_and_enriches_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory)

    client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor query setup",
        },
    )
    response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "planned_amount_min": "45",
            "manual_added_amount_min": "80",
            "effective_amount_min": "130",
            "has_manual_add": "true",
            "current_product_amount_min": "25",
            "total_recharge_amount_min": "100",
            "total_withdraw_amount_min": "20",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["packageId"] == seeded["package_id"]
    assert payload[0]["publicUserId"] == seeded["public_user_id"]
    assert payload[0]["manualAddedAmount"] == 90.0
    assert payload[0]["effectiveAmount"] == 140.0
    assert payload[0]["dayPlannedAmount"] == 50.0
    assert payload[0]["daySystemGeneratedAmount"] == 50.0
    assert payload[0]["dayManualAddedAmount"] == 90.0
    assert payload[0]["dayEffectiveAmount"] == 140.0
    assert payload[0]["currentItemIndex"] == 2
    assert payload[0]["currentProductAmount"] == 30.0
    assert payload[0]["currentProductOrigin"] == "system_generated"
    assert payload[0]["totalRealRechargeAmount"] == 120.0
    assert payload[0]["totalWithdrawAmount"] == 30.0


def test_task_monitor_summary_returns_aggregates_for_filtered_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-summary")

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor summary setup",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.get(
        "/api/tasks/monitor/summary",
        params={
            "account_id": seeded["account_id"],
            "manual_added_amount_min": "80",
            "has_manual_add": "true",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totalCount"] == 1
    assert payload["manualAddCount"] == 1
    assert payload["totalPlannedAmount"] == 50.0
    assert payload["totalManualAddedAmount"] == 90.0
    assert payload["totalEffectiveAmount"] == 140.0
    assert payload["totalRealRechargeAmount"] == 120.0
    assert payload["totalWithdrawAmount"] == 30.0


def test_task_monitor_query_supports_day_amount_filters(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-day-amounts")

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor day amount setup",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "day_planned_amount_min": "40",
            "day_manual_added_amount_min": "80",
            "day_effective_amount_min": "130",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["packageId"] == seeded["package_id"]

    empty_response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "day_effective_amount_min": "200",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert empty_response.status_code == 200, empty_response.text
    assert empty_response.json() == []


def test_task_monitor_query_supports_user_query_for_public_user_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-user-query")

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"]],
            "reason_text": "task monitor user query setup",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "user_query": seeded["public_user_id"],
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["packageId"] == seeded["package_id"]

    empty_response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "user_query": "pub-missing",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert empty_response.status_code == 200, empty_response.text
    assert empty_response.json() == []


def test_task_monitor_query_includes_latest_manual_add_metadata_and_supports_operator_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_monitor_query_scope(db_session_factory, suffix="-manual-meta")

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers(seeded["account_id"]),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "task monitor manual metadata setup",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "latest_manual_add_operator_id": "operator-h5-member-auth",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["packageId"] == seeded["package_id"]
    assert payload[0]["manualAddedItemCount"] == 2
    assert payload[0]["latestManualAddOperatorId"] == "operator-h5-member-auth"
    assert payload[0]["latestManualAddAt"] is not None

    empty_response = client.get(
        "/api/tasks/monitor/query",
        params={
            "account_id": seeded["account_id"],
            "latest_manual_add_operator_id": "operator-missing",
        },
        headers=_operator_headers(seeded["account_id"]),
    )
    assert empty_response.status_code == 200, empty_response.text
    assert empty_response.json() == []

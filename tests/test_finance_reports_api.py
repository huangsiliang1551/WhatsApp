from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, PaymentCallback, WalletAccount, WithdrawalRequest, WithdrawalSetting
from app.services.bonus_grant_service import BonusGrantService
from app.services.recharge_repair_service import RechargeRepairService
from app.services.wallet_ledger_service import WalletLedgerService
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _super_admin_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-finance-reports",
        "X-Actor-Role": "super_admin",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def _finance_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "finance-actor-finance-reports",
        "X-Actor-Role": "finance",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_finance_recharge_and_withdrawal_lists_use_wallet_split_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-api", site_key="finance-api")
    auth_payload = _register_member(
        client,
        site_key="finance-api",
        phone="+8613900087301",
        display_name="Finance API Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-api",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("100"),
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("200"),
            currency=wallet.currency,
            transaction_type="bonus_grant",
            source_type="admin_bonus",
            note="Bonus credited",
            reference_type=None,
            reference_id=None,
            fund_type="bonus",
            is_bonus=True,
        )
        session.commit()

    withdrawal_response = client.post("/api/h5/withdrawals", json={"amount": 250})
    assert withdrawal_response.status_code == 200, withdrawal_response.text
    withdrawal_id = withdrawal_response.json()["id"]
    paid_response = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approved."},
        headers=_super_admin_headers("acct-finance-api"),
    )
    assert paid_response.status_code == 200, paid_response.text
    paid_response = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Paid."},
        headers=_super_admin_headers("acct-finance-api"),
    )
    assert paid_response.status_code == 200, paid_response.text

    recharge_list = client.get(
        "/api/finance/recharge-records",
        headers=_super_admin_headers("acct-finance-api"),
        params={"agency_id": "acct-finance-api"},
    )
    assert recharge_list.status_code == 200, recharge_list.text
    recharge_items = recharge_list.json()
    assert {item["source_type"] for item in recharge_items} == {"manual_real_recharge", "admin_bonus"}
    bonus_row = next(item for item in recharge_items if item["source_type"] == "admin_bonus")
    cash_row = next(item for item in recharge_items if item["source_type"] == "manual_real_recharge")
    assert bonus_row["public_user_id"] == auth_payload["member"]["publicUserId"]
    assert cash_row["public_user_id"] == auth_payload["member"]["publicUserId"]
    assert bonus_row["bonus_amount"] == 200.0
    assert bonus_row["cash_amount"] == 0.0
    assert cash_row["cash_amount"] == 100.0
    assert cash_row["is_real_recharge"] is True

    withdrawal_list = client.get(
        "/api/finance/withdrawal-records",
        headers=_super_admin_headers("acct-finance-api"),
        params={"agency_id": "acct-finance-api"},
    )
    assert withdrawal_list.status_code == 200, withdrawal_list.text
    withdrawal_items = withdrawal_list.json()
    assert len(withdrawal_items) == 1
    assert withdrawal_items[0]["public_user_id"] == auth_payload["member"]["publicUserId"]
    assert withdrawal_items[0]["cash_amount"] == 100.0
    assert withdrawal_items[0]["bonus_amount"] == 150.0
    assert withdrawal_items[0]["amount"] == 250.0


def test_finance_summary_supports_excluding_bonus_via_query_flag(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-summary-api", site_key="finance-summary-api")
    auth_payload = _register_member(
        client,
        site_key="finance-summary-api",
        phone="+8613900087302",
        display_name="Finance Summary API Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-summary-api",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("100"),
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("200"),
            currency=wallet.currency,
            transaction_type="bonus_grant",
            source_type="admin_bonus",
            note="Bonus credited",
            reference_type=None,
            reference_id=None,
            fund_type="bonus",
            is_bonus=True,
        )
        session.commit()

    withdrawal_response = client.post("/api/h5/withdrawals", json={"amount": 250})
    assert withdrawal_response.status_code == 200, withdrawal_response.text
    withdrawal_id = withdrawal_response.json()["id"]
    client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approved."},
        headers=_super_admin_headers("acct-finance-summary-api"),
    )
    client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Paid."},
        headers=_super_admin_headers("acct-finance-summary-api"),
    )

    full_summary = client.get(
        "/api/finance/report/summary",
        headers=_super_admin_headers("acct-finance-summary-api"),
        params={"agency_id": "acct-finance-summary-api"},
    )
    assert full_summary.status_code == 200, full_summary.text
    assert full_summary.json()["bonus_amount"] == 200.0
    assert full_summary.json()["withdrawal_bonus_amount"] == 150.0

    cash_only_summary = client.get(
        "/api/finance/report/summary",
        headers=_super_admin_headers("acct-finance-summary-api"),
        params={"agency_id": "acct-finance-summary-api", "include_bonus": "false"},
    )
    assert cash_only_summary.status_code == 200, cash_only_summary.text
    payload = cash_only_summary.json()
    assert payload["recharge_amount"] == 100.0
    assert payload["bonus_amount"] == 0.0
    assert payload["withdrawal_amount"] == 100.0
    assert payload["withdrawal_cash_amount"] == 100.0
    assert payload["withdrawal_bonus_amount"] == 0.0
    assert payload["net_recharge"] == 0.0


def test_finance_wallet_ledger_list_uses_real_wallet_entries(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-ledger-api", site_key="finance-ledger-api")
    auth_payload = _register_member(
        client,
        site_key="finance-ledger-api",
        phone="+8613900087303",
        display_name="Finance Ledger API Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-ledger-api",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("100"),
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Manual recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("200"),
            currency=wallet.currency,
            transaction_type="bonus_grant",
            source_type="admin_bonus",
            note="Bonus credited",
            reference_type=None,
            reference_id=None,
            fund_type="bonus",
            is_bonus=True,
        )
        session.commit()

    withdrawal_response = client.post("/api/h5/withdrawals", json={"amount": 50})
    assert withdrawal_response.status_code == 200, withdrawal_response.text

    ledger_list = client.get(
        "/api/finance/wallet-ledgers",
        headers=_super_admin_headers("acct-finance-ledger-api"),
        params={"agency_id": "acct-finance-ledger-api"},
    )
    assert ledger_list.status_code == 200, ledger_list.text
    items = ledger_list.json()
    assert len(items) == 3

    bonus_entry = next(item for item in items if item["transaction_type"] == "bonus_grant")
    recharge_entry = next(item for item in items if item["transaction_type"] == "manual_recharge")
    withdrawal_entry = next(item for item in items if item["transaction_type"] == "withdraw_request")
    assert bonus_entry["public_user_id"] == auth_payload["member"]["publicUserId"]
    assert recharge_entry["public_user_id"] == auth_payload["member"]["publicUserId"]
    assert withdrawal_entry["public_user_id"] == auth_payload["member"]["publicUserId"]

    assert bonus_entry["direction"] == "credit"
    assert bonus_entry["bonus_amount"] == 200.0
    assert bonus_entry["cash_amount"] == 0.0
    assert bonus_entry["display_title"] == "Bonus credited"
    assert bonus_entry["balance_after"] == 300.0

    assert recharge_entry["cash_amount"] == 100.0
    assert recharge_entry["display_category"] == "wallet_credit"

    assert withdrawal_entry["direction"] == "debit"
    assert withdrawal_entry["cash_amount"] == 50.0
    assert withdrawal_entry["status"] == "submitted"


def test_finance_anomaly_alerts_include_account_scope_for_member_navigation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-alert-api", site_key="finance-alert-api")
    auth_payload = _register_member(
        client,
        site_key="finance-alert-api",
        phone="+8613900087304",
        display_name="Finance Alert API Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-alert-api",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("12000"),
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Large recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    alerts_response = client.get(
        "/api/finance/anomaly-alerts",
        headers=_super_admin_headers("acct-finance-alert-api"),
    )
    assert alerts_response.status_code == 200, alerts_response.text
    alerts = alerts_response.json()
    large_recharge_alert = next(item for item in alerts if item["type"] == "large_recharge")
    assert large_recharge_alert["account_id"] == "acct-finance-alert-api"
    assert large_recharge_alert["public_user_id"] == auth_payload["member"]["publicUserId"]


def test_finance_withdrawal_records_include_duplicate_account_risk_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-withdraw-risk", site_key="finance-withdraw-risk")
    first_auth = _register_member(
        client,
        site_key="finance-withdraw-risk",
        phone="+8613900087391",
        display_name="Finance Withdraw Risk A",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-withdraw-risk",
        site_id=site["id"],
        public_user_id=first_auth["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )
    first_response = client.post(
        "/api/h5/withdrawals",
        json={
            "amount": 100,
            "withdraw_account_type": "bank",
            "bank_name": "ICBC",
            "account_no": "6222020000007788",
        },
    )
    assert first_response.status_code == 200, first_response.text

    second_auth = _register_member(
        client,
        site_key="finance-withdraw-risk",
        phone="+8613900087392",
        display_name="Finance Withdraw Risk B",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-withdraw-risk",
        site_id=site["id"],
        public_user_id=second_auth["member"]["publicUserId"],
        system_balance=Decimal("300"),
        task_balance=Decimal("0"),
    )
    second_response = client.post(
        "/api/h5/withdrawals",
        json={
            "amount": 120,
            "withdraw_account_type": "bank",
            "bank_name": "ICBC",
            "account_no": "6222020000007788",
        },
    )
    assert second_response.status_code == 200, second_response.text

    withdrawal_list = client.get(
        "/api/finance/withdrawal-records",
        headers=_super_admin_headers("acct-finance-withdraw-risk"),
        params={"agency_id": "acct-finance-withdraw-risk"},
    )
    assert withdrawal_list.status_code == 200, withdrawal_list.text
    items = withdrawal_list.json()
    risky_row = next(item for item in items if item["public_user_id"] == second_auth["member"]["publicUserId"])
    assert risky_row["account_no_masked"] == "************7788"
    assert risky_row["withdraw_account_type"] == "bank"
    assert risky_row["duplicate_account_count"] == 1
    assert risky_row["duplicate_member_ids"] == [first_auth["member"]["publicUserId"]]
    assert risky_row["risk_level"] == "low"
    assert risky_row["risk_flags"] == ["duplicate_withdraw_account"]


def test_finance_report_endpoints_do_not_allow_cross_account_scope_for_non_super_admin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    own_site = _create_site(client, account_id="acct-finance-scope-own", site_key="finance-scope-own")
    own_auth = _register_member(
        client,
        site_key="finance-scope-own",
        phone="+8613900087393",
        display_name="Finance Scope Own",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-scope-own",
        site_id=own_site["id"],
        public_user_id=own_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    foreign_site = _create_site(client, account_id="acct-finance-scope-foreign", site_key="finance-scope-foreign")
    foreign_auth = _register_member(
        client,
        site_key="finance-scope-foreign",
        phone="+8613900087394",
        display_name="Finance Scope Foreign",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-scope-foreign",
        site_id=foreign_site["id"],
        public_user_id=foreign_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        own_user = session.query(AppUser).filter(AppUser.public_user_id == own_auth["member"]["publicUserId"]).one()
        own_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == own_user.id).one()
        foreign_user = session.query(AppUser).filter(AppUser.public_user_id == foreign_auth["member"]["publicUserId"]).one()
        foreign_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == foreign_user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=own_wallet,
            account_id=own_user.account_id,
            user_id=own_user.id,
            amount=Decimal("100"),
            currency=own_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Own recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=foreign_wallet,
            account_id=foreign_user.account_id,
            user_id=foreign_user.id,
            amount=Decimal("200"),
            currency=foreign_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Foreign recharge credited",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    own_withdrawal_response = client.post("/api/h5/withdrawals", json={"amount": 50})
    assert own_withdrawal_response.status_code == 200, own_withdrawal_response.text
    own_withdrawal_id = own_withdrawal_response.json()["id"]
    client.post(
        f"/api/platform/withdrawals/{own_withdrawal_id}/status",
        json={"status": "approved", "note": "Approved."},
        headers=_super_admin_headers("acct-finance-scope-own"),
    )
    client.post(
        f"/api/platform/withdrawals/{own_withdrawal_id}/status",
        json={"status": "paid", "note": "Paid."},
        headers=_super_admin_headers("acct-finance-scope-own"),
    )

    foreign_withdrawal_response = client.post("/api/h5/withdrawals", json={"amount": 80})
    assert foreign_withdrawal_response.status_code == 200, foreign_withdrawal_response.text
    foreign_withdrawal_id = foreign_withdrawal_response.json()["id"]
    client.post(
        f"/api/platform/withdrawals/{foreign_withdrawal_id}/status",
        json={"status": "approved", "note": "Approved."},
        headers=_super_admin_headers("acct-finance-scope-foreign"),
    )
    client.post(
        f"/api/platform/withdrawals/{foreign_withdrawal_id}/status",
        json={"status": "paid", "note": "Paid."},
        headers=_super_admin_headers("acct-finance-scope-foreign"),
    )

    forbidden_summary = client.get(
        "/api/finance/report/summary",
        headers=_finance_headers("acct-finance-scope-own"),
        params={"agency_id": "acct-finance-scope-foreign"},
    )
    assert forbidden_summary.status_code == 403, forbidden_summary.text

    scoped_summary = client.get(
        "/api/finance/report/summary",
        headers=_finance_headers("acct-finance-scope-own"),
    )
    assert scoped_summary.status_code == 200, scoped_summary.text
    summary_payload = scoped_summary.json()
    assert summary_payload["recharge_amount"] == 100.0

    forbidden_recharge_report = client.get(
        "/api/finance/report/recharge",
        headers=_finance_headers("acct-finance-scope-own"),
        params={"agency_id": "acct-finance-scope-foreign"},
    )
    assert forbidden_recharge_report.status_code == 403, forbidden_recharge_report.text

    scoped_recharge_report = client.get(
        "/api/finance/report/recharge",
        headers=_finance_headers("acct-finance-scope-own"),
    )
    assert scoped_recharge_report.status_code == 200, scoped_recharge_report.text
    recharge_items = scoped_recharge_report.json()
    assert len(recharge_items) == 1
    assert recharge_items[0]["account_id"] == "acct-finance-scope-own"
    assert recharge_items[0]["public_user_id"] == own_auth["member"]["publicUserId"]

    forbidden_withdrawal_report = client.get(
        "/api/finance/report/withdrawal",
        headers=_finance_headers("acct-finance-scope-own"),
        params={"agency_id": "acct-finance-scope-foreign"},
    )
    assert forbidden_withdrawal_report.status_code == 403, forbidden_withdrawal_report.text

    scoped_withdrawal_report = client.get(
        "/api/finance/report/withdrawal",
        headers=_finance_headers("acct-finance-scope-own"),
    )
    assert scoped_withdrawal_report.status_code == 200, scoped_withdrawal_report.text


def test_finance_withdrawal_settings_require_account_scope_for_non_super_admin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        session.add_all(
            [
                WithdrawalSetting(
                    agency_id="acct-finance-settings-own",
                    min_withdraw_amount=Decimal("10"),
                ),
                WithdrawalSetting(
                    agency_id="acct-finance-settings-foreign",
                    min_withdraw_amount=Decimal("20"),
                ),
            ]
        )
        session.commit()

    allowed_response = client.get(
        "/api/finance/withdrawal-settings/acct-finance-settings-own",
        headers=_finance_headers("acct-finance-settings-own"),
    )
    assert allowed_response.status_code == 200, allowed_response.text
    assert allowed_response.json()["agency_id"] == "acct-finance-settings-own"

    forbidden_get = client.get(
        "/api/finance/withdrawal-settings/acct-finance-settings-foreign",
        headers=_finance_headers("acct-finance-settings-own"),
    )
    assert forbidden_get.status_code == 403, forbidden_get.text

    forbidden_put = client.put(
        "/api/finance/withdrawal-settings/acct-finance-settings-foreign",
        headers=_finance_headers("acct-finance-settings-own"),
        json={"min_withdraw_amount": 88},
    )
    assert forbidden_put.status_code == 403, forbidden_put.text


def test_finance_anomaly_alerts_hide_callback_failures_from_non_super_admin_without_account_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        session.add(
            PaymentCallback(
                channel_id="channel-alert-1",
                raw_payload={"kind": "signature_failure"},
                signature_valid=False,
            )
        )
        session.commit()

    finance_actor_response = client.get(
        "/api/finance/anomaly-alerts",
        headers=_finance_headers("acct-finance-alert-scope-own"),
    )
    assert finance_actor_response.status_code == 200, finance_actor_response.text
    assert all(item["type"] != "callback_failure" for item in finance_actor_response.json())

    super_admin_response = client.get(
        "/api/finance/anomaly-alerts",
        headers=_super_admin_headers("acct-finance-alert-scope-own"),
    )
    assert super_admin_response.status_code == 200, super_admin_response.text
    assert any(item["type"] == "callback_failure" for item in super_admin_response.json())


def test_finance_anomaly_alerts_do_not_fall_back_to_global_scope_for_multi_account_non_super_admin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    own_site = _create_site(client, account_id="acct-finance-alert-own", site_key="finance-alert-own")
    own_auth = _register_member(
        client,
        site_key="finance-alert-own",
        phone="+8613900087395",
        display_name="Finance Alert Own",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-alert-own",
        site_id=own_site["id"],
        public_user_id=own_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    foreign_site = _create_site(client, account_id="acct-finance-alert-foreign", site_key="finance-alert-foreign")
    foreign_auth = _register_member(
        client,
        site_key="finance-alert-foreign",
        phone="+8613900087396",
        display_name="Finance Alert Foreign",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-alert-foreign",
        site_id=foreign_site["id"],
        public_user_id=foreign_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        own_user = session.query(AppUser).filter(AppUser.public_user_id == own_auth["member"]["publicUserId"]).one()
        own_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == own_user.id).one()
        foreign_user = session.query(AppUser).filter(AppUser.public_user_id == foreign_auth["member"]["publicUserId"]).one()
        foreign_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == foreign_user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=own_wallet,
            account_id=own_user.account_id,
            user_id=own_user.id,
            amount=Decimal("12000"),
            currency=own_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Own large recharge",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=foreign_wallet,
            account_id=foreign_user.account_id,
            user_id=foreign_user.id,
            amount=Decimal("13000"),
            currency=foreign_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Foreign large recharge",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    response = client.get(
        "/api/finance/anomaly-alerts",
        headers=_finance_headers("acct-finance-alert-own", "acct-finance-alert-foreign"),
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_finance_bonus_grants_do_not_fall_back_to_multi_account_union_for_non_super_admin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    own_site = _create_site(client, account_id="acct-finance-grant-own", site_key="finance-grant-own")
    own_auth = _register_member(
        client,
        site_key="finance-grant-own",
        phone="+8613900087397",
        display_name="Finance Grant Own",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-grant-own",
        site_id=own_site["id"],
        public_user_id=own_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    foreign_site = _create_site(client, account_id="acct-finance-grant-foreign", site_key="finance-grant-foreign")
    foreign_auth = _register_member(
        client,
        site_key="finance-grant-foreign",
        phone="+8613900087398",
        display_name="Finance Grant Foreign",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-grant-foreign",
        site_id=foreign_site["id"],
        public_user_id=foreign_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        own_user = session.query(AppUser).filter(AppUser.public_user_id == own_auth["member"]["publicUserId"]).one()
        foreign_user = session.query(AppUser).filter(AppUser.public_user_id == foreign_auth["member"]["publicUserId"]).one()
        svc = BonusGrantService(session)
        svc.create_grant(
            account_id="acct-finance-grant-own",
            user_id=own_user.id,
            amount=Decimal("12"),
            currency="USD",
            reason="Own grant",
            remark=None,
            source_type="admin_bonus",
            operator_id="seed-admin",
        )
        svc.create_grant(
            account_id="acct-finance-grant-foreign",
            user_id=foreign_user.id,
            amount=Decimal("34"),
            currency="USD",
            reason="Foreign grant",
            remark=None,
            source_type="admin_bonus",
            operator_id="seed-admin",
        )

    response = client.get(
        "/api/finance/bonus-grants",
        headers=_finance_headers("acct-finance-grant-own", "acct-finance-grant-foreign"),
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_finance_recharge_repairs_do_not_fall_back_to_multi_account_union_for_non_super_admin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    own_site = _create_site(client, account_id="acct-finance-repair-own", site_key="finance-repair-own")
    own_auth = _register_member(
        client,
        site_key="finance-repair-own",
        phone="+8613900087399",
        display_name="Finance Repair Own",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-repair-own",
        site_id=own_site["id"],
        public_user_id=own_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    foreign_site = _create_site(client, account_id="acct-finance-repair-foreign", site_key="finance-repair-foreign")
    foreign_auth = _register_member(
        client,
        site_key="finance-repair-foreign",
        phone="+8613900087400",
        display_name="Finance Repair Foreign",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-repair-foreign",
        site_id=foreign_site["id"],
        public_user_id=foreign_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        own_user = session.query(AppUser).filter(AppUser.public_user_id == own_auth["member"]["publicUserId"]).one()
        foreign_user = session.query(AppUser).filter(AppUser.public_user_id == foreign_auth["member"]["publicUserId"]).one()
        svc = RechargeRepairService(session)
        svc.create_repair(
            account_id="acct-finance-repair-own",
            user_id=own_user.id,
            amount=Decimal("56"),
            currency="USD",
            repair_type="callback_missing",
            reason="Own repair",
            remark=None,
            channel_id=None,
            platform_order_no="PO-own",
            channel_order_no="CO-own",
            operator_id="seed-admin",
        )
        svc.create_repair(
            account_id="acct-finance-repair-foreign",
            user_id=foreign_user.id,
            amount=Decimal("78"),
            currency="USD",
            repair_type="callback_missing",
            reason="Foreign repair",
            remark=None,
            channel_id=None,
            platform_order_no="PO-foreign",
            channel_order_no="CO-foreign",
            operator_id="seed-admin",
        )

    response = client.get(
        "/api/finance/recharge-repairs",
        headers=_finance_headers("acct-finance-repair-own", "acct-finance-repair-foreign"),
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_finance_recharge_and_withdrawal_lists_honor_site_id_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    primary_site = _create_site(client, account_id="acct-finance-site-filter", site_key="finance-site-filter-a")
    primary_auth = _register_member(
        client,
        site_key="finance-site-filter-a",
        phone="+8613900087401",
        display_name="Finance Site Filter A",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-site-filter",
        site_id=primary_site["id"],
        public_user_id=primary_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    secondary_site = _create_site(client, account_id="acct-finance-site-filter", site_key="finance-site-filter-b")
    secondary_auth = _register_member(
        client,
        site_key="finance-site-filter-b",
        phone="+8613900087402",
        display_name="Finance Site Filter B",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-site-filter",
        site_id=secondary_site["id"],
        public_user_id=secondary_auth["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        primary_user = session.query(AppUser).filter(
            AppUser.public_user_id == primary_auth["member"]["publicUserId"]
        ).one()
        secondary_user = session.query(AppUser).filter(
            AppUser.public_user_id == secondary_auth["member"]["publicUserId"]
        ).one()
        primary_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == primary_user.id).one()
        secondary_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == secondary_user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=primary_wallet,
            account_id=primary_user.account_id,
            user_id=primary_user.id,
            amount=Decimal("110"),
            currency=primary_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Primary site recharge",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        wallet_service.credit_system_balance(
            wallet=secondary_wallet,
            account_id=secondary_user.account_id,
            user_id=secondary_user.id,
            amount=Decimal("220"),
            currency=secondary_wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Secondary site recharge",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    with db_session_factory() as session:
        primary_user = session.query(AppUser).filter(
            AppUser.public_user_id == primary_auth["member"]["publicUserId"]
        ).one()
        secondary_user = session.query(AppUser).filter(
            AppUser.public_user_id == secondary_auth["member"]["publicUserId"]
        ).one()
        primary_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == primary_user.id).one()
        secondary_wallet = session.query(WalletAccount).filter(WalletAccount.user_id == secondary_user.id).one()
        session.add(
            WithdrawalRequest(
                account_id="acct-finance-site-filter",
                wallet_account_id=primary_wallet.id,
                user_id=primary_user.id,
                request_no="WDR-SITE-FILTER-A",
                amount=Decimal("60"),
                cash_amount=Decimal("60"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("60"),
                currency=primary_wallet.currency,
                status="paid",
            )
        )
        session.add(
            WithdrawalRequest(
                account_id="acct-finance-site-filter",
                wallet_account_id=secondary_wallet.id,
                user_id=secondary_user.id,
                request_no="WDR-SITE-FILTER-B",
                amount=Decimal("80"),
                cash_amount=Decimal("80"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("80"),
                currency=secondary_wallet.currency,
                status="paid",
            )
        )
        session.commit()

    recharge_response = client.get(
        "/api/finance/recharge-records",
        headers=_super_admin_headers("acct-finance-site-filter"),
        params={
            "agency_id": "acct-finance-site-filter",
            "site_id": primary_site["id"],
        },
    )
    assert recharge_response.status_code == 200, recharge_response.text
    recharge_items = recharge_response.json()
    assert len(recharge_items) == 1
    assert recharge_items[0]["public_user_id"] == primary_auth["member"]["publicUserId"]

    withdrawal_response = client.get(
        "/api/finance/withdrawal-records",
        headers=_super_admin_headers("acct-finance-site-filter"),
        params={
            "agency_id": "acct-finance-site-filter",
            "site_id": primary_site["id"],
        },
    )
    assert withdrawal_response.status_code == 200, withdrawal_response.text
    withdrawal_items = withdrawal_response.json()
    assert len(withdrawal_items) == 1
    assert withdrawal_items[0]["public_user_id"] == primary_auth["member"]["publicUserId"]
    assert withdrawal_items[0]["amount"] == 60.0


def test_legacy_reports_finance_uses_real_recharge_and_withdrawal_amounts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-legacy-finance-report", site_key="legacy-finance-report")
    auth_payload = _register_member(
        client,
        site_key="legacy-finance-report",
        phone="+8613900087403",
        display_name="Legacy Finance Report Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-legacy-finance-report",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        wallet_service = WalletLedgerService(session=session)
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("150"),
            currency=wallet.currency,
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Legacy finance recharge",
            reference_type=None,
            reference_id=None,
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    withdrawal_response = client.post(
        "/api/h5/withdrawals",
        json={"amount": 90},
        headers={"X-Site-Key": "legacy-finance-report"},
    )
    assert withdrawal_response.status_code == 200, withdrawal_response.text
    withdrawal_id = withdrawal_response.json()["id"]
    approved = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approved."},
        headers=_super_admin_headers("acct-legacy-finance-report"),
    )
    assert approved.status_code == 200, approved.text
    paid = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Paid."},
        headers=_super_admin_headers("acct-legacy-finance-report"),
    )
    assert paid.status_code == 200, paid.text

    response = client.get(
        "/api/reports/finance",
        headers=_super_admin_headers("acct-legacy-finance-report"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["recharge_amount"] == 150.0
    assert payload["withdraw_amount"] == 90.0

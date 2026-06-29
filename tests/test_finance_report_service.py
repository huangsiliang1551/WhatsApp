from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, RechargeRecord, WalletAccount, WalletLedgerEntry, WalletRechargeOrder
from app.services.finance_report_service import FinanceReportService
from app.services.wallet_ledger_service import WalletLedgerService
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _finance_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "finance-report-service",
        "X-Actor-Role": "finance",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def test_manual_recharge_credits_wallet_and_writes_real_recharge_ledger(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-manual", site_key="finance-manual")
    auth_payload = _register_member(
        client,
        site_key="finance-manual",
        phone="+8613900087001",
        display_name="Finance Manual Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-manual",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        service = FinanceReportService(session)
        result = service.manual_recharge(
            user_id=user.id,
            amount=Decimal("88"),
            agency_id="acct-finance-manual",
            site_id=site["id"],
        )

        assert result["amount"] == 88.0
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        assert wallet.system_balance == Decimal("88")
        assert wallet.system_cash_balance == Decimal("88")
        assert wallet.system_bonus_balance == Decimal("0")

        record = session.query(RechargeRecord).filter(RechargeRecord.user_id == user.id).one()
        recharge_order = session.query(WalletRechargeOrder).filter(WalletRechargeOrder.user_id == user.id).one()
        ledger = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.user_id == user.id,
            WalletLedgerEntry.transaction_type == "manual_recharge",
        ).one()

        assert record.amount == Decimal("88")
        assert recharge_order.amount == Decimal("88")
        assert ledger.cash_amount == Decimal("88")
        assert ledger.bonus_amount == Decimal("0")
        assert ledger.is_real_recharge is True
        assert ledger.source_type == "manual_real_recharge"


def test_finance_summary_uses_cash_bonus_split_instead_of_legacy_only_records(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-finance-summary", site_key="finance-summary")
    auth_payload = _register_member(
        client,
        site_key="finance-summary",
        phone="+8613900087002",
        display_name="Finance Summary Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-finance-summary",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        finance_service = FinanceReportService(session)
        wallet_service = WalletLedgerService(session=session)

        finance_service.manual_recharge(
            user_id=user.id,
            amount=Decimal("100"),
            agency_id="acct-finance-summary",
            site_id=site["id"],
        )
        wallet_service.credit_system_balance(
            wallet=wallet,
            account_id=user.account_id,
            user_id=user.id,
            amount=Decimal("200"),
            currency=wallet.currency,
            transaction_type="admin_bonus",
            source_type="admin_bonus",
            note="Admin bonus credited",
            reference_type="test_seed",
            reference_id="finance-summary-bonus",
            fund_type="bonus",
            is_bonus=True,
        )
        session.commit()

    create_response = client.post("/api/h5/withdrawals", json={"amount": 250})
    assert create_response.status_code == 200, create_response.text
    withdrawal_id = create_response.json()["id"]

    approved_response = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "approved", "note": "Approved for payout."},
        headers=_finance_headers("acct-finance-summary"),
    )
    assert approved_response.status_code == 200, approved_response.text

    paid_response = client.post(
        f"/api/platform/withdrawals/{withdrawal_id}/status",
        json={"status": "paid", "note": "Payout completed."},
        headers=_finance_headers("acct-finance-summary"),
    )
    assert paid_response.status_code == 200, paid_response.text

    with db_session_factory() as session:
        service = FinanceReportService(session)
        summary = service.get_finance_summary({"agency_id": "acct-finance-summary"})

    assert summary["recharge_amount"] == 100.0
    assert summary["bonus_amount"] == 200.0
    assert summary["withdrawal_amount"] == 250.0
    assert summary["withdrawal_cash_amount"] == 100.0
    assert summary["withdrawal_bonus_amount"] == 150.0
    assert summary["net_recharge"] == 0.0

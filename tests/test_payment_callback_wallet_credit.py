import hashlib
import hmac
import json
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, PaymentChannel, RechargeRecord, WalletAccount, WalletLedgerEntry
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _sign_payload(secret: str, payload: dict[str, object]) -> str:
    return hmac.new(secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def test_payment_callback_credits_wallet_once_and_ignores_duplicate_order(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-payment-callback", site_key="payment-callback")
    auth_payload = _register_member(
        client,
        site_key="payment-callback",
        phone="+8613900087011",
        display_name="Payment Callback Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-payment-callback",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        channel = PaymentChannel(
            id="channel-wallet-credit",
            name="Wallet Credit Channel",
            channel_type="mock",
            callback_secret="secret-123",
            status="active",
        )
        session.add(channel)
        session.commit()
        user_id = user.id

    payload = {
        "amount": "120",
        "currency": "CNY",
        "user_id": user_id,
        "order_id": "ORDER-001",
    }
    signature = _sign_payload("secret-123", payload)

    first_response = client.post(
        "/api/payment/callback/channel-wallet-credit",
        json=payload,
        headers={"X-Signature": signature},
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["status"] == "success"

    duplicate_response = client.post(
        "/api/payment/callback/channel-wallet-credit",
        json=payload,
        headers={"X-Signature": signature},
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    assert duplicate_response.json()["status"] == "duplicate"

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user_id).one()
        assert wallet.system_balance == Decimal("120")
        assert wallet.system_cash_balance == Decimal("120")
        assert wallet.system_bonus_balance == Decimal("0")

        recharge_records = session.query(RechargeRecord).filter(RechargeRecord.user_id == user_id).all()
        ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.source_type == "payment_callback",
        ).all()

        assert len(recharge_records) == 1
        assert len(ledgers) == 1
        assert ledgers[0].cash_amount == Decimal("120")
        assert ledgers[0].is_real_recharge is True
        assert ledgers[0].idempotency_key is not None

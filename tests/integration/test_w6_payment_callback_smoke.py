from __future__ import annotations

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
    return hmac.new(
        secret.encode(),
        json.dumps(payload, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()


def test_w6_payment_callback_smoke_credits_wallet_once(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="w6-payment-account", site_key="w6-payment-site")
    auth_payload = _register_member(
        client,
        site_key="w6-payment-site",
        phone="+8613900087012",
        display_name="W6 Payment Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="w6-payment-account",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        session.add(
            PaymentChannel(
                id="w6-channel-wallet-credit",
                name="W6 Wallet Credit Channel",
                channel_type="mock",
                callback_secret="w6-secret",
                status="active",
            )
        )
        session.commit()
        user_id = user.id

    payload = {
        "amount": "120",
        "currency": "CNY",
        "user_id": user_id,
        "order_id": "W6-ORDER-001",
    }
    signature = _sign_payload("w6-secret", payload)

    first = client.post(
        "/api/payment/callback/w6-channel-wallet-credit",
        json=payload,
        headers={"X-Signature": signature},
    )
    second = client.post(
        "/api/payment/callback/w6-channel-wallet-credit",
        json=payload,
        headers={"X-Signature": signature},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "success"
    assert second.json()["status"] == "duplicate"

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user_id).one()
        recharges = session.query(RechargeRecord).filter(RechargeRecord.user_id == user_id).all()
        ledgers = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.user_id == user_id,
            WalletLedgerEntry.source_type == "payment_callback",
        ).all()

    assert wallet.system_balance == Decimal("120")
    assert wallet.system_cash_balance == Decimal("120")
    assert len(recharges) == 1
    assert len(ledgers) == 1
    assert ledgers[0].cash_amount == Decimal("120")
    assert ledgers[0].is_real_recharge is True

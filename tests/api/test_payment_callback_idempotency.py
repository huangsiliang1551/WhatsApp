from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, PaymentChannel, RechargeRecord
from tests.test_h5_member_auth import _create_site, _register_member
from tests.test_h5_task_packages_wallet import _seed_task_package_scope


def _sign(secret: str, payload: dict[str, object]) -> str:
    return hmac.new(secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def test_payment_callback_route_is_idempotent(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-api-payment-idem", site_key="api-payment-idem")
    auth_payload = _register_member(
        client,
        site_key="api-payment-idem",
        phone="+86139000879901",
        display_name="API Payment Idempotent",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-api-payment-idem",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=0,
        task_balance=0,
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        channel = PaymentChannel(
            id="channel-api-generic-hmac",
            name="API Generic HMAC",
            channel_type="generic_hmac",
            callback_secret="api-secret",
            status="active",
        )
        session.add(channel)
        session.commit()
        user_id = user.id

    payload = {
        "amount": "66.00",
        "currency": "CNY",
        "user_id": user_id,
        "order_id": "API-PAYMENT-001",
    }
    signature = _sign("api-secret", payload)

    first = client.post(
        "/api/payment/callback/channel-api-generic-hmac",
        json=payload,
        headers={"X-Signature": signature},
    )
    second = client.post(
        "/api/payment/callback/channel-api-generic-hmac",
        json=payload,
        headers={"X-Signature": signature},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "success"
    assert second.json()["status"] == "duplicate"

    with db_session_factory() as session:
        recharges = session.query(RechargeRecord).filter(RechargeRecord.user_id == user_id).all()
        assert len(recharges) == 1

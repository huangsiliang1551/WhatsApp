from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, AppUser, RechargeRecord, RechargeRepairOrder, WalletAccount
from app.services.recharge_repair_service import RechargeRepairService


def test_recharge_repair_approval_rejects_when_callback_recharge_already_exists(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-repair-race", display_name="acct-repair-race", provider_type="mock")
        user = AppUser(
            id="user-repair-race",
            account_id=account.account_id,
            public_user_id="pub-user-repair-race",
            registration_site_id=None,
            display_name="Repair Race",
            has_phone=True,
            is_anonymous=False,
            lifecycle_status="active",
        )
        wallet = WalletAccount(
            id="wallet-repair-race",
            account_id=account.account_id,
            user_id=user.id,
            currency="USD",
        )
        callback_recharge = RechargeRecord(
            id="recharge-race-callback",
            user_id=user.id,
            agency_id=account.account_id,
            amount=Decimal("66.00"),
            currency="USD",
            status="completed",
            channel_id="channel-race",
            channel_order_id="ORDER-RACE-1",
            callback_verified=True,
            callback_data={"source": "callback"},
        )
        repair = RechargeRepairOrder(
            id="repair-race-1",
            account_id=account.account_id,
            repair_no="RPR-RACE-1",
            user_id=user.id,
            channel_id="channel-race",
            channel_order_no="ORDER-RACE-1",
            amount=Decimal("66.00"),
            currency="USD",
            repair_type="callback_missing_credit",
            status="pending",
            reason="Repair after callback",
            operator_id="operator-race",
        )
        session.add_all([account, user, wallet, callback_recharge, repair])
        session.commit()

        with pytest.raises(ValueError, match="Recharge already exists"):
            RechargeRepairService(session).approve_repair(repair_id=repair.id, actor_id="finance-race")

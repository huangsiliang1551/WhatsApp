"""Tests for sign_in_service.py (10 tests)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Account, AppUser, SignInRecord, SystemSetting, WalletAccount, MktTaskInstance
from app.services.sign_in_service import AlreadySignedInError, SignInService, SignInTaskAlreadyCompletedError
from tests.fake_redis import FakeRedis


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.add(AppUser(id="user-1", account_id="acc-1", public_user_id="u1"))
    session.add(WalletAccount(id="wallet-1", account_id="acc-1", user_id="user-1",
                               system_balance=Decimal("100"), task_balance=Decimal("0")))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def fake_redis():
    return FakeRedis()


def test_sign_in_first_time(db_session: Session, fake_redis: FakeRedis):
    svc = SignInService(db_session, fake_redis)
    result = svc.sign_in("user-1", "acc-1")
    assert result.consecutive_days == 1
    assert result.rewarded is False


def test_sign_in_twice_fails(db_session: Session, fake_redis: FakeRedis):
    svc = SignInService(db_session, fake_redis)
    svc.sign_in("user-1", "acc-1")
    with pytest.raises(AlreadySignedInError):
        svc.sign_in("user-1", "acc-1")


def test_sign_in_consecutive(db_session: Session, fake_redis: FakeRedis):
    # First create yesterday's record to simulate a streak
    yesterday = date.today() - timedelta(days=1)
    db_session.add(SignInRecord(account_id="acc-1", user_id="user-1",
                                 sign_date=yesterday, consecutive_days=2))
    db_session.commit()

    svc = SignInService(db_session, fake_redis)
    result = svc.sign_in("user-1", "acc-1")
    assert result.consecutive_days == 3

    # Check status shows consecutive days
    status = svc.get_status("user-1", "acc-1")
    assert status.signed_in_today is True
    assert status.consecutive_days == 3


def test_sign_in_with_reward(db_session: Session, fake_redis: FakeRedis):
    # Set reward config
    db_session.add(SystemSetting(key="sign_in_consecutive_days", value_json={"value": 1}))
    db_session.add(SystemSetting(key="sign_in_reward_amount", value_json={"value": "5.00"}))
    db_session.commit()

    svc = SignInService(db_session, fake_redis)
    result = svc.sign_in("user-1", "acc-1")
    assert result.rewarded is True
    assert result.reward_amount == Decimal("5.00")

    wallet = db_session.query(WalletAccount).first()
    assert wallet.task_balance == Decimal("5.00")


def test_sign_in_task_already_completed(db_session: Session, fake_redis: FakeRedis):
    db_session.add(MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                                    task_type="signin", status="completed"))
    db_session.commit()

    svc = SignInService(db_session, fake_redis)
    # If signin task completed today, it won't block the actual signin but won't reward
    result = svc.sign_in("user-1", "acc-1")
    assert result.consecutive_days == 1


def test_get_status_not_signed_in(db_session: Session):
    svc = SignInService(db_session)
    status = svc.get_status("user-1", "acc-1")
    assert status.signed_in_today is False
    assert status.consecutive_days == 0


def test_get_status_signed_in(db_session: Session, fake_redis: FakeRedis):
    svc = SignInService(db_session, fake_redis)
    svc.sign_in("user-1", "acc-1")
    status = svc.get_status("user-1", "acc-1")
    assert status.signed_in_today is True
    assert status.consecutive_days >= 1


def test_get_config_default(db_session: Session):
    svc = SignInService(db_session)
    config = svc.get_config()
    assert config["consecutive_days"] == 7
    assert config["reward_amount"] == Decimal("5.00")


def test_update_config(db_session: Session):
    svc = SignInService(db_session)
    svc.update_config(consecutive_days=3, reward_amount=Decimal("10"))
    config = svc.get_config()
    assert config["consecutive_days"] == 3
    assert config["reward_amount"] == Decimal("10")

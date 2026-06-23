"""Tests for invite_service.py (10 tests)."""  # noqa: INP001
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Account, AppUser, InviteLink, InviteRecord, SystemSetting, WalletAccount
from app.services.invite_service import AntiFraudError, InviteLimitExceededError, InviteService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.add(AppUser(id="user-1", account_id="acc-1", public_user_id="u1"))
    session.add(AppUser(id="user-2", account_id="acc-1", public_user_id="u2"))
    session.add(WalletAccount(id="wallet-1", account_id="acc-1", user_id="user-1",
                               system_balance=Decimal("100"), task_balance=Decimal("0")))
    session.commit()
    yield session
    session.close()


def test_get_or_create_link(db_session: Session):
    svc = InviteService(db_session)
    link = svc.get_or_create_link("user-1", "acc-1")
    assert link.user_id == "user-1"
    assert link.account_id == "acc-1"
    assert link.invite_code is not None
    assert len(link.invite_code) == 12


def test_get_or_create_link_existing(db_session: Session):
    svc = InviteService(db_session)
    link1 = svc.get_or_create_link("user-1", "acc-1")
    link2 = svc.get_or_create_link("user-1", "acc-1")
    assert link1.id == link2.id
    assert link1.invite_code == link2.invite_code


def test_get_my_records_empty(db_session: Session):
    svc = InviteService(db_session)
    result = svc.get_my_records("user-1")
    assert result["total"] == 0
    assert result["items"] == []


def test_on_register_callback_success(db_session: Session):
    svc = InviteService(db_session)
    link = svc.get_or_create_link("user-1", "acc-1")
    record = svc.on_register_callback(link.invite_code, "user-2")
    assert record is not None
    assert record.inviter_user_id == "user-1"
    assert record.invitee_user_id == "user-2"
    assert record.invite_type == "register"
    assert record.is_rewarded is True


def test_on_register_callback_invalid_code(db_session: Session):
    svc = InviteService(db_session)
    with pytest.raises(LookupError, match="Invalid invite code"):
        svc.on_register_callback("invalid_code", "user-2")


def test_on_register_callback_self_invite(db_session: Session):
    svc = InviteService(db_session)
    link = svc.get_or_create_link("user-1", "acc-1")
    with pytest.raises(ValueError, match="Cannot invite yourself"):
        svc.on_register_callback(link.invite_code, "user-1")


def test_on_register_callback_duplicate(db_session: Session):
    svc = InviteService(db_session)
    link = svc.get_or_create_link("user-1", "acc-1")
    svc.on_register_callback(link.invite_code, "user-2")
    # Duplicate returns None
    record = svc.on_register_callback(link.invite_code, "user-2")
    assert record is None


def test_on_recharge_callback_below_threshold(db_session: Session):
    svc = InviteService(db_session)
    # Recharge below threshold (30) returns None
    record = svc.on_recharge_callback("user-1", "user-2", Decimal("10"))
    assert record is None


def test_on_recharge_callback_above_threshold(db_session: Session):
    svc = InviteService(db_session)
    # First create invite link for user-1
    svc.get_or_create_link("user-1", "acc-1")
    record = svc.on_recharge_callback("user-1", "user-2", Decimal("50"))
    assert record is not None
    assert record.invite_type == "recharge"
    assert record.is_rewarded is True

    # Check wallet was credited
    wallet = db_session.query(WalletAccount).first()
    assert wallet.task_balance == Decimal("3.00")


def test_invite_limit_exceeded(db_session: Session):
    # Set low invite limit
    db_session.add(SystemSetting(key="invite_max_count", value_json={"value": 1}))
    db_session.commit()

    svc = InviteService(db_session)
    link = svc.get_or_create_link("user-1", "acc-1")

    # First invite succeeds
    svc.on_register_callback(link.invite_code, "user-2")

    # Create another user for second invite
    db_session.add(AppUser(id="user-3", account_id="acc-1", public_user_id="u3"))
    db_session.commit()

    # Second invite should fail due to limit
    with pytest.raises(InviteLimitExceededError, match="Invite limit"):
        svc.on_register_callback(link.invite_code, "user-3")

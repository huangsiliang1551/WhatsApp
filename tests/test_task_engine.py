"""Tests for task_engine.py (15 tests)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import (
    Account, AppUser, MktTaskInstance, Product, ProductPackage, TaskRule, WalletAccount
)
from app.services.task_engine import InsufficientBalanceError, TaskEngine
from app.services.product_service import ProductService
from app.schemas.marketing import ProductCreateRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.add(AppUser(id="user-1", account_id="acc-1", public_user_id="u1"))
    session.add(TaskRule(id="rule-1", account_id="acc-1", name="R1",
                          rule_type="package_push", trigger_type="register",
                          trigger_config={"delay_minutes": 0}, is_enabled=True))
    session.add(TaskRule(id="rule-2", account_id="acc-1", name="R2",
                          rule_type="package_push", trigger_type="recharge",
                          trigger_config={"threshold_amount": 50}, is_enabled=True))
    # Create products
    p1 = Product(id="prod-1", account_id="acc-1", name="P1", price=Decimal("10"))
    p2 = Product(id="prod-2", account_id="acc-1", name="P2", price=Decimal("20"))
    session.add_all([p1, p2])
    # Create package
    session.add(ProductPackage(id="pkg-1", account_id="acc-1", name="PKG",
                                target_amount=Decimal("30"), product_count=2,
                                product_ids=["prod-1", "prod-2"],
                                product_snapshot=[{"id": "prod-1", "name": "P1", "price": "10"},
                                                  {"id": "prod-2", "name": "P2", "price": "20"}],
                                total_value=Decimal("30"), completion_reward=Decimal("5")))
    session.add(TaskRule(id="rule-pkg", account_id="acc-1", name="RPKG",
                          rule_type="package_push", trigger_type="register",
                          package_id="pkg-1", trigger_config={}, is_enabled=True))
    # Wallet with balance
    session.add(WalletAccount(id="wallet-1", account_id="acc-1", user_id="user-1",
                               system_balance=Decimal("100"), task_balance=Decimal("0")))
    session.commit()
    yield session
    session.close()


def test_on_user_registered_creates_task(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "acc-1")
    assert len(instances) >= 1


def test_on_user_registered_no_rules(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "no-such-account")
    assert len(instances) == 0


def test_on_user_recharged_below_threshold(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_recharged("user-1", "acc-1", Decimal("10"))
    assert len(instances) == 0


def test_on_user_recharged_above_threshold(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_recharged("user-1", "acc-1", Decimal("100"))
    assert len(instances) == 1


def test_manual_push(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.manual_push("rule-1", ["user-1"], "acc-1")
    assert len(instances) == 1


def test_manual_push_rule_not_found(db_session: Session):
    engine = TaskEngine(db_session)
    with pytest.raises(LookupError):
        engine.manual_push("nonexistent", ["user-1"], "acc-1")


def test_start_product_success(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "acc-1")
    # Find the instance with package
    for inst in instances:
        if inst.package_id == "pkg-1":
            result = engine.start_product(inst.id, "prod-1")
            assert result.status == "running"
            assert result.total_paid >= Decimal("10")
            return


def test_start_product_insufficient_balance(db_session: Session):
    engine = TaskEngine(db_session)
    # Reduce balance
    wallet = db_session.query(WalletAccount).first()
    wallet.system_balance = Decimal("5")
    db_session.commit()
    instances = engine.on_user_registered("user-1", "acc-1")
    for inst in instances:
        if inst.package_id == "pkg-1":
            with pytest.raises(InsufficientBalanceError):
                engine.start_product(inst.id, "prod-1")
            return


def test_complete_product(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "acc-1")
    for inst in instances:
        if inst.package_id == "pkg-1":
            engine.start_product(inst.id, "prod-1")
            result = engine.complete_product(inst.id, "prod-1")
            assert result.status == "running"  # Not all products completed
            return


def test_complete_all_products(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "acc-1")
    for inst in instances:
        if inst.package_id == "pkg-1":
            engine.start_product(inst.id, "prod-1")
            engine.start_product(inst.id, "prod-2")
            engine.complete_product(inst.id, "prod-1")
            result = engine.complete_product(inst.id, "prod-2")
            assert result.status == "completed"
            assert result.reward_amount >= Decimal("5")
            return


def test_expire_task(db_session: Session):
    engine = TaskEngine(db_session)
    instances = engine.on_user_registered("user-1", "acc-1")
    if instances:
        engine.expire_task(instances[0].id)
        expired = db_session.get(MktTaskInstance, instances[0].id)
        assert expired.status == "expired"


def test_create_task_instance_with_package(db_session: Session):
    rule = db_session.query(TaskRule).filter(TaskRule.id == "rule-pkg").first()
    engine = TaskEngine(db_session)
    inst = engine._create_task_instance(rule, "user-1", "acc-1")
    assert inst.task_type == "package_push"
    assert inst.package_id == "pkg-1"
    assert inst.product_progress is not None


def test__all_products_completed(db_session: Session):
    engine = TaskEngine(db_session)
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="running",
                            product_progress=[{"product_id": "p1", "status": "completed"},
                                              {"product_id": "p2", "status": "completed"}])
    assert engine._all_products_completed(inst) is True


def test__all_products_completed_not_all(db_session: Session):
    engine = TaskEngine(db_session)
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="running",
                            product_progress=[{"product_id": "p1", "status": "completed"},
                                              {"product_id": "p2", "status": "pending"}])
    assert engine._all_products_completed(inst) is False


def test__all_products_completed_empty(db_session: Session):
    engine = TaskEngine(db_session)
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="running",
                            product_progress=[])
    assert engine._all_products_completed(inst) is False

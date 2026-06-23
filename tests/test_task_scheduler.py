"""Tests for task_scheduler.py (8 tests)."""  # noqa: INP001
from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Account, AppUser, MktTaskInstance, WalletAccount
from app.services.task_scheduler import TaskScheduler
from tests.fake_redis import FakeRedis


@pytest.fixture
def engine_factory():
    """Create an engine + sessionmaker for shared in-memory DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    # Seed initial data
    session = TestSessionLocal()
    session.add(Account(account_id="acc-1", display_name="Test"))
    session.add(AppUser(id="user-1", account_id="acc-1", public_user_id="u1"))
    session.add(WalletAccount(id="wallet-1", account_id="acc-1", user_id="user-1",
                               system_balance=Decimal("100"), task_balance=Decimal("0")))
    session.commit()
    session.close()
    return TestSessionLocal


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def scheduler(fake_redis):
    return TaskScheduler(fake_redis)


@pytest.mark.asyncio
async def test_process_delayed_tasks_empty(engine_factory, scheduler: TaskScheduler):
    """No delayed tasks to process."""
    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._process_delayed_tasks()


@pytest.mark.asyncio
async def test_process_delayed_tasks_activate(engine_factory, scheduler: TaskScheduler, fake_redis: FakeRedis):
    """Activate a pending delayed task."""
    # Create task instance using a session from the factory
    session = engine_factory()
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="pending")
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    job = {"task_instance_id": inst_id, "rule_id": "rule-1", "user_id": "user-1"}
    await fake_redis.zadd("delayed_tasks", {json.dumps(job): 0})

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._process_delayed_tasks()

    # Verify with a fresh session
    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "running"
    assert updated.started_at is not None
    session.close()


@pytest.mark.asyncio
async def test_process_delayed_tasks_not_due(engine_factory, scheduler: TaskScheduler, fake_redis: FakeRedis):
    """Tasks not yet due should not be activated."""
    session = engine_factory()
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="pending")
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    job = {"task_instance_id": inst_id, "rule_id": "rule-1", "user_id": "user-1"}
    future_ts = time.time() + 3600  # 1 hour in the future
    await fake_redis.zadd("delayed_tasks", {json.dumps(job): future_ts})

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._process_delayed_tasks()

    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "pending"
    session.close()


@pytest.mark.asyncio
async def test_expire_tasks_no_expired(engine_factory, scheduler: TaskScheduler):
    """No expired tasks."""
    session = engine_factory()
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="running",
                            expires_at=datetime.now(UTC) + timedelta(hours=1))
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._expire_tasks()

    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "running"
    session.close()


@pytest.mark.asyncio
async def test_expire_tasks_with_expired(engine_factory, scheduler: TaskScheduler):
    """Expire tasks past their expires_at."""
    session = engine_factory()
    past_time = datetime.now(UTC) - timedelta(hours=2)
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="running",
                            expires_at=past_time)
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._expire_tasks()

    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "expired"
    session.close()


@pytest.mark.asyncio
async def test_expire_tasks_skips_completed(engine_factory, scheduler: TaskScheduler):
    """Completed tasks should not be expired."""
    session = engine_factory()
    past_time = datetime.now(UTC) - timedelta(hours=2)
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="completed",
                            expires_at=past_time)
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._expire_tasks()

    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "completed"
    session.close()


@pytest.mark.asyncio
async def test_catch_up_missed(engine_factory, scheduler: TaskScheduler, fake_redis: FakeRedis):
    """Catch up missed delayed tasks on startup."""
    session = engine_factory()
    inst = MktTaskInstance(account_id="acc-1", user_id="user-1", rule_id="rule-1",
                            task_type="package_push", status="pending")
    session.add(inst)
    session.commit()
    inst_id = inst.id
    session.close()

    job = {"task_instance_id": inst_id, "rule_id": "rule-1", "user_id": "user-1"}
    await fake_redis.zadd("delayed_tasks", {json.dumps(job): 0})

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._catch_up_missed()

    session = engine_factory()
    updated = session.get(MktTaskInstance, inst_id)
    assert updated.status == "running"
    session.close()


@pytest.mark.asyncio
async def test_delayed_task_invalid_job(engine_factory, scheduler: TaskScheduler, fake_redis: FakeRedis):
    """Invalid job JSON should be handled gracefully."""
    await fake_redis.zadd("delayed_tasks", {"not-json": 0})

    with patch("app.services.task_scheduler.SessionLocal", engine_factory):
        await scheduler._process_delayed_tasks()

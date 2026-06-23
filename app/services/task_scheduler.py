from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select

from app.db.models import MktTaskInstance, TaskRule
from app.db.session import SessionLocal
from app.services.notification_service import NotificationService
from app.services.task_engine import TaskEngine

logger = structlog.get_logger()


class TaskScheduler:
    """Worker scheduler: delayed tasks, scheduled push, expiry scan, catch-up."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def run_scheduler_loop(self) -> None:
        logger.info("marketing_scheduler_started")
        backlog_check_interval = 0
        while True:
            try:
                await self._process_delayed_tasks()
                await self._process_scheduled_rules()
                await self._expire_tasks()
                backlog_check_interval += 1
                if backlog_check_interval >= 10:  # ~5 minutes
                    backlog_check_interval = 0
                    await self._check_queue_backlog()
            except Exception as exc:
                logger.error("marketing_scheduler_error", error=str(exc))
            await asyncio.sleep(30)

    async def _process_delayed_tasks(self) -> None:
        now = time.time()
        jobs = await self._redis.zrangebyscore("delayed_tasks", 0, now)
        if not jobs:
            return
        for job_raw in jobs:
            try:
                job = json.loads(job_raw)
                task_instance_id = job.get("task_instance_id")
                if task_instance_id:
                    # Activate the task
                    session = SessionLocal()
                    try:
                        inst = session.get(MktTaskInstance, task_instance_id)
                        if inst and inst.status == "pending":
                            inst.status = "running"
                            inst.started_at = datetime.now(UTC).replace(tzinfo=None)
                            session.commit()
                            logger.info(
                                "delayed_task_activated",
                                task_instance_id=task_instance_id,
                            )
                    finally:
                        session.close()
                elif job.get("rule_id"):
                    # 类型 2: 有 rule_id（创建新实例）
                    rule_id = job["rule_id"]
                    user_id = job["user_id"]
                    account_id = job.get("account_id", "")
                    session = SessionLocal()
                    try:
                        engine = TaskEngine(session)
                        instances = engine.manual_push(
                            rule_id=rule_id,
                            user_ids=[user_id],
                            account_id=account_id,
                        )
                        session.commit()
                        logger.info(
                            "delayed_task_rule_created",
                            rule_id=rule_id,
                            user_id=user_id,
                            instance_count=len(instances),
                        )
                    finally:
                        session.close()
                await self._redis.zrem("delayed_tasks", job_raw)
            except Exception as exc:
                logger.warning(
                    "delayed_task_error",
                    job=job_raw,
                    error=str(exc),
                )

    async def _process_scheduled_rules(self) -> None:
        """Check schedule-triggered rules and create task instances."""
        now = datetime.now(UTC)
        current_hour = now.hour
        current_minute = now.minute

        session = SessionLocal()
        try:
            rules = session.execute(
                select(TaskRule).where(
                    TaskRule.trigger_type == "schedule",
                    TaskRule.is_enabled == True,
                )
            ).scalars().all()

            for rule in rules:
                config = rule.trigger_config or {}
                cron_hour = config.get("cron_hour")
                cron_minute = config.get("cron_minute", 0)
                if cron_hour is None:
                    continue

                # Check if it's time to fire (within the current minute window)
                if current_hour == cron_hour and current_minute == cron_minute:
                    await self._fire_scheduled_rule(session, rule)
        finally:
            session.close()

    async def _fire_scheduled_rule(self, session: Any, rule: TaskRule) -> None:
        """Fire a scheduled rule: find eligible users and create task instances."""
        config = rule.trigger_config or {}
        filter_tags = config.get("filter_tags")
        exclude_claimed = config.get("exclude_claimed", True)

        # Get all users for this account (simplified - in production use a user query)
        from app.db.models import AppUser
        user_query = select(AppUser).where(AppUser.account_id == rule.account_id)
        if filter_tags:
            for tag in filter_tags:
                user_query = user_query.where(AppUser.tags.contains(tag))

        users = session.execute(user_query).scalars().all()

        created = 0
        for user in users:
            if exclude_claimed and rule.package_id:
                existing = session.execute(
                    select(MktTaskInstance).where(
                        MktTaskInstance.user_id == user.id,
                        MktTaskInstance.rule_id == rule.id,
                        MktTaskInstance.status.in_(["pending", "running"]),
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

            inst = MktTaskInstance(
                account_id=rule.account_id,
                user_id=user.id,
                rule_id=rule.id,
                package_id=rule.package_id,
                task_type=rule.rule_type,
                status="pending",
            )
            session.add(inst)
            created += 1

        if created > 0:
            session.commit()
            logger.info(
                "scheduled_push_created",
                rule_id=rule.id,
                user_count=created,
            )

    async def _expire_tasks(self) -> None:
        """Expire tasks past their expires_at."""
        now = datetime.now(UTC).replace(tzinfo=None)
        session = SessionLocal()
        try:
            expired = session.execute(
                select(MktTaskInstance).where(
                    MktTaskInstance.status.in_(["pending", "running"]),
                    MktTaskInstance.expires_at.isnot(None),
                    MktTaskInstance.expires_at < now,
                )
            ).scalars().all()

            for inst in expired:
                inst.status = "expired"
                logger.info(
                    "task_expired",
                    task_id=inst.id,
                    user_id=inst.user_id,
                )
            if expired:
                session.commit()
        finally:
            session.close()

    async def _check_queue_backlog(self) -> None:
        """Check for queue backlog and create notification if threshold exceeded."""
        try:
            delayed_count = await self._redis.zcard("delayed_tasks")
            if delayed_count and delayed_count > 1000:
                session = SessionLocal()
                try:
                    svc = NotificationService(session)
                    svc.create_notification(
                        account_id="",
                        type="alert",
                        category="queue",
                        title="队列积压超过阈值",
                        message=f"delayed_tasks 队列当前积压 {delayed_count} 条任务，超过阈值 1000",
                        severity="warning",
                    )
                    logger.warning("queue_backlog_threshold_exceeded", count=delayed_count)
                finally:
                    session.close()
        except Exception as exc:
            logger.warning("queue_backlog_check_failed", error=str(exc))

    async def _catch_up_missed(self) -> None:
        """On startup, catch up any delayed tasks that were missed during downtime."""
        await self._process_delayed_tasks()

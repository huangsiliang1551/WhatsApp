from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    H5Site,
    MktTaskInstance,
    Notification,
    Product,
    ProductPackage,
    TaskRule,
    WalletAccount,
    WalletLedgerEntry,
)


class InsufficientBalanceError(ValueError):
    pass


class TaskEngine:
    def __init__(self, session: Session, redis_client: Any | None = None) -> None:
        self._session = session
        self._redis = redis_client

    # ─── Triggers ──────────────────────────────────────────────────────────

    def on_user_registered(self, user_id: str, account_id: str) -> list[MktTaskInstance]:
        instances: list[MktTaskInstance] = []
        rules = self._get_enabled_rules(account_id, "register")
        for rule in rules:
            delay_minutes = (rule.trigger_config or {}).get("delay_minutes", 0)
            inst = self._create_task_instance(rule, user_id, account_id)
            if delay_minutes > 0:
                self._schedule_delayed(inst, delay_minutes)
            instances.append(inst)
        return instances

    def on_user_recharged(self, user_id: str, account_id: str, amount: Decimal) -> list[MktTaskInstance]:
        instances: list[MktTaskInstance] = []
        rules = self._get_enabled_rules(account_id, "recharge")
        for rule in rules:
            threshold = (rule.trigger_config or {}).get("threshold_amount", 0)
            if amount >= Decimal(str(threshold)):
                inst = self._create_task_instance(rule, user_id, account_id)
                instances.append(inst)
        return instances

    def manual_push(self, rule_id: str, user_ids: list[str], account_id: str) -> list[MktTaskInstance]:
        rule = self._session.get(TaskRule, rule_id)
        if rule is None:
            raise LookupError(f"Task rule '{rule_id}' not found.")
        instances: list[MktTaskInstance] = []
        for uid in user_ids:
            inst = self._create_task_instance(rule, uid, account_id)
            instances.append(inst)
        return instances

    # ─── Product task lifecycle ────────────────────────────────────────────

    def start_product(self, task_instance_id: str, product_id: str) -> MktTaskInstance:
        inst = self._session.get(MktTaskInstance, task_instance_id)
        if inst is None:
            raise LookupError(f"Task instance '{task_instance_id}' not found.")

        product = self._session.get(Product, product_id)
        if product is None:
            raise LookupError(f"Product '{product_id}' not found.")

        # FOR UPDATE lock the wallet
        wallet = self._session.execute(
            select(WalletAccount)
            .where(WalletAccount.user_id == inst.user_id)
            .with_for_update()
        ).scalar_one_or_none()
        if wallet is None:
            raise LookupError(f"Wallet not found for user '{inst.user_id}'.")

        if wallet.system_balance < product.price:
            # 创建通知：商品任务余额不足
            self._create_notification(
                account_id=inst.account_id,
                type="warning",
                category="system",
                title="商品任务余额不足",
                message=f"用户 {inst.user_id} 系统余额 {wallet.system_balance} 不足，无法扣减 {product.price}（商品: {product.name}）",
                severity="warning",
            )
            raise InsufficientBalanceError(
                f"Insufficient system balance {wallet.system_balance} < {product.price}"
            )

        # Deduct from system_balance
        wallet.system_balance -= product.price

        # Record ledger entry
        ledger = WalletLedgerEntry(
            account_id=inst.account_id,
            wallet_account_id=wallet.id,
            user_id=inst.user_id,
            ledger_type="task_purchase",
            transaction_type=f"product_{product_id}",
            direction="debit",
            amount=product.price,
            currency=wallet.currency,
            status="paid",
            note=f"Product purchase: {product.name}",
            reference_type="task_instance",
            reference_id=task_instance_id,
        )
        self._session.add(ledger)

        # Update progress
        progress = copy.deepcopy(inst.product_progress) if inst.product_progress else []
        found = False
        for item in progress:
            if item.get("product_id") == product_id:
                item["status"] = "running"
                found = True
                break
        if not found:
            progress.append({"product_id": product_id, "status": "running"})
        inst.product_progress = progress
        inst.total_paid = (inst.total_paid or Decimal("0")) + product.price
        if inst.status == "pending":
            inst.status = "running"
            inst.started_at = datetime.now(UTC).replace(tzinfo=None)
        self._session.commit()
        self._session.refresh(inst)
        return inst

    def complete_product(self, task_instance_id: str, product_id: str) -> MktTaskInstance:
        inst = self._session.get(MktTaskInstance, task_instance_id)
        if inst is None:
            raise LookupError(f"Task instance '{task_instance_id}' not found.")

        progress = copy.deepcopy(inst.product_progress) if inst.product_progress else []
        for item in progress:
            if item.get("product_id") == product_id:
                item["status"] = "completed"
                item["paid_at"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
                break

        inst.product_progress = progress

        # Check all completed
        if self._all_products_completed(inst):
            inst.status = "completed"
            inst.completed_at = datetime.now(UTC).replace(tzinfo=None)
            # Grant completion reward to task_balance
            pkg = self._session.get(ProductPackage, inst.package_id)
            if pkg and pkg.completion_reward > Decimal("0"):
                wallet = self._session.execute(
                    select(WalletAccount)
                    .where(WalletAccount.user_id == inst.user_id)
                    .with_for_update()
                ).scalar_one_or_none()
                if wallet:
                    wallet.task_balance += pkg.completion_reward
                    inst.reward_amount = (inst.reward_amount or Decimal("0")) + pkg.completion_reward
                    self._session.add(WalletLedgerEntry(
                        account_id=inst.account_id,
                        wallet_account_id=wallet.id,
                        user_id=inst.user_id,
                        ledger_type="task_reward",
                        transaction_type="package_completion",
                        direction="credit",
                        amount=pkg.completion_reward,
                        currency=wallet.currency,
                        status="paid",
                        note=f"Package completion reward: {pkg.name}",
                        reference_type="task_instance",
                        reference_id=inst.id,
                    ))

            # 创建通知：商品包任务完成
            self._create_notification(
                account_id=inst.account_id,
                type="info",
                category="system",
                title="商品包任务完成",
                message=f"用户 {inst.user_id} 的商品包任务 {inst.id} 已完成，获得奖励 {inst.reward_amount}",
                severity="info",
                user_id=inst.user_id,
            )

            # 检查后续推链：将后续任务排入 Redis delayed_tasks
            if self._redis:
                rule = self._session.get(TaskRule, inst.rule_id)
                if rule and rule.follow_up_chain:
                    for step in rule.follow_up_chain:
                        delay_days = step.get("delay_days", step.get("days", 1))
                        next_rule_id = step.get("rule_id")
                        if next_rule_id:
                            trigger_at = (datetime.now(UTC) + timedelta(days=delay_days)).timestamp()
                            job = json.dumps({
                                "task_instance_id": None,
                                "rule_id": next_rule_id,
                                "user_id": inst.user_id,
                                "account_id": inst.account_id,
                                "trigger_at": trigger_at,
                                "source_task_id": inst.id,
                            })
                            self._redis.zadd("delayed_tasks", {job: trigger_at})

        self._session.commit()
        self._session.refresh(inst)
        return inst

    def retry_product(self, task_instance_id: str, product_id: str) -> MktTaskInstance:
        """Retry a failed or pending product within a task instance."""
        inst = self._session.get(MktTaskInstance, task_instance_id)
        if inst is None:
            raise LookupError(f"Task instance '{task_instance_id}' not found.")
        # Just reset the product status to pending and call start_product
        progress = copy.deepcopy(inst.product_progress) if inst.product_progress else []
        for item in progress:
            if item.get("product_id") == product_id and item.get("status") in ("failed", "pending"):
                item["status"] = "pending"
                break
        inst.product_progress = progress
        self._session.commit()
        return self.start_product(task_instance_id, product_id)

    def expire_task(self, task_id: str) -> None:
        self._session.execute(
            update(MktTaskInstance).where(MktTaskInstance.id == task_id).values(
                status="expired",
            )
        )
        self._session.commit()

    # ─── Helpers ───────────────────────────────────────────────────────────

    def _get_enabled_rules(self, account_id: str, trigger_type: str) -> list[TaskRule]:
        return list(self._session.execute(
            select(TaskRule).where(
                TaskRule.account_id == account_id,
                TaskRule.trigger_type == trigger_type,
                TaskRule.is_enabled == True,
            )
        ).scalars().all())

    def _create_task_instance(
        self,
        rule: TaskRule,
        user_id: str,
        account_id: str,
    ) -> MktTaskInstance:
        pkg = self._session.get(ProductPackage, rule.package_id) if rule.package_id else None
        progress = None
        if pkg and pkg.product_snapshot:
            progress = [
                {"product_id": item["id"], "status": "pending"}
                for item in pkg.product_snapshot
            ]

        # Resolve site_key from user's registration site
        site_key = None
        user = self._session.get(AppUser, user_id)
        if user and user.registration_site_id:
            h5_site = self._session.get(H5Site, user.registration_site_id)
            if h5_site:
                site_key = h5_site.site_key

        inst = MktTaskInstance(
            account_id=account_id,
            user_id=user_id,
            rule_id=rule.id,
            package_id=rule.package_id,
            task_type=rule.rule_type,
            status="pending",
            product_progress=progress,
            total_paid=Decimal("0"),
            reward_amount=Decimal("0"),
            site_key=site_key,
        )
        self._session.add(inst)
        self._session.commit()
        self._session.refresh(inst)
        return inst

    def _create_notification(
        self,
        account_id: str,
        type: str,
        category: str,
        title: str,
        message: str | None = None,
        severity: str = "info",
        user_id: str | None = None,
        action_url: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Create a notification record without extra commit (caller handles commit)."""
        notification = Notification(
            account_id=account_id,
            user_id=user_id,
            type=type,
            category=category,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            metadata_json=metadata,
        )
        self._session.add(notification)

    def _schedule_delayed(self, inst: MktTaskInstance, delay_minutes: int) -> None:
        if self._redis:
            trigger_at = (datetime.now(UTC) + timedelta(minutes=delay_minutes)).timestamp()
            job = json.dumps({"task_instance_id": inst.id, "rule_id": inst.rule_id, "user_id": inst.user_id})
            self._redis.zadd("delayed_tasks", {job: trigger_at})

    def _all_products_completed(self, inst: MktTaskInstance) -> bool:
        progress = inst.product_progress or []
        if not progress:
            return False
        return all(item.get("status") == "completed" for item in progress)

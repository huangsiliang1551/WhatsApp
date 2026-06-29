from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    H5Site,
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskProductGenerationRun,
    TaskProductPool,
    TaskSystemConfig,
    WalletLedgerEntry,
)
from scripts.check_wallet_balance_invariants import collect_wallet_invariant_violations

TWOPLACES = Decimal("0.01")


@dataclass(slots=True)
class IntegrityViolation:
    kind: str
    record_id: str
    account_id: str | None
    detail: str


def _amount(value: Decimal | str | int | float | None) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(value).quantize(TWOPLACES)


def _sum_amounts(values: list[str] | None) -> Decimal:
    total = Decimal("0.00")
    for value in values or []:
        total += _amount(value)
    return total.quantize(TWOPLACES)


def collect_task_system_v3_integrity_violations(session: Session) -> list[IntegrityViolation]:
    violations: list[IntegrityViolation] = []

    sites = session.execute(select(H5Site)).scalars().all()
    configs = session.execute(select(TaskSystemConfig)).scalars().all()
    plans = session.execute(select(TaskIssuePlan)).scalars().all()
    day_rules = session.execute(select(TaskIssuePlanDayRule)).scalars().all()
    quotas = session.execute(select(MemberTaskDayQuota)).scalars().all()
    batches = session.execute(select(MemberTaskBatch)).scalars().all()
    packages = session.execute(select(TaskPackageInstance)).scalars().all()
    items = session.execute(select(TaskPackageInstanceItem)).scalars().all()
    generation_runs = session.execute(select(TaskProductGenerationRun)).scalars().all()
    product_pools = session.execute(select(TaskProductPool)).scalars().all()
    ledger_entries = session.execute(select(WalletLedgerEntry)).scalars().all()
    product_pool_pairs = {(pool.id, pool.account_id) for pool in product_pools}

    config_pairs = {(config.account_id, config.site_id) for config in configs}
    for site in sites:
        if site.status != "active":
            continue
        if (site.account_id, site.id) not in config_pairs and (site.account_id, None) not in config_pairs:
            violations.append(
                IntegrityViolation(
                    kind="task_site_missing_config",
                    record_id=site.id,
                    account_id=site.account_id,
                    detail=f"active site '{site.site_key}' has no site-scoped or account-default task config",
                )
            )

    for config in configs:
        if _amount(config.whatsapp_binding_reward_amount) < Decimal("0.00"):
            violations.append(
                IntegrityViolation(
                    kind="task_system_config_negative_binding_reward",
                    record_id=config.id,
                    account_id=config.account_id,
                    detail=f"whatsapp_binding_reward_amount={_amount(config.whatsapp_binding_reward_amount)} is negative",
                )
            )
        if _amount(config.certified_recharge_threshold) < Decimal("0.00"):
            violations.append(
                IntegrityViolation(
                    kind="task_system_config_negative_certified_threshold",
                    record_id=config.id,
                    account_id=config.account_id,
                    detail=f"certified_recharge_threshold={_amount(config.certified_recharge_threshold)} is negative",
                )
            )
        if config.newbie_plan_id and not any(
            plan.id == config.newbie_plan_id and plan.account_id == config.account_id
            for plan in plans
        ):
            violations.append(
                IntegrityViolation(
                    kind="task_system_config_missing_newbie_plan",
                    record_id=config.id,
                    account_id=config.account_id,
                    detail=f"newbie_plan_id='{config.newbie_plan_id}' does not resolve inside account scope",
                )
            )
        if config.official_plan_id and not any(
            plan.id == config.official_plan_id and plan.account_id == config.account_id
            for plan in plans
        ):
            violations.append(
                IntegrityViolation(
                    kind="task_system_config_missing_official_plan",
                    record_id=config.id,
                    account_id=config.account_id,
                    detail=f"official_plan_id='{config.official_plan_id}' does not resolve inside account scope",
                )
            )

    day_rules_by_plan: dict[str, list[TaskIssuePlanDayRule]] = {}
    for rule in day_rules:
        day_rules_by_plan.setdefault(rule.plan_id, []).append(rule)

    for plan in plans:
        if plan.status == "active" and not day_rules_by_plan.get(plan.id):
            violations.append(
                IntegrityViolation(
                    kind="task_issue_plan_missing_day_rule",
                    record_id=plan.id,
                    account_id=plan.account_id,
                    detail=f"active plan '{plan.name}' has no day rules",
                )
            )
        if plan.default_product_pool_id and (plan.default_product_pool_id, plan.account_id) not in product_pool_pairs:
            violations.append(
                IntegrityViolation(
                    kind="task_issue_plan_missing_default_product_pool",
                    record_id=plan.id,
                    account_id=plan.account_id,
                    detail=(
                        f"default_product_pool_id='{plan.default_product_pool_id}' "
                        "does not resolve inside account scope"
                    ),
                )
            )

    for rule in day_rules:
        if rule.package_count <= 0:
            violations.append(
                IntegrityViolation(
                    kind="task_issue_plan_day_rule_invalid_package_count",
                    record_id=rule.id,
                    account_id=rule.account_id,
                    detail=f"package_count={rule.package_count} must be > 0",
                )
            )
        if _amount(rule.day_total_amount) <= Decimal("0.00"):
            violations.append(
                IntegrityViolation(
                    kind="task_issue_plan_day_rule_invalid_total_amount",
                    record_id=rule.id,
                    account_id=rule.account_id,
                    detail=f"day_total_amount={_amount(rule.day_total_amount)} must be > 0",
                )
            )
        if rule.amount_allocation_mode == "manual":
            try:
                manual_total = _sum_amounts(rule.package_amounts_json)
            except (InvalidOperation, ValueError) as exc:
                manual_total = Decimal("-1.00")
                violations.append(
                    IntegrityViolation(
                        kind="task_issue_plan_day_rule_manual_total_mismatch",
                        record_id=rule.id,
                        account_id=rule.account_id,
                        detail=f"manual package amounts are invalid: {exc}",
                    )
                )
            else:
                if manual_total != _amount(rule.day_total_amount):
                    violations.append(
                        IntegrityViolation(
                            kind="task_issue_plan_day_rule_manual_total_mismatch",
                            record_id=rule.id,
                            account_id=rule.account_id,
                            detail=(
                                f"manual total={manual_total} does not match "
                                f"day_total_amount={_amount(rule.day_total_amount)}"
                            ),
                        )
                    )
        if rule.product_pool_id and (rule.product_pool_id, rule.account_id) not in product_pool_pairs:
            violations.append(
                IntegrityViolation(
                    kind="task_issue_plan_day_rule_missing_product_pool",
                    record_id=rule.id,
                    account_id=rule.account_id,
                    detail=f"product_pool_id='{rule.product_pool_id}' does not resolve inside account scope",
                )
            )

    quotas_by_id = {quota.id: quota for quota in quotas}
    for quota in quotas:
        try:
            quota_total = _sum_amounts(quota.package_amounts_json)
        except (InvalidOperation, ValueError) as exc:
            violations.append(
                IntegrityViolation(
                    kind="member_task_day_quota_total_mismatch",
                    record_id=quota.id,
                    account_id=quota.account_id,
                    detail=f"quota package amounts are invalid: {exc}",
                )
            )
            continue
        if quota_total != _amount(quota.day_total_amount):
            violations.append(
                IntegrityViolation(
                    kind="member_task_day_quota_total_mismatch",
                    record_id=quota.id,
                    account_id=quota.account_id,
                    detail=(
                        f"quota package total={quota_total} does not match "
                        f"day_total_amount={_amount(quota.day_total_amount)}"
                    ),
                )
            )
        if quota.product_pool_id and (quota.product_pool_id, quota.account_id) not in product_pool_pairs:
            violations.append(
                IntegrityViolation(
                    kind="member_task_day_quota_missing_product_pool",
                    record_id=quota.id,
                    account_id=quota.account_id,
                    detail=f"product_pool_id='{quota.product_pool_id}' does not resolve inside account scope",
                )
            )
        if quota.issued_batch_id and not any(
            batch.id == quota.issued_batch_id and batch.account_id == quota.account_id
            for batch in batches
        ):
            violations.append(
                IntegrityViolation(
                    kind="member_task_day_quota_missing_issued_batch",
                    record_id=quota.id,
                    account_id=quota.account_id,
                    detail=f"issued_batch_id='{quota.issued_batch_id}' does not resolve inside account scope",
                )
            )
        if quota.status == "locked":
            if not quota.issued_batch_id:
                violations.append(
                    IntegrityViolation(
                        kind="member_task_day_quota_locked_missing_batch_link",
                        record_id=quota.id,
                        account_id=quota.account_id,
                        detail="locked quota is missing issued_batch_id",
                    )
                )
            if quota.generated_at is None:
                violations.append(
                    IntegrityViolation(
                        kind="member_task_day_quota_locked_missing_generated_at",
                        record_id=quota.id,
                        account_id=quota.account_id,
                        detail="locked quota is missing generated_at",
                    )
                )
            if quota.locked_at is None:
                violations.append(
                    IntegrityViolation(
                        kind="member_task_day_quota_locked_missing_locked_at",
                        record_id=quota.id,
                        account_id=quota.account_id,
                        detail="locked quota is missing locked_at",
                    )
                )

    items_by_package: dict[str, list[TaskPackageInstanceItem]] = {}
    packages_by_batch: dict[str, list[TaskPackageInstance]] = {}
    ledger_entries_by_id = {entry.id: entry for entry in ledger_entries}
    batch_product_counts: dict[tuple[str, str], int] = {}
    package_product_counts: dict[tuple[str, str], int] = {}
    for item in items:
        items_by_package.setdefault(item.package_instance_id, []).append(item)
        if item.batch_id and item.product_id:
            batch_key = (item.batch_id, item.product_id)
            batch_product_counts[batch_key] = batch_product_counts.get(batch_key, 0) + 1
        if item.product_id:
            package_key = (item.package_instance_id, item.product_id)
            package_product_counts[package_key] = package_product_counts.get(package_key, 0) + 1
        if item.status == "completed" and not item.debit_ledger_id:
            violations.append(
                IntegrityViolation(
                    kind="task_package_item_completed_missing_debit_ledger",
                    record_id=item.id,
                    account_id=item.account_id,
                    detail="completed item is missing debit_ledger_id",
                )
            )
        if item.debit_ledger_id:
            expected_source_type = f"task_item_purchase_{(item.item_origin or 'system_generated').strip().lower()}"
            ledger_entry = ledger_entries_by_id.get(item.debit_ledger_id)
            if ledger_entry is None:
                violations.append(
                    IntegrityViolation(
                        kind="task_package_item_missing_purchase_ledger_entry",
                        record_id=item.id,
                        account_id=item.account_id,
                        detail=f"debit_ledger_id='{item.debit_ledger_id}' does not exist",
                    )
                )
            else:
                if (
                    ledger_entry.ledger_type != "system"
                    or ledger_entry.transaction_type != "purchase"
                    or ledger_entry.direction != "debit"
                ):
                    violations.append(
                        IntegrityViolation(
                            kind="task_package_item_invalid_purchase_contract",
                            record_id=item.id,
                            account_id=item.account_id,
                            detail=(
                                "purchase ledger contract is invalid: "
                                f"ledger_type='{ledger_entry.ledger_type}', "
                                f"transaction_type='{ledger_entry.transaction_type}', "
                                f"direction='{ledger_entry.direction}'"
                            ),
                        )
                    )
                if ledger_entry.source_type != expected_source_type:
                    violations.append(
                        IntegrityViolation(
                            kind="task_package_item_invalid_purchase_source_type",
                            record_id=item.id,
                            account_id=item.account_id,
                            detail=(
                                f"purchase ledger source_type='{ledger_entry.source_type}' "
                                f"!= expected '{expected_source_type}'"
                            ),
                        )
                    )
        if item.item_origin == "manual_added" and not item.manual_add_log_id:
            violations.append(
                IntegrityViolation(
                    kind="task_package_item_manual_added_missing_log",
                    record_id=item.id,
                    account_id=item.account_id,
                    detail="manual added item is missing manual_add_log_id",
                )
            )

    for package in packages:
        if package.batch_id:
            packages_by_batch.setdefault(package.batch_id, []).append(package)

    for (batch_id, product_id), count in batch_product_counts.items():
        if count > 1:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_duplicate_product",
                    record_id=batch_id,
                    account_id=None,
                    detail=f"batch contains duplicate product_id='{product_id}' ({count} times)",
                )
            )
    for (package_id, product_id), count in package_product_counts.items():
        if count > 1:
            violations.append(
                IntegrityViolation(
                    kind="task_package_duplicate_product",
                    record_id=package_id,
                    account_id=None,
                    detail=f"package contains duplicate product_id='{product_id}' ({count} times)",
                )
            )

    for batch in batches:
        batch_packages = sorted(
            packages_by_batch.get(batch.id, []),
            key=lambda package: (
                int(package.batch_index or 0),
                package.created_at.isoformat() if package.created_at is not None else "",
                package.id,
            ),
        )
        completed_package_count = sum(1 for package in batch_packages if package.status == "completed")
        next_package = next((package for package in batch_packages if package.status != "completed"), None)
        expected_current_package_index = (
            max(int(batch.package_count or 0), completed_package_count)
            if next_package is None
            else int(next_package.batch_index or (completed_package_count + 1))
        )
        if int(batch.completed_package_count or 0) != completed_package_count:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_completed_package_count_mismatch",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail=(
                        f"completed_package_count={int(batch.completed_package_count or 0)} != "
                        f"actual completed package count={completed_package_count}"
                    ),
                )
            )
        if int(batch.current_package_index or 0) != expected_current_package_index:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_current_package_index_mismatch",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail=(
                        f"current_package_index={int(batch.current_package_index or 0)} != "
                        f"expected current package index={expected_current_package_index}"
                    ),
                )
            )
        expected_batch_status = "completed" if batch_packages and next_package is None else batch.status
        if batch_packages and expected_batch_status != batch.status:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_status_mismatch",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail=f"batch status='{batch.status}' != expected aggregate status='{expected_batch_status}'",
                )
            )
        if batch_packages and next_package is None and batch.completed_at is None:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_completed_missing_completed_at",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail="completed batch is missing completed_at",
                )
            )

        quota = quotas_by_id.get(batch.quota_id or "")
        if quota is not None:
            if batch_packages and next_package is None and quota.status != "completed":
                violations.append(
                    IntegrityViolation(
                        kind="member_task_batch_completed_quota_status_mismatch",
                        record_id=batch.id,
                        account_id=batch.account_id,
                        detail=f"linked quota status='{quota.status}' must be 'completed' when batch is completed",
                    )
                )
            minimum = _amount(quota.day_total_amount) - _amount(quota.tolerance_amount)
            maximum = _amount(quota.day_total_amount) + _amount(quota.tolerance_amount)
            actual = _amount(batch.system_generated_amount)
            if actual < minimum or actual > maximum:
                violations.append(
                    IntegrityViolation(
                        kind="member_task_batch_system_amount_out_of_tolerance",
                        record_id=batch.id,
                        account_id=batch.account_id,
                        detail=(
                            f"system_generated_amount={actual} outside allowed range "
                            f"[{minimum}, {maximum}]"
                        ),
                    )
                )
        expected_manual_added = _amount(
            sum(
                (
                    _amount(package.manual_added_amount)
                    for package in packages_by_batch.get(batch.id, [])
                ),
                start=Decimal("0.00"),
            )
        )
        if _amount(batch.manual_added_amount) != expected_manual_added:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_manual_added_amount_mismatch",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail=(
                        f"manual_added_amount={_amount(batch.manual_added_amount)} != "
                        f"sum(package.manual_added_amount)={expected_manual_added}"
                    ),
                )
            )
        expected_effective = _amount(batch.system_generated_amount) + _amount(batch.manual_added_amount)
        if _amount(batch.effective_day_amount) != expected_effective:
            violations.append(
                IntegrityViolation(
                    kind="member_task_batch_effective_amount_mismatch",
                    record_id=batch.id,
                    account_id=batch.account_id,
                    detail=(
                        f"effective_day_amount={_amount(batch.effective_day_amount)} != "
                        f"system_generated_amount+manual_added_amount={expected_effective}"
                    ),
                )
            )

    for package in packages:
        ordered_items = sorted(
            items_by_package.get(package.id, []),
            key=lambda item: (
                int(item.sort_order or 0),
                item.created_at.isoformat() if item.created_at is not None else "",
                item.id,
            ),
        )
        next_incomplete = next((item for item in ordered_items if item.completed_at is None), None)
        expected_current_item_index = ordered_items.index(next_incomplete) + 1 if next_incomplete is not None else 0
        expected_visible_item_id = None if package.status == "pending_claim" or next_incomplete is None else next_incomplete.id
        if int(package.current_item_index or 0) != expected_current_item_index:
            violations.append(
                IntegrityViolation(
                    kind="task_package_current_item_index_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"current_item_index={int(package.current_item_index or 0)} != "
                        f"expected runtime index={expected_current_item_index}"
                    ),
                )
            )
        if package.visible_item_id != expected_visible_item_id:
            violations.append(
                IntegrityViolation(
                    kind="task_package_visible_item_pointer_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"visible_item_id='{package.visible_item_id}' != "
                        f"expected '{expected_visible_item_id}'"
                    ),
                )
            )

        visible_item_ids = sorted(item.id for item in ordered_items if item.visible_to_user)
        expected_visible_ids = [expected_visible_item_id] if expected_visible_item_id is not None else []
        if visible_item_ids != expected_visible_ids:
            violations.append(
                IntegrityViolation(
                    kind="task_package_visible_item_flag_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"visible_to_user item ids={visible_item_ids} != "
                        f"expected visible ids={expected_visible_ids}"
                    ),
                )
            )

        for item in ordered_items:
            expected_status = (
                "completed"
                if item.completed_at is not None
                else "available"
                if expected_visible_item_id == item.id
                else "pending"
            )
            if item.status != expected_status:
                violations.append(
                    IntegrityViolation(
                        kind="task_package_item_status_mismatch",
                        record_id=item.id,
                        account_id=item.account_id,
                        detail=f"item status='{item.status}' != expected runtime status='{expected_status}'",
                    )
                )

        required_items = [item for item in ordered_items if item.is_required]
        if int(package.required_item_count or 0) != len(required_items):
            violations.append(
                IntegrityViolation(
                    kind="task_package_required_item_count_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"required_item_count={int(package.required_item_count or 0)} != "
                        f"actual required item count={len(required_items)}"
                    ),
                )
            )
        completed_required_count = sum(1 for item in required_items if item.completed_at is not None)
        if int(package.completed_required_item_count or 0) != completed_required_count:
            violations.append(
                IntegrityViolation(
                    kind="task_package_completed_required_item_count_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"completed_required_item_count={int(package.completed_required_item_count or 0)} != "
                        f"actual completed required count={completed_required_count}"
                    ),
                )
            )
        if package.status == "completed" and package.completed_at is None:
            violations.append(
                IntegrityViolation(
                    kind="task_package_completed_missing_completed_at",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail="completed package is missing completed_at",
                )
            )

        has_seen_manual_added = False
        for item in ordered_items:
            is_manual_added = (item.item_origin or "").strip().lower() == "manual_added"
            if is_manual_added:
                has_seen_manual_added = True
                continue
            if has_seen_manual_added:
                violations.append(
                    IntegrityViolation(
                        kind="task_package_manual_items_not_appended",
                        record_id=package.id,
                        account_id=package.account_id,
                        detail=(
                            "manual added items must stay at the package tail, "
                            f"but item '{item.id}' with origin '{item.item_origin}' appears after them"
                        ),
                    )
                )
                break

        manual_added_total = _amount(
            sum(
                (
                    _amount(item.price or item.price_snapshot)
                    for item in items_by_package.get(package.id, [])
                    if item.item_origin == "manual_added"
                ),
                start=Decimal("0.00"),
            )
        )
        if _amount(package.manual_added_amount) != manual_added_total:
            violations.append(
                IntegrityViolation(
                    kind="task_package_manual_added_amount_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"manual_added_amount={_amount(package.manual_added_amount)} != "
                        f"sum(manual_added item prices)={manual_added_total}"
                    ),
                )
            )
        expected_effective = _amount(package.system_generated_amount) + _amount(package.manual_added_amount)
        if _amount(package.effective_amount) != expected_effective:
            violations.append(
                IntegrityViolation(
                    kind="task_package_effective_amount_mismatch",
                    record_id=package.id,
                    account_id=package.account_id,
                    detail=(
                        f"effective_amount={_amount(package.effective_amount)} != "
                        f"system_generated_amount+manual_added_amount={expected_effective}"
                    ),
                )
            )
        if package.status == "completed":
            required_items = [item for item in items_by_package.get(package.id, []) if item.is_required]
            if any(item.status != "completed" for item in required_items):
                violations.append(
                    IntegrityViolation(
                        kind="task_package_completed_missing_required_items",
                        record_id=package.id,
                        account_id=package.account_id,
                        detail="completed package still has required items not completed",
                    )
                )
            if not package.reward_ledger_id:
                violations.append(
                    IntegrityViolation(
                        kind="task_package_completed_missing_reward_ledger",
                        record_id=package.id,
                        account_id=package.account_id,
                        detail="completed package is missing reward_ledger_id",
                    )
                )
            else:
                reward_ledger = ledger_entries_by_id.get(package.reward_ledger_id)
                if reward_ledger is None:
                    violations.append(
                        IntegrityViolation(
                            kind="task_package_missing_reward_ledger_entry",
                            record_id=package.id,
                            account_id=package.account_id,
                            detail=f"reward_ledger_id='{package.reward_ledger_id}' does not exist",
                        )
                    )
                else:
                    if reward_ledger.ledger_type != "task" or reward_ledger.transaction_type != "task_reward":
                        violations.append(
                            IntegrityViolation(
                                kind="task_package_invalid_reward_ledger_contract",
                                record_id=package.id,
                                account_id=package.account_id,
                                detail=(
                                    f"reward ledger contract is invalid: ledger_type='{reward_ledger.ledger_type}', "
                                    f"transaction_type='{reward_ledger.transaction_type}'"
                                ),
                            )
                        )
                    if reward_ledger.direction != "credit":
                        violations.append(
                            IntegrityViolation(
                                kind="task_package_invalid_reward_ledger_direction",
                                record_id=package.id,
                                account_id=package.account_id,
                                detail=f"reward ledger direction='{reward_ledger.direction}' must be 'credit'",
                            )
                        )
                    if reward_ledger.source_type != "task_reward":
                        violations.append(
                            IntegrityViolation(
                                kind="task_package_invalid_reward_ledger_source_type",
                                record_id=package.id,
                                account_id=package.account_id,
                                detail=(
                                    f"reward ledger source_type='{reward_ledger.source_type}' "
                                    "must be 'task_reward'"
                                ),
                            )
                        )
                    if reward_ledger.fund_type != "task" or _amount(reward_ledger.task_amount) != _amount(reward_ledger.amount):
                        violations.append(
                            IntegrityViolation(
                                kind="task_package_invalid_reward_ledger_fund_type",
                                record_id=package.id,
                                account_id=package.account_id,
                                detail=(
                                    f"reward ledger fund_type='{reward_ledger.fund_type}', "
                                    f"task_amount={_amount(reward_ledger.task_amount)} "
                                    f"must mirror amount={_amount(reward_ledger.amount)} in task ledger"
                                ),
                            )
                        )
            expected_reward_amount = (Decimal(package.effective_amount or 0) * Decimal(package.reward_ratio_snapshot or 0)).quantize(
                TWOPLACES
            )
            if _amount(package.reward_amount_final) != expected_reward_amount:
                violations.append(
                    IntegrityViolation(
                        kind="task_package_reward_amount_mismatch",
                        record_id=package.id,
                        account_id=package.account_id,
                        detail=(
                            f"reward_amount_final={_amount(package.reward_amount_final)} != "
                            f"effective_amount*reward_ratio_snapshot={expected_reward_amount}"
                        ),
                    )
                )

    run_scope_counts: dict[tuple[str, str | None], int] = {}
    batches_by_id = {batch.id: batch for batch in batches}
    for run in generation_runs:
        scope_key = (run.quota_id, run.batch_id)
        run_scope_counts[scope_key] = run_scope_counts.get(scope_key, 0) + 1
        if run.batch_id not in batches_by_id:
            violations.append(
                IntegrityViolation(
                    kind="task_generation_run_missing_batch",
                    record_id=run.id,
                    account_id=run.account_id,
                    detail=f"batch_id='{run.batch_id}' does not resolve inside account scope",
                )
            )
        quota = quotas_by_id.get(run.quota_id)
        if quota is None:
            violations.append(
                IntegrityViolation(
                    kind="task_generation_run_missing_quota",
                    record_id=run.id,
                    account_id=run.account_id,
                    detail=f"quota_id='{run.quota_id}' does not resolve inside account scope",
                )
            )
        if (run.product_pool_id, run.account_id) not in product_pool_pairs:
            violations.append(
                IntegrityViolation(
                    kind="task_generation_run_missing_product_pool",
                    record_id=run.id,
                    account_id=run.account_id,
                    detail=f"product_pool_id='{run.product_pool_id}' does not resolve inside account scope",
                )
            )
        batch = batches_by_id.get(run.batch_id)
        if batch is not None:
            actual_package_count = len(packages_by_batch.get(batch.id, []))
            actual_item_count = sum(len(items_by_package.get(package.id, [])) for package in packages_by_batch.get(batch.id, []))
            if int(run.generated_package_count or 0) != actual_package_count:
                violations.append(
                    IntegrityViolation(
                        kind="task_generation_run_package_count_mismatch",
                        record_id=run.id,
                        account_id=run.account_id,
                        detail=(
                            f"generated_package_count={int(run.generated_package_count or 0)} != "
                            f"actual batch package count={actual_package_count}"
                        ),
                    )
                )
            if int(run.generated_item_count or 0) != actual_item_count:
                violations.append(
                    IntegrityViolation(
                        kind="task_generation_run_item_count_mismatch",
                        record_id=run.id,
                        account_id=run.account_id,
                        detail=(
                            f"generated_item_count={int(run.generated_item_count or 0)} != "
                            f"actual batch item count={actual_item_count}"
                        ),
                    )
                )
            if _amount(run.actual_day_system_amount) != _amount(batch.system_generated_amount):
                violations.append(
                    IntegrityViolation(
                        kind="task_generation_run_actual_amount_mismatch",
                        record_id=run.id,
                        account_id=run.account_id,
                        detail=(
                            f"actual_day_system_amount={_amount(run.actual_day_system_amount)} != "
                            f"batch.system_generated_amount={_amount(batch.system_generated_amount)}"
                        ),
                    )
                )
        if quota is not None:
            minimum = _amount(quota.day_total_amount) - _amount(quota.tolerance_amount)
            maximum = _amount(quota.day_total_amount) + _amount(quota.tolerance_amount)
            actual = _amount(run.actual_day_system_amount)
            if actual < minimum or actual > maximum:
                violations.append(
                    IntegrityViolation(
                        kind="task_generation_run_out_of_quota_tolerance",
                        record_id=run.id,
                        account_id=run.account_id,
                        detail=(
                            f"actual_day_system_amount={actual} outside quota allowed range "
                            f"[{minimum}, {maximum}]"
                        ),
                    )
                )
    for (quota_id, batch_id), count in run_scope_counts.items():
        if count > 1:
            violations.append(
                IntegrityViolation(
                    kind="task_generation_run_duplicate_scope",
                    record_id=batch_id or quota_id,
                    account_id=None,
                    detail=f"generation runs duplicated for quota_id='{quota_id}' batch_id='{batch_id}' ({count} runs)",
                )
            )

    for wallet_violation in collect_wallet_invariant_violations(session):
        violations.append(
            IntegrityViolation(
                kind=wallet_violation.kind,
                record_id=wallet_violation.record_id,
                account_id=wallet_violation.account_id,
                detail=wallet_violation.detail,
            )
        )

    for ledger_entry in ledger_entries:
        if ledger_entry.transaction_type != "task_to_system_transfer":
            continue
        if ledger_entry.ledger_type == "task":
            if (
                ledger_entry.direction != "debit"
                or ledger_entry.source_type != "task_transfer_bonus"
                or ledger_entry.fund_type != "task"
            ):
                violations.append(
                    IntegrityViolation(
                        kind="wallet_task_transfer_invalid_task_contract",
                        record_id=ledger_entry.id,
                        account_id=ledger_entry.account_id,
                        detail=(
                            "task transfer task-ledger contract invalid: "
                            f"direction='{ledger_entry.direction}', "
                            f"source_type='{ledger_entry.source_type}', "
                            f"fund_type='{ledger_entry.fund_type}'"
                        ),
                    )
                )
        elif ledger_entry.ledger_type == "system":
            if (
                ledger_entry.direction != "credit"
                or ledger_entry.source_type != "task_transfer_bonus"
                or ledger_entry.fund_type != "bonus"
            ):
                violations.append(
                    IntegrityViolation(
                        kind="wallet_task_transfer_invalid_system_contract",
                        record_id=ledger_entry.id,
                        account_id=ledger_entry.account_id,
                        detail=(
                            "task transfer system-ledger contract invalid: "
                            f"direction='{ledger_entry.direction}', "
                            f"source_type='{ledger_entry.source_type}', "
                            f"fund_type='{ledger_entry.fund_type}'"
                        ),
                    )
                )

    return violations


def build_task_system_v3_integrity_report(session: Session) -> dict[str, Any]:
    violations = collect_task_system_v3_integrity_violations(session)
    return {
        "ok": len(violations) == 0,
        "violation_count": len(violations),
        "violations": [asdict(item) for item in violations],
    }


def _load_session_factory():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()


def main() -> int:
    try:
        session_factory = _load_session_factory()
        with session_factory() as session:
            report = build_task_system_v3_integrity_report(session)
    except Exception as exc:  # pragma: no cover
        error_report = {
            "ok": False,
            "error": str(exc),
            "hint": (
                "Ensure DATABASE_URL points to a reachable database with a working driver, "
                "run alembic upgrade head before checking a fresh database, "
                "or run with TEST_MODE=true for a test-only sqlite context."
            ),
            "test_mode": os.environ.get("TEST_MODE"),
        }
        print(json.dumps(error_report, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

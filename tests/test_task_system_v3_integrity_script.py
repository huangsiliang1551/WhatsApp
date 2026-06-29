from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    Account,
    AppUser,
    H5Site,
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    TaskProductGenerationRun,
    TaskProductPool,
    TaskProductPoolItem,
    TaskSystemConfig,
    WalletAccount,
    WalletLedgerEntry,
    utc_now,
)
import scripts.check_task_system_v3_integrity as integrity_script
from scripts.check_task_system_v3_integrity import build_task_system_v3_integrity_report


def _seed_valid_task_system_scope(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as session:
        now = utc_now()
        account = Account(
            account_id="acct-task-integrity",
            display_name="Task Integrity",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        site = H5Site(
            account_id=account.account_id,
            site_key="task-integrity",
            domain="task-integrity.example.com",
            brand_name="Task Integrity",
            default_language="zh-CN",
            status="active",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="user-task-integrity",
            registration_site_id=site.id,
            display_name="Task Integrity User",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=True,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        session.add_all([account, site, user])
        session.flush()

        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Integrity Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        session.add(
            TaskProductPoolItem(
                account_id=account.account_id,
                pool_id=pool.id,
                product_id="integrity-product-1",
                product_name="Integrity Product 1",
                image_url="https://example.com/integrity-1.png",
                price=Decimal("100.00"),
                currency="USD",
                weight=100,
                status="active",
                sort_order=1,
            )
        )

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Integrity Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            require_previous_batch_completed=True,
            max_unfinished_batches=1,
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("0.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add(plan)
        session.flush()

        config = TaskSystemConfig(
            account_id=account.account_id,
            site_id=None,
            status="active",
            whatsapp_binding_reward_enabled=True,
            whatsapp_binding_reward_amount=Decimal("20.00"),
            whatsapp_binding_reward_wallet_type="task_balance",
            whatsapp_binding_reward_currency="USD",
            certified_member_enabled=True,
            certified_recharge_threshold=Decimal("50.00"),
            certified_recharge_scope="real_recharge",
            auto_certify_on_recharge=True,
            newbie_task_enabled=True,
            newbie_plan_id=plan.id,
            newbie_auto_popup=True,
            official_plan_id=plan.id,
            show_task_balance_transfer_prompt=True,
            min_task_balance_transfer_prompt_amount=Decimal("1.00"),
            max_active_batches_per_user=1,
            max_active_packages_per_user=1,
        )
        day_rule = TaskIssuePlanDayRule(
            account_id=account.account_id,
            site_id=site.id,
            plan_id=plan.id,
            day_no=1,
            package_count=1,
            day_total_amount=Decimal("100.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["100.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.10"),
            status="active",
        )
        session.add_all([config, day_rule])
        session.flush()

        batch = MemberTaskBatch(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=1,
            completed_package_count=1,
            current_package_index=1,
            planned_amount=Decimal("100.00"),
            system_generated_amount=Decimal("100.00"),
            manual_added_amount=Decimal("0.00"),
            effective_day_amount=Decimal("100.00"),
            reward_ratio_snapshot=Decimal("0.10"),
            status="completed",
            products_generated=True,
            completed_at=now,
        )
        session.add(batch)
        session.flush()

        quota = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=1,
            day_total_amount=Decimal("100.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["100.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.10"),
            status="completed",
            issued_batch_id=batch.id,
        )
        session.add(quota)
        session.flush()

        batch.quota_id = quota.id
        session.add(batch)

        template = TaskPackageTemplate(
            account_id=account.account_id,
            name="Integrity Template",
            title="Integrity Template",
            description="Integrity template",
            package_type="official",
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
        )
        session.add(template)
        session.flush()

        template_item = TaskPackageTemplateItem(
            account_id=account.account_id,
            template_id=template.id,
            sort_order=1,
            product_name="Integrity Product 1",
            image_url="https://example.com/integrity-1.png",
            price=Decimal("100.00"),
            currency="USD",
        )
        session.add(template_item)
        session.flush()

        package = TaskPackageInstance(
            account_id=account.account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site.id,
            batch_id=batch.id,
            quota_id=quota.id,
            batch_day_no=1,
            batch_index=1,
            batch_total=1,
            planned_amount=Decimal("100.00"),
            system_generated_amount=Decimal("100.00"),
            manual_added_amount=Decimal("0.00"),
            effective_amount=Decimal("100.00"),
            status="completed",
            reward_ratio_snapshot=Decimal("0.10"),
            reward_amount_final=Decimal("10.00"),
            reward_ledger_id="reward-ledger-1",
            completed_at=now,
            current_item_index=0,
            required_item_count=1,
            completed_required_item_count=1,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.flush()

        session.add(
            TaskPackageInstanceItem(
                account_id=account.account_id,
                batch_id=batch.id,
                quota_id=quota.id,
                package_instance_id=package.id,
                template_item_id=template_item.id,
                item_origin="system_generated",
                is_required=True,
                product_pool_id=pool.id,
                product_id="integrity-product-1",
                product_name_snapshot="Integrity Product 1",
                product_image_url_snapshot="https://example.com/integrity-1.png",
                price_snapshot=Decimal("100.00"),
                sort_order=1,
                product_name="Integrity Product 1",
                image_url="https://example.com/integrity-1.png",
                price=Decimal("100.00"),
                currency="USD",
                status="completed",
                visible_to_user=False,
                debit_ledger_id="debit-ledger-1",
                completed_at=now,
            )
        )

        session.add(
            TaskProductGenerationRun(
                account_id=account.account_id,
                site_id=site.id,
                user_id=user.id,
                quota_id=quota.id,
                batch_id=batch.id,
                product_pool_id=pool.id,
                selection_seed="seed-1",
                selection_algorithm="weighted_random_unique_v1",
                target_day_amount=Decimal("100.00"),
                actual_day_system_amount=Decimal("100.00"),
                tolerance_amount=Decimal("0.00"),
                generated_package_count=1,
                generated_item_count=1,
                status="success",
                idempotency_key="run-1",
            )
        )

        wallet = WalletAccount(
            id="wallet-task-integrity",
            account_id=account.account_id,
            user_id=user.id,
            system_balance=Decimal("10.00"),
            system_cash_balance=Decimal("10.00"),
            system_bonus_balance=Decimal("0.00"),
            frozen_balance=Decimal("0.00"),
            system_cash_frozen=Decimal("0.00"),
            system_bonus_frozen=Decimal("0.00"),
            task_balance=Decimal("0.00"),
            currency="USD",
            withdraw_threshold=Decimal("100.00"),
        )
        session.add(wallet)
        session.flush()
        session.add(
            WalletLedgerEntry(
                id="reward-ledger-1",
                account_id=account.account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="task",
                transaction_type="task_reward",
                direction="credit",
                amount=Decimal("10.00"),
                currency="USD",
                status="paid",
                source_type="task_reward",
                fund_type="task",
                cash_amount=Decimal("0.00"),
                bonus_amount=Decimal("0.00"),
                task_amount=Decimal("10.00"),
                task_balance_before=Decimal("0.00"),
                task_balance_after=Decimal("10.00"),
                is_bonus=False,
                idempotency_key="wallet-task-reward-1",
                reference_type="task_package_instance",
                reference_id=package.id,
            )
        )
        session.add(
            WalletLedgerEntry(
                id="debit-ledger-1",
                account_id=account.account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="system",
                transaction_type="purchase",
                direction="debit",
                amount=Decimal("100.00"),
                currency="USD",
                status="paid",
                source_type="task_item_purchase_system_generated",
                fund_type="cash",
                cash_amount=Decimal("100.00"),
                bonus_amount=Decimal("0.00"),
                balance_before=Decimal("110.00"),
                balance_after=Decimal("10.00"),
                cash_balance_before=Decimal("110.00"),
                cash_balance_after=Decimal("10.00"),
                bonus_balance_before=Decimal("0.00"),
                bonus_balance_after=Decimal("0.00"),
                is_bonus=False,
                idempotency_key="wallet-task-item-debit-1",
                reference_type="member_order",
                reference_id="order-integrity-1",
            )
        )
        session.add(
            WalletLedgerEntry(
                account_id=account.account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="system",
                transaction_type="manual_recharge",
                direction="credit",
                amount=Decimal("10.00"),
                currency="USD",
                status="paid",
                source_type="manual_real_recharge",
                fund_type="cash",
                cash_amount=Decimal("10.00"),
                bonus_amount=Decimal("0.00"),
                is_bonus=False,
                idempotency_key="wallet-integrity-ledger-1",
            )
        )

        session.commit()


def test_task_system_v3_integrity_script_executes_as_a_direct_script() -> None:
    script_path = Path("scripts/check_task_system_v3_integrity.py")
    env = os.environ.copy()
    env["TEST_MODE"] = "true"
    env.setdefault("PYTHONUTF8", "1")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode in {0, 1, 2}, result.stderr
    combined_output = (result.stdout + result.stderr).strip()
    assert "ModuleNotFoundError" not in combined_output
    assert "No module named 'scripts'" not in combined_output


def test_task_system_v3_integrity_script_subprocess_returns_zero_for_clean_sqlite_scope() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "task_system_v3_integrity.db"
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        try:
            _seed_valid_task_system_scope(factory)
        finally:
            engine.dispose()

        script_path = Path("scripts/check_task_system_v3_integrity.py")
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
        env["TEST_MODE"] = "false"
        env.setdefault("PYTHONUTF8", "1")

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["violation_count"] == 0


def test_task_system_v3_integrity_report_passes_for_valid_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        report = build_task_system_v3_integrity_report(session)

    assert report["ok"] is True
    assert report["violation_count"] == 0
    assert report["violations"] == []


def test_task_system_v3_integrity_report_detects_task_item_purchase_source_type_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        debit_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == "debit-ledger-1").one()
        debit_entry.source_type = "purchase"
        session.add(debit_entry)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_item_invalid_purchase_source_type" in kinds


def test_task_system_v3_integrity_report_detects_task_item_purchase_contract_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        debit_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == "debit-ledger-1").one()
        debit_entry.transaction_type = "task_reward"
        debit_entry.direction = "credit"
        session.add(debit_entry)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_item_invalid_purchase_contract" in kinds


def test_task_system_v3_integrity_report_detects_task_reward_ledger_source_type_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        reward_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == "reward-ledger-1").one()
        reward_entry.source_type = "manual_reward"
        session.add(reward_entry)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_invalid_reward_ledger_source_type" in kinds


def test_task_system_v3_integrity_report_detects_task_reward_ledger_fund_type_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        reward_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == "reward-ledger-1").one()
        reward_entry.fund_type = "bonus"
        reward_entry.task_amount = Decimal("0.00")
        session.add(reward_entry)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_invalid_reward_ledger_fund_type" in kinds


def test_task_system_v3_integrity_report_detects_task_transfer_contract_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        wallet = session.query(WalletAccount).filter(WalletAccount.id == "wallet-task-integrity").one()
        user = session.query(AppUser).filter(AppUser.public_user_id == "user-task-integrity").one()

        session.add(
            WalletLedgerEntry(
                id="transfer-task-ledger-1",
                account_id=wallet.account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="task",
                transaction_type="task_to_system_transfer",
                direction="debit",
                amount=Decimal("5.00"),
                currency="USD",
                status="paid",
                source_type="task_transfer_bonus",
                fund_type="task",
                cash_amount=Decimal("0.00"),
                bonus_amount=Decimal("0.00"),
                task_amount=Decimal("5.00"),
                task_balance_before=Decimal("10.00"),
                task_balance_after=Decimal("5.00"),
                is_bonus=False,
                idempotency_key="transfer-task-ledger-1",
                reference_type="wallet_transfer_request",
                reference_id="transfer-ref-1",
            )
        )
        session.add(
            WalletLedgerEntry(
                id="transfer-system-ledger-1",
                account_id=wallet.account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="system",
                transaction_type="task_to_system_transfer",
                direction="credit",
                amount=Decimal("5.00"),
                currency="USD",
                status="paid",
                source_type="task_transfer_bonus",
                fund_type="bonus",
                cash_amount=Decimal("0.00"),
                bonus_amount=Decimal("5.00"),
                task_amount=Decimal("0.00"),
                balance_before=Decimal("10.00"),
                balance_after=Decimal("15.00"),
                cash_balance_before=Decimal("10.00"),
                cash_balance_after=Decimal("10.00"),
                bonus_balance_before=Decimal("0.00"),
                bonus_balance_after=Decimal("5.00"),
                is_bonus=True,
                idempotency_key="transfer-system-ledger-1",
                reference_type="wallet_transfer_request",
                reference_id="transfer-ref-1",
            )
        )
        session.commit()

        system_transfer = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == "transfer-system-ledger-1").one()
        system_transfer.source_type = "task_reward"
        system_transfer.fund_type = "cash"
        session.add(system_transfer)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "wallet_task_transfer_invalid_system_contract" in kinds


def test_task_system_v3_integrity_report_detects_runtime_visible_item_pointer_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.account_id == "acct-task-integrity").one()
        item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == package.id
        ).one()

        package.current_item_index = 2
        package.visible_item_id = item.id
        item.visible_to_user = True
        session.add_all([package, item])
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_current_item_index_mismatch" in kinds
    assert "task_package_visible_item_pointer_mismatch" in kinds
    assert "task_package_visible_item_flag_mismatch" in kinds


def test_task_system_v3_integrity_report_detects_required_item_count_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.account_id == "acct-task-integrity").one()
        package.required_item_count = 3
        package.completed_required_item_count = 0
        session.add(package)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_required_item_count_mismatch" in kinds
    assert "task_package_completed_required_item_count_mismatch" in kinds


def test_task_system_v3_integrity_report_detects_item_status_and_package_completion_timestamp_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.account_id == "acct-task-integrity").one()
        item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == package.id
        ).one()
        package.completed_at = None
        item.status = "available"
        session.add_all([package, item])
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_package_completed_missing_completed_at" in kinds
    assert "task_package_item_status_mismatch" in kinds


def test_task_system_v3_integrity_report_detects_completed_batch_aggregate_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        batch = session.query(MemberTaskBatch).filter(MemberTaskBatch.account_id == "acct-task-integrity").one()
        batch.completed_package_count = 0
        batch.current_package_index = 9
        batch.status = "active"
        batch.completed_at = None
        session.add(batch)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "member_task_batch_completed_package_count_mismatch" in kinds
    assert "member_task_batch_current_package_index_mismatch" in kinds
    assert "member_task_batch_status_mismatch" in kinds
    assert "member_task_batch_completed_missing_completed_at" in kinds


def test_task_system_v3_integrity_report_detects_completed_batch_with_incomplete_linked_quota(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.account_id == "acct-task-integrity").one()
        quota.status = "locked"
        session.add(quota)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "member_task_batch_completed_quota_status_mismatch" in kinds


def test_task_system_v3_integrity_report_detects_generation_run_contract_mismatch(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        run = session.query(TaskProductGenerationRun).filter(
            TaskProductGenerationRun.account_id == "acct-task-integrity"
        ).one()
        run.generated_package_count = 9
        run.generated_item_count = 5
        run.actual_day_system_amount = Decimal("88.00")
        session.add(run)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_generation_run_package_count_mismatch" in kinds
    assert "task_generation_run_item_count_mismatch" in kinds
    assert "task_generation_run_actual_amount_mismatch" in kinds


def test_task_system_v3_integrity_report_detects_locked_quota_missing_generation_linkage(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.account_id == "acct-task-integrity").one()
        quota.status = "locked"
        quota.issued_batch_id = None
        quota.generated_at = None
        quota.locked_at = None
        session.add(quota)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "member_task_day_quota_locked_missing_batch_link" in kinds
    assert "member_task_day_quota_locked_missing_generated_at" in kinds
    assert "member_task_day_quota_locked_missing_locked_at" in kinds


def test_task_system_v3_integrity_report_detects_generation_run_out_of_quota_tolerance(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.account_id == "acct-task-integrity").one()
        quota.tolerance_amount = Decimal("0.00")
        session.add(quota)

        run = session.query(TaskProductGenerationRun).filter(
            TaskProductGenerationRun.account_id == "acct-task-integrity"
        ).one()
        run.actual_day_system_amount = Decimal("120.00")
        session.add(run)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_generation_run_out_of_quota_tolerance" in kinds


def test_task_system_v3_integrity_report_detects_quota_with_missing_issued_batch_reference(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.account_id == "acct-task-integrity").one()
        quota.issued_batch_id = "missing-batch-id"
        session.add(quota)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "member_task_day_quota_missing_issued_batch" in kinds


def test_task_system_v3_integrity_report_detects_generation_run_missing_scope_references(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        run = session.query(TaskProductGenerationRun).filter(
            TaskProductGenerationRun.account_id == "acct-task-integrity"
        ).one()
        run.batch_id = "missing-batch-id"
        run.quota_id = "missing-quota-id"
        run.product_pool_id = "missing-pool-id"
        session.add(run)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_generation_run_missing_batch" in kinds
    assert "task_generation_run_missing_quota" in kinds
    assert "task_generation_run_missing_product_pool" in kinds


def test_task_system_v3_integrity_report_detects_documented_breakages(
    db_session_factory: sessionmaker[Session],
) -> None:
    _seed_valid_task_system_scope(db_session_factory)

    with db_session_factory() as session:
        broken_account = Account(
            account_id="acct-task-integrity-broken",
            display_name="Task Integrity Broken",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        broken_site = H5Site(
            account_id=broken_account.account_id,
            site_key="task-integrity-broken",
            domain="task-integrity-broken.example.com",
            brand_name="Task Integrity Broken",
            default_language="zh-CN",
            status="active",
        )
        broken_user = AppUser(
            account_id=broken_account.account_id,
            public_user_id="user-task-integrity-broken",
            registration_site_id=broken_site.id,
            display_name="Task Integrity Broken User",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=True,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        broken_plan = TaskIssuePlan(
            account_id=broken_account.account_id,
            site_id=broken_site.id,
            name="Broken Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            require_previous_batch_completed=True,
            max_unfinished_batches=1,
            after_last_rule_mode="repeat_last",
            default_product_pool_id="missing-broken-plan-pool",
            default_tolerance_amount=Decimal("0.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add_all([broken_account, broken_site, broken_user])
        session.flush()
        broken_plan.site_id = broken_site.id
        session.add(broken_plan)

        config = session.query(TaskSystemConfig).filter(TaskSystemConfig.account_id == "acct-task-integrity").one()
        config.whatsapp_binding_reward_amount = Decimal("-1.00")
        config.certified_recharge_threshold = Decimal("-2.00")
        config.newbie_plan_id = "missing-newbie-plan"
        config.official_plan_id = "missing-official-plan"

        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.account_id == "acct-task-integrity").one()
        quota.package_amounts_json = ["99.00"]
        quota.tolerance_amount = Decimal("0.00")
        quota.product_pool_id = "missing-quota-pool"

        batch = session.query(MemberTaskBatch).filter(MemberTaskBatch.account_id == "acct-task-integrity").one()
        batch.system_generated_amount = Decimal("130.00")
        batch.manual_added_amount = Decimal("5.00")
        batch.effective_day_amount = Decimal("131.00")

        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.account_id == "acct-task-integrity").one()
        package.effective_amount = Decimal("120.00")
        package.reward_amount_final = Decimal("9.00")
        package.reward_ledger_id = None

        item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == package.id
        ).one()
        item.debit_ledger_id = None
        item.product_id = "duplicate-product"

        duplicate_item = TaskPackageInstanceItem(
            account_id=item.account_id,
            batch_id=item.batch_id,
            quota_id=item.quota_id,
            package_instance_id=item.package_instance_id,
            template_item_id=item.template_item_id,
            item_origin="manual_added",
            is_required=True,
            product_pool_id=item.product_pool_id,
            product_id="duplicate-product",
            product_name_snapshot="Duplicate Product",
            product_image_url_snapshot="https://example.com/dup.png",
            price_snapshot=Decimal("20.00"),
            sort_order=2,
            product_name="Duplicate Product",
            image_url="https://example.com/dup.png",
            price=Decimal("20.00"),
            currency="USD",
            status="available",
            visible_to_user=False,
            manual_add_log_id=None,
        )
        session.add(duplicate_item)

        out_of_order_manual_item = TaskPackageInstanceItem(
            account_id=item.account_id,
            batch_id=item.batch_id,
            quota_id=item.quota_id,
            package_instance_id=item.package_instance_id,
            template_item_id=item.template_item_id,
            item_origin="manual_added",
            is_required=True,
            product_pool_id=item.product_pool_id,
            product_id="manual-order-product",
            product_name_snapshot="Manual Order Product",
            product_image_url_snapshot="https://example.com/manual-order.png",
            price_snapshot=Decimal("5.00"),
            sort_order=0,
            product_name="Manual Order Product",
            image_url="https://example.com/manual-order.png",
            price=Decimal("5.00"),
            currency="USD",
            status="pending",
            visible_to_user=False,
            manual_add_log_id="manual-log-order-1",
        )
        session.add(out_of_order_manual_item)

        rule = session.query(TaskIssuePlanDayRule).filter(TaskIssuePlanDayRule.plan_id == quota.plan_id).one()
        rule.package_count = 0
        rule.day_total_amount = Decimal("0.00")
        rule.package_amounts_json = ["80.00", "10.00"]
        rule.product_pool_id = "missing-rule-pool"

        duplicate_run = TaskProductGenerationRun(
            account_id=batch.account_id,
            site_id=batch.site_id,
            user_id=batch.user_id,
            quota_id=quota.id,
            batch_id=batch.id,
            product_pool_id=quota.product_pool_id,
            selection_seed="seed-2",
            selection_algorithm="weighted_random_unique_v1",
            target_day_amount=Decimal("100.00"),
            actual_day_system_amount=Decimal("100.00"),
            tolerance_amount=Decimal("0.00"),
            generated_package_count=1,
            generated_item_count=2,
            status="success",
            idempotency_key="run-2",
        )
        session.add(duplicate_run)

        broken_wallet = WalletAccount(
            id="wallet-task-integrity-broken",
            account_id="acct-task-integrity",
            user_id=broken_user.id,
            system_balance=Decimal("5.00"),
            system_cash_balance=Decimal("1.00"),
            system_bonus_balance=Decimal("1.00"),
            frozen_balance=Decimal("0.00"),
            system_cash_frozen=Decimal("0.00"),
            system_bonus_frozen=Decimal("0.00"),
            task_balance=Decimal("0.00"),
            currency="USD",
            withdraw_threshold=Decimal("100.00"),
        )
        session.add(broken_wallet)
        session.commit()

        report = build_task_system_v3_integrity_report(session)

    kinds = {item["kind"] for item in report["violations"]}
    assert report["ok"] is False
    assert "task_site_missing_config" in kinds
    assert "task_system_config_negative_binding_reward" in kinds
    assert "task_system_config_negative_certified_threshold" in kinds
    assert "task_system_config_missing_newbie_plan" in kinds
    assert "task_system_config_missing_official_plan" in kinds
    assert "task_issue_plan_missing_day_rule" in kinds
    assert "task_issue_plan_missing_default_product_pool" in kinds
    assert "task_issue_plan_day_rule_invalid_package_count" in kinds
    assert "task_issue_plan_day_rule_invalid_total_amount" in kinds
    assert "task_issue_plan_day_rule_manual_total_mismatch" in kinds
    assert "task_issue_plan_day_rule_missing_product_pool" in kinds
    assert "member_task_day_quota_total_mismatch" in kinds
    assert "member_task_day_quota_missing_product_pool" in kinds
    assert "member_task_batch_system_amount_out_of_tolerance" in kinds
    assert "member_task_batch_effective_amount_mismatch" in kinds
    assert "member_task_batch_manual_added_amount_mismatch" in kinds
    assert "task_package_effective_amount_mismatch" in kinds
    assert "task_package_manual_added_amount_mismatch" in kinds
    assert "member_task_batch_duplicate_product" in kinds
    assert "task_package_duplicate_product" in kinds
    assert "task_package_manual_items_not_appended" in kinds
    assert "task_package_completed_missing_reward_ledger" in kinds
    assert "task_package_reward_amount_mismatch" in kinds
    assert "task_package_item_completed_missing_debit_ledger" in kinds
    assert "task_package_item_manual_added_missing_log" in kinds
    assert "task_generation_run_duplicate_scope" in kinds
    assert "wallet_balance_mismatch" in kinds
    assert "wallet_missing_ledger" in kinds


def test_task_system_v3_integrity_script_main_returns_zero_for_clean_scope(
    db_session_factory: sessionmaker[Session],
    capsys,
    monkeypatch,
) -> None:
    _seed_valid_task_system_scope(db_session_factory)
    monkeypatch.setattr(integrity_script, "_load_session_factory", lambda: db_session_factory)

    exit_code = integrity_script.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["violation_count"] == 0


def test_task_system_v3_integrity_script_main_returns_one_for_broken_scope(
    db_session_factory: sessionmaker[Session],
    capsys,
    monkeypatch,
) -> None:
    _seed_valid_task_system_scope(db_session_factory)
    with db_session_factory() as session:
        config = session.query(TaskSystemConfig).filter(TaskSystemConfig.account_id == "acct-task-integrity").one()
        config.whatsapp_binding_reward_amount = Decimal("-5.00")
        session.commit()

    monkeypatch.setattr(integrity_script, "_load_session_factory", lambda: db_session_factory)

    exit_code = integrity_script.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["violation_count"] >= 1
    assert {item["kind"] for item in payload["violations"]} >= {"task_system_config_negative_binding_reward"}

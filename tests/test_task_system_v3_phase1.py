from decimal import Decimal
from pathlib import Path

from app.db.base import Base
from app.db.models import (
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskProductPool,
    TaskProductPoolItem,
    TaskSystemConfig,
)
from app.services.task_amount_allocation_service import TaskAmountAllocationService


def test_task_system_v3_phase1_tables_exist() -> None:
    expected_tables = {
        "task_system_configs",
        "task_issue_plans",
        "task_issue_plan_day_rules",
        "member_task_day_quotas",
        "member_task_batches",
        "task_product_pools",
        "task_product_pool_items",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_task_system_v3_phase1_key_columns_exist() -> None:
    assert "whatsapp_binding_reward_amount" in TaskSystemConfig.__table__.c
    assert "claim_gate" in TaskIssuePlan.__table__.c
    assert "default_tolerance_amount" in TaskIssuePlan.__table__.c
    assert "default_reward_ratio" in TaskIssuePlan.__table__.c
    assert "day_no" in TaskIssuePlanDayRule.__table__.c
    assert "issue_time_of_day" in TaskIssuePlanDayRule.__table__.c
    assert "elapsed_delay_hours" in TaskIssuePlanDayRule.__table__.c
    assert "package_amounts_json" in MemberTaskDayQuota.__table__.c
    assert "quota_id" in MemberTaskBatch.__table__.c
    assert "pool_type" in TaskProductPool.__table__.c
    assert "price_mode" in TaskProductPool.__table__.c
    assert "allow_repeat_in_same_batch" in TaskProductPool.__table__.c
    assert "product_id" in TaskProductPoolItem.__table__.c


def test_average_allocation_balances_tail_rounding() -> None:
    amounts = TaskAmountAllocationService.allocate(
        mode="average",
        package_count=3,
        day_total_amount=Decimal("1000.00"),
    )

    assert amounts == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]


def test_incremental_allocation_matches_total_amount() -> None:
    amounts = TaskAmountAllocationService.allocate(
        mode="incremental",
        package_count=5,
        day_total_amount=Decimal("1000.00"),
    )

    assert amounts == [
        Decimal("66.67"),
        Decimal("133.33"),
        Decimal("200.00"),
        Decimal("266.67"),
        Decimal("333.33"),
    ]


def test_manual_allocation_requires_exact_total() -> None:
    amounts = TaskAmountAllocationService.allocate(
        mode="manual",
        package_count=3,
        day_total_amount=Decimal("100.00"),
        manual_amounts=[Decimal("20.00"), Decimal("30.00"), Decimal("50.00")],
    )

    assert amounts == [Decimal("20.00"), Decimal("30.00"), Decimal("50.00")]


def test_task_system_v3_documented_artifact_files_exist() -> None:
    expected_paths = [
        "app/services/member_certification_service.py",
        "app/services/whatsapp_binding_reward_service.py",
        "app/services/task_runtime_service.py",
        "app/services/task_monitor_alert_service.py",
        "frontend/src/services/tasksApi.ts",
        "frontend/src/types/h5Member.ts",
        "frontend/src/types/tasks.ts",
    ]

    missing = [path for path in expected_paths if not Path(path).exists()]
    assert missing == []

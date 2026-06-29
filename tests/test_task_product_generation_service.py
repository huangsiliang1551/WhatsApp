from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

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
    TaskProductGenerationRun,
    TaskProductPool,
    TaskProductPoolItem,
)
from app.services.task_product_generation_service import TaskProductGenerationService


def _seed_generation_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-generation", display_name="Task Generation")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-generation",
            domain="task-generation.example.com",
            brand_name="Task Generation",
            default_language="zh-CN",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="user-task-generation",
            registration_site_id=site.id,
            display_name="Task Generation User",
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
            name="Weighted Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        for index in range(1, 7):
            session.add(
                TaskProductPoolItem(
                    account_id=account.account_id,
                    pool_id=pool.id,
                    product_id=f"weighted-product-{index}",
                    product_name=f"Weighted Product {index}",
                    image_url=f"https://example.com/weighted-{index}.png",
                    price=Decimal("0.00"),
                    currency="USD",
                    weight=100 if index <= 3 else 25,
                    status="active",
                    sort_order=index,
                )
            )

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Weighted Official Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("0.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add(plan)
        session.flush()

        session.add(
            TaskIssuePlanDayRule(
                account_id=account.account_id,
                site_id=site.id,
                plan_id=plan.id,
                day_no=1,
                package_count=2,
                day_total_amount=Decimal("120.00"),
                tolerance_amount=Decimal("0.00"),
                amount_allocation_mode="manual",
                package_amounts_json=["50.00", "70.00"],
                product_pool_id=pool.id,
                product_count_mode="fixed",
                product_count_fixed=2,
                reward_ratio=Decimal("0.10"),
                status="active",
            )
        )
        session.flush()

        quota_one = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=2,
            day_total_amount=Decimal("120.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["50.00", "70.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=2,
            reward_ratio=Decimal("0.10"),
            status="pending",
        )
        quota_two = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=2,
            package_count=2,
            day_total_amount=Decimal("120.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["50.00", "70.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=2,
            reward_ratio=Decimal("0.10"),
            status="pending",
        )
        session.add_all([quota_one, quota_two])
        session.commit()
        return {
            "quota_one_id": quota_one.id,
            "quota_two_id": quota_two.id,
        }


def test_task_product_generation_varies_selection_by_seed_and_keeps_batch_unique(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_generation_scope(db_session_factory)

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        batch_one = service.generate_for_quota(quota_id=seeded["quota_one_id"], generated_by="test")
        batch_two = service.generate_for_quota(quota_id=seeded["quota_two_id"], generated_by="test")

        items_batch_one = session.query(TaskPackageInstanceItem).join(
            TaskPackageInstance,
            TaskPackageInstance.id == TaskPackageInstanceItem.package_instance_id,
        ).filter(
            TaskPackageInstance.batch_id == batch_one.id,
        ).order_by(TaskPackageInstance.batch_index.asc(), TaskPackageInstanceItem.sort_order.asc()).all()
        items_batch_two = session.query(TaskPackageInstanceItem).join(
            TaskPackageInstance,
            TaskPackageInstance.id == TaskPackageInstanceItem.package_instance_id,
        ).filter(
            TaskPackageInstance.batch_id == batch_two.id,
        ).order_by(TaskPackageInstance.batch_index.asc(), TaskPackageInstanceItem.sort_order.asc()).all()

        product_ids_batch_one = [item.product_id for item in items_batch_one]
        product_ids_batch_two = [item.product_id for item in items_batch_two]

        assert len(product_ids_batch_one) == len(set(product_ids_batch_one))
        assert len(product_ids_batch_two) == len(set(product_ids_batch_two))
        assert product_ids_batch_one != product_ids_batch_two

        generated_batches = session.query(MemberTaskBatch).filter(
            MemberTaskBatch.id.in_([batch_one.id, batch_two.id]),
        ).all()
        assert all(batch.products_generated is True for batch in generated_batches)
        quota_one = session.get(MemberTaskDayQuota, seeded["quota_one_id"])
        quota_two = session.get(MemberTaskDayQuota, seeded["quota_two_id"])
        assert quota_one is not None
        assert quota_two is not None
        assert quota_one.status == "locked"
        assert quota_two.status == "locked"
        assert quota_one.locked_at is not None
        assert quota_two.locked_at is not None


def test_task_product_generation_retries_when_only_stale_empty_batch_exists(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_generation_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.get(MemberTaskDayQuota, seeded["quota_one_id"])
        assert quota is not None
        stale_batch = MemberTaskBatch(
            account_id=quota.account_id,
            site_id=quota.site_id,
            user_id=quota.user_id,
            quota_id=quota.id,
            plan_id=quota.plan_id,
            day_no=quota.day_no,
            package_count=quota.package_count,
            planned_amount=Decimal("120.00"),
            system_generated_amount=Decimal("120.00"),
            manual_added_amount=Decimal("0.00"),
            effective_day_amount=Decimal("120.00"),
            reward_ratio_snapshot=Decimal("0.10"),
            status="pending_claim",
            products_generated=False,
        )
        session.add(stale_batch)
        session.flush()
        quota.issued_batch_id = stale_batch.id
        session.add(quota)
        session.commit()

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        regenerated = service.generate_for_quota(quota_id=seeded["quota_one_id"], generated_by="retry")

        session.refresh(regenerated)
        quota = session.get(MemberTaskDayQuota, seeded["quota_one_id"])
        packages = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.batch_id == regenerated.id,
        ).all()

    assert regenerated.products_generated is True
    assert quota is not None
    assert quota.status == "locked"
    assert quota.locked_at is not None
    assert quota.issued_batch_id == regenerated.id
    assert len(packages) == 2


def test_task_product_generation_fails_when_unique_pool_items_are_insufficient(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_generation_scope(db_session_factory)

    with db_session_factory() as session:
        quota = session.get(MemberTaskDayQuota, seeded["quota_one_id"])
        assert quota is not None

        pool_items = session.query(TaskProductPoolItem).filter(
            TaskProductPoolItem.pool_id == quota.product_pool_id,
        ).order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc()).all()
        assert len(pool_items) >= 4
        for item in pool_items[3:]:
            item.status = "disabled"
            session.add(item)
        session.commit()

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        with pytest.raises(ValueError, match="PRODUCT_POOL_NOT_ENOUGH_UNIQUE_ITEMS"):
            service.generate_for_quota(quota_id=seeded["quota_one_id"], generated_by="short-pool")
        session.rollback()

        assert session.query(MemberTaskBatch).filter(
            MemberTaskBatch.quota_id == seeded["quota_one_id"],
        ).count() == 0
        assert session.query(TaskPackageInstance).count() == 0
        assert session.query(TaskPackageInstanceItem).count() == 0


def test_task_product_generation_uses_reference_prices_when_pool_requires_product_reference_price(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-generation-reference", display_name="Task Generation Reference")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-generation-reference",
            domain="task-generation-reference.example.com",
            brand_name="Task Generation Reference",
            default_language="zh-CN",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="user-task-generation-reference",
            registration_site_id=site.id,
            display_name="Task Generation Reference User",
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
            name="Reference Price Pool",
            pool_type="general",
            price_mode="product_reference_price",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        for index, reference_price in enumerate((Decimal("82.00"), Decimal("97.00")), start=1):
            session.add(
                TaskProductPoolItem(
                    account_id=account.account_id,
                    pool_id=pool.id,
                    product_id=f"reference-product-{index}",
                    product_name=f"Reference Product {index}",
                    image_url=f"https://example.com/reference-{index}.png",
                    price=Decimal("0.00"),
                    reference_price=reference_price,
                    currency="USD",
                    weight=100,
                    status="active",
                    sort_order=index,
                )
            )

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Reference Price Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add(plan)
        session.flush()

        quota = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=2,
            day_total_amount=Decimal("180.00"),
            tolerance_amount=Decimal("5.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["80.00", "100.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.10"),
            status="pending",
        )
        session.add(quota)
        session.commit()
        quota_id = quota.id

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        batch = service.generate_for_quota(quota_id=quota_id, generated_by="reference-price")

        packages = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.batch_id == batch.id,
        ).order_by(TaskPackageInstance.batch_index.asc()).all()
        items = session.query(TaskPackageInstanceItem).join(
            TaskPackageInstance,
            TaskPackageInstance.id == TaskPackageInstanceItem.package_instance_id,
        ).filter(
            TaskPackageInstance.batch_id == batch.id,
        ).order_by(TaskPackageInstance.batch_index.asc(), TaskPackageInstanceItem.sort_order.asc()).all()

        run = session.query(MemberTaskBatch).filter(MemberTaskBatch.id == batch.id).one()
        generation_run = session.get(TaskProductGenerationRun, run.product_generation_run_id)

    assert sorted(item.price_snapshot for item in items) == [Decimal("82.00"), Decimal("97.00")]
    assert sorted(package.system_generated_amount for package in packages) == [Decimal("82.00"), Decimal("97.00")]
    assert batch.system_generated_amount == Decimal("179.00")
    assert generation_run is not None
    assert generation_run.actual_day_system_amount == Decimal("179.00")


def test_task_product_generation_fails_when_reference_price_total_is_outside_tolerance(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-generation-tolerance", display_name="Task Generation Tolerance")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-generation-tolerance",
            domain="task-generation-tolerance.example.com",
            brand_name="Task Generation Tolerance",
            default_language="zh-CN",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="user-task-generation-tolerance",
            registration_site_id=site.id,
            display_name="Task Generation Tolerance User",
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
            name="Tolerance Failure Pool",
            pool_type="general",
            price_mode="product_reference_price",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        for index, reference_price in enumerate((Decimal("120.00"), Decimal("95.00")), start=1):
            session.add(
                TaskProductPoolItem(
                    account_id=account.account_id,
                    pool_id=pool.id,
                    product_id=f"tolerance-product-{index}",
                    product_name=f"Tolerance Product {index}",
                    image_url=f"https://example.com/tolerance-{index}.png",
                    price=Decimal("0.00"),
                    reference_price=reference_price,
                    currency="USD",
                    weight=100,
                    status="active",
                    sort_order=index,
                )
            )

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Tolerance Failure Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add(plan)
        session.flush()

        quota = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=2,
            day_total_amount=Decimal("180.00"),
            tolerance_amount=Decimal("5.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["80.00", "100.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.10"),
            status="pending",
        )
        session.add(quota)
        session.commit()
        quota_id = quota.id

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        with pytest.raises(ValueError, match="TASK_PRODUCT_GENERATION_OUTSIDE_TOLERANCE"):
            service.generate_for_quota(quota_id=quota_id, generated_by="tolerance-failure")
        session.rollback()

        assert session.query(MemberTaskBatch).filter(MemberTaskBatch.quota_id == quota_id).count() == 0
        assert session.query(TaskPackageInstance).count() == 0
        assert session.query(TaskPackageInstanceItem).count() == 0


def test_task_product_generation_range_mode_uses_seeded_counts_within_range(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        account = Account(account_id="acct-task-generation-range", display_name="Task Generation Range")
        site = H5Site(
            account_id=account.account_id,
            site_key="task-generation-range",
            domain="task-generation-range.example.com",
            brand_name="Task Generation Range",
            default_language="zh-CN",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="user-task-generation-range",
            registration_site_id=site.id,
            display_name="Task Generation Range User",
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
            name="Range Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        for index in range(1, 10):
            session.add(
                TaskProductPoolItem(
                    account_id=account.account_id,
                    pool_id=pool.id,
                    product_id=f"range-product-{index}",
                    product_name=f"Range Product {index}",
                    image_url=f"https://example.com/range-{index}.png",
                    price=Decimal("0.00"),
                    currency="USD",
                    weight=100,
                    status="active",
                    sort_order=index,
                )
            )

        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Range Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("0.00"),
            default_reward_ratio=Decimal("0.10"),
        )
        session.add(plan)
        session.flush()

        quota = MemberTaskDayQuota(
            id="quota-range-seeded",
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=1,
            package_count=3,
            day_total_amount=Decimal("180.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["60.00", "60.00", "60.00"],
            product_pool_id=pool.id,
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.10"),
            status="pending",
        )
        session.add(quota)
        session.commit()

    with db_session_factory() as session:
        service = TaskProductGenerationService(session=session)
        batch = service.generate_for_quota(quota_id="quota-range-seeded", generated_by="range-mode")
        packages = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.batch_id == batch.id,
        ).order_by(TaskPackageInstance.batch_index.asc()).all()

    counts = [package.required_item_count for package in packages]
    assert counts == [2, 1, 3]
    assert all(1 <= count <= 3 for count in counts)

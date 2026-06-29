from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    AppUser,
    H5Site,
    MemberTaskBatch,
    TaskManualAddItemLog,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    TaskProductPool,
    TaskProductPoolItem,
    utc_now,
)
from app.services.task_manual_add_service import TaskManualAddService


def _seed_manual_add_scope(
    db_session_factory: sessionmaker[Session],
    *,
    suffix: str = "",
) -> dict[str, str]:
    now = utc_now()
    with db_session_factory() as session:
        account = Account(
            account_id=f"acct-task-manual-add{suffix}",
            display_name=f"Task Manual Add{suffix}",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        site = H5Site(
            account_id=account.account_id,
            site_key=f"task-manual-add{suffix}",
            domain=f"task-manual-add{suffix}.example.com",
            brand_name=f"Task Manual Add{suffix}",
            default_language="zh-CN",
            status="active",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id=f"user-task-manual-add{suffix}",
            registration_site_id=site.id,
            display_name=f"Task Manual Add User{suffix}",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=True,
            is_invited_user=False,
            is_new_user=True,
            restrict_task_claim=False,
            last_active_at=now,
        )
        session.add_all([account, site, user])
        session.flush()

        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Manual Add Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        pool_items: list[TaskProductPoolItem] = []
        for index, price in enumerate((Decimal("20.00"), Decimal("30.00"), Decimal("40.00"), Decimal("50.00")), start=1):
            item = TaskProductPoolItem(
                account_id=account.account_id,
                pool_id=pool.id,
                product_id=f"manual-product-{index}{suffix}",
                product_name=f"Manual Product {index}{suffix}",
                image_url=f"https://example.com/manual-{index}{suffix}.png",
                price=price,
                currency="USD",
                product_description=f"Manual Product {index}{suffix} description",
                status="active",
                sort_order=index,
            )
            session.add(item)
            session.flush()
            pool_items.append(item)

        batch = MemberTaskBatch(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            day_no=1,
            package_count=1,
            current_package_index=1,
            completed_package_count=0,
            planned_amount=Decimal("50.00"),
            system_generated_amount=Decimal("50.00"),
            manual_added_amount=Decimal("0.00"),
            effective_day_amount=Decimal("50.00"),
            reward_ratio_snapshot=Decimal("0.10"),
            status="active",
            products_generated=True,
            claimed_at=now,
        )
        session.add(batch)
        session.flush()

        template = TaskPackageTemplate(
            account_id=account.account_id,
            name="Manual Add Package",
            title="Manual Add Package",
            description="For task manual add tests",
            package_type="official",
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
        )
        session.add(template)
        session.flush()

        package = TaskPackageInstance(
            account_id=account.account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site.id,
            batch_id=batch.id,
            batch_day_no=1,
            batch_index=1,
            batch_total=1,
            planned_amount=Decimal("50.00"),
            system_generated_amount=Decimal("50.00"),
            manual_added_amount=Decimal("0.00"),
            effective_amount=Decimal("50.00"),
            status="active",
            reward_ratio_snapshot=Decimal("0.10"),
            current_item_index=2,
            visible_item_id=None,
            required_item_count=2,
            completed_required_item_count=1,
            completion_window_hours_snapshot=24,
            claimed_at=now,
        )
        session.add(package)
        session.flush()

        for sort_order, pool_item in enumerate(pool_items[:2], start=1):
            template_item = TaskPackageTemplateItem(
                account_id=account.account_id,
                template_id=template.id,
                sort_order=sort_order,
                product_name=pool_item.product_name,
                image_url=pool_item.image_url,
                price=pool_item.price,
                currency="USD",
            )
            session.add(template_item)
            session.flush()

            session.add(
                TaskPackageInstanceItem(
                    account_id=account.account_id,
                    batch_id=batch.id,
                    package_instance_id=package.id,
                    template_item_id=template_item.id,
                    item_origin="system_generated",
                    is_required=True,
                    product_pool_id=pool.id,
                    pool_item_id=pool_item.id,
                    product_id=pool_item.product_id,
                    product_name_snapshot=pool_item.product_name,
                    product_image_url_snapshot=pool_item.image_url,
                    product_description_snapshot=pool_item.product_description,
                    price_snapshot=pool_item.price,
                    sort_order=sort_order,
                    product_name=pool_item.product_name,
                    image_url=pool_item.image_url,
                    price=pool_item.price,
                    currency="USD",
                    status="completed" if sort_order == 1 else "available",
                    visible_to_user=sort_order == 2,
                    completed_at=now if sort_order == 1 else None,
                )
            )

        session.commit()
        return {
            "pool_id": pool.id,
            "batch_id": batch.id,
            "package_id": package.id,
            "pool_item_3_id": pool_items[2].id,
            "pool_item_4_id": pool_items[3].id,
        }


def test_list_available_pool_items_filters_out_products_already_used_in_batch(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        available = service.list_available_pool_items(package_id=seeded["package_id"])

    assert [item.product_id for item in available] == ["manual-product-3", "manual-product-4"]


def test_add_manual_items_appends_to_package_end_and_updates_amounts(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        log = service.add_items(
            package_id=seeded["package_id"],
            pool_item_ids=[seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            operator_id="staff-manual-add-1",
            notify_user=True,
            reason_text="客服追加任务商品",
            user_notice_text="客服已追加商品，请以后台记录为准。",
        )
        session.expire_all()

        package = session.get(TaskPackageInstance, seeded["package_id"])
        batch = session.get(MemberTaskBatch, seeded["batch_id"])
        items = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == seeded["package_id"]
        ).order_by(TaskPackageInstanceItem.sort_order.asc()).all()
        stored_log = session.get(TaskManualAddItemLog, log.id)

    assert package is not None
    assert batch is not None
    assert package.manual_added_amount == Decimal("90.00")
    assert package.effective_amount == Decimal("140.00")
    assert package.manual_added_item_count == 2
    assert package.required_item_count == 4
    assert package.has_adjustment_notice is False
    assert package.adjustment_notice is None
    assert batch.manual_added_amount == Decimal("90.00")
    assert batch.effective_day_amount == Decimal("140.00")
    assert [item.sort_order for item in items] == [1, 2, 3, 4]
    assert [item.item_origin for item in items[2:]] == ["manual_added", "manual_added"]
    assert all(item.is_required is True for item in items[2:])
    assert all(item.manual_add_log_id == log.id for item in items[2:])
    assert stored_log is not None
    assert stored_log.added_item_count == 2
    assert stored_log.added_amount == Decimal("90.00")
    assert stored_log.notify_user is True
    assert stored_log.user_notice_text is not None
    assert stored_log.user_notified_at is not None
    assert stored_log.user_notice_text == "客服已追加商品，请以后台记录为准。"


def test_manual_add_allows_same_package_repeat_when_pool_policy_allows_it(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    with db_session_factory() as session:
        package = session.get(TaskPackageInstance, seeded["package_id"])
        assert package is not None
        first_item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == seeded["package_id"],
            TaskPackageInstanceItem.product_id == "manual-product-1",
        ).one()
        first_pool_item_id = first_item.pool_item_id
        pool = session.get(TaskProductPool, seeded["pool_id"])
        assert pool is not None
        pool.allow_repeat_in_same_batch = True
        pool.allow_repeat_in_same_package = True
        session.commit()

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        available = service.list_available_pool_items(package_id=seeded["package_id"])
        assert "manual-product-1" in [item.product_id for item in available]

        log = service.add_items(
            package_id=seeded["package_id"],
            pool_item_ids=[first_pool_item_id],
            operator_id="staff-manual-add-repeat",
            reason_text="allow repeat",
        )
        added_item_count = log.added_item_count
        session.expire_all()

        package = session.get(TaskPackageInstance, seeded["package_id"])
        items = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == seeded["package_id"]
        ).order_by(TaskPackageInstanceItem.sort_order.asc()).all()

    assert added_item_count == 1
    assert package is not None
    assert package.manual_added_item_count == 1
    assert [item.product_id for item in items].count("manual-product-1") == 2

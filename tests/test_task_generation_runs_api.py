from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    AppUser,
    H5Site,
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskProductGenerationRun,
    TaskProductPool,
    TaskProductPoolItem,
    TaskPackageInstance,
    utc_now,
)


def _seed_task_generation_run_scope(
    db_session_factory: sessionmaker[Session],
    *,
    suffix: str = "",
) -> dict[str, str]:
    with db_session_factory() as session:
        account_id = f"acct-task-run-api{suffix}"
        account = Account(account_id=account_id, display_name=f"Task Run API{suffix}")
        site = H5Site(
            account_id=account.account_id,
            site_key=f"task-run-api{suffix}",
            domain=f"task-run-api{suffix}.example.com",
            brand_name=f"Task Run API{suffix}",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account.account_id,
            public_user_id=f"task-run-user{suffix}",
            registration_site_id=site.id,
            display_name=f"Task Run User{suffix}",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Run Pool",
            pool_type="general",
            status="active",
        )
        session.add_all([user, pool])
        session.flush()

        quota = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            day_no=2,
            package_count=3,
            day_total_amount=Decimal("300.00"),
            tolerance_amount=Decimal("5.00"),
            amount_allocation_mode="average",
            package_amounts_json=["100.00", "100.00", "100.00"],
            product_pool_id=pool.id,
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.20"),
            status="locked",
            generated_at=utc_now(),
            generated_by="operator-task-run-api",
            locked_at=utc_now(),
            created_by="operator-task-run-api",
        )
        session.add(quota)
        session.flush()

        batch = MemberTaskBatch(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            quota_id=quota.id,
            day_no=2,
            package_count=3,
            planned_amount=Decimal("300.00"),
            system_generated_amount=Decimal("295.00"),
            manual_added_amount=Decimal("0.00"),
            effective_day_amount=Decimal("295.00"),
            reward_ratio_snapshot=Decimal("0.20"),
            status="active",
        )
        session.add(batch)
        session.flush()
        quota.issued_batch_id = batch.id
        session.add(quota)

        run = TaskProductGenerationRun(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            quota_id=quota.id,
            batch_id=batch.id,
            product_pool_id=pool.id,
            selection_seed="seed-1",
            selection_algorithm="weighted_random_unique_v1",
            target_day_amount=Decimal("300.00"),
            actual_day_system_amount=Decimal("295.00"),
            tolerance_amount=Decimal("5.00"),
            generated_package_count=3,
            generated_item_count=7,
            status="success",
            idempotency_key=f"quota:run-1{suffix}:generation",
        )
        session.add(run)
        session.commit()
        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "user_id": user.id,
            "run_id": run.id,
        }


def _seed_task_generation_ready_quota_scope(
    db_session_factory: sessionmaker[Session],
    *,
    suffix: str = "",
    pool_item_count: int = 4,
) -> dict[str, str]:
    with db_session_factory() as session:
        account_id = f"acct-task-run-generate{suffix}"
        account = Account(account_id=account_id, display_name=f"Task Run Generate{suffix}")
        site = H5Site(
            account_id=account.account_id,
            site_key=f"task-run-generate{suffix}",
            domain=f"task-run-generate{suffix}.example.com",
            brand_name=f"Task Run Generate{suffix}",
            default_language="zh-CN",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account.account_id,
            public_user_id=f"task-run-generate-user{suffix}",
            registration_site_id=site.id,
            display_name=f"Task Run Generate User{suffix}",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
        )
        pool = TaskProductPool(
            account_id=account.account_id,
            site_id=site.id,
            name="Generation Ready Pool",
            pool_type="general",
            status="active",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            currency="USD",
        )
        session.add_all([user, pool])
        session.flush()

        for index in range(pool_item_count):
            session.add(
                TaskProductPoolItem(
                    account_id=account.account_id,
                    pool_id=pool.id,
                    product_id=f"product-{suffix or 'base'}-{index}",
                    product_name=f"Product {index}",
                    image_url=f"https://example.com/{index}.png",
                    price=Decimal("100.00"),
                    currency="USD",
                    status="active",
                    sort_order=index + 1,
                )
            )

        quota = MemberTaskDayQuota(
            account_id=account.account_id,
            site_id=site.id,
            user_id=user.id,
            day_no=1,
            package_count=2,
            day_total_amount=Decimal("200.00"),
            tolerance_amount=Decimal("0.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["100.00", "100.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.20"),
            status="locked",
            generated_at=utc_now(),
            generated_by="operator-task-run-api",
            locked_at=utc_now(),
            created_by="operator-task-run-api",
        )
        session.add(quota)
        session.commit()
        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "user_id": user.id,
            "quota_id": quota.id,
            "pool_id": pool.id,
        }


def test_list_task_generation_runs(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_task_generation_run_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-run-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.get(
        "/api/tasks/generation-runs",
        params={"account_id": seeded["account_id"], "user_id": seeded["user_id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == seeded["run_id"]
    assert listed[0]["publicUserId"] == "task-run-user"
    assert listed[0]["actualDaySystemAmount"] == 295.0


def test_cross_account_task_generation_run_list_is_forbidden(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_generation_run_scope(db_session_factory)
    headers = {
        "X-Actor-Id": "operator-task-run-forbidden",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-other-scope",
    }

    response = client.get(
        "/api/tasks/generation-runs",
        params={"account_id": seeded["account_id"]},
        headers=headers,
    )
    assert response.status_code == 403


def test_list_task_generation_runs_without_account_filter_ignores_other_accounts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_generation_run_scope(db_session_factory)
    _seed_task_generation_run_scope(db_session_factory, suffix="-other")

    headers = {
        "X-Actor-Id": "operator-task-run-api",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.get(
        "/api/tasks/generation-runs",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["accountId"] == seeded["account_id"]


def test_generate_task_batch_for_quota_creates_success_run_and_packages(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_generation_ready_quota_scope(db_session_factory, suffix="-generate")
    headers = {
        "X-Actor-Id": "operator-task-run-generate",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    response = client.post(
        f"/api/tasks/member-day-quotas/{seeded['quota_id']}/generate-batch",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["quotaId"] == seeded["quota_id"]
    assert payload["status"] == "success"
    assert payload["generatedPackageCount"] == 2
    assert payload["generatedItemCount"] == 2

    second = client.post(
        f"/api/tasks/member-day-quotas/{seeded['quota_id']}/generate-batch",
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == payload["id"]

    with db_session_factory() as session:
        quota = session.get(MemberTaskDayQuota, seeded["quota_id"])
        assert quota is not None
        assert quota.issued_batch_id is not None
        assert session.query(MemberTaskBatch).filter(
            MemberTaskBatch.quota_id == seeded["quota_id"],
        ).count() == 1
        assert session.query(TaskPackageInstance).filter(
            TaskPackageInstance.quota_id == seeded["quota_id"],
        ).count() == 2


def test_retry_failed_task_generation_run_regenerates_after_pool_is_fixed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_task_generation_ready_quota_scope(
        db_session_factory,
        suffix="-retry",
        pool_item_count=1,
    )
    headers = {
        "X-Actor-Id": "operator-task-run-retry",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": seeded["account_id"],
    }

    failed_response = client.post(
        f"/api/tasks/member-day-quotas/{seeded['quota_id']}/generate-batch",
        headers=headers,
    )
    assert failed_response.status_code == 409, failed_response.text
    assert failed_response.json()["detail"] == "PRODUCT_POOL_NOT_ENOUGH_UNIQUE_ITEMS"

    with db_session_factory() as session:
        failed_run = session.query(TaskProductGenerationRun).filter(
            TaskProductGenerationRun.quota_id == seeded["quota_id"],
            TaskProductGenerationRun.status == "failed",
        ).one()
        session.add(
            TaskProductPoolItem(
                account_id=seeded["account_id"],
                pool_id=seeded["pool_id"],
                product_id="product-retry-1",
                product_name="Retry Product 1",
                image_url="https://example.com/retry-1.png",
                price=Decimal("100.00"),
                currency="USD",
                status="active",
                sort_order=10,
            )
        )
        session.commit()
        failed_run_id = failed_run.id

    retried = client.post(
        f"/api/tasks/generation-runs/{failed_run_id}/retry",
        headers=headers,
    )
    assert retried.status_code == 200, retried.text
    payload = retried.json()
    assert payload["status"] == "success"
    assert payload["quotaId"] == seeded["quota_id"]
    assert payload["id"] != failed_run_id

    with db_session_factory() as session:
        statuses = {
            row.status
            for row in session.query(TaskProductGenerationRun).filter(
                TaskProductGenerationRun.quota_id == seeded["quota_id"],
            ).all()
        }
        assert statuses == {"failed", "success"}

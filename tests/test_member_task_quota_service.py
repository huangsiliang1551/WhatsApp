from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    AppUser,
    H5Site,
    MemberProfile,
    MemberTaskBatch,
    MemberTaskDayQuota,
    MemberVerificationRequest,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskProductPool,
    utc_now,
)
from app.schemas.member_task_quota import MemberTaskQuotaCreateRequest, MemberTaskQuotaPlanIssueRequest
from app.services import member_task_quota_service as member_task_quota_service_module
from app.services.member_task_quota_service import MemberTaskQuotaService


def _seed_quota_scope(db_session_factory: sessionmaker[Session]) -> dict[str, str]:
    with db_session_factory() as session:
        account = Account(account_id="acct-quota", display_name="Quota Account")
        site = H5Site(
            account_id=account.account_id,
            site_key="quota-site",
            domain="quota.example.com",
            brand_name="Quota Site",
            default_language="zh-CN",
        )
        user = AppUser(
            account_id=account.account_id,
            public_user_id="quota-user",
            registration_site_id=site.id,
            display_name="Quota User",
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
            name="Default Pool",
            pool_type="general",
            status="active",
        )
        plan = TaskIssuePlan(
            account_id=account.account_id,
            site_id=site.id,
            name="Official Plan",
            plan_type="official",
            status="active",
            claim_gate="certified_member",
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="arithmetic_growth",
            growth_package_count_step=2,
            growth_amount_step=Decimal("100.00"),
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.15"),
        )
        session.add_all([account, site, user, pool, plan])
        session.flush()

        member_profile = MemberProfile(
            account_id=account.account_id,
            user_id=user.id,
            member_no="10000001",
            password_hash="quota-password-hash",
            password_salt="quota-password-salt",
        )
        session.add(member_profile)
        session.flush()

        verification = MemberVerificationRequest(
            account_id=account.account_id,
            member_profile_id=member_profile.id,
            request_type="identity",
            status="approved",
            reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
        )
        session.add(verification)

        day1 = TaskIssuePlanDayRule(
            account_id=account.account_id,
            site_id=site.id,
            plan_id=plan.id,
            day_no=1,
            package_count=3,
            day_total_amount=Decimal("300.00"),
            tolerance_amount=Decimal("6.00"),
            amount_allocation_mode="average",
            package_amounts_json=[],
            product_pool_id=pool.id,
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.12"),
        )
        day2 = TaskIssuePlanDayRule(
            account_id=account.account_id,
            site_id=site.id,
            plan_id=plan.id,
            day_no=2,
            package_count=5,
            day_total_amount=Decimal("500.00"),
            tolerance_amount=Decimal("8.00"),
            amount_allocation_mode="manual",
            package_amounts_json=["50.00", "75.00", "100.00", "125.00", "150.00"],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=2,
            reward_ratio=Decimal("0.18"),
            issue_time_of_day="09:30",
        )
        session.add_all([day1, day2])
        session.commit()

        return {
            "account_id": account.account_id,
            "site_id": site.id,
            "user_id": user.id,
            "plan_id": plan.id,
            "pool_id": pool.id,
        }


def test_create_manual_quota_allocates_average_amounts(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        payload = MemberTaskQuotaCreateRequest(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            day_no=7,
            package_count=3,
            day_total_amount=Decimal("1000.00"),
            tolerance_amount=Decimal("10.00"),
            amount_allocation_mode="average",
            product_pool_id=seeded["pool_id"],
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.20"),
            created_by="operator-1",
        )

        quota = service.create_quota(payload)

        assert quota.package_amounts_json == ["333.33", "333.33", "333.34"]
        assert quota.status == "pending"
        assert quota.created_by == "operator-1"


def test_issue_quota_from_plan_uses_exact_day_rule(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        quota = service.issue_quota_from_plan(
            MemberTaskQuotaPlanIssueRequest(
                plan_id=seeded["plan_id"],
                user_id=seeded["user_id"],
                day_no=2,
                created_by="planner-1",
            )
        )

        assert quota.package_count == 5
        assert quota.amount_allocation_mode == "manual"
        assert quota.package_amounts_json == ["50.00", "75.00", "100.00", "125.00", "150.00"]
        assert quota.reward_ratio == Decimal("0.1800")


def test_issue_quota_from_plan_applies_arithmetic_growth_after_last_rule(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        quota = service.issue_quota_from_plan(
            MemberTaskQuotaPlanIssueRequest(
                plan_id=seeded["plan_id"],
                user_id=seeded["user_id"],
                day_no=4,
                created_by="planner-2",
            )
        )

        assert quota.package_count == 9
        assert quota.day_total_amount == Decimal("700.00")
        assert quota.package_amounts_json == [
            "77.78",
            "77.78",
            "77.78",
            "77.78",
            "77.78",
            "77.78",
            "77.78",
            "77.78",
            "77.76",
        ]


def test_create_quota_rejects_duplicate_scope(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        payload = MemberTaskQuotaCreateRequest(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            plan_id=seeded["plan_id"],
            day_no=9,
            package_count=2,
            day_total_amount=Decimal("200.00"),
            amount_allocation_mode="average",
            product_pool_id=seeded["pool_id"],
        )
        service.create_quota(payload)

        with pytest.raises(ValueError, match="already exists"):
            service.create_quota(payload)


def test_issue_quota_from_plan_stop_mode_blocks_missing_rule(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        plan = session.get(TaskIssuePlan, seeded["plan_id"])
        assert plan is not None
        plan.after_last_rule_mode = "stop"
        session.add(plan)
        session.commit()

        service = MemberTaskQuotaService(session)
        with pytest.raises(LookupError, match="No day rule"):
            service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=seeded["plan_id"],
                    user_id=seeded["user_id"],
                    day_no=4,
                )
            )


def test_issue_quota_from_plan_persists_row(db_session_factory: sessionmaker[Session]) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        created = service.issue_quota_from_plan(
            MemberTaskQuotaPlanIssueRequest(
                plan_id=seeded["plan_id"],
                user_id=seeded["user_id"],
                day_no=1,
                created_by="planner-3",
            )
        )

        stored = session.get(MemberTaskDayQuota, created.id)
        assert stored is not None
        assert stored.plan_id == seeded["plan_id"]
        assert stored.product_pool_id == seeded["pool_id"]


def test_issue_quota_from_plan_only_allocates_amounts_without_pre_generating_user_products(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        service = MemberTaskQuotaService(session)
        created = service.issue_quota_from_plan(
            MemberTaskQuotaPlanIssueRequest(
                plan_id=seeded["plan_id"],
                user_id=seeded["user_id"],
                day_no=1,
                created_by="planner-no-products",
            )
        )

        assert created.package_amounts_json == ["100.00", "100.00", "100.00"]
        assert session.query(MemberTaskBatch).filter(MemberTaskBatch.quota_id == created.id).count() == 0
        assert session.query(TaskPackageInstance).filter(TaskPackageInstance.quota_id == created.id).count() == 0
        assert (
            session.query(TaskPackageInstanceItem)
            .join(TaskPackageInstance, TaskPackageInstance.id == TaskPackageInstanceItem.package_instance_id)
            .filter(TaskPackageInstance.quota_id == created.id)
            .count()
            == 0
        )


def test_issue_quota_from_plan_blocks_when_previous_batch_must_be_completed(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        quota = MemberTaskDayQuota(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            plan_id=seeded["plan_id"],
            day_no=1,
            package_count=3,
            day_total_amount=Decimal("300.00"),
            tolerance_amount=Decimal("6.00"),
            amount_allocation_mode="average",
            package_amounts_json=["100.00", "100.00", "100.00"],
            product_pool_id=seeded["pool_id"],
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.12"),
            status="locked",
            generated_at=utc_now(),
            generated_by="test-seed",
            locked_at=utc_now(),
        )
        session.add(quota)
        session.flush()

        batch = MemberTaskBatch(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            quota_id=quota.id,
            plan_id=seeded["plan_id"],
            day_no=1,
            package_count=3,
            completed_package_count=1,
            current_package_index=2,
            planned_amount=Decimal("300.00"),
            system_generated_amount=Decimal("300.00"),
            effective_day_amount=Decimal("300.00"),
            reward_ratio_snapshot=Decimal("0.12"),
            status="active",
            products_generated=True,
        )
        session.add(batch)
        session.flush()
        quota.issued_batch_id = batch.id
        session.add(quota)
        session.commit()

        service = MemberTaskQuotaService(session)
        with pytest.raises(ValueError, match="Previous batch must be completed"):
            service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=seeded["plan_id"],
                    user_id=seeded["user_id"],
                    day_no=2,
                    created_by="planner-blocked",
                )
            )


def test_issue_quota_from_plan_blocks_when_unfinished_batch_limit_is_reached(
    db_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        plan = session.get(TaskIssuePlan, seeded["plan_id"])
        assert plan is not None
        plan.require_previous_batch_completed = False
        plan.max_unfinished_batches = 1
        session.add(plan)

        quota = MemberTaskDayQuota(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            plan_id=seeded["plan_id"],
            day_no=1,
            package_count=3,
            day_total_amount=Decimal("300.00"),
            tolerance_amount=Decimal("6.00"),
            amount_allocation_mode="average",
            package_amounts_json=["100.00", "100.00", "100.00"],
            product_pool_id=seeded["pool_id"],
            product_count_mode="range",
            product_count_min=1,
            product_count_max=3,
            reward_ratio=Decimal("0.12"),
            status="locked",
            generated_at=utc_now(),
            generated_by="test-seed",
            locked_at=utc_now(),
        )
        session.add(quota)
        session.flush()

        batch = MemberTaskBatch(
            account_id=seeded["account_id"],
            site_id=seeded["site_id"],
            user_id=seeded["user_id"],
            quota_id=quota.id,
            plan_id=seeded["plan_id"],
            day_no=1,
            package_count=3,
            completed_package_count=0,
            current_package_index=1,
            planned_amount=Decimal("300.00"),
            system_generated_amount=Decimal("300.00"),
            effective_day_amount=Decimal("300.00"),
            reward_ratio_snapshot=Decimal("0.12"),
            status="pending_claim",
            products_generated=True,
        )
        session.add(batch)
        session.flush()
        quota.issued_batch_id = batch.id
        session.add(quota)
        session.commit()

        service = MemberTaskQuotaService(session)
        with pytest.raises(ValueError, match="Maximum unfinished batch limit reached"):
            service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=seeded["plan_id"],
                    user_id=seeded["user_id"],
                    day_no=2,
                    created_by="planner-limit",
                )
            )


def test_issue_quota_from_plan_blocks_before_issue_time_of_day(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == seeded["user_id"]).one()
        verification = MemberVerificationRequest(
            account_id=seeded["account_id"],
            member_profile_id=member_profile.id,
            request_type="identity",
            status="approved",
            reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
        )
        session.add(verification)
        session.commit()

        monkeypatch.setattr(
            member_task_quota_service_module,
            "utc_now",
            lambda: datetime.fromisoformat("2026-06-21T09:00:00"),
        )

        service = MemberTaskQuotaService(session)
        with pytest.raises(ValueError, match="schedule window has not been reached"):
            service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=seeded["plan_id"],
                    user_id=seeded["user_id"],
                    day_no=2,
                    created_by="planner-schedule",
                )
            )


def test_issue_quota_from_plan_blocks_before_elapsed_delay_hours(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_quota_scope(db_session_factory)

    with db_session_factory() as session:
        day1 = session.query(TaskIssuePlanDayRule).filter(
            TaskIssuePlanDayRule.plan_id == seeded["plan_id"],
            TaskIssuePlanDayRule.day_no == 1,
        ).one()
        day1.elapsed_delay_hours = 6
        session.add(day1)

        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == seeded["user_id"]).one()
        verification = MemberVerificationRequest(
            account_id=seeded["account_id"],
            member_profile_id=member_profile.id,
            request_type="identity",
            status="approved",
            reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
        )
        session.add(verification)
        session.commit()

        monkeypatch.setattr(
            member_task_quota_service_module,
            "utc_now",
            lambda: datetime.fromisoformat("2026-06-20T13:00:00"),
        )

        service = MemberTaskQuotaService(session)
        with pytest.raises(ValueError, match="schedule window has not been reached"):
            service.issue_quota_from_plan(
                MemberTaskQuotaPlanIssueRequest(
                    plan_id=seeded["plan_id"],
                    user_id=seeded["user_id"],
                    day_no=1,
                    created_by="planner-delay",
                )
            )

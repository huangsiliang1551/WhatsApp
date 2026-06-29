import asyncio
import os
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, BrokenBarrierError, Thread
from uuid import uuid4

import pytest
psycopg = pytest.importorskip("psycopg", exc_type=ImportError)
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import (
    Account,
    AppUser,
    H5Site,
    InviteCode,
    MemberAuthSession,
    MemberTaskBatch,
    MemberProfile,
    PromotionTaskInstance,
    PromotionTaskTemplate,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    TaskProductPool,
    TaskProductPoolItem,
    UserReferral,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
    UserIdentity,
    utc_now,
)
from app.db.session import build_sync_database_url
from app.core.platform_enums import UserIdentityType
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from app.services.task_manual_add_service import TaskManualAddService


def _build_postgres_test_url() -> URL:
    return make_url(
        os.environ.get(
            "H5_POSTGRES_TEST_DSN",
            "postgresql://whatsapp_user:secure_password@127.0.0.1:5432/postgres",
        )
    )


def _render_url(url: URL) -> str:
    return url.render_as_string(hide_password=False)


@pytest.fixture
def postgres_session_factory() -> sessionmaker[Session]:
    admin_url = _build_postgres_test_url()
    try:
        with psycopg.connect(_render_url(admin_url), connect_timeout=2, autocommit=True):
            pass
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL test server is unavailable: {exc}")

    database_name = f"codex_h5_promotion_{uuid4().hex[:8]}"
    app_url = admin_url.set(database=database_name)

    with psycopg.connect(_render_url(admin_url), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{database_name}"')

    engine = create_engine(build_sync_database_url(_render_url(app_url)), future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    try:
        yield factory
    finally:
        engine.dispose()
        with psycopg.connect(_render_url(admin_url), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                    (database_name,),
                )
                cur.execute(f'DROP DATABASE IF EXISTS "{database_name}"')


def _seed_postgres_promotion_claim_scope(
    db_session_factory: sessionmaker[Session],
    *,
    create_wallet: bool = True,
) -> dict[str, str]:
    now = utc_now()
    account_id = "acct-h5-promotion-postgres"
    public_user_id = "h5-promotion-postgres-member"
    referred_user_id = "h5-promotion-postgres-referral"

    with db_session_factory() as session:
        account = Account(
            account_id=account_id,
            display_name="H5 Promotion Postgres",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        site = H5Site(
            account_id=account_id,
            site_key="h5-promotion-postgres",
            domain="h5-promotion-postgres.example.com",
            brand_name="H5 Promotion Postgres",
            default_language="zh-CN",
            status="active",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account_id,
            public_user_id=public_user_id,
            registration_site_id=site.id,
            display_name="Postgres Promotion Member",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=True,
            restrict_task_claim=False,
            last_active_at=now,
        )
        session.add(user)
        session.flush()

        member_profile = MemberProfile(
            account_id=account_id,
            user_id=user.id,
            member_no="22334455",
            password_hash="seeded-password-hash",
            password_salt="seeded-password-salt",
            password_updated_at=now,
            last_login_at=now,
        )
        session.add(member_profile)
        session.flush()

        referred_user = AppUser(
            account_id=account_id,
            public_user_id=referred_user_id,
            registration_site_id=site.id,
            display_name="Postgres Referral",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=True,
            is_new_user=True,
            restrict_task_claim=False,
            last_active_at=now,
        )
        session.add(referred_user)
        session.flush()

        invite_code = InviteCode(
            code="PROMO-POSTGRES-01",
            site_id=site.id,
            inviter_user_id=user.id,
            status="active",
        )
        template = TaskPackageTemplate(
            account_id=account_id,
            name="Promotion Postgres Package",
            title="Promotion Postgres Package",
            description="Concurrent claim test package",
            package_type="promotion",
            reward_ratio=Decimal("0.12"),
            completion_window_hours=24,
            status="active",
            promotion_metric="invited_registrations",
            promotion_target_value=1,
        )
        session.add_all([invite_code, template])
        session.flush()

        template_item = TaskPackageTemplateItem(
            account_id=account_id,
            template_id=template.id,
            sort_order=1,
            product_name="Promotion Product",
            image_url="https://example.com/promotion.png",
            price=Decimal("18"),
            currency="USD",
        )
        session.add(template_item)
        session.flush()

        package = TaskPackageInstance(
            account_id=account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site.id,
            status="pending_claim",
            reward_ratio_snapshot=Decimal("0.12"),
            dispatched_at=template.created_at,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.flush()

        package_item = TaskPackageInstanceItem(
            account_id=account_id,
            package_instance_id=package.id,
            template_item_id=template_item.id,
            sort_order=1,
            product_name=template_item.product_name,
            image_url=template_item.image_url,
            price=template_item.price,
            currency=template_item.currency,
        )
        promotion_template = PromotionTaskTemplate(
            account_id=account_id,
            task_package_template_id=template.id,
            metric="invited_registrations",
            target_value=1,
            status="active",
        )
        session.add_all([package_item, promotion_template])
        session.flush()

        promotion_instance = PromotionTaskInstance(
            account_id=account_id,
            promotion_task_template_id=promotion_template.id,
            task_package_instance_id=package.id,
            user_id=user.id,
            member_profile_id=member_profile.id,
            metric="invited_registrations",
            target_value=1,
            invite_code_snapshot=invite_code.code,
            current_value=1,
            achieved_at=now,
            status="active",
        )
        referral = UserReferral(
            account_id=account_id,
            site_id=site.id,
            invite_code=invite_code.code,
            referrer_user_id=user.id,
            referred_user_id=referred_user.id,
            registered_at=now,
            status="registered",
        )
        session.add_all([promotion_instance, referral])
        if create_wallet:
            session.add(
                WalletAccount(
                    account_id=account_id,
                    user_id=user.id,
                    system_balance=Decimal("0"),
                    task_balance=Decimal("0"),
                    currency="USD",
                    withdraw_threshold=Decimal("100"),
                )
            )
        session.commit()

        return {
            "account_id": account_id,
            "site_id": site.id,
            "public_user_id": public_user_id,
            "user_id": user.id,
            "member_profile_id": member_profile.id,
            "package_id": package.id,
        }


def _build_context(
    session: Session,
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
        member_profile_id: str,
) -> H5MemberContext:
    user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
    member_profile = session.query(MemberProfile).filter(MemberProfile.id == member_profile_id).one()
    site = session.query(H5Site).filter(H5Site.id == site_id).one()
    username_identity = (
        session.query(UserIdentity)
        .filter(
            UserIdentity.user_id == user.id,
            UserIdentity.identity_type == UserIdentityType.USERNAME.value,
        )
        .order_by(UserIdentity.is_primary.desc(), UserIdentity.created_at.asc(), UserIdentity.id.asc())
        .first()
    )
    auth_session = MemberAuthSession(
        account_id=account_id,
        user_id=user.id,
        member_profile_id=member_profile.id,
        session_token_hash=f"session-{uuid4().hex}",
        refresh_token_hash=f"refresh-{uuid4().hex}",
        status="active",
        expires_at=utc_now() + timedelta(hours=1),
        refresh_expires_at=utc_now() + timedelta(days=7),
    )
    return H5MemberContext(
        member_profile=member_profile,
        user=user,
        site=site,
        username=username_identity.identity_value if username_identity is not None else "+8613900099999",
        phone="+8613900099999",
        auth_session=auth_session,
    )


def _seed_postgres_withdrawal_scope(
    db_session_factory: sessionmaker[Session],
) -> dict[str, str]:
    now = utc_now()
    account_id = "acct-h5-withdraw-postgres"
    public_user_id = "h5-withdraw-postgres-member"

    with db_session_factory() as session:
        account = Account(
            account_id=account_id,
            display_name="H5 Withdrawal Postgres",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        site = H5Site(
            account_id=account_id,
            site_key="h5-withdraw-postgres",
            domain="h5-withdraw-postgres.example.com",
            brand_name="H5 Withdrawal Postgres",
            default_language="zh-CN",
            status="active",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account_id,
            public_user_id=public_user_id,
            registration_site_id=site.id,
            display_name="Postgres Withdrawal Member",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=True,
            restrict_task_claim=False,
            last_active_at=now,
        )
        session.add(user)
        session.flush()

        member_profile = MemberProfile(
            account_id=account_id,
            user_id=user.id,
            member_no="33445566",
            password_hash="seeded-password-hash",
            password_salt="seeded-password-salt",
            password_updated_at=now,
            last_login_at=now,
        )
        wallet = WalletAccount(
            account_id=account_id,
            user_id=user.id,
            system_balance=Decimal("150"),
            task_balance=Decimal("20"),
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        session.add_all([member_profile, wallet])
        session.commit()

        return {
            "account_id": account_id,
            "site_id": site.id,
            "public_user_id": public_user_id,
            "user_id": user.id,
            "member_profile_id": member_profile.id,
        }


def _seed_postgres_manual_add_purchase_race_scope(
    db_session_factory: sessionmaker[Session],
) -> dict[str, str]:
    now = utc_now()
    account_id = "acct-h5-manual-add-race-postgres"
    public_user_id = "h5-manual-add-race-postgres-member"

    with db_session_factory() as session:
        account = Account(
            account_id=account_id,
            display_name="H5 Manual Add Race Postgres",
            provider_type="whatsapp",
            is_active=True,
            ai_enabled=True,
        )
        site = H5Site(
            account_id=account_id,
            site_key="h5-manual-add-race-postgres",
            domain="h5-manual-add-race-postgres.example.com",
            brand_name="H5 Manual Add Race Postgres",
            default_language="zh-CN",
            status="active",
        )
        session.add_all([account, site])
        session.flush()

        user = AppUser(
            account_id=account_id,
            public_user_id=public_user_id,
            registration_site_id=site.id,
            display_name="Postgres Manual Add Race Member",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=True,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
            last_active_at=now,
        )
        session.add(user)
        session.flush()

        member_profile = MemberProfile(
            account_id=account_id,
            user_id=user.id,
            member_no="55667788",
            password_hash="seeded-password-hash",
            password_salt="seeded-password-salt",
            password_updated_at=now,
            last_login_at=now,
        )
        wallet = WalletAccount(
            account_id=account_id,
            user_id=user.id,
            system_balance=Decimal("200"),
            task_balance=Decimal("0"),
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        session.add_all([member_profile, wallet])
        session.flush()

        pool = TaskProductPool(
            account_id=account_id,
            site_id=site.id,
            name="Race Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        base_item = TaskProductPoolItem(
            account_id=account_id,
            pool_id=pool.id,
            product_id="race-product-1",
            product_name="Race Product 1",
            image_url="https://example.com/race-1.png",
            price=Decimal("50"),
            currency="USD",
            weight=100,
            status="active",
            sort_order=1,
        )
        add_item = TaskProductPoolItem(
            account_id=account_id,
            pool_id=pool.id,
            product_id="race-product-2",
            product_name="Race Product 2",
            image_url="https://example.com/race-2.png",
            price=Decimal("30"),
            currency="USD",
            weight=100,
            status="active",
            sort_order=2,
        )
        session.add_all([base_item, add_item])
        session.flush()

        template = TaskPackageTemplate(
            account_id=account_id,
            name="Manual Add Race Package",
            title="Manual Add Race Package",
            description="Concurrent manual add and purchase race",
            package_type="official",
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
        )
        session.add(template)
        session.flush()

        template_item = TaskPackageTemplateItem(
            account_id=account_id,
            template_id=template.id,
            sort_order=1,
            product_name=base_item.product_name,
            image_url=base_item.image_url,
            price=base_item.price,
            currency="USD",
        )
        session.add(template_item)
        session.flush()

        batch = MemberTaskBatch(
            account_id=account_id,
            site_id=site.id,
            user_id=user.id,
            day_no=1,
            package_count=1,
            current_package_index=1,
            completed_package_count=0,
            planned_amount=Decimal("50"),
            system_generated_amount=Decimal("50"),
            manual_added_amount=Decimal("0"),
            effective_day_amount=Decimal("50"),
            reward_ratio_snapshot=Decimal("0.10"),
            status="active",
            products_generated=True,
            claimed_at=now,
        )
        session.add(batch)
        session.flush()

        package = TaskPackageInstance(
            account_id=account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site.id,
            batch_id=batch.id,
            batch_day_no=1,
            batch_index=1,
            batch_total=1,
            planned_amount=Decimal("50"),
            system_generated_amount=Decimal("50"),
            manual_added_amount=Decimal("0"),
            effective_amount=Decimal("50"),
            status="active",
            reward_ratio_snapshot=Decimal("0.10"),
            current_item_index=1,
            visible_item_id=None,
            required_item_count=1,
            completed_required_item_count=0,
            completion_window_hours_snapshot=24,
            claimed_at=now,
        )
        session.add(package)
        session.flush()

        package_item = TaskPackageInstanceItem(
            account_id=account_id,
            batch_id=batch.id,
            package_instance_id=package.id,
            template_item_id=template_item.id,
            item_origin="system_generated",
            is_required=True,
            product_pool_id=pool.id,
            pool_item_id=base_item.id,
            product_id=base_item.product_id,
            product_name_snapshot=base_item.product_name,
            product_image_url_snapshot=base_item.image_url,
            product_description_snapshot=None,
            price_snapshot=base_item.price,
            sort_order=1,
            product_name=base_item.product_name,
            image_url=base_item.image_url,
            price=base_item.price,
            currency=base_item.currency,
            status="available",
            visible_to_user=True,
            available_at=now,
        )
        session.add(package_item)
        session.commit()

        return {
            "account_id": account_id,
            "site_id": site.id,
            "public_user_id": public_user_id,
            "user_id": user.id,
            "member_profile_id": member_profile.id,
            "package_id": package.id,
            "item_id": package_item.id,
            "manual_pool_item_id": add_item.id,
        }


def _run_postgres_concurrent_claims(
    postgres_session_factory: sessionmaker[Session],
    *,
    seeded: dict[str, str],
    synchronize_wallet_creation: bool,
    synchronize_reward_commit: bool,
) -> tuple[list[object], list[BaseException]]:
    barrier = Barrier(2)
    results: list[object] = []
    errors: list[BaseException] = []

    def run_claim() -> None:
        session = postgres_session_factory()
        try:
            context = _build_context(
                session,
                account_id=seeded["account_id"],
                site_id=seeded["site_id"],
                public_user_id=seeded["public_user_id"],
                member_profile_id=seeded["member_profile_id"],
            )
            service = H5MemberCommerceService(session=session)
            original_commit = session.commit

            def synchronized_commit() -> None:
                waits_for_wallet = synchronize_wallet_creation and any(
                    isinstance(item, WalletAccount) for item in session.new
                )
                waits_for_reward = synchronize_reward_commit and any(
                    isinstance(item, WalletLedgerEntry) and item.transaction_type == "task_reward"
                    for item in session.new
                )
                if waits_for_wallet or waits_for_reward:
                    barrier.wait(timeout=10)
                return original_commit()

            session.commit = synchronized_commit  # type: ignore[method-assign]
            payload = asyncio.run(
                service.claim_task_package(context=context, package_id=seeded["package_id"])
            )
            results.append(payload)
        except BaseException as exc:  # pragma: no cover - assertion path
            errors.append(exc)
        finally:
            session.close()

    first = Thread(target=run_claim)
    second = Thread(target=run_claim)
    first.start()
    second.start()
    first.join()
    second.join()
    return results, errors


def _run_postgres_concurrent_withdrawals(
    postgres_session_factory: sessionmaker[Session],
    *,
    seeded: dict[str, str],
    amount: Decimal,
) -> tuple[list[object], list[ValueError], list[BaseException]]:
    barrier = Barrier(2)
    results: list[object] = []
    value_errors: list[ValueError] = []
    errors: list[BaseException] = []

    def run_withdraw() -> None:
        session = postgres_session_factory()
        try:
            context = _build_context(
                session,
                account_id=seeded["account_id"],
                site_id=seeded["site_id"],
                public_user_id=seeded["public_user_id"],
                member_profile_id=seeded["member_profile_id"],
            )
            service = H5MemberCommerceService(session=session)
            original_commit = session.commit

            def synchronized_commit() -> None:
                if any(isinstance(item, WithdrawalRequest) for item in session.new):
                    try:
                        barrier.wait(timeout=2)
                    except BrokenBarrierError:
                        pass
                return original_commit()

            session.commit = synchronized_commit  # type: ignore[method-assign]
            payload = asyncio.run(service.create_withdrawal(context=context, amount=amount))
            results.append(payload)
        except ValueError as exc:
            value_errors.append(exc)
        except BaseException as exc:  # pragma: no cover - assertion path
            errors.append(exc)
        finally:
            session.close()

    first = Thread(target=run_withdraw)
    second = Thread(target=run_withdraw)
    first.start()
    second.start()
    first.join()
    second.join()
    return results, value_errors, errors


def test_h5_promotion_task_package_claim_is_idempotent_under_postgres_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_postgres_promotion_claim_scope(postgres_session_factory)
    results, errors = _run_postgres_concurrent_claims(
        postgres_session_factory,
        seeded=seeded,
        synchronize_wallet_creation=False,
        synchronize_reward_commit=True,
    )

    assert errors == []
    assert len(results) == 2

    with postgres_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(
            TaskPackageInstance.id == seeded["package_id"]
        ).one()
        wallet = verify_session.query(WalletAccount).filter(
            WalletAccount.account_id == seeded["account_id"],
            WalletAccount.user_id == seeded["user_id"],
        ).one()
        promotion_instance = verify_session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == seeded["package_id"]
        ).one()
        reward_entries = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert package.claimed_at is not None
        assert package.completed_at is not None
        assert package.task_balance_awarded_at is not None
        assert wallet.task_balance == Decimal("2.16")
        assert promotion_instance.rewarded_at is not None
        assert len(reward_entries) == 1

        for payload in results:
            assert payload.status == "completed"
            assert payload.claimed_at == package.claimed_at
            assert payload.completed_at == package.completed_at
            assert payload.task_balance_awarded_at == package.task_balance_awarded_at
            assert payload.countdown_seconds == 0


def test_h5_withdrawal_allows_only_one_success_under_postgres_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_postgres_withdrawal_scope(postgres_session_factory)
    results, value_errors, errors = _run_postgres_concurrent_withdrawals(
        postgres_session_factory,
        seeded=seeded,
        amount=Decimal("100"),
    )

    assert errors == []
    assert len(results) == 1
    assert len(value_errors) == 1
    assert "active withdrawal request" in str(value_errors[0]).lower()

    with postgres_session_factory() as verify_session:
        wallet = verify_session.query(WalletAccount).filter(
            WalletAccount.account_id == seeded["account_id"],
            WalletAccount.user_id == seeded["user_id"],
        ).one()
        withdrawals = verify_session.query(WithdrawalRequest).filter(
            WithdrawalRequest.account_id == seeded["account_id"],
            WithdrawalRequest.user_id == seeded["user_id"],
        ).all()
        withdraw_ledgers = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.account_id == seeded["account_id"],
            WalletLedgerEntry.user_id == seeded["user_id"],
            WalletLedgerEntry.transaction_type == "withdraw_request",
        ).all()

        assert wallet.system_balance == Decimal("50")
        assert len(withdrawals) == 1
        assert len(withdraw_ledgers) == 1
        assert results[0].status == "submitted"
        assert results[0].amount == 100.0


def test_h5_promotion_task_package_claim_creates_single_wallet_under_postgres_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_postgres_promotion_claim_scope(
        postgres_session_factory,
        create_wallet=False,
    )
    results, errors = _run_postgres_concurrent_claims(
        postgres_session_factory,
        seeded=seeded,
        synchronize_wallet_creation=True,
        synchronize_reward_commit=False,
    )

    assert errors == []
    assert len(results) == 2

    with postgres_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(
            TaskPackageInstance.id == seeded["package_id"]
        ).one()
        wallets = verify_session.query(WalletAccount).filter(
            WalletAccount.account_id == seeded["account_id"],
            WalletAccount.user_id == seeded["user_id"],
        ).all()
        reward_entries = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert package.claimed_at is not None
        assert package.completed_at is not None
        assert package.task_balance_awarded_at is not None
        assert len(wallets) == 1
        assert wallets[0].task_balance == Decimal("2.16")
        assert len(reward_entries) == 1

        for payload in results:
            assert payload.status == "completed"
            assert payload.claimed_at == package.claimed_at
            assert payload.completed_at == package.completed_at
            assert payload.task_balance_awarded_at == package.task_balance_awarded_at
            assert payload.countdown_seconds == 0


def test_h5_task_purchase_waits_for_manual_add_and_does_not_settle_early_under_postgres(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    seeded = _seed_postgres_manual_add_purchase_race_scope(postgres_session_factory)
    manual_add_ready = Barrier(2)
    purchase_results: list[object] = []
    manual_add_results: list[object] = []
    errors: list[BaseException] = []

    def run_manual_add() -> None:
        session = postgres_session_factory()
        try:
            service = TaskManualAddService(session=session)
            original_commit = session.commit

            def synchronized_commit() -> None:
                if any(type(item).__name__ == "TaskManualAddItemLog" for item in session.new):
                    manual_add_ready.wait(timeout=10)
                return original_commit()

            session.commit = synchronized_commit  # type: ignore[method-assign]
            result = service.add_items(
                package_id=seeded["package_id"],
                pool_item_ids=[seeded["manual_pool_item_id"]],
                operator_id="postgres-race-operator",
                reason_text="race add",
            )
            manual_add_results.append(result)
        except BaseException as exc:
            errors.append(exc)
        finally:
            session.close()

    def run_purchase() -> None:
        session = postgres_session_factory()
        try:
            context = _build_context(
                session,
                account_id=seeded["account_id"],
                site_id=seeded["site_id"],
                public_user_id=seeded["public_user_id"],
                member_profile_id=seeded["member_profile_id"],
            )
            service = H5MemberCommerceService(session=session)
            manual_add_ready.wait(timeout=10)
            payload = asyncio.run(
                service.purchase_task_package_item(
                    context=context,
                    package_id=seeded["package_id"],
                    item_id=seeded["item_id"],
                )
            )
            purchase_results.append(payload)
        except BaseException as exc:
            errors.append(exc)
        finally:
            session.close()

    add_thread = Thread(target=run_manual_add)
    purchase_thread = Thread(target=run_purchase)
    add_thread.start()
    purchase_thread.start()
    add_thread.join()
    purchase_thread.join()

    assert errors == []
    assert len(manual_add_results) == 1
    assert len(purchase_results) == 1
    assert purchase_results[0].success is True

    with postgres_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(
            TaskPackageInstance.id == seeded["package_id"]
        ).one()
        items = verify_session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == seeded["package_id"]
        ).order_by(TaskPackageInstanceItem.sort_order.asc()).all()
        reward_entries = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "active"
        assert package.completed_at is None
        assert package.reward_amount_final is None
        assert package.completed_required_item_count == 1
        assert package.required_item_count == 2
        assert package.manual_added_item_count == 1
        assert package.manual_added_amount == Decimal("30")
        assert package.effective_amount == Decimal("80")
        assert len(items) == 2
        assert items[0].completed_at is not None
        assert items[1].item_origin == "manual_added"
        assert items[1].completed_at is None
        assert len(reward_entries) == 0

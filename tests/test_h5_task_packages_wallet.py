import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AuditLog,
    AppUser,
    H5Site,
    InviteCode,
    MemberAuthSession,
    MemberTaskBatch,
    MemberTaskDayQuota,
    MemberOrder,
    MemberProfile,
    TaskSystemConfig,
    MemberVerificationRequest,
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
    WalletRechargeOrder,
    UserIdentity,
    utc_now,
)
from app.core.platform_enums import UserIdentityType
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from app.services.task_manual_add_service import TaskManualAddService
from app.services.wallet_ledger_service import WalletLedgerService
from tests.test_h5_member_auth import _create_site, _operator_headers, _register_member, _seed_task_system_config


def _seed_task_package_scope(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    system_balance: Decimal,
    task_balance: Decimal = Decimal("0"),
) -> dict[str, str]:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()

        wallet = WalletAccount(
            account_id=account_id,
            user_id=user.id,
            system_balance=system_balance,
            task_balance=task_balance,
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        template = TaskPackageTemplate(
            account_id=account_id,
            name="Rookie Package",
            title="Rookie Package",
            description="First package for wallet and order flow",
            package_type="rookie",
            reward_ratio=Decimal("0.20"),
            completion_window_hours=24,
            status="active",
        )
        session.add_all([wallet, template])
        session.flush()

        item_a = TaskPackageTemplateItem(
            account_id=account_id,
            template_id=template.id,
            sort_order=1,
            product_name="Starter Product A",
            image_url="https://example.com/a.png",
            price=Decimal("30"),
            currency="USD",
        )
        item_b = TaskPackageTemplateItem(
            account_id=account_id,
            template_id=template.id,
            sort_order=2,
            product_name="Starter Product B",
            image_url="https://example.com/b.png",
            price=Decimal("20"),
            currency="USD",
        )
        session.add_all([item_a, item_b])
        session.flush()

        package = TaskPackageInstance(
            account_id=account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site_id,
            status="pending_claim",
            reward_ratio_snapshot=Decimal("0.20"),
            dispatched_at=template.created_at,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.flush()

        package_item_a = TaskPackageInstanceItem(
            account_id=account_id,
            package_instance_id=package.id,
            template_item_id=item_a.id,
            sort_order=1,
            product_name=item_a.product_name,
            image_url=item_a.image_url,
            price=item_a.price,
            currency=item_a.currency,
        )
        package_item_b = TaskPackageInstanceItem(
            account_id=account_id,
            package_instance_id=package.id,
            template_item_id=item_b.id,
            sort_order=2,
            product_name=item_b.product_name,
            image_url=item_b.image_url,
            price=item_b.price,
            currency=item_b.currency,
        )
        session.add_all([package_item_a, package_item_b])
        session.commit()

        return {
            "user_id": user.id,
            "package_id": package.id,
            "item_a_id": package_item_a.id,
            "item_b_id": package_item_b.id,
        }


def _seed_task_batch_scope(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    system_balance: Decimal,
    package_amounts: list[Decimal] | None = None,
) -> dict[str, str]:
    with db_session_factory() as session:
        now = utc_now()
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        resolved_package_amounts = package_amounts or [Decimal("10"), Decimal("20")]
        total_amount = sum(resolved_package_amounts, Decimal("0"))
        package_count = len(resolved_package_amounts)

        wallet = WalletAccount(
            account_id=account_id,
            user_id=user.id,
            system_balance=system_balance,
            task_balance=Decimal("0"),
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        template = TaskPackageTemplate(
            account_id=account_id,
            name="Official Batch Package",
            title="Official Batch Package",
            description="Batch package sequencing test",
            package_type="official",
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
        )
        session.add_all([wallet, template])
        session.flush()

        pool = TaskProductPool(
            account_id=account_id,
            site_id=site_id,
            name="Official Batch Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        batch = MemberTaskBatch(
            account_id=account_id,
            site_id=site_id,
            user_id=user.id,
            day_no=1,
            package_count=package_count,
            current_package_index=1,
            completed_package_count=0,
            planned_amount=total_amount,
            system_generated_amount=total_amount,
            effective_day_amount=total_amount,
            reward_ratio_snapshot=Decimal("0.10"),
            status="pending_claim",
            products_generated=True,
        )
        session.add(batch)
        session.flush()

        quota = MemberTaskDayQuota(
            account_id=account_id,
            site_id=site_id,
            user_id=user.id,
            day_no=1,
            package_count=package_count,
            day_total_amount=total_amount,
            tolerance_amount=Decimal("0"),
            amount_allocation_mode="manual",
            package_amounts_json=[f"{amount:.2f}" for amount in resolved_package_amounts],
            product_pool_id=pool.id,
            product_count_mode="fixed",
            product_count_fixed=1,
            reward_ratio=Decimal("0.10"),
            status="locked",
            issued_batch_id=batch.id,
            generated_at=now,
            generated_by="test-seed",
            locked_at=now,
        )
        session.add(quota)
        session.flush()
        batch.quota_id = quota.id
        session.add(batch)

        item_ids: list[str] = []
        package_ids: list[str] = []
        for batch_index, price in enumerate(resolved_package_amounts, start=1):
            template_item = TaskPackageTemplateItem(
                account_id=account_id,
                template_id=template.id,
                sort_order=batch_index,
                product_name=f"Batch Product {batch_index}",
                image_url=f"https://example.com/batch-{batch_index}.png",
                price=price,
                currency="USD",
            )
            session.add(template_item)
            session.flush()

            package = TaskPackageInstance(
                account_id=account_id,
                template_id=template.id,
                user_id=user.id,
                site_id=site_id,
                batch_id=batch.id,
                quota_id=quota.id,
                batch_day_no=1,
                batch_index=batch_index,
                batch_total=package_count,
                planned_amount=price,
                system_generated_amount=price,
                effective_amount=price,
                status="pending_claim",
                reward_ratio_snapshot=Decimal("0.10"),
                current_item_index=1,
                required_item_count=1,
                completion_window_hours_snapshot=24,
            )
            session.add(package)
            session.flush()

            package_item = TaskPackageInstanceItem(
                account_id=account_id,
                batch_id=batch.id,
                package_instance_id=package.id,
                template_item_id=template_item.id,
                sort_order=1,
                product_name=template_item.product_name,
                image_url=template_item.image_url,
                price=template_item.price,
                currency=template_item.currency,
                status="pending",
                visible_to_user=False,
            )
            session.add(package_item)
            session.flush()
            item_ids.append(package_item.id)
            package_ids.append(package.id)

        session.commit()
        return {
            "batch_id": batch.id,
            "quota_id": quota.id,
            "package_one_id": package_ids[0],
            "package_two_id": package_ids[1],
            "item_one_id": item_ids[0],
            "item_two_id": item_ids[1],
        }


def _seed_promotion_task_package_scope(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    metric: str,
    target_value: int,
    invited_registration_count: int,
    recharged_invitee_count: int,
    include_item: bool = False,
) -> dict[str, str]:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        invite_code = InviteCode(
            code=f"PROMO-{public_user_id[-6:].upper()}",
            site_id=site_id,
            inviter_user_id=user.id,
            status="active",
        )
        template = TaskPackageTemplate(
            account_id=account_id,
            name=f"Promotion Package {metric}",
            title=f"Promotion Package {metric}",
            description="Promotion package progress should reflect referral stats",
            package_type="promotion",
            reward_ratio=Decimal("0.12"),
            completion_window_hours=24,
            status="active",
            promotion_metric=metric,
            promotion_target_value=target_value,
        )
        session.add_all([invite_code, template])
        session.flush()

        promotion_template = PromotionTaskTemplate(
            account_id=account_id,
            task_package_template_id=template.id,
            metric=metric,
            target_value=target_value,
            status="active",
        )
        session.add(promotion_template)
        session.flush()

        package = TaskPackageInstance(
            account_id=account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site_id,
            status="pending_claim",
            reward_ratio_snapshot=Decimal("0.12"),
            dispatched_at=template.created_at,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.flush()

        package_item_id = ""
        if include_item:
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
            session.add(package_item)
            session.flush()
            package_item_id = package_item.id

        session.add(
            PromotionTaskInstance(
                account_id=account_id,
                promotion_task_template_id=promotion_template.id,
                task_package_instance_id=package.id,
                user_id=user.id,
                member_profile_id=member_profile.id,
                metric=metric,
                target_value=target_value,
                invite_code_snapshot=invite_code.code,
                current_value=0,
                status="active",
            )
        )

        for index in range(invited_registration_count):
            referred_user = AppUser(
                account_id=account_id,
                public_user_id=f"{public_user_id}-promotion-{metric}-{index}",
                registration_site_id=site_id,
                display_name=f"Referral {index}",
                language_code="zh-CN",
                is_anonymous=False,
                lifecycle_status="active",
                has_phone=True,
                has_email=False,
                has_whatsapp=False,
                is_invited_user=True,
                is_new_user=True,
                restrict_task_claim=False,
                registration_invite_code=invite_code.code,
                last_active_at=utc_now(),
            )
            session.add(referred_user)
            session.flush()

            referred_profile = MemberProfile(
                account_id=account_id,
                user_id=referred_user.id,
                member_no=f"{index + 1:08d}",
                password_hash="seeded-password-hash",
                password_salt="seeded-password-salt",
                password_updated_at=utc_now(),
                last_login_at=utc_now(),
            )
            session.add(referred_profile)
            session.flush()

            session.add(
                UserReferral(
                    account_id=account_id,
                    site_id=site_id,
                    invite_code=invite_code.code,
                    referrer_user_id=user.id,
                    referred_user_id=referred_user.id,
                    referred_member_profile_id=referred_profile.id,
                    registered_at=utc_now(),
                    first_recharged_at=utc_now() if index < recharged_invitee_count else None,
                )
            )

        session.commit()
        return {
            "package_id": package.id,
            "invite_code": invite_code.code,
            "item_id": package_item_id,
        }


def _seed_uninitialized_promotion_task_package_scope(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    metric: str,
    target_value: int,
) -> dict[str, str]:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        template = TaskPackageTemplate(
            account_id=account_id,
            name=f"Promotion Package Init {metric}",
            title=f"Promotion Package Init {metric}",
            description="Promotion package should bootstrap promotion rows on first read",
            package_type="promotion",
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
            promotion_metric=metric,
            promotion_target_value=target_value,
        )
        session.add(template)
        session.flush()

        package = TaskPackageInstance(
            account_id=account_id,
            template_id=template.id,
            user_id=user.id,
            site_id=site_id,
            status="pending_claim",
            reward_ratio_snapshot=Decimal("0.10"),
            dispatched_at=template.created_at,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.commit()
        return {
            "package_id": package.id,
        }


def _load_h5_member_context(
    db_session: Session,
    *,
    public_user_id: str,
    site_id: str,
    phone: str,
) -> H5MemberContext:
    user = db_session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
    member_profile = db_session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
    auth_session = (
        db_session.query(MemberAuthSession)
        .filter(MemberAuthSession.user_id == user.id)
        .order_by(MemberAuthSession.created_at.desc(), MemberAuthSession.id.desc())
        .first()
    )
    assert auth_session is not None
    site_model = db_session.query(H5Site).filter(H5Site.id == site_id).one()
    username_identity = (
        db_session.query(UserIdentity)
        .filter(
            UserIdentity.user_id == user.id,
            UserIdentity.identity_type == UserIdentityType.USERNAME.value,
        )
        .order_by(UserIdentity.is_primary.desc(), UserIdentity.created_at.asc(), UserIdentity.id.asc())
        .first()
    )
    assert username_identity is not None
    return H5MemberContext(
        member_profile=member_profile,
        user=user,
        site=site_model,
        username=username_identity.identity_value,
        phone=phone,
        auth_session=auth_session,
    )


def test_h5_task_package_claim_purchase_reward_and_orders_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package", site_key="h5-package")
    auth_payload = _register_member(
        client,
        site_key="h5-package",
        phone="+8613900044444",
        display_name="Package Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    list_response = client.get("/api/h5/task-packages")
    assert list_response.status_code == 200, list_response.text
    packages = list_response.json()
    assert [item["id"] for item in packages] == [seeded["package_id"]]
    assert packages[0]["status"] == "pending_claim"
    assert packages[0]["countdownSeconds"] == 86400
    assert packages[0]["totalCommission"] == 10.0

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    claimed = claim_response.json()
    assert claimed["status"] == "active"
    assert claimed["claimedAt"] is not None
    assert claimed["expiresAt"] is not None

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        audit_logs = session.query(AuditLog).filter(
            AuditLog.account_id == "acct-h5-package",
            AuditLog.action == "h5_task_package_claimed",
            AuditLog.actor_type == "member",
            AuditLog.actor_id == user.id,
            AuditLog.target_id == seeded["package_id"],
        ).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["generated_item_count"] == 2
        assert audit_logs[0].payload["claimed_status"] == "active"

    wallet_before_purchase = client.get("/api/h5/wallet")
    assert wallet_before_purchase.status_code == 200, wallet_before_purchase.text
    assert wallet_before_purchase.json()["systemBalance"] == 100.0
    assert wallet_before_purchase.json()["taskBalance"] == 0.0

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    first_payload = first_purchase.json()
    assert first_payload["success"] is True
    assert first_payload["order"]["amount"] == 30.0
    assert first_payload["taskPackage"]["completedItems"] == 1
    assert first_payload["taskPackage"]["status"] == "active"
    assert first_payload["wallet"]["systemBalance"] == 70.0
    assert first_payload["wallet"]["taskBalance"] == 0.0

    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_b_id']}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text
    second_payload = second_purchase.json()
    assert second_payload["success"] is True
    assert second_payload["taskPackage"]["completedItems"] == 2
    assert second_payload["taskPackage"]["status"] == "completed"
    assert second_payload["wallet"]["systemBalance"] == 50.0
    assert second_payload["wallet"]["taskBalance"] == 10.0

    orders_response = client.get("/api/h5/orders")
    assert orders_response.status_code == 200, orders_response.text
    orders = orders_response.json()
    assert len(orders) == 2
    assert {item["status"] for item in orders} == {"paid"}
    assert {item["packageId"] for item in orders} == {seeded["package_id"]}

    transactions_response = client.get("/api/h5/wallet/transactions")
    assert transactions_response.status_code == 200, transactions_response.text
    transaction_types = [item["transactionType"] for item in transactions_response.json()]
    assert "purchase" in transaction_types
    assert "task_reward" in transaction_types

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert messages[0]["title"] == "Task reward credited"
    assert messages[0]["category"] == "task"
    assert "10.00 USD" in messages[0]["bodyText"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] == 1


def test_h5_task_package_detail_exposes_batch_progress_and_current_item_after_claim(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-current", site_key="h5-package-current")
    auth_payload = _register_member(
        client,
        site_key="h5-package-current",
        phone="+8613900044455",
        display_name="Package Current Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package-current",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    pending_detail = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert pending_detail.status_code == 200, pending_detail.text
    pending_payload = pending_detail.json()
    assert pending_payload["batchIndex"] == 1
    assert pending_payload["batchTotal"] == 1
    assert pending_payload["currentItemIndex"] is None
    assert pending_payload["currentItem"] is None

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    claimed = claim_response.json()
    assert claimed["batchIndex"] == 1
    assert claimed["batchTotal"] == 1
    assert claimed["currentItemIndex"] == 1
    assert claimed["currentItem"]["id"] == seeded["item_a_id"]
    assert claimed["currentItem"]["productName"] == "Starter Product A"


def test_h5_legacy_task_package_without_batch_link_still_behaves_as_single_package(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-legacy-package", site_key="h5-legacy-package")
    auth_payload = _register_member(
        client,
        site_key="h5-legacy-package",
        phone="+86139000444552",
        display_name="Legacy Package Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-legacy-package",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        package.batch_id = None
        package.quota_id = None
        package.batch_index = None
        package.batch_total = None
        session.add(package)
        session.commit()

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["batchIndex"] == 1
    assert detail_payload["batchTotal"] == 1
    assert detail_payload["currentItemIndex"] is None

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    claim_payload = claim_response.json()
    assert claim_payload["batchIndex"] == 1
    assert claim_payload["batchTotal"] == 1
    assert claim_payload["currentItemIndex"] == 1
    assert claim_payload["currentItem"]["id"] == seeded["item_a_id"]


def test_h5_task_package_repeated_claim_keeps_same_current_item_and_snapshot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-reclaim", site_key="h5-package-reclaim")
    auth_payload = _register_member(
        client,
        site_key="h5-package-reclaim",
        phone="+86139000444551",
        display_name="Package Reclaim Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package-reclaim",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text
    first_payload = first_claim.json()

    detail_after_first_claim = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_after_first_claim.status_code == 200, detail_after_first_claim.text
    detail_payload = detail_after_first_claim.json()

    second_claim = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert second_claim.status_code == 200, second_claim.text
    second_payload = second_claim.json()

    detail_after_second_claim = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_after_second_claim.status_code == 200, detail_after_second_claim.text
    second_detail_payload = detail_after_second_claim.json()

    assert first_payload["status"] == "active"
    assert second_payload["status"] == "active"
    assert first_payload["currentItem"]["id"] == seeded["item_a_id"]
    assert second_payload["currentItem"]["id"] == seeded["item_a_id"]
    assert second_payload["claimedAt"] == first_payload["claimedAt"]
    assert detail_payload["currentItem"]["id"] == seeded["item_a_id"]
    assert second_detail_payload["currentItem"]["id"] == seeded["item_a_id"]
    assert [item["id"] for item in detail_payload["items"]] == [item["id"] for item in second_detail_payload["items"]]
    assert [item["productName"] for item in detail_payload["items"]] == [
        item["productName"] for item in second_detail_payload["items"]
    ]

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        audit_logs = session.query(AuditLog).filter(
            AuditLog.account_id == "acct-h5-package-reclaim",
            AuditLog.action == "h5_task_package_claimed",
            AuditLog.target_id == seeded["package_id"],
        ).all()
        assert package.status == "active"
        assert package.visible_item_id == seeded["item_a_id"]
        assert len(audit_logs) == 1


def test_h5_task_package_purchase_advances_current_item_pointer(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-advance", site_key="h5-package-advance")
    auth_payload = _register_member(
        client,
        site_key="h5-package-advance",
        phone="+8613900044456",
        display_name="Package Advance Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package-advance",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    purchase_payload = first_purchase.json()
    assert purchase_payload["taskPackage"]["currentItemIndex"] == 2
    assert purchase_payload["taskPackage"]["currentItem"]["id"] == seeded["item_b_id"]
    assert purchase_payload["taskPackage"]["currentItem"]["productName"] == "Starter Product B"

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        item_a = session.query(TaskPackageInstanceItem).filter(TaskPackageInstanceItem.id == seeded["item_a_id"]).one()
        assert package.current_item_index == 2
        assert package.visible_item_id == seeded["item_b_id"]
        assert item_a.debit_ledger_id is not None
        assert item_a.completed_at is not None


def test_h5_task_package_completion_persists_reward_ledger_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-ledger", site_key="h5-package-ledger")
    auth_payload = _register_member(
        client,
        site_key="h5-package-ledger",
        phone="+8613900044458",
        display_name="Package Ledger Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package-ledger",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_b_id']}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        item_a = session.query(TaskPackageInstanceItem).filter(TaskPackageInstanceItem.id == seeded["item_a_id"]).one()
        item_b = session.query(TaskPackageInstanceItem).filter(TaskPackageInstanceItem.id == seeded["item_b_id"]).one()
        reward_entry = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.id == package.reward_ledger_id
        ).one()
        assert item_a.debit_ledger_id is not None
        assert item_b.debit_ledger_id is not None
        assert package.reward_amount_final == Decimal("10.00")
        assert package.reward_ledger_id is not None
        assert reward_entry.transaction_type == "task_reward"
        assert reward_entry.source_type == "task_reward"
        assert reward_entry.task_amount == Decimal("10.00")
        assert reward_entry.idempotency_key is not None

        audit_logs = session.query(AuditLog).filter(
            AuditLog.account_id == "acct-h5-package-ledger",
            AuditLog.action == "h5_task_reward_credited",
            AuditLog.actor_type == "member",
            AuditLog.actor_id == user.id,
            AuditLog.target_id == seeded["package_id"],
        ).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["amount"] == 10.0
        assert audit_logs[0].payload["currency"] == "USD"
        assert audit_logs[0].payload["transaction_type"] == "task_reward"


def test_h5_task_batch_blocks_claiming_next_package_before_previous_is_completed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-batch-claim-block", site_key="h5-batch-claim-block")
    auth_payload = _register_member(
        client,
        site_key="h5-batch-claim-block",
        phone="+8613900044457",
        display_name="Batch Claim Block Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-batch-claim-block",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text
    assert first_claim.json()["status"] == "active"

    blocked_claim = client.post(f"/api/h5/task-packages/{seeded['package_two_id']}/claim")
    assert blocked_claim.status_code == 409, blocked_claim.text
    assert "current batch package" in blocked_claim.json()["detail"].lower()


def test_h5_task_batch_unlocks_next_package_after_previous_completion(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-batch-unlock", site_key="h5-batch-unlock")
    auth_payload = _register_member(
        client,
        site_key="h5-batch-unlock",
        phone="+8613900044458",
        display_name="Batch Unlock Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-batch-unlock",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    first_payload = first_purchase.json()
    assert first_payload["taskPackage"]["status"] == "completed"

    second_claim = client.post(f"/api/h5/task-packages/{seeded['package_two_id']}/claim")
    assert second_claim.status_code == 200, second_claim.text
    second_payload = second_claim.json()
    assert second_payload["status"] == "active"
    assert second_payload["currentItemIndex"] == 1
    assert second_payload["currentItem"]["id"] == seeded["item_two_id"]

    with db_session_factory() as session:
        batch = session.query(MemberTaskBatch).filter(MemberTaskBatch.id == seeded["batch_id"]).one()
        package_two = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.id == seeded["package_two_id"]
        ).one()
        assert batch.completed_package_count == 1
        assert batch.current_package_index == 2
        assert batch.status == "active"
        assert batch.claimed_at is not None
        assert package_two.visible_item_id == seeded["item_two_id"]


def test_h5_task_batch_progress_labels_advance_from_one_of_five_to_two_of_five(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-batch-five", site_key="h5-batch-five")
    auth_payload = _register_member(
        client,
        site_key="h5-batch-five",
        phone="+86139000444581",
        display_name="Batch Five Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-batch-five",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
        package_amounts=[Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")],
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text
    first_payload = first_claim.json()
    assert first_payload["batchIndex"] == 1
    assert first_payload["batchTotal"] == 5

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    assert first_purchase.json()["taskPackage"]["status"] == "completed"

    second_claim = client.post(f"/api/h5/task-packages/{seeded['package_two_id']}/claim")
    assert second_claim.status_code == 200, second_claim.text
    second_payload = second_claim.json()
    assert second_payload["batchIndex"] == 2
    assert second_payload["batchTotal"] == 5
    assert second_payload["currentItem"]["id"] == seeded["item_two_id"]


def test_h5_task_batch_completion_marks_linked_quota_completed(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-batch-complete", site_key="h5-batch-complete")
    auth_payload = _register_member(
        client,
        site_key="h5-batch-complete",
        phone="+8613900044459",
        display_name="Batch Complete Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-batch-complete",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text
    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text

    second_claim = client.post(f"/api/h5/task-packages/{seeded['package_two_id']}/claim")
    assert second_claim.status_code == 200, second_claim.text
    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_two_id']}/items/{seeded['item_two_id']}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text
    assert second_purchase.json()["taskPackage"]["status"] == "completed"

    with db_session_factory() as session:
        batch = session.query(MemberTaskBatch).filter(MemberTaskBatch.id == seeded["batch_id"]).one()
        quota = session.query(MemberTaskDayQuota).filter(MemberTaskDayQuota.id == seeded["quota_id"]).one()
        assert batch.status == "completed"
        assert batch.completed_package_count == 2
        assert batch.completed_at is not None
        assert quota.status == "completed"


def test_h5_task_package_purchase_rejects_insufficient_balance(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-low", site_key="h5-package-low")
    auth_payload = _register_member(
        client,
        site_key="h5-package-low",
        phone="+8613900055555",
        display_name="Low Balance Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-package-low",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("10"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    purchase_response = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert purchase_response.status_code == 200, purchase_response.text
    purchase_payload = purchase_response.json()
    assert purchase_payload["success"] is False
    assert "balance" in purchase_payload["reason"].lower()
    assert purchase_payload["wallet"]["systemBalance"] == 10.0
    assert purchase_payload["taskPackage"]["completedItems"] == 0

    orders_response = client.get("/api/h5/orders")
    assert orders_response.status_code == 200, orders_response.text
    assert orders_response.json() == []


def test_h5_wallet_transfer_and_recharge_update_balances_and_ledgers(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-wallet", site_key="h5-wallet")
    auth_payload = _register_member(
        client,
        site_key="h5-wallet",
        phone="+8613900066666",
        display_name="Wallet Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-wallet",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("20"),
        task_balance=Decimal("88"),
    )
    assert seeded["package_id"]

    recharge_response = client.post("/api/h5/wallet/recharges", json={"amount": 30})
    assert recharge_response.status_code == 200, recharge_response.text
    assert recharge_response.json()["systemBalance"] == 50.0
    assert recharge_response.json()["taskBalance"] == 88.0

    transfer_response = client.post("/api/h5/wallet/transfers", json={"amount": 50})
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_payload = transfer_response.json()
    assert transfer_payload["systemBalance"] == 100.0
    assert transfer_payload["taskBalance"] == 38.0

    transactions_response = client.get("/api/h5/wallet/transactions")
    assert transactions_response.status_code == 200, transactions_response.text
    transaction_types = [item["transactionType"] for item in transactions_response.json()]
    assert "recharge" in transaction_types
    assert transaction_types.count("task_to_system_transfer") == 2

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert [item["title"] for item in messages[:2]] == [
        "Task balance transferred",
        "Recharge credited",
    ]
    assert [item["category"] for item in messages[:2]] == ["wallet", "wallet"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] == 2

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        assert wallet.system_balance == Decimal("100")
        assert wallet.system_cash_balance == Decimal("50")
        assert wallet.system_bonus_balance == Decimal("50")
        assert wallet.system_cash_frozen == Decimal("0")
        assert wallet.system_bonus_frozen == Decimal("0")

        recharge_ledger = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.transaction_type == "recharge",
        ).one()
        assert recharge_ledger.cash_amount == Decimal("30")
        assert recharge_ledger.bonus_amount == Decimal("0")
        assert recharge_ledger.fund_type == "cash"
        assert recharge_ledger.is_real_recharge is True

        transfer_credit_ledger = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.transaction_type == "task_to_system_transfer",
            WalletLedgerEntry.ledger_type == "system",
        ).one()
        assert transfer_credit_ledger.cash_amount == Decimal("0")
        assert transfer_credit_ledger.bonus_amount == Decimal("50")
        assert transfer_credit_ledger.fund_type == "bonus"

        audit_logs = session.query(AuditLog).filter(
            AuditLog.account_id == "acct-h5-wallet",
            AuditLog.action == "h5_task_balance_transferred",
            AuditLog.actor_type == "member",
            AuditLog.actor_id == user.id,
        ).all()
        assert len(audit_logs) == 1
        assert audit_logs[0].payload["amount"] == 50.0
        assert audit_logs[0].payload["currency"] == "USD"
        assert audit_logs[0].payload["transaction_type"] == "task_to_system_transfer"


def test_h5_recharge_auto_certifies_member_when_threshold_is_reached(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-recharge-certify", site_key="h5-recharge-certify")
    auth_payload = _register_member(
        client,
        site_key="h5-recharge-certify",
        phone="+8613900066667",
        display_name="Recharge Certify Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-recharge-certify",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        auto_certify_on_recharge=True,
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-recharge-certify",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )

    recharge_response = client.post("/api/h5/wallet/recharges", json={"amount": 50})
    assert recharge_response.status_code == 200, recharge_response.text

    verification_response = client.get("/api/h5/member/verification")
    assert verification_response.status_code == 200, verification_response.text
    assert verification_response.json()["currentStatus"] == "approved"

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        request = session.query(MemberVerificationRequest).filter(
            MemberVerificationRequest.account_id == "acct-h5-recharge-certify",
            MemberVerificationRequest.member_profile_id == member_profile.id,
        ).one()
        assert request.status == "approved"
        assert request.review_note is not None
        assert "auto" in request.review_note.lower()


def test_h5_recharge_auto_certification_respects_49_50_and_updated_100_thresholds(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-recharge-thresholds", site_key="h5-recharge-thresholds")
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-recharge-thresholds",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        auto_certify_on_recharge=True,
    )

    member_below = _register_member(
        client,
        site_key="h5-recharge-thresholds",
        phone="+8613900066670",
        display_name="Recharge Threshold 49 Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-recharge-thresholds",
        site_id=site["id"],
        public_user_id=member_below["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )
    recharge_49_response = client.post("/api/h5/wallet/recharges", json={"amount": 49})
    assert recharge_49_response.status_code == 200, recharge_49_response.text
    verification_49_response = client.get("/api/h5/member/verification")
    assert verification_49_response.status_code == 200, verification_49_response.text
    assert verification_49_response.json()["currentStatus"] != "approved"

    member_at_threshold = _register_member(
        client,
        site_key="h5-recharge-thresholds",
        phone="+8613900066671",
        display_name="Recharge Threshold 50 Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-recharge-thresholds",
        site_id=site["id"],
        public_user_id=member_at_threshold["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )
    recharge_50_response = client.post("/api/h5/wallet/recharges", json={"amount": 50})
    assert recharge_50_response.status_code == 200, recharge_50_response.text
    verification_50_response = client.get("/api/h5/member/verification")
    assert verification_50_response.status_code == 200, verification_50_response.text
    assert verification_50_response.json()["currentStatus"] == "approved"

    with db_session_factory() as session:
        config = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == "acct-h5-recharge-thresholds",
            TaskSystemConfig.site_id == site["id"],
        ).one()
        config.certified_recharge_threshold = Decimal("100.00")
        session.commit()

    member_after_update = _register_member(
        client,
        site_key="h5-recharge-thresholds",
        phone="+8613900066672",
        display_name="Recharge Threshold 100 Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-recharge-thresholds",
        site_id=site["id"],
        public_user_id=member_after_update["member"]["publicUserId"],
        system_balance=Decimal("0"),
        task_balance=Decimal("0"),
    )
    recharge_99_response = client.post("/api/h5/wallet/recharges", json={"amount": 99})
    assert recharge_99_response.status_code == 200, recharge_99_response.text
    verification_99_response = client.get("/api/h5/member/verification")
    assert verification_99_response.status_code == 200, verification_99_response.text
    assert verification_99_response.json()["currentStatus"] != "approved"

    recharge_1_response = client.post("/api/h5/wallet/recharges", json={"amount": 1})
    assert recharge_1_response.status_code == 200, recharge_1_response.text
    verification_100_response = client.get("/api/h5/member/verification")
    assert verification_100_response.status_code == 200, verification_100_response.text
    assert verification_100_response.json()["currentStatus"] == "approved"


def test_h5_main_flow_acceptance_progresses_from_certification_to_reward_and_transfer(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-main-flow", site_key="h5-main-flow")
    auth_payload = _register_member(
        client,
        site_key="h5-main-flow",
        phone="+8613900066688",
        display_name="Main Flow Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-main-flow",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-main-flow",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("30"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        user.has_whatsapp = True
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        package.template.package_type = "official"
        session.add(user)
        session.add(package.template)
        session.commit()

    before_recharge_entry = client.get("/api/h5/tasks/entry-state")
    assert before_recharge_entry.status_code == 200, before_recharge_entry.text
    before_recharge_payload = before_recharge_entry.json()
    assert before_recharge_payload["state"] == "need_certification"
    assert before_recharge_payload["remainingRechargeAmount"] == 50.0

    recharge_response = client.post("/api/h5/wallet/recharges", json={"amount": 50})
    assert recharge_response.status_code == 200, recharge_response.text

    after_recharge_entry = client.get("/api/h5/tasks/entry-state")
    assert after_recharge_entry.status_code == 200, after_recharge_entry.text
    after_recharge_payload = after_recharge_entry.json()
    assert after_recharge_payload["state"] == "official_batch_available"
    assert after_recharge_payload["taskPackageId"] == seeded["package_id"]

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    assert claim_response.json()["status"] == "active"

    active_entry = client.get("/api/h5/tasks/entry-state")
    assert active_entry.status_code == 200, active_entry.text
    active_payload = active_entry.json()
    assert active_payload["state"] == "official_batch_active"
    assert active_payload["taskPackageId"] == seeded["package_id"]

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_a_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    first_purchase_payload = first_purchase.json()
    assert first_purchase_payload["success"] is True
    assert first_purchase_payload["taskPackage"]["status"] == "active"
    assert first_purchase_payload["wallet"]["taskBalance"] == 0.0

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_response.status_code == 200, detail_response.text
    current_item_id = detail_response.json()["currentItem"]["id"]

    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{current_item_id}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text
    second_purchase_payload = second_purchase.json()
    assert second_purchase_payload["success"] is True
    assert second_purchase_payload["taskPackage"]["status"] == "completed"
    assert second_purchase_payload["wallet"]["taskBalance"] == 10.0

    next_entry = client.get("/api/h5/tasks/entry-state")
    assert next_entry.status_code == 200, next_entry.text
    next_entry_payload = next_entry.json()
    assert next_entry_payload["state"] == "no_task"
    assert next_entry_payload["taskPackageId"] is None

    transfer_response = client.post("/api/h5/wallet/transfers", json={"amount": 10})
    assert transfer_response.status_code == 200, transfer_response.text
    transfer_payload = transfer_response.json()
    assert transfer_payload["taskBalance"] == 0.0
    assert transfer_payload["systemBalance"] == 40.0

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == auth_payload["member"]["publicUserId"]).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.account_id == "acct-h5-main-flow",
            WalletLedgerEntry.user_id == user.id,
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()
        transfer_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.account_id == "acct-h5-main-flow",
            WalletLedgerEntry.user_id == user.id,
            WalletLedgerEntry.transaction_type == "task_to_system_transfer",
            WalletLedgerEntry.ledger_type == "system",
        ).all()

        assert wallet.task_balance == Decimal("0")
        assert wallet.system_balance == Decimal("40")
        assert wallet.system_cash_balance == Decimal("30")
        assert wallet.system_bonus_balance == Decimal("10")
        assert len(reward_entries) == 1
        assert reward_entries[0].task_amount == Decimal("10")
        assert len(transfer_entries) == 1
        assert transfer_entries[0].bonus_amount == Decimal("10")


def test_h5_task_package_detail_exposes_manual_added_amounts_and_current_item_origin(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-package-manual-view", site_key="h5-package-manual-view")
    auth_payload = _register_member(
        client,
        site_key="h5-package-manual-view",
        phone="+8613900066668",
        display_name="Package Manual View Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-package-manual-view",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("200"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        pool = TaskProductPool(
            account_id=package.account_id,
            site_id=package.site_id,
            name="Manual H5 Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
            currency="USD",
        )
        session.add(pool)
        session.flush()

        extra_item = TaskProductPoolItem(
            account_id=package.account_id,
            pool_id=pool.id,
            product_id="manual-h5-product-1",
            product_name="Manual H5 Product 1",
            image_url="https://example.com/manual-h5-1.png",
            price=Decimal("66.00"),
            currency="USD",
            product_description="Manual H5 Product 1 description",
            status="active",
            sort_order=1,
        )
        session.add(extra_item)
        session.flush()

        existing_items = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == package.id
        ).all()
        for item in existing_items:
            item.product_pool_id = pool.id
            session.add(item)
        session.commit()

        service.add_items(
            package_id=package.id,
            pool_item_ids=[extra_item.id],
            operator_id="staff-h5-manual-view",
            reason_text="客服追加任务商品",
        )

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_one_id']}")
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["manualAddedAmount"] == 66.0
    assert payload["effectiveAmount"] == 76.0
    assert payload["currentItem"]["origin"] == "manual_added"
    assert payload["hasAdjustmentNotice"] is False
    assert payload["adjustmentNotice"] is None


def test_h5_current_item_matches_admin_detail_and_monitor_row_after_manual_add(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-current-item-sync", site_key="h5-current-item-sync")
    auth_payload = _register_member(
        client,
        site_key="h5-current-item-sync",
        phone="+8613900066680",
        display_name="Current Item Sync Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-current-item-sync",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        pool = session.query(TaskProductPool).filter(TaskProductPool.id == package.items[0].product_pool_id).one_or_none()
        if pool is None:
            pool = session.query(TaskProductPool).filter(TaskProductPool.account_id == package.account_id).one()
            for item in package.items:
                item.product_pool_id = pool.id
                session.add(item)
            session.flush()

        extra_item = TaskProductPoolItem(
            account_id=package.account_id,
            pool_id=pool.id,
            product_id="manual-sync-product-1",
            product_name="Manual Sync Product",
            image_url="https://example.com/manual-sync.png",
            price=Decimal("66.00"),
            currency="USD",
            product_description="Manual sync add-on product",
            status="active",
            sort_order=55,
        )
        session.add(extra_item)
        session.flush()

        service.add_items(
            package_id=package.id,
            pool_item_ids=[extra_item.id],
            operator_id="staff-current-item-sync",
            reason_text="sync current item across h5 admin monitor",
        )

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text

    h5_detail = client.get(f"/api/h5/task-packages/{seeded['package_one_id']}")
    assert h5_detail.status_code == 200, h5_detail.text
    h5_payload = h5_detail.json()
    current_item = h5_payload["currentItem"]
    assert current_item["origin"] == "manual_added"

    admin_detail = client.get(
        f"/api/tasks/packages/{seeded['package_one_id']}",
        headers=_operator_headers("acct-h5-current-item-sync"),
    )
    assert admin_detail.status_code == 200, admin_detail.text
    admin_payload = admin_detail.json()
    admin_current_item = admin_payload["items"][-1]
    assert admin_current_item["origin"] == "manual_added"

    monitor_response = client.get(
        "/api/tasks/monitor/query",
        params={"account_id": "acct-h5-current-item-sync"},
        headers=_operator_headers("acct-h5-current-item-sync"),
    )
    assert monitor_response.status_code == 200, monitor_response.text
    monitor_payload = monitor_response.json()
    assert len(monitor_payload) == 2
    row = next(item for item in monitor_payload if item["packageId"] == seeded["package_one_id"])

    assert row["currentItemIndex"] == h5_payload["currentItemIndex"]
    assert row["currentProductOrigin"] == current_item["origin"]
    assert row["currentProductId"] == current_item["id"]
    assert row["currentProductName"] == current_item["productName"]
    assert admin_current_item["id"] == current_item["id"]
    assert admin_current_item["productName"] == current_item["productName"]


def test_h5_manual_added_items_delay_completion_and_recalculate_reward_from_effective_amount(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-manual-reward", site_key="h5-manual-reward")
    auth_payload = _register_member(
        client,
        site_key="h5-manual-reward",
        phone="+8613900066669",
        display_name="Manual Reward Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-manual-reward",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        pool = session.query(TaskProductPool).filter(TaskProductPool.id == package.items[0].product_pool_id).one_or_none()
        if pool is None:
            pool = session.query(TaskProductPool).filter(TaskProductPool.account_id == package.account_id).one()
            for item in package.items:
                item.product_pool_id = pool.id
                session.add(item)
            session.flush()

        extra_item = TaskProductPoolItem(
            account_id=package.account_id,
            pool_id=pool.id,
            product_id="manual-reward-product-1",
            product_name="Manual Reward Product",
            image_url="https://example.com/manual-reward.png",
            price=Decimal("66.00"),
            currency="USD",
            product_description="Manual reward add-on product",
            status="active",
            sort_order=50,
        )
        session.add(extra_item)
        session.flush()

        service.add_items(
            package_id=package.id,
            pool_item_ids=[extra_item.id],
            operator_id="staff-manual-reward",
            reason_text="客服追加商品用于奖励重算",
        )

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text
    first_payload = first_purchase.json()
    assert first_payload["taskPackage"]["status"] == "active"
    assert first_payload["taskPackage"]["currentItem"]["origin"] == "manual_added"

    blocked_claim = client.post(f"/api/h5/task-packages/{seeded['package_two_id']}/claim")
    assert blocked_claim.status_code == 409, blocked_claim.text

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_one_id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    manual_item_id = detail_payload["currentItem"]["id"]

    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{manual_item_id}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text
    second_payload = second_purchase.json()
    assert second_payload["taskPackage"]["status"] == "completed"

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        reward_entry = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.id == package.reward_ledger_id
        ).one()
        assert package.manual_added_amount == Decimal("66.00")
        assert package.effective_amount == Decimal("76.00")
        assert package.reward_amount_final == Decimal("7.60")
        assert reward_entry.task_amount == Decimal("7.60")


def test_h5_last_system_item_purchase_does_not_settle_reward_before_concurrent_manual_add(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    site = _create_site(client, account_id="acct-h5-manual-race", site_key="h5-manual-race")
    auth_payload = _register_member(
        client,
        site_key="h5-manual-race",
        phone="+8613900066679",
        display_name="Manual Race Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-manual-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        pool = session.query(TaskProductPool).filter(TaskProductPool.id == package.items[0].product_pool_id).one_or_none()
        if pool is None:
            pool = session.query(TaskProductPool).filter(TaskProductPool.account_id == package.account_id).one()
            for item in package.items:
                item.product_pool_id = pool.id
                session.add(item)
            session.flush()

        extra_item = TaskProductPoolItem(
            account_id=package.account_id,
            pool_id=pool.id,
            product_id="manual-race-product-1",
            product_name="Manual Race Product",
            image_url="https://example.com/manual-race.png",
            price=Decimal("66.00"),
            currency="USD",
            product_description="Concurrent manual add product",
            status="active",
            sort_order=52,
        )
        session.add(extra_item)
        session.commit()
        extra_item_id = extra_item.id

    original_debit_system_balance = WalletLedgerService.debit_system_balance
    injected_manual_add = False

    def debit_with_concurrent_manual_add(self: WalletLedgerService, **kwargs):
        nonlocal injected_manual_add
        split, ledger = original_debit_system_balance(self, **kwargs)
        if not injected_manual_add:
            injected_manual_add = True
            with db_session_factory() as competing_session:
                add_service = TaskManualAddService(session=competing_session)
                add_service.add_items(
                    package_id=seeded["package_one_id"],
                    pool_item_ids=[extra_item_id],
                    operator_id="staff-manual-race",
                    reason_text="concurrent manual add before reward settlement",
                )
        return split, ledger

    monkeypatch.setattr(WalletLedgerService, "debit_system_balance", debit_with_concurrent_manual_add)

    purchase_response = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert purchase_response.status_code == 200, purchase_response.text
    payload = purchase_response.json()
    assert payload["taskPackage"]["status"] == "active"
    assert payload["taskPackage"]["currentItem"]["origin"] == "manual_added"

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.account_id == "acct-h5-manual-race",
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_one_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()
        assert package.status == "active"
        assert package.completed_at is None
        assert package.reward_ledger_id is None
        assert package.task_balance_awarded_at is None
        assert len(reward_entries) == 0


def test_h5_task_item_purchase_ledger_source_type_distinguishes_system_and_manual_items(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-ledger-origin", site_key="h5-ledger-origin")
    auth_payload = _register_member(
        client,
        site_key="h5-ledger-origin",
        phone="+8613900066670",
        display_name="Ledger Origin Member",
    )
    seeded = _seed_task_batch_scope(
        db_session_factory,
        account_id="acct-h5-ledger-origin",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("300"),
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_one_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text

    with db_session_factory() as session:
        service = TaskManualAddService(session=session)
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_one_id"]).one()
        pool = session.query(TaskProductPool).filter(TaskProductPool.id == package.items[0].product_pool_id).one_or_none()
        if pool is None:
            pool = session.query(TaskProductPool).filter(TaskProductPool.account_id == package.account_id).one()
            for item in package.items:
                item.product_pool_id = pool.id
                session.add(item)
            session.flush()

        extra_item = TaskProductPoolItem(
            account_id=package.account_id,
            pool_id=pool.id,
            product_id="ledger-origin-product-1",
            product_name="Ledger Origin Product",
            image_url="https://example.com/ledger-origin.png",
            price=Decimal("66.00"),
            currency="USD",
            product_description="Ledger origin add-on product",
            status="active",
            sort_order=51,
        )
        session.add(extra_item)
        session.flush()

        service.add_items(
            package_id=package.id,
            pool_item_ids=[extra_item.id],
            operator_id="staff-ledger-origin",
            reason_text="追加商品用于校验账务来源类型",
        )

    first_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{seeded['item_one_id']}/purchase"
    )
    assert first_purchase.status_code == 200, first_purchase.text

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_one_id']}")
    assert detail_response.status_code == 200, detail_response.text
    manual_item_id = detail_response.json()["currentItem"]["id"]

    second_purchase = client.post(
        f"/api/h5/task-packages/{seeded['package_one_id']}/items/{manual_item_id}/purchase"
    )
    assert second_purchase.status_code == 200, second_purchase.text

    with db_session_factory() as session:
        purchased_items = (
            session.query(TaskPackageInstanceItem)
            .filter(TaskPackageInstanceItem.package_instance_id == seeded["package_one_id"])
            .order_by(TaskPackageInstanceItem.sort_order.asc())
            .all()
        )
        system_item = purchased_items[0]
        manual_item = purchased_items[1]
        system_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == system_item.debit_ledger_id).one()
        manual_entry = session.query(WalletLedgerEntry).filter(WalletLedgerEntry.id == manual_item.debit_ledger_id).one()

        assert system_item.item_origin == "system_generated"
        assert manual_item.item_origin == "manual_added"
        assert system_entry.source_type == "task_item_purchase_system_generated"
        assert manual_entry.source_type == "task_item_purchase_manual_added"


def test_h5_member_home_includes_wallet_and_task_package_counts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-home-slice3", site_key="h5-home-slice3")
    auth_payload = _register_member(
        client,
        site_key="h5-home-slice3",
        phone="+8613900077777",
        display_name="Home Member",
    )
    _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-home-slice3",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("200"),
        task_balance=Decimal("30"),
    )

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    payload = home_response.json()
    assert payload["wallet"]["systemBalance"] == 200.0
    assert payload["wallet"]["taskBalance"] == 30.0
    assert payload["pendingClaimCount"] == 1
    assert payload["activeCount"] == 0
    assert payload["expiringCount"] == 0


def test_h5_promotion_task_package_uses_invited_registration_progress(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-registrations", site_key="h5-promotion-registrations")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-registrations",
        phone="+8613900067771",
        display_name="Promotion Registrations Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-registrations",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=5,
        invited_registration_count=3,
        recharged_invitee_count=1,
    )

    list_response = client.get("/api/h5/task-packages")
    assert list_response.status_code == 200, list_response.text
    packages = list_response.json()
    assert [item["id"] for item in packages] == [seeded["package_id"]]
    assert packages[0]["promotion"] == {
        "metric": "invited_registrations",
        "current": 3,
        "target": 5,
        "inviteCode": seeded["invite_code"],
    }


def test_h5_promotion_task_package_uses_recharged_invitee_progress(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-recharges", site_key="h5-promotion-recharges")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-recharges",
        phone="+8613900067772",
        display_name="Promotion Recharges Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-recharges",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="recharged_invitees",
        target_value=4,
        invited_registration_count=3,
        recharged_invitee_count=2,
    )

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["promotion"] == {
        "metric": "recharged_invitees",
        "current": 2,
        "target": 4,
        "inviteCode": seeded["invite_code"],
    }


def test_h5_promotion_task_package_bootstraps_missing_promotion_rows_on_first_read(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-bootstrap", site_key="h5-promotion-bootstrap")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-bootstrap",
        phone="+8613900067773",
        display_name="Promotion Bootstrap Member",
    )
    seeded = _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-bootstrap",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=3,
    )

    list_response = client.get("/api/h5/task-packages")
    assert list_response.status_code == 200, list_response.text
    packages = list_response.json()
    assert [item["id"] for item in packages] == [seeded["package_id"]]
    assert packages[0]["promotion"] == {
        "metric": "invited_registrations",
        "current": 0,
        "target": 3,
        "inviteCode": packages[0]["promotion"]["inviteCode"],
    }
    assert packages[0]["promotion"]["inviteCode"].startswith("PROMO-")

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        promotion_template = session.query(PromotionTaskTemplate).filter(
            PromotionTaskTemplate.task_package_template_id == package.template_id
        ).one()
        promotion_instance = session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == package.id
        ).one()
        invite_code = session.query(InviteCode).filter(
            InviteCode.site_id == site["id"],
            InviteCode.inviter_user_id == package.user_id,
            InviteCode.code == promotion_instance.invite_code_snapshot,
        ).one()

        assert promotion_template.metric == "invited_registrations"
        assert promotion_template.target_value == 3
        assert promotion_instance.metric == "invited_registrations"
        assert promotion_instance.target_value == 3
        assert promotion_instance.current_value == 0
        assert promotion_instance.invite_code_snapshot == invite_code.code


def test_h5_promotion_task_package_bootstrap_recovers_from_template_unique_conflict(
    db_session_factory: sessionmaker[Session],
    client: TestClient,
    monkeypatch,
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-bootstrap-template-race", site_key="h5-promotion-bootstrap-template-race")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-bootstrap-template-race",
        phone="+86139000677731",
        display_name="Promotion Bootstrap Template Race Member",
    )
    seeded = _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-bootstrap-template-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=3,
    )

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677731",
        )
        service = H5MemberCommerceService(session=session)
        original_flush = session.flush
        triggered = False

        def flush_with_template_conflict(*args, **kwargs):
            nonlocal triggered
            if not triggered and any(isinstance(item, PromotionTaskTemplate) for item in session.new):
                with db_session_factory() as competing:
                    package = competing.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
                    competing.add(
                        PromotionTaskTemplate(
                            account_id="acct-h5-promotion-bootstrap-template-race",
                            task_package_template_id=package.template_id,
                            metric="invited_registrations",
                            target_value=3,
                            status="active",
                        )
                    )
                    competing.commit()
                triggered = True
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", flush_with_template_conflict)

        packages = asyncio.run(service.list_task_packages(context=context))
        assert [item.id for item in packages] == [seeded["package_id"]]
        assert packages[0].promotion is not None
        assert packages[0].promotion.metric == "invited_registrations"
        assert packages[0].promotion.target == 3
    finally:
        session.close()

    with db_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        promotion_templates = verify_session.query(PromotionTaskTemplate).filter(
            PromotionTaskTemplate.task_package_template_id == package.template_id
        ).all()
        promotion_instance = verify_session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == package.id
        ).one()

        assert len(promotion_templates) == 1
        assert promotion_instance.metric == "invited_registrations"
        assert promotion_instance.target_value == 3


def test_h5_promotion_task_package_bootstrap_recovers_from_instance_unique_conflict(
    db_session_factory: sessionmaker[Session],
    client: TestClient,
    monkeypatch,
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-bootstrap-instance-race", site_key="h5-promotion-bootstrap-instance-race")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-bootstrap-instance-race",
        phone="+86139000677732",
        display_name="Promotion Bootstrap Instance Race Member",
    )
    seeded = _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-bootstrap-instance-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=4,
    )

    with db_session_factory() as setup_session:
        package = setup_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        user = setup_session.query(AppUser).filter(AppUser.id == package.user_id).one()
        member_profile = setup_session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        promotion_template = PromotionTaskTemplate(
            account_id="acct-h5-promotion-bootstrap-instance-race",
            task_package_template_id=package.template_id,
            metric="invited_registrations",
            target_value=4,
            status="active",
        )
        invite_code = InviteCode(
            code="PROMO-BOOTSTRAP-RACE",
            site_id=site["id"],
            inviter_user_id=user.id,
            status="active",
        )
        setup_session.add_all([promotion_template, invite_code])
        setup_session.flush()
        setup_session.commit()
        promotion_template_id = promotion_template.id
        member_profile_id = member_profile.id
        user_id = user.id

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677732",
        )
        service = H5MemberCommerceService(session=session)
        original_flush = session.flush
        triggered = False

        def flush_with_instance_conflict(*args, **kwargs):
            nonlocal triggered
            if not triggered and any(isinstance(item, PromotionTaskInstance) for item in session.new):
                with db_session_factory() as competing:
                    competing.add(
                        PromotionTaskInstance(
                            account_id="acct-h5-promotion-bootstrap-instance-race",
                            promotion_task_template_id=promotion_template_id,
                            task_package_instance_id=seeded["package_id"],
                            user_id=user_id,
                            member_profile_id=member_profile_id,
                            metric="invited_registrations",
                            target_value=4,
                            invite_code_snapshot="PROMO-BOOTSTRAP-RACE",
                            current_value=0,
                            status="active",
                        )
                    )
                    competing.commit()
                triggered = True
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", flush_with_instance_conflict)

        packages = asyncio.run(service.list_task_packages(context=context))
        assert [item.id for item in packages] == [seeded["package_id"]]
        assert packages[0].promotion is not None
        assert packages[0].promotion.metric == "invited_registrations"
        assert packages[0].promotion.target == 4
        assert packages[0].promotion.invite_code == "PROMO-BOOTSTRAP-RACE"
    finally:
        session.close()

    with db_session_factory() as verify_session:
        promotion_instances = verify_session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == seeded["package_id"]
        ).all()
        assert len(promotion_instances) == 1
        assert promotion_instances[0].invite_code_snapshot == "PROMO-BOOTSTRAP-RACE"


def test_h5_promotion_task_package_bootstrap_retries_when_generated_invite_code_conflicts(
    db_session_factory: sessionmaker[Session],
    client: TestClient,
    monkeypatch,
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-bootstrap-invite-race", site_key="h5-promotion-bootstrap-invite-race")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-bootstrap-invite-race",
        phone="+86139000677733",
        display_name="Promotion Bootstrap Invite Race Member",
    )
    seeded = _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-bootstrap-invite-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=2,
    )

    with db_session_factory() as setup_session:
        competing_user = AppUser(
            account_id="acct-h5-promotion-bootstrap-invite-race",
            public_user_id="h5-promotion-bootstrap-invite-race-competing",
            registration_site_id=site["id"],
            display_name="Competing Invite Owner",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
            last_active_at=utc_now(),
        )
        setup_session.add(competing_user)
        setup_session.flush()
        setup_session.add(
            InviteCode(
                code="PROMO-CONFLICT-CODE",
                site_id=site["id"],
                inviter_user_id=competing_user.id,
                status="active",
            )
        )
        setup_session.commit()

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677733",
        )
        service = H5MemberCommerceService(session=session)
        generated_codes = iter(["PROMO-CONFLICT-CODE", "PROMO-RECOVERED-CODE"])
        monkeypatch.setattr(service, "_generate_promotion_invite_code", lambda: next(generated_codes))

        packages = asyncio.run(service.list_task_packages(context=context))
        assert [item.id for item in packages] == [seeded["package_id"]]
        assert packages[0].promotion is not None
        assert packages[0].promotion.invite_code == "PROMO-RECOVERED-CODE"
    finally:
        session.close()

    with db_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        promotion_instance = verify_session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == package.id
        ).one()
        invite_codes = verify_session.query(InviteCode).filter(
            InviteCode.site_id == site["id"],
            InviteCode.code.like("PROMO-%"),
        ).all()

        assert {item.code for item in invite_codes} >= {"PROMO-CONFLICT-CODE", "PROMO-RECOVERED-CODE"}
        assert promotion_instance.invite_code_snapshot == "PROMO-RECOVERED-CODE"


def test_h5_promotion_task_package_counts_only_snapshot_invite_code_referrals(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-snapshot", site_key="h5-promotion-snapshot")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-snapshot",
        phone="+8613900067774",
        display_name="Promotion Snapshot Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-snapshot",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=5,
        invited_registration_count=1,
        recharged_invitee_count=0,
    )

    with db_session_factory() as session:
        inviter = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        alternate_code = InviteCode(
            code="PROMO-ALT-SNAPSHOT",
            site_id=site["id"],
            inviter_user_id=inviter.id,
            status="active",
        )
        session.add(alternate_code)
        session.flush()

        referred_user = AppUser(
            account_id="acct-h5-promotion-snapshot",
            public_user_id="h5-promotion-snapshot-alt-referral",
            registration_site_id=site["id"],
            display_name="Alt Referral",
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=True,
            is_new_user=True,
            restrict_task_claim=False,
            registration_invite_code=alternate_code.code,
            last_active_at=utc_now(),
        )
        session.add(referred_user)
        session.flush()

        referred_profile = MemberProfile(
            account_id="acct-h5-promotion-snapshot",
            user_id=referred_user.id,
            member_no="87654321",
            password_hash="seeded-password-hash",
            password_salt="seeded-password-salt",
            password_updated_at=utc_now(),
            last_login_at=utc_now(),
        )
        session.add(referred_profile)
        session.flush()

        session.add(
            UserReferral(
                account_id="acct-h5-promotion-snapshot",
                site_id=site["id"],
                invite_code=alternate_code.code,
                referrer_user_id=inviter.id,
                referred_user_id=referred_user.id,
                referred_member_profile_id=referred_profile.id,
                registered_at=utc_now(),
            )
        )
        session.commit()

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["promotion"] == {
        "metric": "invited_registrations",
        "current": 1,
        "target": 5,
        "inviteCode": seeded["invite_code"],
    }


def test_h5_promotion_task_package_claim_requires_target_completion(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-claim-gate", site_key="h5-promotion-claim-gate")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-gate",
        phone="+8613900067775",
        display_name="Promotion Claim Gate Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-gate",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=3,
        invited_registration_count=1,
        recharged_invitee_count=0,
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 409, claim_response.text
    assert claim_response.json()["detail"] == "Promotion task target has not been reached yet."


def test_h5_task_package_claim_enforces_whatsapp_claim_gate_snapshot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-claim-gate-whatsapp", site_key="h5-claim-gate-whatsapp")
    auth_payload = _register_member(
        client,
        site_key="h5-claim-gate-whatsapp",
        phone="+86139000677756",
        display_name="WhatsApp Gate Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-claim-gate-whatsapp",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        package.claim_gate_snapshot = "whatsapp_bound"
        session.commit()

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 409, claim_response.text
    assert claim_response.json()["detail"] == "This task package requires a bound WhatsApp account before claiming."


def test_h5_task_package_claim_enforces_certified_member_claim_gate_snapshot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-claim-gate-certified", site_key="h5-claim-gate-certified")
    auth_payload = _register_member(
        client,
        site_key="h5-claim-gate-certified",
        phone="+86139000677757",
        display_name="Certified Gate Member",
    )
    seeded = _seed_task_package_scope(
        db_session_factory,
        account_id="acct-h5-claim-gate-certified",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("100"),
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-claim-gate-certified",
        site_id=site["id"],
        certified_member_enabled=True,
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        package.claim_gate_snapshot = "certified_member"
        session.commit()

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 409, claim_response.text
    assert claim_response.json()["detail"] == "This task package requires certification before claiming."


def test_h5_promotion_task_package_claim_settles_reward_after_target_completion(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-claim-reward", site_key="h5-promotion-claim-reward")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-reward",
        phone="+86139000677755",
        display_name="Promotion Claim Reward Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-reward",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    payload = claim_response.json()
    assert payload["status"] == "completed"
    assert payload["claimedAt"] is not None
    assert payload["completedAt"] is not None
    assert payload["taskBalanceAwardedAt"] is not None
    assert payload["countdownSeconds"] == 0

    wallet_response = client.get("/api/h5/wallet")
    assert wallet_response.status_code == 200, wallet_response.text
    wallet_payload = wallet_response.json()
    assert wallet_payload["systemBalance"] == 0.0
    assert wallet_payload["taskBalance"] == 2.16

    transactions_response = client.get("/api/h5/wallet/transactions")
    assert transactions_response.status_code == 200, transactions_response.text
    transactions = transactions_response.json()
    task_rewards = [item for item in transactions if item["transactionType"] == "task_reward"]
    assert len(task_rewards) == 1
    assert task_rewards[0]["ledgerType"] == "task"
    assert task_rewards[0]["amount"] == 2.16

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert messages[0]["title"] == "Task reward credited"
    assert messages[0]["category"] == "task"
    assert "2.16 USD" in messages[0]["bodyText"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] == 1

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        promotion_instance = session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == seeded["package_id"]
        ).one()
        wallet = session.query(WalletAccount).filter(
            WalletAccount.account_id == "acct-h5-promotion-claim-reward",
            WalletAccount.user_id == package.user_id,
        ).one()
        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert package.completed_at is not None
        assert package.task_balance_awarded_at is not None
        assert promotion_instance.achieved_at is not None
        assert promotion_instance.rewarded_at is not None
        assert wallet.task_balance == Decimal("2.16")
        assert len(reward_entries) == 1


def test_h5_promotion_task_package_repeated_claim_is_idempotent_after_reward(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-claim-idempotent", site_key="h5-promotion-claim-idempotent")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-idempotent",
        phone="+86139000677756",
        display_name="Promotion Claim Idempotent Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-idempotent",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    first_claim = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert first_claim.status_code == 200, first_claim.text
    first_payload = first_claim.json()
    assert first_payload["status"] == "completed"
    awarded_at = first_payload["taskBalanceAwardedAt"]

    second_claim = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert second_claim.status_code == 200, second_claim.text
    second_payload = second_claim.json()
    assert second_payload["status"] == "completed"
    assert second_payload["taskBalanceAwardedAt"] == awarded_at

    wallet_response = client.get("/api/h5/wallet")
    assert wallet_response.status_code == 200, wallet_response.text
    assert wallet_response.json()["taskBalance"] == 2.16

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert len(reward_entries) == 1


def test_h5_promotion_task_package_claim_reuses_existing_reward_ledger_without_double_credit(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(
        client,
        account_id="acct-h5-promotion-claim-ledger-reuse",
        site_key="h5-promotion-claim-ledger-reuse",
    )
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-ledger-reuse",
        phone="+86139000677757",
        display_name="Promotion Claim Ledger Reuse Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-ledger-reuse",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        wallet = WalletAccount(
            account_id="acct-h5-promotion-claim-ledger-reuse",
            user_id=package.user_id,
            system_balance=Decimal("0"),
            task_balance=Decimal("2.16"),
            currency="USD",
            withdraw_threshold=Decimal("100"),
        )
        session.add(wallet)
        session.flush()
        session.add(
            WalletLedgerEntry(
                account_id="acct-h5-promotion-claim-ledger-reuse",
                wallet_account_id=wallet.id,
                user_id=package.user_id,
                ledger_type="task",
                transaction_type="task_reward",
                direction="credit",
                amount=Decimal("2.16"),
                currency="USD",
                status="paid",
                note="Pre-existing reward entry",
                reference_type="task_package_instance",
                reference_id=package.id,
            )
        )
        session.commit()

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    assert claim_response.json()["status"] == "completed"
    assert claim_response.json()["taskBalanceAwardedAt"] is not None

    wallet_response = client.get("/api/h5/wallet")
    assert wallet_response.status_code == 200, wallet_response.text
    assert wallet_response.json()["taskBalance"] == 2.16

    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.task_balance_awarded_at is not None
        assert len(reward_entries) == 1


def test_h5_promotion_task_package_claim_recovers_from_wallet_creation_unique_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    site = _create_site(
        client,
        account_id="acct-h5-promotion-claim-wallet-race",
        site_key="h5-promotion-claim-wallet-race",
    )
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-wallet-race",
        phone="+86139000677758",
        display_name="Promotion Claim Wallet Race Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-wallet-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677758",
        )
        service = H5MemberCommerceService(session=session)
        original_commit = session.commit
        triggered = False

        def commit_with_wallet_conflict(*args, **kwargs):
            nonlocal triggered
            if not triggered and any(isinstance(item, WalletAccount) for item in session.new):
                with db_session_factory() as competing:
                    user = competing.query(AppUser).filter(
                        AppUser.public_user_id == auth_payload["member"]["publicUserId"]
                    ).one()
                    competing.add(
                        WalletAccount(
                            account_id="acct-h5-promotion-claim-wallet-race",
                            user_id=user.id,
                            system_balance=Decimal("0"),
                            task_balance=Decimal("0"),
                            currency="USD",
                            withdraw_threshold=Decimal("100"),
                        )
                    )
                    competing.commit()
                triggered = True
            return original_commit(*args, **kwargs)

        monkeypatch.setattr(session, "commit", commit_with_wallet_conflict)

        payload = asyncio.run(service.claim_task_package(context=context, package_id=seeded["package_id"]))
        assert payload.status == "completed"
        assert payload.task_balance_awarded_at is not None
    finally:
        session.close()

    with db_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        wallets = verify_session.query(WalletAccount).filter(
            WalletAccount.account_id == "acct-h5-promotion-claim-wallet-race",
            WalletAccount.user_id == package.user_id,
        ).all()
        reward_entries = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert len(wallets) == 1
        assert wallets[0].task_balance == Decimal("2.16")
        assert len(reward_entries) == 1


def test_h5_promotion_task_package_claim_recovers_from_reward_ledger_unique_conflict_on_commit(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    site = _create_site(
        client,
        account_id="acct-h5-promotion-claim-ledger-race",
        site_key="h5-promotion-claim-ledger-race",
    )
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-ledger-race",
        phone="+86139000677759",
        display_name="Promotion Claim Ledger Race Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-ledger-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    with db_session_factory() as setup_session:
        package = setup_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        setup_session.add(
            WalletAccount(
                account_id="acct-h5-promotion-claim-ledger-race",
                user_id=package.user_id,
                system_balance=Decimal("0"),
                task_balance=Decimal("0"),
                currency="USD",
                withdraw_threshold=Decimal("100"),
            )
        )
        setup_session.commit()

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677759",
        )
        service = H5MemberCommerceService(session=session)
        original_commit = session.commit
        triggered = False

        def commit_with_reward_ledger_conflict(*args, **kwargs):
            nonlocal triggered
            if not triggered and any(
                isinstance(item, WalletLedgerEntry) and item.transaction_type == "task_reward"
                for item in session.new
            ):
                with db_session_factory() as competing:
                    package = competing.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
                    wallet = competing.query(WalletAccount).filter(
                        WalletAccount.account_id == "acct-h5-promotion-claim-ledger-race",
                        WalletAccount.user_id == package.user_id,
                    ).one()
                    promotion_instance = competing.query(PromotionTaskInstance).filter(
                        PromotionTaskInstance.task_package_instance_id == package.id
                    ).one()
                    now = utc_now()
                    package.status = "completed"
                    package.claimed_at = now
                    package.completed_at = now
                    package.expires_at = now
                    package.task_balance_awarded_at = now
                    wallet.task_balance = Decimal("2.16")
                    promotion_instance.rewarded_at = now
                    promotion_instance.status = "completed"
                    competing.add(package)
                    competing.add(wallet)
                    competing.add(promotion_instance)
                    competing.add(
                        WalletLedgerEntry(
                            account_id="acct-h5-promotion-claim-ledger-race",
                            wallet_account_id=wallet.id,
                            user_id=package.user_id,
                            ledger_type="task",
                            transaction_type="task_reward",
                            direction="credit",
                            amount=Decimal("2.16"),
                            currency="USD",
                            status="paid",
                            note="Competing reward entry",
                            reference_type="task_package_instance",
                            reference_id=package.id,
                        )
                    )
                    competing.commit()
                triggered = True
            return original_commit(*args, **kwargs)

        monkeypatch.setattr(session, "commit", commit_with_reward_ledger_conflict)

        payload = asyncio.run(service.claim_task_package(context=context, package_id=seeded["package_id"]))
        assert payload.status == "completed"
        assert payload.task_balance_awarded_at is not None
    finally:
        session.close()

    with db_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        wallet = verify_session.query(WalletAccount).filter(
            WalletAccount.account_id == "acct-h5-promotion-claim-ledger-race",
            WalletAccount.user_id == package.user_id,
        ).one()
        promotion_instance = verify_session.query(PromotionTaskInstance).filter(
            PromotionTaskInstance.task_package_instance_id == package.id
        ).one()
        reward_entries = verify_session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.reference_type == "task_package_instance",
            WalletLedgerEntry.reference_id == seeded["package_id"],
            WalletLedgerEntry.transaction_type == "task_reward",
        ).all()

        assert package.status == "completed"
        assert wallet.task_balance == Decimal("2.16")
        assert promotion_instance.rewarded_at is not None
        assert len(reward_entries) == 1


def test_h5_promotion_task_package_claim_returns_reloaded_completed_payload_after_commit_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    site = _create_site(
        client,
        account_id="acct-h5-promotion-claim-payload-race",
        site_key="h5-promotion-claim-payload-race",
    )
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-claim-payload-race",
        phone="+86139000677760",
        display_name="Promotion Claim Payload Race Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-claim-payload-race",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    with db_session_factory() as setup_session:
        package = setup_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
        setup_session.add(
            WalletAccount(
                account_id="acct-h5-promotion-claim-payload-race",
                user_id=package.user_id,
                system_balance=Decimal("0"),
                task_balance=Decimal("0"),
                currency="USD",
                withdraw_threshold=Decimal("100"),
            )
        )
        setup_session.commit()

    session = db_session_factory()
    try:
        context = _load_h5_member_context(
            session,
            public_user_id=auth_payload["member"]["publicUserId"],
            site_id=site["id"],
            phone="+86139000677760",
        )
        service = H5MemberCommerceService(session=session)
        original_commit = session.commit
        triggered = False

        def commit_with_competing_completion(*args, **kwargs):
            nonlocal triggered
            if not triggered and any(
                isinstance(item, WalletLedgerEntry) and item.transaction_type == "task_reward"
                for item in session.new
            ):
                with db_session_factory() as competing:
                    package = competing.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()
                    wallet = competing.query(WalletAccount).filter(
                        WalletAccount.account_id == "acct-h5-promotion-claim-payload-race",
                        WalletAccount.user_id == package.user_id,
                    ).one()
                    promotion_instance = competing.query(PromotionTaskInstance).filter(
                        PromotionTaskInstance.task_package_instance_id == package.id
                    ).one()
                    now = utc_now()
                    package.status = "completed"
                    package.claimed_at = now
                    package.completed_at = now
                    package.expires_at = now
                    package.task_balance_awarded_at = now
                    wallet.task_balance = Decimal("2.16")
                    promotion_instance.rewarded_at = now
                    promotion_instance.status = "completed"
                    competing.add(package)
                    competing.add(wallet)
                    competing.add(promotion_instance)
                    competing.add(
                        WalletLedgerEntry(
                            account_id="acct-h5-promotion-claim-payload-race",
                            wallet_account_id=wallet.id,
                            user_id=package.user_id,
                            ledger_type="task",
                            transaction_type="task_reward",
                            direction="credit",
                            amount=Decimal("2.16"),
                            currency="USD",
                            status="paid",
                            note="Competing reward entry for payload reload",
                            reference_type="task_package_instance",
                            reference_id=package.id,
                        )
                    )
                    competing.commit()
                triggered = True
            return original_commit(*args, **kwargs)

        monkeypatch.setattr(session, "commit", commit_with_competing_completion)

        payload = asyncio.run(service.claim_task_package(context=context, package_id=seeded["package_id"]))
    finally:
        session.close()

    with db_session_factory() as verify_session:
        package = verify_session.query(TaskPackageInstance).filter(TaskPackageInstance.id == seeded["package_id"]).one()

        assert payload.status == "completed"
        assert payload.claimed_at == package.claimed_at
        assert payload.completed_at == package.completed_at
        assert payload.task_balance_awarded_at == package.task_balance_awarded_at
        assert payload.countdown_seconds == 0
        assert payload.completed_items == 0
        assert payload.total_items == 1


def test_h5_promotion_task_package_rejects_item_purchase_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-purchase-gate", site_key="h5-promotion-purchase-gate")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-purchase-gate",
        phone="+8613900067776",
        display_name="Promotion Purchase Gate Member",
    )
    seeded = _seed_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-purchase-gate",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="invited_registrations",
        target_value=1,
        invited_registration_count=1,
        recharged_invitee_count=0,
        include_item=True,
    )

    claim_response = client.post(f"/api/h5/task-packages/{seeded['package_id']}/claim")
    assert claim_response.status_code == 200, claim_response.text
    assert claim_response.json()["status"] == "completed"

    purchase_response = client.post(
        f"/api/h5/task-packages/{seeded['package_id']}/items/{seeded['item_id']}/purchase"
    )
    assert purchase_response.status_code == 200, purchase_response.text
    payload = purchase_response.json()
    assert payload["success"] is False
    assert payload["reason"] == "Promotion task packages do not support item purchase."


def test_h5_promotion_task_package_rejects_unsupported_metric_configuration(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-invalid-metric", site_key="h5-promotion-invalid-metric")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-invalid-metric",
        phone="+8613900067777",
        display_name="Promotion Invalid Metric Member",
    )
    seeded = _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-invalid-metric",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="unsupported_metric",
        target_value=2,
    )

    detail_response = client.get(f"/api/h5/task-packages/{seeded['package_id']}")
    assert detail_response.status_code == 409, detail_response.text
    assert detail_response.json()["detail"] == "Unsupported promotion metric 'unsupported_metric'."


def test_h5_promotion_task_package_list_rejects_unsupported_metric_configuration(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-promotion-invalid-metric-list", site_key="h5-promotion-invalid-metric-list")
    auth_payload = _register_member(
        client,
        site_key="h5-promotion-invalid-metric-list",
        phone="+8613900067778",
        display_name="Promotion Invalid Metric List Member",
    )
    _seed_uninitialized_promotion_task_package_scope(
        db_session_factory,
        account_id="acct-h5-promotion-invalid-metric-list",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        metric="unsupported_metric",
        target_value=2,
    )

    list_response = client.get("/api/h5/task-packages")
    assert list_response.status_code == 409, list_response.text
    assert list_response.json()["detail"] == "Unsupported promotion metric 'unsupported_metric'."


def test_h5_recharge_marks_referral_as_recharged(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-wallet-referral", site_key="h5-wallet-referral")
    inviter_payload = _register_member(
        client,
        site_key="h5-wallet-referral",
        phone="+8613900068881",
        display_name="Wallet Inviter",
    )

    with db_session_factory() as session:
        inviter = session.query(AppUser).filter(
            AppUser.public_user_id == inviter_payload["member"]["publicUserId"]
        ).one()
        inviter_member = session.query(MemberProfile).filter(
            MemberProfile.user_id == inviter.id
        ).one()
        inviter_member.current_owner_staff_user_id = "staff-wallet-inviter"
        inviter_member.attribution_status = "owned"
        from app.db.ownership_models import MemberOwnerAssignment
        session.add(
            InviteCode(
                code="PROMO-WALLET-REF",
                site_id=site["id"],
                inviter_user_id=inviter.id,
                status="active",
            )
        )
        session.add(
            MemberOwnerAssignment(
                account_id=inviter_member.account_id,
                site_id=site["id"],
                user_id=inviter.id,
                member_profile_id=inviter_member.id,
                owner_staff_user_id="staff-wallet-inviter",
                source_type="staff_entry_link",
                is_current=True,
            )
        )
        session.commit()

    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    referred_payload = _register_member(
        client,
        site_key="h5-wallet-referral",
        phone="+8613900068882",
        display_name="Wallet Referred",
        invite_code="PROMO-WALLET-REF",
    )
    assert referred_payload["member"]["siteKey"] == "h5-wallet-referral"

    recharge_response = client.post("/api/h5/wallet/recharges", json={"amount": 35})
    assert recharge_response.status_code == 200, recharge_response.text

    with db_session_factory() as session:
        referred = session.query(AppUser).filter(
            AppUser.public_user_id == referred_payload["member"]["publicUserId"]
        ).one()
        referral = session.query(UserReferral).filter(
            UserReferral.referred_user_id == referred.id
        ).one()
        recharge_order = session.query(WalletRechargeOrder).filter(
            WalletRechargeOrder.user_id == referred.id
        ).one()

        assert referral.first_recharged_at is not None
        assert referral.first_recharge_order_id == recharge_order.id


def test_h5_recharge_marks_only_referral_matching_registration_invite_code(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-wallet-referral-scope", site_key="h5-wallet-referral-scope")
    inviter_a_payload = _register_member(
        client,
        site_key="h5-wallet-referral-scope",
        phone="+8613900068883",
        display_name="Wallet Inviter A",
    )
    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    inviter_b_payload = _register_member(
        client,
        site_key="h5-wallet-referral-scope",
        phone="+8613900068884",
        display_name="Wallet Inviter B",
    )
    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    referred_payload = _register_member(
        client,
        site_key="h5-wallet-referral-scope",
        phone="+8613900068885",
        display_name="Wallet Referred Scoped",
    )

    with db_session_factory() as session:
        inviter_a = session.query(AppUser).filter(
            AppUser.public_user_id == inviter_a_payload["member"]["publicUserId"]
        ).one()
        inviter_b = session.query(AppUser).filter(
            AppUser.public_user_id == inviter_b_payload["member"]["publicUserId"]
        ).one()
        referred = session.query(AppUser).filter(
            AppUser.public_user_id == referred_payload["member"]["publicUserId"]
        ).one()
        referred_profile = session.query(MemberProfile).filter(
            MemberProfile.user_id == referred.id
        ).one()

        wrong_code = InviteCode(
            code="PROMO-WALLET-WRONG",
            site_id=site["id"],
            inviter_user_id=inviter_a.id,
            status="active",
        )
        right_code = InviteCode(
            code="PROMO-WALLET-RIGHT",
            site_id=site["id"],
            inviter_user_id=inviter_b.id,
            status="active",
        )
        session.add_all([wrong_code, right_code])
        session.flush()

        referred.registration_invite_code = right_code.code
        referred.is_invited_user = True
        session.add(referred)
        session.flush()

        wrong_referral = UserReferral(
            account_id="acct-h5-wallet-referral-scope",
            site_id=site["id"],
            invite_code=wrong_code.code,
            referrer_user_id=inviter_a.id,
            referred_user_id=referred.id,
            referred_member_profile_id=referred_profile.id,
            registered_at=utc_now(),
            status="registered",
        )
        right_referral = UserReferral(
            account_id="acct-h5-wallet-referral-scope",
            site_id=site["id"],
            invite_code=right_code.code,
            referrer_user_id=inviter_b.id,
            referred_user_id=referred.id,
            referred_member_profile_id=referred_profile.id,
            registered_at=utc_now(),
            status="registered",
        )
        session.add_all([wrong_referral, right_referral])
        session.commit()

    recharge_response = client.post("/api/h5/wallet/recharges", json={"amount": 66})
    assert recharge_response.status_code == 200, recharge_response.text

    with db_session_factory() as session:
        referred = session.query(AppUser).filter(
            AppUser.public_user_id == referred_payload["member"]["publicUserId"]
        ).one()
        recharge_order = session.query(WalletRechargeOrder).filter(
            WalletRechargeOrder.user_id == referred.id
        ).one()
        referrals = session.query(UserReferral).filter(
            UserReferral.referred_user_id == referred.id
        ).all()

        referral_by_code = {item.invite_code: item for item in referrals}
        assert referral_by_code["PROMO-WALLET-WRONG"].first_recharged_at is None
        assert referral_by_code["PROMO-WALLET-WRONG"].first_recharge_order_id is None
        assert referral_by_code["PROMO-WALLET-RIGHT"].first_recharged_at is not None
        assert referral_by_code["PROMO-WALLET-RIGHT"].first_recharge_order_id == recharge_order.id

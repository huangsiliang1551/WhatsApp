import asyncio
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    H5Site,
    InviteCode,
    MemberAuthSession,
    MemberOrder,
    MemberProfile,
    PromotionTaskInstance,
    PromotionTaskTemplate,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    UserReferral,
    WalletAccount,
    WalletLedgerEntry,
    WalletRechargeOrder,
    utc_now,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_commerce_service import H5MemberCommerceService
from tests.test_h5_member_auth import _create_site, _register_member


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
    return H5MemberContext(
        member_profile=member_profile,
        user=user,
        site=site_model,
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
        session.add(
            InviteCode(
                code="PROMO-WALLET-REF",
                site_id=site["id"],
                inviter_user_id=inviter.id,
                status="active",
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

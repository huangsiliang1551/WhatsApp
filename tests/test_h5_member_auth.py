import os
from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, timedelta
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import (
    AppUser,
    InviteCode,
    MemberAuthSession,
    MemberTaskBatch,
    MemberTaskDayQuota,
    MemberProfile,
    MemberVerificationRequest,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskProductPool,
    TaskProductPoolItem,
    TaskSystemConfig,
    UserReferral,
    WalletAccount,
    WalletLedgerEntry,
    utc_now,
)


def _operator_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "operator-h5-member-auth",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def _create_site(
    client: TestClient,
    *,
    account_id: str,
    site_key: str,
) -> dict[str, object]:
    response = client.post(
        "/api/platform/sites",
        json={
            "account_id": account_id,
            "site_key": site_key,
            "domain": f"{site_key}.example.com",
            "brand_name": f"Brand {site_key}",
        },
        headers=_operator_headers(account_id),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _register_member(
    client: TestClient,
    *,
    site_key: str,
    phone: str | None = None,
    username: str | None = None,
    password: str = "pass123456",
    display_name: str = "H5 Member",
    invite_code: str | None = None,
) -> dict[str, object]:
    resolved_username = (username or phone or "").strip()
    payload: dict[str, object] = {
        "site_key": site_key,
        "username": resolved_username,
        "password": password,
        "confirm_password": password,
        "display_name": display_name,
    }
    if phone is not None:
        payload["phone"] = phone
    if invite_code is None:
        # Spec 归属改造后站点默认 registration_entry_required=True。
        # 这些测试聚焦登录/会话/编号而非注册强制，故关闭强制以保持原语义。
        _disable_entry_required_for_tests(client, site_key)
    if invite_code is not None:
        payload["invite_code"] = invite_code
    response = client.post(
        "/api/h5/auth/register",
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _disable_entry_required_for_tests(client: TestClient, site_key: str) -> None:
    from app.api.deps import get_db_session
    from app.db.models import H5Site

    session_gen = client.app.dependency_overrides[get_db_session]()
    session = next(session_gen)
    try:
        site = session.query(H5Site).filter(H5Site.site_key == site_key).one_or_none()
        if site is not None:
            site.registration_entry_required = False
            session.commit()
    finally:
        session_gen.close()


@contextmanager
def _strict_h5_member_auth() -> Generator[None, None, None]:
    original_test_mode = os.environ.get("TEST_MODE")
    original_auth_required = os.environ.get("AUTH_REQUIRED")
    os.environ["TEST_MODE"] = "false"
    os.environ["AUTH_REQUIRED"] = "true"
    get_settings.cache_clear()
    try:
        yield
    finally:
        if original_test_mode is None:
            os.environ.pop("TEST_MODE", None)
        else:
            os.environ["TEST_MODE"] = original_test_mode
        if original_auth_required is None:
            os.environ.pop("AUTH_REQUIRED", None)
        else:
            os.environ["AUTH_REQUIRED"] = original_auth_required
        get_settings.cache_clear()


def _create_claimed_task_instance(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    task_key: str,
) -> dict[str, object]:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        user_id = user.id

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": account_id,
            "task_key": task_key,
            "name": f"Template {task_key}",
            "title": f"Template {task_key}",
            "description": "Strict H5 auth scope test task",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 3600,
            "auto_review_enabled": True,
        },
        headers=_operator_headers(account_id),
    )
    assert template_response.status_code == 200, template_response.text
    template = template_response.json()

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": account_id,
            "template_id": template["id"],
            "user_id": user_id,
            "site_id": site_id,
            "review_required": True,
        },
        headers=_operator_headers(account_id),
    )
    assert instance_response.status_code == 200, instance_response.text
    instance = instance_response.json()

    claim_response = client.post(
        f"/api/tasks/instances/{instance['id']}/claim",
        json={},
        headers=_operator_headers(account_id),
    )
    assert claim_response.status_code == 200, claim_response.text
    return claim_response.json()


def _create_h5_ticket(client: TestClient, *, title: str) -> dict[str, object]:
    response = client.post(
        "/api/h5/tickets",
        json={
            "ticket_type": "help",
            "title": title,
            "body_text": f"{title} body",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_error_response(
    response,
    *,
    status_code: int,
    detail: str,
) -> None:
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert payload["detail"] == detail
    assert "request_id" in payload


def _seed_task_system_config(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    certified_member_enabled: bool = True,
    certified_recharge_threshold: Decimal = Decimal("50.00"),
    auto_certify_on_recharge: bool = True,
    show_task_balance_transfer_prompt: bool = True,
    min_task_balance_transfer_prompt_amount: Decimal = Decimal("1.00"),
    newbie_task_enabled: bool = True,
    max_active_batches_per_user: int = 1,
    max_active_packages_per_user: int = 1,
    newbie_plan_id: str | None = None,
    official_plan_id: str | None = None,
) -> None:
    with db_session_factory() as session:
        config = TaskSystemConfig(
            account_id=account_id,
            site_id=site_id,
            status="active",
            certified_member_enabled=certified_member_enabled,
            certified_recharge_threshold=certified_recharge_threshold,
            auto_certify_on_recharge=auto_certify_on_recharge,
            show_task_balance_transfer_prompt=show_task_balance_transfer_prompt,
            min_task_balance_transfer_prompt_amount=min_task_balance_transfer_prompt_amount,
            newbie_task_enabled=newbie_task_enabled,
            max_active_batches_per_user=max_active_batches_per_user,
            max_active_packages_per_user=max_active_packages_per_user,
            newbie_plan_id=newbie_plan_id,
            official_plan_id=official_plan_id,
        )
        session.add(config)
        session.commit()


def _mark_h5_member_whatsapp_bound(
    db_session_factory: sessionmaker[Session],
    *,
    public_user_id: str,
) -> None:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        user.has_whatsapp = True
        session.commit()


def _seed_member_wallet(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    system_balance: Decimal = Decimal("0.00"),
    task_balance: Decimal = Decimal("0.00"),
) -> None:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        session.add(
            WalletAccount(
                account_id=account_id,
                user_id=user.id,
                system_balance=system_balance,
                task_balance=task_balance,
                currency="USD",
                withdraw_threshold=Decimal("100.00"),
            )
        )
        session.commit()


def _seed_real_recharge_ledger(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    amount: Decimal,
) -> None:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        session.add(
            WalletLedgerEntry(
                account_id=account_id,
                wallet_account_id=wallet.id,
                user_id=user.id,
                ledger_type="wallet",
                transaction_type="recharge",
                direction="credit",
                amount=amount,
                currency=wallet.currency,
                status="paid",
                source_type="user_recharge",
                fund_type="cash",
                cash_amount=amount,
                bonus_amount=Decimal("0.00"),
                task_amount=Decimal("0.00"),
                is_real_recharge=True,
            )
        )
        session.commit()


def _seed_member_verification_approved(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    reviewed_at: datetime,
) -> None:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        session.add(
            MemberVerificationRequest(
                account_id=account_id,
                member_profile_id=member_profile.id,
                request_type="identity",
                status="approved",
                reviewed_at=reviewed_at,
            )
        )
        session.commit()


def _seed_pending_claim_task_package(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
    package_type: str = "official",
) -> str:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        template = TaskPackageTemplate(
            account_id=account_id,
            name="Entry State Package",
            title="Entry State Package",
            description="Seeded for entry state tests",
            package_type=package_type,
            reward_ratio=Decimal("0.10"),
            completion_window_hours=24,
            status="active",
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
            dispatched_at=utc_now(),
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.commit()
        return package.id


def _seed_official_task_plan(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    site_id: str,
    plan_type: str = "official",
    claim_gate: str = "certified_member",
) -> str:
    with db_session_factory() as session:
        pool = TaskProductPool(
            account_id=account_id,
            site_id=site_id,
            name="Entry Official Pool",
            pool_type="general",
            price_mode="task_price_snapshot",
            allow_repeat_in_same_batch=False,
            allow_repeat_in_same_package=False,
            status="active",
        )
        session.add(pool)
        session.flush()

        for index in range(1, 5):
            session.add(
                TaskProductPoolItem(
                    account_id=account_id,
                    pool_id=pool.id,
                    product_id=f"entry-prod-{index}",
                    product_name=f"Entry Product {index}",
                    image_url=f"https://example.com/entry-{index}.png",
                    price=Decimal("0.00"),
                    currency="USD",
                    status="active",
                    sort_order=index,
                    metadata_json={"reference_price": f"{100 + index:.2f}"},
                )
            )

        plan = TaskIssuePlan(
            account_id=account_id,
            site_id=site_id,
            name="Entry Official Plan" if plan_type == "official" else "Entry Newbie Plan",
            plan_type=plan_type,
            status="active",
            claim_gate=claim_gate,
            issue_anchor="certified_at",
            issue_mode="calendar_day",
            after_last_rule_mode="repeat_last",
            default_product_pool_id=pool.id,
            default_tolerance_amount=Decimal("5.00"),
            default_reward_ratio=Decimal("0.12"),
        )
        session.add(plan)
        session.flush()

        session.add(
            TaskIssuePlanDayRule(
                account_id=account_id,
                site_id=site_id,
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
                reward_ratio=Decimal("0.12"),
                status="active",
            )
        )
        session.commit()
        return plan.id


def test_h5_member_register_me_logout_and_login(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth", site_key="h5-auth")

    register_payload = _register_member(
        client,
        site_key="h5-auth",
        phone="+8613900011111",
        display_name="Member Alpha",
    )
    member = register_payload["member"]
    assert member["accountId"] == "acct-h5-auth"
    assert member["siteKey"] == "h5-auth"
    assert member["phone"] == "+8613900011111"
    assert member["displayName"] == "Member Alpha"
    assert member["memberNo"].isdigit()
    assert len(member["memberNo"]) == 8

    me_response = client.get("/api/h5/auth/me")
    assert me_response.status_code == 200, me_response.text
    me_payload = me_response.json()
    assert me_payload["member"]["memberNo"] == member["memberNo"]
    assert me_payload["member"]["publicUserId"] == member["publicUserId"]
    assert me_payload["site"]["siteKey"] == "h5-auth"

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    home_payload = home_response.json()
    assert home_payload["member"]["memberNo"] == member["memberNo"]
    assert home_payload["site"]["siteKey"] == "h5-auth"
    assert home_payload["openTicketCount"] == 0
    assert home_payload["wallet"]["systemBalance"] is None
    assert home_payload["wallet"]["taskBalance"] is None
    assert home_payload["verification"]["currentStatus"] == "not_submitted"
    assert home_payload["verification"]["hasActiveRequest"] is False
    assert home_payload["fragments"]["rewardName"] == "Star Ring Gift Box"
    assert home_payload["fragments"]["completedCount"] == 0
    assert home_payload["fragments"]["totalCount"] == 3
    assert home_payload["fragments"]["missingCount"] == 3
    assert home_payload["fragments"]["canExchange"] is False
    assert home_payload["fragments"]["shippingOrderCount"] == 0
    assert home_payload["fragments"]["latestShippingStatus"] is None

    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    me_after_logout = client.get("/api/h5/auth/me")
    assert me_after_logout.status_code == 401, me_after_logout.text

    login_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth",
            "username": "+8613900011111",
            "password": "pass123456",
        },
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["member"]["memberNo"] == member["memberNo"]


def test_h5_task_entry_state_requires_whatsapp_binding_first(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-binding", site_key="h5-entry-binding")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-binding",
        phone="+8613900011191",
        display_name="Entry Binding Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-binding",
        site_id=site["id"],
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "need_whatsapp_binding"
    assert payload["redirectPath"] == "/h5/whatsapp"
    assert payload["currentRealRechargeAmount"] == 0.0
    assert payload["member"]["publicUserId"] == auth_payload["member"]["publicUserId"]


def test_h5_task_entry_state_prompts_task_balance_transfer_before_certification(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-transfer", site_key="h5-entry-transfer")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-transfer",
        phone="+8613900011192",
        display_name="Entry Transfer Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-transfer",
        site_id=site["id"],
        min_task_balance_transfer_prompt_amount=Decimal("5.00"),
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-transfer",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("8.00"),
        task_balance=Decimal("12.50"),
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "task_balance_transfer_prompt"
    assert payload["redirectPath"] == "/h5/wallet"
    assert payload["taskBalance"] == 12.5
    assert payload["systemBalance"] == 8.0


def test_h5_task_entry_state_requires_certification_when_recharge_threshold_not_met(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-cert", site_key="h5-entry-cert")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-cert",
        phone="+8613900011193",
        display_name="Entry Certification Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-cert",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-cert",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-cert",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("20.00"),
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "need_certification"
    assert payload["redirectPath"] == "/h5/wallet/recharge"
    assert payload["certificationRequiredAmount"] == 50.0
    assert payload["currentRealRechargeAmount"] == 20.0
    assert payload["remainingRechargeAmount"] == 30.0


def test_h5_task_entry_state_returns_official_batch_available_when_pending_claim_package_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-official", site_key="h5-entry-official")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-official",
        phone="+8613900011194",
        display_name="Entry Official Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-official",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-official",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-official",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )
    package_id = _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-official",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="official",
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "official_batch_available"
    assert payload["redirectPath"] == f"/h5/tasks/package/{package_id}"
    assert payload["taskPackageId"] == package_id


def test_h5_task_entry_state_skips_newbie_package_when_newbie_tasks_are_disabled(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-newbie-disabled", site_key="h5-entry-newbie-disabled")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-newbie-disabled",
        phone="+86139000111941",
        display_name="Entry Newbie Disabled Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-newbie-disabled",
        site_id=site["id"],
        certified_member_enabled=False,
        show_task_balance_transfer_prompt=False,
        newbie_task_enabled=False,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-newbie-disabled",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-newbie-disabled",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="rookie",
    )
    official_package_id = _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-newbie-disabled",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="official",
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "official_batch_available"
    assert payload["redirectPath"] == f"/h5/tasks/package/{official_package_id}"
    assert payload["taskPackageId"] == official_package_id


def test_h5_task_entry_state_returns_newbie_task_active_when_active_rookie_package_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-newbie-active", site_key="h5-entry-newbie-active")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-newbie-active",
        phone="+86139000111942",
        display_name="Entry Newbie Active Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-newbie-active",
        site_id=site["id"],
        certified_member_enabled=False,
        show_task_balance_transfer_prompt=False,
        newbie_task_enabled=True,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    package_id = _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-newbie-active",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="rookie",
    )
    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == package_id).one()
        package.status = "active"
        package.claimed_at = utc_now()
        package.expires_at = utc_now() + timedelta(hours=24)
        session.commit()

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "newbie_task_active"
    assert payload["redirectPath"] == f"/h5/tasks/package/{package_id}"
    assert payload["taskPackageId"] == package_id


def test_h5_task_entry_state_returns_official_batch_active_when_active_official_package_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-official-active", site_key="h5-entry-official-active")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-official-active",
        phone="+86139000111943",
        display_name="Entry Official Active Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-official-active",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-official-active",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-official-active",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )
    package_id = _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-official-active",
        site_id=site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="official",
    )
    with db_session_factory() as session:
        package = session.query(TaskPackageInstance).filter(TaskPackageInstance.id == package_id).one()
        package.status = "active"
        package.claimed_at = utc_now()
        package.expires_at = utc_now() + timedelta(hours=24)
        session.commit()

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "official_batch_active"
    assert payload["redirectPath"] == f"/h5/tasks/package/{package_id}"
    assert payload["taskPackageId"] == package_id


def test_h5_task_entry_state_returns_no_task_when_member_is_bound_but_has_no_packages_or_prompts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-no-task", site_key="h5-entry-no-task")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-no-task",
        phone="+86139000111944",
        display_name="Entry No Task Member",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-no-task",
        site_id=site["id"],
        certified_member_enabled=False,
        show_task_balance_transfer_prompt=False,
        newbie_task_enabled=False,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-no-task",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "no_task"
    assert payload["redirectPath"] == "/h5/tasks"
    assert payload["taskPackageId"] is None


def test_h5_task_entry_state_generates_first_official_batch_when_member_is_eligible(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-generate", site_key="h5-entry-generate")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-generate",
        phone="+8613900011195",
        display_name="Entry Generate Member",
    )
    official_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-h5-entry-generate",
        site_id=site["id"],
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-generate",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    with db_session_factory() as session:
        config = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == "acct-h5-entry-generate",
            TaskSystemConfig.site_id == site["id"],
        ).one()
        config.official_plan_id = official_plan_id
        session.commit()
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-generate",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-generate",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "official_batch_available"
    assert payload["taskPackageId"] is not None

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        quotas = session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-generate",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).all()
        assert len(quotas) == 1
        assert quotas[0].day_no == 1
        assert quotas[0].status == "locked"
        assert quotas[0].issued_batch_id is not None
        assert quotas[0].locked_at is not None

        batches = session.query(MemberTaskBatch).filter(
            MemberTaskBatch.quota_id == quotas[0].id,
        ).all()
        assert len(batches) == 1
        assert batches[0].products_generated is True
        assert batches[0].current_package_index == 1

        packages = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.batch_id == batches[0].id,
        ).order_by(TaskPackageInstance.batch_index.asc()).all()
        assert len(packages) == 2
        assert packages[0].status == "pending_claim"
        assert packages[0].visible_item_id is not None
        assert packages[1].status == "pending_claim"

        first_item = session.query(TaskPackageInstanceItem).filter(
            TaskPackageInstanceItem.package_instance_id == packages[0].id,
        ).one()
        assert first_item.status == "available"
        assert first_item.visible_to_user is True


def test_h5_task_entry_state_generation_is_idempotent_for_same_member_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-idempotent", site_key="h5-entry-idempotent")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-idempotent",
        phone="+8613900011196",
        display_name="Entry Idempotent Member",
    )
    official_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-h5-entry-idempotent",
        site_id=site["id"],
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-idempotent",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
    )
    with db_session_factory() as session:
        config = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == "acct-h5-entry-idempotent",
            TaskSystemConfig.site_id == site["id"],
        ).one()
        config.official_plan_id = official_plan_id
        session.commit()
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-idempotent",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-idempotent",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )

    first_response = client.get("/api/h5/tasks/entry-state")
    assert first_response.status_code == 200, first_response.text
    second_response = client.get("/api/h5/tasks/entry-state")
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()["taskPackageId"] == first_response.json()["taskPackageId"]

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assert session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-idempotent",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).count() == 1
        quota = session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-idempotent",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).one()
        assert quota.status == "locked"
        assert quota.locked_at is not None
        assert session.query(MemberTaskBatch).filter(
            MemberTaskBatch.quota_id == quota.id,
        ).count() == 1


def test_h5_task_entry_state_waits_when_account_level_active_package_limit_is_reached(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-package-limit", site_key="h5-entry-package-limit")
    shadow_site = _create_site(client, account_id="acct-h5-entry-package-limit", site_key="h5-entry-package-limit-shadow")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-package-limit",
        phone="+86139000111961",
        display_name="Entry Package Limit Member",
    )
    official_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-h5-entry-package-limit",
        site_id=site["id"],
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-package-limit",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
        max_active_batches_per_user=3,
        max_active_packages_per_user=1,
        official_plan_id=official_plan_id,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-package-limit",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-package-limit",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )
    _seed_pending_claim_task_package(
        db_session_factory,
        account_id="acct-h5-entry-package-limit",
        site_id=shadow_site["id"],
        public_user_id=auth_payload["member"]["publicUserId"],
        package_type="official",
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "waiting_next_batch"
    assert payload["taskPackageId"] is None

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assert session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-package-limit",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).count() == 0


def test_h5_task_entry_state_waits_when_account_level_unfinished_batch_limit_is_reached(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-batch-limit", site_key="h5-entry-batch-limit")
    shadow_site = _create_site(client, account_id="acct-h5-entry-batch-limit", site_key="h5-entry-batch-limit-shadow")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-batch-limit",
        phone="+86139000111962",
        display_name="Entry Batch Limit Member",
    )
    official_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-h5-entry-batch-limit",
        site_id=site["id"],
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-batch-limit",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
        max_active_batches_per_user=1,
        max_active_packages_per_user=5,
        official_plan_id=official_plan_id,
    )
    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-batch-limit",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_real_recharge_ledger(
        db_session_factory,
        account_id="acct-h5-entry-batch-limit",
        public_user_id=auth_payload["member"]["publicUserId"],
        amount=Decimal("60.00"),
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        template = TaskPackageTemplate(
            account_id="acct-h5-entry-batch-limit",
            name="Shadow Official Package",
            title="Shadow Official Package",
            description="Cross-site active batch",
            package_type="official",
            reward_ratio=Decimal("0.12"),
            completion_window_hours=24,
            status="active",
        )
        session.add(template)
        session.flush()

        batch = MemberTaskBatch(
            account_id="acct-h5-entry-batch-limit",
            site_id=shadow_site["id"],
            user_id=user.id,
            plan_id=official_plan_id,
            day_no=1,
            package_count=1,
            completed_package_count=0,
            current_package_index=1,
            planned_amount=Decimal("80.00"),
            system_generated_amount=Decimal("80.00"),
            effective_day_amount=Decimal("80.00"),
            reward_ratio_snapshot=Decimal("0.12"),
            status="pending_claim",
            products_generated=True,
        )
        session.add(batch)
        session.flush()

        package = TaskPackageInstance(
            account_id="acct-h5-entry-batch-limit",
            template_id=template.id,
            user_id=user.id,
            site_id=shadow_site["id"],
            batch_id=batch.id,
            batch_day_no=1,
            batch_index=1,
            batch_total=1,
            planned_amount=Decimal("80.00"),
            system_generated_amount=Decimal("80.00"),
            effective_amount=Decimal("80.00"),
            status="completed",
            reward_ratio_snapshot=Decimal("0.12"),
            claimed_at=utc_now(),
            completed_at=utc_now(),
            current_item_index=0,
            required_item_count=0,
            completed_required_item_count=0,
            completion_window_hours_snapshot=24,
        )
        session.add(package)
        session.commit()

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "waiting_next_batch"
    assert payload["taskPackageId"] is None

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assert session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-batch-limit",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).count() == 0


def test_h5_task_entry_state_waits_until_issue_schedule_window_is_reached(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = _create_site(client, account_id="acct-h5-entry-schedule", site_key="h5-entry-schedule")
    auth_payload = _register_member(
        client,
        site_key="h5-entry-schedule",
        phone="+86139000111999",
        display_name="Entry Schedule Member",
    )
    official_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-h5-entry-schedule",
        site_id=site["id"],
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-h5-entry-schedule",
        site_id=site["id"],
        certified_recharge_threshold=Decimal("50.00"),
        show_task_balance_transfer_prompt=False,
        official_plan_id=official_plan_id,
    )
    with db_session_factory() as session:
        day1 = session.query(TaskIssuePlanDayRule).filter(
            TaskIssuePlanDayRule.plan_id == official_plan_id,
            TaskIssuePlanDayRule.day_no == 1,
        ).one()
        day1.issue_time_of_day = "12:00"
        session.add(day1)
        session.commit()

    _mark_h5_member_whatsapp_bound(
        db_session_factory,
        public_user_id=auth_payload["member"]["publicUserId"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-h5-entry-schedule",
        public_user_id=auth_payload["member"]["publicUserId"],
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )
    _seed_member_verification_approved(
        db_session_factory,
        account_id="acct-h5-entry-schedule",
        public_user_id=auth_payload["member"]["publicUserId"],
        reviewed_at=datetime.fromisoformat("2026-06-20T08:00:00"),
    )
    monkeypatch.setattr(
        "app.services.member_task_quota_service.utc_now",
        lambda: datetime.fromisoformat("2026-06-20T10:00:00"),
    )

    response = client.get("/api/h5/tasks/entry-state")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "waiting_next_batch"
    assert payload["taskPackageId"] is None

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assert session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-h5-entry-schedule",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == official_plan_id,
        ).count() == 0


def test_h5_member_register_and_login_with_english_username(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-username", site_key="h5-auth-username")

    register_payload = _register_member(
        client,
        site_key="h5-auth-username",
        username="Demo.User-01",
        display_name="Username Member",
    )
    member = register_payload["member"]
    assert member["username"] == "demo.user-01"
    assert member["phone"] is None

    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    login_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth-username",
            "username": "Demo.User-01",
            "password": "pass123456",
        },
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["member"]["username"] == "demo.user-01"


def test_h5_member_username_must_be_globally_unique(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-unique-a", site_key="h5-auth-unique-a")
    _create_site(client, account_id="acct-h5-auth-unique-b", site_key="h5-auth-unique-b")

    _register_member(
        client,
        site_key="h5-auth-unique-a",
        username="global-user",
    )
    client.post("/api/h5/auth/logout")

    duplicate_response = client.post(
        "/api/h5/auth/register",
        json={
            "site_key": "h5-auth-unique-b",
            "username": "global-user",
            "password": "pass123456",
            "confirm_password": "pass123456",
            "display_name": "Another Member",
        },
    )
    assert duplicate_response.status_code == 409, duplicate_response.text
    payload = duplicate_response.json()
    assert payload["detail"]["code"] == "username_taken"


def test_h5_member_login_uses_uniform_invalid_credentials_error(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-invalid", site_key="h5-auth-invalid")
    _register_member(
        client,
        site_key="h5-auth-invalid",
        username="member-alpha",
    )
    client.post("/api/h5/auth/logout")

    missing_account_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth-invalid",
            "username": "missing-account",
            "password": "pass123456",
        },
    )
    wrong_password_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth-invalid",
            "username": "member-alpha",
            "password": "wrong-password",
        },
    )
    assert missing_account_response.status_code == 401, missing_account_response.text
    assert wrong_password_response.status_code == 401, wrong_password_response.text
    assert missing_account_response.json()["detail"]["code"] == "invalid_credentials"
    assert wrong_password_response.json()["detail"]["code"] == "invalid_credentials"


def test_h5_member_login_locks_after_repeated_failures(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-lock", site_key="h5-auth-lock")
    _register_member(
        client,
        site_key="h5-auth-lock",
        username="lock-user",
    )
    client.post("/api/h5/auth/logout")

    for _ in range(5):
        response = client.post(
            "/api/h5/auth/login",
            json={
                "site_key": "h5-auth-lock",
                "username": "lock-user",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401, response.text

    locked_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth-lock",
            "username": "lock-user",
            "password": "pass123456",
        },
    )
    assert locked_response.status_code == 423, locked_response.text
    assert locked_response.json()["detail"]["code"] == "account_locked"


def test_h5_member_register_and_login_accepts_64_char_password(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-long-pass", site_key="h5-auth-long-pass")
    long_password = "Pass1234" * 8

    register_payload = _register_member(
        client,
        site_key="h5-auth-long-pass",
        username="long-pass-user",
        password=long_password,
        display_name="Long Password Member",
    )

    logout_response = client.post("/api/h5/auth/logout")
    assert logout_response.status_code == 200, logout_response.text

    login_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-auth-long-pass",
            "username": "long-pass-user",
            "password": long_password,
        },
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["member"]["publicUserId"] == register_payload["member"]["publicUserId"]


def test_h5_member_lifecycle_change_revokes_existing_sessions(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-auth-revoke", site_key="h5-auth-revoke")
    register_payload = _register_member(
        client,
        site_key="h5-auth-revoke",
        username="revoke-user",
    )
    public_user_id = register_payload["member"]["publicUserId"]

    revoke_response = client.patch(
        f"/api/customers/{public_user_id}/lifecycle-status",
        params={"account_id": "acct-h5-auth-revoke"},
        json={"lifecycle_status": "blacklisted"},
        headers=_operator_headers("acct-h5-auth-revoke"),
    )
    assert revoke_response.status_code == 200, revoke_response.text

    me_response = client.get("/api/h5/auth/me")
    assert me_response.status_code == 401, me_response.text
    assert me_response.json()["detail"]["code"] == "session_revoked"

    with db_session_factory() as session:
        auth_session = session.query(MemberAuthSession).order_by(MemberAuthSession.created_at.desc()).first()
        assert auth_session is not None
        assert auth_session.status == "revoked"
        assert auth_session.revoked_at is not None


def test_h5_member_refresh_renews_near_expiry_session_without_500(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-auth-refresh", site_key="h5-auth-refresh")

    _register_member(
        client,
        site_key="h5-auth-refresh",
        phone="+8613900012345",
        display_name="Refresh Member",
    )

    with db_session_factory() as session:
        auth_session = session.query(MemberAuthSession).order_by(MemberAuthSession.created_at.desc()).first()
        assert auth_session is not None
        auth_session.refresh_expires_at = utc_now() + timedelta(days=7)
        session.add(auth_session)
        session.commit()

    response = client.post("/api/h5/auth/refresh")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["member"]["siteKey"] == "h5-auth-refresh"

    me_response = client.get("/api/h5/auth/me")
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["member"]["siteKey"] == "h5-auth-refresh"


def test_h5_member_numbers_are_eight_digits_and_unique_within_account(client: TestClient) -> None:
    _create_site(client, account_id="acct-h5-auth-unique", site_key="h5-auth-unique")

    first = _register_member(client, site_key="h5-auth-unique", phone="+8613900022221")
    client.post("/api/h5/auth/logout")
    second = _register_member(client, site_key="h5-auth-unique", phone="+8613900022222")

    first_member_no = first["member"]["memberNo"]
    second_member_no = second["member"]["memberNo"]
    assert first_member_no.isdigit()
    assert second_member_no.isdigit()
    assert len(first_member_no) == 8
    assert len(second_member_no) == 8
    assert first_member_no != second_member_no


def test_h5_authenticated_routes_use_member_session_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-auth-scope", site_key="h5-auth-scope")
    register_payload = _register_member(
        client,
        site_key="h5-auth-scope",
        phone="+8613900033333",
        display_name="Scope Member",
    )
    public_user_id = register_payload["member"]["publicUserId"]

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        user_id = user.id

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": "acct-h5-auth-scope",
            "task_key": "h5-auth-scope-task",
            "name": "H5 Auth Scope Task",
            "title": "H5 Auth Scope Task",
            "description": "Authenticated member task list coverage",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 3600,
            "auto_review_enabled": True,
        },
        headers=_operator_headers("acct-h5-auth-scope"),
    )
    assert template_response.status_code == 200, template_response.text
    template = template_response.json()

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": "acct-h5-auth-scope",
            "template_id": template["id"],
            "user_id": user_id,
            "site_id": site["id"],
            "review_required": True,
        },
        headers=_operator_headers("acct-h5-auth-scope"),
    )
    assert instance_response.status_code == 200, instance_response.text
    instance = instance_response.json()

    claim_response = client.post(
        f"/api/tasks/instances/{instance['id']}/claim",
        json={},
        headers=_operator_headers("acct-h5-auth-scope"),
    )
    assert claim_response.status_code == 200, claim_response.text

    tasks_response = client.get("/api/h5/tasks")
    assert tasks_response.status_code == 200, tasks_response.text
    tasks = tasks_response.json()
    assert [item["id"] for item in tasks] == [instance["id"]]


def test_h5_tasks_require_auth_when_query_identity_is_absent(client: TestClient) -> None:
    response = client.get("/api/h5/tasks")
    assert response.status_code == 401, response.text


def test_h5_member_register_with_invite_code_creates_referral(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-auth-invite", site_key="h5-auth-invite")
    inviter_payload = _register_member(
        client,
        site_key="h5-auth-invite",
        phone="+8613900090001",
        display_name="Inviter Member",
    )

    with db_session_factory() as session:
        inviter = session.query(AppUser).filter(
            AppUser.public_user_id == inviter_payload["member"]["publicUserId"]
        ).one()
        # 邀请人需要有人力归属，被邀请人才能继承（spec 7.5）
        from app.db.models import MemberProfile
        from app.db.ownership_models import MemberOwnerAssignment
        inviter_member = session.query(MemberProfile).filter(
            MemberProfile.user_id == inviter.id
        ).one()
        inviter_member.current_owner_staff_user_id = "staff-inviter"
        inviter_member.attribution_status = "owned"
        session.add(
            MemberOwnerAssignment(
                account_id=inviter_member.account_id,
                site_id=site["id"],
                user_id=inviter.id,
                member_profile_id=inviter_member.id,
                owner_staff_user_id="staff-inviter",
                source_type="staff_entry_link",
                is_current=True,
            )
        )
        session.add(
            InviteCode(
                code="PROMO-AUTH-INVITE",
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
        site_key="h5-auth-invite",
        phone="+8613900090002",
        display_name="Referred Member",
        invite_code="PROMO-AUTH-INVITE",
    )

    with db_session_factory() as session:
        referred = session.query(AppUser).filter(
            AppUser.public_user_id == referred_payload["member"]["publicUserId"]
        ).one()
        referral = session.query(UserReferral).filter(
            UserReferral.referred_user_id == referred.id
        ).one()

        assert referred.is_invited_user is True
        assert referred.registration_invite_code == "PROMO-AUTH-INVITE"
        assert referral.invite_code == "PROMO-AUTH-INVITE"
        assert referral.registered_at is not None
        assert referral.first_recharged_at is None


def test_h5_formal_routes_reject_legacy_identity_without_session(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with _strict_h5_member_auth():
        site = _create_site(client, account_id="acct-h5-auth-strict", site_key="h5-auth-strict")
        register_payload = _register_member(
            client,
            site_key="h5-auth-strict",
            phone="+8613900044444",
            display_name="Strict Member",
        )
        public_user_id = register_payload["member"]["publicUserId"]
        task = _create_claimed_task_instance(
            client,
            db_session_factory,
            account_id="acct-h5-auth-strict",
            site_id=site["id"],
            public_user_id=public_user_id,
            task_key="h5-auth-strict-task",
        )
        ticket = _create_h5_ticket(client, title="Strict Ticket")

        logout_response = client.post("/api/h5/auth/logout")
        assert logout_response.status_code == 200, logout_response.text

        unauthenticated_cases = [
            (
                "GET",
                "/api/h5/bootstrap",
                {"params": {"site_key": "h5-auth-strict", "public_user_id": public_user_id}},
            ),
            (
                "GET",
                "/api/h5/tasks",
                {"params": {"site_key": "h5-auth-strict", "public_user_id": public_user_id}},
            ),
            (
                "GET",
                f"/api/h5/tasks/{task['id']}",
                {"params": {"site_key": "h5-auth-strict", "public_user_id": public_user_id}},
            ),
            (
                "POST",
                f"/api/h5/tasks/{task['id']}/submit",
                {
                    "json": {
                        "public_user_id": public_user_id,
                        "site_key": "h5-auth-strict",
                        "proof_file_ids": [],
                        "notes": "legacy-submit",
                    }
                },
            ),
            (
                "GET",
                "/api/h5/tickets",
                {"params": {"site_key": "h5-auth-strict", "public_user_id": public_user_id}},
            ),
            (
                "GET",
                f"/api/h5/tickets/{ticket['id']}",
                {"params": {"site_key": "h5-auth-strict", "public_user_id": public_user_id}},
            ),
            (
                "POST",
                "/api/h5/tickets",
                {
                    "json": {
                        "public_user_id": public_user_id,
                        "site_key": "h5-auth-strict",
                        "ticket_type": "help",
                        "title": "Legacy create",
                        "body_text": "legacy-body",
                    }
                },
            ),
        ]

        for method, path, request_kwargs in unauthenticated_cases:
            response = client.request(method, path, **request_kwargs)
            _assert_error_response(
                response,
                status_code=401,
                detail="H5 member authentication is required.",
            )

        unauthenticated_proof_upload = client.post(
            "/api/h5/task-proofs",
            data={
                "task_instance_id": task["id"],
                "public_user_id": public_user_id,
                "site_key": "h5-auth-strict",
            },
            files={"file": ("proof.txt", BytesIO(b"legacy-proof"), "text/plain")},
        )
        _assert_error_response(
            unauthenticated_proof_upload,
            status_code=401,
            detail="H5 member authentication is required.",
        )


def test_h5_formal_routes_reject_mismatched_identity_with_session(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with _strict_h5_member_auth():
        site = _create_site(
            client,
            account_id="acct-h5-auth-session-scope",
            site_key="h5-auth-session-scope",
        )
        register_payload = _register_member(
            client,
            site_key="h5-auth-session-scope",
            phone="+8613900055555",
            display_name="Scoped Member",
        )
        public_user_id = register_payload["member"]["publicUserId"]
        task = _create_claimed_task_instance(
            client,
            db_session_factory,
            account_id="acct-h5-auth-session-scope",
            site_id=site["id"],
            public_user_id=public_user_id,
            task_key="h5-auth-session-task",
        )
        ticket = _create_h5_ticket(client, title="Scoped Ticket")

        member_scope_cases = [
            (
                "GET",
                "/api/h5/bootstrap",
                {"params": {"site_key": "h5-auth-session-scope", "public_user_id": "h5-user-mismatch"}},
            ),
            (
                "GET",
                "/api/h5/tasks",
                {"params": {"public_user_id": "h5-user-mismatch"}},
            ),
            (
                "GET",
                f"/api/h5/tasks/{task['id']}",
                {"params": {"public_user_id": "h5-user-mismatch"}},
            ),
            (
                "POST",
                f"/api/h5/tasks/{task['id']}/submit",
                {
                    "json": {
                        "public_user_id": "h5-user-mismatch",
                        "proof_file_ids": [],
                    }
                },
            ),
            (
                "GET",
                "/api/h5/tickets",
                {"params": {"public_user_id": "h5-user-mismatch"}},
            ),
            (
                "GET",
                f"/api/h5/tickets/{ticket['id']}",
                {"params": {"public_user_id": "h5-user-mismatch"}},
            ),
            (
                "POST",
                "/api/h5/tickets",
                {
                    "json": {
                        "public_user_id": "h5-user-mismatch",
                        "ticket_type": "help",
                        "title": "Mismatch create",
                        "body_text": "mismatch",
                    }
                },
            ),
        ]
        for method, path, request_kwargs in member_scope_cases:
            response = client.request(method, path, **request_kwargs)
            _assert_error_response(
                response,
                status_code=403,
                detail="User is outside the current H5 member scope.",
            )

        mismatched_member_proof_upload = client.post(
            "/api/h5/task-proofs",
            data={
                "task_instance_id": task["id"],
                "public_user_id": "h5-user-mismatch",
                "site_key": "h5-auth-session-scope",
            },
            files={"file": ("proof.txt", BytesIO(b"wrong-user-proof"), "text/plain")},
        )
        _assert_error_response(
            mismatched_member_proof_upload,
            status_code=403,
            detail="User is outside the current H5 member scope.",
        )

        site_scope_cases = [
            (
                "GET",
                "/api/h5/bootstrap",
                {"params": {"site_key": "h5-auth-other-site"}},
            ),
            (
                "GET",
                "/api/h5/tasks",
                {"params": {"site_key": "h5-auth-other-site"}},
            ),
            (
                "GET",
                f"/api/h5/tasks/{task['id']}",
                {"params": {"site_key": "h5-auth-other-site"}},
            ),
            (
                "POST",
                f"/api/h5/tasks/{task['id']}/submit",
                {
                    "json": {
                        "site_key": "h5-auth-other-site",
                        "proof_file_ids": [],
                    }
                },
            ),
            (
                "GET",
                "/api/h5/tickets",
                {"params": {"site_key": "h5-auth-other-site"}},
            ),
            (
                "GET",
                f"/api/h5/tickets/{ticket['id']}",
                {"params": {"site_key": "h5-auth-other-site"}},
            ),
            (
                "POST",
                "/api/h5/tickets",
                {
                    "json": {
                        "site_key": "h5-auth-other-site",
                        "ticket_type": "help",
                        "title": "Wrong site create",
                        "body_text": "wrong-site",
                    }
                },
            ),
        ]
        for method, path, request_kwargs in site_scope_cases:
            response = client.request(method, path, **request_kwargs)
            _assert_error_response(
                response,
                status_code=403,
                detail="User is outside the current H5 site scope.",
            )

        mismatched_site_proof_upload = client.post(
            "/api/h5/task-proofs",
            data={
                "task_instance_id": task["id"],
                "public_user_id": public_user_id,
                "site_key": "h5-auth-other-site",
            },
            files={"file": ("proof.txt", BytesIO(b"wrong-site-proof"), "text/plain")},
        )
        _assert_error_response(
            mismatched_site_proof_upload,
            status_code=403,
            detail="User is outside the current H5 site scope.",
        )

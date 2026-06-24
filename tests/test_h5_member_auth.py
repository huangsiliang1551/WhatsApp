import os
from collections.abc import Generator
from contextlib import contextmanager
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import AppUser, InviteCode, UserReferral


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
    phone: str,
    password: str = "pass123456",
    display_name: str = "H5 Member",
    invite_code: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "site_key": site_key,
        "phone": phone,
        "password": password,
        "confirm_password": password,
        "display_name": display_name,
    }
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
            "phone": "+8613900011111",
            "password": "pass123456",
        },
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["member"]["memberNo"] == member["memberNo"]


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

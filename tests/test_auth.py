from collections.abc import Generator
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.api.deps import get_db_session, get_request_actor
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import (
    Account,
    Agency,
    AuditLog,
    H5Site,
    ProviderStatusEventBuffer,
    WebhookSubscription,
    WhatsAppBusinessAccount,
    utc_now,
)
from app.main import app
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from tests.conftest import StubMetaManagementProvider


def _issue_jwt(
    *,
    sub: str,
    user_type: str,
    role: str,
    agency_id: str | None = None,
    username: str | None = None,
    display_name: str | None = None,
    account_ids: list[str] | None = None,
) -> str:
    settings = get_settings()
    payload = {
        "sub": sub,
        "user_type": user_type,
        "role": role,
    }
    if agency_id is not None:
        payload["agency_id"] = agency_id
    if username is not None:
        payload["username"] = username
    if display_name is not None:
        payload["display_name"] = display_name
    if account_ids is not None:
        payload["account_ids"] = account_ids
    return _encode_agent_jwt(
        payload,
        settings.admin_jwt_secret,
        settings.admin_access_token_ttl_minutes,
    )


def _build_request(headers: dict[str, str], path: str = "/api/auth/permissions") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in headers.items()
            ],
        }
    )


def _post_unmatched_provider_status_webhook(
    client: TestClient,
    *,
    account_id: str,
    waba_id: str,
    phone_number_id: str,
    app_secret: str,
    provider_message_id: str,
) -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 000 4101",
                                "phone_number_id": phone_number_id,
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712347788",
                                    "recipient_id": "14150004101",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature(app_secret, raw_body)

    response = client.post(
        f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200


@pytest.fixture
def strict_db_session_factory(tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    database_path = tmp_path / "strict_auth.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    from app.db.base import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    yield factory

    engine.dispose()


@pytest.fixture
def strict_client(strict_db_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:

    original_env = {
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
    }
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["LIVE_TRANSLATION_ENABLED"] = "false"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"

    from app.core.settings import get_settings

    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = strict_db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _seed_launch_readiness_focus_accounts(
    client: TestClient,
    *,
    admin_headers: dict[str, str],
) -> None:
    ready_create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "launch-focus-ready-account",
            "display_name": "Launch Focus Ready Account",
            "meta_business_portfolio_id": "biz-launch-focus-ready",
            "waba_id": "waba-launch-focus-ready",
            "access_token": "token-launch-focus-ready",
            "verify_token": "verify-launch-focus-ready",
            "app_secret": "secret-launch-focus-ready",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-launch-focus-ready",
                    "display_phone_number": "+1 555 000 5101",
                    "verified_name": "Launch Focus Ready",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
        headers=admin_headers,
    )
    assert ready_create_response.status_code == 200

    ready_subscribe_response = client.post(
        "/api/meta/accounts/launch-focus-ready-account/wabas/waba-launch-focus-ready/webhook-subscription",
        json={"callback_url": "https://example.com/launch-focus-ready/webhook"},
        headers=admin_headers,
    )
    assert ready_subscribe_response.status_code == 200

    ready_verify_response = client.get(
        "/webhooks/whatsapp/launch-focus-ready-account/wabas/waba-launch-focus-ready",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-launch-focus-ready",
            "hub.challenge": "challenge-launch-focus-ready",
        },
        headers=admin_headers,
    )
    assert ready_verify_response.status_code == 200

    pending_create_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "launch-focus-pending-account",
            "display_name": "Launch Focus Pending Account",
            "meta_business_portfolio_id": "biz-launch-focus-pending",
            "waba_id": "waba-launch-focus-pending",
            "access_token": "token-launch-focus-pending",
            "verify_token": "verify-launch-focus-pending",
            "app_secret": "secret-launch-focus-pending",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-launch-focus-pending",
                    "display_phone_number": "+1 555 000 5102",
                    "verified_name": "Launch Focus Pending",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
        headers=admin_headers,
    )
    assert pending_create_response.status_code == 200

    pending_subscribe_response = client.post(
        "/api/meta/accounts/launch-focus-pending-account/wabas/waba-launch-focus-pending/webhook-subscription",
        json={"callback_url": "https://example.com/launch-focus-pending/webhook"},
        headers=admin_headers,
    )
    assert pending_subscribe_response.status_code == 200


def _mark_meta_account_ready_for_launch_readiness(
    strict_db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    waba_id: str,
    callback_url: str,
) -> None:
    with strict_db_session_factory() as session:
        waba_account = session.query(WhatsAppBusinessAccount).filter(
            WhatsAppBusinessAccount.account_id == account_id,
            WhatsAppBusinessAccount.waba_id == waba_id,
        ).one()
        waba_account.webhook_subscribed = True
        waba_account.webhook_verification_status = "verified"
        waba_account.webhook_last_verified_at = utc_now()
        waba_account.webhook_last_verification_error = None
        session.add(
            WebhookSubscription(
                account_id=account_id,
                waba_account_id=waba_account.id,
                waba_id=waba_id,
                callback_url=callback_url,
                verify_token=waba_account.verify_token,
                app_id=None,
                status="remote_subscribed",
                subscribed_at=utc_now(),
            )
        )
        session.add(waba_account)
        session.commit()


def test_runtime_state_requires_actor_headers_when_not_in_test_mode(strict_client: TestClient) -> None:
    response = strict_client.get("/api/runtime/state")

    assert response.status_code == 401
    assert "X-Actor-Id" in response.json()["detail"]


def test_runtime_state_accepts_jwt_only_agent_actor_without_explicit_actor_headers(
    strict_client: TestClient,
) -> None:
    token = _issue_jwt(
        sub="agent-jwt-only-runtime-view",
        agency_id="agency-jwt-only-runtime-view",
        user_type="agent",
        role="agent",
        username="agent-jwt-only-runtime-view",
    )

    response = strict_client.get(
        "/api/runtime/state",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "accounts" in payload
    assert "conversations" in payload


def test_runtime_register_account_accepts_jwt_only_super_admin_with_system_agency_scope(
    strict_client: TestClient,
) -> None:
    token = _issue_jwt(
        sub="super-admin-jwt-only-runtime-edit",
        agency_id="system",
        user_type="super_admin",
        role="super_admin",
        username="super-admin-jwt-only-runtime-edit",
    )

    response = strict_client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "runtime-jwt-super-admin-account",
            "display_name": "Runtime JWT Super Admin Account",
            "provider_type": "mock",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["account_id"] == "runtime-jwt-super-admin-account"


def test_runtime_state_rejects_invalid_jwt_even_if_legacy_actor_headers_are_present(
    strict_client: TestClient,
) -> None:
    response = strict_client.get(
        "/api/runtime/state",
        headers={
            "Authorization": "Bearer invalidtoken123",
            "X-Actor-Id": "legacy-header-admin",
            "X-Actor-Role": "super_admin",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token."


def test_permission_center_rejects_header_only_actor_when_auth_is_required(
    strict_client: TestClient,
) -> None:
    original_env = {"APP_ENV": os.environ.get("APP_ENV")}
    try:
        os.environ["APP_ENV"] = "production"
        from app.core.settings import get_settings

        get_settings.cache_clear()
        response = strict_client.get(
            "/api/auth/permissions",
            headers={
                "X-Actor-Id": "legacy-header-admin",
                "X-Actor-Role": "super_admin",
            },
        )

        assert response.status_code == 401
    finally:
        if original_env["APP_ENV"] is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = original_env["APP_ENV"]
        get_settings.cache_clear()


def test_get_request_actor_ignores_legacy_headers_when_bearer_jwt_is_present(
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    token = _issue_jwt(
        sub="jwt-scope-owner",
        agency_id="agency-jwt-scope",
        user_type="agent",
        role="agent",
        username="jwt-username",
        display_name="JWT Display Name",
        account_ids=["jwt-account-a", "jwt-account-b"],
    )

    with strict_db_session_factory() as session:
        actor = get_request_actor(
            request=_build_request(
                {
                    "Authorization": f"Bearer {token}",
                    "X-Actor-Id": "legacy-header-admin",
                    "X-Actor-Role": "super_admin",
                    "X-Actor-Name": "Legacy Header Name",
                    "X-Actor-Account-Ids": "legacy-account-only",
                }
            ),
            settings=get_settings(),
            session=session,
        )

    assert actor.actor_id == "jwt-scope-owner"
    assert actor.role.value == "agent"
    assert actor.display_name == "JWT Display Name"
    assert actor.account_ids == ["jwt-account-a", "jwt-account-b"]


def test_get_request_actor_backfills_db_account_scope_when_jwt_has_no_account_ids(
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    with strict_db_session_factory() as session:
        session.add(
            Account(
                account_id="agency-db-scope-account",
                display_name="Agency DB Scope Account",
                provider_type="mock",
            )
        )
        session.add(
            Agency(
                id="agency-db-scope",
                name="Agency DB Scope",
                username="agency-db-scope-owner",
                password_hash="placeholder",
            )
        )
        session.add(
            H5Site(
                id="agency-db-scope-site",
                account_id="agency-db-scope-account",
                site_key="agency-db-scope-site-key",
                domain="agency-db-scope.example.com",
                brand_name="Agency DB Scope Brand",
                agency_id="agency-db-scope",
            )
        )
        session.commit()

        actor = get_request_actor(
            request=_build_request(
                {
                    "Authorization": (
                        "Bearer "
                        + _issue_jwt(
                            sub="jwt-db-scope-owner",
                            agency_id="agency-db-scope",
                            user_type="agent",
                            role="agent",
                            username="jwt-db-scope-owner",
                        )
                    ),
                    "X-Actor-Account-Ids": "legacy-overridden-account",
                }
            ),
            settings=get_settings(),
            session=session,
        )

    assert actor.account_ids == ["agency-db-scope-account"]


def test_api_stats_middleware_uses_jwt_scope_instead_of_legacy_actor_header(
    strict_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations: list[tuple[str, str, int | None]] = []

    class RecordingRedis:
        def incr(self, key: str) -> int:
            operations.append(("incr", key, None))
            return 1

        def incrby(self, key: str, value: int) -> int:
            operations.append(("incrby", key, value))
            return value

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.core.api_stats_middleware.sync_redis.from_url",
        lambda *args, **kwargs: RecordingRedis(),
    )

    token = _issue_jwt(
        sub="jwt-api-stats-admin",
        agency_id="system",
        user_type="super_admin",
        role="super_admin",
        username="jwt-api-stats-admin",
    )

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Actor-Id": "legacy-header-admin",
            "X-Actor-Role": "operator",
        },
    )

    assert response.status_code == 200, response.text
    assert any(
        op == "incr" and key.startswith("api_stats:system:/api/auth/permissions:")
        for op, key, _ in operations
    )
    assert not any(
        op == "incr" and key.startswith("api_stats:legacy-header-admin:/api/auth/permissions:")
        for op, key, _ in operations
    )


def test_runtime_account_audit_uses_jwt_subject_when_legacy_actor_headers_conflict(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    token = _issue_jwt(
        sub="jwt-admin-actor",
        agency_id="system",
        user_type="super_admin",
        role="super_admin",
        username="jwt-admin-actor",
    )

    response = strict_client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "runtime-jwt-audit-account",
            "display_name": "Runtime JWT Audit Account",
            "provider_type": "mock",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Actor-Id": "legacy-header-admin",
            "X-Actor-Role": "operator",
        },
    )

    assert response.status_code == 200, response.text

    with strict_db_session_factory() as session:
        audit_log = session.query(AuditLog).filter(AuditLog.target_id == "runtime-jwt-audit-account").one()
        assert audit_log.actor_id == "jwt-admin-actor"


def test_account_scope_blocks_cross_account_read(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-1",
        "X-Actor-Role": "super_admin",
    }
    strict_client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "account-alpha",
            "display_name": "Alpha",
            "provider_type": "mock",
        },
        headers=admin_headers,
    )

    response = strict_client.get(
        "/api/ecommerce/orders",
        params={"account_id": "account-alpha"},
        headers={
            "X-Actor-Id": "agent-1",
            "X-Actor-Role": "support_agent",
            "X-Actor-Account-Ids": "account-beta",
        },
    )

    assert response.status_code == 403
    assert "account-alpha" in response.json()["detail"]


def test_meta_account_list_respects_actor_account_scope(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-meta-scope",
        "X-Actor-Role": "super_admin",
    }
    scoped_headers = {
        "X-Actor-Id": "operator-meta-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "meta-scope-a",
    }

    for account_id, display_name, portfolio_id, waba_id in (
        ("meta-scope-a", "Meta Scope A", "biz-meta-scope-a", "waba-meta-scope-a"),
        ("meta-scope-b", "Meta Scope B", "biz-meta-scope-b", "waba-meta-scope-b"),
    ):
        create_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200

    allowed_response = strict_client.get(
        "/api/meta/accounts",
        headers=scoped_headers,
    )
    assert allowed_response.status_code == 200
    assert [item["account_id"] for item in allowed_response.json()] == ["meta-scope-a"]

    filtered_response = strict_client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-scope-a"},
        headers=scoped_headers,
    )
    assert filtered_response.status_code == 200
    assert [item["waba_id"] for item in filtered_response.json()] == ["waba-meta-scope-a"]

    denied_response = strict_client.get(
        "/api/meta/accounts",
        params={"account_id": "meta-scope-b"},
        headers=scoped_headers,
    )
    assert denied_response.status_code == 403
    assert "meta-scope-b" in denied_response.json()["detail"]


def test_meta_scope_list_mismatch_does_not_leak_hidden_owner_account(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-meta-scope-mismatch",
        "X-Actor-Role": "super_admin",
    }
    scoped_headers = {
        "X-Actor-Id": "operator-meta-scope-mismatch",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "meta-scope-leak-a",
    }

    for account_id, display_name, portfolio_id, waba_id in (
        ("meta-scope-leak-a", "Meta Scope Leak A", "biz-meta-scope-leak-a", "waba-meta-scope-leak-a"),
        ("meta-scope-leak-b", "Meta Scope Leak B", "biz-meta-scope-leak-b", "waba-meta-scope-leak-b"),
    ):
        create_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": f"secret-{account_id}",
                "token_source": "system_user",
                "phone_numbers": [],
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200

    for path in (
        "/api/meta/accounts",
        "/api/meta/accounts/phone-numbers",
        "/api/meta/accounts/webhook-subscriptions",
        "/api/meta/accounts/embedded-signup/sessions",
    ):
        mismatch_response = strict_client.get(
            path,
            params={
                "account_id": "meta-scope-leak-a",
                "waba_id": "waba-meta-scope-leak-b",
            },
            headers=scoped_headers,
        )
        assert mismatch_response.status_code == 400, (path, mismatch_response.text)
        detail = mismatch_response.json()["detail"]
        assert detail == "WABA 'waba-meta-scope-leak-b' is not available in account 'meta-scope-leak-a'."
        assert "belongs to account" not in detail
        assert "not 'meta-scope-leak-a'" not in detail


def test_meta_account_ready_filters_keep_visible_scope_and_blocking_reason_consistency(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-meta-ready-filter",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-meta-ready-filter",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": (
            "launch-focus-ready-account,launch-focus-pending-account"
        ),
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())
        _seed_launch_readiness_focus_accounts(strict_client, admin_headers=admin_headers)

        ready_response = strict_client.get(
            "/api/meta/accounts",
            params={"ready_for_webhook_delivery": True},
            headers=operator_headers,
        )
        assert ready_response.status_code == 200, ready_response.text
        ready_accounts = ready_response.json()
        assert [item["account_id"] for item in ready_accounts] == [
            "launch-focus-ready-account"
        ]
        assert ready_accounts[0]["waba_id"] == "waba-launch-focus-ready"
        assert ready_accounts[0]["ready_for_webhook_delivery"] is True
        assert ready_accounts[0]["ready_for_meta_activation"] is True
        assert ready_accounts[0]["blocking_reasons"] == []

        pending_response = strict_client.get(
            "/api/meta/accounts",
            params={"ready_for_webhook_delivery": False},
            headers=operator_headers,
        )
        assert pending_response.status_code == 200, pending_response.text
        pending_accounts = pending_response.json()
        assert [item["account_id"] for item in pending_accounts] == [
            "launch-focus-pending-account"
        ]
        assert pending_accounts[0]["waba_id"] == "waba-launch-focus-pending"
        assert pending_accounts[0]["ready_for_webhook_delivery"] is False
        assert pending_accounts[0]["ready_for_meta_activation"] is False
        assert pending_accounts[0]["webhook_verification_status"] == "pending"
        assert pending_accounts[0]["blocking_reasons"] == ["webhook_not_ready"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_meta_phone_number_filters_respect_actor_account_scope(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-meta-phone-filter",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-meta-phone-filter",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": (
            "launch-focus-ready-account,launch-focus-pending-account"
        ),
    }
    ready_only_headers = {
        "X-Actor-Id": "operator-meta-phone-ready-only",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "launch-focus-ready-account",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())
        _seed_launch_readiness_focus_accounts(strict_client, admin_headers=admin_headers)

        ready_response = strict_client.get(
            "/api/meta/accounts/phone-numbers",
            params={"ready_for_meta_activation": True},
            headers=operator_headers,
        )
        assert ready_response.status_code == 200, ready_response.text
        ready_phone_numbers = ready_response.json()
        assert [item["account_id"] for item in ready_phone_numbers] == [
            "launch-focus-ready-account"
        ]
        assert [item["phone_number_id"] for item in ready_phone_numbers] == [
            "pn-launch-focus-ready"
        ]
        assert ready_phone_numbers[0]["waba_id"] == "waba-launch-focus-ready"
        assert ready_phone_numbers[0]["ready_for_meta_activation"] is True

        pending_response = strict_client.get(
            "/api/meta/accounts/phone-numbers",
            params={"ready_for_meta_activation": False},
            headers=operator_headers,
        )
        assert pending_response.status_code == 200, pending_response.text
        pending_phone_numbers = pending_response.json()
        assert [item["account_id"] for item in pending_phone_numbers] == [
            "launch-focus-pending-account"
        ]
        assert [item["phone_number_id"] for item in pending_phone_numbers] == [
            "pn-launch-focus-pending"
        ]
        assert pending_phone_numbers[0]["ready_for_meta_activation"] is False

        hidden_waba_response = strict_client.get(
            "/api/meta/accounts/phone-numbers",
            params={"waba_id": "waba-launch-focus-pending"},
            headers=ready_only_headers,
        )
        assert hidden_waba_response.status_code == 200, hidden_waba_response.text
        assert hidden_waba_response.json() == []

        denied_response = strict_client.get(
            "/api/meta/accounts/phone-numbers",
            params={"account_id": "launch-focus-pending-account"},
            headers=ready_only_headers,
        )
        assert denied_response.status_code == 403
        assert "launch-focus-pending-account" in denied_response.json()["detail"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_meta_webhook_subscription_filters_respect_actor_account_scope(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-meta-subscription-filter",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-meta-subscription-filter",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": (
            "launch-focus-ready-account,launch-focus-pending-account"
        ),
    }
    ready_only_headers = {
        "X-Actor-Id": "operator-meta-subscription-ready-only",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "launch-focus-ready-account",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())
        _seed_launch_readiness_focus_accounts(strict_client, admin_headers=admin_headers)
        resubscribe_response = strict_client.post(
            "/api/meta/accounts/launch-focus-ready-account/wabas/waba-launch-focus-ready/webhook-subscription",
            json={"callback_url": "https://example.com/launch-focus-ready/webhook-v2"},
            headers=admin_headers,
        )
        assert resubscribe_response.status_code == 200, resubscribe_response.text
        reverify_response = strict_client.get(
            "/webhooks/whatsapp/launch-focus-ready-account/wabas/waba-launch-focus-ready",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-launch-focus-ready",
                "hub.challenge": "challenge-launch-focus-ready-v2",
            },
            headers=admin_headers,
        )
        assert reverify_response.status_code == 200, reverify_response.text

        verified_response = strict_client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"webhook_verification_status": "verified"},
            headers=operator_headers,
        )
        assert verified_response.status_code == 200, verified_response.text
        verified_subscriptions = verified_response.json()
        assert [item["account_id"] for item in verified_subscriptions] == [
            "launch-focus-ready-account"
        ]
        assert verified_subscriptions[0]["waba_id"] == "waba-launch-focus-ready"
        assert verified_subscriptions[0]["webhook_verification_status"] == "verified"
        assert [item["callback_url"] for item in verified_subscriptions] == [
            "https://example.com/launch-focus-ready/webhook-v2"
        ]

        pending_response = strict_client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"webhook_verification_status": "pending"},
            headers=operator_headers,
        )
        assert pending_response.status_code == 200, pending_response.text
        pending_subscriptions = pending_response.json()
        assert [item["account_id"] for item in pending_subscriptions] == [
            "launch-focus-pending-account"
        ]
        assert pending_subscriptions[0]["waba_id"] == "waba-launch-focus-pending"
        assert pending_subscriptions[0]["webhook_verification_status"] == "pending"

        hidden_waba_response = strict_client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"waba_id": "waba-launch-focus-pending"},
            headers=ready_only_headers,
        )
        assert hidden_waba_response.status_code == 200, hidden_waba_response.text
        assert hidden_waba_response.json() == []

        denied_response = strict_client.get(
            "/api/meta/accounts/webhook-subscriptions",
            params={"account_id": "launch-focus-pending-account"},
            headers=ready_only_headers,
        )
        assert denied_response.status_code == 403
        assert "launch-focus-pending-account" in denied_response.json()["detail"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_embedded_signup_session_ready_filters_keep_visible_scope_and_blocking_reason_consistency(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-signup-ready-filter",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-signup-ready-filter",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": (
            "signup-filter-visible-ready-account,signup-filter-visible-pending-account"
        ),
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "META_APP_SECRET": os.environ.get("META_APP_SECRET"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["META_APP_SECRET"] = "meta-app-secret-signup-scope-filter"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())

        session_ids: dict[str, str] = {}
        for account_id, display_name, callback_suffix in (
            (
                "signup-filter-visible-ready-account",
                "Signup Filter Visible Ready",
                "visible-ready",
            ),
            (
                "signup-filter-visible-pending-account",
                "Signup Filter Visible Pending",
                "visible-pending",
            ),
            (
                "signup-filter-hidden-ready-account",
                "Signup Filter Hidden Ready",
                "hidden-ready",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/embedded-signup/session",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "redirect_uri": f"https://example.com/embedded-signup/{callback_suffix}",
                    "webhook_subscription": {
                        "callback_url": f"https://example.com/webhooks/{callback_suffix}",
                        "verify_token": f"verify-{callback_suffix}",
                        "app_id": f"app-{callback_suffix}",
                    },
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200, create_response.text
            session_id = create_response.json()["session_id"]
            session_ids[account_id] = session_id

            callback_response = strict_client.post(
                f"/webhooks/meta/embedded-signup/session/{session_id}",
                json={
                    "status": "completed",
                    "waba_id": f"waba-{callback_suffix}",
                    "meta_business_portfolio_id": f"biz-{callback_suffix}",
                    "phone_number_ids": [f"pn-{callback_suffix}-1"],
                    "authorization_code": f"code-{callback_suffix}",
                    "raw_payload": {"source": f"scope-filter-{callback_suffix}"},
                },
                headers=admin_headers,
            )
            assert callback_response.status_code == 200, callback_response.text
            assert callback_response.json()["webhook_verification_status"] == "pending"

        for account_id, callback_suffix in (
            ("signup-filter-visible-ready-account", "visible-ready"),
            ("signup-filter-hidden-ready-account", "hidden-ready"),
        ):
            verify_response = strict_client.get(
                f"/webhooks/whatsapp/{account_id}/wabas/waba-{callback_suffix}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": f"verify-{callback_suffix}",
                    "hub.challenge": f"challenge-{callback_suffix}",
                },
                headers=admin_headers,
            )
            assert verify_response.status_code == 200, verify_response.text

        ready_response = strict_client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"ready_for_webhook_delivery": True},
            headers=operator_headers,
        )
        assert ready_response.status_code == 200, ready_response.text
        ready_sessions = ready_response.json()
        assert [item["account_id"] for item in ready_sessions] == [
            "signup-filter-visible-ready-account"
        ]
        assert [item["session_id"] for item in ready_sessions] == [
            session_ids["signup-filter-visible-ready-account"]
        ]
        assert ready_sessions[0]["webhook_verification_status"] == "verified"
        assert ready_sessions[0]["ready_for_webhook_delivery"] is True
        assert "webhook_not_ready" not in ready_sessions[0]["webhook_blocking_reasons"]

        pending_response = strict_client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"ready_for_webhook_delivery": False},
            headers=operator_headers,
        )
        assert pending_response.status_code == 200, pending_response.text
        pending_sessions = pending_response.json()
        assert [item["account_id"] for item in pending_sessions] == [
            "signup-filter-visible-pending-account"
        ]
        assert [item["session_id"] for item in pending_sessions] == [
            session_ids["signup-filter-visible-pending-account"]
        ]
        assert pending_sessions[0]["webhook_verification_status"] == "pending"
        assert pending_sessions[0]["ready_for_webhook_delivery"] is False
        assert "webhook_not_ready" in pending_sessions[0]["webhook_blocking_reasons"]

        hidden_response = strict_client.get(
            "/api/meta/accounts/embedded-signup/sessions",
            params={"account_id": "signup-filter-hidden-ready-account"},
            headers=operator_headers,
        )
        assert hidden_response.status_code == 403
        assert "signup-filter-hidden-ready-account" in str(hidden_response.json()["detail"])
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_media_library_permissions_are_explicit(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-media-1",
        "X-Actor-Role": "super_admin",
    }
    support_headers = {
        "X-Actor-Id": "readonly-media-1",
        "X-Actor-Role": "readonly",
        "X-Actor-Account-Ids": "media-account-auth-1",
    }

    create_account_response = strict_client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "media-account-auth-1",
            "display_name": "Media Account Auth 1",
            "provider_type": "mock",
        },
        headers=admin_headers,
    )
    assert create_account_response.status_code == 200

    list_response = strict_client.get(
        "/api/media/assets",
        params={"account_id": "media-account-auth-1"},
        headers=support_headers,
    )
    assert list_response.status_code == 200

    create_response = strict_client.post(
        "/api/media/assets",
        json={
            "account_id": "media-account-auth-1",
            "name": "auth-media-asset",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "storage_url": "https://cdn.example.com/auth-media.jpg",
            "source": "auth_test",
            "tags": [],
        },
        headers=support_headers,
    )
    assert create_response.status_code == 403
    assert "media.upload" in create_response.json()["detail"]


def test_runtime_agent_global_scope_requires_super_admin(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-agent-scope",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-agent-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "agent-scope-auth",
    }

    denied_global_create = strict_client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "global-agent-auth",
            "display_name": "Global Agent Auth",
            "status": "online",
            "is_active": True,
        },
        headers=operator_headers,
    )
    assert denied_global_create.status_code == 403
    assert "explicit account scope" in denied_global_create.json()["detail"]

    admin_global_create = strict_client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "global-agent-auth",
            "display_name": "Global Agent Auth",
            "status": "online",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert admin_global_create.status_code == 200
    assert admin_global_create.json()["account_id"] is None

    denied_global_status = strict_client.post(
        "/api/runtime/agents/global-agent-auth/status",
        json={"status": "busy"},
        headers=operator_headers,
    )
    assert denied_global_status.status_code == 403
    assert "explicit account scope" in denied_global_status.json()["detail"]

    scoped_create = strict_client.post(
        "/api/runtime/agents",
        json={
            "account_id": "agent-scope-auth",
            "agent_id": "scoped-agent-auth",
            "display_name": "Scoped Agent Auth",
            "status": "offline",
            "is_active": True,
        },
        headers=operator_headers,
    )
    assert scoped_create.status_code == 200
    assert scoped_create.json()["account_id"] == "agent-scope-auth"

    scoped_status = strict_client.post(
        "/api/runtime/agents/scoped-agent-auth/status",
        params={"account_id": "agent-scope-auth"},
        json={"status": "online"},
        headers=operator_headers,
    )
    assert scoped_status.status_code == 200
    assert scoped_status.json()["status"] == "online"


def test_extended_roles_are_accepted_for_authorized_reads(strict_client: TestClient) -> None:
    cases = (
        ("reviewer", "/api/tasks/templates"),
        ("finance", "/api/finance/recharge-records"),
        ("risk_control", "/api/platform/users"),
    )

    for role, path in cases:
        response = strict_client.get(
            path,
            headers={
                "X-Actor-Id": f"{role}-reader-1",
                "X-Actor-Role": role,
            },
        )

        assert response.status_code == 200, response.text


def test_global_ai_audit_uses_request_actor(client: TestClient) -> None:
    headers = {
        "X-Actor-Id": "admin-audit",
        "X-Actor-Role": "super_admin",
        "X-Actor-Name": "Audit Admin",
    }

    response = client.post(
        "/api/runtime/ai/global",
        json={"enabled": False},
        headers=headers,
    )
    assert response.status_code == 200

    logs_response = client.get("/api/runtime/audit-logs", headers=headers)
    assert logs_response.status_code == 200
    assert logs_response.json()[0]["actor_id"] == "admin-audit"
    assert logs_response.json()[0]["actor_type"] == "user"


def test_launch_readiness_respects_actor_account_scope(strict_client: TestClient) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-scope-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "scope-account-a",
    }

    create_a_response = strict_client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "scope-account-a",
            "display_name": "Scope Account A",
            "meta_business_portfolio_id": "biz-scope-a",
            "waba_id": "waba-scope-a",
            "access_token": "token-scope-a",
            "verify_token": "verify-scope-a",
            "app_secret": "secret-scope-a",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-scope-a",
                    "display_phone_number": "+1 555 000 3101",
                    "verified_name": "Scope Account A",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
        headers=admin_headers,
    )
    assert create_a_response.status_code == 200

    subscribe_a_response = strict_client.post(
        "/api/meta/accounts/scope-account-a/wabas/waba-scope-a/webhook-subscription",
        json={
            "callback_url": "https://example.com/scope-a/webhook",
        },
        headers=admin_headers,
    )
    assert subscribe_a_response.status_code == 200

    create_b_response = strict_client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "scope-account-b",
            "display_name": "Scope Account B",
            "meta_business_portfolio_id": "biz-scope-b",
            "waba_id": "waba-scope-b",
            "access_token": "token-scope-b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
        headers=admin_headers,
    )
    assert create_b_response.status_code == 200

    response = strict_client.get(
        "/api/runtime/launch-readiness",
        headers=operator_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["active_account_count"] == 1
    assert payload["summary"]["meta_account_count"] == 1
    assert payload["summary"]["meta_ready_account_count"] == 1

    account_checks = [item for item in payload["checks"] if item["scope"] == "account"]
    assert len(account_checks) >= 1
    assert all(item["account_id"] == "scope-account-a" for item in account_checks)
    assert all(item["waba_id"] == "waba-scope-a" for item in account_checks)
    assert any(
        item["key"] == "meta.account.scope-account-a.waba-scope-a" and item["status"] == "pass"
        for item in account_checks
    )
    assert not any(item.get("account_id") == "scope-account-b" for item in payload["checks"])


def test_launch_readiness_provider_status_buffer_uses_actor_account_scope(
    strict_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-buffer-scope",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-launch-buffer-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "launch-buffer-scope-a",
    }

    for account_id, display_name, portfolio_id, waba_id, phone_number_id, app_secret in (
        (
            "launch-buffer-scope-a",
            "Launch Buffer Scope A",
            "biz-launch-buffer-scope-a",
            "waba-launch-buffer-scope-a",
            "pn-launch-buffer-scope-a",
            "secret-launch-buffer-scope-a",
        ),
        (
            "launch-buffer-scope-b",
            "Launch Buffer Scope B",
            "biz-launch-buffer-scope-b",
            "waba-launch-buffer-scope-b",
            "pn-launch-buffer-scope-b",
            "secret-launch-buffer-scope-b",
        ),
    ):
        create_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": app_secret,
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": "+1 555 000 4101",
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200
        _post_unmatched_provider_status_webhook(
            strict_client,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            app_secret=app_secret,
            provider_message_id=f"wamid.{account_id}.pending.1",
        )

    admin_response = strict_client.get(
        "/api/runtime/launch-readiness",
        headers=admin_headers,
    )
    assert admin_response.status_code == 200
    admin_checks = {item["key"]: item for item in admin_response.json()["checks"]}
    assert admin_checks["messaging.provider_status_buffer"]["metadata"]["pending_by_account"] == {
        "launch-buffer-scope-a": 1,
        "launch-buffer-scope-b": 1,
    }
    assert admin_checks["messaging.provider_status_buffer"]["metadata"]["pending_account_count"] == 2

    scoped_response = strict_client.get(
        "/api/runtime/launch-readiness",
        headers=operator_headers,
    )

    assert scoped_response.status_code == 200
    scoped_checks = {item["key"]: item for item in scoped_response.json()["checks"]}
    buffer_check = scoped_checks["messaging.provider_status_buffer"]
    assert buffer_check["status"] == "warning"
    assert buffer_check["metadata"]["pending_count"] == 1
    assert buffer_check["metadata"]["pending_by_account"] == {
        "launch-buffer-scope-a": 1,
    }
    assert buffer_check["metadata"]["pending_account_count"] == 1
    assert buffer_check["metadata"]["pending_accounts_ranked"] == [
        {
            "account_id": "launch-buffer-scope-a",
            "pending_count": 1,
        }
    ]
    assert buffer_check["metadata"]["oldest_pending_event"]["account_id"] == "launch-buffer-scope-a"


def test_launch_readiness_provider_status_buffer_becomes_blocker_in_whatsapp_mode(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-buffer-blocker",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        create_response = strict_client.post(
            "/api/runtime/accounts",
            json={
                "account_id": "launch-buffer-blocker-account",
                "display_name": "Launch Buffer Blocker Account",
                "provider_type": "whatsapp",
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200

        with strict_db_session_factory() as session:
            now = utc_now()
            session.add(
                ProviderStatusEventBuffer(
                    account_id="launch-buffer-blocker-account",
                    provider_name="whatsapp",
                    waba_id="waba-launch-buffer-blocker",
                    phone_number_id="pn-launch-buffer-blocker",
                    provider_message_id="wamid.launch.buffer.blocker.1",
                    external_status="delivered",
                    payload={"conversation_category": "utility"},
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                    replay_state="pending",
                )
            )
            session.commit()

        response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers=admin_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        buffer_check = checks["messaging.provider_status_buffer"]

        assert payload["summary"]["overall_status"] == "blocked"
        assert buffer_check["status"] == "blocker"
        assert buffer_check["metadata"]["pending_count"] == 1
        assert buffer_check["metadata"]["pending_by_account"] == {
            "launch-buffer-blocker-account": 1,
        }
        assert buffer_check["metadata"]["pending_account_count"] == 1
        assert buffer_check["metadata"]["oldest_pending_event"]["account_id"] == "launch-buffer-blocker-account"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        from app.core.settings import get_settings

        get_settings.cache_clear()


def test_provider_status_buffer_list_uses_actor_account_scope(
    strict_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-buffer-list-scope",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-buffer-list-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "buffer-list-scope-a",
    }

    for account_id, display_name, portfolio_id, waba_id, phone_number_id, app_secret in (
        (
            "buffer-list-scope-a",
            "Buffer List Scope A",
            "biz-buffer-list-scope-a",
            "waba-buffer-list-scope-a",
            "pn-buffer-list-scope-a",
            "secret-buffer-list-scope-a",
        ),
        (
            "buffer-list-scope-b",
            "Buffer List Scope B",
            "biz-buffer-list-scope-b",
            "waba-buffer-list-scope-b",
            "pn-buffer-list-scope-b",
            "secret-buffer-list-scope-b",
        ),
    ):
        create_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "meta_business_portfolio_id": portfolio_id,
                "waba_id": waba_id,
                "access_token": f"token-{account_id}",
                "verify_token": f"verify-{account_id}",
                "app_secret": app_secret,
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": "+1 555 000 4301",
                        "verified_name": display_name,
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200
        _post_unmatched_provider_status_webhook(
            strict_client,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            app_secret=app_secret,
            provider_message_id=f"wamid.{account_id}.pending.1",
        )

    response = strict_client.get(
        "/api/runtime/provider-status-buffer",
        headers=operator_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pending_count"] == 1
    assert payload["replayed_count"] == 0
    assert payload["returned_count"] == 1
    assert [item["account_id"] for item in payload["items"]] == ["buffer-list-scope-a"]


def test_provider_status_buffer_replay_rejects_cross_account_scope(
    strict_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-buffer-replay-scope",
        "X-Actor-Role": "super_admin",
    }
    operator_headers = {
        "X-Actor-Id": "operator-buffer-replay-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "buffer-replay-scope-a",
    }

    create_response = strict_client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "buffer-replay-scope-b",
            "display_name": "Buffer Replay Scope B",
            "meta_business_portfolio_id": "biz-buffer-replay-scope-b",
            "waba_id": "waba-buffer-replay-scope-b",
            "access_token": "token-buffer-replay-scope-b",
            "verify_token": "verify-buffer-replay-scope-b",
            "app_secret": "secret-buffer-replay-scope-b",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-buffer-replay-scope-b",
                    "display_phone_number": "+1 555 000 4401",
                    "verified_name": "Buffer Replay Scope B",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    _post_unmatched_provider_status_webhook(
        strict_client,
        account_id="buffer-replay-scope-b",
        waba_id="waba-buffer-replay-scope-b",
        phone_number_id="pn-buffer-replay-scope-b",
        app_secret="secret-buffer-replay-scope-b",
        provider_message_id="wamid.buffer-replay-scope-b.pending.1",
    )

    response = strict_client.post(
        "/api/runtime/provider-status-buffer/replay",
        json={
            "account_id": "buffer-replay-scope-b",
            "provider_name": "whatsapp",
            "provider_message_id": "wamid.buffer-replay-scope-b.pending.1",
        },
        headers=operator_headers,
    )

    assert response.status_code == 403


def test_launch_readiness_filters_account_scoped_checks_for_non_super_admin(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-scope",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())

        for account_id, display_name, portfolio_id, waba_id, phone_number_id in (
            (
                "account-scope-alpha",
                "Scope Alpha",
                "biz-scope-alpha",
                "waba-scope-alpha",
                "pn-scope-alpha",
            ),
            (
                "account-scope-beta",
                "Scope Beta",
                "biz-scope-beta",
                "waba-scope-beta",
                "pn-scope-beta",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": f"verify-{account_id}",
                    "app_secret": f"secret-{account_id}",
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200

            subscribe_response = strict_client.post(
                f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
                json={"callback_url": f"https://example.com/{account_id}/webhook"},
                headers=admin_headers,
            )
            assert subscribe_response.status_code == 200

            verify_response = strict_client.get(
                f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": f"verify-{account_id}",
                    "hub.challenge": f"challenge-{account_id}",
                },
                headers=admin_headers,
            )
            assert verify_response.status_code == 200

        response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-alpha",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "account-scope-alpha",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        account_check_keys = {
            item["key"]
            for item in payload["checks"]
            if item.get("scope") == "account"
        }

        assert payload["summary"]["active_account_count"] == 1
        assert payload["summary"]["meta_account_count"] == 1
        assert payload["summary"]["meta_ready_account_count"] == 1
        assert checks["meta.accounts_present"]["status"] == "pass"
        assert checks["messaging.provider_mode"]["status"] == "pass"
        assert "meta.account.account-scope-alpha.waba-scope-alpha" in account_check_keys
        assert checks["meta.account.account-scope-alpha.waba-scope-alpha"]["account_id"] == "account-scope-alpha"
        assert checks["meta.account.account-scope-alpha.waba-scope-alpha"]["status"] == "pass"
        assert "meta.account.account-scope-beta.waba-scope-beta" not in checks
        assert "meta.account.account-scope-beta.waba-scope-beta" not in account_check_keys
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_keeps_verify_token_conflicts_visible_with_hidden_scope_counts(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-conflict-scope",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"

        from app.core.settings import get_settings

        get_settings.cache_clear()

        shared_verify_token = "verify-launch-hidden-conflict-shared"
        for account_id, display_name, portfolio_id, waba_id, phone_number_id in (
            (
                "launch-hidden-conflict-alpha",
                "Launch Hidden Conflict Alpha",
                "biz-launch-hidden-conflict-alpha",
                "waba-launch-hidden-conflict-alpha",
                "pn-launch-hidden-conflict-alpha",
            ),
            (
                "launch-hidden-conflict-beta",
                "Launch Hidden Conflict Beta",
                "biz-launch-hidden-conflict-beta",
                "waba-launch-hidden-conflict-beta",
                "pn-launch-hidden-conflict-beta",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": (
                        shared_verify_token
                        if account_id == "launch-hidden-conflict-alpha"
                        else "verify-launch-hidden-conflict-beta"
                    ),
                    "app_secret": f"secret-{account_id}",
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200, create_response.text

        with strict_db_session_factory() as session:
            conflicting_waba = session.query(WhatsAppBusinessAccount).filter(
                WhatsAppBusinessAccount.account_id == "launch-hidden-conflict-beta",
                WhatsAppBusinessAccount.waba_id == "waba-launch-hidden-conflict-beta",
            ).one()
            conflicting_waba.verify_token = shared_verify_token
            session.add(conflicting_waba)
            session.commit()

        scoped_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-launch-hidden-conflict-alpha",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "launch-hidden-conflict-alpha",
            },
        )

        assert scoped_response.status_code == 200, scoped_response.text
        checks = {item["key"]: item for item in scoped_response.json()["checks"]}
        verify_routing_check = checks["meta.webhook_verify_token_routing"]

        assert verify_routing_check["status"] == "blocker"
        assert verify_routing_check["metadata"]["conflict_count"] == 1
        assert verify_routing_check["metadata"]["hidden_scope_count"] == 1
        assert "outside the current account visibility" in verify_routing_check["message"]

        conflicts = verify_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["hidden_scope_count"] == 1
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-hidden-conflict-alpha",
                "waba_id": "waba-launch-hidden-conflict-alpha",
            }
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_keeps_root_receive_signature_conflicts_visible_with_hidden_scope_counts(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-root-receive-conflict-scope",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"

        from app.core.settings import get_settings

        get_settings.cache_clear()

        shared_callback_url = "https://example.com/webhooks/whatsapp"
        for account_id, display_name, portfolio_id, waba_id, phone_number_id, app_secret in (
            (
                "launch-root-receive-hidden-conflict-alpha",
                "Launch Root Receive Hidden Conflict Alpha",
                "biz-launch-root-receive-hidden-conflict-alpha",
                "waba-launch-root-receive-hidden-conflict-alpha",
                "pn-launch-root-receive-hidden-conflict-alpha",
                "secret-launch-root-receive-hidden-conflict-alpha",
            ),
            (
                "launch-root-receive-hidden-conflict-beta",
                "Launch Root Receive Hidden Conflict Beta",
                "biz-launch-root-receive-hidden-conflict-beta",
                "waba-launch-root-receive-hidden-conflict-beta",
                "pn-launch-root-receive-hidden-conflict-beta",
                "secret-launch-root-receive-hidden-conflict-beta",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": f"verify-{account_id}",
                    "app_secret": app_secret,
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200, create_response.text

        with strict_db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-receive-hidden-conflict-alpha",
                    "waba-launch-root-receive-hidden-conflict-alpha",
                ),
                (
                    "launch-root-receive-hidden-conflict-beta",
                    "waba-launch-root-receive-hidden-conflict-beta",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=shared_callback_url,
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        scoped_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-launch-root-receive-hidden-conflict-alpha",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "launch-root-receive-hidden-conflict-alpha",
            },
        )

        assert scoped_response.status_code == 200, scoped_response.text
        checks = {item["key"]: item for item in scoped_response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "blocker"
        assert signature_routing_check["metadata"]["conflict_count"] == 1
        assert signature_routing_check["metadata"]["hidden_scope_count"] == 1
        assert "outside the current account visibility" in signature_routing_check["message"]

        conflicts = signature_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["callback_target"] == shared_callback_url
        assert conflicts[0]["distinct_app_secret_count"] == 2
        assert conflicts[0]["hidden_scope_count"] == 1
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-root-receive-hidden-conflict-alpha",
                "waba_id": "waba-launch-root-receive-hidden-conflict-alpha",
            }
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_keeps_root_receive_signature_conflicts_visible_when_only_subscription_snapshots_hold_secrets(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"

        from app.core.settings import get_settings

        get_settings.cache_clear()

        shared_callback_url = "https://example.com/webhooks/whatsapp"
        for account_id, display_name, portfolio_id, waba_id, phone_number_id, app_secret in (
            (
                "launch-root-receive-snapshot-conflict-alpha",
                "Launch Root Receive Snapshot Conflict Alpha",
                "launch-root-receive-snapshot-conflict-portfolio-alpha",
                "waba-launch-root-receive-snapshot-conflict-alpha",
                "pn-launch-root-receive-snapshot-conflict-alpha",
                "secret-launch-root-receive-snapshot-conflict-alpha",
            ),
            (
                "launch-root-receive-snapshot-conflict-beta",
                "Launch Root Receive Snapshot Conflict Beta",
                "launch-root-receive-snapshot-conflict-portfolio-beta",
                "waba-launch-root-receive-snapshot-conflict-beta",
                "pn-launch-root-receive-snapshot-conflict-beta",
                "secret-launch-root-receive-snapshot-conflict-beta",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": f"verify-{account_id}",
                    "app_secret": app_secret,
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers={
                    "X-Actor-Id": f"admin-{account_id}",
                    "X-Actor-Role": "super_admin",
                },
            )
            assert create_response.status_code == 200, create_response.text

        with strict_db_session_factory() as session:
            for account_id, waba_id, app_secret in (
                (
                    "launch-root-receive-snapshot-conflict-alpha",
                    "waba-launch-root-receive-snapshot-conflict-alpha",
                    "secret-launch-root-receive-snapshot-conflict-alpha",
                ),
                (
                    "launch-root-receive-snapshot-conflict-beta",
                    "waba-launch-root-receive-snapshot-conflict-beta",
                    "secret-launch-root-receive-snapshot-conflict-beta",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                waba_account.webhook_verification_status = "verified"
                waba_account.app_secret = None
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=shared_callback_url,
                        verify_token=waba_account.verify_token,
                        app_secret=app_secret,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        scoped_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-launch-root-receive-snapshot-conflict-alpha",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "launch-root-receive-snapshot-conflict-alpha",
            },
        )

        assert scoped_response.status_code == 200, scoped_response.text
        checks = {item["key"]: item for item in scoped_response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "blocker"
        assert signature_routing_check["metadata"]["conflict_count"] == 1
        assert signature_routing_check["metadata"]["hidden_scope_count"] == 1

        conflicts = signature_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["callback_target"] == shared_callback_url
        assert conflicts[0]["distinct_app_secret_count"] == 2
        assert conflicts[0]["hidden_scope_count"] == 1
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-root-receive-snapshot-conflict-alpha",
                "waba_id": "waba-launch-root-receive-snapshot-conflict-alpha",
            }
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_keeps_root_receive_query_variant_conflicts_visible_with_hidden_scope_counts(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-root-receive-query-conflict-scope",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"

        from app.core.settings import get_settings

        get_settings.cache_clear()

        shared_callback_target = "https://example.com/webhooks/whatsapp"
        callback_urls = {
            "launch-root-receive-query-hidden-conflict-alpha": f"{shared_callback_target}?tenant=alpha",
            "launch-root-receive-query-hidden-conflict-beta": f"{shared_callback_target}?tenant=beta",
        }
        for account_id, display_name, portfolio_id, waba_id, phone_number_id, app_secret in (
            (
                "launch-root-receive-query-hidden-conflict-alpha",
                "Launch Root Receive Query Hidden Conflict Alpha",
                "biz-launch-root-receive-query-hidden-conflict-alpha",
                "waba-launch-root-receive-query-hidden-conflict-alpha",
                "pn-launch-root-receive-query-hidden-conflict-alpha",
                "secret-launch-root-receive-query-hidden-conflict-alpha",
            ),
            (
                "launch-root-receive-query-hidden-conflict-beta",
                "Launch Root Receive Query Hidden Conflict Beta",
                "biz-launch-root-receive-query-hidden-conflict-beta",
                "waba-launch-root-receive-query-hidden-conflict-beta",
                "pn-launch-root-receive-query-hidden-conflict-beta",
                "secret-launch-root-receive-query-hidden-conflict-beta",
            ),
        ):
            create_response = strict_client.post(
                "/api/meta/accounts/manual",
                json={
                    "account_id": account_id,
                    "display_name": display_name,
                    "meta_business_portfolio_id": portfolio_id,
                    "waba_id": waba_id,
                    "access_token": f"token-{account_id}",
                    "verify_token": f"verify-{account_id}",
                    "app_secret": app_secret,
                    "token_source": "system_user",
                    "phone_numbers": [
                        {
                            "phone_number_id": phone_number_id,
                            "display_phone_number": f"+1 555 {phone_number_id[-4:]}",
                            "verified_name": f"{display_name} Number",
                            "quality_rating": "GREEN",
                            "is_registered": True,
                        }
                    ],
                },
                headers=admin_headers,
            )
            assert create_response.status_code == 200, create_response.text

        with strict_db_session_factory() as session:
            for account_id, waba_id in (
                (
                    "launch-root-receive-query-hidden-conflict-alpha",
                    "waba-launch-root-receive-query-hidden-conflict-alpha",
                ),
                (
                    "launch-root-receive-query-hidden-conflict-beta",
                    "waba-launch-root-receive-query-hidden-conflict-beta",
                ),
            ):
                waba_account = session.query(WhatsAppBusinessAccount).filter(
                    WhatsAppBusinessAccount.account_id == account_id,
                    WhatsAppBusinessAccount.waba_id == waba_id,
                ).one()
                waba_account.webhook_subscribed = True
                session.add(
                    WebhookSubscription(
                        account_id=account_id,
                        waba_account_id=waba_account.id,
                        waba_id=waba_id,
                        callback_url=callback_urls[account_id],
                        verify_token=waba_account.verify_token,
                        app_id=None,
                        status="remote_subscribed",
                        subscribed_at=utc_now(),
                    )
                )
                session.add(waba_account)
            session.commit()

        scoped_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers={
                "X-Actor-Id": "readonly-launch-root-receive-query-hidden-conflict-alpha",
                "X-Actor-Role": "readonly",
                "X-Actor-Account-Ids": "launch-root-receive-query-hidden-conflict-alpha",
            },
        )

        assert scoped_response.status_code == 200, scoped_response.text
        checks = {item["key"]: item for item in scoped_response.json()["checks"]}
        signature_routing_check = checks["meta.webhook_root_receive_signature_routing"]

        assert signature_routing_check["status"] == "blocker"
        assert signature_routing_check["metadata"]["conflict_count"] == 1
        assert signature_routing_check["metadata"]["hidden_scope_count"] == 1
        assert "outside the current account visibility" in signature_routing_check["message"]

        conflicts = signature_routing_check["metadata"]["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["callback_target"] == shared_callback_target
        assert conflicts[0]["distinct_app_secret_count"] == 2
        assert conflicts[0]["hidden_scope_count"] == 1
        assert conflicts[0]["scopes"] == [
            {
                "account_id": "launch-root-receive-query-hidden-conflict-alpha",
                "waba_id": "waba-launch-root-receive-query-hidden-conflict-alpha",
            }
        ]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_focuses_summary_and_meta_checks_to_visible_accounts(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-focus",
        "X-Actor-Role": "super_admin",
    }
    ready_actor_headers = {
        "X-Actor-Id": "readonly-launch-focus-ready",
        "X-Actor-Role": "readonly",
        "X-Actor-Account-Ids": "launch-focus-ready-account",
    }
    pending_actor_headers = {
        "X-Actor-Id": "readonly-launch-focus-pending",
        "X-Actor-Role": "readonly",
        "X-Actor-Account-Ids": "launch-focus-pending-account",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())
        _seed_launch_readiness_focus_accounts(strict_client, admin_headers=admin_headers)

        admin_response = strict_client.get("/api/runtime/launch-readiness", headers=admin_headers)
        assert admin_response.status_code == 200
        admin_payload = admin_response.json()
        admin_checks = {item["key"]: item for item in admin_payload["checks"]}
        admin_account_checks = [
            item for item in admin_payload["checks"] if item.get("scope") == "account"
        ]

        assert admin_payload["summary"]["active_account_count"] == 2
        assert admin_payload["summary"]["meta_account_count"] == 2
        assert admin_payload["summary"]["meta_ready_account_count"] == 1
        assert admin_payload["summary"]["scope"] == "system"
        assert admin_payload["summary"]["account_id"] is None
        assert admin_checks["messaging.provider_mode"]["status"] == "pass"
        assert {
            item["account_id"] for item in admin_account_checks if item["key"].startswith("meta.account.")
        } == {
            "launch-focus-ready-account",
            "launch-focus-pending-account",
        }
        assert (
            admin_checks["meta.account.launch-focus-ready-account.waba-launch-focus-ready"]["status"]
            == "pass"
        )
        assert (
            admin_checks["meta.account.launch-focus-pending-account.waba-launch-focus-pending"]["status"]
            == "warning"
        )

        ready_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers=ready_actor_headers,
        )
        assert ready_response.status_code == 200
        ready_payload = ready_response.json()
        ready_checks = {item["key"]: item for item in ready_payload["checks"]}

        assert ready_payload["summary"]["active_account_count"] == 1
        assert ready_payload["summary"]["meta_account_count"] == 1
        assert ready_payload["summary"]["meta_ready_account_count"] == 1
        assert ready_payload["summary"]["scope"] == "system"
        assert ready_payload["summary"]["account_id"] is None
        assert ready_checks["messaging.provider_mode"]["status"] == "pass"
        assert "meta.account.launch-focus-ready-account.waba-launch-focus-ready" in ready_checks
        assert "meta.account.launch-focus-pending-account.waba-launch-focus-pending" not in ready_checks

        pending_response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers=pending_actor_headers,
        )
        assert pending_response.status_code == 200
        pending_payload = pending_response.json()
        pending_checks = {item["key"]: item for item in pending_payload["checks"]}
        pending_account_check = pending_checks[
            "meta.account.launch-focus-pending-account.waba-launch-focus-pending"
        ]

        assert pending_payload["summary"]["active_account_count"] == 1
        assert pending_payload["summary"]["meta_account_count"] == 1
        assert pending_payload["summary"]["meta_ready_account_count"] == 0
        assert pending_payload["summary"]["scope"] == "system"
        assert pending_payload["summary"]["account_id"] is None
        assert pending_checks["messaging.provider_mode"]["status"] == "blocker"
        assert "meta.account.launch-focus-ready-account.waba-launch-focus-ready" not in pending_checks
        assert pending_account_check["status"] == "warning"
        assert pending_account_check["metadata"]["ready_for_webhook_delivery"] is False
        assert pending_account_check["metadata"]["ready_for_outbound_messages"] is True
        assert pending_account_check["metadata"]["ready_for_meta_activation"] is False
        assert pending_account_check["metadata"]["webhook_verification_status"] == "pending"
        assert pending_account_check["metadata"]["blocking_reasons"] == ["webhook_not_ready"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_system_scope_keeps_active_runtime_accounts_without_waba_visible(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-runtime-no-waba-system",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        runtime_only_response = strict_client.post(
            "/api/runtime/accounts",
            json={
                "account_id": "launch-runtime-no-waba-system",
                "display_name": "Launch Runtime No WABA System",
                "provider_type": "whatsapp",
            },
            headers=admin_headers,
        )
        assert runtime_only_response.status_code == 200

        ready_create_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-runtime-ready-system",
                "display_name": "Launch Runtime Ready System",
                "meta_business_portfolio_id": "biz-launch-runtime-ready-system",
                "waba_id": "waba-launch-runtime-ready-system",
                "access_token": "token-launch-runtime-ready-system",
                "verify_token": "verify-launch-runtime-ready-system",
                "app_secret": "secret-launch-runtime-ready-system",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-runtime-ready-system",
                        "display_phone_number": "+1 555 000 6201",
                        "verified_name": "Launch Runtime Ready System",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
            headers=admin_headers,
        )
        assert ready_create_response.status_code == 200

        _mark_meta_account_ready_for_launch_readiness(
            strict_db_session_factory,
            account_id="launch-runtime-ready-system",
            waba_id="waba-launch-runtime-ready-system",
            callback_url="https://example.com/launch-runtime-ready-system/webhook",
        )

        response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers=admin_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["summary"]["active_account_count"] == 2
        assert payload["summary"]["meta_account_count"] == 1
        assert payload["summary"]["meta_ready_account_count"] == 1
        assert payload["summary"]["metadata"]["visible_account_count"] == 2
        assert payload["summary"]["metadata"]["active_accounts_without_waba_count"] == 1
        assert payload["summary"]["metadata"]["active_accounts_without_ready_waba_count"] == 0
        assert payload["summary"]["metadata"]["active_accounts_with_ready_waba_count"] == 1
        assert [
            item["account_id"] for item in payload["summary"]["metadata"]["active_accounts_without_waba"]
        ] == ["launch-runtime-no-waba-system"]
        assert [
            item["account_id"]
            for item in payload["summary"]["metadata"]["active_accounts_with_ready_waba"]
        ] == ["launch-runtime-ready-system"]

        coverage_check = next(
            item for item in payload["checks"] if item["key"] == "meta.account_runtime_coverage"
        )
        assert coverage_check["status"] == "blocker"
        assert [
            item["account_id"]
            for item in coverage_check["metadata"]["active_accounts_without_waba"]
        ] == ["launch-runtime-no-waba-system"]
        assert coverage_check["metadata"]["active_accounts_without_ready_waba"] == []
        assert [
            item["account_id"]
            for item in coverage_check["metadata"]["active_accounts_with_ready_waba"]
        ] == ["launch-runtime-ready-system"]

        runtime_only_checks = [
            item
            for item in payload["checks"]
            if item.get("scope") == "account"
            and item.get("account_id") == "launch-runtime-no-waba-system"
        ]
        assert len(runtime_only_checks) == 1
        runtime_only_check = runtime_only_checks[0]
        assert runtime_only_check["category"] == "meta"
        assert runtime_only_check["status"] == "blocker"
        assert runtime_only_check.get("waba_id") is None
        assert "WABA" in runtime_only_check["message"]
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_account_scope_keeps_runtime_accounts_without_waba_visible(
    strict_client: TestClient,
    strict_db_session_factory: sessionmaker[Session],
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-runtime-no-waba-scope",
        "X-Actor-Role": "super_admin",
    }
    scoped_headers = {
        "X-Actor-Id": "readonly-launch-runtime-no-waba-scope",
        "X-Actor-Role": "readonly",
        "X-Actor-Account-Ids": "launch-runtime-no-waba-scope",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        runtime_only_response = strict_client.post(
            "/api/runtime/accounts",
            json={
                "account_id": "launch-runtime-no-waba-scope",
                "display_name": "Launch Runtime No WABA Scope",
                "provider_type": "whatsapp",
            },
            headers=admin_headers,
        )
        assert runtime_only_response.status_code == 200

        hidden_ready_response = strict_client.post(
            "/api/meta/accounts/manual",
            json={
                "account_id": "launch-runtime-hidden-ready-scope",
                "display_name": "Launch Runtime Hidden Ready Scope",
                "meta_business_portfolio_id": "biz-launch-runtime-hidden-ready-scope",
                "waba_id": "waba-launch-runtime-hidden-ready-scope",
                "access_token": "token-launch-runtime-hidden-ready-scope",
                "verify_token": "verify-launch-runtime-hidden-ready-scope",
                "app_secret": "secret-launch-runtime-hidden-ready-scope",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-launch-runtime-hidden-ready-scope",
                        "display_phone_number": "+1 555 000 6202",
                        "verified_name": "Launch Runtime Hidden Ready Scope",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                    }
                ],
            },
            headers=admin_headers,
        )
        assert hidden_ready_response.status_code == 200

        _mark_meta_account_ready_for_launch_readiness(
            strict_db_session_factory,
            account_id="launch-runtime-hidden-ready-scope",
            waba_id="waba-launch-runtime-hidden-ready-scope",
            callback_url="https://example.com/launch-runtime-hidden-ready-scope/webhook",
        )

        response = strict_client.get(
            "/api/runtime/launch-readiness",
            headers=scoped_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["summary"]["active_account_count"] == 1
        assert payload["summary"]["meta_account_count"] == 0
        assert payload["summary"]["meta_ready_account_count"] == 0
        assert payload["summary"]["metadata"]["visible_account_count"] == 1
        assert payload["summary"]["metadata"]["active_accounts_without_waba_count"] == 1
        assert payload["summary"]["metadata"]["active_accounts_without_ready_waba_count"] == 0
        assert payload["summary"]["metadata"]["active_accounts_with_ready_waba_count"] == 0
        assert [
            item["account_id"] for item in payload["summary"]["metadata"]["active_accounts_without_waba"]
        ] == ["launch-runtime-no-waba-scope"]
        assert payload["summary"]["metadata"]["active_accounts_without_ready_waba"] == []
        assert payload["summary"]["metadata"]["active_accounts_with_ready_waba"] == []

        coverage_check = next(
            item for item in payload["checks"] if item["key"] == "meta.account_runtime_coverage"
        )
        assert coverage_check["status"] == "blocker"
        assert [
            item["account_id"]
            for item in coverage_check["metadata"]["active_accounts_without_waba"]
        ] == ["launch-runtime-no-waba-scope"]
        assert coverage_check["metadata"]["active_accounts_without_ready_waba"] == []
        assert coverage_check["metadata"]["active_accounts_with_ready_waba"] == []

        runtime_only_checks = [
            item
            for item in payload["checks"]
            if item.get("scope") == "account"
            and item.get("account_id") == "launch-runtime-no-waba-scope"
        ]
        assert len(runtime_only_checks) == 1
        runtime_only_check = runtime_only_checks[0]
        assert runtime_only_check["category"] == "meta"
        assert runtime_only_check["status"] == "blocker"
        assert runtime_only_check.get("waba_id") is None
        assert "WABA" in runtime_only_check["message"]
        assert "launch-runtime-hidden-ready-scope" not in str(payload["summary"]["metadata"])
        assert "launch-runtime-hidden-ready-scope" not in str(coverage_check["metadata"])
        assert not any(
            item.get("account_id") == "launch-runtime-hidden-ready-scope"
            for item in payload["checks"]
        )
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_account_focus_returns_account_summary_and_scoped_checks(
    strict_client: TestClient,
    override_meta_management_provider,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-account-focus",
        "X-Actor-Role": "super_admin",
    }
    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "MESSAGING_PROVIDER": os.environ.get("MESSAGING_PROVIDER"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }

    try:
        os.environ["APP_ENV"] = "staging"
        os.environ["MESSAGING_PROVIDER"] = "whatsapp"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        from app.core.settings import get_settings

        get_settings.cache_clear()
        override_meta_management_provider(strict_client, StubMetaManagementProvider())
        _seed_launch_readiness_focus_accounts(strict_client, admin_headers=admin_headers)

        focused_response = strict_client.get(
            "/api/runtime/launch-readiness",
            params={"account_id": "launch-focus-ready-account"},
            headers=admin_headers,
        )

        assert focused_response.status_code == 200
        payload = focused_response.json()
        checks = {item["key"]: item for item in payload["checks"]}
        meta_account_checks = [
            item for item in payload["checks"] if item["key"].startswith("meta.account.")
        ]

        assert payload["summary"]["scope"] == "account"
        assert payload["summary"]["account_id"] == "launch-focus-ready-account"
        assert payload["summary"]["active_account_count"] == 1
        assert payload["summary"]["meta_account_count"] == 1
        assert payload["summary"]["meta_ready_account_count"] == 1
        assert "meta.account.launch-focus-ready-account.waba-launch-focus-ready" in checks
        assert "meta.account.launch-focus-pending-account.waba-launch-focus-pending" not in checks
        assert {item["account_id"] for item in meta_account_checks} == {"launch-focus-ready-account"}
        assert checks["meta.account.launch-focus-ready-account.waba-launch-focus-ready"]["status"] == "pass"
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_launch_readiness_account_focus_rejects_inaccessible_account(
    strict_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-launch-account-focus-forbidden",
        "X-Actor-Role": "super_admin",
    }
    scoped_headers = {
        "X-Actor-Id": "operator-launch-account-focus-forbidden",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "launch-scope-allowed-account",
    }

    for account_id in ("launch-scope-allowed-account", "launch-scope-denied-account"):
        create_response = strict_client.post(
            "/api/runtime/accounts",
            json={
                "account_id": account_id,
                "display_name": account_id,
                "provider_type": "mock",
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200

    response = strict_client.get(
        "/api/runtime/launch-readiness",
        params={"account_id": "launch-scope-denied-account"},
        headers=scoped_headers,
    )

    assert response.status_code == 403
    assert "launch-scope-denied-account" in response.json()["detail"]


def test_launch_readiness_account_focus_returns_404_for_missing_account(
    strict_client: TestClient,
) -> None:
    response = strict_client.get(
        "/api/runtime/launch-readiness",
        params={"account_id": "launch-focus-missing-account"},
        headers={
            "X-Actor-Id": "admin-launch-account-focus-missing",
            "X-Actor-Role": "super_admin",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account 'launch-focus-missing-account' was not found."


def test_runtime_account_list_filters_requested_account_and_enforces_scope(
    strict_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-runtime-account-filter",
        "X-Actor-Role": "super_admin",
    }
    scoped_headers = {
        "X-Actor-Id": "operator-runtime-account-filter",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "runtime-filter-account-a",
    }

    for account_id, display_name in (
        ("runtime-filter-account-a", "Runtime Filter Account A"),
        ("runtime-filter-account-b", "Runtime Filter Account B"),
    ):
        create_response = strict_client.post(
            "/api/runtime/accounts",
            json={
                "account_id": account_id,
                "display_name": display_name,
                "provider_type": "mock",
            },
            headers=admin_headers,
        )
        assert create_response.status_code == 200

    admin_filtered_response = strict_client.get(
        "/api/runtime/accounts",
        params={"account_id": "runtime-filter-account-b"},
        headers=admin_headers,
    )
    assert admin_filtered_response.status_code == 200
    assert [item["account_id"] for item in admin_filtered_response.json()] == [
        "runtime-filter-account-b"
    ]

    scoped_filtered_response = strict_client.get(
        "/api/runtime/accounts",
        params={"account_id": "runtime-filter-account-a"},
        headers=scoped_headers,
    )
    assert scoped_filtered_response.status_code == 200
    assert [item["account_id"] for item in scoped_filtered_response.json()] == [
        "runtime-filter-account-a"
    ]

    denied_response = strict_client.get(
        "/api/runtime/accounts",
        params={"account_id": "runtime-filter-account-b"},
        headers=scoped_headers,
    )
    assert denied_response.status_code == 403
    assert "runtime-filter-account-b" in denied_response.json()["detail"]


def test_runtime_account_list_returns_404_for_missing_account_filter(
    strict_client: TestClient,
) -> None:
    response = strict_client.get(
        "/api/runtime/accounts",
        params={"account_id": "runtime-filter-missing-account"},
        headers={
            "X-Actor-Id": "admin-runtime-account-filter-missing",
            "X-Actor-Role": "super_admin",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account 'runtime-filter-missing-account' was not found."

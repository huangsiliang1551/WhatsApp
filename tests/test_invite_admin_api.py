from collections.abc import Generator
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import Account, AppUser, InviteRecord
from app.main import app


@pytest.fixture
def strict_client(db_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
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
    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = db_session_factory()
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


def _issue_super_admin_token() -> str:
    settings = get_settings()
    return _encode_agent_jwt(
        {
            "sub": "super-admin-1",
            "agency_id": "system",
            "user_type": "super_admin",
            "role": "super_admin",
            "username": "root",
            "agent_key": "super-admin-1",
        },
        settings.admin_jwt_secret,
        settings.admin_access_token_ttl_minutes,
    )


def test_invite_relations_endpoint_returns_public_user_ids(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        session.add(Account(account_id="acct-invite-1", display_name="Invite Account", provider_type="mock"))
        session.add_all(
            [
                AppUser(
                    id="user-inviter",
                    account_id="acct-invite-1",
                    public_user_id="pub-inviter",
                    registration_site_id=None,
                    language_code="zh-CN",
                    is_anonymous=False,
                    lifecycle_status="active",
                ),
                AppUser(
                    id="user-invitee",
                    account_id="acct-invite-1",
                    public_user_id="pub-invitee",
                    registration_site_id=None,
                    language_code="en",
                    is_anonymous=False,
                    lifecycle_status="active",
                ),
            ]
        )
        session.add(
            InviteRecord(
                id="invite-record-1",
                account_id="acct-invite-1",
                inviter_user_id="user-inviter",
                invitee_user_id="user-invitee",
                invite_type="register",
                reward_amount=5,
                is_rewarded=True,
                invitee_ip="10.0.0.1",
                invitee_device_id="device-1",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/invites/relations",
        headers={"Authorization": f"Bearer {_issue_super_admin_token()}"},
        params={"account_id": "acct-invite-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"] == [
        {
            "id": "invite-record-1",
            "account_id": "acct-invite-1",
            "inviter_user_id": "user-inviter",
            "inviter_public_user_id": "pub-inviter",
            "invitee_user_id": "user-invitee",
            "invitee_public_user_id": "pub-invitee",
            "invite_type": "register",
            "reward_amount": "5.00",
            "is_rewarded": True,
            "reward_fund_type": "task_balance",
            "reward_transaction_type": "invite_register",
            "invitee_ip": "10.0.0.1",
            "invitee_device_id": "device-1",
            "created_at": payload["items"][0]["created_at"],
        }
    ]


def test_invite_rewards_endpoint_supports_reward_status_filter(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        session.add(Account(account_id="acct-invite-2", display_name="Invite Account 2", provider_type="mock"))
        session.add_all(
            [
                AppUser(
                    id="user-inviter-2",
                    account_id="acct-invite-2",
                    public_user_id="pub-inviter-2",
                    registration_site_id=None,
                    language_code="zh-CN",
                    is_anonymous=False,
                    lifecycle_status="active",
                ),
                AppUser(
                    id="user-invitee-2",
                    account_id="acct-invite-2",
                    public_user_id="pub-invitee-2",
                    registration_site_id=None,
                    language_code="en",
                    is_anonymous=False,
                    lifecycle_status="active",
                ),
            ]
        )
        session.add_all(
            [
                InviteRecord(
                    id="invite-record-2a",
                    account_id="acct-invite-2",
                    inviter_user_id="user-inviter-2",
                    invitee_user_id="user-invitee-2",
                    invite_type="register",
                    reward_amount=2,
                    is_rewarded=True,
                ),
                InviteRecord(
                    id="invite-record-2b",
                    account_id="acct-invite-2",
                    inviter_user_id="user-inviter-2",
                    invitee_user_id="user-invitee-2",
                    invite_type="recharge",
                    reward_amount=3,
                    is_rewarded=False,
                ),
            ]
        )
        session.commit()

    response = strict_client.get(
        "/api/invites/rewards",
        headers={"Authorization": f"Bearer {_issue_super_admin_token()}"},
        params={"account_id": "acct-invite-2", "is_rewarded": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == ["invite-record-2a"]
    assert payload["items"][0]["reward_transaction_type"] == "invite_register"

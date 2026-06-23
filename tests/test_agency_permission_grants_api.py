from collections.abc import Generator
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import Account, Agency, AgencyMember, AgencyPermissionGrant, Agent, H5Site, RolePermission
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


def _issue_agent_token(*, user_id: str, agency_id: str, user_type: str, role: str) -> str:
    settings = get_settings()
    return _encode_agent_jwt(
        {
            "sub": user_id,
            "agency_id": agency_id,
            "user_type": user_type,
            "role": role,
            "username": user_id,
            "agent_key": user_id,
        },
        settings.admin_jwt_secret,
        settings.admin_access_token_ttl_minutes,
    )


def _seed_agency_scope(session: Session, *, agency_id: str) -> dict[str, str]:
    account_id = f"{agency_id}-account"
    session.add(
        Account(
            account_id=account_id,
            display_name=f"{agency_id} account",
            provider_type="mock",
        )
    )
    session.add(
        Agency(
            id=agency_id,
            name=f"{agency_id} agency",
            username=f"{agency_id}-owner",
            password_hash="placeholder",
        )
    )
    session.add(
        H5Site(
            id=f"{agency_id}-site",
            account_id=account_id,
            site_key=f"{agency_id}-site-key",
            domain=f"{agency_id}.example.com",
            brand_name=f"{agency_id} brand",
            agency_id=agency_id,
        )
    )
    session.flush()
    return {"account_id": account_id}


def test_super_admin_can_get_empty_agency_permission_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-grants-empty"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.get(
        f"/api/agents/{agency_id}/granted-permissions",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-grants-read', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "agency_id": agency_id,
        "permissions": [],
    }


def test_super_admin_can_update_agency_permission_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-grants-update"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.put(
        f"/api/agents/{agency_id}/granted-permissions",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-grants-write', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
        json={
            "permissions": ["tickets.reply", "tickets.view", "tickets.reply"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "agency_id": agency_id,
        "permissions": ["tickets.reply", "tickets.view"],
    }

    read_response = strict_client.get(
        f"/api/agents/{agency_id}/granted-permissions",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-grants-write', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
    )
    assert read_response.status_code == 200
    assert read_response.json()["permissions"] == ["tickets.reply", "tickets.view"]


def test_list_agencies_includes_member_role_and_permission_counts(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-list-counts"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="agency-list-counts-role-agent",
                agency_id=agency_id,
                role_name="agent",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="agency-list-counts-role-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view", "tickets.reply"],
                created_by="seed",
            )
        )
        session.add(
            AgencyPermissionGrant(
                id="agency-list-counts-grants",
                agency_id=agency_id,
                permissions=["tickets.view", "tickets.reply", "members.view"],
                created_by="seed",
            )
        )
        session.add(
            Agent(
                id="agency-list-counts-member-agent",
                account_id=seeded["account_id"],
                agent_key="agency-counts-member",
                display_name="Agency Counts Member",
                user_type="agent_member",
                agency_id=agency_id,
                is_active=True,
            )
        )
        session.add(
            AgencyMember(
                id="agency-list-counts-member",
                agency_id=agency_id,
                user_id="agency-list-counts-member-agent",
                role="agent",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/agents",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-agency-list', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
    )

    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == agency_id)
    assert payload["member_count"] == 1
    assert payload["role_count"] == 2
    assert payload["granted_permission_count"] == 3


def test_list_members_includes_display_name_username_and_status(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-member-list"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id="agency-member-list-agent",
                account_id=seeded["account_id"],
                agent_key="member-login",
                display_name="成员张三",
                user_type="agent_member",
                agency_id=agency_id,
                is_active=False,
                status="offline",
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-list-binding",
                agency_id=agency_id,
                user_id="agency-member-list-agent",
                role="support",
            )
        )
        session.commit()

    response = strict_client.get(
        f"/api/agents/{agency_id}/members",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-member-list', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "agency-member-list-binding",
            "agency_id": agency_id,
            "user_id": "agency-member-list-agent",
            "username": "member-login",
            "display_name": "成员张三",
            "status": "inactive",
            "role": "support",
            "created_at": response.json()[0]["created_at"],
        }
    ]


def test_unknown_permission_codes_are_rejected(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-grants-unknown"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.put(
        f"/api/agents/{agency_id}/granted-permissions",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-grants-unknown', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
        json={
            "permissions": ["tickets.view", "not.real.permission"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "message": "Unknown permission codes in agency granted permissions.",
        "unknown_permissions": ["not.real.permission"],
    }


def test_non_super_admin_cannot_update_foreign_agency_permission_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    own_agency_id = "agency-grants-own"
    foreign_agency_id = "agency-grants-foreign"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=own_agency_id)
        _seed_agency_scope(session, agency_id=foreign_agency_id)
        session.add(
            RolePermission(
                id="role-own-agency-permission-admin",
                agency_id=own_agency_id,
                role_name="custom_permission_admin",
                permissions=["roles.view", "roles.edit_perms"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.put(
        f"/api/agents/{foreign_agency_id}/granted-permissions",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='agent-own-agency', agency_id=own_agency_id, user_type='agent', role='agent')}"
            ),
        },
        json={
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this agency's permissions."


def test_add_member_rejects_nonexistent_agency_role(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-member-role-missing"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.post(
        f"/api/agents/{agency_id}/members",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-add-member', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
        json={
            "username": "newmemberrolemissing",
            "password": "Password123",
            "role": "custom_missing_role",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Role 'custom_missing_role' is not configured for agency 'agency-member-role-missing'."


def test_add_member_succeeds_without_notification_attribute_error(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-member-create-ok"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(64) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        session.add(
            RolePermission(
                id="role-agency-member-create-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        f"/api/agents/{agency_id}/members",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-create-member-ok', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
        json={
            "username": "newmemberok",
            "password": "Password123",
            "role": "support",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agency_id"] == agency_id
    assert payload["role"] == "support"
    assert payload["user_id"]

    with db_session_factory() as session:
        member = session.get(AgencyMember, payload["id"])
        assert member is not None
        assert member.agency_id == agency_id
        agent = session.get(Agent, payload["user_id"])
        assert agent is not None
        assert agent.agency_id == agency_id
        assert agent.agent_key == "newmemberok"


def test_update_member_role_rejects_nonexistent_agency_role(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-member-role-update-missing"
    member_id = "agency-member-role-update-missing-member"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-existing-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            Agent(
                id=member_id,
                account_id=seeded["account_id"],
                agent_key="member-role-update",
                display_name="Member Role Update",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-role-update",
                agency_id=agency_id,
                user_id=member_id,
                role="support",
            )
        )
        session.commit()

    response = strict_client.patch(
        f"/api/agents/{agency_id}/members/agency-member-role-update",
        headers={
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id='super-admin-update-member-role', agency_id='system', user_type='super_admin', role='super_admin')}"
            ),
        },
        json={
            "role": "custom_missing_role",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Role 'custom_missing_role' is not configured for agency 'agency-member-role-update-missing'."

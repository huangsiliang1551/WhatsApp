from collections.abc import Generator
import os

from fastapi.testclient import TestClient
import pytest
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


def test_agent_member_custom_role_permissions_are_exposed_as_canonical_codes(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-member"
    member_id = "member-custom-role"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id=member_id,
                account_id=f"{agency_id}-account",
                agent_key="member-custom-role",
                display_name="Member Custom Role",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-custom-role",
                agency_id=agency_id,
                user_id=member_id,
                role="custom_support",
            )
        )
        session.add(
            RolePermission(
                id="role-perm-custom-support",
                agency_id=agency_id,
                role_name="custom_support",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_support')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "custom_support"
    assert payload["permissions"] == sorted(
        [
            "profile.change_password",
            "profile.edit",
            "profile.view",
            "tags.view",
        ]
    )
    assert payload["menus"] == ["profile", "tags"]


def test_agent_permissions_config_can_omit_ungranted_canonical_codes(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-agent"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-perm-agent-restricted",
                agency_id=agency_id,
                role_name="agent",
                permissions=["profile.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='agency-owner', agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["permissions"] == [
        "profile.change_password",
        "profile.edit",
        "profile.view",
    ]
    assert payload["menus"] == ["profile"]


def test_auth_permissions_endpoint_returns_only_canonical_permission_codes(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-canonical"
    agent_id = "agent-canonical-reader"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-perm-agent-canonical",
                agency_id=agency_id,
                role_name="agent",
                permissions=["tags.view", "member_access", "access_control"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=agent_id, agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["permissions"] == sorted(
        [
            "profile.change_password",
            "profile.edit",
            "profile.view",
            "tags.view",
        ]
    )
    assert payload["menus"] == ["profile", "tags"]
    assert "member_access" not in payload["permissions"]
    assert "access_control" not in payload["permissions"]


def test_auth_permissions_endpoint_maps_roles_permissions_to_agents_menu(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-roles-menu"
    agent_id = "agent-roles-menu-reader"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-perm-agent-roles-menu",
                agency_id=agency_id,
                role_name="agent",
                permissions=["roles.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=agent_id, agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["permissions"] == sorted(
        [
            "profile.change_password",
            "profile.edit",
            "profile.view",
            "roles.view",
        ]
    )
    assert payload["menus"] == ["agents", "profile"]


def test_auth_permissions_endpoint_maps_manager_role_to_standard_manager_template(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-manager-template"
    member_id = "member-manager-template"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id=member_id,
                account_id=f"{agency_id}-account",
                agent_key="member-manager-template",
                display_name="Manager Template Member",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-manager-template",
                agency_id=agency_id,
                user_id=member_id,
                role="manager",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='manager')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "h5_templates.view" not in payload["permissions"]
    assert "h5_templates" not in payload["menus"]


def test_auth_permissions_endpoint_rejects_agent_member_without_membership_for_token_agency(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-membership-missing"
    other_agency_id = "agency-perm-membership-other"
    member_id = "member-membership-missing"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id=other_agency_id)
        session.add(
            Agent(
                id=member_id,
                account_id=f"{agency_id}-account",
                agent_key="member-membership-missing",
                display_name="Membership Missing Member",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-membership-other",
                agency_id=other_agency_id,
                user_id=member_id,
                role="manager",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='support')}",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Agency membership not found for this token."


def test_auth_permissions_endpoint_uses_db_membership_role_over_jwt_role_claim(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-role-claim-guard"
    member_id = "member-role-claim-guard"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id=member_id,
                account_id=f"{agency_id}-account",
                agent_key="member-role-claim-guard",
                display_name="Role Claim Guard",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-role-claim-guard",
                agency_id=agency_id,
                user_id=member_id,
                role="support",
            )
        )
        session.add(
            RolePermission(
                id="role-support-role-claim-guard",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-manager-role-claim-guard",
                agency_id=agency_id,
                role_name="manager",
                permissions=["roles.create", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='manager')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "support"
    assert payload["permissions"] == sorted(
        [
            "profile.change_password",
            "profile.edit",
            "profile.view",
            "tickets.view",
        ]
    )
    assert "roles.create" not in payload["permissions"]


def test_agency_granted_permissions_do_not_leak_into_effective_member_permissions(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-grant-bridge"
    member_id = "member-grant-bridge"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id=member_id,
                account_id=f"{agency_id}-account",
                agent_key="member-grant-bridge",
                display_name="Grant Bridge Member",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-grant-bridge",
                agency_id=agency_id,
                user_id=member_id,
                role="custom_support",
            )
        )
        session.add(
            AgencyPermissionGrant(
                id="agency-permission-grant-bridge",
                agency_id=agency_id,
                permissions=["tags.view", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-perm-grant-bridge-support",
                agency_id=agency_id,
                role_name="custom_support",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_support')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["permissions"] == sorted(
        [
            "profile.change_password",
            "profile.edit",
            "profile.view",
            "tags.view",
        ]
    )
    assert "tickets.view" not in payload["permissions"]


def test_auth_permissions_endpoint_falls_back_to_builtin_agent_permissions(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-agent-fallback"
    agent_id = "agent-fallback-reader"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=agent_id, agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["permissions"]) > 3
    assert "sites" in payload["menus"]


def test_update_agency_permissions_rejects_unknown_permission_codes(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-unknown-update"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-1', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "role_name": "agent",
            "permissions": ["tags.view", "member_access"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "message": f"Unknown permission codes in agency.{agency_id}.agent.",
        "unknown_permissions": ["member_access"],
    }

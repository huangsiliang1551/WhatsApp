from collections.abc import Generator
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import Account, Agency, AgencyMember, Agent, AuditLog, H5Site, RolePermission
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


def test_agent_can_delete_unused_custom_role_and_audit_it(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-role-delete-ok"
    role_id = "role-custom-delete-ok"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-agent-delete-access",
                agency_id=agency_id,
                role_name="agent",
                permissions=["roles.delete", "tags.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id=role_id,
                agency_id=agency_id,
                role_name="custom_tier2",
                permissions=["tags.view", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.delete(
        f"/api/permissions/agency/{agency_id}/roles/custom_tier2",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='agency-owner-1', agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "action": "deleted",
        "agency_id": agency_id,
        "role_name": "custom_tier2",
    }

    with db_session_factory() as session:
        deleted_role = session.get(RolePermission, role_id)
        assert deleted_role is None

        audit_logs = session.execute(
            select(AuditLog).where(AuditLog.action == "permissions.deleted")
        ).scalars().all()
        assert len(audit_logs) == 1
        assert audit_logs[0].actor_type == "agent"
        assert audit_logs[0].actor_id == "agency-owner-1"
        assert audit_logs[0].target_type == "agency_role"
        assert audit_logs[0].target_id == f"{agency_id}/custom_tier2"
        assert audit_logs[0].payload == {
            "agency_id": agency_id,
            "role_name": "custom_tier2",
            "permission_count": 2,
        }


def test_delete_custom_role_rejects_assigned_roles(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-role-delete-in-use"
    member_id = "agent-member-delete-in-use"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-agent-delete-access-in-use",
                agency_id=agency_id,
                role_name="agent",
                permissions=["roles.delete", "tags.view"],
                created_by="seed",
            )
        )
        session.add(
            Agent(
                id=member_id,
                account_id=seeded["account_id"],
                agent_key=member_id,
                display_name="Assigned Member",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-delete-in-use",
                agency_id=agency_id,
                user_id=member_id,
                role="custom_tier2",
            )
        )
        session.add(
            RolePermission(
                id="role-custom-delete-in-use",
                agency_id=agency_id,
                role_name="custom_tier2",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.delete(
        f"/api/permissions/agency/{agency_id}/roles/custom_tier2",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='agency-owner-1', agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Role 'custom_tier2' is assigned to agency members and cannot be deleted."


def test_delete_role_rejects_builtin_role_configs(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-role-delete-builtin"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            Agent(
                id="member-role-delete-builtin",
                account_id=seeded["account_id"],
                agent_key="member-role-delete-builtin",
                display_name="Role Delete Member",
                user_type="agent_member",
                agency_id=agency_id,
            )
        )
        session.add(
            AgencyMember(
                id="agency-member-role-delete-builtin",
                agency_id=agency_id,
                user_id="member-role-delete-builtin",
                role="custom_role_admin",
            )
        )
        session.add(
            RolePermission(
                id="role-custom-role-admin-delete-builtin",
                agency_id=agency_id,
                role_name="custom_role_admin",
                permissions=["roles.delete", "tags.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-agent-delete-builtin",
                agency_id=agency_id,
                role_name="agent",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.delete(
        f"/api/permissions/agency/{agency_id}/roles/agent",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='member-role-delete-builtin', agency_id=agency_id, user_type='agent_member', role='custom_role_admin')}",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only custom roles can be deleted from the permission center."


def test_delete_role_rejects_cross_agency_agent_access(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-role-delete-foreign"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id="another-agency")
        session.add(
            RolePermission(
                id="role-agent-delete-access-another",
                agency_id="another-agency",
                role_name="agent",
                permissions=["roles.delete", "tags.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-custom-delete-foreign",
                agency_id=agency_id,
                role_name="custom_tier2",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.delete(
        f"/api/permissions/agency/{agency_id}/roles/custom_tier2",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='agency-owner-2', agency_id='another-agency', user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this agency's permissions."

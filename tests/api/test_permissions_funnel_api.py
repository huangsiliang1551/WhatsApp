from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import os

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import (
    Account,
    Agency,
    AgencyMember,
    Agent,
    AppUser,
    Conversation,
    ConversationAssignment,
    CustomerOwnershipAssignment,
    DataScopeGrant,
    H5Site,
    PermissionGrant,
    RolePermission,
)
from app.main import app


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


def _seed_scope(session: Session, *, agency_id: str = "agency-w3-api") -> dict[str, str]:
    account_id = f"{agency_id}-account"
    site_id = f"{agency_id}-site"
    session.add(Account(account_id=account_id, display_name=agency_id, provider_type="mock"))
    session.add(
        Agency(
            id=agency_id,
            name=agency_id,
            username=f"{agency_id}-owner",
            password_hash="placeholder",
        )
    )
    session.add(
        H5Site(
            id=site_id,
            account_id=account_id,
            site_key=f"{agency_id}-site-key",
            domain=f"{agency_id}.example.com",
            brand_name=agency_id,
            agency_id=agency_id,
        )
    )
    session.flush()
    return {"account_id": account_id, "agency_id": agency_id, "site_id": site_id}


def _seed_member(
    session: Session,
    *,
    agency_id: str,
    account_id: str,
    member_id: str,
    role_name: str,
    permissions: list[str],
) -> None:
    session.add(
        Agent(
            id=member_id,
            account_id=account_id,
            agent_key=member_id,
            display_name=member_id,
            user_type="agent_member",
            agency_id=agency_id,
        )
    )
    session.add(
        AgencyMember(
            id=f"{member_id}-agency-member",
            agency_id=agency_id,
            user_id=member_id,
            role=role_name,
        )
    )
    session.add(
        RolePermission(
            id=f"role-{role_name}-{member_id}",
            agency_id=agency_id,
            role_name=role_name,
            permissions=permissions,
            created_by="seed",
        )
    )


def _seed_customer(session: Session, *, account_id: str, site_id: str, public_user_id: str) -> AppUser:
    customer = AppUser(
        account_id=account_id,
        public_user_id=public_user_id,
        registration_site_id=site_id,
        display_name=public_user_id,
        lifecycle_status="active",
    )
    session.add(customer)
    session.flush()
    return customer


def _auth_headers(*, user_id: str, agency_id: str, role: str) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {_issue_agent_token(user_id=user_id, agency_id=agency_id, user_type='agent_member', role=role)}"
        )
    }


@contextmanager
def _build_strict_client(
    db_session_factory: sessionmaker[Session],
) -> Generator[TestClient, None, None]:
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
            session.commit()
        except Exception:
            session.rollback()
            raise
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


def test_effective_access_endpoint_returns_permission_and_scope_summary(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session)
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-scope-reader",
            role_name="scope_reader",
            permissions=["data_scope.view"],
        )
        session.add(
            PermissionGrant(
                grantor_subject_type="super_admin",
                grantor_subject_id="root",
                grantee_subject_type="actor",
                grantee_subject_id="member-scope-reader",
                permission_code="handover.manage",
                can_delegate=True,
                created_by="root",
            )
        )
        session.add(
            DataScopeGrant(
                subject_type="actor",
                subject_id="member-scope-reader",
                scope_type="site",
                scope_id=scope["site_id"],
                granted_by_subject_type="super_admin",
                granted_by_subject_id="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/permissions/effective-access",
            headers=_auth_headers(
                user_id="member-scope-reader",
                agency_id=scope["agency_id"],
                role="scope_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor_id"] == "member-scope-reader"
    assert "data_scope.view" in payload["effective_permissions"]
    assert "handover.manage" in payload["effective_permissions"]
    assert payload["delegatable_permissions"] == ["handover.manage"]
    assert payload["data_scope"]["site_ids"] == [scope["site_id"]]
    assert payload["data_scope"]["staff_ids"] == ["member-scope-reader"]


def test_permission_grant_endpoint_rejects_non_delegatable_permissions(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-grant")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-grantor",
            role_name="grant_admin",
            permissions=["roles.edit_perms"],
        )
        session.add(
            PermissionGrant(
                grantor_subject_type="super_admin",
                grantor_subject_id="root",
                grantee_subject_type="actor",
                grantee_subject_id="member-grantor",
                permission_code="data_scope.manage",
                can_delegate=True,
                created_by="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/permissions/grants",
            headers=_auth_headers(
                user_id="member-grantor",
                agency_id=scope["agency_id"],
                role="grant_admin",
            ),
            json={
                "grantee_subject_type": "actor",
                "grantee_subject_id": "target-member",
                "permission_code": "handover.manage",
                "can_delegate": False,
                "scope_type": "inherit",
            },
        )

    assert response.status_code == 403
    assert "cannot delegate" in response.json()["detail"]


def test_data_scope_grant_endpoint_persists_scope_grant(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-scope-grant")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-scope-admin",
            role_name="scope_admin",
            permissions=["data_scope.manage"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/permissions/data-scopes",
            headers=_auth_headers(
                user_id="member-scope-admin",
                agency_id=scope["agency_id"],
                role="scope_admin",
            ),
            json={
                "subject_type": "actor",
                "subject_id": "member-scope-admin",
                "scope_type": "site",
                "scope_id": scope["site_id"],
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["scope_type"] == "site"
    assert payload["scope_id"] == scope["site_id"]

    with db_session_factory() as session:
        persisted = session.scalar(
            select(DataScopeGrant).where(DataScopeGrant.subject_id == "member-scope-admin")
        )
        assert persisted is not None
        assert persisted.scope_id == scope["site_id"]


def test_batch_permission_grant_endpoint_persists_multiple_grants(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-batch-grant")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-batch-grant",
            role_name="grant_admin",
            permissions=["roles.edit_perms"],
        )
        session.add(
            PermissionGrant(
                grantor_subject_type="super_admin",
                grantor_subject_id="root",
                grantee_subject_type="actor",
                grantee_subject_id="member-batch-grant",
                permission_code="handover.manage",
                can_delegate=True,
                created_by="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/permissions/grants/batch",
            headers=_auth_headers(
                user_id="member-batch-grant",
                agency_id=scope["agency_id"],
                role="grant_admin",
            ),
            json={
                "items": [
                    {
                        "grantee_subject_type": "actor",
                        "grantee_subject_id": "target-member-1",
                        "permission_code": "handover.manage",
                        "can_delegate": False,
                        "scope_type": "inherit",
                    },
                    {
                        "grantee_subject_type": "actor",
                        "grantee_subject_id": "target-member-2",
                        "permission_code": "handover.manage",
                        "can_delegate": False,
                        "scope_type": "inherit",
                    },
                ]
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_count"] == 2
    assert len(payload["items"]) == 2
    with db_session_factory() as session:
        persisted = session.scalars(
            select(PermissionGrant).where(
                PermissionGrant.grantee_subject_id.in_(["target-member-1", "target-member-2"])
            )
        ).all()
        assert len(persisted) == 2


def test_batch_data_scope_grant_endpoint_persists_multiple_scopes(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-batch-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-batch-scope",
            role_name="scope_admin",
            permissions=["data_scope.manage"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/permissions/data-scopes/batch",
            headers=_auth_headers(
                user_id="member-batch-scope",
                agency_id=scope["agency_id"],
                role="scope_admin",
            ),
            json={
                "items": [
                    {
                        "subject_type": "actor",
                        "subject_id": "target-member-1",
                        "scope_type": "site",
                        "scope_id": scope["site_id"],
                    },
                    {
                        "subject_type": "actor",
                        "subject_id": "target-member-2",
                        "scope_type": "account",
                        "scope_id": scope["account_id"],
                    },
                ]
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_count"] == 2
    assert len(payload["items"]) == 2
    with db_session_factory() as session:
        persisted = session.scalars(
            select(DataScopeGrant).where(
                DataScopeGrant.subject_id.in_(["target-member-1", "target-member-2"])
            )
        ).all()
        assert len(persisted) == 2


def test_conversation_handover_endpoint_keeps_customer_ownership_unchanged(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-handover")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-handover-admin",
            role_name="handover_admin",
            permissions=["handover.manage"],
        )
        customer = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="customer-handover",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=customer.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-owner",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add(
            Conversation(
                account_id=scope["account_id"],
                external_conversation_id="conv-api-handover",
                customer_id=customer.id,
                status="open",
            )
        )
        session.commit()

    with db_session_factory() as session:
        conversation = session.scalar(select(Conversation).where(Conversation.external_conversation_id == "conv-api-handover"))
        assert conversation is not None
        conversation_id = conversation.id

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/permissions/conversation-handover",
            headers=_auth_headers(
                user_id="member-handover-admin",
                agency_id=scope["agency_id"],
                role="handover_admin",
            ),
            json={
                "conversation_id": conversation_id,
                "assigned_staff_id": "member-temp-handler",
                "team_id": "team-1",
                "supervisor_id": "sup-1",
                "reason": "temporary escalation",
                "is_temporary": True,
            },
        )

    assert response.status_code == 201
    with db_session_factory() as session:
        ownership = session.scalar(
            select(CustomerOwnershipAssignment).where(
                CustomerOwnershipAssignment.customer_id == session.scalar(
                    select(Conversation.customer_id).where(Conversation.id == conversation_id)
                ),
                CustomerOwnershipAssignment.status == "active",
            )
        )
        assignment = session.scalar(
            select(ConversationAssignment).where(
                ConversationAssignment.conversation_id == conversation_id,
                ConversationAssignment.status == "active",
            )
        )
        assert ownership is not None
        assert ownership.owner_staff_id == "member-owner"
        assert assignment is not None
        assert assignment.assigned_staff_id == "member-temp-handler"
        assert assignment.is_temporary is True


def test_permission_grant_revoke_endpoint_marks_grant_revoked(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-revoke-grant")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-revoke-grant",
            role_name="grant_admin",
            permissions=["roles.edit_perms"],
        )
        grant = PermissionGrant(
            grantor_subject_type="super_admin",
            grantor_subject_id="root",
            grantee_subject_type="actor",
            grantee_subject_id="target-member",
            permission_code="handover.manage",
            created_by="root",
        )
        session.add(grant)
        session.commit()
        grant_id = grant.id

    with _build_strict_client(db_session_factory) as client:
        response = client.delete(
            f"/api/permissions/grants/{grant_id}",
            headers=_auth_headers(
                user_id="member-revoke-grant",
                agency_id=scope["agency_id"],
                role="grant_admin",
            ),
        )

    assert response.status_code == 200
    with db_session_factory() as session:
        persisted = session.get(PermissionGrant, grant_id)
        assert persisted is not None
        assert persisted.status == "revoked"
        assert persisted.revoked_by == "member-revoke-grant"
        assert persisted.revoked_at is not None


def test_data_scope_grant_revoke_endpoint_marks_scope_revoked(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-revoke-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-revoke-scope",
            role_name="scope_admin",
            permissions=["data_scope.manage"],
        )
        grant = DataScopeGrant(
            subject_type="actor",
            subject_id="target-member",
            scope_type="site",
            scope_id=scope["site_id"],
            granted_by_subject_type="super_admin",
            granted_by_subject_id="root",
        )
        session.add(grant)
        session.commit()
        grant_id = grant.id

    with _build_strict_client(db_session_factory) as client:
        response = client.delete(
            f"/api/permissions/data-scopes/{grant_id}",
            headers=_auth_headers(
                user_id="member-revoke-scope",
                agency_id=scope["agency_id"],
                role="scope_admin",
            ),
        )

    assert response.status_code == 200
    with db_session_factory() as session:
        persisted = session.get(DataScopeGrant, grant_id)
        assert persisted is not None
        assert persisted.status == "revoked"
        assert persisted.revoked_at is not None


def test_site_effective_access_endpoint_marks_when_site_is_in_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-site-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-site-reader",
            role_name="site_reader",
            permissions=["data_scope.view", "sites.view"],
        )
        session.add(
            DataScopeGrant(
                subject_type="actor",
                subject_id="member-site-reader",
                scope_type="site",
                scope_id=scope["site_id"],
                granted_by_subject_type="super_admin",
                granted_by_subject_id="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            f"/api/h5/sites/{scope['site_id']}/effective-access",
            headers=_auth_headers(
                user_id="member-site-reader",
                agency_id=scope["agency_id"],
                role="site_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == scope["site_id"]
    assert payload["in_scope"] is True
    assert "data_scope.view" in payload["effective_permissions"]

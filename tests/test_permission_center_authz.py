from collections.abc import Generator
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.permission_defs import DEFAULT_TEMPLATES
from app.core.settings import get_settings
from app.db.models import Account, Agency, AgencyMember, AgencyPermissionGrant, Agent, AuditLog, H5Site, RolePermission
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


def _seed_member(
    session: Session,
    *,
    agency_id: str,
    account_id: str,
    member_id: str,
    role_name: str,
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


def test_agency_permission_list_requires_roles_view(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-authz-view"
    member_id = "member-no-roles-view"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="support",
        )
        session.commit()

    response = strict_client.get(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='support')}",
        },
    )

    assert response.status_code == 403
    assert "roles.view" in response.json()["detail"]


def test_agency_permission_update_accepts_same_agency_member_with_roles_edit_perms(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-authz-edit"
    member_id = "member-role-editor"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_admin",
        )
        session.add(
            RolePermission(
                id="role-custom-role-admin",
                agency_id=agency_id,
                role_name="custom_role_admin",
                permissions=["roles.edit_perms", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-support-existing",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view", "tickets.reply"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_admin')}",
        },
        json={
            "role_name": "support",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 200
    assert response.json()["role_name"] == "support"
    assert response.json()["permissions"] == ["tickets.view"]


def test_apply_template_requires_roles_edit_perms(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-authz-template"
    member_id = "member-no-template-edit"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="support",
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='support')}",
        },
        json={
            "agency_id": agency_id,
            "template_id": "standard_support",
            "target_role": "support",
        },
    )

    assert response.status_code == 403
    assert "roles.edit_perms" in response.json()["detail"]


def test_agency_role_updates_reject_super_admin_only_permissions(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-super-admin-only"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-1', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "role_name": "support",
            "permissions": ["agents.permissions"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "message": "Super-admin-only permissions cannot be assigned to agency roles.",
        "forbidden_permissions": ["agents.permissions"],
    }


def test_auth_permissions_strip_super_admin_only_codes_from_agency_roles(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-strip-super-only"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-agent-strip-super-only",
                agency_id=agency_id,
                role_name="agent",
                permissions=["roles.view", "agents.permissions"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/auth/permissions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='agency-owner-strip', agency_id=agency_id, user_type='agent', role='agent')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "roles.view" in payload["permissions"]
    assert "agents.permissions" not in payload["permissions"]


def test_create_custom_role_uses_canonical_roles_create_and_writes_audit_log(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-create-role-audit"
    member_id = "member-custom-role-creator"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_admin",
        )
        session.add(
            RolePermission(
                id="role-custom-role-audit-admin",
                agency_id=agency_id,
                role_name="custom_role_admin",
                permissions=["roles.create", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/custom-role",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_admin')}",
        },
        json={
            "role_name": "custom_quality",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 200
    assert response.json()["role_name"] == "custom_quality"

    with db_session_factory() as session:
        audit_logs = session.execute(
            select(AuditLog).where(AuditLog.action == "permissions.created")
        ).scalars().all()
        assert len(audit_logs) == 1
        assert audit_logs[0].actor_type == "agent_member"
        assert audit_logs[0].actor_id == member_id
        assert audit_logs[0].target_id == f"{agency_id}/custom_quality"


def test_create_custom_role_rejects_jwt_role_claim_when_db_membership_is_lower(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-role-claim-write-guard"
    member_id = "member-role-claim-write-guard"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="support",
        )
        session.add(
            RolePermission(
                id="role-support-write-guard",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-custom-role-admin-write-guard",
                agency_id=agency_id,
                role_name="custom_role_admin",
                permissions=["roles.create", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/custom-role",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_admin')}",
        },
        json={
            "role_name": "custom_quality",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 403
    assert "roles.create" in response.json()["detail"]


def test_permission_definitions_requires_roles_view(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-definitions-authz"
    member_id = "member-no-definitions-view"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="support",
        )
        session.commit()

    response = strict_client.get(
        "/api/permissions/definitions",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='support')}",
        },
    )

    assert response.status_code == 403
    assert "roles.view" in response.json()["detail"]


def test_permission_templates_are_scoped_to_actor_agency_and_strip_super_admin_only_codes(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-scope-a"
    other_agency_id = "agency-perm-template-scope-b"
    member_id = "member-template-reader"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id=other_agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_viewer",
        )
        session.add(
            RolePermission(
                id="role-template-reader",
                agency_id=agency_id,
                role_name="custom_role_viewer",
                permissions=["roles.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="tpl-local-visible",
                agency_id=agency_id,
                role_name="custom_template_local",
                is_template=True,
                template_name="Local Template",
                permissions=["tickets.view", "agents.permissions"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="tpl-foreign-hidden",
                agency_id=other_agency_id,
                role_name="custom_template_foreign",
                is_template=True,
                template_name="Foreign Template",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        "/api/permissions/templates",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_viewer')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    custom_ids = [item["id"] for item in payload["custom"]]
    assert custom_ids == ["tpl-local-visible"]
    assert payload["custom"][0]["agency_id"] == agency_id
    assert payload["custom"][0]["permissions"] == ["tickets.view"]


def test_apply_template_rejects_foreign_custom_template_ids_for_agency_actors(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-apply-a"
    other_agency_id = "agency-perm-template-apply-b"
    member_id = "member-template-editor"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id=other_agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_editor",
        )
        session.add(
            RolePermission(
                id="role-template-editor",
                agency_id=agency_id,
                role_name="custom_role_editor",
                permissions=["roles.edit_perms", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="tpl-foreign-apply",
                agency_id=other_agency_id,
                role_name="custom_template_foreign_apply",
                is_template=True,
                template_name="Foreign Apply Template",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_editor')}",
        },
        json={
            "agency_id": agency_id,
            "template_id": "tpl-foreign-apply",
            "target_role": "support",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found."


def test_agency_permissions_strip_super_admin_only_codes_from_read_payloads(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-read-sanitize"
    member_id = "member-read-sanitize"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_viewer",
        )
        session.add(
            RolePermission(
                id="role-read-sanitize-viewer",
                agency_id=agency_id,
                role_name="custom_role_viewer",
                permissions=["roles.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-read-sanitize-target",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view", "agents.permissions"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_viewer')}",
        },
    )

    assert response.status_code == 200
    support_role = next(item for item in response.json()["roles"] if item["role_name"] == "support")
    assert support_role["permissions"] == ["tickets.view"]


def test_copy_permissions_requires_agents_permissions(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    source_agency_id = "agency-perm-copy-authz-source"
    target_agency_id = "agency-perm-copy-authz-target"
    agency_owner_id = "agency-copy-owner"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=source_agency_id)
        _seed_agency_scope(session, agency_id=target_agency_id)
        session.add(
            RolePermission(
                id="role-agent-no-copy",
                agency_id=source_agency_id,
                role_name="agent",
                permissions=["roles.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/copy",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=agency_owner_id, agency_id=source_agency_id, user_type='agent', role='agent')}",
        },
        json={
            "source_agency_id": source_agency_id,
            "target_agency_id": target_agency_id,
        },
    )

    assert response.status_code == 403
    assert "agents.permissions" in response.json()["detail"]


def test_copy_permissions_copies_roles_and_writes_audit_log(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    source_agency_id = "agency-perm-copy-source"
    target_agency_id = "agency-perm-copy-target"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=source_agency_id)
        _seed_agency_scope(session, agency_id=target_agency_id)
        session.add(
            RolePermission(
                id="role-copy-source-agent",
                agency_id=source_agency_id,
                role_name="agent",
                permissions=["roles.view", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-copy-source-support",
                agency_id=source_agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-copy-source-template",
                agency_id=source_agency_id,
                role_name="custom_template_source",
                is_template=True,
                template_name="Template Source",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-copy-target-stale",
                agency_id=target_agency_id,
                role_name="support",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/copy",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-copy', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "source_agency_id": source_agency_id,
            "target_agency_id": target_agency_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["roles_copied"] == 2

    with db_session_factory() as session:
        copied_roles = session.execute(
            select(RolePermission).where(RolePermission.agency_id == target_agency_id).order_by(RolePermission.role_name)
        ).scalars().all()
        assert [(item.role_name, item.is_template, item.permissions) for item in copied_roles] == [
            ("agent", False, ["roles.view", "tickets.view"]),
            ("support", False, ["tickets.view"]),
        ]
        audit_logs = session.execute(
            select(AuditLog).where(AuditLog.action == "permissions.copy")
        ).scalars().all()
        assert len(audit_logs) == 1
        assert audit_logs[0].actor_type == "super_admin"
        assert audit_logs[0].target_id == target_agency_id


def test_copy_permissions_rejects_super_admin_only_source_codes_without_destroying_target_roles(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    source_agency_id = "agency-perm-copy-invalid-source"
    target_agency_id = "agency-perm-copy-invalid-target"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=source_agency_id)
        _seed_agency_scope(session, agency_id=target_agency_id)
        session.add(
            RolePermission(
                id="role-copy-invalid-source-agent",
                agency_id=source_agency_id,
                role_name="agent",
                permissions=["agents.permissions", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-copy-invalid-target-support",
                agency_id=target_agency_id,
                role_name="support",
                permissions=["tags.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/copy",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-copy-invalid', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "source_agency_id": source_agency_id,
            "target_agency_id": target_agency_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "message": "Super-admin-only permissions cannot be assigned to agency roles.",
        "forbidden_permissions": ["agents.permissions"],
    }

    with db_session_factory() as session:
        target_roles = session.execute(
            select(RolePermission).where(RolePermission.agency_id == target_agency_id).order_by(RolePermission.role_name)
        ).scalars().all()
        assert [(item.role_name, item.permissions) for item in target_roles] == [
            ("support", ["tags.view"]),
        ]
        audit_logs = session.execute(
            select(AuditLog).where(AuditLog.action == "permissions.copy")
        ).scalars().all()
        assert audit_logs == []


def test_agency_permission_list_includes_member_count_and_excludes_template_rows(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-summary-counts"
    member_id = "member-role-summary-viewer"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_role_viewer",
        )
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id="member-support-1",
            role_name="support",
        )
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id="member-support-2",
            role_name="support",
        )
        session.add(
            RolePermission(
                id="role-summary-viewer",
                agency_id=agency_id,
                role_name="custom_role_viewer",
                permissions=["roles.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-summary-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-summary-template",
                agency_id=agency_id,
                role_name="custom_template_night_shift",
                is_template=True,
                template_name="Night Shift",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.get(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_viewer')}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    role_names = [item["role_name"] for item in payload["roles"]]
    assert "custom_template_night_shift" not in role_names
    support_role = next(item for item in payload["roles"] if item["role_name"] == "support")
    assert support_role["member_count"] == 2


def test_super_admin_can_create_custom_role_for_selected_agency(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-superadmin-create-role"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.post(
        "/api/permissions/custom-role",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-role-create', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": agency_id,
            "role_name": "custom_escalation",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 200
    assert response.json()["role_name"] == "custom_escalation"


def test_create_update_and_delete_custom_template(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-crud"
    member_id = "member-template-crud"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_template_admin",
        )
        session.add(
            RolePermission(
                id="role-template-crud-admin",
                agency_id=agency_id,
                role_name="custom_template_admin",
                permissions=["roles.view", "roles.create", "roles.edit_perms", "roles.delete", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    create_response = strict_client.post(
        "/api/permissions/templates",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_admin')}",
        },
        json={
            "template_name": "Night Shift",
            "permissions": ["tickets.view"],
        },
    )

    assert create_response.status_code == 200
    template_id = create_response.json()["id"]
    assert create_response.json()["template_name"] == "Night Shift"

    update_response = strict_client.put(
        f"/api/permissions/templates/{template_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_admin')}",
        },
        json={
            "template_name": "Night Shift Updated",
            "permissions": ["tickets.view"],
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["template_name"] == "Night Shift Updated"

    delete_response = strict_client.delete(
        f"/api/permissions/templates/{template_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_admin')}",
        },
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["id"] == template_id


def test_super_admin_template_create_requires_explicit_agency_id(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id="agency-perm-template-superadmin-required")
        session.commit()

    response = strict_client.post(
        "/api/permissions/templates",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-create', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "template_name": "Missing Agency",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "agency_id is required for super admin permission-center writes."


def test_agency_member_template_crud_cannot_target_foreign_agency(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-own"
    other_agency_id = "agency-perm-template-foreign"
    member_id = "member-template-own-only"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id=other_agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_template_admin",
        )
        session.add(
            RolePermission(
                id="role-template-own-only-admin",
                agency_id=agency_id,
                role_name="custom_template_admin",
                permissions=["roles.create", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/templates",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_admin')}",
        },
        json={
            "agency_id": other_agency_id,
            "template_name": "Foreign Agency Template",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have access to this agency's permissions."


def test_template_update_and_delete_require_same_agency_access(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-update-own"
    other_agency_id = "agency-perm-template-update-foreign"
    member_id = "member-template-update-own"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id=other_agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_template_editor",
        )
        session.add(
            RolePermission(
                id="role-template-update-own-editor",
                agency_id=agency_id,
                role_name="custom_template_editor",
                permissions=["roles.edit_perms", "roles.delete", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="tpl-foreign-update-delete",
                agency_id=other_agency_id,
                role_name="custom_template_foreign_update_delete",
                is_template=True,
                template_name="Foreign Update Delete",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    update_response = strict_client.put(
        "/api/permissions/templates/tpl-foreign-update-delete",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_editor')}",
        },
        json={
            "template_name": "Foreign Update Delete Updated",
            "permissions": ["tickets.view"],
        },
    )

    assert update_response.status_code == 403
    assert update_response.json()["detail"] == "You do not have access to this agency's permissions."

    delete_response = strict_client.delete(
        "/api/permissions/templates/tpl-foreign-update-delete",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_editor')}",
        },
    )

    assert delete_response.status_code == 403
    assert delete_response.json()["detail"] == "You do not have access to this agency's permissions."


def test_apply_template_persists_template_provenance_and_manual_edit_clears_it(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-template-provenance"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    apply_response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-provenance', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": agency_id,
            "template_id": "standard_support",
            "target_role": "support",
        },
    )

    assert apply_response.status_code == 200
    applied_template_name = apply_response.json()["template_name"]

    get_after_apply = strict_client.get(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-provenance', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
    )

    assert get_after_apply.status_code == 200
    support_role = next(item for item in get_after_apply.json()["roles"] if item["role_name"] == "support")
    assert support_role["template_name"] == applied_template_name

    edit_response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-provenance', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "role_name": "support",
            "permissions": ["tickets.view"],
        },
    )

    assert edit_response.status_code == 200

    get_after_edit = strict_client.get(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-provenance', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
    )

    assert get_after_edit.status_code == 200
    support_role_after_edit = next(item for item in get_after_edit.json()["roles"] if item["role_name"] == "support")
    assert support_role_after_edit["template_name"] is None


def test_agency_permission_update_cannot_create_new_role_without_roles_create(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-update-create-guard"
    member_id = "member-edit-only"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_edit_only",
        )
        session.add(
            RolePermission(
                id="role-edit-only",
                agency_id=agency_id,
                role_name="custom_edit_only",
                permissions=["roles.edit_perms", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_edit_only')}",
        },
        json={
            "role_name": "custom_new_role",
            "permissions": ["tickets.view"],
        },
    )

    assert response.status_code == 403
    assert "roles.create" in response.json()["detail"]

    with db_session_factory() as session:
        created = session.execute(
            select(RolePermission).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == "custom_new_role",
            )
        ).scalar_one_or_none()
        assert created is None


def test_apply_template_cannot_create_new_role_without_roles_create(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-apply-create-guard"
    member_id = "member-template-edit-only"
    with db_session_factory() as session:
        seeded = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=seeded["account_id"],
            member_id=member_id,
            role_name="custom_template_edit_only",
        )
        session.add(
            RolePermission(
                id="role-template-edit-only",
                agency_id=agency_id,
                role_name="custom_template_edit_only",
                permissions=["roles.edit_perms", "tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_template_edit_only')}",
        },
        json={
            "agency_id": agency_id,
            "template_id": "standard_support",
            "target_role": "custom_night_shift",
        },
    )

    assert response.status_code == 403
    assert "roles.create" in response.json()["detail"]

    with db_session_factory() as session:
        created = session.execute(
            select(RolePermission).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == "custom_night_shift",
            )
        ).scalar_one_or_none()
        assert created is None


def test_apply_template_requires_existing_target_agency(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    missing_agency_id = "agency-perm-template-missing-agency"

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-missing-agency', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": missing_agency_id,
            "template_id": "standard_support",
            "target_role": "support",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agency not found."

    with db_session_factory() as session:
        audit_logs = session.execute(
            select(AuditLog).where(AuditLog.action == "permissions.apply_template")
        ).scalars().all()
        assert audit_logs == []


def test_create_custom_role_rejects_permissions_outside_agency_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-grant-cap-custom-role"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            AgencyPermissionGrant(
                id="grant-cap-custom-role",
                agency_id=agency_id,
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/custom-role",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-grant-cap-custom-role', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": agency_id,
            "role_name": "custom_capped",
            "permissions": ["tickets.view", "tickets.reply"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "message": "Permissions exceed agency granted permissions.",
        "disallowed_permissions": ["tickets.reply"],
    }


def test_update_agency_role_rejects_permissions_outside_agency_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-grant-cap-update"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            AgencyPermissionGrant(
                id="grant-cap-update",
                agency_id=agency_id,
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-cap-update-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.put(
        f"/api/permissions/agency/{agency_id}",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-grant-cap-update', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "role_name": "support",
            "permissions": ["tickets.view", "tickets.reply"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "message": "Permissions exceed agency granted permissions.",
        "disallowed_permissions": ["tickets.reply"],
    }


def test_apply_template_rejects_permissions_outside_agency_grants(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-grant-cap-template"
    template_permissions = list(DEFAULT_TEMPLATES["standard_support"]["permissions"])
    granted_permissions = sorted(permission for permission in template_permissions if permission != "tickets.reply")
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.add(
            AgencyPermissionGrant(
                id="grant-cap-template",
                agency_id=agency_id,
                permissions=granted_permissions,
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-grant-cap-template', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": agency_id,
            "template_id": "standard_support",
            "target_role": "support",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "message": "Permissions exceed agency granted permissions.",
        "disallowed_permissions": ["tickets.reply"],
    }


def test_super_admin_cannot_apply_foreign_agency_custom_template_to_other_agency(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    source_agency_id = "agency-perm-template-source-scope"
    target_agency_id = "agency-perm-template-target-scope"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=source_agency_id)
        _seed_agency_scope(session, agency_id=target_agency_id)
        session.add(
            RolePermission(
                id="tpl-source-only",
                agency_id=source_agency_id,
                role_name="custom_template_source_only",
                is_template=True,
                template_name="Source Only Template",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.commit()

    response = strict_client.post(
        "/api/permissions/apply-template",
        headers={
            "Authorization": f"Bearer {_issue_agent_token(user_id='super-admin-template-cross-agency', agency_id='system', user_type='super_admin', role='super_admin')}",
        },
        json={
            "agency_id": target_agency_id,
            "template_id": "tpl-source-only",
            "target_role": "support",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found."

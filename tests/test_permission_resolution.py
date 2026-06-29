from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import ActorRole
from app.core.permission_resolution import get_builtin_role_permissions, resolve_role_permissions
from app.db.models import Agency, RolePermission


def _seed_agency(session: Session, *, agency_id: str) -> None:
    session.add(
        Agency(
            id=agency_id,
            name=f"{agency_id} agency",
            username=f"{agency_id}-owner",
            password_hash="placeholder",
        )
    )
    session.flush()


def test_resolve_role_permissions_prefers_member_custom_role_over_support_role(
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-resolution-custom-first"
    with db_session_factory() as session:
        _seed_agency(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-resolution-support",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="role-resolution-custom",
                agency_id=agency_id,
                role_name="custom_specialist",
                permissions=["customers.view"],
                created_by="seed",
            )
        )
        session.commit()

    with db_session_factory() as session:
        resolved = resolve_role_permissions(
            session,
            user_type="agent_member",
            agency_id=agency_id,
            role_name="custom_specialist",
        )

    assert resolved == ["customers.view"]


def test_resolve_role_permissions_falls_back_to_support_role_when_member_role_missing(
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-resolution-support-fallback"
    with db_session_factory() as session:
        _seed_agency(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-resolution-support-fallback",
                agency_id=agency_id,
                role_name="support",
                permissions=["tickets.view", "customers.view"],
                created_by="seed",
            )
        )
        session.commit()

    with db_session_factory() as session:
        resolved = resolve_role_permissions(
            session,
            user_type="agent_member",
            agency_id=agency_id,
            role_name="custom_missing",
        )

    assert resolved == ["tickets.view", "customers.view"]


def test_resolve_role_permissions_falls_back_to_template_alias_for_manager(
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-resolution-manager-template"
    with db_session_factory() as session:
        _seed_agency(session, agency_id=agency_id)
        session.commit()

    with db_session_factory() as session:
        resolved = resolve_role_permissions(
            session,
            user_type="agent_member",
            agency_id=agency_id,
            role_name="manager",
    )

    assert resolved is not None
    assert "h5_templates.view" not in resolved
    assert "reports.view" in resolved


def test_resolve_role_permissions_filters_unknown_and_super_admin_only_codes_from_db_roles(
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-perm-resolution-filtering"
    with db_session_factory() as session:
        _seed_agency(session, agency_id=agency_id)
        session.add(
            RolePermission(
                id="role-resolution-agent-filtering",
                agency_id=agency_id,
                role_name="agent",
                permissions=["roles.view", "agents.permissions", "legacy.permission.code"],
                created_by="seed",
            )
        )
        session.commit()

    with db_session_factory() as session:
        resolved = resolve_role_permissions(
            session,
            user_type="agent",
            agency_id=agency_id,
            role_name="agent",
        )

    assert resolved == ["roles.view"]


def test_get_builtin_role_permissions_for_operator_excludes_unknown_codes() -> None:
    resolved = get_builtin_role_permissions(ActorRole.OPERATOR)

    assert "backups.manage" not in resolved
    assert "batch.manage" not in resolved
    assert "backups.view" in resolved
    assert "batch.tags" in resolved


def test_get_builtin_role_permissions_for_operator_includes_customer_timeline() -> None:
    resolved = get_builtin_role_permissions(ActorRole.OPERATOR)

    assert "customers.view" in resolved
    assert "customers.detail" in resolved
    assert "customers.timeline" in resolved

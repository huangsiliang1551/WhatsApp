from __future__ import annotations

from collections.abc import Generator
import os

import httpx
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import Account, Agency, AgencyMember, H5Site, H5SiteConfig, RolePermission
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
    with TestClient(app) as test_client:
        yield test_client
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


def _seed_agency_scope(session: Session, *, agency_id: str) -> str:
    account_id = f"{agency_id}-account"
    session.add(Account(account_id=account_id, display_name=account_id, provider_type="mock"))
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
    return account_id


def _seed_member(
    session: Session,
    *,
    agency_id: str,
    account_id: str,
    member_id: str,
    role_name: str,
) -> None:
    from app.db.models import Agent

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


def test_w6_permissions_smoke_updates_same_agency_role(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "w6-perm-agency"
    member_id = "w6-role-editor"
    with db_session_factory() as session:
        account_id = _seed_agency_scope(session, agency_id=agency_id)
        _seed_member(
            session,
            agency_id=agency_id,
            account_id=account_id,
            member_id=member_id,
            role_name="custom_role_admin",
        )
        session.add(
            RolePermission(
                id="w6-role-admin",
                agency_id=agency_id,
                role_name="custom_role_admin",
                permissions=["roles.edit_perms", "tickets.view"],
                created_by="seed",
            )
        )
        session.add(
            RolePermission(
                id="w6-role-support",
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
            "Authorization": (
                f"Bearer {_issue_agent_token(user_id=member_id, agency_id=agency_id, user_type='agent_member', role='custom_role_admin')}"
            ),
        },
        json={"role_name": "support", "permissions": ["tickets.view"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["permissions"] == ["tickets.view"]

    with db_session_factory() as session:
        role = session.execute(
            select(RolePermission).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == "support",
            )
        ).scalar_one()
    assert role.permissions == ["tickets.view"]


def test_w6_h5_deploy_smoke_routes_use_real_service(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with db_session_factory() as session:
        session.add(
            Account(
                account_id="w6-h5-account",
                display_name="W6 H5 Account",
                provider_type="mock",
            )
        )
        session.add(
            H5Site(
                id="w6-h5-site",
                account_id="w6-h5-account",
                site_key="w6-h5-site-key",
                domain="w6-h5.example.com",
                brand_name="W6 H5",
            )
        )
        session.add(
            H5SiteConfig(
                id="w6-h5-config",
                site_id="w6-h5-site",
                domain="w6-h5-preview.example.com",
                deploy_type="docker",
                ssl_enabled=True,
            )
        )
        session.commit()

    class _Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    def fake_get(url: str, timeout: int, follow_redirects: bool) -> _Response:
        assert timeout == 10
        assert follow_redirects is True
        if url.endswith("/api/h5/sites/w6-h5-site-key/brand-config"):
            return _Response(200)
        if url.endswith("/h5/login?site_key=w6-h5-site-key"):
            return _Response(200)
        return _Response(200)

    monkeypatch.setattr(httpx, "get", fake_get)

    headers = {"X-Actor-Id": "w6-super-admin", "X-Actor-Role": "super_admin"}
    script_response = client.post("/api/h5/sites/w6-h5-site/deploy-script", headers=headers)
    verify_response = client.post("/api/h5/sites/w6-h5-site/verify-deployment", headers=headers)

    assert script_response.status_code == 200, script_response.text
    assert "docker compose" in script_response.json()["script"]
    assert "w6-h5-site-key" in script_response.json()["script"]

    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["results"] == {
        "domain_accessible": True,
        "ssl_valid": True,
        "api_proxy_working": True,
        "h5_preview_working": True,
    }

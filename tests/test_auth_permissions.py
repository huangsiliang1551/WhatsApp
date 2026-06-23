"""P0-01 regression tests: forged X-Actor-* headers must not bypass auth.

These tests pin the security boundary described in
``whatsapp_code_fix_spec.md`` section 2:

* In production (``APP_ENV=production`` with ``AUTH_REQUIRED=true``) a forged
  ``X-Actor-Role: super_admin`` header must not access permission-protected
  endpoints.
* Without a Bearer token, ``require_permission`` endpoints must return 401 in
  production.
* In test mode / when auth is disabled, local development must keep working so
  the test suite does not collapse.
"""

import os
from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.db.base import Base
from app.main import app


@pytest.fixture
def production_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """A client that simulates production: auth required, no test mode."""
    database_path = tmp_path / "prod_auth.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    original_env = {
        "APP_ENV": os.environ.get("APP_ENV"),
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
    }
    os.environ["APP_ENV"] = "production"
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["LIVE_TRANSLATION_ENABLED"] = "false"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"

    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    get_settings.cache_clear()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    engine.dispose()


def test_permission_endpoint_rejects_forged_header_actor_in_production(
    production_client: TestClient,
) -> None:
    """Forged X-Actor-Role: super_admin cannot access a permission endpoint."""
    response = production_client.get(
        "/api/conversations/stats",
        headers={
            "X-Actor-Id": "attacker",
            "X-Actor-Role": "super_admin",
            "X-Actor-Account-Ids": "*",
        },
    )

    assert response.status_code in {401, 403}, response.text


def test_permission_endpoint_requires_bearer_token_in_production(
    production_client: TestClient,
) -> None:
    """No Bearer token in production -> 401 on a permission endpoint."""
    response = production_client.get("/api/conversations/stats")

    assert response.status_code == 401, response.text


def test_permission_endpoint_allows_local_dev_actor_when_auth_disabled(
    client: TestClient,
) -> None:
    """In test mode (auth relaxed), the local dev actor must still work.

    The shared ``client`` fixture sets ``TEST_MODE=true``.
    """
    response = client.get("/api/conversations/stats")

    assert response.status_code != 401, response.text

from collections.abc import Generator
from datetime import date
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import Account, Agency, AgencyBilling, H5Site
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


def _admin_headers() -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            + _issue_agent_token(
                user_id="super-admin-billing",
                agency_id="system",
                user_type="super_admin",
                role="super_admin",
            )
        ),
    }


def _seed_agency_scope(session: Session, *, agency_id: str) -> None:
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


def _seed_billing(
    session: Session,
    *,
    billing_id: str,
    agency_id: str,
    billing_type: str = "subscription",
    amount: float = 99.0,
    status: str = "draft",
    billing_period_start: date | None = None,
    billing_period_end: date | None = None,
    line_items: list[dict[str, object]] | None = None,
) -> AgencyBilling:
    billing = AgencyBilling(
        id=billing_id,
        agency_id=agency_id,
        billing_type=billing_type,
        amount=amount,
        status=status,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        line_items=line_items,
    )
    session.add(billing)
    session.flush()
    return billing


def test_list_agency_billing_supports_filters_and_stable_line_items(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-filters"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_agency_scope(session, agency_id="agency-billing-filters-other")
        _seed_billing(
            session,
            billing_id="billing-match",
            agency_id=agency_id,
            billing_type="subscription",
            amount=128.5,
            status="pending",
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
            line_items=[
                {"description": "January plan", "quantity": 1, "unit_price": 128.5},
            ],
        )
        _seed_billing(
            session,
            billing_id="billing-status-miss",
            agency_id=agency_id,
            billing_type="subscription",
            amount=128.5,
            status="draft",
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
        )
        _seed_billing(
            session,
            billing_id="billing-type-miss",
            agency_id=agency_id,
            billing_type="usage",
            amount=66.0,
            status="pending",
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
        )
        _seed_billing(
            session,
            billing_id="billing-period-miss",
            agency_id=agency_id,
            billing_type="subscription",
            amount=70.0,
            status="pending",
            billing_period_start=date(2026, 2, 1),
            billing_period_end=date(2026, 2, 28),
        )
        _seed_billing(
            session,
            billing_id="billing-agency-miss",
            agency_id="agency-billing-filters-other",
            billing_type="subscription",
            amount=80.0,
            status="pending",
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
        )
        session.commit()

    response = strict_client.get(
        f"/api/agents/{agency_id}/billing",
        params={
            "status": "pending",
            "billing_type": "subscription",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
        },
        headers=_admin_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": "billing-match",
            "agency_id": agency_id,
            "billing_type": "subscription",
            "amount": 128.5,
            "billing_period_start": "2026-01-01",
            "billing_period_end": "2026-01-31",
            "status": "pending",
            "line_items": [
                {"description": "January plan", "quantity": 1, "unit_price": 128.5},
            ],
            "created_at": response.json()[0]["created_at"],
        }
    ]


def test_get_agency_billing_detail_returns_full_line_items(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-detail"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_billing(
            session,
            billing_id="billing-detail-1",
            agency_id=agency_id,
            billing_type="usage",
            amount=222.0,
            status="pending",
            billing_period_start=date(2026, 3, 1),
            billing_period_end=date(2026, 3, 31),
            line_items=[
                {"description": "AI messages", "quantity": 1200, "unit_price": 0.1},
                {"description": "Translations", "quantity": 300, "unit_price": 0.34},
            ],
        )
        session.commit()

    response = strict_client.get(
        f"/api/agents/{agency_id}/billing/billing-detail-1",
        headers=_admin_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": "billing-detail-1",
        "agency_id": agency_id,
        "billing_type": "usage",
        "amount": 222.0,
        "billing_period_start": "2026-03-01",
        "billing_period_end": "2026-03-31",
        "status": "pending",
        "line_items": [
            {"description": "AI messages", "quantity": 1200, "unit_price": 0.1},
            {"description": "Translations", "quantity": 300, "unit_price": 0.34},
        ],
        "created_at": response.json()["created_at"],
    }


def test_create_agency_billing_defaults_to_draft_and_persists_line_items(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-create"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        session.commit()

    response = strict_client.post(
        f"/api/agents/{agency_id}/billing",
        headers=_admin_headers(),
        json={
            "billing_type": "subscription",
            "amount": 88.6,
            "billing_period_start": "2026-04-01",
            "billing_period_end": "2026-04-30",
            "line_items": [
                {"description": "April base fee", "quantity": 1, "unit_price": 88.6},
            ],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["agency_id"] == agency_id
    assert payload["billing_type"] == "subscription"
    assert payload["amount"] == 88.6
    assert payload["billing_period_start"] == "2026-04-01"
    assert payload["billing_period_end"] == "2026-04-30"
    assert payload["status"] == "draft"
    assert payload["line_items"] == [
        {"description": "April base fee", "quantity": 1, "unit_price": 88.6},
    ]

    detail_response = strict_client.get(
        f"/api/agents/{agency_id}/billing/{payload['id']}",
        headers=_admin_headers(),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["line_items"] == payload["line_items"]


def test_patch_agency_billing_supports_state_flow_and_updates_editable_fields(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-patch"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_billing(
            session,
            billing_id="billing-state-flow",
            agency_id=agency_id,
            billing_type="usage",
            amount=150.0,
            status="draft",
            billing_period_start=date(2026, 5, 1),
            billing_period_end=date(2026, 5, 31),
            line_items=[
                {"description": "Original item", "quantity": 1, "unit_price": 150.0},
            ],
        )
        session.commit()

    pending_response = strict_client.patch(
        f"/api/agents/{agency_id}/billing/billing-state-flow",
        headers=_admin_headers(),
        json={
            "billing_type": "subscription",
            "amount": 166.8,
            "status": "pending",
            "billing_period_start": "2026-05-05",
            "billing_period_end": "2026-05-28",
            "line_items": [
                {"description": "Adjusted item", "quantity": 2, "unit_price": 75.0},
            ],
        },
    )
    assert pending_response.status_code == 200, pending_response.text
    assert pending_response.json()["billing_type"] == "subscription"
    assert pending_response.json()["amount"] == 166.8
    assert pending_response.json()["status"] == "pending"
    assert pending_response.json()["billing_period_start"] == "2026-05-05"
    assert pending_response.json()["billing_period_end"] == "2026-05-28"
    assert pending_response.json()["line_items"] == [
        {"description": "Adjusted item", "quantity": 2, "unit_price": 75.0},
    ]

    paid_response = strict_client.patch(
        f"/api/agents/{agency_id}/billing/billing-state-flow",
        headers=_admin_headers(),
        json={"status": "paid"},
    )
    assert paid_response.status_code == 200, paid_response.text
    assert paid_response.json()["status"] == "paid"

    verified_response = strict_client.patch(
        f"/api/agents/{agency_id}/billing/billing-state-flow",
        headers=_admin_headers(),
        json={"status": "verified"},
    )
    assert verified_response.status_code == 200, verified_response.text
    assert verified_response.json()["status"] == "verified"

    detail_response = strict_client.get(
        f"/api/agents/{agency_id}/billing/billing-state-flow",
        headers=_admin_headers(),
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["billing_type"] == "subscription"
    assert detail_response.json()["amount"] == 166.8


def test_patch_agency_billing_rejects_illegal_status_transition(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-invalid-transition"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_billing(
            session,
            billing_id="billing-invalid-transition",
            agency_id=agency_id,
            amount=51.0,
            status="draft",
        )
        session.commit()

    response = strict_client.patch(
        f"/api/agents/{agency_id}/billing/billing-invalid-transition",
        headers=_admin_headers(),
        json={"status": "verified"},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Invalid billing status transition: draft -> verified."


def test_delete_agency_billing_cancels_draft_and_blocks_paid_records(
    strict_client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    agency_id = "agency-billing-delete"
    with db_session_factory() as session:
        _seed_agency_scope(session, agency_id=agency_id)
        _seed_billing(
            session,
            billing_id="billing-cancel-me",
            agency_id=agency_id,
            status="draft",
        )
        _seed_billing(
            session,
            billing_id="billing-paid-locked",
            agency_id=agency_id,
            status="paid",
        )
        session.commit()

    cancel_response = strict_client.delete(
        f"/api/agents/{agency_id}/billing/billing-cancel-me",
        headers=_admin_headers(),
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"

    detail_response = strict_client.get(
        f"/api/agents/{agency_id}/billing/billing-cancel-me",
        headers=_admin_headers(),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "cancelled"

    locked_response = strict_client.delete(
        f"/api/agents/{agency_id}/billing/billing-paid-locked",
        headers=_admin_headers(),
    )
    assert locked_response.status_code == 409, locked_response.text
    assert locked_response.json()["detail"] == (
        "Billing record in status 'paid' cannot be cancelled."
    )


def test_legacy_agent_billing_routes_are_not_exposed(
    strict_client: TestClient,
) -> None:
    response = strict_client.get(
        "/api/agent-billing",
        headers=_admin_headers(),
    )

    assert response.status_code == 404, response.text

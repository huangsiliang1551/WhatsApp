from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.ownership import (
    get_ownership_report,
    list_ownership_audit_events,
)
from app.core.auth import ActorRole, RequestActor
from app.db.base import Base
from app.db.models import Account
from app.db.ownership_models import AIAgent, EntryLink, OwnershipAuditEvent
from app.services.ownership_report_service import OwnershipReportService


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _actor(*, role: ActorRole, account_ids: list[str]) -> RequestActor:
    return RequestActor(
        actor_id="test-actor",
        display_name="Test Actor",
        role=role,
        account_ids=account_ids,
        resolved_permissions=["reports.ownership.view", "member_ownership.history"],
    )


@pytest.mark.asyncio
async def test_ownership_report_rejects_explicit_cross_account_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        actor = _actor(role=ActorRole.OPERATOR, account_ids=["acct-a"])
        with pytest.raises(Exception) as exc_info:
            await get_ownership_report(
                account_id="acct-b",
                session=session,
                actor=actor,
            )
        assert getattr(exc_info.value, "status_code", None) == 403


def test_ownership_report_anomalies_count_active_links_pointing_to_disabled_ai(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        account = Account(account_id="acct-report", display_name="Report", provider_type="mock")
        session.add(account)
        disabled_agent = AIAgent(
            account_id=account.account_id,
            name="disabled-ai",
            display_name="Disabled AI",
            status="disabled",
            provider_name="openai",
            model_name="gpt-4o-mini",
            health_status="healthy",
        )
        healthy_agent = AIAgent(
            account_id=account.account_id,
            name="healthy-ai",
            display_name="Healthy AI",
            status="active",
            provider_name="openai",
            model_name="gpt-4o-mini",
            health_status="healthy",
            fallback_staff_user_id="staff-1",
        )
        session.add_all([disabled_agent, healthy_agent])
        session.flush()
        session.add_all(
            [
                EntryLink(
                    account_id=account.account_id,
                    code="bad-link",
                    link_type="register",
                    channel="h5",
                    status="active",
                    target_type="ai_agent",
                    target_ai_agent_id=disabled_agent.id,
                ),
                EntryLink(
                    account_id=account.account_id,
                    code="good-link",
                    link_type="register",
                    channel="h5",
                    status="active",
                    target_type="ai_agent",
                    target_ai_agent_id=healthy_agent.id,
                ),
            ]
        )
        session.commit()

        report = OwnershipReportService(session).anomalies(account_id=account.account_id)
        assert report["entry_link_pointing_disabled_ai"] == 1


@pytest.mark.asyncio
async def test_ownership_audit_list_filters_to_actor_accounts(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        session.add_all(
            [
                OwnershipAuditEvent(
                    account_id="acct-a",
                    action="member_owner_transferred",
                    target_type="member_profile",
                    target_id="member-a",
                    actor_type="user",
                    actor_id="actor-a",
                    payload={"account": "a"},
                ),
                OwnershipAuditEvent(
                    account_id="acct-b",
                    action="member_owner_transferred",
                    target_type="member_profile",
                    target_id="member-b",
                    actor_type="user",
                    actor_id="actor-b",
                    payload={"account": "b"},
                ),
            ]
        )
        session.commit()

        rows = await list_ownership_audit_events(
            account_id=None,
            target_type=None,
            target_id=None,
            action=None,
            limit=100,
            session=session,
            actor=_actor(role=ActorRole.OPERATOR, account_ids=["acct-a"]),
        )

        assert len(rows) == 1
        assert rows[0]["target_id"] == "member-a"

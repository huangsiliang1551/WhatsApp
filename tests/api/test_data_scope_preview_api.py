from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
import os

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.api.routes.agent_auth import _encode_agent_jwt
from app.core.settings import get_settings
from app.db.models import (
    Account,
    Agent,
    Agency,
    AgencyMember,
    AppUser,
    Conversation,
    ConversationNote,
    CustomerOwnershipAssignment,
    DataScopeGrant,
    H5Site,
    H5SiteConfig,
    HandoverLog,
    MktTaskInstance,
    Message,
    MessageEvent,
    RolePermission,
    TaskRule,
    Ticket,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
)
from app.main import app
from app.services.bonus_grant_service import BonusGrantService
from app.services.recharge_repair_service import RechargeRepairService
from app.services.wallet_ledger_service import WalletLedgerService


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


def _seed_scope(session: Session, *, agency_id: str = "agency-w3-preview") -> dict[str, str]:
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


def _seed_withdrawal(session: Session, *, account_id: str, user_id: str, request_no: str) -> WithdrawalRequest:
    wallet = WalletAccount(account_id=account_id, user_id=user_id, system_balance=Decimal("50"))
    session.add(wallet)
    session.flush()
    withdrawal = WithdrawalRequest(
        account_id=account_id,
        wallet_account_id=wallet.id,
        user_id=user_id,
        request_no=request_no,
        amount=Decimal("10"),
        currency="USD",
        status="submitted",
    )
    session.add(withdrawal)
    session.flush()
    return withdrawal


def test_customer_preview_query_respects_customer_ownership_not_only_account_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-preview-customers")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-preview-customer",
            role_name="preview_reader",
            permissions=["data_scope.view", "customers.view"],
        )
        owned = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="owned-customer")
        other = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="other-customer")
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-preview-customer",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/permissions/data-scope-preview/customers",
            headers=_auth_headers(
                user_id="member-preview-customer",
                agency_id=scope["agency_id"],
                role="preview_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["public_user_id"] for item in payload["items"]] == ["owned-customer"]


def test_conversation_preview_query_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-preview-conversations")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-preview-conversation",
            role_name="preview_reader",
            permissions=["data_scope.view", "conversations.view"],
        )
        owned = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="owned-conversation-customer")
        other = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="other-conversation-customer")
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-preview-conversation",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-conv",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-conv",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/permissions/data-scope-preview/conversations",
            headers=_auth_headers(
                user_id="member-preview-conversation",
                agency_id=scope["agency_id"],
                role="preview_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["external_conversation_id"] for item in payload["items"]] == ["owned-conv"]


def test_withdrawal_preview_query_respects_snapshot_scope_via_explicit_data_scope_grant(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-preview-withdrawals")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-preview-finance",
            role_name="preview_finance",
            permissions=["data_scope.view", "finance.view_withdrawal"],
        )
        owned = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="owned-withdraw-customer")
        other = _seed_customer(session, account_id=scope["account_id"], site_id=scope["site_id"], public_user_id="other-withdraw-customer")
        session.add(
            DataScopeGrant(
                subject_type="actor",
                subject_id="member-preview-finance",
                scope_type="staff",
                scope_id="member-preview-finance",
                granted_by_subject_type="super_admin",
                granted_by_subject_id="root",
            )
        )
        owned_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=owned.id,
            request_no="WD-OWNED-PREVIEW",
        )
        owned_withdrawal.owner_staff_id_snapshot = "member-preview-finance"
        owned_withdrawal.agency_id_snapshot = scope["agency_id"]
        owned_withdrawal.site_id_snapshot = scope["site_id"]

        other_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=other.id,
            request_no="WD-OTHER-PREVIEW",
        )
        other_withdrawal.owner_staff_id_snapshot = "member-other"
        other_withdrawal.agency_id_snapshot = scope["agency_id"]
        other_withdrawal.site_id_snapshot = scope["site_id"]
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/permissions/data-scope-preview/withdrawals",
            headers=_auth_headers(
                user_id="member-preview-finance",
                agency_id=scope["agency_id"],
                role="preview_finance",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["request_no"] for item in payload["items"]] == ["WD-OWNED-PREVIEW"]


def test_platform_users_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-platform-users")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-platform-users",
            role_name="platform_user_reader",
            permissions=["users.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-platform-user",
        )
        _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-platform-user",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-platform-users",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/platform/users?page=1&size=20",
            headers=_auth_headers(
                user_id="member-platform-users",
                agency_id=scope["agency_id"],
                role="platform_user_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["public_user_id"] for item in payload["items"]] == ["owned-platform-user"]


def test_conversations_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversations")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversations",
            role_name="conversation_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversations",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/conversations?page=1&size=20",
            headers=_auth_headers(
                user_id="member-route-conversations",
                agency_id=scope["agency_id"],
                role="conversation_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["conversation_id"] for item in payload["items"]] == ["owned-route-conversation"]


def test_platform_withdrawals_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-withdrawals")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-withdrawals",
            role_name="withdrawal_reader",
            permissions=["finance.view_withdrawal"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-withdrawal-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-withdrawal-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-withdrawals",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=owned.id,
            request_no="WD-OWNED-ROUTE",
        )
        _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=other.id,
            request_no="WD-OTHER-ROUTE",
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/platform/withdrawals",
            headers=_auth_headers(
                user_id="member-route-withdrawals",
                agency_id=scope["agency_id"],
                role="withdrawal_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["requestNo"] for item in payload] == ["WD-OWNED-ROUTE"]


def test_conversation_stats_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-stats")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-stats",
            role_name="conversation_stats_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-stats-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-stats-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-stats",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-stats",
                    customer_id=owned.id,
                    status="open",
                    is_sleeping=False,
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-stats",
                    customer_id=other.id,
                    status="open",
                    is_sleeping=False,
                ),
            ]
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/conversations/stats",
            headers=_auth_headers(
                user_id="member-route-conversation-stats",
                agency_id=scope["agency_id"],
                role="conversation_stats_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_count"] == 1
    assert payload["sleeping_count"] == 0
    assert payload["closed_count"] == 0


def test_finance_bonus_grants_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-bonus-grants")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-bonus-grants",
            role_name="finance_reader",
            permissions=["reports.finance"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-bonus-grant-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-bonus-grant-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-bonus-grants",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with db_session_factory() as session:
        svc = BonusGrantService(session)
        svc.create_grant(
            account_id=scope["account_id"],
            user_id=owned_id,
            amount=Decimal("12"),
            currency="USD",
            reason="Owned grant",
            remark=None,
            source_type="admin_bonus",
            operator_id="seed-admin",
        )
        svc.create_grant(
            account_id=scope["account_id"],
            user_id=other_id,
            amount=Decimal("34"),
            currency="USD",
            reason="Other grant",
            remark=None,
            source_type="admin_bonus",
            operator_id="seed-admin",
        )

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/finance/bonus-grants",
            headers=_auth_headers(
                user_id="member-route-bonus-grants",
                agency_id=scope["agency_id"],
                role="finance_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["public_user_id"] for item in payload] == ["owned-route-bonus-grant-customer"]


def test_finance_recharge_repairs_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-recharge-repairs")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-recharge-repairs",
            role_name="finance_reader",
            permissions=["reports.finance"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-recharge-repair-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-recharge-repair-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-recharge-repairs",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with db_session_factory() as session:
        svc = RechargeRepairService(session)
        svc.create_repair(
            account_id=scope["account_id"],
            user_id=owned_id,
            amount=Decimal("56"),
            currency="USD",
            repair_type="callback_missing",
            reason="Owned repair",
            remark=None,
            channel_id=None,
            platform_order_no="PO-owned",
            channel_order_no="CO-owned",
            operator_id="seed-admin",
        )
        svc.create_repair(
            account_id=scope["account_id"],
            user_id=other_id,
            amount=Decimal("78"),
            currency="USD",
            repair_type="callback_missing",
            reason="Other repair",
            remark=None,
            channel_id=None,
            platform_order_no="PO-other",
            channel_order_no="CO-other",
            operator_id="seed-admin",
        )

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/finance/recharge-repairs",
            headers=_auth_headers(
                user_id="member-route-recharge-repairs",
                agency_id=scope["agency_id"],
                role="finance_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["public_user_id"] for item in payload] == ["owned-route-recharge-repair-customer"]


def test_finance_report_routes_respect_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-finance-reports")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-finance-reports",
            role_name="finance_reader",
            permissions=["reports.finance", "finance.view_recharge", "finance.view_withdrawal"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-finance-report-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-finance-report-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-finance-reports",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_id = owned.id
        other_id = other.id
        owned_wallet = WalletAccount(account_id=scope["account_id"], user_id=owned_id, system_balance=Decimal("100"))
        other_wallet = WalletAccount(account_id=scope["account_id"], user_id=other_id, system_balance=Decimal("100"))
        session.add_all([owned_wallet, other_wallet])
        session.flush()

        ledger_service = WalletLedgerService(session=session)
        ledger_service.credit_system_balance(
            wallet=owned_wallet,
            account_id=scope["account_id"],
            user_id=owned_id,
            amount=Decimal("10"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Owned recharge",
            reference_type="test_seed",
            reference_id="owned-ledger-seed",
            fund_type="cash",
            is_real_recharge=True,
        )
        ledger_service.credit_system_balance(
            wallet=other_wallet,
            account_id=scope["account_id"],
            user_id=other_id,
            amount=Decimal("20"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Other recharge",
            reference_type="test_seed",
            reference_id="other-ledger-seed",
            fund_type="cash",
            is_real_recharge=True,
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=owned_wallet.id,
                user_id=owned_id,
                request_no="WD-FINANCE-OWNED",
                amount=Decimal("6"),
                cash_amount=Decimal("6"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("6"),
                currency="USD",
                status="submitted",
            )
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=other_wallet.id,
                user_id=other_id,
                request_no="WD-FINANCE-OTHER",
                amount=Decimal("8"),
                cash_amount=Decimal("8"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("8"),
                currency="USD",
                status="submitted",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-finance-reports",
            agency_id=scope["agency_id"],
            role="finance_reader",
        )
        recharge_response = client.get("/api/finance/recharge-records", headers=headers)
        withdrawal_response = client.get("/api/finance/withdrawal-records", headers=headers)
        ledger_response = client.get("/api/finance/wallet-ledgers", headers=headers)

    assert recharge_response.status_code == 200
    assert [item["public_user_id"] for item in recharge_response.json()] == ["owned-route-finance-report-customer"]
    assert withdrawal_response.status_code == 200
    assert [item["public_user_id"] for item in withdrawal_response.json()] == ["owned-route-finance-report-customer"]
    assert ledger_response.status_code == 200
    assert [item["public_user_id"] for item in ledger_response.json()] == ["owned-route-finance-report-customer"]


def test_finance_summary_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-finance-summary")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-finance-summary",
            role_name="finance_reader",
            permissions=["reports.finance"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-finance-summary-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-finance-summary-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-finance-summary",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_wallet = WalletAccount(account_id=scope["account_id"], user_id=owned.id, system_balance=Decimal("50"))
        other_wallet = WalletAccount(account_id=scope["account_id"], user_id=other.id, system_balance=Decimal("80"))
        session.add_all([owned_wallet, other_wallet])
        session.flush()
        ledger_service = WalletLedgerService(session=session)
        ledger_service.credit_system_balance(
            wallet=owned_wallet,
            account_id=scope["account_id"],
            user_id=owned.id,
            amount=Decimal("50"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Owned summary recharge",
            reference_type="test_seed",
            reference_id="owned-summary-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        ledger_service.credit_system_balance(
            wallet=other_wallet,
            account_id=scope["account_id"],
            user_id=other.id,
            amount=Decimal("80"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Other summary recharge",
            reference_type="test_seed",
            reference_id="other-summary-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=owned_wallet.id,
                user_id=owned.id,
                request_no="WD-SUMMARY-OWNED",
                amount=Decimal("20"),
                cash_amount=Decimal("20"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("20"),
                currency="USD",
                status="paid",
            )
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=other_wallet.id,
                user_id=other.id,
                request_no="WD-SUMMARY-OTHER",
                amount=Decimal("30"),
                cash_amount=Decimal("30"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("30"),
                currency="USD",
                status="paid",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/finance/report/summary",
            headers=_auth_headers(
                user_id="member-route-finance-summary",
                agency_id=scope["agency_id"],
                role="finance_reader",
            ),
            params={"agency_id": scope["account_id"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recharge_amount"] == 50.0
    assert payload["withdrawal_amount"] == 20.0
    assert payload["withdrawal_cash_amount"] == 20.0
    assert payload["recharge_count"] == 1
    assert payload["withdrawal_count"] == 1


def test_finance_anomaly_alerts_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-finance-alerts")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-finance-alerts",
            role_name="finance_reader",
            permissions=["reports.finance"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-finance-alerts-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-finance-alerts-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-finance-alerts",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_wallet = WalletAccount(account_id=scope["account_id"], user_id=owned.id, system_balance=Decimal("12000"))
        other_wallet = WalletAccount(account_id=scope["account_id"], user_id=other.id, system_balance=Decimal("13000"))
        session.add_all([owned_wallet, other_wallet])
        session.flush()
        ledger_service = WalletLedgerService(session=session)
        ledger_service.credit_system_balance(
            wallet=owned_wallet,
            account_id=scope["account_id"],
            user_id=owned.id,
            amount=Decimal("12000"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Owned anomaly recharge",
            reference_type="test_seed",
            reference_id="owned-anomaly-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        ledger_service.credit_system_balance(
            wallet=other_wallet,
            account_id=scope["account_id"],
            user_id=other.id,
            amount=Decimal("13000"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Other anomaly recharge",
            reference_type="test_seed",
            reference_id="other-anomaly-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/finance/anomaly-alerts",
            headers=_auth_headers(
                user_id="member-route-finance-alerts",
                agency_id=scope["agency_id"],
                role="finance_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["public_user_id"] for item in payload if item["type"] == "large_recharge"] == [
        "owned-route-finance-alerts-customer"
    ]


def test_legacy_reports_finance_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-legacy-finance-report")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-legacy-finance-report",
            role_name="finance_reader",
            permissions=["reports.finance"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-legacy-finance-report-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-legacy-finance-report-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-legacy-finance-report",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_wallet = WalletAccount(account_id=scope["account_id"], user_id=owned.id, system_balance=Decimal("70"))
        other_wallet = WalletAccount(account_id=scope["account_id"], user_id=other.id, system_balance=Decimal("90"))
        session.add_all([owned_wallet, other_wallet])
        session.flush()
        ledger_service = WalletLedgerService(session=session)
        ledger_service.credit_system_balance(
            wallet=owned_wallet,
            account_id=scope["account_id"],
            user_id=owned.id,
            amount=Decimal("70"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Owned legacy finance recharge",
            reference_type="test_seed",
            reference_id="owned-legacy-finance-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        ledger_service.credit_system_balance(
            wallet=other_wallet,
            account_id=scope["account_id"],
            user_id=other.id,
            amount=Decimal("90"),
            currency="USD",
            transaction_type="manual_recharge",
            source_type="manual_real_recharge",
            note="Other legacy finance recharge",
            reference_type="test_seed",
            reference_id="other-legacy-finance-ledger",
            fund_type="cash",
            is_real_recharge=True,
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=owned_wallet.id,
                user_id=owned.id,
                request_no="WD-LEGACY-FINANCE-OWNED",
                amount=Decimal("15"),
                cash_amount=Decimal("15"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("15"),
                currency="USD",
                status="paid",
            )
        )
        session.add(
            WithdrawalRequest(
                account_id=scope["account_id"],
                wallet_account_id=other_wallet.id,
                user_id=other.id,
                request_no="WD-LEGACY-FINANCE-OTHER",
                amount=Decimal("25"),
                cash_amount=Decimal("25"),
                bonus_amount=Decimal("0"),
                actual_payout_amount=Decimal("25"),
                currency="USD",
                status="paid",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/reports/finance",
            headers=_auth_headers(
                user_id="member-route-legacy-finance-report",
                agency_id=scope["agency_id"],
                role="finance_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recharge_amount"] == 70.0
    assert payload["withdraw_amount"] == 15.0


def test_reports_overview_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-reports-overview")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-reports-overview",
            role_name="report_reader",
            permissions=["reports.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-reports-overview-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-reports-overview-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-reports-overview",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-overview-conversation",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-overview-conversation",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        task_rule = TaskRule(
            account_id=scope["account_id"],
            name="Overview task rule",
            rule_type="event",
            trigger_type="manual",
        )
        session.add(task_rule)
        session.flush()
        session.add_all(
            [
                Ticket(
                    account_id=scope["account_id"],
                    ticket_no="TKT-OVERVIEW-OWNED",
                    user_id=owned.id,
                    site_id=scope["site_id"],
                    ticket_type="help",
                    status="open",
                    priority="normal",
                    title="Owned overview ticket",
                ),
                Ticket(
                    account_id=scope["account_id"],
                    ticket_no="TKT-OVERVIEW-OTHER",
                    user_id=other.id,
                    site_id=scope["site_id"],
                    ticket_type="help",
                    status="open",
                    priority="normal",
                    title="Other overview ticket",
                ),
                MktTaskInstance(
                    account_id=scope["account_id"],
                    user_id=owned.id,
                    rule_id=task_rule.id,
                    task_type="manual",
                    status="pending",
                ),
                MktTaskInstance(
                    account_id=scope["account_id"],
                    user_id=other.id,
                    rule_id=task_rule.id,
                    task_type="manual",
                    status="pending",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/reports",
            headers=_auth_headers(
                user_id="member-route-reports-overview",
                agency_id=scope["agency_id"],
                role="report_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_users"] == 1
    assert payload["total_conversations"] == 1
    assert payload["open_conversations"] == 1
    assert payload["total_tickets"] == 1
    assert payload["open_tickets"] == 1
    assert payload["total_task_instances"] == 1


def test_customer_conversations_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-customer-conversations")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-customer-conversations",
            role_name="conversation_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-customer-conversations-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-customer-conversations-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-customer-conversations",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-customer-conversation",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-customer-conversation",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        owned_id = owned.id
        other_id = other.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-customer-conversations",
            agency_id=scope["agency_id"],
            role="conversation_reader",
        )
        owned_response = client.get(
            f"/api/conversations/by-customer/{owned_id}",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )
        other_response = client.get(
            f"/api/conversations/by-customer/{other_id}",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )

    assert owned_response.status_code == 200
    assert [item["conversation_id"] for item in owned_response.json()] == ["owned-customer-conversation"]
    assert other_response.status_code == 200
    assert other_response.json() == []


def test_customer_summary_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-customer-summary")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-customer-summary",
            role_name="customer_reader",
            permissions=["customers.detail"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-customer-summary-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-customer-summary-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-customer-summary",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.commit()
        owned_id = owned.id
        other_id = other.id

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-customer-summary",
            agency_id=scope["agency_id"],
            role="customer_reader",
        )
        owned_response = client.get(
            f"/api/customers/{owned_id}/summary",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )
        other_response = client.get(
            f"/api/customers/{other_id}/summary",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["customer"]["id"] == owned_id
    assert other_response.status_code == 404


def test_customer_timeline_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-customer-timeline")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-customer-timeline",
            role_name="customer_timeline_reader",
            permissions=["customers.timeline"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-customer-timeline-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-customer-timeline-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-customer-timeline",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-timeline-conversation",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-timeline-conversation",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                Message(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    direction="inbound",
                    content_text="owned timeline message",
                ),
                Message(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    direction="inbound",
                    content_text="other timeline message",
                ),
                WalletLedgerEntry(
                    account_id=scope["account_id"],
                    wallet_account_id="wallet-owned",
                    user_id=owned.id,
                    ledger_type="system",
                    transaction_type="manual_recharge",
                    direction="credit",
                    amount=Decimal("10"),
                    cash_amount=Decimal("10"),
                    bonus_amount=Decimal("0"),
                    task_amount=Decimal("0"),
                    balance_after=Decimal("10"),
                    currency="USD",
                    status="paid",
                    source_type="manual_real_recharge",
                    reference_type="test_seed",
                    reference_id="owned-timeline-ledger",
                    idempotency_key="owned-timeline-ledger-key",
                ),
                WalletLedgerEntry(
                    account_id=scope["account_id"],
                    wallet_account_id="wallet-other",
                    user_id=other.id,
                    ledger_type="system",
                    transaction_type="manual_recharge",
                    direction="credit",
                    amount=Decimal("20"),
                    cash_amount=Decimal("20"),
                    bonus_amount=Decimal("0"),
                    task_amount=Decimal("0"),
                    balance_after=Decimal("20"),
                    currency="USD",
                    status="paid",
                    source_type="manual_real_recharge",
                    reference_type="test_seed",
                    reference_id="other-timeline-ledger",
                    idempotency_key="other-timeline-ledger-key",
                ),
            ]
        )
        session.commit()
        owned_id = owned.id
        other_id = other.id

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-customer-timeline",
            agency_id=scope["agency_id"],
            role="customer_timeline_reader",
        )
        owned_response = client.get(
            f"/api/customers/{owned_id}/timeline",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )
        other_response = client.get(
            f"/api/customers/{other_id}/timeline",
            headers=headers,
            params={"account_id": scope["account_id"]},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["events"]
    assert other_response.status_code == 404


def test_customer_lifecycle_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-customer-lifecycle")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-customer-lifecycle",
            role_name="customer_lifecycle_editor",
            permissions=["customers.edit_lifecycle"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-customer-lifecycle-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-customer-lifecycle-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-customer-lifecycle",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.commit()
        owned_id = owned.id
        other_id = other.id

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-customer-lifecycle",
            agency_id=scope["agency_id"],
            role="customer_lifecycle_editor",
        )
        owned_response = client.patch(
            f"/api/customers/{owned_id}/lifecycle-status",
            headers=headers,
            params={"account_id": scope["account_id"]},
            json={"lifecycle_status": "frozen"},
        )
        other_response = client.patch(
            f"/api/customers/{other_id}/lifecycle-status",
            headers=headers,
            params={"account_id": scope["account_id"]},
            json={"lifecycle_status": "frozen"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["lifecycle_status"] == "frozen"
    assert other_response.status_code == 404

    with db_session_factory() as session:
        owned_user = session.get(AppUser, owned_id)
        other_user = session.get(AppUser, other_id)
        assert owned_user is not None
        assert other_user is not None
        assert owned_user.lifecycle_status == "frozen"
        assert other_user.lifecycle_status == "active"


def test_customer_batch_lifecycle_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-customer-batch-lifecycle")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-customer-batch-lifecycle",
            role_name="customer_batch_lifecycle_editor",
            permissions=["customers.edit_lifecycle"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-customer-batch-lifecycle-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-customer-batch-lifecycle-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-customer-batch-lifecycle",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.commit()
        owned_id = owned.id
        other_id = other.id

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-customer-batch-lifecycle",
            agency_id=scope["agency_id"],
            role="customer_batch_lifecycle_editor",
        )
        response = client.post(
            "/api/customers/batch-lifecycle",
            headers=headers,
            json={
                "customer_ids": [owned_id, other_id],
                "account_id": scope["account_id"],
                "lifecycle_status": "blacklisted",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_count"] == 1
    assert payload["customer_ids"] == [owned_id]

    with db_session_factory() as session:
        owned_user = session.get(AppUser, owned_id)
        other_user = session.get(AppUser, other_id)
        assert owned_user is not None
        assert other_user is not None
        assert owned_user.lifecycle_status == "blacklisted"
        assert other_user.lifecycle_status == "active"


def test_conversation_messages_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-messages")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-messages",
            role_name="conversation_detail_reader",
            permissions=["conversations.detail"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-messages-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-messages-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-messages",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-messages",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-messages",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                Message(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    direction="inbound",
                    content_text="owned detail message",
                ),
                Message(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    direction="inbound",
                    content_text="other detail message",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-messages",
            agency_id=scope["agency_id"],
            role="conversation_detail_reader",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-messages/messages",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-messages/messages",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert [item["original_text"] for item in owned_response.json()] == ["owned detail message"]
    assert other_response.status_code == 404


def test_conversation_timeline_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-timeline")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-timeline",
            role_name="conversation_timeline_reader",
            permissions=["conversations.detail"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-timeline-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-timeline-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-timeline",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-timeline",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-timeline",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                MessageEvent(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    event_type="sent",
                    provider_event_id="owned-route-timeline-event",
                    payload={"detail": "owned"},
                ),
                MessageEvent(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    event_type="sent",
                    provider_event_id="other-route-timeline-event",
                    payload={"detail": "other"},
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-timeline",
            agency_id=scope["agency_id"],
            role="conversation_timeline_reader",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-timeline/timeline",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-timeline/timeline",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert owned_response.json()
    assert other_response.status_code == 404


def test_conversation_tags_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-tags")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-tags",
            role_name="conversation_tags_editor",
            permissions=["conversations.tags"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-tags-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-tags-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-tags",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-tags",
            customer_id=owned.id,
            status="open",
            tags=["owned"],
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-tags",
            customer_id=other.id,
            status="open",
            tags=["other"],
        )
        session.add_all([owned_conversation, other_conversation])
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-tags",
            agency_id=scope["agency_id"],
            role="conversation_tags_editor",
        )
        owned_get = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-tags/tags",
            headers=headers,
        )
        owned_put = client.put(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-tags/tags",
            headers=headers,
            json={"tags": ["updated"]},
        )
        other_get = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-tags/tags",
            headers=headers,
        )
        other_put = client.put(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-tags/tags",
            headers=headers,
            json={"tags": ["should-not-work"]},
        )

    assert owned_get.status_code == 200
    assert owned_get.json()["tags"] == ["owned"]
    assert owned_put.status_code == 200
    assert owned_put.json()["tags"] == ["updated"]
    assert other_get.status_code == 404
    assert other_put.status_code == 404


def test_conversation_assignment_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-assignment")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-assignment",
            role_name="conversation_transfer_editor",
            permissions=["conversations.transfer"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-assignment-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-assignment-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-assignment",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add(
            Agent(
                account_id=scope["account_id"],
                agent_key="scope-agent-1",
                display_name="Scope Agent",
                status="online",
                is_active=True,
                user_type="agent_member",
                agency_id=scope["agency_id"],
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-assignment",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-assignment",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-assignment",
            agency_id=scope["agency_id"],
            role="conversation_transfer_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-assignment/assignment",
            headers=headers,
            json={"agent_id": "scope-agent-1", "reason": "scope-check"},
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-assignment/assignment",
            headers=headers,
            json={"agent_id": "scope-agent-1", "reason": "scope-check"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["assigned_agent_id"] == "scope-agent-1"
    assert other_response.status_code == 404


def test_conversation_batch_assign_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-batch")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-batch",
            role_name="conversation_batch_editor",
            permissions=["conversations.batch"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-batch-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-batch-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-batch",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add(
            Agent(
                account_id=scope["account_id"],
                agent_key="scope-batch-agent-1",
                display_name="Scope Batch Agent",
                status="online",
                is_active=True,
                user_type="agent_member",
                agency_id=scope["agency_id"],
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-batch",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-batch",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-batch",
            agency_id=scope["agency_id"],
            role="conversation_batch_editor",
        )
        response = client.post(
            "/api/conversations/batch-assign",
            headers=headers,
            json={
                "conversation_ids": [
                    f"{scope['account_id']}:owned-route-conversation-batch",
                    f"{scope['account_id']}:other-route-conversation-batch",
                ],
                "agent_id": "scope-batch-agent-1",
                "reason": "scope-check",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 1
    assert [item["status"] for item in payload["results"]] == ["success", "failed"]


def test_conversation_batch_handover_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-batch-handover")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-batch-handover",
            role_name="conversation_batch_editor",
            permissions=["conversations.batch"],
        )
        session.flush()
        handover_agent = session.scalar(
            select(Agent).where(
                Agent.account_id == scope["account_id"],
                Agent.agent_key == "member-route-conversation-batch-handover",
            )
        )
        assert handover_agent is not None
        handover_agent.status = "online"
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-batch-handover-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-batch-handover-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-batch-handover",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-batch-handover",
                    customer_id=owned.id,
                    status="open",
                    management_mode="ai_managed",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-batch-handover",
                    customer_id=other.id,
                    status="open",
                    management_mode="ai_managed",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-batch-handover",
            agency_id=scope["agency_id"],
            role="conversation_batch_editor",
        )
        response = client.post(
            "/api/conversations/batch-handover",
            headers=headers,
            json={
                "conversation_ids": [
                    f"{scope['account_id']}:owned-route-conversation-batch-handover",
                    f"{scope['account_id']}:other-route-conversation-batch-handover",
                ],
                "reason": "scope-check",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 1
    assert [item["status"] for item in payload["results"]] == ["success", "failed"]


def test_conversation_batch_restore_ai_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-batch-restore")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-batch-restore",
            role_name="conversation_batch_editor",
            permissions=["conversations.batch"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-batch-restore-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-batch-restore-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-batch-restore",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-batch-restore",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-batch-restore",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-batch-restore",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-batch-restore",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-batch-restore",
            agency_id=scope["agency_id"],
            role="conversation_batch_editor",
        )
        response = client.post(
            "/api/conversations/batch-restore-ai",
            headers=headers,
            json={
                "conversation_ids": [
                    f"{scope['account_id']}:owned-route-conversation-batch-restore",
                    f"{scope['account_id']}:other-route-conversation-batch-restore",
                ],
                "reason": "scope-check",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 1
    assert [item["status"] for item in payload["results"]] == ["success", "failed"]


def test_conversation_batch_close_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-batch-close")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-batch-close",
            role_name="conversation_batch_editor",
            permissions=["conversations.batch"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-batch-close-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-batch-close-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-batch-close",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-batch-close",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-batch-close",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-batch-close",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-batch-close",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-batch-close",
            agency_id=scope["agency_id"],
            role="conversation_batch_editor",
        )
        response = client.post(
            "/api/conversations/batch-close",
            headers=headers,
            json={
                "conversation_ids": [
                    f"{scope['account_id']}:owned-route-conversation-batch-close",
                    f"{scope['account_id']}:other-route-conversation-batch-close",
                ],
                "reason": "scope-check",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 1
    assert [item["status"] for item in payload["results"]] == ["success", "failed"]


def test_conversation_close_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-close")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-close",
            role_name="conversation_close_editor",
            permissions=["conversations.close"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-close-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-close-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-close",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-close",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-close",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-close",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-close",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-close",
            agency_id=scope["agency_id"],
            role="conversation_close_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-close/close",
            headers=headers,
            json={"agent_id": "member-route-conversation-close", "reason": "scope-check"},
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-close/close",
            headers=headers,
            json={"agent_id": "member-route-conversation-close", "reason": "scope-check"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["status"] == "closed"
    assert other_response.status_code == 404


def test_conversation_reopen_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-reopen")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-reopen",
            role_name="conversation_reopen_editor",
            permissions=["conversations.reopen"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-reopen-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-reopen-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-reopen",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-reopen",
                    customer_id=owned.id,
                    status="closed",
                    management_mode="ai_managed",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-reopen",
                    customer_id=other.id,
                    status="closed",
                    management_mode="ai_managed",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-reopen",
            agency_id=scope["agency_id"],
            role="conversation_reopen_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-reopen/reopen",
            headers=headers,
            json={"agent_id": "member-route-conversation-reopen", "reason": "scope-check"},
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-reopen/reopen",
            headers=headers,
            json={"agent_id": "member-route-conversation-reopen", "reason": "scope-check"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["status"] == "open"
    assert other_response.status_code == 404


def test_conversation_media_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-media")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-media",
            role_name="conversation_reply_editor",
            permissions=["conversations.reply"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-media-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-media-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-media",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-media",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-media",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-media",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="member-route-conversation-media",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-media",
            agency_id=scope["agency_id"],
            role="conversation_reply_editor",
        )
        payload = {
            "asset_id": "missing-media-asset",
            "caption": "scope-check",
            "agent_id": "member-route-conversation-media",
        }
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-media/messages/media",
            headers=headers,
            json=payload,
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-media/messages/media",
            headers=headers,
            json=payload,
        )

    assert owned_response.status_code == 404
    assert "Media asset" in owned_response.json()["detail"]
    assert other_response.status_code == 404
    assert other_response.json()["detail"] == "Conversation not found."


def test_conversation_ai_preview_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-ai-preview")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-ai-preview",
            role_name="conversation_ai_preview_reader",
            permissions=["conversations.ai_preview"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-ai-preview-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-ai-preview-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-ai-preview",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-ai-preview",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-ai-preview",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                Message(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    direction="inbound",
                    content_text="owned ai preview message",
                ),
                Message(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    direction="inbound",
                    content_text="other ai preview message",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-ai-preview",
            agency_id=scope["agency_id"],
            role="conversation_ai_preview_reader",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-ai-preview/ai-preview",
            headers=headers,
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-ai-preview/ai-preview",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert "preview_text" in owned_response.json()
    assert other_response.status_code == 404


def test_assigned_conversations_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-assigned-conversations")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="scope-assigned-agent-1",
            role_name="conversation_assigned_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-assigned-conversations-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-assigned-conversations-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="scope-assigned-agent-1",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-assigned-conversations",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="scope-assigned-agent-1",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-assigned-conversations",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id="scope-assigned-agent-1",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="scope-assigned-agent-1",
            agency_id=scope["agency_id"],
            role="conversation_assigned_reader",
        )
        response = client.get(
            "/api/conversations/assigned",
            headers=headers,
            params={
                "account_id": scope["account_id"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["conversation_id"] for item in payload] == ["owned-route-assigned-conversations"]


def test_conversation_wake_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-wake")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-wake",
            role_name="conversation_wake_editor",
            permissions=["conversations.wake"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-wake-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-wake-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-wake",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-wake",
                    customer_id=owned.id,
                    status="open",
                    is_sleeping=True,
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-wake",
                    customer_id=other.id,
                    status="open",
                    is_sleeping=True,
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-wake",
            agency_id=scope["agency_id"],
            role="conversation_wake_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-wake/wake",
            headers=headers,
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-wake/wake",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["conversation_id"] == "owned-route-conversation-wake"
    assert other_response.status_code == 404


def test_conversation_batch_metadata_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-metadata")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-metadata",
            role_name="conversation_metadata_reader",
            permissions=["conversations.detail"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-metadata-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-metadata-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-metadata",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-metadata",
                    customer_id=owned.id,
                    status="open",
                    tags=["owned-metadata"],
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-metadata",
                    customer_id=other.id,
                    status="open",
                    tags=["other-metadata"],
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-metadata",
            agency_id=scope["agency_id"],
            role="conversation_metadata_reader",
        )
        response = client.get(
            "/api/conversations/metadata/batch",
            headers=headers,
            params={
                "ids": (
                    f"{scope['account_id']}:owned-route-conversation-metadata,"
                    f"{scope['account_id']}:other-route-conversation-metadata"
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert payload[0]["conversation_id"] == "owned-route-conversation-metadata"
    assert payload[0]["tags"] == ["owned-metadata"]
    assert payload[0]["error"] is None
    assert payload[1]["conversation_id"] == "other-route-conversation-metadata"
    assert payload[1]["tags"] == []
    assert payload[1]["error"] == "404: Conversation not found."


def test_conversation_translate_outbound_preview_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-translate-preview")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-translate-preview",
            role_name="conversation_translate_editor",
            permissions=["conversations.translate"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-translate-preview-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-translate-preview-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-translate-preview",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-translate-preview",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-translate-preview",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-translate-preview",
            agency_id=scope["agency_id"],
            role="conversation_translate_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-translate-preview/messages/translate-outbound",
            headers=headers,
            json={"text": "hello", "target_language": "zh-CN"},
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-translate-preview/messages/translate-outbound",
            headers=headers,
            json={"text": "hello", "target_language": "zh-CN"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["original_text"] == "hello"
    assert other_response.status_code == 404


def test_platform_withdrawal_status_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-platform-withdrawal-status")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-platform-withdrawal-status",
            role_name="withdrawal_status_editor",
            permissions=["finance.approve_withdrawal"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-platform-withdrawal-status-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-platform-withdrawal-status-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-platform-withdrawal-status",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=owned.id,
            request_no="WD-SCOPE-OWNED-STATUS",
        )
        other_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=other.id,
            request_no="WD-SCOPE-OTHER-STATUS",
        )
        owned_withdrawal_id = owned_withdrawal.id
        other_withdrawal_id = other_withdrawal.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-platform-withdrawal-status",
            agency_id=scope["agency_id"],
            role="withdrawal_status_editor",
        )
        owned_response = client.post(
            f"/api/platform/withdrawals/{owned_withdrawal_id}/status",
            headers=headers,
            json={"status": "reviewing", "note": "owned ok"},
        )
        other_response = client.post(
            f"/api/platform/withdrawals/{other_withdrawal_id}/status",
            headers=headers,
            json={"status": "reviewing", "note": "other blocked"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["status"] == "reviewing"
    assert other_response.status_code == 404


def test_platform_withdrawal_duplicate_accounts_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-platform-withdrawal-duplicate")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-platform-withdrawal-duplicate",
            role_name="withdrawal_duplicate_reader",
            permissions=["withdrawal.duplicate_account.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-platform-withdrawal-duplicate-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-platform-withdrawal-duplicate-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-platform-withdrawal-duplicate",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=owned.id,
            request_no="WD-SCOPE-OWNED-DUP",
        )
        other_withdrawal = _seed_withdrawal(
            session,
            account_id=scope["account_id"],
            user_id=other.id,
            request_no="WD-SCOPE-OTHER-DUP",
        )
        owned_withdrawal.account_fingerprint = "owned-fingerprint"
        owned_withdrawal.account_no_masked = "****1111"
        other_withdrawal.account_fingerprint = "other-fingerprint"
        other_withdrawal.account_no_masked = "****2222"
        owned_withdrawal_id = owned_withdrawal.id
        other_withdrawal_id = other_withdrawal.id
        session.add_all([owned_withdrawal, other_withdrawal])
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-platform-withdrawal-duplicate",
            agency_id=scope["agency_id"],
            role="withdrawal_duplicate_reader",
        )
        owned_response = client.get(
            f"/api/platform/withdrawals/{owned_withdrawal_id}/duplicate-accounts",
            headers=headers,
        )
        other_response = client.get(
            f"/api/platform/withdrawals/{other_withdrawal_id}/duplicate-accounts",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["withdrawalId"] == owned_withdrawal_id
    assert other_response.status_code == 404


def test_platform_site_config_get_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-config-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-config-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-config-reader",
            role_name="site_config_editor",
            permissions=["sites.brand_config"],
        )
        session.add(
            H5SiteConfig(
                site_id=other_scope["site_id"],
                primary_color="#123456",
                footer_text="other-config",
                domain="other.example.com",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            f"/api/platform/sites/{other_scope['site_id']}/config",
            headers=_auth_headers(
                user_id="member-route-site-config-reader",
                agency_id=owned_scope["agency_id"],
                role="site_config_editor",
            ),
        )

    assert response.status_code == 403


def test_platform_site_config_update_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-config-update-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-config-update-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-config-updater",
            role_name="site_config_editor",
            permissions=["sites.brand_config"],
        )
        session.add(
            H5SiteConfig(
                site_id=other_scope["site_id"],
                primary_color="#654321",
                footer_text="before-update",
                domain="before.example.com",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.put(
            f"/api/platform/sites/{other_scope['site_id']}/config",
            headers=_auth_headers(
                user_id="member-route-site-config-updater",
                agency_id=owned_scope["agency_id"],
                role="site_config_editor",
            ),
            json={"footer_text": "should-not-update"},
        )

    assert response.status_code == 403


def test_platform_site_clone_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-clone-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-clone-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-clone",
            role_name="site_clone_editor",
            permissions=["sites.clone"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            f"/api/platform/sites/{other_scope['site_id']}/clone",
            headers=_auth_headers(
                user_id="member-route-site-clone",
                agency_id=owned_scope["agency_id"],
                role="site_clone_editor",
            ),
            json={
                "new_site_key": "cloned-site-cross-account",
                "new_brand_name": "Cloned Cross Account",
                "new_domain": "cloned-cross-account.example.com",
            },
        )

    assert response.status_code == 403


def test_platform_site_export_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-export-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-export-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-export",
            role_name="site_deploy_editor",
            permissions=["sites.deploy"],
        )
        session.add(
            H5SiteConfig(
                site_id=other_scope["site_id"],
                primary_color="#abcdef",
                footer_text="export-me",
                domain="export.example.com",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            f"/api/platform/sites/{other_scope['site_id']}/export-config",
            headers=_auth_headers(
                user_id="member-route-site-export",
                agency_id=owned_scope["agency_id"],
                role="site_deploy_editor",
            ),
        )

    assert response.status_code == 403


def test_platform_site_update_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-update-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-update-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-update",
            role_name="site_editor",
            permissions=["sites.edit"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.put(
            f"/api/platform/sites/{other_scope['site_id']}",
            headers=_auth_headers(
                user_id="member-route-site-update",
                agency_id=owned_scope["agency_id"],
                role="site_editor",
            ),
            json={"brand_name": "should-not-update"},
        )

    assert response.status_code == 403


def test_platform_site_delete_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-delete-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-delete-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-delete",
            role_name="site_delete_editor",
            permissions=["sites.delete"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.delete(
            f"/api/platform/sites/{other_scope['site_id']}",
            headers=_auth_headers(
                user_id="member-route-site-delete",
                agency_id=owned_scope["agency_id"],
                role="site_delete_editor",
            ),
        )

    assert response.status_code == 403


def test_platform_site_batch_update_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-batch-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-site-batch-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-batch",
            role_name="site_batch_editor",
            permissions=["sites.edit"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/platform/sites/batch-update",
            headers=_auth_headers(
                user_id="member-route-site-batch",
                agency_id=owned_scope["agency_id"],
                role="site_batch_editor",
            ),
            json={"site_ids": [other_scope["site_id"]], "action": "pause"},
        )

    assert response.status_code == 403


def test_platform_site_import_route_uses_actor_account_scope_not_actor_id(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-site-import-owned")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-site-import",
            role_name="site_deploy_editor",
            permissions=["sites.deploy"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            "/api/platform/sites/import-config",
            headers=_auth_headers(
                user_id="member-route-site-import",
                agency_id=owned_scope["agency_id"],
                role="site_deploy_editor",
            ),
            json={
                "site": {
                    "site_key": "imported-scope-site",
                    "domain": "imported-scope-site.example.com",
                    "brand_name": "Imported Scope Site",
                },
                "config": {
                    "primary_color": "#112233",
                    "footer_text": "imported-footer",
                },
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["account_id"] == owned_scope["account_id"]
    assert payload["account_id"] != "member-route-site-import"


def test_platform_user_delete_route_rejects_cross_account_access(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        owned_scope = _seed_scope(session, agency_id="agency-w3-route-user-delete-owned")
        other_scope = _seed_scope(session, agency_id="agency-w3-route-user-delete-other")
        _seed_member(
            session,
            agency_id=owned_scope["agency_id"],
            account_id=owned_scope["account_id"],
            member_id="member-route-user-delete",
            role_name="user_delete_editor",
            permissions=["users.delete"],
        )
        other_user = _seed_customer(
            session,
            account_id=other_scope["account_id"],
            site_id=other_scope["site_id"],
            public_user_id="other-route-user-delete-customer",
        )
        other_user_id = other_user.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.delete(
            f"/api/platform/users/{other_user_id}",
            headers=_auth_headers(
                user_id="member-route-user-delete",
                agency_id=owned_scope["agency_id"],
                role="user_delete_editor",
            ),
        )

    assert response.status_code == 403


def test_conversation_notes_list_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-notes-list")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-notes-list",
            role_name="conversation_notes_editor",
            permissions=["conversations.notes"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-notes-list-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-notes-list-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-notes-list",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-notes-list",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-notes-list",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.add(
            ConversationNote(
                account_id=scope["account_id"],
                conversation_id="other-route-conversation-notes-list",
                content="other note",
                agent_id="seed-agent",
                agent_name="Seed Agent",
            )
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-notes-list",
            agency_id=scope["agency_id"],
            role="conversation_notes_editor",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-notes-list/notes",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-notes-list/notes",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert other_response.status_code == 404


def test_conversation_notes_create_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-notes-create")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-notes-create",
            role_name="conversation_notes_editor",
            permissions=["conversations.notes"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-notes-create-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-notes-create-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-notes-create",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-notes-create",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-notes-create",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-notes-create",
            agency_id=scope["agency_id"],
            role="conversation_notes_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-notes-create/notes",
            headers=headers,
            json={"content": "owned note"},
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-notes-create/notes",
            headers=headers,
            json={"content": "other note"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["content"] == "owned note"
    assert other_response.status_code == 404


def test_conversation_poll_route_respects_customer_ownership_scope_for_messages(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-poll-messages")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-poll-messages",
            role_name="conversation_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-poll-messages-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-poll-messages-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-poll-messages",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-poll-messages",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-poll-messages",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                Message(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    direction="inbound",
                    content_text="owned poll message",
                ),
                Message(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    direction="inbound",
                    content_text="other poll message",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/conversations/poll?since=2000-01-01T00:00:00Z",
            headers=_auth_headers(
                user_id="member-route-conversation-poll-messages",
                agency_id=scope["agency_id"],
                role="conversation_reader",
            ),
        )

    assert response.status_code == 200
    events = response.json()["events"]
    new_message_events = [item for item in events if item["event"] == "new_message"]
    assert [item["conversation_id"] for item in new_message_events] == [
        "owned-route-conversation-poll-messages"
    ]


def test_conversation_poll_route_respects_customer_ownership_scope_for_handovers(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-poll-handovers")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-poll-handovers",
            role_name="conversation_reader",
            permissions=["conversations.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-poll-handovers-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-poll-handovers-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-poll-handovers",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-poll-handovers",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-poll-handovers",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                HandoverLog(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    triggered_by_type="agent",
                    triggered_by_id="seed-agent",
                    from_mode="ai_managed",
                    to_mode="human_managed",
                ),
                HandoverLog(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    triggered_by_type="agent",
                    triggered_by_id="seed-agent",
                    from_mode="ai_managed",
                    to_mode="human_managed",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/conversations/poll?since=2000-01-01T00:00:00Z",
            headers=_auth_headers(
                user_id="member-route-conversation-poll-handovers",
                agency_id=scope["agency_id"],
                role="conversation_reader",
            ),
        )

    assert response.status_code == 200
    handover_events = [item for item in response.json()["events"] if item["event"] == "handover"]
    assert [item["conversation_id"] for item in handover_events] == [
        "owned-route-conversation-poll-handovers"
    ]


def test_conversation_forward_route_rejects_unowned_source_conversation(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-forward-source")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-forward-source",
            role_name="conversation_replier",
            permissions=["conversations.reply"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-forward-source-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-forward-source-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-forward-source",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-forward-source",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-forward-source",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        forwarded_message = Message(
            account_id=scope["account_id"],
            conversation_id=other_conversation.id,
            direction="inbound",
            content_text="other source message",
        )
        session.add(forwarded_message)
        session.flush()
        forwarded_message_id = forwarded_message.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-forward-source/messages/{forwarded_message_id}/forward",
            headers=_auth_headers(
                user_id="member-route-conversation-forward-source",
                agency_id=scope["agency_id"],
                role="conversation_replier",
            ),
            json={"target_conversation_id": "owned-route-conversation-forward-source"},
        )

    assert response.status_code == 404


def test_conversation_forward_route_rejects_unowned_target_conversation(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-forward-target")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-forward-target",
            role_name="conversation_replier",
            permissions=["conversations.reply"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-forward-target-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-forward-target-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-forward-target",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-forward-target",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-forward-target",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        forwarded_message = Message(
            account_id=scope["account_id"],
            conversation_id=owned_conversation.id,
            direction="inbound",
            content_text="owned source message",
        )
        session.add(forwarded_message)
        session.flush()
        forwarded_message_id = forwarded_message.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-forward-target/messages/{forwarded_message_id}/forward",
            headers=_auth_headers(
                user_id="member-route-conversation-forward-target",
                agency_id=scope["agency_id"],
                role="conversation_replier",
            ),
            json={"target_conversation_id": "other-route-conversation-forward-target"},
        )

    assert response.status_code == 404


def test_conversation_message_search_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-search")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-search",
            role_name="conversation_reader",
            permissions=["conversations.detail"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-search-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-search-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-search",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-search",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-search",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        session.add_all(
            [
                Message(
                    account_id=scope["account_id"],
                    conversation_id=owned_conversation.id,
                    direction="inbound",
                    content_text="owned searchable text",
                ),
                Message(
                    account_id=scope["account_id"],
                    conversation_id=other_conversation.id,
                    direction="inbound",
                    content_text="other searchable text",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-search",
            agency_id=scope["agency_id"],
            role="conversation_reader",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-search/messages/search?q=owned",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-search/messages/search?q=other",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert len(owned_response.json()) == 1
    assert other_response.status_code == 404


def test_conversation_sentiment_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-sentiment")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-sentiment",
            role_name="conversation_reader",
            permissions=["conversations.sentiment"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-sentiment-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-sentiment-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-sentiment",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-sentiment",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-sentiment",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-sentiment",
            agency_id=scope["agency_id"],
            role="conversation_reader",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-sentiment/sentiment",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-sentiment/sentiment",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["sentiment"] == "neutral"
    assert other_response.status_code == 404


def test_conversation_sla_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-sla")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-sla",
            role_name="conversation_reader",
            permissions=["conversations.sla"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-sla-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-sla-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-sla",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-sla",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-sla",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-sla",
            agency_id=scope["agency_id"],
            role="conversation_reader",
        )
        owned_response = client.get(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-sla/sla",
            headers=headers,
        )
        other_response = client.get(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-sla/sla",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert "waiting_seconds" in owned_response.json()
    assert other_response.status_code == 404


def test_conversation_translate_message_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-translate-message")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-translate-message",
            role_name="conversation_translate_editor",
            permissions=["conversations.translate"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-translate-message-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-translate-message-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-translate-message",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        owned_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="owned-route-conversation-translate-message",
            customer_id=owned.id,
            status="open",
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-translate-message",
            customer_id=other.id,
            status="open",
        )
        session.add_all([owned_conversation, other_conversation])
        session.flush()
        owned_message = Message(
            account_id=scope["account_id"],
            conversation_id=owned_conversation.id,
            direction="inbound",
            content_text="bonjour owned translation message",
            language_code="fr",
        )
        other_message = Message(
            account_id=scope["account_id"],
            conversation_id=other_conversation.id,
            direction="inbound",
            content_text="bonjour other translation message",
            language_code="fr",
        )
        session.add_all([owned_message, other_message])
        session.flush()
        owned_message_id = owned_message.id
        other_message_id = other_message.id
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-translate-message",
            agency_id=scope["agency_id"],
            role="conversation_translate_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-translate-message/messages/{owned_message_id}/translate",
            headers=headers,
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-translate-message/messages/{other_message_id}/translate",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert "translated_text" in owned_response.json()
    assert other_response.status_code == 404


def test_conversation_batch_translate_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-translate-batch")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-translate-batch",
            role_name="conversation_translate_editor",
            permissions=["conversations.translate"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-translate-batch-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-translate-batch-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-translate-batch",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-translate-batch",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-route-conversation-translate-batch",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-translate-batch",
            agency_id=scope["agency_id"],
            role="conversation_translate_editor",
        )
        owned_response = client.post(
            f"/api/conversations/{scope['account_id']}/owned-route-conversation-translate-batch/messages/translate-batch",
            headers=headers,
        )
        other_response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-translate-batch/messages/translate-batch",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert "translations" in owned_response.json()
    assert other_response.status_code == 404


def test_conversation_outbound_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-route-conversation-outbound")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-route-conversation-outbound",
            role_name="conversation_replier",
            permissions=["conversations.reply"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-route-conversation-outbound-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-route-conversation-outbound-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-route-conversation-outbound",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        other_conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="other-route-conversation-outbound",
            customer_id=other.id,
            status="open",
            management_mode="human_managed",
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-route-conversation-outbound",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                ),
                other_conversation,
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-route-conversation-outbound",
            agency_id=scope["agency_id"],
            role="conversation_replier",
        )
        response = client.post(
            f"/api/conversations/{scope['account_id']}/other-route-conversation-outbound/messages/outbound",
            headers=headers,
            json={"text": "blocked outbound", "agent_id": "member-route-conversation-outbound"},
        )

    assert response.status_code == 404


def test_runtime_conversation_ai_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-runtime-ai-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-runtime-ai-scope",
            role_name="conversation_handover_editor",
            permissions=["conversations.handover"],
        )
        session.flush()
        agent = session.scalar(
            select(Agent).where(
                Agent.account_id == scope["account_id"],
                Agent.agent_key == "member-runtime-ai-scope",
            )
        )
        assert agent is not None
        agent.status = "online"
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-runtime-ai-scope-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-runtime-ai-scope-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-runtime-ai-scope",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-runtime-ai-scope",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    ai_enabled=False,
                    assigned_agent_id=agent.id,
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-runtime-ai-scope",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    ai_enabled=False,
                    assigned_agent_id=agent.id,
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-runtime-ai-scope",
            agency_id=scope["agency_id"],
            role="conversation_handover_editor",
        )
        owned_response = client.post(
            f"/api/runtime/conversations/owned-runtime-ai-scope/ai?account_id={scope['account_id']}",
            headers=headers,
            json={"enabled": True, "agent_id": "member-runtime-ai-scope"},
        )
        other_response = client.post(
            f"/api/runtime/conversations/other-runtime-ai-scope/ai?account_id={scope['account_id']}",
            headers=headers,
            json={"enabled": True, "agent_id": "member-runtime-ai-scope"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["conversation_id"] == "owned-runtime-ai-scope"
    assert other_response.status_code == 404


def test_runtime_conversation_ai_status_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-runtime-ai-status-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-runtime-ai-status-scope",
            role_name="runtime_reader",
            permissions=["runtime.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-runtime-ai-status-scope-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-runtime-ai-status-scope-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-runtime-ai-status-scope",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-runtime-ai-status-scope",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-runtime-ai-status-scope",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-runtime-ai-status-scope",
            agency_id=scope["agency_id"],
            role="runtime_reader",
        )
        owned_response = client.get(
            f"/api/runtime/conversations/owned-runtime-ai-status-scope/ai-status?account_id={scope['account_id']}",
            headers=headers,
        )
        other_response = client.get(
            f"/api/runtime/conversations/other-runtime-ai-status-scope/ai-status?account_id={scope['account_id']}",
            headers=headers,
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["conversation_id"] == "owned-runtime-ai-status-scope"
    assert other_response.status_code == 404


def test_runtime_conversation_handover_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-runtime-handover-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-runtime-handover-scope",
            role_name="conversation_handover_editor",
            permissions=["conversations.handover"],
        )
        session.flush()
        agent = session.scalar(
            select(Agent).where(
                Agent.account_id == scope["account_id"],
                Agent.agent_key == "member-runtime-handover-scope",
            )
        )
        assert agent is not None
        agent.status = "online"
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-runtime-handover-scope-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-runtime-handover-scope-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-runtime-handover-scope",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-runtime-handover-scope",
                    customer_id=owned.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id=agent.id,
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-runtime-handover-scope",
                    customer_id=other.id,
                    status="open",
                    management_mode="human_managed",
                    assigned_agent_id=agent.id,
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-runtime-handover-scope",
            agency_id=scope["agency_id"],
            role="conversation_handover_editor",
        )
        owned_response = client.post(
            f"/api/runtime/conversations/owned-runtime-handover-scope/handover?account_id={scope['account_id']}",
            headers=headers,
            json={"management_mode": "paused", "agent_id": "member-runtime-handover-scope", "reason": "scope-check"},
        )
        other_response = client.post(
            f"/api/runtime/conversations/other-runtime-handover-scope/handover?account_id={scope['account_id']}",
            headers=headers,
            json={"management_mode": "paused", "agent_id": "member-runtime-handover-scope", "reason": "scope-check"},
        )

    assert owned_response.status_code == 200
    assert owned_response.json()["conversation_id"] == "owned-runtime-handover-scope"
    assert other_response.status_code == 404


def test_runtime_state_route_respects_customer_ownership_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-runtime-state-scope")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-runtime-state-scope",
            role_name="runtime_reader",
            permissions=["runtime.view"],
        )
        owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-runtime-state-scope-customer",
        )
        other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-runtime-state-scope-customer",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-runtime-state-scope",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.add_all(
            [
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="owned-runtime-state-scope",
                    customer_id=owned.id,
                    status="open",
                ),
                Conversation(
                    account_id=scope["account_id"],
                    external_conversation_id="other-runtime-state-scope",
                    customer_id=other.id,
                    status="open",
                ),
            ]
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        response = client.get(
            "/api/runtime/state",
            headers=_auth_headers(
                user_id="member-runtime-state-scope",
                agency_id=scope["agency_id"],
                role="runtime_reader",
            ),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["conversation_id"] for item in payload["conversations"]] == [
        "owned-runtime-state-scope"
    ]


def test_runtime_set_agent_status_route_accepts_implicit_account_scope_for_accessible_agent(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session, agency_id="agency-w3-runtime-agent-status")
        _seed_member(
            session,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            member_id="member-runtime-agent-status",
            role_name="runtime_editor",
            permissions=["runtime.edit"],
        )
        session.commit()

    with _build_strict_client(db_session_factory) as client:
        headers = _auth_headers(
            user_id="member-runtime-agent-status",
            agency_id=scope["agency_id"],
            role="runtime_editor",
        )
        response = client.post(
            "/api/runtime/agents/member-runtime-agent-status/status",
            headers=headers,
            json={"status": "away"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "member-runtime-agent-status"
    assert payload["status"] == "away"

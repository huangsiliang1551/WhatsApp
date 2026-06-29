from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import ActorRole, RequestActor
from app.db.models import (
    AIHandoverPolicy,
    Account,
    Agency,
    AppUser,
    Conversation,
    ConversationAssignment,
    CustomerOwnershipAssignment,
    DataScopeGrant,
    H5Site,
    HandoverQueue,
    PermissionGrant,
    StaffTeam,
    StaffTeamAssignment,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
)
from app.services.conversation_handover_service import ConversationHandoverService
from app.services.customer_ownership_service import CustomerOwnershipService
from app.services.data_scope_filter_service import DataScopeFilterService
from app.services.effective_access_service import EffectiveAccessService


def _seed_scope(session: Session) -> dict[str, str]:
    account_id = "acc-w3"
    agency_id = "agency-w3"
    site_id = "site-w3"
    session.add(Account(account_id=account_id, display_name="W3 Account", provider_type="mock"))
    session.add(
        Agency(
            id=agency_id,
            name="W3 Agency",
            username="agency-w3-owner",
            password_hash="placeholder",
        )
    )
    session.add(
        H5Site(
            id=site_id,
            account_id=account_id,
            site_key="site-w3-key",
            domain="w3.example.com",
            brand_name="W3 Brand",
            agency_id=agency_id,
        )
    )
    session.flush()
    return {"account_id": account_id, "agency_id": agency_id, "site_id": site_id}


def _seed_customer(
    session: Session,
    *,
    account_id: str,
    site_id: str,
    public_user_id: str,
) -> AppUser:
    user = AppUser(
        account_id=account_id,
        public_user_id=public_user_id,
        registration_site_id=site_id,
        display_name=public_user_id,
        lifecycle_status="active",
    )
    session.add(user)
    session.flush()
    return user


def _seed_wallet_artifacts(
    session: Session,
    *,
    account_id: str,
    customer_id: str,
    owner_staff_id_snapshot: str | None = None,
    supervisor_id_snapshot: str | None = None,
    team_id_snapshot: str | None = None,
    agency_id_snapshot: str | None = None,
    site_id_snapshot: str | None = None,
) -> tuple[WalletLedgerEntry, WithdrawalRequest]:
    wallet = WalletAccount(account_id=account_id, user_id=customer_id, system_balance=Decimal("100"))
    session.add(wallet)
    session.flush()
    ledger = WalletLedgerEntry(
        account_id=account_id,
        wallet_account_id=wallet.id,
        user_id=customer_id,
        ledger_type="recharge",
        transaction_type="credit",
        direction="credit",
        amount=Decimal("25"),
        currency="USD",
        owner_staff_id_snapshot=owner_staff_id_snapshot,
        supervisor_id_snapshot=supervisor_id_snapshot,
        team_id_snapshot=team_id_snapshot,
        agency_id_snapshot=agency_id_snapshot,
        site_id_snapshot=site_id_snapshot,
    )
    withdrawal = WithdrawalRequest(
        account_id=account_id,
        wallet_account_id=wallet.id,
        user_id=customer_id,
        request_no=f"WD-{customer_id}",
        amount=Decimal("10"),
        currency="USD",
        owner_staff_id_snapshot=owner_staff_id_snapshot,
        supervisor_id_snapshot=supervisor_id_snapshot,
        team_id_snapshot=team_id_snapshot,
        agency_id_snapshot=agency_id_snapshot,
        site_id_snapshot=site_id_snapshot,
    )
    session.add_all([ledger, withdrawal])
    session.flush()
    return ledger, withdrawal


def _member_actor(actor_id: str, *, account_id: str, agency_id: str) -> RequestActor:
    return RequestActor(
        actor_id=actor_id,
        display_name=actor_id,
        role=ActorRole.AGENT_MEMBER,
        account_ids=[account_id],
        agency_id=agency_id,
        permission_role="support",
        resolved_permissions=["customers.view", "conversations.view"],
    )


def test_effective_access_service_combines_runtime_permissions_and_active_grants(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session)
        session.add_all(
            [
                PermissionGrant(
                    grantor_subject_type="super_admin",
                    grantor_subject_id="root",
                    grantee_subject_type="agency",
                    grantee_subject_id=scope["agency_id"],
                    permission_code="data_scope.manage",
                    can_delegate=True,
                    created_by="root",
                ),
                PermissionGrant(
                    grantor_subject_type="super_admin",
                    grantor_subject_id="root",
                    grantee_subject_type="actor",
                    grantee_subject_id="member-1",
                    permission_code="handover.manage",
                    can_delegate=False,
                    created_by="root",
                ),
                PermissionGrant(
                    grantor_subject_type="super_admin",
                    grantor_subject_id="root",
                    grantee_subject_type="actor",
                    grantee_subject_id="member-1",
                    permission_code="customers.detail",
                    can_delegate=False,
                    status="revoked",
                    created_by="root",
                ),
            ]
        )
        actor = _member_actor("member-1", account_id=scope["account_id"], agency_id=scope["agency_id"])

        access = EffectiveAccessService(session)

        assert access.get_effective_permissions(actor) == {
            "conversations.view",
            "customers.view",
            "data_scope.manage",
            "handover.manage",
        }
        assert access.get_delegatable_permissions(actor) == {"data_scope.manage"}


def test_data_scope_filter_service_uses_current_ownership_for_customers_and_snapshot_for_finance(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session)
        customer_owned = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="owned-user",
        )
        customer_other = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="other-user",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=customer_owned.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-1",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        _seed_wallet_artifacts(
            session,
            account_id=scope["account_id"],
            customer_id=customer_owned.id,
            owner_staff_id_snapshot="member-1",
            supervisor_id_snapshot="sup-1",
            team_id_snapshot="team-1",
            agency_id_snapshot=scope["agency_id"],
            site_id_snapshot=scope["site_id"],
        )
        _seed_wallet_artifacts(
            session,
            account_id=scope["account_id"],
            customer_id=customer_other.id,
            owner_staff_id_snapshot="member-2",
            supervisor_id_snapshot="sup-2",
            team_id_snapshot="team-2",
            agency_id_snapshot=scope["agency_id"],
            site_id_snapshot=scope["site_id"],
        )
        actor = _member_actor("member-1", account_id=scope["account_id"], agency_id=scope["agency_id"])

        service = DataScopeFilterService(session)

        customer_ids = session.scalars(
            service.filter_customers(select(AppUser), actor).with_only_columns(AppUser.id)
        ).all()
        ledger_ids = session.scalars(
            service.filter_wallet_ledger_entries(
                select(WalletLedgerEntry),
                actor,
                mode="snapshot",
            ).with_only_columns(WalletLedgerEntry.user_id)
        ).all()
        withdrawal_ids = session.scalars(
            service.filter_withdrawals(
                select(WithdrawalRequest),
                actor,
                mode="snapshot",
            ).with_only_columns(WithdrawalRequest.user_id)
        ).all()

        assert customer_ids == [customer_owned.id]
        assert ledger_ids == [customer_owned.id]
        assert withdrawal_ids == [customer_owned.id]


def test_customer_ownership_transfer_changes_future_owner_only(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session)
        customer = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="transfer-user",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=customer.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-1",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        session.flush()

        service = CustomerOwnershipService(session)
        updated = service.transfer_customer_ownership(
            customer_id=customer.id,
            agency_id=scope["agency_id"],
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            new_owner_staff_id="member-2",
            new_supervisor_id="sup-2",
            new_team_id="team-2",
            assigned_by="supervisor-9",
            reason="team rebalance",
        )

        assignments = session.scalars(
            select(CustomerOwnershipAssignment)
            .where(CustomerOwnershipAssignment.customer_id == customer.id)
            .order_by(CustomerOwnershipAssignment.created_at.asc())
        ).all()

        assert updated.owner_staff_id == "member-2"
        assert len(assignments) == 2
        assert assignments[0].status == "ended"
        assert assignments[0].owner_staff_id == "member-1"
        assert assignments[1].status == "active"
        assert assignments[1].owner_staff_id == "member-2"


def test_conversation_handover_only_changes_conversation_assignment_not_customer_owner(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        scope = _seed_scope(session)
        customer = _seed_customer(
            session,
            account_id=scope["account_id"],
            site_id=scope["site_id"],
            public_user_id="handover-user",
        )
        session.add(
            CustomerOwnershipAssignment(
                customer_id=customer.id,
                agency_id=scope["agency_id"],
                account_id=scope["account_id"],
                site_id=scope["site_id"],
                owner_staff_id="member-1",
                supervisor_id="sup-1",
                team_id="team-1",
                assignment_type="manual",
                assigned_by="root",
            )
        )
        conversation = Conversation(
            account_id=scope["account_id"],
            external_conversation_id="conv-handover",
            customer_id=customer.id,
            status="open",
        )
        queue = HandoverQueue(
            agency_id=scope["agency_id"],
            team_id="team-1",
            supervisor_id="sup-1",
            name="Team 1 Queue",
        )
        policy = AIHandoverPolicy(
            agency_id=scope["agency_id"],
            site_id=scope["site_id"],
            owner_first=True,
            require_online_owner=False,
        )
        session.add_all([conversation, queue, policy])
        session.flush()

        service = ConversationHandoverService(session)
        assignment = service.assign_conversation(
            conversation_id=conversation.id,
            customer_id=customer.id,
            agency_id=scope["agency_id"],
            assigned_staff_id="member-9",
            team_id="team-1",
            supervisor_id="sup-1",
            assignment_type="human_handover",
            assigned_by="supervisor-1",
            reason="temporary escalation",
            is_temporary=True,
        )

        ownership = session.scalar(
            select(CustomerOwnershipAssignment).where(
                CustomerOwnershipAssignment.customer_id == customer.id,
                CustomerOwnershipAssignment.status == "active",
            )
        )
        active_conversation_assignment = session.scalar(
            select(ConversationAssignment).where(
                ConversationAssignment.conversation_id == conversation.id,
                ConversationAssignment.status == "active",
            )
        )

        assert assignment.assigned_staff_id == "member-9"
        assert active_conversation_assignment is not None
        assert active_conversation_assignment.is_temporary is True
        assert ownership is not None
        assert ownership.owner_staff_id == "member-1"


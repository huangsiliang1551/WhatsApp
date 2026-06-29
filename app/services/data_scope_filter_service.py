from __future__ import annotations

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.sql import ColumnElement
from sqlalchemy.orm import Session

from app.core.auth import RequestActor
from app.db.models import (
    AppUser,
    Conversation,
    CustomerOwnershipAssignment,
    MktTaskInstance,
    RechargeRepairOrder,
    Ticket,
    WalletBonusGrantRecord,
    WalletLedgerEntry,
    WithdrawalRequest,
)
from app.services.effective_access_service import EffectiveAccessService, EffectiveDataScope


class DataScopeFilterService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._access_service = EffectiveAccessService(session)

    def filter_customers(self, query: Select, actor: RequestActor) -> Select:
        scope = self._access_service.get_data_scope(actor)
        if scope.all_access:
            return query

        conditions: list[ColumnElement[bool]] = []
        ownership_filters = self._ownership_conditions(scope)
        use_ownership_scope = self._should_use_ownership_scope(scope, ownership_filters)
        if scope.account_ids and not use_ownership_scope and not scope.site_ids and not scope.customer_ids:
            conditions.append(AppUser.account_id.in_(scope.account_ids))
        if scope.site_ids:
            conditions.append(AppUser.registration_site_id.in_(scope.site_ids))
        if use_ownership_scope and ownership_filters:
            owned_customer_ids = select(CustomerOwnershipAssignment.customer_id).where(
                CustomerOwnershipAssignment.status == "active",
                or_(*ownership_filters),
            )
            conditions.append(AppUser.id.in_(owned_customer_ids))
        if scope.customer_ids:
            conditions.append(AppUser.id.in_(scope.customer_ids))
        return query.where(or_(*conditions)) if conditions else query.where(False)

    def filter_conversations(self, query: Select, actor: RequestActor) -> Select:
        scope = self._access_service.get_data_scope(actor)
        if scope.all_access:
            return query

        conditions: list[ColumnElement[bool]] = []
        ownership_filters = self._ownership_conditions(scope)
        use_ownership_scope = self._should_use_ownership_scope(scope, ownership_filters)
        if scope.account_ids and not use_ownership_scope and not scope.customer_ids:
            conditions.append(Conversation.account_id.in_(scope.account_ids))
        if use_ownership_scope and ownership_filters:
            scoped_customers = select(CustomerOwnershipAssignment.customer_id).where(
                CustomerOwnershipAssignment.status == "active",
                or_(*ownership_filters),
            )
            conditions.append(Conversation.customer_id.in_(scoped_customers))
        if scope.customer_ids:
            conditions.append(Conversation.customer_id.in_(scope.customer_ids))
        return query.where(or_(*conditions)) if conditions else query.where(False)

    def filter_wallet_ledger_entries(self, query: Select, actor: RequestActor, *, mode: str = "snapshot") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=WalletLedgerEntry)

    def filter_withdrawals(self, query: Select, actor: RequestActor, *, mode: str = "snapshot") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=WithdrawalRequest)

    def filter_bonus_grants(self, query: Select, actor: RequestActor, *, mode: str = "current") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=WalletBonusGrantRecord)

    def filter_recharge_repairs(self, query: Select, actor: RequestActor, *, mode: str = "current") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=RechargeRepairOrder)

    def filter_tickets(self, query: Select, actor: RequestActor, *, mode: str = "current") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=Ticket)

    def filter_task_instances(self, query: Select, actor: RequestActor, *, mode: str = "current") -> Select:
        return self._filter_finance_like(query, actor, mode=mode, model=MktTaskInstance)

    def _filter_finance_like(self, query: Select, actor: RequestActor, *, mode: str, model) -> Select:
        scope = self._access_service.get_data_scope(actor)
        if scope.all_access:
            return query
        if mode == "snapshot":
            conditions = self._snapshot_conditions(scope, model)
            return query.where(or_(*conditions)) if conditions else query.where(False)
        if mode == "current":
            ownership_filters = self._ownership_conditions(scope)
            use_ownership_scope = self._should_use_ownership_scope(scope, ownership_filters)
            conditions: list[ColumnElement[bool]] = []
            if scope.account_ids and not use_ownership_scope:
                conditions.append(model.account_id.in_(scope.account_ids))
            if use_ownership_scope and ownership_filters:
                scoped_customers = select(CustomerOwnershipAssignment.customer_id).where(
                    CustomerOwnershipAssignment.status == "active",
                    or_(*ownership_filters),
                )
                conditions.append(model.user_id.in_(scoped_customers))
            if scope.customer_ids:
                conditions.append(model.user_id.in_(scope.customer_ids))
            return query.where(or_(*conditions)) if conditions else query.where(False)
        raise ValueError(f"unsupported finance filter mode '{mode}'")

    @staticmethod
    def _ownership_conditions(scope: EffectiveDataScope) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if scope.account_ids:
            conditions.append(CustomerOwnershipAssignment.account_id.in_(scope.account_ids))
        if scope.agency_ids:
            conditions.append(CustomerOwnershipAssignment.agency_id.in_(scope.agency_ids))
        if scope.site_ids:
            conditions.append(CustomerOwnershipAssignment.site_id.in_(scope.site_ids))
        if scope.team_ids:
            conditions.append(CustomerOwnershipAssignment.team_id.in_(scope.team_ids))
        if scope.supervisor_ids:
            conditions.append(CustomerOwnershipAssignment.supervisor_id.in_(scope.supervisor_ids))
        if scope.staff_ids:
            conditions.append(CustomerOwnershipAssignment.owner_staff_id.in_(scope.staff_ids))
        if scope.customer_ids:
            conditions.append(CustomerOwnershipAssignment.customer_id.in_(scope.customer_ids))
        return conditions

    @staticmethod
    def _snapshot_conditions(scope: EffectiveDataScope, model) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        owner_scoped = any((scope.agency_ids, scope.site_ids, scope.team_ids, scope.supervisor_ids, scope.staff_ids))
        if scope.account_ids and not owner_scoped:
            conditions.append(model.account_id.in_(scope.account_ids))
        if scope.agency_ids:
            conditions.append(model.agency_id_snapshot.in_(scope.agency_ids))
        if scope.site_ids:
            conditions.append(model.site_id_snapshot.in_(scope.site_ids))
        if scope.team_ids:
            conditions.append(model.team_id_snapshot.in_(scope.team_ids))
        if scope.supervisor_ids:
            conditions.append(model.supervisor_id_snapshot.in_(scope.supervisor_ids))
        if scope.staff_ids:
            conditions.append(model.owner_staff_id_snapshot.in_(scope.staff_ids))
        return conditions

    def _should_use_ownership_scope(
        self,
        scope: EffectiveDataScope,
        ownership_filters: list[ColumnElement[bool]],
    ) -> bool:
        if scope.customer_ids or scope.site_ids:
            return True
        if not ownership_filters:
            return False
        scoped_assignment = self._session.scalar(
            select(CustomerOwnershipAssignment.id).where(
                CustomerOwnershipAssignment.status == "active",
                or_(*ownership_filters),
            ).limit(1)
        )
        return scoped_assignment is not None

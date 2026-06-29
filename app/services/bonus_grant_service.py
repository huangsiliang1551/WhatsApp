from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import RequestActor
from app.db.models import AppUser, WalletAccount, WalletBonusGrantRecord, utc_now
from app.services.data_scope_filter_service import DataScopeFilterService
from app.services.wallet_ledger_service import WalletLedgerService


class BonusGrantService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._wallet_ledger_service = WalletLedgerService(session=session)

    def create_grant(
        self,
        *,
        account_id: str,
        user_id: str,
        amount: Decimal,
        currency: str,
        reason: str,
        remark: str | None,
        source_type: str,
        operator_id: str,
    ) -> WalletBonusGrantRecord:
        user = self._require_user(user_id=user_id, account_id=account_id)
        grant = WalletBonusGrantRecord(
            account_id=account_id,
            grant_no=f"BGR-{utc_now().strftime('%Y%m%d%H%M%S%f')}",
            user_id=user.id,
            amount=amount,
            currency=currency,
            source_type=source_type,
            reason=reason,
            remark=remark,
            status="pending",
            operator_id=operator_id,
        )
        self._session.add(grant)
        self._session.commit()
        return grant

    def approve_grant(self, *, grant_id: str, actor_id: str) -> WalletBonusGrantRecord:
        grant = self._require_grant_for_update(grant_id=grant_id)
        if grant.status == "credited":
            return grant
        if grant.status != "pending":
            raise ValueError(f"Bonus grant '{grant.id}' cannot be approved from '{grant.status}'.")

        wallet = self._require_wallet(account_id=grant.account_id, user_id=grant.user_id)
        now = utc_now()
        ledger = self._wallet_ledger_service.credit_system_balance(
            wallet=wallet,
            account_id=grant.account_id,
            user_id=grant.user_id,
            amount=Decimal(grant.amount),
            currency=grant.currency,
            transaction_type="bonus_grant",
            source_type=grant.source_type,
            note="Bonus credited",
            reference_type="wallet_bonus_grant_record",
            reference_id=grant.id,
            fund_type="bonus",
            is_bonus=True,
        )
        self._session.flush()
        grant.status = "credited"
        grant.approved_by = actor_id
        grant.approved_at = now
        grant.credited_at = now
        grant.ledger_id = ledger.id
        self._session.add(grant)
        self._session.commit()
        return grant

    def reject_grant(self, *, grant_id: str, actor_id: str, reason: str | None = None) -> WalletBonusGrantRecord:
        grant = self._require_grant_for_update(grant_id=grant_id)
        if grant.status == "rejected":
            return grant
        if grant.status != "pending":
            raise ValueError(f"Bonus grant '{grant.id}' cannot be rejected from '{grant.status}'.")
        grant.status = "rejected"
        grant.approved_by = actor_id
        grant.rejected_at = utc_now()
        if reason:
            grant.remark = reason
        self._session.add(grant)
        self._session.commit()
        return grant

    def list_grants(
        self,
        *,
        account_id: str | None = None,
        scope_actor: RequestActor | None = None,
    ) -> list[WalletBonusGrantRecord]:
        query = select(WalletBonusGrantRecord).order_by(
            WalletBonusGrantRecord.created_at.desc(),
            WalletBonusGrantRecord.id.desc(),
        )
        if account_id is not None:
            query = query.where(WalletBonusGrantRecord.account_id == account_id)
        if scope_actor is not None:
            query = DataScopeFilterService(self._session).filter_bonus_grants(query, scope_actor, mode="current")
        return self._session.scalars(query).all()

    def _require_user(self, *, user_id: str, account_id: str) -> AppUser:
        user = self._session.get(AppUser, user_id)
        if user is None:
            user = self._session.scalars(
                select(AppUser).where(
                    AppUser.account_id == account_id,
                    AppUser.public_user_id == user_id,
                )
            ).first()
        if user is None or user.account_id != account_id:
            raise LookupError(f"User '{user_id}' not found for account '{account_id}'.")
        return user

    def _require_wallet(self, *, account_id: str, user_id: str) -> WalletAccount:
        wallet = self._session.scalars(
            select(WalletAccount).where(
                WalletAccount.account_id == account_id,
                WalletAccount.user_id == user_id,
            )
        ).first()
        if wallet is None:
            wallet = WalletAccount(account_id=account_id, user_id=user_id)
            self._session.add(wallet)
            self._session.flush()
        return wallet

    def _require_grant_for_update(self, *, grant_id: str) -> WalletBonusGrantRecord:
        grant = self._session.scalars(
            select(WalletBonusGrantRecord)
            .where(WalletBonusGrantRecord.id == grant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if grant is None:
            raise LookupError(f"Bonus grant '{grant_id}' not found.")
        return grant

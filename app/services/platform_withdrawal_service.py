from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    MemberNotification,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalAuditLog,
    WithdrawalRequest,
    utc_now,
)
from app.schemas.h5_member_commerce import H5WithdrawalAuditLogResponse
from app.schemas.platform_withdrawals import PlatformWithdrawalResponse, PlatformWithdrawalStatus

TERMINAL_WITHDRAWAL_STATUSES = {"rejected", "paid"}
# Status transition map: submitted → reviewing → approved → rejected/paid.
# Balance validation is performed at the commerce-service level before submission.
# TODO: BE2-023 — Add duplicate submission prevention in H5MemberCommerceService.create_withdrawal
#       to reject a new withdrawal if an active pending request (submitted/reviewing/approved) exists.
# TODO: BE2-023 — Add max-amount cap and daily/weekly withdrawal frequency limits to
#       prevent abuse. Consider configurable thresholds per account or site.
WITHDRAWAL_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"reviewing", "approved", "rejected"},
    "reviewing": {"approved", "rejected"},
    "approved": {"paid", "rejected"},
    "rejected": set(),
    "paid": set(),
}


class PlatformWithdrawalService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    async def list_withdrawals(
        self,
        *,
        account_id: str | None,
        allowed_account_ids: set[str] | None,
        status: PlatformWithdrawalStatus | None,
    ) -> list[PlatformWithdrawalResponse]:
        query = select(WithdrawalRequest).order_by(
            WithdrawalRequest.created_at.desc(),
            WithdrawalRequest.id.desc(),
        )
        if account_id is not None:
            query = query.where(WithdrawalRequest.account_id == account_id)
        if allowed_account_ids is not None:
            query = query.where(WithdrawalRequest.account_id.in_(sorted(allowed_account_ids)))
        if status is not None:
            query = query.where(WithdrawalRequest.status == status)
        withdrawals = self._session.scalars(query).all()
        return self._serialize_withdrawals(withdrawals)

    async def get_withdrawal(
        self,
        *,
        withdrawal_id: str,
    ) -> PlatformWithdrawalResponse:
        withdrawal = self._require_withdrawal(withdrawal_id=withdrawal_id)
        return self._serialize_withdrawal(
            withdrawal,
            history=self._load_withdrawal_histories([withdrawal.id]).get(withdrawal.id, []),
        )

    async def update_withdrawal_status(
        self,
        *,
        withdrawal_id: str,
        status: PlatformWithdrawalStatus,
        note: str | None,
        rejection_reason: str | None,
        actor_type: str,
        actor_id: str | None,
    ) -> PlatformWithdrawalResponse:
        withdrawal = self._require_withdrawal_for_update(withdrawal_id=withdrawal_id)
        if withdrawal.status == status:
            return self._serialize_withdrawal(
                withdrawal,
                history=self._load_withdrawal_histories([withdrawal.id]).get(withdrawal.id, []),
            )
        if status not in WITHDRAWAL_STATUS_TRANSITIONS[withdrawal.status]:
            raise ValueError(
                f"Withdrawal '{withdrawal.id}' cannot transition from '{withdrawal.status}' to '{status}'."
            )
        if status == "rejected" and not (rejection_reason or "").strip():
            raise ValueError("Rejected withdrawals require a rejection reason.")

        now = utc_now()
        review_note = (note or "").strip() or self._default_status_note(status)
        withdrawal.status = status
        if status in {"approved", "rejected", "paid"} and withdrawal.reviewed_at is None:
            withdrawal.reviewed_at = now
        if status == "paid":
            withdrawal.paid_at = now
            withdrawal.rejection_reason = None
        elif status == "rejected":
            withdrawal.rejection_reason = rejection_reason.strip() if rejection_reason is not None else None
            self._refund_rejected_withdrawal(withdrawal=withdrawal, note=review_note)
        else:
            withdrawal.rejection_reason = None

        self._update_withdraw_request_ledgers(
            withdrawal_id=withdrawal.id,
            status="rejected" if status == "rejected" else status,
        )
        self._create_member_notification(
            withdrawal=withdrawal,
            status=status,
            note=review_note,
        )
        self._session.add(withdrawal)
        self._session.add(
            WithdrawalAuditLog(
                account_id=withdrawal.account_id,
                withdrawal_request_id=withdrawal.id,
                status=status,
                note=review_note,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        )
        self._session.commit()
        reloaded = self._require_withdrawal(withdrawal_id=withdrawal.id)
        return self._serialize_withdrawal(
            reloaded,
            history=self._load_withdrawal_histories([reloaded.id]).get(reloaded.id, []),
        )

    def _refund_rejected_withdrawal(
        self,
        *,
        withdrawal: WithdrawalRequest,
        note: str,
    ) -> None:
        wallet = self._require_wallet_for_update(wallet_id=withdrawal.wallet_account_id)
        refund_amount = Decimal(withdrawal.amount)
        wallet.system_balance = self._quantize(Decimal(wallet.system_balance) + refund_amount)
        self._session.add(wallet)
        self._session.add(
            WalletLedgerEntry(
                account_id=withdrawal.account_id,
                wallet_account_id=wallet.id,
                user_id=withdrawal.user_id,
                ledger_type="system",
                transaction_type="withdraw_reject_refund",
                direction="credit",
                amount=refund_amount,
                currency=withdrawal.currency,
                status="paid",
                note=note,
                reference_type="withdrawal_request",
                reference_id=withdrawal.id,
            )
        )

    def _create_member_notification(
        self,
        *,
        withdrawal: WithdrawalRequest,
        status: str,
        note: str,
    ) -> None:
        if status not in {"approved", "rejected", "paid"}:
            return
        user = self._session.get(AppUser, withdrawal.user_id)
        if user is None or withdrawal.member_profile_id is None:
            return
        title, default_body = self._build_notification_copy(withdrawal=withdrawal, status=status)
        body_text = note if note else default_body
        self._session.add(
            MemberNotification(
                account_id=withdrawal.account_id,
                user_id=withdrawal.user_id,
                member_profile_id=withdrawal.member_profile_id,
                site_id=user.registration_site_id,
                category="wallet",
                title=title,
                body_text=body_text,
                is_read=False,
                reference_type="withdrawal_request",
                reference_id=withdrawal.id,
                metadata_json={
                    "withdrawal_status": status,
                    "request_no": withdrawal.request_no,
                    "amount": float(withdrawal.amount),
                    "currency": withdrawal.currency,
                },
            )
        )

    def _update_withdraw_request_ledgers(
        self,
        *,
        withdrawal_id: str,
        status: str,
    ) -> None:
        ledger_entries = self._session.scalars(
            select(WalletLedgerEntry).where(
                WalletLedgerEntry.reference_type == "withdrawal_request",
                WalletLedgerEntry.reference_id == withdrawal_id,
                WalletLedgerEntry.transaction_type == "withdraw_request",
            )
        ).all()
        for entry in ledger_entries:
            entry.status = status
            self._session.add(entry)

    def _require_withdrawal(
        self,
        *,
        withdrawal_id: str,
    ) -> WithdrawalRequest:
        withdrawal = self._session.get(WithdrawalRequest, withdrawal_id)
        if withdrawal is None:
            raise LookupError(f"Withdrawal '{withdrawal_id}' was not found.")
        return withdrawal

    def _require_withdrawal_for_update(
        self,
        *,
        withdrawal_id: str,
    ) -> WithdrawalRequest:
        withdrawal = self._session.scalars(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.id == withdrawal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if withdrawal is None:
            raise LookupError(f"Withdrawal '{withdrawal_id}' was not found.")
        return withdrawal

    def _require_wallet_for_update(
        self,
        *,
        wallet_id: str,
    ) -> WalletAccount:
        wallet = self._session.scalars(
            select(WalletAccount)
            .where(WalletAccount.id == wallet_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if wallet is None:
            raise LookupError(f"Wallet '{wallet_id}' was not found.")
        return wallet

    def _load_withdrawal_histories(
        self,
        withdrawal_ids: list[str],
    ) -> dict[str, list[WithdrawalAuditLog]]:
        if not withdrawal_ids:
            return {}
        history_rows = self._session.scalars(
            select(WithdrawalAuditLog)
            .where(WithdrawalAuditLog.withdrawal_request_id.in_(withdrawal_ids))
            .order_by(WithdrawalAuditLog.created_at.asc(), WithdrawalAuditLog.id.asc())
        ).all()
        histories: dict[str, list[WithdrawalAuditLog]] = {item: [] for item in withdrawal_ids}
        for row in history_rows:
            histories.setdefault(row.withdrawal_request_id, []).append(row)
        return histories

    def _serialize_withdrawals(
        self,
        withdrawals: list[WithdrawalRequest],
    ) -> list[PlatformWithdrawalResponse]:
        histories = self._load_withdrawal_histories([item.id for item in withdrawals])
        return [
            self._serialize_withdrawal(item, history=histories.get(item.id, []))
            for item in withdrawals
        ]

    @staticmethod
    def _serialize_withdrawal(
        withdrawal: WithdrawalRequest,
        *,
        history: list[WithdrawalAuditLog],
    ) -> PlatformWithdrawalResponse:
        return PlatformWithdrawalResponse(
            id=withdrawal.id,
            account_id=withdrawal.account_id,
            wallet_account_id=withdrawal.wallet_account_id,
            user_id=withdrawal.user_id,
            member_profile_id=withdrawal.member_profile_id,
            request_no=withdrawal.request_no,
            amount=float(withdrawal.amount),
            currency=withdrawal.currency,
            status=withdrawal.status,
            rejection_reason=withdrawal.rejection_reason,
            created_at=withdrawal.created_at,
            reviewed_at=withdrawal.reviewed_at,
            paid_at=withdrawal.paid_at,
            history=[
                H5WithdrawalAuditLogResponse(
                    id=item.id,
                    status=item.status,
                    note=item.note,
                    actor_type=item.actor_type,
                    actor_id=item.actor_id,
                    created_at=item.created_at,
                )
                for item in history
            ],
        )

    @staticmethod
    def _default_status_note(status: str) -> str:
        return {
            "reviewing": "Withdrawal request is under review.",
            "approved": "Withdrawal request was approved.",
            "rejected": "Withdrawal request was rejected.",
            "paid": "Withdrawal request payout completed.",
        }.get(status, "Withdrawal request status updated.")

    @staticmethod
    def _build_notification_copy(
        *,
        withdrawal: WithdrawalRequest,
        status: str,
    ) -> tuple[str, str]:
        amount = f"{Decimal(withdrawal.amount):.2f} {withdrawal.currency}"
        if status == "approved":
            return ("Withdrawal approved", f"Your withdrawal request {withdrawal.request_no} for {amount} was approved.")
        if status == "rejected":
            return ("Withdrawal rejected", f"Your withdrawal request {withdrawal.request_no} for {amount} was rejected.")
        return ("Withdrawal paid", f"Your withdrawal request {withdrawal.request_no} for {amount} was paid.")

    @staticmethod
    def _quantize(amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"))

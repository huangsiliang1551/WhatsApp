from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import WithdrawalRequest

ACTIVE_WITHDRAWAL_STATUSES = {"submitted", "reviewing", "approved"}


@dataclass(frozen=True, slots=True)
class WithdrawalRiskDecision:
    allowed: bool
    reason_code: str | None = None
    message: str | None = None


class WithdrawalRiskService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def evaluate_for_transition(
        self,
        *,
        withdrawal: WithdrawalRequest,
        next_status: str,
    ) -> WithdrawalRiskDecision:
        if next_status != "approved":
            return WithdrawalRiskDecision(allowed=True)

        if self._has_other_active_withdrawal(withdrawal=withdrawal):
            return WithdrawalRiskDecision(
                allowed=False,
                reason_code="duplicate_active_withdrawal",
                message="Duplicate active withdrawal exists for this member.",
            )

        risk_flags = set(withdrawal.risk_flags or [])
        if (
            "duplicate_withdraw_account" in risk_flags
            or (withdrawal.duplicate_account_count or 0) > 0
        ) and withdrawal.status != "reviewing":
            return WithdrawalRiskDecision(
                allowed=False,
                reason_code="second_review_required",
                message="Second review is required before approving this withdrawal.",
            )

        return WithdrawalRiskDecision(allowed=True)

    def _has_other_active_withdrawal(self, *, withdrawal: WithdrawalRequest) -> bool:
        active_count = self._session.scalar(
            select(func.count())
            .select_from(WithdrawalRequest)
            .where(
                WithdrawalRequest.account_id == withdrawal.account_id,
                WithdrawalRequest.user_id == withdrawal.user_id,
                WithdrawalRequest.id != withdrawal.id,
                WithdrawalRequest.status.in_(sorted(ACTIVE_WITHDRAWAL_STATUSES)),
            )
        )
        return int(active_count or 0) > 0

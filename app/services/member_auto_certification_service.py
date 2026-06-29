from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    MemberNotification,
    MemberVerificationRequest,
    TaskSystemConfig,
    WalletLedgerEntry,
    utc_now,
)


class MemberAutoCertificationService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def auto_certify_after_real_recharge(
        self,
        *,
        account_id: str,
        site_id: str | None,
        member_profile_id: str,
        user_id: str,
        trigger_source: str,
    ) -> MemberVerificationRequest | None:
        config = self._resolve_task_system_config(account_id=account_id, site_id=site_id)
        if config is None or not config.certified_member_enabled or not config.auto_certify_on_recharge:
            return None

        real_recharge_amount = self._load_real_recharge_amount(account_id=account_id, user_id=user_id)
        if real_recharge_amount < Decimal(config.certified_recharge_threshold):
            return None

        latest_request = self._session.scalars(
            select(MemberVerificationRequest)
            .where(
                MemberVerificationRequest.account_id == account_id,
                MemberVerificationRequest.member_profile_id == member_profile_id,
            )
            .order_by(MemberVerificationRequest.created_at.desc(), MemberVerificationRequest.id.desc())
        ).first()
        if latest_request is not None and latest_request.status == "approved":
            return latest_request

        note = (
            f"Auto approved after real recharge reached threshold "
            f"{Decimal(config.certified_recharge_threshold):.2f}."
        )
        now = utc_now()
        if latest_request is not None and latest_request.status in {"pending", "under_review"}:
            latest_request.status = "approved"
            latest_request.review_note = note
            latest_request.reviewer_actor_id = "system:auto_certify"
            latest_request.reviewed_at = now
            self._session.add(latest_request)
            request = latest_request
        else:
            request = MemberVerificationRequest(
                account_id=account_id,
                member_profile_id=member_profile_id,
                request_type="identity",
                status="approved",
                notes=f"Auto certification triggered by {trigger_source}.",
                review_note=note,
                reviewer_actor_id="system:auto_certify",
                reviewed_at=now,
            )
            self._session.add(request)
            self._session.flush()

        self._create_notification(
            account_id=account_id,
            member_profile_id=member_profile_id,
            user_id=user_id,
            site_id=site_id,
            threshold=Decimal(config.certified_recharge_threshold),
            trigger_source=trigger_source,
        )
        return request

    def _resolve_task_system_config(
        self,
        *,
        account_id: str,
        site_id: str | None,
    ) -> TaskSystemConfig | None:
        if site_id is not None:
            scoped = self._session.scalars(
                select(TaskSystemConfig).where(
                    TaskSystemConfig.account_id == account_id,
                    TaskSystemConfig.site_id == site_id,
                )
            ).first()
            if scoped is not None:
                return scoped
        return self._session.scalars(
            select(TaskSystemConfig).where(
                TaskSystemConfig.account_id == account_id,
                TaskSystemConfig.site_id.is_(None),
            )
        ).first()

    def _load_real_recharge_amount(self, *, account_id: str, user_id: str) -> Decimal:
        amount = self._session.scalar(
            select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0))
            .where(
                WalletLedgerEntry.account_id == account_id,
                WalletLedgerEntry.user_id == user_id,
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.status == "paid",
                WalletLedgerEntry.is_real_recharge.is_(True),
            )
        )
        return Decimal(amount or 0)

    def _create_notification(
        self,
        *,
        account_id: str,
        member_profile_id: str,
        user_id: str,
        site_id: str | None,
        threshold: Decimal,
        trigger_source: str,
    ) -> None:
        self._session.add(
            MemberNotification(
                account_id=account_id,
                user_id=user_id,
                member_profile_id=member_profile_id,
                site_id=site_id,
                category="system",
                title="会员认证已通过",
                body_text=(
                    f"您的会员已因真实充值达到 {threshold:.2f} 阈值自动认证通过。"
                    f" 来源：{trigger_source}。"
                ),
                is_read=False,
                reference_type="member_verification_request",
                reference_id=None,
            )
        )

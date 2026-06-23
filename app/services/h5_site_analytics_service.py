"""Site analytics aggregation service."""
from __future__ import annotations

from datetime import UTC, datetime, date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    H5Site,
    SignInRecord,
    TaskInstance,
    UptimeCheck,
    WalletAccount,
)


class H5SiteAnalyticsService:
    """Aggregate analytics data for an H5 site."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_analytics(self, site_id: str) -> dict:
        """Compute analytics for a single site."""
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"Site '{site_id}' not found.")

        today = datetime.now(UTC).date()
        today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)

        # ── total_users ──
        total_users: int = (
            self._session.scalar(
                select(func.count(AppUser.id)).where(AppUser.registration_site_id == site_id)
            )
            or 0
        )

        # ── active_users_today ──
        active_users_today: int = (
            self._session.scalar(
                select(func.count(AppUser.id)).where(
                    AppUser.registration_site_id == site_id,
                    AppUser.updated_at >= today_start,
                )
            )
            or 0
        )

        # ── sign_in_count_today ──
        sign_in_count_today: int = (
            self._session.scalar(
                select(func.count(SignInRecord.id)).where(
                    SignInRecord.sign_date == today,
                )
            )
            or 0
        )

        # ── task_completion_rate ──
        total_tasks: int = (
            self._session.scalar(
                select(func.count(TaskInstance.id)).where(TaskInstance.site_id == site_id)
            )
            or 0
        )
        completed_tasks: int = (
            self._session.scalar(
                select(func.count(TaskInstance.id)).where(
                    TaskInstance.site_id == site_id,
                    TaskInstance.status.in_(["completed", "approved"]),
                )
            )
            or 0
        )
        task_completion_rate: float = round(
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0,
            1,
        )

        # ── revenue_today (wallet task_balance increases today) ──
        revenue_today: float = 0.0
        wallet_sum = self._session.scalar(
            select(func.coalesce(func.sum(WalletAccount.task_balance), 0)).where(
                WalletAccount.updated_at >= today_start,
            )
        )
        if wallet_sum is not None:
            revenue_today = float(wallet_sum)

        # ── last_verified_at / health_status from uptime_checks ──
        last_check = self._session.scalar(
            select(UptimeCheck)
            .where(UptimeCheck.site_id == site_id)
            .order_by(UptimeCheck.created_at.desc())
            .limit(1)
        )
        if last_check is not None:
            last_verified_at = last_check.created_at.isoformat() if last_check.created_at else None
            if last_check.status == "up":
                health_status = "healthy"
            elif last_check.status == "timeout":
                health_status = "warning"
            else:
                health_status = "error"
        else:
            last_verified_at = None
            health_status = "unverified"

        return {
            "site_id": site_id,
            "total_users": total_users,
            "active_users_today": active_users_today,
            "sign_in_count_today": sign_in_count_today,
            "task_completion_rate": task_completion_rate,
            "revenue_today": revenue_today,
            "last_verified_at": last_verified_at,
            "health_status": health_status,
        }

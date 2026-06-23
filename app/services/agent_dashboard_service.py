"""Agent dashboard service for multi-tenant data aggregation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Agency,
    AgencyBilling,
    AgencyMember,
    Agent,
    AppUser,
    H5Site,
    SignInRecord,
    TaskInstance,
    WalletAccount,
)


class AgentDashboardService:
    """Aggregated data for agent dashboards."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_dashboard(self, agency_id: str) -> dict:
        """Get full dashboard data for an agency."""
        agency = self.session.get(Agency, agency_id)
        if agency is None:
            raise LookupError(f"Agency not found: {agency_id}")

        # Get all site IDs for this agency
        site_stmt = select(H5Site.id).where(H5Site.agency_id == agency_id)
        site_ids = [row[0] for row in self.session.execute(site_stmt).all()]

        # Site stats
        total_sites = len(site_ids)
        active_stmt = (
            select(func.count(H5Site.id))
            .where(H5Site.agency_id == agency_id, H5Site.status == "active")
        )
        active_sites = self.session.execute(active_stmt).scalar() or 0

        # User stats
        if site_ids:
            total_users_stmt = (
                select(func.count(AppUser.id))
                .where(AppUser.registration_site_id.in_(site_ids))
            )
            total_users = self.session.execute(total_users_stmt).scalar() or 0
        else:
            total_users = 0

        # Task stats
        if site_ids:
            total_tasks_stmt = (
                select(func.count(TaskInstance.id))
                .where(TaskInstance.site_id.in_(site_ids))
            )
            total_tasks = self.session.execute(total_tasks_stmt).scalar() or 0

            completed_tasks_stmt = (
                select(func.count(TaskInstance.id))
                .where(
                    TaskInstance.site_id.in_(site_ids),
                    TaskInstance.status == "completed",
                )
            )
            completed_tasks = self.session.execute(completed_tasks_stmt).scalar() or 0
        else:
            total_tasks = 0
            completed_tasks = 0

        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        # Revenue
        if site_ids:
            revenue_stmt = (
                select(func.coalesce(func.sum(WalletAccount.task_balance), 0))
                .where(WalletAccount.registration_site_id.in_(site_ids))
            )
            revenue = float(self.session.execute(revenue_stmt).scalar() or 0)
        else:
            revenue = 0.0

        # Member stats
        member_stmt = (
            select(func.count(AgencyMember.id))
            .where(AgencyMember.agency_id == agency_id)
        )
        total_members = self.session.execute(member_stmt).scalar() or 0

        # Billing stats
        pending_billing_stmt = (
            select(func.coalesce(func.sum(AgencyBilling.amount), 0))
            .where(
                AgencyBilling.agency_id == agency_id,
                AgencyBilling.status == "pending",
            )
        )
        pending_billing = float(self.session.execute(pending_billing_stmt).scalar() or 0)

        return {
            "agency_id": agency_id,
            "agency_name": agency.name,
            "total_sites": total_sites,
            "active_sites": active_sites,
            "total_users": total_users,
            "total_tasks": total_tasks,
            "task_completion_rate": task_completion_rate,
            "revenue": revenue,
            "pending_billing": pending_billing,
            "total_members": total_members,
        }

    def get_site_stats(self, agency_id: str) -> list[dict]:
        """Get per-site statistics for an agency."""
        stmt = select(H5Site).where(H5Site.agency_id == agency_id)
        sites = list(self.session.execute(stmt).scalars().all())

        results = []
        for site in sites:
            user_count = self.session.execute(
                select(func.count(AppUser.id)).where(AppUser.registration_site_id == site.id)
            ).scalar() or 0
            results.append({
                "site_id": site.id,
                "site_key": site.site_key,
                "domain": site.domain,
                "brand_name": site.brand_name,
                "status": site.status,
                "user_count": user_count,
            })
        return results

    def get_revenue_stats(self, agency_id: str) -> dict:
        """Get revenue statistics for an agency."""
        site_stmt = select(H5Site.id).where(H5Site.agency_id == agency_id)
        site_ids = [row[0] for row in self.session.execute(site_stmt).all()]

        if not site_ids:
            return {"total_revenue": 0.0, "pending_billing": 0.0, "paid_billing": 0.0}

        revenue_stmt = (
            select(func.coalesce(func.sum(WalletAccount.task_balance), 0))
            .where(WalletAccount.registration_site_id.in_(site_ids))
        )
        total_revenue = float(self.session.execute(revenue_stmt).scalar() or 0)

        # Billing by status
        bill_stmt = select(
            AgencyBilling.status,
            func.coalesce(func.sum(AgencyBilling.amount), 0),
        ).where(AgencyBilling.agency_id == agency_id).group_by(AgencyBilling.status)
        billing_by_status = dict(self.session.execute(bill_stmt).all())

        return {
            "total_revenue": total_revenue,
            "pending_billing": float(billing_by_status.get("pending", 0)),
            "paid_billing": float(billing_by_status.get("paid", 0)),
            "overdue_billing": float(billing_by_status.get("overdue", 0)),
        }

    def get_member_stats(self, agency_id: str) -> list[dict]:
        """Get member statistics for an agency."""
        stmt = select(AgencyMember).where(AgencyMember.agency_id == agency_id)
        members = list(self.session.execute(stmt).scalars().all())

        results = []
        for member in members:
            agent = self.session.get(Agent, member.user_id)
            results.append({
                "member_id": member.id,
                "user_id": member.user_id,
                "username": agent.display_name if agent else "Unknown",
                "role": member.role,
                "created_at": member.created_at.isoformat() if member.created_at else None,
            })
        return results

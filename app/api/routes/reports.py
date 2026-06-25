"""Reports API routes for super admin and agency reporting."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import AgencyBilling, AppUser, Conversation, MktTaskInstance, Product, ProductPackage, Ticket
from app.services.finance_report_service import FinanceReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _apply_account_scope(base_query, actor: RequestActor, model_field):
    if not actor.is_super_admin and actor.account_ids:
        return base_query.where(model_field.in_(actor.account_ids))
    return base_query


def _apply_billing_scope(base_query, actor: RequestActor):
    if actor.is_super_admin:
        return base_query
    return base_query.where(text("1=0"))


def _resolve_effective_report_account_id(
    actor: RequestActor,
    requested_account_id: str | None,
) -> str | None:
    if actor.is_super_admin:
        return requested_account_id
    if requested_account_id is not None:
        actor.require_account_access(requested_account_id)
        return requested_account_id
    if len(actor.account_ids) == 1:
        return actor.account_ids[0]
    return None


@router.get("")
async def report_overview(
    agency_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("reports.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Reports overview - super admin sees all, agent sees own scope."""
    conv_query = _apply_account_scope(
        select(func.count(Conversation.id)),
        actor,
        Conversation.account_id,
    )
    if agency_id and actor.is_super_admin:
        pass

    total_conversations = session.scalar(conv_query) or 0
    open_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.status == "open"),
            actor,
            Conversation.account_id,
        )
    ) or 0
    closed_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.status == "closed"),
            actor,
            Conversation.account_id,
        )
    ) or 0
    total_users = session.scalar(
        _apply_account_scope(select(func.count(AppUser.id)), actor, AppUser.account_id)
    ) or 0
    total_tickets = session.scalar(
        _apply_account_scope(select(func.count(Ticket.id)), actor, Ticket.account_id)
    ) or 0
    open_tickets = session.scalar(
        _apply_account_scope(
            select(func.count(Ticket.id)).where(Ticket.status.in_(["open", "pending"])),
            actor,
            Ticket.account_id,
        )
    ) or 0
    total_products = session.scalar(
        _apply_account_scope(select(func.count(Product.id)), actor, Product.account_id)
    ) or 0
    total_packages = session.scalar(
        _apply_account_scope(select(func.count(ProductPackage.id)), actor, ProductPackage.account_id)
    ) or 0
    total_task_instances = session.scalar(
        _apply_account_scope(select(func.count(MktTaskInstance.id)), actor, MktTaskInstance.account_id)
    ) or 0

    return {
        "total_conversations": total_conversations,
        "open_conversations": open_conversations,
        "closed_conversations": closed_conversations,
        "total_users": total_users,
        "total_tickets": total_tickets,
        "open_tickets": open_tickets,
        "total_products": total_products,
        "total_packages": total_packages,
        "total_task_instances": total_task_instances,
    }


@router.get("/finance")
async def finance_report(
    agency_id: str | None = Query(default=None, description="Filter by agency"),
    period: str = Query(default="monthly", description="daily/weekly/monthly"),
    actor: RequestActor = Depends(require_permission("reports.finance")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Financial report with revenue, billing, and commission data."""
    del period
    effective_account_id = _resolve_effective_report_account_id(actor, agency_id)

    billing_query = _apply_billing_scope(select(AgencyBilling), actor)
    if effective_account_id and actor.is_super_admin:
        billing_query = billing_query.where(AgencyBilling.agency_id == effective_account_id)
    billings = list(session.execute(billing_query).scalars().all())

    total_billing = sum(float(b.amount) for b in billings)
    paid_billing = sum(float(b.amount) for b in billings if b.status == "paid")
    pending_billing = sum(float(b.amount) for b in billings if b.status == "pending")

    if effective_account_id is not None:
        reward_query = select(func.coalesce(func.sum(MktTaskInstance.reward_amount), 0)).where(
            MktTaskInstance.account_id == effective_account_id
        )
        total_reward = float(session.scalar(reward_query) or 0)
    elif actor.is_super_admin:
        reward_query = select(func.coalesce(func.sum(MktTaskInstance.reward_amount), 0))
        total_reward = float(session.scalar(reward_query) or 0)
    else:
        total_reward = 0.0

    finance_summary = FinanceReportService(session).get_finance_summary(
        {"agency_id": effective_account_id} if effective_account_id else None
    )
    details = [
        {
            "period": str(b.created_at.date()) if b.created_at else "unknown",
            "agency_id": b.agency_id,
            "billing_type": b.billing_type,
            "amount": float(b.amount),
            "status": b.status,
        }
        for b in billings
    ]

    return {
        "total_revenue": round(total_reward, 2),
        "total_billing": round(total_billing, 2),
        "paid_billing": round(paid_billing, 2),
        "pending_billing": round(pending_billing, 2),
        "recharge_amount": finance_summary["recharge_amount"],
        "withdraw_amount": finance_summary["withdrawal_amount"],
        "commission": round(total_reward * 0.10, 2),
        "details": details,
    }

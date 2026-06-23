"""Reports API routes for super admin and agency reporting."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import AgencyBilling, AppUser, Conversation, MktTaskInstance, Product, ProductPackage, Ticket

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _apply_account_scope(base_query, actor: RequestActor, model_field):
    if not actor.is_super_admin and actor.account_ids:
        return base_query.where(model_field.in_(actor.account_ids))
    return base_query


def _apply_billing_scope(base_query, actor: RequestActor):
    if actor.is_super_admin:
        return base_query
    # Non-super-admin: no billing access (AgencyBilling has agency_id, not account_id)
    return base_query.where(text('1=0'))


@router.get("")
async def report_overview(
    agency_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("reports.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Reports overview - super admin sees all, agent sees own scope."""
    # Conversation stats
    conv_query = _apply_account_scope(
        select(func.count(Conversation.id)), actor, Conversation.account_id
    )
    if agency_id and actor.is_super_admin:
        pass

    total_conversations = session.scalar(conv_query) or 0

    open_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.status == "open"),
            actor, Conversation.account_id,
        )
    ) or 0

    closed_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.status == "closed"),
            actor, Conversation.account_id,
        )
    ) or 0

    # User stats
    total_users = session.scalar(
        _apply_account_scope(select(func.count(AppUser.id)), actor, AppUser.account_id)
    ) or 0

    # Ticket stats
    total_tickets = session.scalar(
        _apply_account_scope(select(func.count(Ticket.id)), actor, Ticket.account_id)
    ) or 0
    open_tickets = session.scalar(
        _apply_account_scope(
            select(func.count(Ticket.id)).where(Ticket.status.in_(["open", "pending"])),
            actor, Ticket.account_id,
        )
    ) or 0

    # Product stats
    total_products = session.scalar(
        _apply_account_scope(select(func.count(Product.id)), actor, Product.account_id)
    ) or 0
    total_packages = session.scalar(
        _apply_account_scope(select(func.count(ProductPackage.id)), actor, ProductPackage.account_id)
    ) or 0

    # Task stats
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
    # Billing stats — only super admin sees billing data
    billing_query = _apply_billing_scope(select(AgencyBilling), actor)
    if agency_id and actor.is_super_admin:
        billing_query = billing_query.where(AgencyBilling.agency_id == agency_id)

    billings = list(session.execute(billing_query).scalars().all())

    total_billing = sum(float(b.amount) for b in billings)
    paid_billing = sum(float(b.amount) for b in billings if b.status == "paid")
    pending_billing = sum(float(b.amount) for b in billings if b.status == "pending")

    # Task instance payout stats (reward_amount as proxy for revenue)
    reward_query = _apply_account_scope(
        select(func.coalesce(func.sum(MktTaskInstance.reward_amount), 0)),
        actor, MktTaskInstance.account_id,
    )
    if agency_id:
        pass  # MktTaskInstance uses account_id, not agency_id directly
    total_reward = float(session.scalar(reward_query) or 0)

    # Commission estimate (placeholder - 10% of revenue)
    commission = round(total_reward * 0.10, 2)

    # Recharge/withdraw placeholder (extend when withdrawal tables are linked)
    recharge_amount = 0.0
    withdraw_amount = 0.0

    # Period-based details
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
        "recharge_amount": recharge_amount,
        "withdraw_amount": withdraw_amount,
        "commission": commission,
        "details": details,
    }

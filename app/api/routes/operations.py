"""Operations center API routes for super admin oversight."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import (
    AgencyBilling,
    Conversation,
    MktTaskInstance,
    Notification,
    Product,
    ProductPackage,
    Ticket,
)

router = APIRouter(prefix="/api/operations", tags=["operations"])


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
async def operation_overview(
    agency_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission("operations.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Operations overview - super admin sees all, agents see own scope."""
    # Active conversations
    active_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.is_sleeping == False, Conversation.status == "open"),
            actor, Conversation.account_id,
        )
    ) or 0

    sleeping_conversations = session.scalar(
        _apply_account_scope(
            select(func.count(Conversation.id)).where(Conversation.is_sleeping == True),
            actor, Conversation.account_id,
        )
    ) or 0

    # Tickets needing attention
    open_tickets = session.scalar(
        _apply_account_scope(
            select(func.count(Ticket.id)).where(Ticket.status == "open"),
            actor, Ticket.account_id,
        )
    ) or 0

    # Task instances running
    running_tasks = session.scalar(
        _apply_account_scope(
            select(func.count(MktTaskInstance.id)).where(MktTaskInstance.status == "running"),
            actor, MktTaskInstance.account_id,
        )
    ) or 0

    pending_tasks = session.scalar(
        _apply_account_scope(
            select(func.count(MktTaskInstance.id)).where(MktTaskInstance.status == "pending"),
            actor, MktTaskInstance.account_id,
        )
    ) or 0

    # Product stats
    total_products = session.scalar(
        _apply_account_scope(select(func.count(Product.id)), actor, Product.account_id)
    ) or 0
    total_packages = session.scalar(
        _apply_account_scope(select(func.count(ProductPackage.id)), actor, ProductPackage.account_id)
    ) or 0

    # Billing overview — only super admin sees billing data
    billing_query = _apply_billing_scope(select(AgencyBilling), actor)
    if agency_id and actor.is_super_admin:
        billing_query = billing_query.where(AgencyBilling.agency_id == agency_id)
    all_billings = list(session.execute(billing_query).scalars().all())
    pending_billing_count = sum(1 for b in all_billings if b.status == "pending")
    total_billing_amount = sum(float(b.amount) for b in all_billings)
    pending_billing_amount = sum(float(b.amount) for b in all_billings if b.status == "pending")

    # Notifications
    unread_notifications = session.scalar(
        _apply_account_scope(
            select(func.count(Notification.id)).where(Notification.is_read == False),
            actor, Notification.account_id,
        )
    ) or 0

    return {
        "active_conversations": active_conversations,
        "sleeping_conversations": sleeping_conversations,
        "open_tickets": open_tickets,
        "running_tasks": running_tasks,
        "pending_tasks": pending_tasks,
        "total_products": total_products,
        "total_packages": total_packages,
        "pending_billing_count": pending_billing_count,
        "total_billing_amount": total_billing_amount,
        "pending_billing_amount": pending_billing_amount,
        "unread_notifications": unread_notifications,
    }

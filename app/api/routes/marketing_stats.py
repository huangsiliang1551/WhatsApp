from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import (
    InviteRecord,
    MktTaskInstance,
    Product,
    ProductPackage,
    SignInRecord,
)

router = APIRouter(prefix="/api/marketing/stats", tags=["marketing"])


@router.get("/packages")
async def package_stats(
    account_id: str = "",
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    items = session.execute(
        select(
            ProductPackage.id,
            ProductPackage.name,
            func.count(MktTaskInstance.id).label("total_created"),
        )
        .outerjoin(MktTaskInstance, MktTaskInstance.package_id == ProductPackage.id)
        .where(ProductPackage.account_id == account_id)
        .group_by(ProductPackage.id, ProductPackage.name)
    ).all()

    result = []
    for row in items:
        completed = session.execute(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.package_id == row.id,
                MktTaskInstance.status == "completed",
            )
        ).scalar() or 0
        running = session.execute(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.package_id == row.id,
                MktTaskInstance.status == "running",
            )
        ).scalar() or 0
        total_claimed = completed + running
        comp_rate = round(completed / total_claimed * 100, 2) if total_claimed > 0 else 0.0
        result.append({
            "package_id": row.id,
            "package_name": row.name,
            "total_created": row.total_created or 0,
            "total_claimed": total_claimed,
            "completion_count": completed,
            "completion_rate": comp_rate,
        })
    return {"items": result}


@router.get("/tasks")
async def task_stats(
    account_id: str = "",
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    items = session.execute(
        select(
            MktTaskInstance.task_type,
            func.count(MktTaskInstance.id).label("trigger_count"),
            func.sum(MktTaskInstance.reward_amount).label("total_reward"),
        )
        .where(MktTaskInstance.account_id == account_id)
        .group_by(MktTaskInstance.task_type)
    ).all()

    result = []
    for row in items:
        completed = session.execute(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.account_id == account_id,
                MktTaskInstance.task_type == row.task_type,
                MktTaskInstance.status == "completed",
            )
        ).scalar() or 0
        total = row.trigger_count or 0
        comp_rate = round(completed / total * 100, 2) if total > 0 else 0.0
        result.append({
            "task_type": row.task_type,
            "trigger_count": total,
            "completed_count": completed,
            "total_reward": Decimal(str(row.total_reward or 0)),
            "completion_rate": comp_rate,
        })
    return {"items": result}


@router.get("/overview")
async def overview_stats(
    account_id: str = "",
    actor: RequestActor = Depends(require_permission("tasks.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    today = date.today()
    today_sign_ins = session.execute(
        select(func.count(SignInRecord.id)).where(
            SignInRecord.account_id == account_id,
            SignInRecord.sign_date == today,
        )
    ).scalar() or 0

    today_invites = session.execute(
        select(func.count(InviteRecord.id)).where(
            InviteRecord.account_id == account_id,
            func.date(InviteRecord.created_at) == today,
        )
    ).scalar() or 0

    today_pushes = session.execute(
        select(func.count(MktTaskInstance.id)).where(
            MktTaskInstance.account_id == account_id,
            func.date(MktTaskInstance.created_at) == today,
        )
    ).scalar() or 0

    total_products = session.execute(
        select(func.count(Product.id)).where(Product.account_id == account_id)
    ).scalar() or 0

    total_packages = session.execute(
        select(func.count(ProductPackage.id)).where(ProductPackage.account_id == account_id)
    ).scalar() or 0

    return {
        "today_sign_ins": today_sign_ins,
        "today_invites": today_invites,
        "today_push_count": today_pushes,
        "total_products": total_products,
        "total_packages": total_packages,
    }

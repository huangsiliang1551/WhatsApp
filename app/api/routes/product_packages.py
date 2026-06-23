from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.schemas.marketing import (
    AssemblePreviewRequest,
    AssemblePreviewResponse,
    PackageCreateRequest,
    PackageUpdateRequest,
)
from app.services.product_package_service import ProductPackageService

router = APIRouter(prefix="/api/product-packages", tags=["marketing"])


@router.get("")
async def list_packages(
    account_id: str | None = Query(default=None, min_length=1),
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = ProductPackageService(session)
    return svc.list_packages(account_id)


@router.post("/assemble-preview")
async def assemble_preview(
    payload: AssemblePreviewRequest,
    account_id: str = Query(..., min_length=1),
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(account_id)
    svc = ProductPackageService(session)
    try:
        result = svc.preview_assemble(
            target_amount=payload.target_amount,
            tolerance_pct=payload.tolerance_pct,
            product_count=payload.product_count,
            account_id=account_id,
        )
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", status_code=201)
async def create_package(
    payload: PackageCreateRequest,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(payload.account_id)
    svc = ProductPackageService(session)
    try:
        pkg = svc.create_package(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": pkg.id,
        "account_id": pkg.account_id,
        "name": pkg.name,
        "target_amount": pkg.target_amount,
        "amount_tolerance_pct": pkg.amount_tolerance_pct,
        "product_count": pkg.product_count,
        "product_ids": pkg.product_ids,
        "product_snapshot": pkg.product_snapshot,
        "total_value": pkg.total_value,
        "completion_reward": pkg.completion_reward,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
    }


@router.get("/{package_id}")
async def get_package(
    package_id: str,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ProductPackageService(session)
    try:
        pkg = svc.get_package(package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    d = {
        "id": pkg.id,
        "account_id": pkg.account_id,
        "name": pkg.name,
        "target_amount": pkg.target_amount,
        "amount_tolerance_pct": pkg.amount_tolerance_pct,
        "product_count": pkg.product_count,
        "product_ids": pkg.product_ids,
        "product_snapshot": pkg.product_snapshot,
        "total_value": pkg.total_value,
        "completion_reward": pkg.completion_reward,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
    }
    d["claim_count"] = svc._count_claims(pkg.id)
    d["completion_rate"] = svc._completion_rate(pkg.id)
    return d


@router.patch("/{package_id}")
async def update_package(
    package_id: str,
    payload: PackageUpdateRequest,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ProductPackageService(session)
    try:
        pkg = svc.update_package(package_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": pkg.id,
        "account_id": pkg.account_id,
        "name": pkg.name,
        "target_amount": pkg.target_amount,
        "amount_tolerance_pct": pkg.amount_tolerance_pct,
        "product_count": pkg.product_count,
        "product_ids": pkg.product_ids,
        "product_snapshot": pkg.product_snapshot,
        "total_value": pkg.total_value,
        "completion_reward": pkg.completion_reward,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
    }


@router.delete("/{package_id}", status_code=204)
async def delete_package(
    package_id: str,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> Response:
    svc = ProductPackageService(session)
    try:
        svc.delete_package(package_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)

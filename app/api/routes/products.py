from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.datastructures import UploadFile
from fastapi.params import File, Form

from app.api.deps import (
    get_db_session,
    require_permission,
)
from app.core.auth import RequestActor, get_effective_account_ids
from app.schemas.marketing import (
    ProductCreateRequest,
    ProductUpdateRequest,
)
from app.services.product_service import ProductService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/products", tags=["marketing"])


@router.get("")
async def list_products(
    account_id: str | None = Query(default=None, min_length=1),
    page: int | None = Query(default=None, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    tags: str | None = Query(default=None),  # comma-separated
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = ProductService(session)
    tag_list = tags.split(",") if tags else None
    return svc.list_products(
        account_id=account_id,
        account_ids=get_effective_account_ids(actor),
        page=page,
        size=size,
        search=search,
        tags=tag_list,
    )


@router.post("", status_code=201)
async def create_product(
    payload: ProductCreateRequest,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(payload.account_id)
    svc = ProductService(session)
    product = svc.create_product(payload)
    return {
        "id": product.id,
        "account_id": product.account_id,
        "name": product.name,
        "image_asset_id": product.image_asset_id,
        "price": product.price,
        "tags": product.tags,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


@router.patch("/{product_id}")
async def update_product(
    product_id: str,
    payload: ProductUpdateRequest,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = ProductService(session)
    try:
        product = svc.update_product(product_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": product.id,
        "account_id": product.account_id,
        "name": product.name,
        "image_asset_id": product.image_asset_id,
        "price": product.price,
        "tags": product.tags,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> Response:
    svc = ProductService(session)
    try:
        svc.delete_product(product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/import", status_code=201)
async def import_products_csv(
    account_id: str = Form(...),
    file: UploadFile = File(...),
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(account_id)
    content = (await file.read()).decode("utf-8-sig")
    svc = ProductService(session)
    count = svc.import_csv(account_id, content)
    return {"imported_count": count}


@router.get("/export")
async def export_products_csv(
    account_id: str = Query(..., min_length=1),
    actor: RequestActor = Depends(require_permission("ecommerce.view")),
    session: Session = Depends(get_db_session),
) -> Response:
    actor.require_account_access(account_id)
    svc = ProductService(session)
    csv_content = svc.export_csv(account_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=products-{account_id}.csv"},
    )

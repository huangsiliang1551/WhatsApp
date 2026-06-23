from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any

from sqlalchemy import cast, select, String
from sqlalchemy.orm import Session

from app.db.models import Product, ProductPackage
from app.schemas.marketing import (
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
)


class ProductService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_products(
        self,
        account_id: str | None = None,
        account_ids: set[str] | None = None,
        page: int | None = None,
        size: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        query = select(Product).order_by(Product.created_at.desc())
        if account_ids is not None:
            if not account_ids:
                return {"items": [], "total": 0, "page": page, "size": size}
            query = query.where(Product.account_id.in_(sorted(account_ids)))
        elif account_id:
            query = query.where(Product.account_id == account_id)
        if search:
            query = query.where(Product.name.ilike(f"%{search}%"))
        if tags:
            for tag in tags:
                query = query.where(Product.tags["tags"].as_string().contains(tag))

        if page is not None:
            total_query = select(Product)
            if account_id:
                total_query = total_query.where(Product.account_id == account_id)
            total = self._session.execute(total_query).scalars().all()
            total_count = len(total)
            offset = (page - 1) * size
            items = self._session.execute(query.offset(offset).limit(size)).scalars().all()
            return {
                "items": [self._to_response(p) for p in items],
                "total": total_count,
            }
        items = self._session.execute(query).scalars().all()
        return {
            "items": [self._to_response(p) for p in items],
            "total": len(items),
        }

    def get_product(self, product_id: str) -> Product:
        product = self._session.get(Product, product_id)
        if product is None:
            raise LookupError(f"Product '{product_id}' not found.")
        return product

    def create_product(self, payload: ProductCreateRequest) -> Product:
        product = Product(
            account_id=payload.account_id,
            name=payload.name,
            image_asset_id=payload.image_asset_id,
            price=payload.price,
            tags=payload.tags,
        )
        self._session.add(product)
        self._session.commit()
        self._session.refresh(product)
        return product

    def update_product(self, product_id: str, payload: ProductUpdateRequest) -> Product:
        product = self._session.get(Product, product_id)
        if product is None:
            raise LookupError(f"Product '{product_id}' not found.")
        if payload.name is not None:
            product.name = payload.name
        if payload.image_asset_id is not None:
            product.image_asset_id = payload.image_asset_id
        if payload.price is not None:
            product.price = payload.price
        if payload.tags is not None:
            product.tags = payload.tags
        self._session.commit()
        self._session.refresh(product)
        return product

    def delete_product(self, product_id: str) -> None:
        product = self._session.get(Product, product_id)
        if product is None:
            raise LookupError(f"Product '{product_id}' not found.")
        # Check if referenced by any package
        packages = self._session.execute(
            select(ProductPackage).where(cast(ProductPackage.product_ids, String).contains(product_id))
        ).scalars().all()
        if packages:
            raise ValueError(f"Product '{product_id}' is referenced by {len(packages)} package(s).")
        self._session.delete(product)
        self._session.commit()

    def import_csv(self, account_id: str, csv_content: str) -> int:
        reader = csv.DictReader(io.StringIO(csv_content))
        count = 0
        for row in reader:
            product = Product(
                account_id=account_id,
                name=row["name"].strip(),
                price=Decimal(row["price"].strip()),
                image_asset_id=row.get("image_asset_id", "").strip() or None,
                tags=[t.strip() for t in row.get("tags", "").split(",") if t.strip()] if row.get("tags") else None,
            )
            self._session.add(product)
            count += 1
        self._session.commit()
        return count

    def export_csv(self, account_id: str) -> str:
        products = self._session.execute(
            select(Product).where(Product.account_id == account_id).order_by(Product.created_at)
        ).scalars().all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "price", "image_asset_id", "tags"])
        for p in products:
            tags_str = ",".join(p.tags) if p.tags else ""
            writer.writerow([p.name, str(p.price), p.image_asset_id or "", tags_str])
        return output.getvalue()

    def _to_response(self, product: Product) -> dict[str, Any]:
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

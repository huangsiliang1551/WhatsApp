from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Product, ProductPackage
from app.schemas.marketing import AssemblePreviewResponse, PackageCreateRequest, PackageUpdateRequest


class ProductPackageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_packages(self, account_id: str | None = None) -> dict[str, Any]:
        query = select(ProductPackage).order_by(ProductPackage.created_at.desc())
        if account_id:
            query = query.where(ProductPackage.account_id == account_id)
        items = self._session.execute(query).scalars().all()
        result = []
        for pkg in items:
            d = self._to_response(pkg)
            d["claim_count"] = self._count_claims(pkg.id)
            d["completion_rate"] = self._completion_rate(pkg.id)
            result.append(d)
        return {"items": result, "total": len(result)}

    def get_package(self, package_id: str) -> ProductPackage:
        pkg = self._session.get(ProductPackage, package_id)
        if pkg is None:
            raise LookupError(f"Product package '{package_id}' not found.")
        return pkg

    def create_package(self, payload: PackageCreateRequest) -> ProductPackage:
        products = self._assemble_package(
            target_amount=payload.target_amount,
            tolerance_pct=payload.amount_tolerance_pct,
            product_count=payload.product_count,
            account_id=payload.account_id,
        )
        snapshot = [
            {"id": p.id, "name": p.name, "price": str(p.price), "image_url": None}
            for p in products
        ]
        total_value = sum(p.price for p in products)
        pkg = ProductPackage(
            account_id=payload.account_id,
            name=payload.name,
            target_amount=payload.target_amount,
            amount_tolerance_pct=payload.amount_tolerance_pct,
            product_count=payload.product_count,
            product_ids=[p.id for p in products],
            product_snapshot=snapshot,
            total_value=total_value,
            completion_reward=payload.completion_reward,
        )
        self._session.add(pkg)
        self._session.commit()
        self._session.refresh(pkg)
        return pkg

    def update_package(self, package_id: str, payload: PackageUpdateRequest) -> ProductPackage:
        pkg = self._session.get(ProductPackage, package_id)
        if pkg is None:
            raise LookupError(f"Product package '{package_id}' not found.")
        if payload.name is not None:
            pkg.name = payload.name
        if payload.completion_reward is not None:
            pkg.completion_reward = payload.completion_reward
        self._session.commit()
        self._session.refresh(pkg)
        return pkg

    def delete_package(self, package_id: str) -> None:
        pkg = self._session.get(ProductPackage, package_id)
        if pkg is None:
            raise LookupError(f"Product package '{package_id}' not found.")
        # Check if referenced by task rules
        from app.db.models import TaskRule
        rules = self._session.execute(
            select(TaskRule).where(TaskRule.package_id == package_id)
        ).scalars().all()
        if rules:
            raise ValueError(f"Package '{package_id}' is referenced by {len(rules)} rule(s).")
        self._session.delete(pkg)
        self._session.commit()

    def preview_assemble(
        self,
        target_amount: Decimal,
        tolerance_pct: int,
        product_count: int,
        account_id: str,
    ) -> AssemblePreviewResponse:
        products = self._assemble_package(target_amount, tolerance_pct, product_count, account_id)
        total_value = sum(p.price for p in products)
        deviation = abs(float(total_value - target_amount)) / float(target_amount) * 100
        within_range = deviation <= tolerance_pct
        return AssemblePreviewResponse(
            items=[{"id": p.id, "name": p.name, "price": p.price} for p in products],
            total_value=total_value,
            target_amount=target_amount,
            deviation_pct=round(deviation, 2),
            within_range=within_range,
            tolerance_pct=tolerance_pct,
        )

    def _assemble_package(
        self,
        target_amount: Decimal,
        tolerance_pct: int,
        product_count: int,
        account_id: str,
    ) -> list[Product]:
        all_products = self._session.execute(
            select(Product).where(Product.account_id == account_id)
        ).scalars().all()
        if len(all_products) < product_count:
            raise ValueError(
                f"Not enough products ({len(all_products)}) to assemble a package of {product_count}."
            )

        tolerance = Decimal(tolerance_pct) / Decimal(100)
        min_amount = target_amount * (Decimal(1) - tolerance)
        max_amount = target_amount * (Decimal(1) + tolerance)

        best_combination = None
        best_diff = Decimal("Infinity")
        max_attempts = min(100, 1000)

        for _ in range(max_attempts):
            selected = random.sample(all_products, min(product_count, len(all_products)))
            total = sum(p.price for p in selected)
            if min_amount <= total <= max_amount:
                return selected
            diff = abs(total - target_amount)
            if diff < best_diff:
                best_diff = diff
                best_combination = list(selected)

        if best_combination:
            return best_combination
        raise ValueError(
            f"Could not assemble package within ±{tolerance_pct}% of {target_amount} "
            f"after {max_attempts} attempts."
        )

    def _count_claims(self, package_id: str) -> int:
        from app.db.models import MktTaskInstance
        return self._session.execute(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.package_id == package_id,
                MktTaskInstance.status.in_(["running", "completed"]),
            )
        ).scalar() or 0

    def _completion_rate(self, package_id: str) -> float:
        from app.db.models import MktTaskInstance
        total = self._session.execute(
            select(func.count(MktTaskInstance.id)).where(MktTaskInstance.package_id == package_id)
        ).scalar() or 0
        if total == 0:
            return 0.0
        completed = self._session.execute(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.package_id == package_id,
                MktTaskInstance.status == "completed",
            )
        ).scalar() or 0
        return round(completed / total * 100, 2)

    def _to_response(self, pkg: ProductPackage) -> dict[str, Any]:
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
            "claim_count": 0,
            "completion_rate": 0.0,
        }

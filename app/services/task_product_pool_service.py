from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Site, TaskProductPool, TaskProductPoolItem
from app.schemas.task_product_pool import (
    TaskProductPoolCreateRequest,
    TaskProductPoolImportRequest,
    TaskProductPoolItemsRequest,
    TaskProductPoolItemUpdateRequest,
    TaskProductPoolItemResponse,
    TaskProductPoolResponse,
    TaskProductPoolUpdateRequest,
)


class TaskProductPoolService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_pools(
        self,
        *,
        account_id: str | None = None,
        site_id: str | None = None,
        status: str | None = None,
    ) -> list[TaskProductPoolResponse]:
        pools = self._session.scalars(
            select(TaskProductPool).where(
                TaskProductPool.account_id == account_id if account_id is not None else True,
                TaskProductPool.site_id == site_id if site_id is not None else True,
                TaskProductPool.status == status if status is not None else True,
            ).order_by(TaskProductPool.created_at.desc(), TaskProductPool.id.desc())
        ).all()
        return [self._serialize(pool) for pool in pools]

    def create_pool(self, payload: TaskProductPoolCreateRequest) -> TaskProductPoolResponse:
        self._validate_site_scope(account_id=payload.account_id, site_id=payload.site_id)
        pool = TaskProductPool(
            account_id=payload.account_id,
            site_id=payload.site_id,
            name=payload.name,
            code=payload.code,
            pool_type=payload.pool_type,
            price_mode=payload.price_mode,
            allow_repeat_in_same_batch=payload.allow_repeat_in_same_batch,
            allow_repeat_in_same_package=payload.allow_repeat_in_same_package,
            status=payload.status,
            currency=payload.currency,
            metadata_json=payload.metadata_json,
        )
        self._session.add(pool)
        self._session.flush()

        for item in payload.items:
            self._session.add(
                TaskProductPoolItem(
                    account_id=payload.account_id,
                    pool_id=pool.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    image_url=item.image_url,
                    price=item.price,
                    currency=item.currency,
                    product_description=item.product_description,
                    status=item.status,
                    sort_order=item.sort_order,
                    weight=item.weight,
                    metadata_json=item.metadata_json,
                )
            )

        self._session.commit()
        self._session.refresh(pool)
        return self._serialize(pool)

    def get_pool(self, pool_id: str) -> TaskProductPoolResponse:
        return self._serialize(self._require_pool(pool_id))

    def update_pool(self, pool_id: str, payload: TaskProductPoolUpdateRequest) -> TaskProductPoolResponse:
        pool = self._require_pool(pool_id)
        target_site_id = payload.site_id if payload.site_id is not None else pool.site_id
        self._validate_site_scope(account_id=pool.account_id, site_id=target_site_id)
        pool.site_id = target_site_id
        pool.name = payload.name or pool.name
        pool.code = payload.code if payload.code is not None else pool.code
        pool.pool_type = payload.pool_type or pool.pool_type
        pool.price_mode = payload.price_mode or pool.price_mode
        if payload.allow_repeat_in_same_batch is not None:
            pool.allow_repeat_in_same_batch = payload.allow_repeat_in_same_batch
        if payload.allow_repeat_in_same_package is not None:
            pool.allow_repeat_in_same_package = payload.allow_repeat_in_same_package
        pool.status = payload.status or pool.status
        pool.currency = payload.currency or pool.currency
        if payload.metadata_json is not None:
            pool.metadata_json = payload.metadata_json
        self._session.add(pool)
        self._session.commit()
        self._session.refresh(pool)
        return self._serialize(pool)

    def add_items(self, pool_id: str, payload: TaskProductPoolItemsRequest) -> TaskProductPoolResponse:
        pool = self._require_pool(pool_id)
        current_max_sort = self._session.scalars(
            select(TaskProductPoolItem.sort_order)
            .where(TaskProductPoolItem.pool_id == pool.id)
            .order_by(TaskProductPoolItem.sort_order.desc())
        ).first() or 0
        next_sort = current_max_sort
        for item in payload.items:
            next_sort = max(next_sort + 1, item.sort_order)
            self._session.add(
                TaskProductPoolItem(
                    account_id=pool.account_id,
                    pool_id=pool.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    image_url=item.image_url,
                    price=item.price,
                    currency=item.currency,
                    product_description=item.product_description,
                    status=item.status,
                    sort_order=next_sort,
                    weight=item.weight,
                    metadata_json=item.metadata_json,
                )
            )
        self._session.commit()
        self._session.refresh(pool)
        return self._serialize(pool)

    def import_items(self, pool_id: str, payload: TaskProductPoolImportRequest) -> TaskProductPoolResponse:
        pool = self._require_pool(pool_id)
        if payload.replace_existing:
            existing_items = self._session.scalars(
                select(TaskProductPoolItem).where(TaskProductPoolItem.pool_id == pool.id)
            ).all()
            for item in existing_items:
                self._session.delete(item)
            self._session.flush()

        for item in payload.items:
            self._session.add(
                TaskProductPoolItem(
                    account_id=pool.account_id,
                    pool_id=pool.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    image_url=item.image_url,
                    price=item.price,
                    currency=item.currency,
                    product_description=item.product_description,
                    status=item.status,
                    sort_order=item.sort_order,
                    weight=item.weight,
                    metadata_json=item.metadata_json,
                )
            )
        self._session.commit()
        self._session.refresh(pool)
        return self._serialize(pool)

    def update_pool_item(self, item_id: str, payload: TaskProductPoolItemUpdateRequest) -> TaskProductPoolItemResponse:
        item = self._require_pool_item(item_id)
        item.product_id = payload.product_id or item.product_id
        item.product_name = payload.product_name or item.product_name
        item.image_url = payload.image_url if payload.image_url is not None else item.image_url
        item.price = payload.price if payload.price is not None else item.price
        item.currency = payload.currency or item.currency
        item.product_description = (
            payload.product_description if payload.product_description is not None else item.product_description
        )
        item.status = payload.status or item.status
        item.sort_order = payload.sort_order if payload.sort_order is not None else item.sort_order
        item.weight = payload.weight if payload.weight is not None else item.weight
        if payload.metadata_json is not None:
            item.metadata_json = payload.metadata_json
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return self._serialize_item(item)

    def delete_pool_item(self, item_id: str) -> None:
        item = self._require_pool_item(item_id)
        self._session.delete(item)
        self._session.commit()

    def _serialize(self, pool: TaskProductPool) -> TaskProductPoolResponse:
        items = self._session.scalars(
            select(TaskProductPoolItem)
            .where(TaskProductPoolItem.pool_id == pool.id)
            .order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc())
        ).all()
        return TaskProductPoolResponse(
            id=pool.id,
            account_id=pool.account_id,
            site_id=pool.site_id,
            name=pool.name,
            code=pool.code,
            pool_type=pool.pool_type,
            price_mode=pool.price_mode,
            allow_repeat_in_same_batch=pool.allow_repeat_in_same_batch,
            allow_repeat_in_same_package=pool.allow_repeat_in_same_package,
            status=pool.status,
            currency=pool.currency,
            metadata_json=pool.metadata_json,
            item_count=len(items),
            items=[self._serialize_item(item) for item in items],
            created_at=pool.created_at,
            updated_at=pool.updated_at,
        )

    def _validate_site_scope(self, *, account_id: str, site_id: str | None) -> None:
        if site_id is None:
            return
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"Task product pool site '{site_id}' was not found.")
        if site.account_id != account_id:
            raise ValueError("Task product pool site account scope mismatch.")

    def _require_pool(self, pool_id: str) -> TaskProductPool:
        pool = self._session.get(TaskProductPool, pool_id)
        if pool is None:
            raise LookupError(f"Task product pool '{pool_id}' was not found.")
        return pool

    def _require_pool_item(self, item_id: str) -> TaskProductPoolItem:
        item = self._session.get(TaskProductPoolItem, item_id)
        if item is None:
            raise LookupError(f"Task product pool item '{item_id}' was not found.")
        return item

    @staticmethod
    def _serialize_item(item: TaskProductPoolItem) -> TaskProductPoolItemResponse:
        return TaskProductPoolItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            image_url=item.image_url,
            price=item.price,
            currency=item.currency,
            product_description=item.product_description,
            status=item.status,
            sort_order=item.sort_order,
            weight=item.weight,
            metadata_json=item.metadata_json,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

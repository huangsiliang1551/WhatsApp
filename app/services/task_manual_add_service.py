from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AppUser,
    H5Site,
    MemberTaskBatch,
    MemberTaskDayQuota,
    new_id,
    TaskManualAddItemLog,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplateItem,
    TaskProductPool,
    TaskProductPoolItem,
    utc_now,
)
from app.schemas.member_task_quota import MemberTaskDayQuotaResponse


TWOPLACES = Decimal("0.01")


class TaskManualAddService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def get_package_detail(self, *, package_id: str) -> tuple[TaskPackageInstance, list[TaskManualAddItemLog]]:
        package = self._require_package(package_id=package_id)
        logs = self.list_logs(package_id=package_id)
        return package, logs

    def list_packages(
        self,
        *,
        account_id: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
    ) -> list[tuple[TaskPackageInstance, str, str | None]]:
        rows = self._session.execute(
            select(TaskPackageInstance, AppUser.public_user_id, H5Site.site_key)
            .join(AppUser, AppUser.id == TaskPackageInstance.user_id)
            .outerjoin(H5Site, H5Site.id == TaskPackageInstance.site_id)
            .options(joinedload(TaskPackageInstance.items))
            .where(
                TaskPackageInstance.account_id == account_id if account_id is not None else True,
                TaskPackageInstance.status == status if status is not None else True,
                TaskPackageInstance.user_id == user_id if user_id is not None else True,
            )
            .order_by(TaskPackageInstance.created_at.desc(), TaskPackageInstance.id.desc())
        ).unique().all()
        return [(package, public_user_id, site_key) for package, public_user_id, site_key in rows]

    def list_logs(self, *, package_id: str) -> list[TaskManualAddItemLog]:
        self._require_package(package_id=package_id)
        return self._session.scalars(
            select(TaskManualAddItemLog)
            .where(TaskManualAddItemLog.package_instance_id == package_id)
            .order_by(TaskManualAddItemLog.created_at.desc(), TaskManualAddItemLog.id.desc())
        ).all()

    def list_available_pool_items(self, *, package_id: str) -> list[TaskProductPoolItem]:
        package = self._require_package(package_id=package_id)
        pool = self._require_product_pool(package=package)
        used_product_ids = set(self._load_restricted_product_ids(package=package, pool=pool))
        return self._session.scalars(
            select(TaskProductPoolItem)
            .where(
                TaskProductPoolItem.pool_id == pool.id,
                TaskProductPoolItem.status == "active",
                TaskProductPoolItem.product_id.not_in(sorted(used_product_ids)) if used_product_ids else True,
            )
            .order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc())
        ).all()

    def preview_add_items(
        self,
        *,
        package_id: str,
        pool_item_ids: list[str],
    ) -> tuple[TaskPackageInstance, list[TaskProductPoolItem], Decimal]:
        package = self._require_package(package_id=package_id)
        if package.status in {"completed", "expired"}:
            raise ValueError("Task package does not allow manual add in current status.")

        pool = self._require_product_pool(package=package)
        used_product_ids = set(self._load_restricted_product_ids(package=package, pool=pool))
        pool_items = self._session.scalars(
            select(TaskProductPoolItem)
            .where(
                TaskProductPoolItem.id.in_(pool_item_ids),
                TaskProductPoolItem.pool_id == pool.id,
                TaskProductPoolItem.status == "active",
            )
            .order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc())
        ).all()
        if len(pool_items) != len(pool_item_ids):
            raise LookupError("Some task product pool items were not found.")

        duplicate_product_ids = [item.product_id for item in pool_items if item.product_id in used_product_ids]
        if duplicate_product_ids:
            raise ValueError("Manual add products already exist in current batch.")

        added_amount = self._quantize(sum((Decimal(item.price) for item in pool_items), start=Decimal("0.00")))
        return package, pool_items, added_amount

    def add_items(
        self,
        *,
        package_id: str,
        pool_item_ids: list[str],
        operator_id: str,
        reason_text: str | None,
        notify_user: bool = False,
        user_notice_text: str | None = None,
    ) -> TaskManualAddItemLog:
        package = self._require_package(package_id=package_id, for_update=True)
        if package.status in {"completed", "expired"}:
            raise ValueError("Task package does not allow manual add in current status.")

        pool = self._require_product_pool(package=package)
        pool_id = pool.id
        used_product_ids = set(self._load_restricted_product_ids(package=package, pool=pool))
        pool_items = self._session.scalars(
            select(TaskProductPoolItem)
            .where(
                TaskProductPoolItem.id.in_(pool_item_ids),
                TaskProductPoolItem.pool_id == pool_id,
                TaskProductPoolItem.status == "active",
            )
            .order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc())
        ).all()
        if len(pool_items) != len(pool_item_ids):
            raise LookupError("Some task product pool items were not found.")

        duplicate_product_ids = [item.product_id for item in pool_items if item.product_id in used_product_ids]
        if duplicate_product_ids:
            raise ValueError("Manual add products already exist in current batch.")

        next_sort_order = (
            self._session.scalar(
                select(func.coalesce(func.max(TaskPackageInstanceItem.sort_order), 0)).where(
                    TaskPackageInstanceItem.package_instance_id == package.id
                )
            )
            or 0
        ) + 1
        next_template_sort_order = (
            self._session.scalar(
                select(func.coalesce(func.max(TaskPackageTemplateItem.sort_order), 0)).where(
                    TaskPackageTemplateItem.template_id == package.template_id
                )
            )
            or 0
        ) + 1
        added_amount = self._quantize(sum((Decimal(item.price) for item in pool_items), start=Decimal("0.00")))
        before_manual_added_amount = self._quantize(Decimal(package.manual_added_amount))
        before_effective_amount = self._quantize(Decimal(package.effective_amount))
        log_created_at = utc_now()
        log_id = new_id()

        log = TaskManualAddItemLog(
            id=log_id,
            account_id=package.account_id,
            site_id=package.site_id,
            user_id=package.user_id,
            batch_id=package.batch_id,
            package_instance_id=package.id,
            operator_id=operator_id,
            reason_text=reason_text,
            notify_user=notify_user,
            user_notice_text=user_notice_text,
            user_notified_at=utc_now() if notify_user else None,
            added_item_count=len(pool_items),
            added_amount=added_amount,
            before_manual_added_amount=before_manual_added_amount,
            after_manual_added_amount=self._quantize(before_manual_added_amount + added_amount),
            before_effective_amount=before_effective_amount,
            after_effective_amount=self._quantize(before_effective_amount + added_amount),
            metadata_json={"pool_item_ids": [item.id for item in pool_items]},
            created_at=log_created_at,
            updated_at=log_created_at,
        )
        self._session.add(log)

        for index, pool_item in enumerate(pool_items, start=0):
            template_item_id = new_id()
            template_item = TaskPackageTemplateItem(
                id=template_item_id,
                account_id=package.account_id,
                template_id=package.template_id,
                sort_order=next_template_sort_order + index,
                product_name=pool_item.product_name,
                image_url=pool_item.image_url,
                price=pool_item.price,
                currency=pool_item.currency,
                metadata_json={
                    "product_id": pool_item.product_id,
                    "pool_item_id": pool_item.id,
                    "product_description": pool_item.product_description,
                    "source": "task_manual_add",
                },
            )
            self._session.add(template_item)

            self._session.add(
                TaskPackageInstanceItem(
                    account_id=package.account_id,
                    batch_id=package.batch_id,
                    quota_id=package.quota_id,
                    package_instance_id=package.id,
                    template_item_id=template_item_id,
                    item_origin="manual_added",
                    is_required=True,
                    product_pool_id=pool_id,
                    pool_item_id=pool_item.id,
                    product_id=pool_item.product_id,
                    product_name_snapshot=pool_item.product_name,
                    product_image_url_snapshot=pool_item.image_url,
                    product_description_snapshot=pool_item.product_description,
                    price_snapshot=pool_item.price,
                    sort_order=next_sort_order + index,
                    product_name=pool_item.product_name,
                    image_url=pool_item.image_url,
                    price=pool_item.price,
                    currency=pool_item.currency,
                    status="pending",
                    visible_to_user=False,
                    manual_add_log_id=log.id,
                    metadata_json={"source": "task_manual_add"},
                )
            )

        package.manual_added_amount = self._quantize(Decimal(package.manual_added_amount) + added_amount)
        package.effective_amount = self._quantize(Decimal(package.system_generated_amount) + Decimal(package.manual_added_amount))
        package.manual_added_item_count = int(package.manual_added_item_count or 0) + len(pool_items)
        package.required_item_count = int(package.required_item_count or 0) + len(pool_items)
        package.last_manual_added_at = log_created_at
        # Product rule: backend manual-add records stay in ops/audit logs only.
        # H5 should not surface a package adjustment notice for this action,
        # even if a legacy caller still submits notify_user/user_notice_text.
        package.has_adjustment_notice = False
        package.adjustment_notice = None
        self._session.add(package)

        if package.batch_id is not None:
            batch = self._session.get(MemberTaskBatch, package.batch_id)
            if batch is not None:
                batch.manual_added_amount = self._quantize(Decimal(batch.manual_added_amount) + added_amount)
                batch.effective_day_amount = self._quantize(
                    Decimal(batch.system_generated_amount) + Decimal(batch.manual_added_amount)
                )
                self._session.add(batch)

        self._session.commit()
        self._session.refresh(log)
        return log

    def pause_package(
        self,
        *,
        package_id: str,
        reason_text: str | None,
    ) -> TaskPackageInstance:
        package = self._require_package(package_id=package_id, for_update=True)
        if package.status in {"completed", "expired", "cancelled"}:
            raise ValueError("Task package cannot be paused in current status.")
        if package.status != "paused":
            package.status = "paused"
        package.pause_reason = reason_text or package.pause_reason or "manual_pause"
        self._session.add(package)
        self._session.commit()
        self._session.refresh(package)
        return package

    def resume_package(
        self,
        *,
        package_id: str,
        reason_text: str | None,
    ) -> TaskPackageInstance:
        package = self._require_package(package_id=package_id, for_update=True)
        if package.status != "paused":
            raise ValueError("Only paused task packages can be resumed.")
        package.status = "active" if package.claimed_at is not None else "pending_claim"
        package.pause_reason = None
        metadata_json = dict(package.metadata_json or {})
        if reason_text:
            metadata_json["last_resume_reason"] = reason_text
        package.metadata_json = metadata_json or None
        self._session.add(package)
        self._session.commit()
        self._session.refresh(package)
        return package

    def cancel_package(
        self,
        *,
        package_id: str,
        reason_text: str | None,
    ) -> TaskPackageInstance:
        package = self._require_package(package_id=package_id, for_update=True)
        if package.status in {"completed", "expired", "cancelled"}:
            raise ValueError("Task package cannot be cancelled in current status.")
        package.status = "cancelled"
        package.locked_reason = reason_text or package.locked_reason or "manual_cancel"
        package.pause_reason = None
        self._session.add(package)
        self._session.commit()
        self._session.refresh(package)
        return package

    def cancel_next_pending_quota_for_package(
        self,
        *,
        package_id: str,
        reason: str | None,
        cancelled_by: str | None = None,
    ) -> MemberTaskDayQuotaResponse:
        package = self._require_package(package_id=package_id, for_update=True)
        if package.batch_id is None:
            raise ValueError("Task package is not linked to a batch.")

        batch = self._session.get(MemberTaskBatch, package.batch_id)
        if batch is None:
            raise LookupError(f"Task batch '{package.batch_id}' was not found.")
        if batch.plan_id is None:
            raise ValueError("Task package batch is not linked to an issue plan.")

        next_quota = self._session.execute(
            select(MemberTaskDayQuota)
            .where(
                MemberTaskDayQuota.account_id == batch.account_id,
                MemberTaskDayQuota.user_id == batch.user_id,
                MemberTaskDayQuota.plan_id == batch.plan_id,
                MemberTaskDayQuota.day_no > batch.day_no,
                MemberTaskDayQuota.status == "pending",
                MemberTaskDayQuota.issued_batch_id.is_(None),
            )
            .order_by(MemberTaskDayQuota.day_no.asc(), MemberTaskDayQuota.created_at.asc())
            .with_for_update()
        ).scalar_one_or_none()
        if next_quota is None:
            raise ValueError("No next pending quota is available to pause.")

        next_quota.status = "cancelled"
        metadata = dict(next_quota.metadata_json or {})
        if reason:
            metadata["cancel_reason"] = reason
        if cancelled_by:
            metadata["cancelled_by"] = cancelled_by
        metadata["cancelled_at"] = utc_now().isoformat()
        metadata["cancel_source_package_id"] = package.id
        next_quota.metadata_json = metadata
        self._session.add(next_quota)
        self._session.commit()
        self._session.refresh(next_quota)
        return MemberTaskDayQuotaResponse.model_validate(next_quota, from_attributes=True)

    def _require_package(self, *, package_id: str, for_update: bool = False) -> TaskPackageInstance:
        if for_update:
            package = self._session.scalars(
                select(TaskPackageInstance)
                .where(TaskPackageInstance.id == package_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).first()
        else:
            package = self._session.scalars(
                select(TaskPackageInstance)
                .options(joinedload(TaskPackageInstance.items))
                .where(TaskPackageInstance.id == package_id)
            ).first()
        if package is None:
            raise LookupError(f"Task package '{package_id}' was not found.")
        return package

    @staticmethod
    def _quantize(amount: Decimal) -> Decimal:
        return Decimal(amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    def estimate_reward_amount(self, *, package: TaskPackageInstance, effective_amount: Decimal) -> Decimal:
        return self._quantize(Decimal(effective_amount) * Decimal(package.reward_ratio_snapshot))

    def _require_product_pool(self, *, package: TaskPackageInstance) -> TaskProductPool:
        pool_id = next((item.product_pool_id for item in package.items if item.product_pool_id), None)
        if pool_id is None:
            raise ValueError("Task package does not have a bound product pool.")
        pool = self._session.get(TaskProductPool, pool_id)
        if pool is None:
            raise LookupError(f"Task product pool '{pool_id}' was not found.")
        return pool

    def _load_restricted_product_ids(
        self,
        *,
        package: TaskPackageInstance,
        pool: TaskProductPool,
    ) -> list[str]:
        if pool.allow_repeat_in_same_batch and pool.allow_repeat_in_same_package:
            return []
        if pool.allow_repeat_in_same_batch:
            return self._load_package_product_ids(package=package)
        return self._load_batch_product_ids(package=package)

    def _load_batch_product_ids(self, *, package: TaskPackageInstance) -> list[str]:
        if package.batch_id is None:
            return self._load_package_product_ids(package=package)
        return [
            product_id
            for product_id in self._session.scalars(
                select(TaskPackageInstanceItem.product_id).where(
                    TaskPackageInstanceItem.batch_id == package.batch_id,
                    TaskPackageInstanceItem.product_id.is_not(None),
                )
            ).all()
            if product_id is not None
        ]

    @staticmethod
    def _load_package_product_ids(*, package: TaskPackageInstance) -> list[str]:
        return [item.product_id for item in package.items if item.product_id is not None]

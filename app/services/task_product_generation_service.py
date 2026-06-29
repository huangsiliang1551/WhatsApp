from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    MemberTaskBatch,
    MemberTaskDayQuota,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskIssuePlan,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    TaskProductGenerationRun,
    TaskProductPool,
    TaskProductPoolItem,
    utc_now,
)


class TaskProductGenerationService:
    _MAX_GENERATION_ATTEMPTS = 5

    def __init__(self, session: Session) -> None:
        self._session = session

    def generate_for_quota(
        self,
        *,
        quota_id: str,
        generated_by: str | None = None,
    ) -> MemberTaskBatch:
        quota = self._require_quota(quota_id)
        plan = self._require_plan(quota.plan_id)
        existing_batch = self._load_existing_batch(quota=quota)
        if existing_batch is not None:
            self._ensure_quota_locked(quota=quota, generated_by=generated_by)
            return existing_batch

        pool = self._require_pool(quota=quota)
        package_amounts = [self._quantize(Decimal(value)) for value in quota.package_amounts_json]
        if len(package_amounts) != quota.package_count:
            raise ValueError("QUOTA_PACKAGE_AMOUNTS_INVALID")

        generation_plan = self._plan_generation(
            quota=quota,
            pool=pool,
            package_amounts=package_amounts,
        )
        batch = MemberTaskBatch(
            account_id=quota.account_id,
            site_id=quota.site_id,
            user_id=quota.user_id,
            quota_id=quota.id,
            plan_id=quota.plan_id,
            day_no=quota.day_no,
            package_count=quota.package_count,
            completed_package_count=0,
            current_package_index=1,
            planned_amount=self._quantize(sum(package_amounts, Decimal("0.00"))),
            system_generated_amount=generation_plan["actual_day_system_amount"],
            manual_added_amount=Decimal("0.00"),
            effective_day_amount=generation_plan["actual_day_system_amount"],
            reward_ratio_snapshot=Decimal(quota.reward_ratio),
            status="pending_claim",
            products_generated=False,
            issued_at=quota.created_at,
        )
        self._session.add(batch)
        self._session.flush()

        generated_items = 0
        first_visible_item_id: str | None = None
        selection_seed = str(generation_plan["selection_seed"])

        for package_index, package_plan in enumerate(generation_plan["packages"], start=1):
            planned_amount = package_amounts[package_index - 1]
            item_count = int(package_plan["item_count"])
            package_pool_items = list(package_plan["pool_items"])
            package_prices = list(package_plan["item_prices"])
            package_system_generated_amount = Decimal(package_plan["system_generated_amount"])

            template = TaskPackageTemplate(
                account_id=quota.account_id,
                name=f"batch-{batch.id}-package-{package_index}",
                title=f"Task Package {package_index}",
                description=f"Generated from quota {quota.id}",
                package_type=self._resolve_package_type(plan),
                reward_ratio=Decimal(quota.reward_ratio),
                completion_window_hours=24,
                status="active",
                metadata_json={
                    "source": "task_product_generation",
                    "quota_id": quota.id,
                    "batch_id": batch.id,
                    "package_index": package_index,
                },
            )
            self._session.add(template)
            self._session.flush()

            package = TaskPackageInstance(
                account_id=quota.account_id,
                template_id=template.id,
                user_id=quota.user_id,
                site_id=quota.site_id,
                batch_id=batch.id,
                quota_id=quota.id,
                batch_day_no=quota.day_no,
                batch_index=package_index,
                batch_total=quota.package_count,
                planned_amount=planned_amount,
                system_generated_amount=package_system_generated_amount,
                manual_added_amount=Decimal("0.00"),
                effective_amount=package_system_generated_amount,
                status="pending_claim",
                reward_ratio_snapshot=Decimal(quota.reward_ratio),
                current_item_index=1,
                required_item_count=item_count,
                completed_required_item_count=0,
                manual_added_item_count=0,
                claim_gate_snapshot=plan.claim_gate if plan is not None else "certified_member",
                completion_window_hours_snapshot=24,
                metadata_json={
                    "source": "task_product_generation",
                    "quota_id": quota.id,
                    "batch_id": batch.id,
                },
            )
            self._session.add(package)
            self._session.flush()
            package_first_item_id: str | None = None

            for item_index, (pool_item, item_price) in enumerate(zip(package_pool_items, package_prices, strict=True), start=1):
                template_item = TaskPackageTemplateItem(
                    account_id=quota.account_id,
                    template_id=template.id,
                    sort_order=item_index,
                    product_name=pool_item.product_name,
                    image_url=pool_item.image_url,
                    price=item_price,
                    currency=pool_item.currency,
                    metadata_json={
                        "product_id": pool_item.product_id,
                        "pool_item_id": pool_item.id,
                        "product_description": self._resolve_description(pool_item),
                    },
                )
                self._session.add(template_item)
                self._session.flush()

                is_first_visible = package_index == 1 and item_index == 1
                package_item = TaskPackageInstanceItem(
                    account_id=quota.account_id,
                    batch_id=batch.id,
                    quota_id=quota.id,
                    package_instance_id=package.id,
                    template_item_id=template_item.id,
                    item_origin="system_generated",
                    is_required=True,
                    product_pool_id=pool.id,
                    pool_item_id=pool_item.id,
                    product_id=pool_item.product_id,
                    product_name_snapshot=pool_item.product_name,
                    product_image_url_snapshot=pool_item.image_url,
                    product_description_snapshot=self._resolve_description(pool_item),
                    price_snapshot=item_price,
                    sort_order=item_index,
                    product_name=pool_item.product_name,
                    image_url=pool_item.image_url,
                    price=item_price,
                    currency=pool_item.currency,
                    status="available" if is_first_visible else "pending",
                    visible_to_user=is_first_visible,
                    selection_seed=selection_seed,
                    selection_algorithm="weighted_random_unique_v1",
                    metadata_json={
                        "reference_price": self._format_optional_decimal(self._resolve_reference_price(pool_item)),
                        "pool_price_mode": pool.price_mode,
                    },
                )
                self._session.add(package_item)
                self._session.flush()

                package_first_item_id = package_first_item_id or package_item.id
                first_visible_item_id = first_visible_item_id or package_item.id
                generated_items += 1

            package.visible_item_id = package_first_item_id
            self._session.add(package)

        run = TaskProductGenerationRun(
            account_id=quota.account_id,
            site_id=quota.site_id,
            user_id=quota.user_id,
            quota_id=quota.id,
            batch_id=batch.id,
            product_pool_id=pool.id,
            selection_seed=selection_seed,
            selection_algorithm="weighted_random_unique_v1",
            target_day_amount=batch.planned_amount,
            actual_day_system_amount=generation_plan["actual_day_system_amount"],
            tolerance_amount=quota.tolerance_amount,
            generated_package_count=quota.package_count,
            generated_item_count=generated_items,
            status="success",
            idempotency_key=f"quota:{quota.id}:generation",
            metadata_json={
                "generated_by": generated_by,
                "first_visible_item_id": first_visible_item_id,
            },
        )
        self._session.add(run)
        self._session.flush()

        batch.products_generated = True
        batch.product_generation_run_id = run.id
        self._session.add(batch)

        quota.generated_by = generated_by
        quota.generated_at = run.created_at
        quota.issued_batch_id = batch.id
        quota.status = "locked"
        quota.locked_at = run.created_at or utc_now()
        self._session.add(quota)

        self._session.commit()
        self._session.refresh(batch)
        return batch

    def _ensure_quota_locked(
        self,
        *,
        quota: MemberTaskDayQuota,
        generated_by: str | None = None,
    ) -> None:
        if quota.status == "locked" and quota.locked_at is not None:
            return

        locked_changed = False
        if quota.generated_at is None:
            quota.generated_at = utc_now()
            locked_changed = True
        if quota.generated_by is None and generated_by is not None:
            quota.generated_by = generated_by
            locked_changed = True
        if quota.status != "locked":
            quota.status = "locked"
            locked_changed = True
        if quota.locked_at is None:
            quota.locked_at = quota.generated_at
            locked_changed = True
        if quota.issued_batch_id is None:
            batch = self._session.execute(
                select(MemberTaskBatch.id)
                .where(
                    MemberTaskBatch.account_id == quota.account_id,
                    MemberTaskBatch.quota_id == quota.id,
                )
                .order_by(MemberTaskBatch.created_at.desc(), MemberTaskBatch.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if batch is not None:
                quota.issued_batch_id = batch
                locked_changed = True
        if locked_changed:
            self._session.add(quota)
            self._session.commit()

    def _require_quota(self, quota_id: str) -> MemberTaskDayQuota:
        quota = self._session.get(MemberTaskDayQuota, quota_id)
        if quota is None:
            raise LookupError(f"Task quota '{quota_id}' was not found.")
        return quota

    def _require_plan(self, plan_id: str | None) -> TaskIssuePlan | None:
        if not plan_id:
            return None
        plan = self._session.get(TaskIssuePlan, plan_id)
        if plan is None:
            raise LookupError(f"Task issue plan '{plan_id}' was not found.")
        return plan

    def _load_existing_batch(self, *, quota: MemberTaskDayQuota) -> MemberTaskBatch | None:
        if quota.issued_batch_id:
            batch = self._session.get(MemberTaskBatch, quota.issued_batch_id)
            if batch is not None:
                if batch.products_generated:
                    return batch
                if self._is_empty_batch(batch_id=batch.id):
                    return None
                return batch
        batch = self._session.execute(
            select(MemberTaskBatch)
            .where(
                MemberTaskBatch.quota_id == quota.id,
                MemberTaskBatch.account_id == quota.account_id,
            )
            .order_by(MemberTaskBatch.created_at.desc(), MemberTaskBatch.id.desc())
        ).scalars().first()
        if batch is None:
            return None
        if batch.products_generated:
            return batch
        if self._is_empty_batch(batch_id=batch.id):
            return None
        return batch

    def _is_empty_batch(self, *, batch_id: str) -> bool:
        package_count = self._session.scalar(
            select(TaskPackageInstance.id)
            .where(TaskPackageInstance.batch_id == batch_id)
            .limit(1)
        )
        return package_count is None

    def _require_pool(self, *, quota: MemberTaskDayQuota) -> TaskProductPool:
        pool = self._session.get(TaskProductPool, quota.product_pool_id)
        if pool is None:
            raise LookupError(f"Task product pool '{quota.product_pool_id}' was not found.")
        if pool.account_id != quota.account_id:
            raise ValueError("TASK_PRODUCT_POOL_ACCOUNT_SCOPE_MISMATCH")
        return pool

    def _load_pool_items(self, *, pool_id: str) -> list[TaskProductPoolItem]:
        return self._session.execute(
            select(TaskProductPoolItem)
            .where(
                TaskProductPoolItem.pool_id == pool_id,
                TaskProductPoolItem.status == "active",
            )
            .order_by(TaskProductPoolItem.sort_order.asc(), TaskProductPoolItem.id.asc())
        ).scalars().all()

    def _plan_generation(
        self,
        *,
        quota: MemberTaskDayQuota,
        pool: TaskProductPool,
        package_amounts: list[Decimal],
    ) -> dict[str, object]:
        available_items = self._load_pool_items(pool_id=pool.id)
        last_error: ValueError | None = None

        for attempt in range(1, self._MAX_GENERATION_ATTEMPTS + 1):
            selection_seed = self._build_selection_seed(quota_id=quota.id, attempt=attempt)
            product_counts = self._resolve_product_counts(
                quota=quota,
                package_count=quota.package_count,
                selection_seed=selection_seed,
            )
            selected_items = self._select_pool_items(
                pool=pool,
                available_items=available_items,
                product_counts=product_counts,
                selection_seed=selection_seed,
            )

            selected_offset = 0
            packages: list[dict[str, object]] = []
            actual_day_system_amount = Decimal("0.00")

            for package_index, planned_amount in enumerate(package_amounts, start=1):
                item_count = product_counts[package_index - 1]
                package_pool_items = selected_items[selected_offset:selected_offset + item_count]
                selected_offset += item_count
                item_prices = self._resolve_package_snapshot_prices(
                    pool=pool,
                    package_pool_items=package_pool_items,
                    planned_amount=planned_amount,
                )
                package_system_generated_amount = self._quantize(sum(item_prices, Decimal("0.00")))
                actual_day_system_amount = self._quantize(actual_day_system_amount + package_system_generated_amount)
                packages.append(
                    {
                        "item_count": item_count,
                        "pool_items": package_pool_items,
                        "item_prices": item_prices,
                        "system_generated_amount": package_system_generated_amount,
                    }
                )

            if self._within_tolerance(
                actual_day_system_amount=actual_day_system_amount,
                target_day_amount=Decimal(quota.day_total_amount),
                tolerance_amount=Decimal(quota.tolerance_amount),
            ):
                return {
                    "selection_seed": selection_seed,
                    "actual_day_system_amount": actual_day_system_amount,
                    "packages": packages,
                }

            last_error = ValueError("TASK_PRODUCT_GENERATION_OUTSIDE_TOLERANCE")

        raise last_error or ValueError("TASK_PRODUCT_GENERATION_OUTSIDE_TOLERANCE")

    def _select_pool_items(
        self,
        *,
        pool: TaskProductPool,
        available_items: list[TaskProductPoolItem],
        product_counts: list[int],
        selection_seed: str,
    ) -> list[TaskProductPoolItem]:
        total_required = sum(product_counts)
        if not pool.allow_repeat_in_same_batch and len(available_items) < total_required:
            raise ValueError("PRODUCT_POOL_NOT_ENOUGH_UNIQUE_ITEMS")
        if not available_items:
            raise ValueError("PRODUCT_POOL_EMPTY")

        selected: list[TaskProductPoolItem] = []
        available_by_id = list(available_items)
        global_used: set[str] = set()
        rng = random.Random(self._seed_to_int(selection_seed))

        for package_count in product_counts:
            package_used: set[str] = set()
            for _ in range(package_count):
                candidate = self._pick_next_item(
                    pool=pool,
                    available_items=available_by_id,
                    global_used=global_used,
                    package_used=package_used,
                    rng=rng,
                )
                selected.append(candidate)
                package_used.add(candidate.id)
                global_used.add(candidate.id)
        return selected

    @staticmethod
    def _pick_next_item(
        *,
        pool: TaskProductPool,
        available_items: list[TaskProductPoolItem],
        global_used: set[str],
        package_used: set[str],
        rng: random.Random,
    ) -> TaskProductPoolItem:
        candidates = [
            item
            for item in available_items
            if (pool.allow_repeat_in_same_batch or item.id not in global_used)
            and (pool.allow_repeat_in_same_package or item.id not in package_used)
        ]
        if candidates:
            return TaskProductGenerationService._weighted_choice(candidates=candidates, rng=rng)
        raise ValueError("PRODUCT_POOL_NOT_ENOUGH_UNIQUE_ITEMS")

    @staticmethod
    def _resolve_product_counts(
        *,
        quota: MemberTaskDayQuota,
        package_count: int,
        selection_seed: str,
    ) -> list[int]:
        if quota.product_count_mode == "fixed":
            resolved = quota.product_count_fixed or 1
            return [resolved] * package_count
        if quota.product_count_mode == "range":
            minimum = quota.product_count_min or quota.product_count_max or 1
            maximum = quota.product_count_max or minimum
            if minimum > maximum:
                raise ValueError("TASK_PRODUCT_COUNT_RANGE_INVALID")
            rng = random.Random(TaskProductGenerationService._seed_to_int(selection_seed))
            return [rng.randint(minimum, maximum) for _ in range(package_count)]
        raise ValueError(f"Unsupported product_count_mode '{quota.product_count_mode}'.")

    def _resolve_package_snapshot_prices(
        self,
        *,
        pool: TaskProductPool,
        package_pool_items: list[TaskProductPoolItem],
        planned_amount: Decimal,
    ) -> list[Decimal]:
        if pool.price_mode == "product_reference_price":
            return [self._resolve_product_reference_snapshot_price(item) for item in package_pool_items]
        return self._split_amount(planned_amount=planned_amount, item_count=len(package_pool_items))

    def _resolve_product_reference_snapshot_price(self, item: TaskProductPoolItem) -> Decimal:
        reference_price = self._resolve_reference_price(item)
        candidate = reference_price if reference_price is not None else Decimal(item.price or Decimal("0.00"))
        candidate = self._quantize(candidate)
        if candidate <= Decimal("0.00"):
            raise ValueError("TASK_PRODUCT_REFERENCE_PRICE_MISSING")
        return candidate

    @staticmethod
    def _split_amount(*, planned_amount: Decimal, item_count: int) -> list[Decimal]:
        if item_count <= 0:
            raise ValueError("TASK_PACKAGE_ITEM_COUNT_INVALID")
        base = (planned_amount / item_count).quantize(Decimal("0.01"))
        amounts = [base] * item_count
        drift = planned_amount - sum(amounts, Decimal("0.00"))
        amounts[-1] = (amounts[-1] + drift).quantize(Decimal("0.01"))
        return amounts

    def _within_tolerance(
        self,
        *,
        actual_day_system_amount: Decimal,
        target_day_amount: Decimal,
        tolerance_amount: Decimal,
    ) -> bool:
        lower_bound = self._quantize(target_day_amount - tolerance_amount)
        upper_bound = self._quantize(target_day_amount + tolerance_amount)
        actual = self._quantize(actual_day_system_amount)
        return lower_bound <= actual <= upper_bound

    @staticmethod
    def _resolve_description(item: TaskProductPoolItem) -> str | None:
        if item.product_description:
            return item.product_description
        metadata = item.metadata_json or {}
        value = metadata.get("product_description")
        return str(value) if value else None

    @staticmethod
    def _resolve_reference_price(item: TaskProductPoolItem) -> Decimal | None:
        if item.reference_price is not None:
            return Decimal(item.reference_price)
        metadata = item.metadata_json or {}
        value = metadata.get("reference_price")
        if value in (None, ""):
            return None
        return Decimal(str(value))

    @staticmethod
    def _format_optional_decimal(value: Decimal | None) -> str | None:
        if value is None:
            return None
        return f"{value.quantize(Decimal('0.01')):.2f}"

    @staticmethod
    def _build_selection_seed(*, quota_id: str, attempt: int) -> str:
        return sha256(f"{quota_id}:{attempt}".encode("utf-8")).hexdigest()

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.01"))

    @staticmethod
    def _resolve_package_type(plan: TaskIssuePlan | None) -> str:
        if plan is not None and plan.plan_type == "newbie":
            return "rookie"
        return "official"

    @staticmethod
    def _seed_to_int(selection_seed: str) -> int:
        return int(sha256(selection_seed.encode("utf-8")).hexdigest(), 16)

    @staticmethod
    def _weighted_choice(
        *,
        candidates: list[TaskProductPoolItem],
        rng: random.Random,
    ) -> TaskProductPoolItem:
        weights = [max(int(item.weight or 0), 1) for item in candidates]
        total_weight = sum(weights)
        cursor = rng.uniform(0, total_weight)
        cumulative = 0.0
        for item, weight in zip(candidates, weights, strict=True):
            cumulative += float(weight)
            if cursor <= cumulative:
                return item
        return candidates[-1]

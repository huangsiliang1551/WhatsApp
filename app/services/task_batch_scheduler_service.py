from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MemberTaskDayQuota, TaskProductGenerationRun
from app.services.task_product_generation_service import TaskProductGenerationService


class TaskBatchSchedulerService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_run(self, run_id: str) -> TaskProductGenerationRun:
        return self._require_run(run_id)

    def generate_batch_for_quota(
        self,
        *,
        quota_id: str,
        requested_by: str | None = None,
    ) -> TaskProductGenerationRun:
        existing_success = self._load_latest_success_run(quota_id=quota_id)
        if existing_success is not None:
            return existing_success

        try:
            batch = TaskProductGenerationService(self._session).generate_for_quota(
                quota_id=quota_id,
                generated_by=requested_by,
            )
        except Exception as exc:
            self._session.rollback()
            self._record_failed_run(
                quota_id=quota_id,
                requested_by=requested_by,
                failure_reason=str(exc),
            )
            raise

        if batch.product_generation_run_id is None:
            raise RuntimeError(f"Generated batch '{batch.id}' is missing product_generation_run_id.")

        run = self._session.get(TaskProductGenerationRun, batch.product_generation_run_id)
        if run is None:
            raise LookupError(f"Task product generation run '{batch.product_generation_run_id}' was not found.")
        return run

    def retry_generation_run(
        self,
        *,
        run_id: str,
        requested_by: str | None = None,
    ) -> TaskProductGenerationRun:
        run = self._require_run(run_id)
        if run.status == "success":
            return run
        return self.generate_batch_for_quota(
            quota_id=run.quota_id,
            requested_by=requested_by,
        )

    def _load_latest_success_run(self, *, quota_id: str) -> TaskProductGenerationRun | None:
        return self._session.execute(
            select(TaskProductGenerationRun)
            .where(
                TaskProductGenerationRun.quota_id == quota_id,
                TaskProductGenerationRun.status == "success",
            )
            .order_by(TaskProductGenerationRun.created_at.desc(), TaskProductGenerationRun.id.desc())
        ).scalars().first()

    def _record_failed_run(
        self,
        *,
        quota_id: str,
        requested_by: str | None,
        failure_reason: str,
    ) -> TaskProductGenerationRun:
        quota = self._require_quota(quota_id)
        attempt = (
            self._session.scalar(
                select(func.count(TaskProductGenerationRun.id)).where(
                    TaskProductGenerationRun.quota_id == quota.id,
                )
            )
            or 0
        ) + 1
        run = TaskProductGenerationRun(
            account_id=quota.account_id,
            site_id=quota.site_id,
            user_id=quota.user_id,
            quota_id=quota.id,
            batch_id=quota.issued_batch_id,
            product_pool_id=quota.product_pool_id,
            selection_seed=f"failed-attempt-{attempt}",
            selection_algorithm="weighted_random_unique_v1",
            target_day_amount=Decimal(quota.day_total_amount),
            actual_day_system_amount=Decimal("0.00"),
            tolerance_amount=Decimal(quota.tolerance_amount),
            generated_package_count=0,
            generated_item_count=0,
            status="failed",
            failure_reason=failure_reason,
            idempotency_key=f"quota:{quota.id}:generation:failed:{attempt}",
            metadata_json={"generated_by": requested_by},
        )
        self._session.add(run)
        self._session.commit()
        return run

    def _require_quota(self, quota_id: str) -> MemberTaskDayQuota:
        quota = self._session.get(MemberTaskDayQuota, quota_id)
        if quota is None:
            raise LookupError(f"Task quota '{quota_id}' was not found.")
        return quota

    def _require_run(self, run_id: str) -> TaskProductGenerationRun:
        run = self._session.get(TaskProductGenerationRun, run_id)
        if run is None:
            raise LookupError(f"Task product generation run '{run_id}' was not found.")
        return run

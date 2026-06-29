from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    MemberProfile,
    MemberTaskBatch,
    MemberTaskDayQuota,
    MemberVerificationRequest,
    TaskIssuePlan,
    TaskIssuePlanDayRule,
    TaskProductPool,
    TaskSystemConfig,
    UserTag,
    UserTagAssignment,
    WalletLedgerEntry,
    utc_now,
)
from app.schemas.member_task_quota import (
    MemberTaskQuotaBatchCreateRequest,
    MemberTaskQuotaBatchPreviewResponse,
    MemberTaskQuotaCancelRequest,
    MemberTaskDayQuotaResponse,
    MemberTaskQuotaCreateRequest,
    MemberTaskQuotaPlanIssueRequest,
    MemberTaskQuotaUpdateRequest,
)
from app.services.task_amount_allocation_service import TaskAmountAllocationService


class MemberTaskQuotaService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_quota(self, payload: MemberTaskQuotaCreateRequest) -> MemberTaskDayQuotaResponse:
        quota = self._create_quota_entity(payload)
        self._session.add(quota)
        self._session.commit()
        self._session.refresh(quota)
        return self._serialize(quota)

    def batch_create_quotas(self, payload: MemberTaskQuotaBatchCreateRequest) -> list[MemberTaskDayQuotaResponse]:
        items = self._resolve_batch_items(payload)
        quotas = [self._create_quota_entity(item) for item in items]
        self._session.add_all(quotas)
        self._session.commit()
        for quota in quotas:
            self._session.refresh(quota)
        return [self._serialize(quota) for quota in quotas]

    def preview_batch_create_quotas(
        self,
        payload: MemberTaskQuotaBatchCreateRequest,
    ) -> MemberTaskQuotaBatchPreviewResponse:
        items = self._resolve_batch_items(payload)
        if len(items) == 0:
            raise ValueError("At least one batch quota item is required.")

        first_item = items[0]
        package_amounts = TaskAmountAllocationService.allocate(
            mode=first_item.amount_allocation_mode,
            package_count=first_item.package_count,
            day_total_amount=first_item.day_total_amount,
            manual_amounts=first_item.package_amounts,
        )
        total_batch_amount = sum((item.day_total_amount for item in items), Decimal("0.00"))
        return MemberTaskQuotaBatchPreviewResponse(
            user_count=len(items),
            total_quota_count=len(items),
            package_amounts=[self._format_amount(amount) for amount in package_amounts],
            computed_total_amount=sum(package_amounts, Decimal("0.00")),
            total_batch_amount=self._quantize(total_batch_amount),
            reward_ratio=first_item.reward_ratio,
            product_pool_id=first_item.product_pool_id,
        )

    def _resolve_batch_items(self, payload: MemberTaskQuotaBatchCreateRequest) -> list[MemberTaskQuotaCreateRequest]:
        if payload.items:
            return payload.items
        return self._build_batch_items_from_selector(payload)

    def _build_batch_items_from_selector(
        self,
        payload: MemberTaskQuotaBatchCreateRequest,
    ) -> list[MemberTaskQuotaCreateRequest]:
        if not payload.account_id:
            raise ValueError("Batch quota selection requires account_id.")
        if payload.day_no is None:
            raise ValueError("Batch quota selection requires day_no.")
        if payload.package_count is None:
            raise ValueError("Batch quota selection requires package_count.")
        if payload.day_total_amount is None:
            raise ValueError("Batch quota selection requires day_total_amount.")
        if not payload.amount_allocation_mode:
            raise ValueError("Batch quota selection requires amount_allocation_mode.")
        if not payload.product_pool_id:
            raise ValueError("Batch quota selection requires product_pool_id.")
        if not any(
            [
                payload.owner_staff_user_id,
                payload.certified_status,
                payload.min_total_real_recharge is not None,
                payload.max_total_real_recharge is not None,
                payload.tag_ids,
                payload.tag_keys,
                payload.user_ids,
            ]
        ):
            raise ValueError("Batch quota selection requires at least one selector.")

        users = self._select_batch_users(payload)
        return [
            MemberTaskQuotaCreateRequest(
                account_id=payload.account_id,
                site_id=payload.site_id,
                user_id=user.id,
                plan_id=payload.plan_id,
                day_no=payload.day_no,
                package_count=payload.package_count,
                day_total_amount=payload.day_total_amount,
                tolerance_amount=payload.tolerance_amount,
                amount_allocation_mode=payload.amount_allocation_mode,
                package_amounts=payload.package_amounts,
                product_pool_id=payload.product_pool_id,
                product_count_mode=payload.product_count_mode,
                product_count_fixed=payload.product_count_fixed,
                product_count_min=payload.product_count_min,
                product_count_max=payload.product_count_max,
                reward_ratio=payload.reward_ratio,
                created_by=payload.created_by,
                metadata_json=payload.metadata_json,
            )
            for user in users
        ]

    def _select_batch_users(self, payload: MemberTaskQuotaBatchCreateRequest) -> list[AppUser]:
        assert payload.account_id is not None
        query = select(AppUser).where(AppUser.account_id == payload.account_id)
        if payload.site_id is not None:
            query = query.where(AppUser.registration_site_id == payload.site_id)
        if payload.user_ids:
            query = query.where(AppUser.id.in_(payload.user_ids))
        users = self._session.execute(query.order_by(AppUser.created_at.asc(), AppUser.id.asc())).scalars().all()
        if not users:
            return []

        selected = users

        if payload.owner_staff_user_id is not None:
            owner_user_ids = set(
                self._session.execute(
                    select(MemberProfile.user_id).where(
                        MemberProfile.account_id == payload.account_id,
                        MemberProfile.current_owner_staff_user_id == payload.owner_staff_user_id,
                    )
                ).scalars().all()
            )
            selected = [user for user in selected if user.id in owner_user_ids]

        if payload.tag_ids or payload.tag_keys:
            tag_ids = list(payload.tag_ids)
            if payload.tag_keys:
                tag_ids.extend(
                    self._session.execute(
                        select(UserTag.id).where(UserTag.tag_key.in_(payload.tag_keys))
                    ).scalars().all()
                )
            tagged_user_ids = set(
                self._session.execute(
                    select(UserTagAssignment.user_id).where(UserTagAssignment.tag_id.in_(tag_ids))
                ).scalars().all()
            )
            selected = [user for user in selected if user.id in tagged_user_ids]

        recharge_totals = self._load_real_recharge_totals(payload.account_id, [user.id for user in selected])
        if payload.min_total_real_recharge is not None:
            selected = [
                user for user in selected
                if recharge_totals.get(user.id, Decimal("0.00")) >= payload.min_total_real_recharge
            ]
        if payload.max_total_real_recharge is not None:
            selected = [
                user for user in selected
                if recharge_totals.get(user.id, Decimal("0.00")) <= payload.max_total_real_recharge
            ]

        if payload.certified_status is not None:
            selected = [
                user for user in selected
                if self._is_user_certified(
                    account_id=payload.account_id,
                    site_id=payload.site_id,
                    user_id=user.id,
                    recharge_total=recharge_totals.get(user.id, Decimal("0.00")),
                ) is (payload.certified_status == "certified")
            ]
        return selected

    def _load_real_recharge_totals(self, account_id: str, user_ids: list[str]) -> dict[str, Decimal]:
        if not user_ids:
            return {}
        rows = self._session.execute(
            select(
                WalletLedgerEntry.user_id,
                func.coalesce(func.sum(WalletLedgerEntry.amount), 0),
            )
            .where(
                WalletLedgerEntry.account_id == account_id,
                WalletLedgerEntry.user_id.in_(user_ids),
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.status == "paid",
                WalletLedgerEntry.is_real_recharge.is_(True),
            )
            .group_by(WalletLedgerEntry.user_id)
        ).all()
        return {user_id: self._quantize(Decimal(total or 0)) for user_id, total in rows}

    def _is_user_certified(
        self,
        *,
        account_id: str,
        site_id: str | None,
        user_id: str,
        recharge_total: Decimal,
    ) -> bool:
        config = self._resolve_task_system_config(account_id=account_id, site_id=site_id)
        if not config.certified_member_enabled:
            return True

        member_profile = self._session.execute(
            select(MemberProfile).where(
                MemberProfile.account_id == account_id,
                MemberProfile.user_id == user_id,
            )
        ).scalar_one_or_none()
        if member_profile is not None:
            latest_request = self._session.execute(
                select(MemberVerificationRequest)
                .where(
                    MemberVerificationRequest.account_id == account_id,
                    MemberVerificationRequest.member_profile_id == member_profile.id,
                )
                .order_by(MemberVerificationRequest.created_at.desc(), MemberVerificationRequest.id.desc())
            ).scalars().first()
            if latest_request is not None and latest_request.status == "approved":
                return True

        return recharge_total >= Decimal(config.certified_recharge_threshold)

    def get_quota(self, quota_id: str) -> MemberTaskDayQuotaResponse:
        return self._serialize(self._require_quota(quota_id))

    def update_quota(self, quota_id: str, payload: MemberTaskQuotaUpdateRequest) -> MemberTaskDayQuotaResponse:
        quota = self._require_quota(quota_id)
        self._ensure_mutable(quota)

        package_count = payload.package_count or quota.package_count
        day_total_amount = self._quantize(payload.day_total_amount or quota.day_total_amount)
        amount_allocation_mode = payload.amount_allocation_mode or quota.amount_allocation_mode
        manual_amounts = payload.package_amounts
        if manual_amounts is None and amount_allocation_mode == quota.amount_allocation_mode:
            manual_amounts = [Decimal(value) for value in (quota.package_amounts_json or [])]

        product_pool_id = payload.product_pool_id or quota.product_pool_id
        self._require_product_pool(account_id=quota.account_id, pool_id=product_pool_id)

        package_amounts = TaskAmountAllocationService.allocate(
            mode=amount_allocation_mode,
            package_count=package_count,
            day_total_amount=day_total_amount,
            manual_amounts=manual_amounts or [],
        )

        quota.site_id = payload.site_id if payload.site_id is not None else quota.site_id
        quota.package_count = package_count
        quota.day_total_amount = day_total_amount
        quota.tolerance_amount = self._quantize(payload.tolerance_amount or quota.tolerance_amount)
        quota.amount_allocation_mode = amount_allocation_mode
        quota.package_amounts_json = [self._format_amount(amount) for amount in package_amounts]
        quota.product_pool_id = product_pool_id
        quota.product_count_mode = payload.product_count_mode or quota.product_count_mode
        quota.product_count_fixed = payload.product_count_fixed if payload.product_count_fixed is not None else quota.product_count_fixed
        quota.product_count_min = payload.product_count_min if payload.product_count_min is not None else quota.product_count_min
        quota.product_count_max = payload.product_count_max if payload.product_count_max is not None else quota.product_count_max
        quota.reward_ratio = payload.reward_ratio if payload.reward_ratio is not None else quota.reward_ratio
        if payload.metadata_json is not None:
            quota.metadata_json = payload.metadata_json

        self._session.add(quota)
        self._session.commit()
        self._session.refresh(quota)
        return self._serialize(quota)

    def cancel_quota(
        self,
        quota_id: str,
        payload: MemberTaskQuotaCancelRequest,
        *,
        cancelled_by: str | None = None,
    ) -> MemberTaskDayQuotaResponse:
        quota = self._require_quota(quota_id)
        self._ensure_mutable(quota)
        quota.status = "cancelled"
        metadata = dict(quota.metadata_json or {})
        if payload.reason:
            metadata["cancel_reason"] = payload.reason
        if cancelled_by:
            metadata["cancelled_by"] = cancelled_by
        metadata["cancelled_at"] = utc_now().isoformat()
        quota.metadata_json = metadata
        self._session.add(quota)
        self._session.commit()
        self._session.refresh(quota)
        return self._serialize(quota)

    def _create_quota_entity(self, payload: MemberTaskQuotaCreateRequest) -> MemberTaskDayQuota:
        user = self._require_user(payload.user_id)
        if user.account_id != payload.account_id:
            raise ValueError("Quota account_id does not match the user account scope.")
        self._require_product_pool(account_id=payload.account_id, pool_id=payload.product_pool_id)
        self._ensure_unique_scope(
            account_id=payload.account_id,
            user_id=payload.user_id,
            plan_id=payload.plan_id,
            day_no=payload.day_no,
        )

        package_amounts = TaskAmountAllocationService.allocate(
            mode=payload.amount_allocation_mode,
            package_count=payload.package_count,
            day_total_amount=payload.day_total_amount,
            manual_amounts=payload.package_amounts,
        )
        quota = MemberTaskDayQuota(
            account_id=payload.account_id,
            site_id=payload.site_id,
            user_id=payload.user_id,
            plan_id=payload.plan_id,
            day_no=payload.day_no,
            package_count=payload.package_count,
            day_total_amount=self._quantize(payload.day_total_amount),
            tolerance_amount=self._quantize(payload.tolerance_amount),
            amount_allocation_mode=payload.amount_allocation_mode,
            package_amounts_json=[self._format_amount(amount) for amount in package_amounts],
            product_pool_id=payload.product_pool_id,
            product_count_mode=payload.product_count_mode,
            product_count_fixed=payload.product_count_fixed,
            product_count_min=payload.product_count_min,
            product_count_max=payload.product_count_max,
            reward_ratio=payload.reward_ratio,
            status="pending",
            created_by=payload.created_by,
            metadata_json=payload.metadata_json,
        )
        return quota

    def list_quotas(
        self,
        *,
        account_id: str | None = None,
        user_id: str | None = None,
        plan_id: str | None = None,
        day_no: int | None = None,
    ) -> list[MemberTaskDayQuotaResponse]:
        query = select(MemberTaskDayQuota).order_by(MemberTaskDayQuota.created_at.desc(), MemberTaskDayQuota.id.desc())
        if account_id is not None:
            query = query.where(MemberTaskDayQuota.account_id == account_id)
        if user_id is not None:
            query = query.where(MemberTaskDayQuota.user_id == user_id)
        if plan_id is not None:
            query = query.where(MemberTaskDayQuota.plan_id == plan_id)
        if day_no is not None:
            query = query.where(MemberTaskDayQuota.day_no == day_no)
        rows = self._session.execute(query).scalars().all()
        return [self._serialize(row) for row in rows]

    def issue_quota_from_plan(self, payload: MemberTaskQuotaPlanIssueRequest) -> MemberTaskDayQuotaResponse:
        plan = self._require_plan(payload.plan_id)
        user = self._require_user(payload.user_id)
        if user.account_id != plan.account_id:
            raise ValueError("Plan account_id does not match the user account scope.")
        self._enforce_plan_issue_constraints(
            plan=plan,
            user_id=user.id,
            day_no=payload.day_no,
        )
        self._ensure_unique_scope(
            account_id=plan.account_id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=payload.day_no,
        )

        resolved_rule = self._resolve_day_rule(plan=plan, day_no=payload.day_no)
        self._enforce_issue_schedule(
            plan=plan,
            user=user,
            resolved_rule=resolved_rule,
            day_no=payload.day_no,
        )
        resolved_pool_id = resolved_rule.product_pool_id or plan.default_product_pool_id
        if not resolved_pool_id:
            raise ValueError("No product pool is configured for the quota issue plan.")
        self._require_product_pool(account_id=plan.account_id, pool_id=resolved_pool_id)

        create_payload = MemberTaskQuotaCreateRequest(
            account_id=plan.account_id,
            site_id=plan.site_id,
            user_id=user.id,
            plan_id=plan.id,
            day_no=payload.day_no,
            package_count=resolved_rule.package_count,
            day_total_amount=resolved_rule.day_total_amount,
            tolerance_amount=resolved_rule.tolerance_amount,
            amount_allocation_mode=resolved_rule.amount_allocation_mode,
            package_amounts=[Decimal(value) for value in resolved_rule.package_amounts_json],
            product_pool_id=resolved_pool_id,
            product_count_mode=resolved_rule.product_count_mode,
            product_count_fixed=resolved_rule.product_count_fixed,
            product_count_min=resolved_rule.product_count_min,
            product_count_max=resolved_rule.product_count_max,
            reward_ratio=resolved_rule.reward_ratio,
            created_by=payload.created_by,
            metadata_json=payload.metadata_json,
        )
        return self.create_quota(create_payload)

    def _enforce_plan_issue_constraints(self, *, plan: TaskIssuePlan, user_id: str, day_no: int) -> None:
        previous_quotas = self._session.execute(
            select(MemberTaskDayQuota)
            .where(
                MemberTaskDayQuota.account_id == plan.account_id,
                MemberTaskDayQuota.user_id == user_id,
                MemberTaskDayQuota.plan_id == plan.id,
                MemberTaskDayQuota.day_no < day_no,
            )
            .order_by(MemberTaskDayQuota.day_no.desc(), MemberTaskDayQuota.created_at.desc(), MemberTaskDayQuota.id.desc())
        ).scalars().all()

        unfinished_batches: list[MemberTaskBatch] = []
        latest_previous_batch: MemberTaskBatch | None = None
        for quota in previous_quotas:
            if quota.issued_batch_id is None:
                continue
            batch = self._session.get(MemberTaskBatch, quota.issued_batch_id)
            if batch is None:
                continue
            if latest_previous_batch is None:
                latest_previous_batch = batch
            if batch.status != "completed":
                unfinished_batches.append(batch)

        if plan.require_previous_batch_completed and latest_previous_batch is not None and latest_previous_batch.status != "completed":
            raise ValueError("Previous batch must be completed before issuing the next quota.")

        if len(unfinished_batches) >= plan.max_unfinished_batches:
            raise ValueError("Maximum unfinished batch limit reached for this member task plan.")

    def _enforce_issue_schedule(
        self,
        *,
        plan: TaskIssuePlan,
        user: AppUser,
        resolved_rule: TaskIssuePlanDayRule,
        day_no: int,
    ) -> None:
        ready_at = self._resolve_issue_ready_at(
            plan=plan,
            user=user,
            resolved_rule=resolved_rule,
            day_no=day_no,
        )
        if ready_at is None:
            return
        if utc_now() < ready_at:
            raise ValueError(f"Task quota issue schedule window has not been reached. Ready at {ready_at.isoformat()}.")

    def _resolve_issue_ready_at(
        self,
        *,
        plan: TaskIssuePlan,
        user: AppUser,
        resolved_rule: TaskIssuePlanDayRule,
        day_no: int,
    ) -> datetime | None:
        anchor_at = self._resolve_issue_anchor_at(plan=plan, user=user)
        if anchor_at is None:
            return None
        if plan.issue_mode != "calendar_day":
            return anchor_at

        day_offset = max(day_no - 1, 0)
        base_ready_at = anchor_at + timedelta(days=day_offset)
        ready_at_candidates = [base_ready_at]

        if resolved_rule.issue_time_of_day:
            ready_at_candidates.append(
                datetime.combine(
                    anchor_at.date() + timedelta(days=day_offset),
                    self._parse_issue_time_of_day(resolved_rule.issue_time_of_day),
                )
            )

        if resolved_rule.elapsed_delay_hours is not None:
            ready_at_candidates.append(anchor_at + timedelta(hours=resolved_rule.elapsed_delay_hours))

        return max(ready_at_candidates)

    def _resolve_issue_anchor_at(self, *, plan: TaskIssuePlan, user: AppUser) -> datetime | None:
        if plan.issue_anchor != "certified_at":
            return user.created_at

        member_profile = self._session.execute(
            select(MemberProfile).where(
                MemberProfile.account_id == plan.account_id,
                MemberProfile.user_id == user.id,
            )
        ).scalar_one_or_none()
        if member_profile is not None:
            approved_request = self._session.execute(
                select(MemberVerificationRequest)
                .where(
                    MemberVerificationRequest.account_id == plan.account_id,
                    MemberVerificationRequest.member_profile_id == member_profile.id,
                    MemberVerificationRequest.status == "approved",
                )
                .order_by(MemberVerificationRequest.reviewed_at.desc(), MemberVerificationRequest.created_at.desc())
            ).scalars().first()
            if approved_request is not None:
                return approved_request.reviewed_at or approved_request.created_at

        config = self._resolve_task_system_config_for_plan(plan=plan)
        if not config.certified_member_enabled:
            return user.created_at

        threshold = Decimal(config.certified_recharge_threshold)
        if threshold <= Decimal("0.00"):
            return user.created_at

        running_total = Decimal("0.00")
        ledger_entries = self._session.execute(
            select(WalletLedgerEntry)
            .where(
                WalletLedgerEntry.account_id == plan.account_id,
                WalletLedgerEntry.user_id == user.id,
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.status == "paid",
                WalletLedgerEntry.is_real_recharge.is_(True),
            )
            .order_by(WalletLedgerEntry.created_at.asc(), WalletLedgerEntry.id.asc())
        ).scalars().all()
        for entry in ledger_entries:
            running_total += Decimal(entry.amount or 0)
            if running_total >= threshold:
                return entry.created_at
        return None

    def _resolve_task_system_config_for_plan(self, *, plan: TaskIssuePlan) -> TaskSystemConfig:
        return self._resolve_task_system_config(account_id=plan.account_id, site_id=plan.site_id)

    def _resolve_task_system_config(self, *, account_id: str, site_id: str | None) -> TaskSystemConfig:
        if site_id is not None:
            site_config = self._session.execute(
                select(TaskSystemConfig)
                .where(
                    TaskSystemConfig.account_id == account_id,
                    TaskSystemConfig.site_id == site_id,
                )
                .order_by(TaskSystemConfig.created_at.desc(), TaskSystemConfig.id.desc())
            ).scalars().first()
            if site_config is not None:
                return site_config

        account_config = self._session.execute(
            select(TaskSystemConfig)
            .where(
                TaskSystemConfig.account_id == account_id,
                TaskSystemConfig.site_id.is_(None),
            )
            .order_by(TaskSystemConfig.created_at.desc(), TaskSystemConfig.id.desc())
        ).scalars().first()
        if account_config is not None:
            return account_config
        return TaskSystemConfig(account_id=account_id, site_id=site_id)

    def _resolve_day_rule(self, *, plan: TaskIssuePlan, day_no: int) -> TaskIssuePlanDayRule:
        exact_rule = self._session.execute(
            select(TaskIssuePlanDayRule).where(
                TaskIssuePlanDayRule.plan_id == plan.id,
                TaskIssuePlanDayRule.day_no == day_no,
            )
        ).scalar_one_or_none()
        if exact_rule is not None:
            return exact_rule

        last_rule = self._session.execute(
            select(TaskIssuePlanDayRule)
            .where(TaskIssuePlanDayRule.plan_id == plan.id)
            .order_by(TaskIssuePlanDayRule.day_no.desc())
        ).scalars().first()
        if last_rule is None:
            raise LookupError(f"No day rule is configured for plan '{plan.id}'.")
        if plan.after_last_rule_mode == "stop":
            raise LookupError(f"No day rule is configured for plan '{plan.id}' day {day_no}.")
        if plan.after_last_rule_mode == "repeat_last":
            return self._clone_rule_for_day(plan=plan, source_rule=last_rule, day_no=day_no)
        if plan.after_last_rule_mode == "arithmetic_growth":
            delta_days = day_no - last_rule.day_no
            if delta_days <= 0:
                raise LookupError(f"No day rule is configured for plan '{plan.id}' day {day_no}.")
            growth_amount_step = plan.growth_amount_step or Decimal("0.00")
            return self._clone_rule_for_day(
                plan=plan,
                source_rule=last_rule,
                day_no=day_no,
                package_count=last_rule.package_count + (plan.growth_package_count_step * delta_days),
                day_total_amount=self._quantize(last_rule.day_total_amount + (growth_amount_step * delta_days)),
            )
        raise ValueError(f"Unsupported after_last_rule_mode '{plan.after_last_rule_mode}'.")

    def _clone_rule_for_day(
        self,
        *,
        plan: TaskIssuePlan,
        source_rule: TaskIssuePlanDayRule,
        day_no: int,
        package_count: int | None = None,
        day_total_amount: Decimal | None = None,
    ) -> TaskIssuePlanDayRule:
        resolved_package_count = package_count or source_rule.package_count
        resolved_total_amount = self._quantize(day_total_amount or source_rule.day_total_amount)
        allocation_mode = source_rule.amount_allocation_mode
        package_amounts_json = list(source_rule.package_amounts_json or [])
        if allocation_mode == "manual" and (
            resolved_package_count != source_rule.package_count
            or resolved_total_amount != self._quantize(source_rule.day_total_amount)
        ):
            allocation_mode = "average"
            package_amounts_json = []
        if allocation_mode != "manual":
            package_amounts_json = [
                self._format_amount(amount)
                for amount in TaskAmountAllocationService.allocate(
                    mode=allocation_mode,
                    package_count=resolved_package_count,
                    day_total_amount=resolved_total_amount,
                )
            ]
        return TaskIssuePlanDayRule(
            account_id=plan.account_id,
            site_id=plan.site_id,
            plan_id=plan.id,
            day_no=day_no,
            package_count=resolved_package_count,
            day_total_amount=resolved_total_amount,
            tolerance_amount=source_rule.tolerance_amount or plan.default_tolerance_amount,
            amount_allocation_mode=allocation_mode,
            package_amounts_json=package_amounts_json,
            product_pool_id=source_rule.product_pool_id or plan.default_product_pool_id,
            product_count_mode=source_rule.product_count_mode,
            product_count_fixed=source_rule.product_count_fixed,
            product_count_min=source_rule.product_count_min,
            product_count_max=source_rule.product_count_max,
            reward_ratio=source_rule.reward_ratio or plan.default_reward_ratio,
            issue_time_of_day=source_rule.issue_time_of_day,
            elapsed_delay_hours=source_rule.elapsed_delay_hours,
            status=source_rule.status,
            metadata_json=source_rule.metadata_json,
        )

    def _require_plan(self, plan_id: str) -> TaskIssuePlan:
        plan = self._session.get(TaskIssuePlan, plan_id)
        if plan is None:
            raise LookupError(f"Task issue plan '{plan_id}' was not found.")
        return plan

    def _require_user(self, user_id: str) -> AppUser:
        user = self._session.get(AppUser, user_id)
        if user is None:
            raise LookupError(f"User '{user_id}' was not found.")
        if user.is_anonymous:
            raise ValueError("Anonymous users cannot receive task quotas.")
        return user

    def _require_product_pool(self, *, account_id: str, pool_id: str) -> TaskProductPool:
        pool = self._session.get(TaskProductPool, pool_id)
        if pool is None:
            raise LookupError(f"Task product pool '{pool_id}' was not found.")
        if pool.account_id != account_id:
            raise ValueError("Task product pool account scope mismatch.")
        return pool

    @staticmethod
    def _ensure_mutable(quota: MemberTaskDayQuota) -> None:
        if quota.status == "cancelled":
            raise ValueError("Cancelled task quota cannot be modified.")
        if quota.issued_batch_id is not None or quota.status in {"locked", "generated", "active", "completed"}:
            raise ValueError("Issued task quota cannot be modified.")

    def _require_quota(self, quota_id: str) -> MemberTaskDayQuota:
        quota = self._session.get(MemberTaskDayQuota, quota_id)
        if quota is None:
            raise LookupError(f"Task quota '{quota_id}' was not found.")
        return quota

    def _ensure_unique_scope(self, *, account_id: str, user_id: str, plan_id: str | None, day_no: int) -> None:
        existing = self._session.execute(
            select(MemberTaskDayQuota.id).where(
                MemberTaskDayQuota.account_id == account_id,
                MemberTaskDayQuota.user_id == user_id,
                MemberTaskDayQuota.plan_id == plan_id,
                MemberTaskDayQuota.day_no == day_no,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError("Member task day quota already exists for this scope.")

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.01"))

    @staticmethod
    def _format_amount(value: Decimal) -> str:
        return f"{Decimal(value).quantize(Decimal('0.01')):.2f}"

    @staticmethod
    def _parse_issue_time_of_day(value: str) -> time:
        hour_text, minute_text = value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))

    @staticmethod
    def _serialize(quota: MemberTaskDayQuota) -> MemberTaskDayQuotaResponse:
        return MemberTaskDayQuotaResponse.model_validate(
            {
                "id": quota.id,
                "account_id": quota.account_id,
                "site_id": quota.site_id,
                "user_id": quota.user_id,
                "plan_id": quota.plan_id,
                "day_no": quota.day_no,
                "package_count": quota.package_count,
                "day_total_amount": quota.day_total_amount,
                "tolerance_amount": quota.tolerance_amount,
                "amount_allocation_mode": quota.amount_allocation_mode,
                "package_amounts_json": list(quota.package_amounts_json or []),
                "product_pool_id": quota.product_pool_id,
                "product_count_mode": quota.product_count_mode,
                "product_count_fixed": quota.product_count_fixed,
                "product_count_min": quota.product_count_min,
                "product_count_max": quota.product_count_max,
                "reward_ratio": quota.reward_ratio,
                "status": quota.status,
                "issued_batch_id": quota.issued_batch_id,
                "generated_at": quota.generated_at,
                "generated_by": quota.generated_by,
                "locked_at": quota.locked_at,
                "created_by": quota.created_by,
                "metadata_json": quota.metadata_json,
                "created_at": quota.created_at,
                "updated_at": quota.updated_at,
            }
        )

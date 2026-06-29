from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Site, TaskIssuePlan, TaskIssuePlanDayRule, TaskProductPool
from app.schemas.task_issue_plan import (
    TaskIssuePlanCreateRequest,
    TaskIssuePlanDayRuleCreateRequest,
    TaskIssuePlanDayRulePreviewResponse,
    TaskIssuePlanDayRuleResponse,
    TaskIssuePlanGenerateDaysRequest,
    TaskIssuePlanPreviewResponse,
    TaskIssuePlanResponse,
    TaskIssuePlanUpdateRequest,
)
from app.services.task_amount_allocation_service import TaskAmountAllocationService


class TaskIssuePlanService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_plans(
        self,
        *,
        account_id: str | None = None,
        site_id: str | None = None,
        status: str | None = None,
    ) -> list[TaskIssuePlanResponse]:
        query = select(TaskIssuePlan).order_by(TaskIssuePlan.created_at.desc(), TaskIssuePlan.id.desc())
        if account_id is not None:
            query = query.where(TaskIssuePlan.account_id == account_id)
        if site_id is not None:
            query = query.where(TaskIssuePlan.site_id == site_id)
        if status is not None:
            query = query.where(TaskIssuePlan.status == status)
        rows = self._session.execute(query).scalars().all()
        return [self._serialize(plan) for plan in rows]

    def get_plan(self, plan_id: str) -> TaskIssuePlanResponse:
        return self._serialize(self._require_plan(plan_id))

    def create_plan(self, payload: TaskIssuePlanCreateRequest) -> TaskIssuePlanResponse:
        self._require_site(account_id=payload.account_id, site_id=payload.site_id)
        if payload.default_product_pool_id:
            self._require_product_pool(account_id=payload.account_id, pool_id=payload.default_product_pool_id)
        normalized_day_rules = self._normalize_day_rules(payload)

        plan = TaskIssuePlan(
            account_id=payload.account_id,
            site_id=payload.site_id,
            name=payload.name,
            plan_type=payload.plan_type,
            status=payload.status,
            claim_gate=payload.claim_gate,
            issue_anchor=payload.issue_anchor,
            issue_mode=payload.issue_mode,
            require_previous_batch_completed=payload.require_previous_batch_completed,
            max_unfinished_batches=payload.max_unfinished_batches,
            after_last_rule_mode=payload.after_last_rule_mode,
            growth_package_count_step=payload.growth_package_count_step,
            growth_amount_step=payload.growth_amount_step,
            default_product_pool_id=payload.default_product_pool_id,
            default_tolerance_amount=payload.default_tolerance_amount,
            default_reward_ratio=payload.default_reward_ratio,
            metadata_json=payload.metadata_json,
        )
        self._session.add(plan)
        self._session.flush()

        for day_rule in normalized_day_rules:
            if day_rule.product_pool_id:
                self._require_product_pool(account_id=payload.account_id, pool_id=day_rule.product_pool_id)
            self._session.add(
                TaskIssuePlanDayRule(
                    account_id=payload.account_id,
                    site_id=payload.site_id,
                    plan_id=plan.id,
                    day_no=day_rule.day_no,
                    package_count=day_rule.package_count,
                    day_total_amount=day_rule.day_total_amount,
                    tolerance_amount=day_rule.tolerance_amount,
                    amount_allocation_mode=day_rule.amount_allocation_mode,
                    package_amounts_json=list(day_rule.package_amounts_json),
                    product_pool_id=day_rule.product_pool_id,
                    product_count_mode=day_rule.product_count_mode,
                    product_count_fixed=day_rule.product_count_fixed,
                    product_count_min=day_rule.product_count_min,
                    product_count_max=day_rule.product_count_max,
                    reward_ratio=day_rule.reward_ratio,
                    issue_time_of_day=day_rule.issue_time_of_day,
                    elapsed_delay_hours=day_rule.elapsed_delay_hours,
                    status=day_rule.status,
                    metadata_json=day_rule.metadata_json,
                )
            )

        self._session.commit()
        self._session.refresh(plan)
        return self._serialize(plan)

    def update_plan(self, plan_id: str, payload: TaskIssuePlanUpdateRequest) -> TaskIssuePlanResponse:
        plan = self._require_plan(plan_id)
        target_site_id = payload.site_id if payload.site_id is not None else plan.site_id
        self._require_site(account_id=plan.account_id, site_id=target_site_id)
        target_default_pool_id = payload.default_product_pool_id if payload.default_product_pool_id is not None else plan.default_product_pool_id
        if target_default_pool_id:
            self._require_product_pool(account_id=plan.account_id, pool_id=target_default_pool_id)

        plan.site_id = target_site_id
        plan.name = payload.name or plan.name
        plan.plan_type = payload.plan_type or plan.plan_type
        plan.status = payload.status or plan.status
        plan.claim_gate = payload.claim_gate or plan.claim_gate
        plan.issue_anchor = payload.issue_anchor or plan.issue_anchor
        plan.issue_mode = payload.issue_mode or plan.issue_mode
        if payload.require_previous_batch_completed is not None:
            plan.require_previous_batch_completed = payload.require_previous_batch_completed
        if payload.max_unfinished_batches is not None:
            plan.max_unfinished_batches = payload.max_unfinished_batches
        plan.after_last_rule_mode = payload.after_last_rule_mode or plan.after_last_rule_mode
        if payload.growth_package_count_step is not None:
            plan.growth_package_count_step = payload.growth_package_count_step
        if payload.growth_amount_step is not None:
            plan.growth_amount_step = payload.growth_amount_step
        plan.default_product_pool_id = target_default_pool_id
        if payload.default_tolerance_amount is not None:
            plan.default_tolerance_amount = payload.default_tolerance_amount
        if payload.default_reward_ratio is not None:
            plan.default_reward_ratio = payload.default_reward_ratio
        if payload.metadata_json is not None:
            plan.metadata_json = payload.metadata_json
        self._session.add(plan)

        if payload.day_rules is not None:
            normalized_day_rules = self._normalize_day_rules(
                TaskIssuePlanCreateRequest(
                    account_id=plan.account_id,
                    site_id=plan.site_id,
                    name=plan.name,
                    plan_type=plan.plan_type,
                    status=plan.status,
                    claim_gate=plan.claim_gate,
                    issue_anchor=plan.issue_anchor,
                    issue_mode=plan.issue_mode,
                    require_previous_batch_completed=plan.require_previous_batch_completed,
                    max_unfinished_batches=plan.max_unfinished_batches,
                    after_last_rule_mode=plan.after_last_rule_mode,
                    growth_package_count_step=plan.growth_package_count_step,
                    growth_amount_step=plan.growth_amount_step,
                    default_product_pool_id=plan.default_product_pool_id,
                    default_tolerance_amount=plan.default_tolerance_amount,
                    default_reward_ratio=plan.default_reward_ratio,
                    metadata_json=plan.metadata_json,
                    day_rules=payload.day_rules,
                )
            )
            for existing_rule in self._list_day_rule_rows(plan.id):
                self._session.delete(existing_rule)
            self._session.flush()
            for day_rule in normalized_day_rules:
                if day_rule.product_pool_id:
                    self._require_product_pool(account_id=plan.account_id, pool_id=day_rule.product_pool_id)
                self._session.add(
                    TaskIssuePlanDayRule(
                        account_id=plan.account_id,
                        site_id=plan.site_id,
                        plan_id=plan.id,
                        day_no=day_rule.day_no,
                        package_count=day_rule.package_count,
                        day_total_amount=day_rule.day_total_amount,
                        tolerance_amount=day_rule.tolerance_amount,
                        amount_allocation_mode=day_rule.amount_allocation_mode,
                        package_amounts_json=list(day_rule.package_amounts_json),
                        product_pool_id=day_rule.product_pool_id,
                        product_count_mode=day_rule.product_count_mode,
                        product_count_fixed=day_rule.product_count_fixed,
                        product_count_min=day_rule.product_count_min,
                        product_count_max=day_rule.product_count_max,
                        reward_ratio=day_rule.reward_ratio,
                        issue_time_of_day=day_rule.issue_time_of_day,
                        elapsed_delay_hours=day_rule.elapsed_delay_hours,
                        status=day_rule.status,
                        metadata_json=day_rule.metadata_json,
                    )
                )

        self._session.commit()
        self._session.refresh(plan)
        return self._serialize(plan)

    def set_plan_status(self, plan_id: str, status: str) -> TaskIssuePlanResponse:
        plan = self._require_plan(plan_id)
        plan.status = status
        self._session.add(plan)
        self._session.commit()
        self._session.refresh(plan)
        return self._serialize(plan)

    def preview_days(self, plan_id: str, payload: TaskIssuePlanGenerateDaysRequest) -> TaskIssuePlanPreviewResponse:
        plan = self._require_plan(plan_id)
        day_rules = [
            self._serialize_preview_day_rule(self._resolve_day_rule(plan=plan, day_no=day_no))
            for day_no in range(payload.start_day_no, payload.end_day_no + 1)
        ]
        return TaskIssuePlanPreviewResponse(plan_id=plan.id, day_rules=day_rules)

    def generate_days(self, plan_id: str, payload: TaskIssuePlanGenerateDaysRequest) -> TaskIssuePlanResponse:
        plan = self._require_plan(plan_id)
        for day_no in range(payload.start_day_no, payload.end_day_no + 1):
            existing = self._get_exact_day_rule(plan_id=plan.id, day_no=day_no)
            if existing is not None:
                continue
            resolved = self._resolve_day_rule(plan=plan, day_no=day_no)
            resolved.plan_id = plan.id
            resolved.account_id = plan.account_id
            resolved.site_id = plan.site_id
            self._session.add(resolved)
        self._session.commit()
        self._session.refresh(plan)
        return self._serialize(plan)

    def _normalize_day_rules(
        self,
        payload: TaskIssuePlanCreateRequest,
    ) -> list[TaskIssuePlanDayRuleCreateRequest]:
        seen_days: set[int] = set()
        normalized: list[TaskIssuePlanDayRuleCreateRequest] = []
        for day_rule in payload.day_rules:
            if day_rule.day_no in seen_days:
                raise ValueError(f"Duplicate day_no '{day_rule.day_no}' is not allowed.")
            seen_days.add(day_rule.day_no)

            self._validate_product_count_rule(day_rule)
            normalized_amounts = TaskAmountAllocationService.allocate(
                mode=day_rule.amount_allocation_mode,
                package_count=day_rule.package_count,
                day_total_amount=Decimal(day_rule.day_total_amount),
                manual_amounts=[Decimal(value) for value in day_rule.package_amounts_json],
            )
            normalized.append(
                day_rule.model_copy(
                    update={
                        "package_amounts_json": [self._format_amount(amount) for amount in normalized_amounts],
                    }
                )
            )
        return normalized

    def _list_day_rule_rows(self, plan_id: str) -> list[TaskIssuePlanDayRule]:
        return self._session.execute(
            select(TaskIssuePlanDayRule)
            .where(TaskIssuePlanDayRule.plan_id == plan_id)
            .order_by(TaskIssuePlanDayRule.day_no.asc())
        ).scalars().all()

    def _get_exact_day_rule(self, *, plan_id: str, day_no: int) -> TaskIssuePlanDayRule | None:
        return self._session.execute(
            select(TaskIssuePlanDayRule).where(
                TaskIssuePlanDayRule.plan_id == plan_id,
                TaskIssuePlanDayRule.day_no == day_no,
            )
        ).scalar_one_or_none()

    def _resolve_day_rule(self, *, plan: TaskIssuePlan, day_no: int) -> TaskIssuePlanDayRule:
        exact_rule = self._get_exact_day_rule(plan_id=plan.id, day_no=day_no)
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
                day_total_amount=last_rule.day_total_amount + (growth_amount_step * delta_days),
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
        resolved_total_amount = Decimal(day_total_amount or source_rule.day_total_amount).quantize(Decimal("0.01"))
        allocation_mode = source_rule.amount_allocation_mode
        package_amounts_json = list(source_rule.package_amounts_json or [])
        if allocation_mode == "manual" and (
            resolved_package_count != source_rule.package_count
            or resolved_total_amount != Decimal(source_rule.day_total_amount).quantize(Decimal("0.01"))
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

    @staticmethod
    def _validate_product_count_rule(day_rule: object) -> None:
        product_count_mode = getattr(day_rule, "product_count_mode")
        product_count_fixed = getattr(day_rule, "product_count_fixed")
        product_count_min = getattr(day_rule, "product_count_min")
        product_count_max = getattr(day_rule, "product_count_max")

        if product_count_mode == "fixed":
            if product_count_fixed is None:
                raise ValueError("product_count_fixed is required when product_count_mode is 'fixed'.")
            return
        if product_count_mode == "range":
            if product_count_min is None or product_count_max is None:
                raise ValueError("product_count_min and product_count_max are required when product_count_mode is 'range'.")
            if product_count_min > product_count_max:
                raise ValueError("product_count_min cannot be greater than product_count_max.")
            return
        raise ValueError(f"Unsupported product_count_mode '{product_count_mode}'.")

    @staticmethod
    def _format_amount(value: Decimal) -> str:
        return f"{Decimal(value).quantize(Decimal('0.01')):.2f}"

    def _require_site(self, *, account_id: str, site_id: str | None) -> H5Site | None:
        if site_id is None:
            return None
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"H5 site '{site_id}' was not found.")
        if site.account_id != account_id:
            raise ValueError("Task issue plan site account scope mismatch.")
        return site

    def _require_product_pool(self, *, account_id: str, pool_id: str) -> TaskProductPool:
        pool = self._session.get(TaskProductPool, pool_id)
        if pool is None:
            raise LookupError(f"Task product pool '{pool_id}' was not found.")
        if pool.account_id != account_id:
            raise ValueError("Task product pool account scope mismatch.")
        return pool

    def _require_plan(self, plan_id: str) -> TaskIssuePlan:
        plan = self._session.get(TaskIssuePlan, plan_id)
        if plan is None:
            raise LookupError(f"Task issue plan '{plan_id}' was not found.")
        return plan

    @staticmethod
    def _serialize_day_rule(day_rule: TaskIssuePlanDayRule) -> TaskIssuePlanDayRuleResponse:
        return TaskIssuePlanDayRuleResponse.model_validate(
            {
                "id": day_rule.id,
                "account_id": day_rule.account_id,
                "site_id": day_rule.site_id,
                "plan_id": day_rule.plan_id,
                "day_no": day_rule.day_no,
                "package_count": day_rule.package_count,
                "day_total_amount": day_rule.day_total_amount,
                "tolerance_amount": day_rule.tolerance_amount,
                "amount_allocation_mode": day_rule.amount_allocation_mode,
                "package_amounts_json": list(day_rule.package_amounts_json or []),
                "product_pool_id": day_rule.product_pool_id,
                "product_count_mode": day_rule.product_count_mode,
                "product_count_fixed": day_rule.product_count_fixed,
                "product_count_min": day_rule.product_count_min,
                "product_count_max": day_rule.product_count_max,
                "reward_ratio": day_rule.reward_ratio,
                "issue_time_of_day": day_rule.issue_time_of_day,
                "elapsed_delay_hours": day_rule.elapsed_delay_hours,
                "status": day_rule.status,
                "metadata_json": day_rule.metadata_json,
                "created_at": day_rule.created_at,
                "updated_at": day_rule.updated_at,
            }
        )

    @staticmethod
    def _serialize_preview_day_rule(day_rule: TaskIssuePlanDayRule) -> TaskIssuePlanDayRulePreviewResponse:
        return TaskIssuePlanDayRulePreviewResponse.model_validate(
            {
                "day_no": day_rule.day_no,
                "package_count": day_rule.package_count,
                "day_total_amount": day_rule.day_total_amount,
                "tolerance_amount": day_rule.tolerance_amount,
                "amount_allocation_mode": day_rule.amount_allocation_mode,
                "package_amounts_json": list(day_rule.package_amounts_json or []),
                "product_pool_id": day_rule.product_pool_id,
                "product_count_mode": day_rule.product_count_mode,
                "product_count_fixed": day_rule.product_count_fixed,
                "product_count_min": day_rule.product_count_min,
                "product_count_max": day_rule.product_count_max,
                "reward_ratio": day_rule.reward_ratio,
                "issue_time_of_day": day_rule.issue_time_of_day,
                "elapsed_delay_hours": day_rule.elapsed_delay_hours,
                "status": day_rule.status,
                "metadata_json": day_rule.metadata_json,
            }
        )

    def _serialize(self, plan: TaskIssuePlan) -> TaskIssuePlanResponse:
        day_rules = self._list_day_rule_rows(plan.id)
        return TaskIssuePlanResponse.model_validate(
            {
                "id": plan.id,
                "account_id": plan.account_id,
                "site_id": plan.site_id,
                "name": plan.name,
                "plan_type": plan.plan_type,
                "status": plan.status,
                "claim_gate": plan.claim_gate,
                "issue_anchor": plan.issue_anchor,
                "issue_mode": plan.issue_mode,
                "require_previous_batch_completed": plan.require_previous_batch_completed,
                "max_unfinished_batches": plan.max_unfinished_batches,
                "after_last_rule_mode": plan.after_last_rule_mode,
                "growth_package_count_step": plan.growth_package_count_step,
                "growth_amount_step": plan.growth_amount_step,
                "default_product_pool_id": plan.default_product_pool_id,
                "default_tolerance_amount": plan.default_tolerance_amount,
                "default_reward_ratio": plan.default_reward_ratio,
                "metadata_json": plan.metadata_json,
                "day_rules": [self._serialize_day_rule(day_rule) for day_rule in day_rules],
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
            }
        )

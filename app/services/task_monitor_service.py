from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AppUser,
    H5Site,
    MemberTaskBatch,
    TaskAlertRule,
    TaskMonitorAlertEvent,
    TaskMonitorSavedView,
    TaskManualAddItemLog,
    TaskPackageInstance,
    WalletLedgerEntry,
    WithdrawalRequest,
)
from app.schemas.task_monitor import (
    TaskAlertRuleCreateRequest,
    TaskMonitorAlertEventResponse,
    TaskAlertRuleResponse,
    TaskAlertRuleUpdateRequest,
    TaskMonitorQueryRowResponse,
    TaskMonitorSummaryResponse,
    TaskMonitorSavedViewCreateRequest,
    TaskMonitorSavedViewResponse,
    TaskMonitorSavedViewUpdateRequest,
)


class TaskMonitorService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_saved_views(
        self,
        *,
        account_id: str | None = None,
        owner_staff_id: str | None = None,
    ) -> list[TaskMonitorSavedViewResponse]:
        query = select(TaskMonitorSavedView).order_by(
            TaskMonitorSavedView.is_default.desc(),
            TaskMonitorSavedView.created_at.desc(),
        )
        if account_id is not None:
            query = query.where(TaskMonitorSavedView.account_id == account_id)
        if owner_staff_id is not None:
            query = query.where(TaskMonitorSavedView.owner_staff_id == owner_staff_id)
        rows = self._session.execute(query).scalars().all()
        return [self._serialize_saved_view(row) for row in rows]

    def create_saved_view(
        self,
        payload: TaskMonitorSavedViewCreateRequest,
        *,
        owner_staff_id: str,
    ) -> TaskMonitorSavedViewResponse:
        if payload.is_default:
            self._session.execute(
                update(TaskMonitorSavedView)
                .where(
                    TaskMonitorSavedView.account_id == payload.account_id,
                    TaskMonitorSavedView.owner_staff_id == owner_staff_id,
                )
                .values(is_default=False)
            )
        row = TaskMonitorSavedView(
            account_id=payload.account_id,
            owner_staff_id=owner_staff_id,
            name=payload.name,
            filter_json=payload.filter_json,
            sort_json=payload.sort_json,
            columns_json=payload.columns_json,
            refresh_seconds=payload.refresh_seconds,
            sound_enabled=payload.sound_enabled,
            is_default=payload.is_default,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._serialize_saved_view(row)

    def update_saved_view(
        self,
        saved_view_id: str,
        payload: TaskMonitorSavedViewUpdateRequest,
        *,
        owner_staff_id: str,
    ) -> TaskMonitorSavedViewResponse:
        row = self._session.get(TaskMonitorSavedView, saved_view_id)
        if row is None or row.owner_staff_id != owner_staff_id:
            raise LookupError(f"Task monitor saved view '{saved_view_id}' was not found.")
        if payload.is_default:
            self._session.execute(
                update(TaskMonitorSavedView)
                .where(
                    TaskMonitorSavedView.account_id == row.account_id,
                    TaskMonitorSavedView.owner_staff_id == owner_staff_id,
                    TaskMonitorSavedView.id != row.id,
                )
                .values(is_default=False)
            )
        row.name = payload.name
        row.filter_json = payload.filter_json
        row.sort_json = payload.sort_json
        row.columns_json = payload.columns_json
        row.refresh_seconds = payload.refresh_seconds
        row.sound_enabled = payload.sound_enabled
        row.is_default = payload.is_default
        self._session.commit()
        self._session.refresh(row)
        return self._serialize_saved_view(row)

    def delete_saved_view(self, saved_view_id: str, *, owner_staff_id: str) -> None:
        row = self._session.get(TaskMonitorSavedView, saved_view_id)
        if row is None or row.owner_staff_id != owner_staff_id:
            raise LookupError(f"Task monitor saved view '{saved_view_id}' was not found.")
        self._session.delete(row)
        self._session.commit()

    def list_alert_rules(self, *, account_id: str | None = None) -> list[TaskAlertRuleResponse]:
        query = select(TaskAlertRule).order_by(TaskAlertRule.created_at.desc())
        if account_id is not None:
            query = query.where(TaskAlertRule.account_id == account_id)
        rows = self._session.execute(query).scalars().all()
        return [self._serialize_alert_rule(row) for row in rows]

    def create_alert_rule(
        self,
        payload: TaskAlertRuleCreateRequest,
        *,
        created_by: str,
    ) -> TaskAlertRuleResponse:
        row = TaskAlertRule(
            account_id=payload.account_id,
            name=payload.name,
            status=payload.status,
            condition_json=payload.condition_json,
            action_json=payload.action_json,
            sound_enabled=payload.sound_enabled,
            priority=payload.priority,
            created_by=created_by,
            metadata_json=payload.metadata_json,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._serialize_alert_rule(row)

    def update_alert_rule(
        self,
        alert_rule_id: str,
        payload: TaskAlertRuleUpdateRequest,
    ) -> TaskAlertRuleResponse:
        row = self._session.get(TaskAlertRule, alert_rule_id)
        if row is None:
            raise LookupError(f"Task alert rule '{alert_rule_id}' was not found.")
        row.name = payload.name
        row.status = payload.status
        row.condition_json = payload.condition_json
        row.action_json = payload.action_json
        row.sound_enabled = payload.sound_enabled
        row.priority = payload.priority
        row.metadata_json = payload.metadata_json
        self._session.commit()
        self._session.refresh(row)
        return self._serialize_alert_rule(row)

    def delete_alert_rule(self, alert_rule_id: str) -> None:
        row = self._session.get(TaskAlertRule, alert_rule_id)
        if row is None:
            raise LookupError(f"Task alert rule '{alert_rule_id}' was not found.")
        self._session.delete(row)
        self._session.commit()

    def list_alert_events(
        self,
        *,
        account_id: str | None = None,
        status: str | None = None,
    ) -> list[TaskMonitorAlertEventResponse]:
        self._sync_alert_events(account_id=account_id)
        query = select(TaskMonitorAlertEvent, TaskAlertRule, AppUser.public_user_id).join(
            TaskAlertRule,
            TaskAlertRule.id == TaskMonitorAlertEvent.alert_rule_id,
        ).join(
            AppUser,
            AppUser.id == TaskMonitorAlertEvent.user_id,
        ).order_by(TaskMonitorAlertEvent.triggered_at.desc())
        if account_id is not None:
            query = query.where(TaskMonitorAlertEvent.account_id == account_id)
        if status is not None:
            query = query.where(TaskMonitorAlertEvent.status == status)
        rows = self._session.execute(query).all()
        return [
            self._serialize_alert_event(event=event, rule=rule, public_user_id=public_user_id)
            for event, rule, public_user_id in rows
        ]

    def acknowledge_alert_event(
        self,
        alert_event_id: str,
        *,
        actor_id: str,
    ) -> TaskMonitorAlertEventResponse:
        event = self._session.get(TaskMonitorAlertEvent, alert_event_id)
        if event is None:
            raise LookupError(f"Task monitor alert '{alert_event_id}' was not found.")
        if event.status == "resolved":
            rule = self._require_alert_rule(event.alert_rule_id)
            public_user_id = self._require_public_user_id(event.user_id)
            return self._serialize_alert_event(event=event, rule=rule, public_user_id=public_user_id)
        event.status = "acknowledged"
        event.acknowledged_at = event.acknowledged_at or self._now()
        event.acknowledged_by = actor_id
        self._session.commit()
        rule = self._require_alert_rule(event.alert_rule_id)
        public_user_id = self._require_public_user_id(event.user_id)
        return self._serialize_alert_event(event=event, rule=rule, public_user_id=public_user_id)

    def resolve_alert_event(
        self,
        alert_event_id: str,
        *,
        actor_id: str,
    ) -> TaskMonitorAlertEventResponse:
        event = self._session.get(TaskMonitorAlertEvent, alert_event_id)
        if event is None:
            raise LookupError(f"Task monitor alert '{alert_event_id}' was not found.")
        event.status = "resolved"
        if event.acknowledged_at is None:
            event.acknowledged_at = self._now()
        if event.acknowledged_by is None:
            event.acknowledged_by = actor_id
        event.resolved_at = self._now()
        event.resolved_by = actor_id
        self._session.commit()
        rule = self._require_alert_rule(event.alert_rule_id)
        public_user_id = self._require_public_user_id(event.user_id)
        return self._serialize_alert_event(event=event, rule=rule, public_user_id=public_user_id)

    def query_packages(
        self,
        *,
        account_id: str | None = None,
        user_id: str | None = None,
        user_query: str | None = None,
        status: str | None = None,
        day_planned_amount_min: Decimal | None = None,
        day_planned_amount_max: Decimal | None = None,
        day_manual_added_amount_min: Decimal | None = None,
        day_manual_added_amount_max: Decimal | None = None,
        day_effective_amount_min: Decimal | None = None,
        day_effective_amount_max: Decimal | None = None,
        planned_amount_min: Decimal | None = None,
        planned_amount_max: Decimal | None = None,
        manual_added_amount_min: Decimal | None = None,
        manual_added_amount_max: Decimal | None = None,
        effective_amount_min: Decimal | None = None,
        effective_amount_max: Decimal | None = None,
        has_manual_add: bool | None = None,
        latest_manual_add_operator_id: str | None = None,
        current_product_amount_min: Decimal | None = None,
        current_product_amount_max: Decimal | None = None,
        total_recharge_amount_min: Decimal | None = None,
        total_recharge_amount_max: Decimal | None = None,
        total_withdraw_amount_min: Decimal | None = None,
        total_withdraw_amount_max: Decimal | None = None,
    ) -> list[TaskMonitorQueryRowResponse]:
        stmt = (
            select(TaskPackageInstance, AppUser.public_user_id, H5Site.site_key)
            .join(AppUser, AppUser.id == TaskPackageInstance.user_id)
            .join(H5Site, H5Site.id == TaskPackageInstance.site_id, isouter=True)
            .options(selectinload(TaskPackageInstance.items))
            .order_by(TaskPackageInstance.created_at.desc())
        )
        if account_id is not None:
            stmt = stmt.where(TaskPackageInstance.account_id == account_id)
        if user_id is not None:
            stmt = stmt.where(TaskPackageInstance.user_id == user_id)
        if status is not None:
            stmt = stmt.where(TaskPackageInstance.status == status)

        rows = self._session.execute(stmt).all()
        packages = [row[0] for row in rows]
        if not packages:
            return []

        user_ids = {package.user_id for package in packages}
        account_ids = {package.account_id for package in packages}
        package_ids = {package.id for package in packages}
        batch_ids = {package.batch_id for package in packages if package.batch_id}
        recharge_totals = self._load_real_recharge_totals(user_ids=user_ids, account_ids=account_ids)
        withdraw_totals = self._load_withdraw_totals(user_ids=user_ids, account_ids=account_ids)
        latest_manual_add_logs = self._load_latest_manual_add_logs(package_ids=package_ids)
        batches = self._load_batches(batch_ids=batch_ids)

        items: list[TaskMonitorQueryRowResponse] = []
        normalized_user_query = user_query.strip().lower() if user_query else None
        normalized_latest_manual_add_operator_id = (
            latest_manual_add_operator_id.strip().lower() if latest_manual_add_operator_id else None
        )
        for package, public_user_id, site_key in rows:
            if normalized_user_query:
                if normalized_user_query not in package.user_id.lower() and normalized_user_query not in (public_user_id or "").lower():
                    continue
            latest_manual_add_log = latest_manual_add_logs.get(package.id)
            latest_operator_id = latest_manual_add_log.operator_id if latest_manual_add_log is not None else None
            if normalized_latest_manual_add_operator_id:
                if (latest_operator_id or "").lower() != normalized_latest_manual_add_operator_id:
                    continue
            batch = batches.get(package.batch_id) if package.batch_id else None
            planned_amount = Decimal(package.planned_amount)
            manual_added_amount = Decimal(package.manual_added_amount)
            effective_amount = Decimal(package.effective_amount)
            day_planned_amount = Decimal(batch.planned_amount) if batch is not None else planned_amount
            day_system_generated_amount = (
                Decimal(batch.system_generated_amount) if batch is not None else Decimal(package.system_generated_amount)
            )
            day_manual_added_amount = Decimal(batch.manual_added_amount) if batch is not None else manual_added_amount
            day_effective_amount = Decimal(batch.effective_day_amount) if batch is not None else effective_amount
            current_product = self._resolve_current_product(package)
            current_product_amount = Decimal(current_product.price) if current_product is not None else Decimal("0")
            total_real_recharge_amount = recharge_totals.get((package.account_id, package.user_id), Decimal("0"))
            total_withdraw_amount = withdraw_totals.get((package.account_id, package.user_id), Decimal("0"))
            package_has_manual_add = manual_added_amount > Decimal("0")

            if not self._matches_decimal_range(day_planned_amount, day_planned_amount_min, day_planned_amount_max):
                continue
            if not self._matches_decimal_range(
                day_manual_added_amount,
                day_manual_added_amount_min,
                day_manual_added_amount_max,
            ):
                continue
            if not self._matches_decimal_range(day_effective_amount, day_effective_amount_min, day_effective_amount_max):
                continue
            if not self._matches_decimal_range(planned_amount, planned_amount_min, planned_amount_max):
                continue
            if not self._matches_decimal_range(manual_added_amount, manual_added_amount_min, manual_added_amount_max):
                continue
            if not self._matches_decimal_range(effective_amount, effective_amount_min, effective_amount_max):
                continue
            if has_manual_add is not None and package_has_manual_add is not has_manual_add:
                continue
            if not self._matches_decimal_range(current_product_amount, current_product_amount_min, current_product_amount_max):
                continue
            if not self._matches_decimal_range(total_real_recharge_amount, total_recharge_amount_min, total_recharge_amount_max):
                continue
            if not self._matches_decimal_range(total_withdraw_amount, total_withdraw_amount_min, total_withdraw_amount_max):
                continue

            batch_index = package.batch_index or 1
            batch_total = package.batch_total or 1
            items.append(
                TaskMonitorQueryRowResponse(
                    package_id=package.id,
                    account_id=package.account_id,
                    user_id=package.user_id,
                    public_user_id=public_user_id,
                    site_id=package.site_id,
                    site_key=site_key,
                    batch_id=package.batch_id,
                    day_no=package.batch_day_no,
                    progress_label=f"{batch_index}/{batch_total}",
                    status=package.status,
                    current_item_index=package.current_item_index,
                    day_planned_amount=float(day_planned_amount),
                    day_system_generated_amount=float(day_system_generated_amount),
                    day_manual_added_amount=float(day_manual_added_amount),
                    day_effective_amount=float(day_effective_amount),
                    planned_amount=float(planned_amount),
                    system_generated_amount=float(package.system_generated_amount),
                    manual_added_amount=float(manual_added_amount),
                    effective_amount=float(effective_amount),
                    has_manual_add=package_has_manual_add,
                    manual_added_item_count=int(package.manual_added_item_count or 0),
                    latest_manual_add_operator_id=latest_operator_id,
                    latest_manual_add_at=(
                        latest_manual_add_log.created_at
                        if latest_manual_add_log is not None
                        else package.last_manual_added_at
                    ),
                    current_product_id=current_product.id if current_product is not None else None,
                    current_product_name=current_product.product_name,
                    current_product_amount=float(current_product_amount),
                    current_product_origin=current_product.item_origin if current_product is not None else None,
                    total_real_recharge_amount=float(total_real_recharge_amount),
                    total_withdraw_amount=float(total_withdraw_amount),
                    estimated_reward_amount=float(effective_amount * Decimal(package.reward_ratio_snapshot)),
                    claimed_at=package.claimed_at,
                    completed_at=package.completed_at,
                )
            )
        return items

    def summarize_packages(self, **filters: object) -> TaskMonitorSummaryResponse:
        rows = self.query_packages(**filters)
        return TaskMonitorSummaryResponse(
            total_count=len(rows),
            manual_add_count=sum(1 for item in rows if item.has_manual_add),
            total_planned_amount=sum(item.planned_amount for item in rows),
            total_manual_added_amount=sum(item.manual_added_amount for item in rows),
            total_effective_amount=sum(item.effective_amount for item in rows),
            total_real_recharge_amount=sum(item.total_real_recharge_amount for item in rows),
            total_withdraw_amount=sum(item.total_withdraw_amount for item in rows),
        )

    @staticmethod
    def _serialize_saved_view(row: TaskMonitorSavedView) -> TaskMonitorSavedViewResponse:
        return TaskMonitorSavedViewResponse.model_validate(
            {
                "id": row.id,
                "account_id": row.account_id,
                "owner_staff_id": row.owner_staff_id,
                "name": row.name,
                "filter_json": row.filter_json,
                "sort_json": row.sort_json,
                "columns_json": row.columns_json,
                "refresh_seconds": row.refresh_seconds,
                "sound_enabled": row.sound_enabled,
                "is_default": row.is_default,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    @staticmethod
    def _serialize_alert_rule(row: TaskAlertRule) -> TaskAlertRuleResponse:
        return TaskAlertRuleResponse.model_validate(
            {
                "id": row.id,
                "account_id": row.account_id,
                "name": row.name,
                "status": row.status,
                "condition_json": row.condition_json,
                "action_json": row.action_json,
                "sound_enabled": row.sound_enabled,
                "priority": row.priority,
                "created_by": row.created_by,
                "metadata_json": row.metadata_json,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    @staticmethod
    def _serialize_alert_event(
        *,
        event: TaskMonitorAlertEvent,
        rule: TaskAlertRule,
        public_user_id: str,
    ) -> TaskMonitorAlertEventResponse:
        return TaskMonitorAlertEventResponse.model_validate(
            {
                "id": event.id,
                "account_id": event.account_id,
                "alert_rule_id": event.alert_rule_id,
                "package_id": event.package_id,
                "user_id": event.user_id,
                "public_user_id": public_user_id,
                "status": event.status,
                "priority": rule.priority,
                "rule_name": rule.name,
                "current_value": float(event.current_value),
                "threshold_value": float(event.threshold_value) if event.threshold_value is not None else None,
                "sound_enabled": rule.sound_enabled,
                "triggered_at": event.triggered_at,
                "acknowledged_at": event.acknowledged_at,
                "acknowledged_by": event.acknowledged_by,
                "resolved_at": event.resolved_at,
                "resolved_by": event.resolved_by,
            }
        )

    def _load_real_recharge_totals(
        self,
        *,
        user_ids: set[str],
        account_ids: set[str],
    ) -> dict[tuple[str, str], Decimal]:
        if not user_ids or not account_ids:
            return {}
        rows = self._session.execute(
            select(
                WalletLedgerEntry.account_id,
                WalletLedgerEntry.user_id,
                WalletLedgerEntry.amount,
            ).where(
                WalletLedgerEntry.account_id.in_(account_ids),
                WalletLedgerEntry.user_id.in_(user_ids),
                WalletLedgerEntry.direction == "credit",
                WalletLedgerEntry.is_real_recharge.is_(True),
            )
        ).all()
        totals: dict[tuple[str, str], Decimal] = {}
        for account_id, user_id, amount in rows:
            key = (account_id, user_id)
            totals[key] = totals.get(key, Decimal("0")) + Decimal(amount or 0)
        return totals

    def _load_batches(
        self,
        *,
        batch_ids: set[str],
    ) -> dict[str, MemberTaskBatch]:
        if not batch_ids:
            return {}
        rows = self._session.execute(
            select(MemberTaskBatch).where(MemberTaskBatch.id.in_(batch_ids))
        ).scalars().all()
        return {row.id: row for row in rows}

    def _load_latest_manual_add_logs(
        self,
        *,
        package_ids: set[str],
    ) -> dict[str, TaskManualAddItemLog]:
        if not package_ids:
            return {}
        rows = self._session.execute(
            select(TaskManualAddItemLog)
            .where(TaskManualAddItemLog.package_instance_id.in_(package_ids))
            .order_by(TaskManualAddItemLog.created_at.desc(), TaskManualAddItemLog.id.desc())
        ).scalars().all()
        latest_by_package_id: dict[str, TaskManualAddItemLog] = {}
        for row in rows:
            latest_by_package_id.setdefault(row.package_instance_id, row)
        return latest_by_package_id

    def _load_withdraw_totals(
        self,
        *,
        user_ids: set[str],
        account_ids: set[str],
    ) -> dict[tuple[str, str], Decimal]:
        if not user_ids or not account_ids:
            return {}
        rows = self._session.execute(
            select(
                WithdrawalRequest.account_id,
                WithdrawalRequest.user_id,
                WithdrawalRequest.amount,
            ).where(
                WithdrawalRequest.account_id.in_(account_ids),
                WithdrawalRequest.user_id.in_(user_ids),
                WithdrawalRequest.status.in_(["approved", "paid", "processing"]),
            )
        ).all()
        totals: dict[tuple[str, str], Decimal] = {}
        for account_id, user_id, amount in rows:
            key = (account_id, user_id)
            totals[key] = totals.get(key, Decimal("0")) + Decimal(amount or 0)
        return totals

    @staticmethod
    def _resolve_current_product(package: TaskPackageInstance) -> TaskPackageInstanceItem | None:
        visible_item = next((item for item in package.items if item.visible_to_user), None)
        if visible_item is not None:
            return visible_item
        indexed_item = next((item for item in package.items if item.sort_order == package.current_item_index), None)
        if indexed_item is not None:
            return indexed_item
        pending_item = next((item for item in package.items if item.status != "completed"), None)
        if pending_item is not None:
            return pending_item
        return None

    @staticmethod
    def _matches_decimal_range(
        value: Decimal,
        minimum: Decimal | None,
        maximum: Decimal | None,
    ) -> bool:
        if minimum is not None and value < minimum:
            return False
        if maximum is not None and value > maximum:
            return False
        return True

    def _sync_alert_events(self, *, account_id: str | None = None) -> None:
        rules = self.list_alert_rules(account_id=account_id)
        if not rules:
            return
        rows = self.query_packages(account_id=account_id)
        existing_rows = self._session.execute(
            select(TaskMonitorAlertEvent)
            .where(TaskMonitorAlertEvent.account_id == account_id) if account_id is not None else select(TaskMonitorAlertEvent)
        ).scalars().all()
        existing_by_key = {
            (row.alert_rule_id, row.package_id): row
            for row in existing_rows
        }
        created = False
        for rule in rules:
            if rule.status != "active":
                continue
            for row in rows:
                matched, current_value, threshold_value = self._rule_matches(rule=rule, row=row)
                if not matched:
                    continue
                key = (rule.id, row.package_id)
                if key in existing_by_key:
                    continue
                event = TaskMonitorAlertEvent(
                    account_id=row.account_id,
                    alert_rule_id=rule.id,
                    package_id=row.package_id,
                    user_id=row.user_id,
                    status="open",
                    current_value=current_value,
                    threshold_value=threshold_value,
                    triggered_at=self._now(),
                    metadata_json={"rule_name": rule.name},
                )
                self._session.add(event)
                existing_by_key[key] = event
                created = True
        if created:
            self._session.commit()

    @staticmethod
    def _rule_matches(
        *,
        rule: TaskAlertRuleResponse,
        row: TaskMonitorQueryRowResponse,
    ) -> tuple[bool, Decimal, Decimal | None]:
        field_name = str(rule.condition_json.get("field") or "").strip()
        operator = str(rule.condition_json.get("operator") or "").strip()
        threshold_raw = rule.condition_json.get("value")
        if not field_name or threshold_raw is None:
            return False, Decimal("0"), None
        field_map = {
            "planned_amount": row.planned_amount,
            "manual_added_amount": row.manual_added_amount,
            "effective_amount": row.effective_amount,
            "current_product_amount": row.current_product_amount,
            "total_real_recharge_amount": row.total_real_recharge_amount,
            "total_withdraw_amount": row.total_withdraw_amount,
        }
        if field_name not in field_map:
            return False, Decimal("0"), None
        current_value = Decimal(str(field_map[field_name]))
        threshold_value = Decimal(str(threshold_raw))
        matched = (
            (operator == ">=" and current_value >= threshold_value)
            or (operator == ">" and current_value > threshold_value)
            or (operator == "<=" and current_value <= threshold_value)
            or (operator == "<" and current_value < threshold_value)
            or (operator == "==" and current_value == threshold_value)
        )
        return matched, current_value, threshold_value

    def _require_alert_rule(self, alert_rule_id: str) -> TaskAlertRule:
        row = self._session.get(TaskAlertRule, alert_rule_id)
        if row is None:
            raise LookupError(f"Task alert rule '{alert_rule_id}' was not found.")
        return row

    def _require_public_user_id(self, user_id: str) -> str:
        value = self._session.scalar(select(AppUser.public_user_id).where(AppUser.id == user_id))
        if value is None:
            raise LookupError(f"App user '{user_id}' was not found.")
        return value

    @staticmethod
    def _now():
        from app.db.models import utc_now

        return utc_now()

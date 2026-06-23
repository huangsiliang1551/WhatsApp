from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaskRule
from app.schemas.marketing import TaskRuleCreateRequest, TaskRuleUpdateRequest


class TaskRuleService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_rules(
        self,
        account_id: str | None = None,
        rule_type: str | None = None,
        trigger_type: str | None = None,
    ) -> dict[str, Any]:
        query = select(TaskRule).order_by(TaskRule.created_at.desc())
        if account_id:
            query = query.where(TaskRule.account_id == account_id)
        if rule_type:
            query = query.where(TaskRule.rule_type == rule_type)
        if trigger_type:
            query = query.where(TaskRule.trigger_type == trigger_type)
        items = self._session.execute(query).scalars().all()
        return {"items": [self._to_response(r) for r in items], "total": len(items)}

    def get_rule(self, rule_id: str) -> TaskRule:
        rule = self._session.get(TaskRule, rule_id)
        if rule is None:
            raise LookupError(f"Task rule '{rule_id}' not found.")
        return rule

    def create_rule(self, payload: TaskRuleCreateRequest) -> TaskRule:
        rule = TaskRule(
            account_id=payload.account_id,
            name=payload.name,
            rule_type=payload.rule_type,
            trigger_type=payload.trigger_type,
            trigger_config=payload.trigger_config,
            package_id=payload.package_id,
            follow_up_chain=payload.follow_up_chain,
            expiry_config=payload.expiry_config,
            is_enabled=payload.is_enabled,
        )
        self._session.add(rule)
        self._session.commit()
        self._session.refresh(rule)
        return rule

    def update_rule(self, rule_id: str, payload: TaskRuleUpdateRequest) -> TaskRule:
        rule = self._session.get(TaskRule, rule_id)
        if rule is None:
            raise LookupError(f"Task rule '{rule_id}' not found.")
        if payload.name is not None:
            rule.name = payload.name
        if payload.trigger_config is not None:
            rule.trigger_config = payload.trigger_config
        if payload.package_id is not None:
            rule.package_id = payload.package_id
        if payload.follow_up_chain is not None:
            rule.follow_up_chain = payload.follow_up_chain
        if payload.expiry_config is not None:
            rule.expiry_config = payload.expiry_config
        if payload.is_enabled is not None:
            rule.is_enabled = payload.is_enabled
        self._session.commit()
        self._session.refresh(rule)
        return rule

    def toggle_rule(self, rule_id: str, is_enabled: bool) -> TaskRule:
        rule = self._session.get(TaskRule, rule_id)
        if rule is None:
            raise LookupError(f"Task rule '{rule_id}' not found.")
        rule.is_enabled = is_enabled
        self._session.commit()
        self._session.refresh(rule)
        return rule

    def delete_rule(self, rule_id: str) -> None:
        rule = self._session.get(TaskRule, rule_id)
        if rule is None:
            raise LookupError(f"Task rule '{rule_id}' not found.")

        # 检查是否有关联任务实例
        from app.db.models import MktTaskInstance
        from sqlalchemy import func, select
        count = self._session.scalar(
            select(func.count(MktTaskInstance.id)).where(
                MktTaskInstance.rule_id == rule_id
            )
        ) or 0
        if count > 0:
            raise ValueError(
                f"Cannot delete rule '{rule.name}': {count} task instance(s) still reference it. "
                "Delete or expire all related task instances first."
            )

        self._session.delete(rule)
        self._session.commit()

    def get_enabled_rules(
        self,
        account_id: str | None = None,
        trigger_type: str | None = None,
    ) -> list[TaskRule]:
        query = select(TaskRule).where(TaskRule.is_enabled == True)
        if account_id:
            query = query.where(TaskRule.account_id == account_id)
        if trigger_type:
            query = query.where(TaskRule.trigger_type == trigger_type)
        return list(self._session.execute(query).scalars().all())

    def _to_response(self, rule: TaskRule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "account_id": rule.account_id,
            "name": rule.name,
            "rule_type": rule.rule_type,
            "trigger_type": rule.trigger_type,
            "trigger_config": rule.trigger_config,
            "package_id": rule.package_id,
            "follow_up_chain": rule.follow_up_chain,
            "expiry_config": rule.expiry_config,
            "is_enabled": rule.is_enabled,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }

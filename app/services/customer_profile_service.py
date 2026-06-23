"""Customer profile service — IV-BE-004.

Aggregates customer behavioral data and evaluates auto-tag rules.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    CustomerAutoTagRule,
    Message,
    UserTag,
)

logger = structlog.get_logger()


class CustomerProfileService:
    """Customer profile aggregation and auto-tag evaluation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Profile ───────────────────────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> dict[str, Any]:
        """Build a customer profile with behavior data and tags."""
        behavior = self._aggregate_behavior(user_id)
        auto_tags = self._get_auto_tags(user_id)
        manual_tags = self._get_manual_tags(user_id)

        return {
            "user_id": user_id,
            "behavior": behavior,
            "auto_tags": auto_tags,
            "manual_tags": manual_tags,
            "tag_count": len(auto_tags) + len(manual_tags),
        }

    def _aggregate_behavior(self, user_id: str) -> dict[str, Any]:
        """Aggregate behavioral data for a user."""
        # Sign-in stats (placeholder - SignIn model may not exist)
        sign_count = 0

        # Recharge total from conversations or task rewards (simplified)
        recharge_total = self._session.scalar(
            select(func.coalesce(func.sum(Conversation.meta.get("recharge_amount", 0).as_string().cast(Decimal)), 0))  # type: ignore[attr-defined]
            .where(Conversation.customer_id == user_id)
        ) or Decimal("0")

        # Conversation count
        conv_count = self._session.scalar(
            select(func.count(Conversation.id)).where(Conversation.customer_id == user_id)
        ) or 0

        # Last active timestamp
        last_msg = self._session.scalar(
            select(func.max(Message.created_at))
            .where(Message.sender_id == user_id)
        )

        return {
            "sign_in_count": sign_count,
            "sign_in_streak": 0,  # Simplified; needs dedicated streak tracking
            "recharge_total": float(recharge_total),
            "recharge_count": 0,
            "withdraw_total": 0.0,
            "conversation_count": conv_count,
            "last_active_at": last_msg.isoformat() if last_msg else None,
        }

    def _get_auto_tags(self, user_id: str) -> list[str]:
        """Get auto-assigned tags for a user."""
        tags = self._session.scalars(
            select(UserTag.tag_name)
            .where(
                UserTag.user_id == user_id,
                UserTag.source == "auto",
            )
        ).all()
        return list(tags)

    def _get_manual_tags(self, user_id: str) -> list[str]:
        """Get manually assigned tags for a user."""
        tags = self._session.scalars(
            select(UserTag.tag_name)
            .where(
                UserTag.user_id == user_id,
                UserTag.source == "manual",
            )
        ).all()
        return list(tags)

    # ── Auto-tag rules ────────────────────────────────────────────────────────────

    def list_rules(self, agency_id: str | None = None) -> list[CustomerAutoTagRule]:
        stmt = select(CustomerAutoTagRule).order_by(CustomerAutoTagRule.created_at.desc())
        if agency_id:
            stmt = stmt.where(CustomerAutoTagRule.agency_id == agency_id)
        return list(self._session.scalars(stmt).all())

    def create_rule(
        self,
        agency_id: str | None,
        name: str,
        condition_type: str,
        condition_operator: str,
        condition_value: float,
        tag_name: str,
    ) -> CustomerAutoTagRule:
        rule = CustomerAutoTagRule(
            agency_id=agency_id,
            name=name,
            condition_type=condition_type,
            condition_operator=condition_operator,
            condition_value=Decimal(str(condition_value)),
            tag_name=tag_name,
        )
        self._session.add(rule)
        self._session.flush()
        return rule

    def update_rule(
        self,
        rule_id: str,
        **kwargs: Any,
    ) -> CustomerAutoTagRule | None:
        rule = self._session.get(CustomerAutoTagRule, rule_id)
        if not rule:
            return None
        for key, value in kwargs.items():
            if hasattr(rule, key) and value is not None:
                setattr(rule, key, value)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        rule = self._session.get(CustomerAutoTagRule, rule_id)
        if not rule:
            return False
        self._session.delete(rule)
        return True

    # ── Evaluate ──────────────────────────────────────────────────────────────────

    def evaluate_auto_tags(self, user_id: str) -> list[str]:
        """Evaluate all enabled rules against a user's behavior data.

        Returns list of tag names that should be applied.
        """
        rules = self._session.scalars(
            select(CustomerAutoTagRule).where(CustomerAutoTagRule.is_enabled.is_(True))
        ).all()

        if not rules:
            return []

        behavior = self._aggregate_behavior(user_id)
        matching_tags: list[str] = []

        for rule in rules:
            value = self._get_condition_value(behavior, rule.condition_type)
            if value is None:
                continue
            if self._compare(value, rule.condition_operator, float(rule.condition_value)):
                matching_tags.append(rule.tag_name)

        # Apply tags (simplified: just log them; full implementation would
        # persist to UserTag table)
        logger.info(
            "auto_tags_evaluated",
            user_id=user_id,
            matched_tags=matching_tags,
        )
        return matching_tags

    def _get_condition_value(
        self,
        behavior: dict[str, Any],
        condition_type: str,
    ) -> float | None:
        mapping = {
            "sign_in_count": behavior.get("sign_in_count"),
            "recharge_total": behavior.get("recharge_total"),
            "conversation_count": behavior.get("conversation_count"),
        }
        val = mapping.get(condition_type)
        if val is None:
            return None
        return float(val)

    def _compare(self, actual: float, operator: str, expected: float) -> bool:
        if operator == "gt":
            return actual > expected
        if operator == "lt":
            return actual < expected
        if operator == "eq":
            return actual == expected
        if operator == "gte":
            return actual >= expected
        if operator == "lte":
            return actual <= expected
        return False

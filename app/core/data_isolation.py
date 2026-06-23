"""Data isolation helpers for multi-tenant agency-level filtering.

Usage:
    from app.core.data_isolation import apply_agency_scope

    query = select(Conversation)
    query = apply_agency_scope(query, Conversation, actor, agency_field="agency_id")
    results = session.execute(query).scalars().all()
"""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import ColumnElement, Select, UnaryExpression, asc

T = TypeVar("T")

# ─── Supported model → agency_id column mapping ───────────────────────────────
# Add entries here as more models gain agency_id support.
_MODEL_AGENCY_FIELD: dict[str, str] = {
    "H5Site": "agency_id",
    "Conversation": "agency_id",
    "Ticket": "agency_id",
    "Agent": "agency_id",
    "AgencyBilling": "agency_id",
    "RolePermission": "agency_id",
    "KnowledgeCategory": "agency_id",
    "KnowledgeArticle": "agency_id",
    "CustomerAutoTagRule": "agency_id",
    "ApiRateLimit": "agency_id",
    # Future additions:
    # "Message": "agency_id",
    # "ConversationNote": "agency_id",
}


# ─── Generic agency-scope helpers via subquery on account_id or site_id ───────


def apply_agency_scope_by_account(
    query: Select[tuple[T]],
    model_class: type[T],
    agency_id: str | None,
    session: Any,
) -> Select[tuple[T]]:
    """Filter a query by agency_id through the model's account_id column.

    Maps agency_id → H5Site account_ids → filter model.account_id.
    """
    if not agency_id:
        return query

    from app.db.models import H5Site
    from sqlalchemy import select

    account_ids = session.scalars(
        select(H5Site.account_id).where(H5Site.agency_id == agency_id).distinct()
    ).all()

    if not account_ids:
        return query.where(1 == 0)

    if hasattr(model_class, "account_id"):
        return query.where(model_class.account_id.in_(account_ids))
    return query


def apply_agency_scope_by_site(
    query: Select[tuple[T]],
    model_class: type[T],
    agency_id: str | None,
    session: Any,
) -> Select[tuple[T]]:
    """Filter a query by agency_id through the model's site_id column.

    Works for models that have ``site_id`` but not ``agency_id`` or ``account_id``.
    Uses a subquery to find all H5Site IDs belonging to the given agency,
    then filters ``model.site_id IN (site_ids)``.
    """
    if not agency_id:
        return query

    from app.db.models import H5Site
    from sqlalchemy import select

    site_ids = session.scalars(
        select(H5Site.id).where(H5Site.agency_id == agency_id)
    ).all()

    if not site_ids:
        return query.where(1 == 0)

    if hasattr(model_class, "site_id"):
        return query.where(model_class.site_id.in_(site_ids))
    return query


def get_account_ids_for_agency(session: Any, agency_id: str | None) -> list[str]:
    """Return all account_ids that belong to the given agency via H5Site."""
    if not agency_id:
        return []
    from app.db.models import H5Site
    from sqlalchemy import select
    return list(session.scalars(
        select(H5Site.account_id).where(H5Site.agency_id == agency_id).distinct()
    ).all())


def get_site_ids_for_agency(session: Any, agency_id: str | None) -> list[str]:
    """Return all site IDs that belong to the given agency."""
    if not agency_id:
        return []
    from app.db.models import H5Site
    from sqlalchemy import select
    return list(session.scalars(
        select(H5Site.id).where(H5Site.agency_id == agency_id)
    ).all())


class DataIsolationActor:
    """Standardised actor info for data-scope decisions."""

    def __init__(self, user_type: str, agency_id: str | None = None) -> None:
        self.user_type = user_type
        self.agency_id = agency_id

    @property
    def is_super_admin(self) -> bool:
        return self.user_type == "super_admin"

    @property
    def is_agent(self) -> bool:
        return self.user_type == "agent"

    @property
    def is_agent_member(self) -> bool:
        return self.user_type == "agent_member"

    @classmethod
    def super_admin(cls) -> DataIsolationActor:
        return cls(user_type="super_admin")

    @classmethod
    def for_agency(cls, user_type: str, agency_id: str) -> DataIsolationActor:
        return cls(user_type=user_type, agency_id=agency_id)


def apply_agency_scope(
    query: Select[tuple[T]],
    model_class: type[T],
    actor: DataIsolationActor,
    *,
    agency_field: str | None = None,
    default_order_by: ColumnElement | UnaryExpression | None = None,
) -> Select[tuple[T]]:
    """Apply agency-level data isolation filter to a query.

    - super_admin: no filter (sees all)
    - agent / agent_member: filter by ``model.agency_id == actor.agency_id``

    Parameters
    ----------
    query : Select
        The SQLAlchemy select statement to modify.
    model_class : type
        The SQLAlchemy model class (used to resolve the column).
    actor : DataIsolationActor
        The authenticated actor info.
    agency_field : str, optional
        Override the column name for agency_id on the model.
        If not given, looked up from ``_MODEL_AGENCY_FIELD``.
    default_order_by : SQLAlchemy expression, optional
        A default ORDER BY clause to add if the query has none.

    Returns
    -------
    Select
        The modified query with the scope filter applied.
    """
    if actor.is_super_admin:
        # No filtering for super admin
        query = _ensure_order_by(query, default_order_by)
        return query

    if not actor.agency_id:
        # No agency context → deny all
        query = query.where(1 == 0)
        return query

    # Resolve the agency_id column
    field_name = agency_field or _resolve_agency_field(model_class)
    column = getattr(model_class, field_name, None)
    if column is None:
        # Column not found → deny all for safety
        query = query.where(1 == 0)
        return query

    query = query.where(column == actor.agency_id)
    query = _ensure_order_by(query, default_order_by)
    return query


def _resolve_agency_field(model_class: type) -> str:
    """Resolve the agency_id column name for the given model class."""
    class_name = model_class.__name__
    return _MODEL_AGENCY_FIELD.get(class_name, "agency_id")


def _ensure_order_by(
    query: Select[tuple[T]],
    default_order_by: ColumnElement | UnaryExpression | None = None,
) -> Select[tuple[T]]:
    """Append a default ORDER BY if the query doesn't have one yet."""
    if default_order_by is not None:
        # Check if the query already has ordering
        from sqlalchemy.sql import LABEL_STYLE_TABLENAME_PLUS_COL

        try:
            stmt = query.with_only_columns(1)
            if not stmt._order_by_cluster:
                query = query.order_by(default_order_by)
        except Exception:
            query = query.order_by(default_order_by)
    return query


def can_actor_manage_agency(actor: DataIsolationActor, target_agency_id: str) -> bool:
    """Check whether an actor can manage resources for a given agency.

    - super_admin can manage any agency.
    - agent can only manage their own agency.
    - agent_member can only manage their own agency (read-only for most ops).
    """
    if actor.is_super_admin:
        return True
    if actor.agency_id and actor.agency_id == target_agency_id:
        return True
    return False

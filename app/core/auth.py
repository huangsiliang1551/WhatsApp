from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from app.core.permission_defs import normalize_permission_code

ACTOR_ID_HEADER = "X-Actor-Id"
ACTOR_NAME_HEADER = "X-Actor-Name"
ACTOR_ROLE_HEADER = "X-Actor-Role"
ACTOR_ACCOUNT_IDS_HEADER = "X-Actor-Account-Ids"


class ActorRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    SUPPORT_AGENT = "support_agent"
    FINANCE = "finance"
    RISK_CONTROL = "risk_control"
    READONLY = "readonly"
    AGENT = "agent"
    AGENT_MEMBER = "agent_member"


class RequestActor(BaseModel):
    actor_id: str
    display_name: str | None = None
    role: ActorRole
    account_ids: list[str] = Field(default_factory=list)
    actor_type: str = "user"
    agency_id: str | None = None
    allow_impersonation: bool = False
    permission_role: str | None = None
    resolved_permissions: list[str] = Field(default_factory=list)
    permissions_source: str = "builtin"

    @property
    def is_super_admin(self) -> bool:
        return self.role == ActorRole.SUPER_ADMIN

    def has_permission(self, permission_code: str) -> bool:
        if self.is_super_admin:
            return True
        try:
            normalized = normalize_permission_code(permission_code)
        except ValueError:
            return False
        return normalized in self.resolved_permissions

    def require_permission(self, permission_code: str) -> None:
        try:
            normalized = normalize_permission_code(permission_code)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
        if self.has_permission(normalized):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Actor '{self.actor_id}' with role '{self.role.value}' "
                f"cannot perform '{normalized}'."
            ),
        )

    def can_access_account(self, account_id: str | None) -> bool:
        if account_id is None:
            return self.is_super_admin
        if self.is_super_admin:
            return True
        return account_id in self.account_ids

    def require_account_access(self, account_id: str | None) -> None:
        if self.can_access_account(account_id):
            return
        detail = (
            "This operation requires an explicit account scope."
            if account_id is None
            else f"Actor '{self.actor_id}' cannot access account '{account_id}'."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    def resolve_agent_id(self, payload_agent_id: str | None = None) -> str:
        normalized_payload = self.validate_agent_id(payload_agent_id)
        if normalized_payload is not None:
            return normalized_payload
        return self.actor_id

    def validate_agent_id(self, payload_agent_id: str | None = None) -> str | None:
        normalized_payload = (payload_agent_id or "").strip() or None
        if self.allow_impersonation:
            return normalized_payload
        if normalized_payload and normalized_payload != self.actor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Payload agent_id '{normalized_payload}' does not match "
                    f"request actor '{self.actor_id}'."
                ),
            )
        return normalized_payload


def parse_account_ids(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    values = [value.strip() for value in raw_value.split(",")]
    return [value for value in values if value and value != "*"]


def build_local_dev_actor() -> RequestActor:
    return RequestActor(
        actor_id="local-dev-admin",
        display_name="Local Development Admin",
        role=ActorRole.SUPER_ADMIN,
        account_ids=[],
        allow_impersonation=True,
    )


def get_effective_account_ids(actor: RequestActor) -> set[str] | None:
    """Get effective account_ids for data isolation."""
    if actor.is_super_admin:
        return None
    ids = set(actor.account_ids)
    return ids if ids else set()


T = TypeVar("T")


def filter_account_scoped_items(
    actor: RequestActor,
    items: list[T],
    account_getter: Callable[[T], str | None],
) -> list[T]:
    if actor.is_super_admin:
        return items
    return [
        item
        for item in items
        if (account_id := account_getter(item)) is not None and actor.can_access_account(account_id)
    ]

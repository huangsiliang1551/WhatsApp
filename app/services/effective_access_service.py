from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import RequestActor
from app.core.permission_defs import PERMISSION_DEFINITIONS
from app.db.models import DataScopeGrant, PermissionGrant, StaffTeamAssignment


ALL_PERMISSION_CODES = frozenset(defn["code"] for defn in PERMISSION_DEFINITIONS)


@dataclass(slots=True)
class EffectiveDataScope:
    all_access: bool = False
    agency_ids: set[str] = field(default_factory=set)
    account_ids: set[str] = field(default_factory=set)
    site_ids: set[str] = field(default_factory=set)
    team_ids: set[str] = field(default_factory=set)
    supervisor_ids: set[str] = field(default_factory=set)
    staff_ids: set[str] = field(default_factory=set)
    customer_ids: set[str] = field(default_factory=set)

    def has_restrictions(self) -> bool:
        return any(
            (
                self.agency_ids,
                self.account_ids,
                self.site_ids,
                self.team_ids,
                self.supervisor_ids,
                self.staff_ids,
                self.customer_ids,
            )
        )


class EffectiveAccessService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_effective_permissions(self, actor: RequestActor) -> set[str]:
        if actor.is_super_admin:
            return set(ALL_PERMISSION_CODES)

        self._session.flush()
        permissions = set(actor.resolved_permissions)
        now = datetime.now()
        grants = self._session.scalars(
            select(PermissionGrant).where(
                PermissionGrant.status == "active",
                PermissionGrant.revoked_at.is_(None),
                or_(PermissionGrant.expires_at.is_(None), PermissionGrant.expires_at > now),
                self._build_grantee_filter(actor),
            )
        ).all()
        for grant in grants:
            permissions.add(grant.permission_code)
        return permissions

    def get_delegatable_permissions(self, actor: RequestActor) -> set[str]:
        if actor.is_super_admin:
            return set(ALL_PERMISSION_CODES)

        self._session.flush()
        now = datetime.now()
        grants = self._session.scalars(
            select(PermissionGrant).where(
                PermissionGrant.status == "active",
                PermissionGrant.can_delegate.is_(True),
                PermissionGrant.revoked_at.is_(None),
                or_(PermissionGrant.expires_at.is_(None), PermissionGrant.expires_at > now),
                self._build_grantee_filter(actor),
            )
        ).all()
        return {grant.permission_code for grant in grants}

    def get_data_scope(self, actor: RequestActor) -> EffectiveDataScope:
        if actor.is_super_admin:
            return EffectiveDataScope(all_access=True)

        self._session.flush()
        scope = EffectiveDataScope()
        scope.account_ids.update(actor.account_ids)
        scope.staff_ids.add(actor.actor_id)

        team_assignments = self._session.scalars(
            select(StaffTeamAssignment).where(
                StaffTeamAssignment.staff_id == actor.actor_id,
                StaffTeamAssignment.status == "active",
            )
        ).all()
        for assignment in team_assignments:
            scope.team_ids.add(assignment.team_id)
            scope.supervisor_ids.add(assignment.supervisor_id)
            scope.agency_ids.add(assignment.agency_id)

        grants = self._session.scalars(
            select(DataScopeGrant).where(
                DataScopeGrant.status == "active",
                DataScopeGrant.revoked_at.is_(None),
                self._build_scope_subject_filter(actor),
            )
        ).all()
        for grant in grants:
            self._apply_scope_grant(scope, grant.scope_type, grant.scope_id)
        return scope

    def assert_can_delegate(self, actor: RequestActor, permission_codes: set[str]) -> None:
        if actor.is_super_admin:
            return
        delegatable = self.get_delegatable_permissions(actor)
        disallowed = sorted(permission_codes - delegatable)
        if disallowed:
            raise PermissionError(f"actor '{actor.actor_id}' cannot delegate permissions: {disallowed}")

    def _build_grantee_filter(self, actor: RequestActor):
        filters = [self._subject_clause("actor", actor.actor_id)]
        if actor.agency_id:
            filters.append(self._subject_clause("agency", actor.agency_id))
        for account_id in actor.account_ids:
            filters.append(self._subject_clause("account", account_id))
        return or_(*filters)

    def _build_scope_subject_filter(self, actor: RequestActor):
        filters = [self._scope_subject_clause("actor", actor.actor_id)]
        if actor.agency_id:
            filters.append(self._scope_subject_clause("agency", actor.agency_id))
        for account_id in actor.account_ids:
            filters.append(self._scope_subject_clause("account", account_id))
        return or_(*filters)

    @staticmethod
    def _subject_clause(subject_type: str, subject_id: str):
        return (
            (PermissionGrant.grantee_subject_type == subject_type)
            & (PermissionGrant.grantee_subject_id == subject_id)
        )

    @staticmethod
    def _scope_subject_clause(subject_type: str, subject_id: str):
        return (
            (DataScopeGrant.subject_type == subject_type)
            & (DataScopeGrant.subject_id == subject_id)
        )

    @staticmethod
    def _apply_scope_grant(scope: EffectiveDataScope, scope_type: str, scope_id: str | None) -> None:
        if scope_type == "all":
            scope.all_access = True
            return
        if scope_id is None:
            return
        mapping = {
            "agency": scope.agency_ids,
            "account": scope.account_ids,
            "site": scope.site_ids,
            "team": scope.team_ids,
            "supervisor": scope.supervisor_ids,
            "staff": scope.staff_ids,
            "customer": scope.customer_ids,
        }
        bucket = mapping.get(scope_type)
        if bucket is not None:
            bucket.add(scope_id)

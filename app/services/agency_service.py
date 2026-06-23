"""Agency service for multi-tenant management."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.permission_defs import PERMISSION_DEFINITIONS
from app.db.models import Agency, AgencyMember, AgencyPermissionGrant, Agent, RolePermission


KNOWN_PERMISSION_CODES = frozenset(permission["code"] for permission in PERMISSION_DEFINITIONS)
SUPER_ADMIN_ONLY_PERMISSION_CODES = frozenset(
    permission["code"]
    for permission in PERMISSION_DEFINITIONS
    if permission.get("super_admin_only")
)


@dataclass(frozen=True)
class AgencySummary:
    agency: Agency
    member_count: int
    role_count: int
    granted_permission_count: int


@dataclass(frozen=True)
class AgencyMemberSummary:
    member: AgencyMember
    username: str | None
    display_name: str | None
    status: str


def new_id() -> str:
    return str(uuid4())


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class AgencyService:
    """CRUD for agencies and their members."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_agencies(self) -> list[AgencySummary]:
        member_counts = (
            select(
                AgencyMember.agency_id.label("agency_id"),
                func.count(AgencyMember.id).label("member_count"),
            )
            .group_by(AgencyMember.agency_id)
            .subquery()
        )
        role_counts = (
            select(
                RolePermission.agency_id.label("agency_id"),
                func.count(RolePermission.id).label("role_count"),
            )
            .where(
                RolePermission.agency_id.is_not(None),
                RolePermission.is_template.is_(False),
            )
            .group_by(RolePermission.agency_id)
            .subquery()
        )
        stmt = (
            select(
                Agency,
                func.coalesce(member_counts.c.member_count, 0),
                func.coalesce(role_counts.c.role_count, 0),
                AgencyPermissionGrant.permissions,
            )
            .outerjoin(member_counts, member_counts.c.agency_id == Agency.id)
            .outerjoin(role_counts, role_counts.c.agency_id == Agency.id)
            .outerjoin(AgencyPermissionGrant, AgencyPermissionGrant.agency_id == Agency.id)
            .order_by(Agency.created_at.desc())
        )
        return [
            AgencySummary(
                agency=agency,
                member_count=int(member_count),
                role_count=int(role_count),
                granted_permission_count=len(granted_permissions or []),
            )
            for agency, member_count, role_count, granted_permissions in self.session.execute(stmt).all()
        ]

    def get_agency(self, agency_id: str) -> Agency:
        agency = self.session.get(Agency, agency_id)
        if agency is None:
            raise LookupError(f"Agency not found: {agency_id}")
        return agency

    def get_agency_by_username(self, username: str) -> Agency | None:
        """Look up an agency by username."""
        stmt = select(Agency).where(Agency.username == username)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_permission_grants(self, agency_id: str) -> list[str]:
        self.get_agency(agency_id)
        grant = self.session.execute(
            select(AgencyPermissionGrant).where(AgencyPermissionGrant.agency_id == agency_id)
        ).scalar_one_or_none()
        if grant is None:
            return []
        return self._normalize_permission_codes(
            list(grant.permissions or []),
            context="agency granted permissions",
        )

    def update_permission_grants(
        self,
        agency_id: str,
        permissions: list[str],
        *,
        actor_id: str,
    ) -> list[str]:
        self.get_agency(agency_id)
        normalized_permissions = self._normalize_permission_codes(
            permissions,
            context="agency granted permissions",
        )

        grant = self.session.execute(
            select(AgencyPermissionGrant).where(AgencyPermissionGrant.agency_id == agency_id)
        ).scalar_one_or_none()
        if grant is None:
            grant = AgencyPermissionGrant(
                id=new_id(),
                agency_id=agency_id,
                permissions=normalized_permissions,
                created_by=actor_id,
            )
            self.session.add(grant)
        else:
            grant.permissions = normalized_permissions
            if grant.created_by is None:
                grant.created_by = actor_id

        self.session.flush()
        return normalized_permissions

    def create_agency(
        self,
        name: str,
        username: str,
        password: str,
        brand_name: str | None = None,
        logo_url: str | None = None,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        contact_email: str | None = None,
    ) -> Agency:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        agency = Agency(
            id=new_id(),
            name=name,
            username=username,
            password_hash=hash_password(password),
            brand_name=brand_name,
            logo_url=logo_url,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
            status="active",
        )
        self.session.add(agency)
        self.session.flush()
        return agency

    def update_agency(self, agency_id: str, **kwargs) -> Agency:
        agency = self.get_agency(agency_id)
        for key, value in kwargs.items():
            if hasattr(agency, key) and value is not None:
                setattr(agency, key, value)
        agency.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return agency

    def delete_agency(self, agency_id: str) -> None:
        agency = self.get_agency(agency_id)
        agency.status = "archived"
        self.session.flush()

    def reset_password(self, agency_id: str, new_password: str) -> None:
        """Reset an agency's password (super admin action)."""
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        agency = self.get_agency(agency_id)
        agency.password_hash = hash_password(new_password)
        self.session.flush()

    # --- Members ---

    def list_members(self, agency_id: str) -> list[AgencyMemberSummary]:
        stmt = (
            select(
                AgencyMember,
                Agent.agent_key,
                Agent.display_name,
                Agent.status,
                Agent.is_active,
            )
            .outerjoin(Agent, Agent.id == AgencyMember.user_id)
            .where(AgencyMember.agency_id == agency_id)
        )
        return [
            AgencyMemberSummary(
                member=member,
                username=username,
                display_name=display_name,
                status="inactive" if is_active is False else (status or "offline"),
            )
            for member, username, display_name, status, is_active in self.session.execute(stmt).all()
        ]

    def ensure_agency_role_exists(self, agency_id: str, role: str) -> None:
        configured_role = self.session.execute(
            select(RolePermission.id).where(
                RolePermission.agency_id == agency_id,
                RolePermission.role_name == role,
                RolePermission.is_template.is_(False),
            )
        ).scalar_one_or_none()
        if configured_role is not None:
            return
        raise ValueError(f"Role '{role}' is not configured for agency '{agency_id}'.")

    def add_member(self, agency_id: str, username: str, password: str, role: str) -> AgencyMember:
        self.ensure_agency_role_exists(agency_id, role)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 1. Check username uniqueness
        existing = self.session.execute(
            text("SELECT 1 FROM admin_users WHERE username = :u"),
            {"u": username},
        ).first()
        if existing:
            raise ValueError(f"Username {username} is already taken")

        # 2. Create Agent record
        agent = Agent(
            id=new_id(),
            agent_key=username,
            display_name=username,
            user_type="agent_member",
            agency_id=agency_id,
            is_active=True,
        )
        self.session.add(agent)
        self.session.flush()

        # 3. Create AgencyMember record
        member = AgencyMember(
            id=new_id(),
            agency_id=agency_id,
            user_id=agent.id,
            role=role,
        )
        self.session.add(member)
        self.session.flush()

        # 4. Insert into admin_users for workspace-auth login
        self.session.execute(
            text("""
                INSERT INTO admin_users (id, username, password_hash, role, is_active, created_at, updated_at)
                VALUES (:id, :username, :pw, :role, true, :created_at, :updated_at)
            """),
            {
                "id": new_id(),
                "username": username,
                "pw": hash_password(password),
                "role": role,
                "created_at": now,
                "updated_at": now,
            },
        )
        self.session.flush()
        return member

    def update_member_role(self, member_id: str, role: str) -> AgencyMember:
        member = self.session.get(AgencyMember, member_id)
        if member is None:
            raise LookupError(f"AgencyMember not found: {member_id}")
        self.ensure_agency_role_exists(member.agency_id, role)
        member.role = role
        self.session.flush()
        return member

    def update_member_password(self, member_id: str, new_password: str) -> None:
        """Update member's password in admin_users table."""
        member = self.session.get(AgencyMember, member_id)
        if member is None:
            raise LookupError(f"AgencyMember not found: {member_id}")

        agent = self.session.get(Agent, member.user_id)
        if agent is None:
            raise LookupError(f"Agent not found: {member.user_id}")

        self.session.execute(
            text("UPDATE admin_users SET password_hash = :pw, updated_at = :updated_at WHERE username = :username"),
            {
                "pw": hash_password(new_password),
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "username": agent.agent_key,
            },
        )
        self.session.flush()

    def remove_member(self, member_id: str) -> None:
        member = self.session.get(AgencyMember, member_id)
        if member is None:
            raise LookupError(f"AgencyMember not found: {member_id}")
        self.session.delete(member)
        self.session.flush()

    def _normalize_permission_codes(self, permissions: list[str], *, context: str) -> list[str]:
        normalized: list[str] = []
        unknown_permissions: set[str] = set()
        forbidden_permissions: set[str] = set()
        seen: set[str] = set()

        for raw_permission in permissions:
            code = raw_permission.strip()
            if not code:
                continue
            if code not in KNOWN_PERMISSION_CODES:
                unknown_permissions.add(code)
                continue
            if code in SUPER_ADMIN_ONLY_PERMISSION_CODES:
                forbidden_permissions.add(code)
                continue
            if code in seen:
                continue
            seen.add(code)
            normalized.append(code)

        if unknown_permissions:
            raise ValueError(
                {
                    "message": f"Unknown permission codes in {context}.",
                    "unknown_permissions": sorted(unknown_permissions),
                }
            )
        if forbidden_permissions:
            raise ValueError(
                {
                    "message": "Super-admin-only permissions cannot be granted to agencies.",
                    "forbidden_permissions": sorted(forbidden_permissions),
                }
            )

        normalized.sort()
        return normalized

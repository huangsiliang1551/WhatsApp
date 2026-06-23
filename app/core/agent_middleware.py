"""Data isolation middleware for multi-tenant filtering.

Based on user_type (super_admin / agent / agent_member), filters querysets
so that each user type only sees data they are authorized to access.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, AgencyMember, H5Site


def get_user_type(session: Session, user_id: str) -> str:
    """Get the user_type for a given user."""
    agent = session.get(Agent, user_id)
    if agent is None:
        return "super_admin"  # fallback for header-based auth without DB record
    return agent.user_type or "super_admin"


def get_agent_agency_id(session: Session, user_id: str) -> str | None:
    """Get the agency_id for an agent user."""
    agent = session.get(Agent, user_id)
    if agent:
        return agent.agency_id
    return None


def get_member_agency_id(session: Session, user_id: str) -> str | None:
    """Get the agency_id for an agent_member user."""
    stmt = select(AgencyMember).where(AgencyMember.user_id == user_id)
    member = session.execute(stmt).scalar_one_or_none()
    if member:
        return member.agency_id
    return None


def get_member_role(session: Session, user_id: str) -> str | None:
    """Get the role for an agent_member user."""
    stmt = select(AgencyMember).where(AgencyMember.user_id == user_id)
    member = session.execute(stmt).scalar_one_or_none()
    if member:
        return member.role
    return None


class AgentDataIsolationMiddleware:
    """Middleware to filter data based on user_type.

    Usage:
        isolation = AgentDataIsolationMiddleware(session, user_id)
        sites = isolation.filter_sites(query)
    """

    def __init__(self, session: Session, user_id: str) -> None:
        self.session = session
        self.user_id = user_id
        self.user_type = get_user_type(session, user_id)
        self.agency_id: str | None = None

        if self.user_type == "agent":
            self.agency_id = get_agent_agency_id(session, user_id)
        elif self.user_type == "agent_member":
            self.agency_id = get_member_agency_id(session, user_id)
            self.role = get_member_role(session, user_id)
        else:
            self.role = None

    @property
    def is_super_admin(self) -> bool:
        return self.user_type == "super_admin"

    @property
    def is_agent(self) -> bool:
        return self.user_type == "agent"

    @property
    def is_agent_member(self) -> bool:
        return self.user_type == "agent_member"

    def filter_sites(self, stmt=None) -> list[H5Site]:
        """Filter sites based on user type."""
        query = select(H5Site) if stmt is None else stmt

        if self.is_super_admin:
            pass  # all sites visible
        elif self.is_agent and self.agency_id:
            query = query.where(H5Site.agency_id == self.agency_id)
        elif self.is_agent_member and self.agency_id:
            query = query.where(H5Site.agency_id == self.agency_id)
        else:
            query = query.where(H5Site.id.is_(None))  # no access

        query = query.order_by(H5Site.created_at.desc())
        return list(self.session.execute(query).scalars().all())

    def check_site_access(self, site_id: str) -> bool:
        """Check if user has access to a specific site."""
        if self.is_super_admin:
            return True

        site = self.session.get(H5Site, site_id)
        if site is None:
            return False

        if self.agency_id and site.agency_id == self.agency_id:
            return True

        return False

    def check_data_access(self, data_type: str) -> bool:
        """Check if user has access to a specific data type.

        For agent_member, this provides role-based access control.
        """
        if self.is_super_admin or self.is_agent:
            return True

        if self.is_agent_member:
            role = getattr(self, "role", None)
            if role == "manager":
                return True
            if role == "finance" and data_type in ("wallet", "withdrawal", "billing", "revenue"):
                return True
            if role == "support" and data_type in ("conversation", "ticket", "user"):
                return True
            return False

        return False

"""Agent authentication and authorization service for multi-tenant."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, Agency, AgencyMember, H5Site


class AgentAuthService:
    """Authentication and permission checks for multi-tenant agents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_agent_by_user(self, user_id: str) -> Agent | None:
        return self.session.get(Agent, user_id)

    def get_agency_by_user(self, user_id: str) -> Agency | None:
        """Find the agency that an agent/member belongs to."""
        # Check if user is an agency admin directly
        agent = self.session.get(Agent, user_id)
        if agent and agent.agency_id:
            return self.session.get(Agency, agent.agency_id)
        # Check if user is a member of some agency
        stmt = select(AgencyMember).where(AgencyMember.user_id == user_id)
        member = self.session.execute(stmt).scalar_one_or_none()
        if member:
            return self.session.get(Agency, member.agency_id)
        return None

    def get_accessible_sites(self, user_id: str) -> list[H5Site]:
        """Get sites accessible by the user based on their agency."""
        agent = self.session.get(Agent, user_id)
        if agent is None:
            return []
        if agent.user_type == "super_admin":
            stmt = select(H5Site).order_by(H5Site.created_at.desc())
            return list(self.session.execute(stmt).scalars().all())
        if agent.user_type == "agent" or agent.user_type == "agent_member":
            agency_id = agent.agency_id
            if not agency_id:
                return []
            stmt = (
                select(H5Site)
                .where(H5Site.agency_id == agency_id)
                .order_by(H5Site.created_at.desc())
            )
            return list(self.session.execute(stmt).scalars().all())
        return []

    def check_permission(self, user_id: str, permission_type: str) -> bool:
        """Check if a user has a given permission type.

        Basic implementation - can be extended for fine-grained control.
        """
        agent = self.session.get(Agent, user_id)
        if agent is None:
            return False
        if agent.user_type == "super_admin":
            return True
        if agent.user_type == "agent":
            # Agency admins have full access to their domain
            return True
        if agent.user_type == "agent_member":
            # Members have role-based access
            stmt = select(AgencyMember).where(AgencyMember.user_id == user_id)
            member = self.session.execute(stmt).scalar_one_or_none()
            if member is None:
                return False
            if member.role == "manager":
                return True
            if member.role == "finance" and permission_type in (
                "wallet", "withdrawal", "billing", "revenue",
            ):
                return True
            if member.role == "support" and permission_type in (
                "conversation", "ticket", "user",
            ):
                return True
            return False
        return False

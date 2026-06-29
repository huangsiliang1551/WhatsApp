from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIHandoverPolicy, ConversationAssignment, HandoverQueue, utc_now


class ConversationHandoverService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_assignment(self, conversation_id: str) -> ConversationAssignment | None:
        return self._session.scalar(
            select(ConversationAssignment).where(
                ConversationAssignment.conversation_id == conversation_id,
                ConversationAssignment.status == "active",
            )
        )

    def list_active_queues(self, agency_id: str) -> list[HandoverQueue]:
        return list(
            self._session.scalars(
                select(HandoverQueue).where(
                    HandoverQueue.agency_id == agency_id,
                    HandoverQueue.status == "active",
                )
            ).all()
        )

    def get_policy(self, agency_id: str, *, site_id: str | None = None) -> AIHandoverPolicy | None:
        if site_id is not None:
            site_policy = self._session.scalar(
                select(AIHandoverPolicy).where(
                    AIHandoverPolicy.agency_id == agency_id,
                    AIHandoverPolicy.site_id == site_id,
                )
            )
            if site_policy is not None:
                return site_policy
        return self._session.scalar(
            select(AIHandoverPolicy).where(
                AIHandoverPolicy.agency_id == agency_id,
                AIHandoverPolicy.site_id.is_(None),
            )
        )

    def assign_conversation(
        self,
        *,
        conversation_id: str,
        customer_id: str,
        agency_id: str,
        assigned_staff_id: str | None,
        team_id: str | None,
        supervisor_id: str | None,
        assignment_type: str,
        assigned_by: str | None,
        reason: str | None,
        is_temporary: bool,
        assigned_queue_id: str | None = None,
    ) -> ConversationAssignment:
        active = self.get_active_assignment(conversation_id)
        if active is not None:
            active.status = "ended"
            active.ended_at = utc_now()
            self._session.add(active)

        assignment = ConversationAssignment(
            conversation_id=conversation_id,
            customer_id=customer_id,
            agency_id=agency_id,
            team_id=team_id,
            supervisor_id=supervisor_id,
            assigned_staff_id=assigned_staff_id,
            assigned_queue_id=assigned_queue_id,
            assignment_type=assignment_type,
            is_temporary=is_temporary,
            status="active",
            assigned_by=assigned_by,
            reason=reason,
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment

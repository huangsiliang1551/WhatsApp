from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CustomerOwnershipAssignment, utc_now


class CustomerOwnershipService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_assignment(self, customer_id: str) -> CustomerOwnershipAssignment | None:
        return self._session.scalar(
            select(CustomerOwnershipAssignment).where(
                CustomerOwnershipAssignment.customer_id == customer_id,
                CustomerOwnershipAssignment.status == "active",
            )
        )

    def transfer_customer_ownership(
        self,
        *,
        customer_id: str,
        agency_id: str,
        account_id: str | None,
        site_id: str | None,
        new_owner_staff_id: str | None,
        new_supervisor_id: str | None,
        new_team_id: str | None,
        assigned_by: str,
        reason: str | None,
        assignment_type: str = "permanent_transfer",
    ) -> CustomerOwnershipAssignment:
        active = self.get_active_assignment(customer_id)
        if active is not None:
            active.status = "ended"
            active.ended_at = utc_now()
            self._session.add(active)

        assignment = CustomerOwnershipAssignment(
            customer_id=customer_id,
            agency_id=agency_id,
            account_id=account_id,
            site_id=site_id,
            owner_staff_id=new_owner_staff_id,
            supervisor_id=new_supervisor_id,
            team_id=new_team_id,
            assignment_type=assignment_type,
            status="active",
            assigned_by=assigned_by,
            reason=reason,
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SiteWhatsAppPhonePool, UserWhatsAppServiceAssignment
from app.services.site_whatsapp_phone_pool_service import SiteWhatsAppPhonePoolService


class WhatsAppPhoneSelectionError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WhatsAppPhoneSelectionService:
    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._pool_service = SiteWhatsAppPhonePoolService(session=session)

    def select_phone(
        self,
        *,
        account_id: str,
        site_id: str,
        user_id: str | None,
        wa_id: str | None,
        prefer_existing_assignment: bool,
    ) -> SiteWhatsAppPhonePool:
        if prefer_existing_assignment and user_id is not None:
            assigned = self._find_existing_assignment(user_id=user_id, wa_id=wa_id)
            if assigned is not None:
                pool = self._pool_service.get_pool_by_phone_number_id(
                    phone_number_id=assigned.assigned_phone_number_id,
                    active_only=True,
                )
                if pool is not None and self._eligible_for_existing_user(pool):
                    return pool

        pools = self._pool_service.list_site_pools(
            account_id=account_id,
            site_id=site_id,
            active_only=True,
        )
        candidates = [
            pool for pool in pools
            if self._eligible(pool, existing_user=user_id is not None)
        ]
        if not candidates:
            raise WhatsAppPhoneSelectionError(
                code="no_available_phone",
                message="No WhatsApp phone is available for this site.",
            )
        candidates.sort(key=self._sort_key)
        return candidates[0]

    def _find_existing_assignment(
        self,
        *,
        user_id: str,
        wa_id: str | None,
    ) -> UserWhatsAppServiceAssignment | None:
        stmt = select(UserWhatsAppServiceAssignment).where(
            UserWhatsAppServiceAssignment.user_id == user_id,
            UserWhatsAppServiceAssignment.status == "active",
        )
        if wa_id:
            stmt = stmt.where(UserWhatsAppServiceAssignment.wa_id == wa_id)
        return self._session.scalars(
            stmt.order_by(UserWhatsAppServiceAssignment.created_at.asc())
        ).first()

    def _eligible(self, pool: SiteWhatsAppPhonePool, *, existing_user: bool) -> bool:
        if existing_user:
            return self._eligible_for_existing_user(pool)
        if pool.allow_new_users is False:
            return False
        if pool.only_existing_users:
            return False
        if pool.status == "restricted" and pool.restricted_stop_allocation:
            return False
        if pool.quality_rating_snapshot in {"LOW", "UNKNOWN"} and pool.low_quality_stop_new_users:
            return False
        return self._runtime_ready(pool)

    def _eligible_for_existing_user(self, pool: SiteWhatsAppPhonePool) -> bool:
        if pool.allow_existing_users is False:
            return False
        return self._runtime_ready(pool)

    @staticmethod
    def _runtime_ready(pool: SiteWhatsAppPhonePool) -> bool:
        return bool(pool.ready_for_webhook_delivery and pool.ready_for_outbound_messages)

    @staticmethod
    def _sort_key(pool: SiteWhatsAppPhonePool) -> tuple[int, int, int, int, int, str]:
        status_score = 3 if pool.status == "active" else 2 if pool.status == "cooling_down" else 1
        readiness_score = int(pool.ready_for_webhook_delivery) + int(pool.ready_for_outbound_messages)
        return (
            -status_score,
            -readiness_score,
            -int(pool.weight or 0),
            int(pool.priority or 0),
            int(pool.active_conversation_count or 0),
            pool.phone_number_id,
        )

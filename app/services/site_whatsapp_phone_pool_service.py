from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Site, SiteWhatsAppPhonePool


ACTIVE_POOL_STATUSES = {"active", "restricted", "cooling_down"}


class SiteWhatsAppPhonePoolService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def get_site_by_id(self, *, site_id: str) -> H5Site | None:
        return self._session.get(H5Site, site_id)

    def get_site_by_key(self, *, site_key: str) -> H5Site | None:
        return self._session.scalars(
            select(H5Site).where(H5Site.site_key == site_key)
        ).first()

    def list_site_pools(
        self,
        *,
        account_id: str,
        site_id: str,
        active_only: bool = True,
    ) -> list[SiteWhatsAppPhonePool]:
        stmt = select(SiteWhatsAppPhonePool).where(
            SiteWhatsAppPhonePool.account_id == account_id,
            SiteWhatsAppPhonePool.site_id == site_id,
        )
        if active_only:
            stmt = stmt.where(SiteWhatsAppPhonePool.status.in_(ACTIVE_POOL_STATUSES))
        return list(
            self._session.scalars(
                stmt.order_by(
                    SiteWhatsAppPhonePool.priority.asc(),
                    SiteWhatsAppPhonePool.weight.desc(),
                    SiteWhatsAppPhonePool.created_at.asc(),
                )
            ).all()
        )

    def get_pool_by_phone_number_id(
        self,
        *,
        phone_number_id: str,
        active_only: bool = True,
    ) -> SiteWhatsAppPhonePool | None:
        stmt = select(SiteWhatsAppPhonePool).where(
            SiteWhatsAppPhonePool.phone_number_id == phone_number_id,
        )
        if active_only:
            stmt = stmt.where(SiteWhatsAppPhonePool.status.in_(ACTIVE_POOL_STATUSES))
        return self._session.scalars(stmt.order_by(SiteWhatsAppPhonePool.created_at.asc())).first()

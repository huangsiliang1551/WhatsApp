from __future__ import annotations

import time
from uuid import uuid4

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import H5Site, H5SiteConfig, UptimeCheck


class UptimeService:
    """Check H5 site availability and record results."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def check_site(self, site: H5Site, config: H5SiteConfig) -> UptimeCheck:
        """Check if a site is online by HTTP GET."""
        domain = config.domain or site.domain
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://{domain}")
            elapsed = int((time.time() - start) * 1000)
            status = "up" if resp.status_code == 200 else "down"
            check = UptimeCheck(
                id=str(uuid4()),
                site_id=site.id,
                status=status,
                response_time_ms=elapsed,
                status_code=resp.status_code,
            )
        except Exception as e:
            check = UptimeCheck(
                id=str(uuid4()),
                site_id=site.id,
                status="timeout",
                error_message=str(e),
            )

        self._session.add(check)
        self._session.commit()
        return check

    def get_latest_checks(self, site_id: str, limit: int = 20) -> list[UptimeCheck]:
        return list(self._session.scalars(
            select(UptimeCheck)
            .where(UptimeCheck.site_id == site_id)
            .order_by(UptimeCheck.created_at.desc())
            .limit(limit)
        ).all())

    def get_site_summary(self, site_id: str) -> dict:
        """Get uptime summary for a site (latest status, total checks, up count)."""
        latest = self._session.scalar(
            select(UptimeCheck)
            .where(UptimeCheck.site_id == site_id)
            .order_by(UptimeCheck.created_at.desc())
        )
        total = self._session.scalar(
            select(func.count(UptimeCheck.id))
            .where(UptimeCheck.site_id == site_id)
        ) or 0
        up_count = self._session.scalar(
            select(func.count(UptimeCheck.id))
            .where(UptimeCheck.site_id == site_id, UptimeCheck.status == "up")
        ) or 0
        return {
            "site_id": site_id,
            "latest_status": latest.status if latest else None,
            "latest_response_time_ms": latest.response_time_ms if latest else None,
            "latest_checked_at": latest.created_at.isoformat() if latest else None,
            "total_checks": total,
            "up_count": up_count,
            "uptime_pct": round(up_count / total * 100, 2) if total > 0 else 0,
        }

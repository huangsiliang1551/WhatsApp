"""Health check service — IV-BE-008.

Executes 5 system health checks (db, redis, api, sites, ssl)
and persists results to the health_checks table.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from datetime import datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db.models import HealthCheck, utc_now

logger = structlog.get_logger()


class HealthCheckService:
    """Execute system health checks."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings

    # ── Run all checks ───────────────────────────────────────────────────────────

    async def check_all(self) -> list[HealthCheck]:
        """Execute all 5 checks and return results."""
        results: list[HealthCheck] = []
        results.append(await self._check_db())
        results.append(await self._check_redis())
        results.append(await self._check_api())
        results.extend(await self._check_sites())
        results.append(await self._check_ssl())

        for r in results:
            self._session.add(r)
        self._session.flush()

        # Alert on errors
        for r in results:
            if r.status == "error":
                try:
                    from app.services.email_service import EmailService

                    email_svc = EmailService(self._session)
                    await email_svc.send_health_alert(
                        check_type=r.check_type,
                        target=r.target or "",
                        status=r.status,
                        details=r.details,
                        checked_at=r.checked_at.isoformat() if r.checked_at else None,
                    )
                except Exception as exc:
                    logger.warning("health_alert_email_failed", error=str(exc))

        logger.info(
            "health_check_all_completed",
            total=len(results),
            errors=sum(1 for r in results if r.status == "error"),
        )
        return results

    def get_latest_results(self) -> list[HealthCheck]:
        """Return the latest health check results per type."""
        # Get max checked_at for each check_type
        subq = (
            select(
                HealthCheck.check_type,
                func_max(HealthCheck.checked_at).label("max_checked"),
            )
            .group_by(HealthCheck.check_type)
            .subquery()
        )
        # Use raw approach instead
        types = ["db", "redis", "api", "site", "ssl"]
        results = []
        for t in types:
            r = self._session.scalar(
                select(HealthCheck)
                .where(HealthCheck.check_type == t)
                .order_by(HealthCheck.checked_at.desc())
                .limit(1)
            )
            if r:
                results.append(r)
        return results

    def get_summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for dashboard display."""
        latest = self.get_latest_results()
        status_map: dict[str, Any] = {}
        for r in latest:
            status_map[r.check_type] = {
                "status": r.status,
                "response_time_ms": r.response_time_ms,
                "checked_at": r.checked_at.isoformat() if r.checked_at else None,
                "details": r.details,
            }
        return {
            "overall": "healthy" if all(
                s.get("status") == "healthy" for s in status_map.values()
            ) else "degraded",
            "checks": status_map,
        }

    # ── Individual checks ────────────────────────────────────────────────────────

    async def _check_db(self) -> HealthCheck:
        start = time.monotonic()
        try:
            self._session.execute(text("SELECT 1"))
            elapsed = int((time.monotonic() - start) * 1000)
            return HealthCheck(
                check_type="db",
                target="PostgreSQL",
                status="healthy",
                response_time_ms=elapsed,
            )
        except Exception as exc:
            return HealthCheck(
                check_type="db",
                target="PostgreSQL",
                status="error",
                details=str(exc),
            )

    async def _check_redis(self) -> HealthCheck:
        start = time.monotonic()
        try:
            import redis as sync_redis

            redis_url = "redis://localhost:6379/0"
            if self._settings:
                redis_url = self._settings.redis_url
            client = sync_redis.from_url(redis_url, socket_timeout=5)
            client.ping()
            client.close()
            elapsed = int((time.monotonic() - start) * 1000)
            return HealthCheck(
                check_type="redis",
                target="Redis",
                status="healthy",
                response_time_ms=elapsed,
            )
        except Exception as exc:
            return HealthCheck(
                check_type="redis",
                target="Redis",
                status="error",
                details=str(exc),
            )

    async def _check_api(self) -> HealthCheck:
        start = time.monotonic()
        try:
            base_url = "http://localhost:8000"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{base_url}/health")
                elapsed = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    return HealthCheck(
                        check_type="api",
                        target="API Self",
                        status="healthy",
                        response_time_ms=elapsed,
                    )
                return HealthCheck(
                    check_type="api",
                    target="API Self",
                    status="warning",
                    response_time_ms=elapsed,
                    details=f"HTTP {resp.status_code}",
                )
        except Exception as exc:
            return HealthCheck(
                check_type="api",
                target="API Self",
                status="error",
                details=str(exc),
            )

    async def _check_sites(self) -> list[HealthCheck]:
        """Check all active H5 sites."""
        from app.db.models import H5Site

        sites = self._session.scalars(
            select(H5Site).where(H5Site.status == "active")
        ).all()
        results: list[HealthCheck] = []
        for site in sites:
            start = time.monotonic()
            try:
                domain = site.domain or f"{site.site_key}.example.com"
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"https://{domain}")
                elapsed = int((time.monotonic() - start) * 1000)
                if resp.status_code < 500:
                    results.append(HealthCheck(
                        check_type="site",
                        target=f"H5:{site.site_key}",
                        status="healthy",
                        response_time_ms=elapsed,
                    ))
                else:
                    results.append(HealthCheck(
                        check_type="site",
                        target=f"H5:{site.site_key}",
                        status="warning",
                        response_time_ms=elapsed,
                        details=f"HTTP {resp.status_code}",
                    ))
            except Exception as exc:
                results.append(HealthCheck(
                    check_type="site",
                    target=f"H5:{site.site_key}",
                    status="error",
                    details=str(exc),
                ))
        if not results:
            results.append(HealthCheck(
                check_type="site",
                target="H5 Sites",
                status="healthy",
                details="No active sites configured",
            ))
        return results

    async def _check_ssl(self) -> HealthCheck:
        """Check SSL certificate expiry for configured domains."""
        start = time.monotonic()
        try:
            from app.db.models import H5Site

            sites = self._session.scalars(
                select(H5Site).where(H5Site.status == "active", H5Site.domain.isnot(None))
            ).all()
            if not sites:
                return HealthCheck(
                    check_type="ssl",
                    target="SSL Certificates",
                    status="healthy",
                    response_time_ms=0,
                    details="No domains to check",
                )

            # Check first domain
            domain = sites[0].domain
            ctx = ssl.create_default_context()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(domain, 443, ssl=ctx),
                timeout=10,
            )
            cert = writer.get_extra_info("ssl_object").getpeercert()
            writer.close()

            if cert and "notAfter" in cert:
                from datetime import datetime as dt

                expiry = dt.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                remaining = (expiry - dt.now()).days
                elapsed = int((time.monotonic() - start) * 1000)

                if remaining > 30:
                    return HealthCheck(
                        check_type="ssl",
                        target=f"SSL:{domain}",
                        status="healthy",
                        response_time_ms=elapsed,
                        details=f"证书剩余 {remaining} 天",
                    )
                elif remaining > 7:
                    return HealthCheck(
                        check_type="ssl",
                        target=f"SSL:{domain}",
                        status="warning",
                        response_time_ms=elapsed,
                        details=f"证书剩余 {remaining} 天",
                    )
                else:
                    return HealthCheck(
                        check_type="ssl",
                        target=f"SSL:{domain}",
                        status="error",
                        response_time_ms=elapsed,
                        details=f"证书即将过期，剩余 {remaining} 天",
                    )

            return HealthCheck(
                check_type="ssl",
                target="SSL Certificates",
                status="healthy",
                response_time_ms=0,
            )
        except Exception as exc:
            return HealthCheck(
                check_type="ssl",
                target="SSL Certificates",
                status="error",
                details=str(exc),
            )


def func_max(col):
    """Helper to work around import."""
    from sqlalchemy import func as sa_func
    return sa_func.max(col)

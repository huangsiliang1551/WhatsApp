"""Performance monitoring API routes.

Provides backend server performance metrics (CPU, memory, disk, DB/Redis connections)
and frontend server health data from uptime_checks.
"""

import os
import platform

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import H5Site, UptimeCheck

router = APIRouter(prefix="/api/performance", tags=["performance"])


def _get_cpu_percent() -> float:
    """Get CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return 0.0


def _get_memory_mb() -> float:
    """Get memory usage in MB."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return round(mem.used / 1024 / 1024, 1)
    except ImportError:
        return 0.0


def _get_disk_usage_percent() -> float:
    """Get disk usage percentage."""
    try:
        import psutil
        return psutil.disk_usage("/").percent
    except ImportError:
        return 0.0


@router.get("/backend")
async def backend_performance(
    _actor: RequestActor = Depends(require_permission("monitoring.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Get backend server performance metrics."""
    # Database connection count
    db_connections = 0
    try:
        result = session.execute(
            select(func.count()).select_from(
                select(__import__("sqlalchemy").text("1")).select_from(
                    __import__("sqlalchemy").text("pg_stat_activity")
                ).subquery()
            )
        )
        db_connections = result.scalar() or 0
    except Exception:
        db_connections = -1  # Unable to query

    # Redis connection check (approximate via health)
    redis_connections = 0
    try:
        import redis as redis_lib
        from app.core.settings import get_settings
        settings = get_settings()
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
        info = r.info("clients")
        redis_connections = info.get("connected_clients", 0)
        r.close()
    except Exception:
        redis_connections = -1

    # CPU architecture
    arch = platform.machine()

    return {
        "platform": platform.system(),
        "architecture": arch,
        "python_version": platform.python_version(),
        "cpu_percent": _get_cpu_percent(),
        "memory_mb": _get_memory_mb(),
        "disk_percent": _get_disk_usage_percent(),
        "db_connections": db_connections,
        "redis_connections": redis_connections,
    }


@router.get("/frontend/{site_key}")
async def frontend_performance(
    site_key: str,
    _actor: RequestActor = Depends(require_permission("monitoring.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Get frontend server performance metrics for a specific site."""
    site = session.execute(
        select(H5Site).where(H5Site.site_key == site_key)
    ).scalar_one_or_none()

    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")

    # Get latest uptime checks
    stats = session.execute(
        select(
            func.avg(UptimeCheck.response_time_ms),
            func.count(),
            func.sum(func.cast(UptimeCheck.status == "up", __import__("sqlalchemy").Integer)),
        ).where(UptimeCheck.site_id == site.id)
    ).one()

    avg_response_time = round(float(stats[0] or 0), 1) if stats[0] else 0
    total_checks = stats[1] or 0
    up_checks = stats[2] or 0
    uptime_percent = round((up_checks / total_checks * 100) if total_checks > 0 else 0, 1)

    return {
        "site_id": site.id,
        "site_key": site.site_key,
        "domain": site.domain,
        "avg_response_time_ms": avg_response_time,
        "uptime_percent": uptime_percent,
        "total_checks": total_checks,
        "status": "up" if uptime_percent > 95 else "degraded" if uptime_percent > 80 else "down",
    }


@router.get("/summary")
async def performance_summary(
    _actor: RequestActor = Depends(require_permission("monitoring.view")),
    session: Session = Depends(get_db_session),
) -> dict:
    """Get aggregated performance summary for dashboard."""
    backend = await backend_performance(_actor=_actor, session=session)

    # Count sites by status
    all_sites = session.execute(select(H5Site)).scalars().all()
    site_count = len(all_sites)

    return {
        "backend": backend,
        "sites": {
            "total": site_count,
        },
    }

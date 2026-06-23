import asyncio
import time

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.core.settings import get_settings
from app.db.db_health import get_db_health, is_db_healthy
from app.db.session import get_engine

router = APIRouter()


@router.get(
    "/health",
    summary="Health check",
    description="Returns service health status with optional deep DB check.",
    tags=["monitoring"],
)
async def health(deep: bool = Query(False)) -> dict[str, object]:
    settings = get_settings()
    result: dict[str, object] = {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "db_circuit_status": get_db_health(),
    }

    if deep:
        engine = get_engine()
        start = time.monotonic()
        try:
            def _check_db() -> None:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

            await asyncio.get_event_loop().run_in_executor(None, _check_db)
            elapsed = (time.monotonic() - start) * 1000
            pool = engine.pool
            result["db_connected"] = True
            result["db_pool_checked_out"] = pool.checkedout()
            result["db_pool_checked_in"] = pool.checkedin()
            result["db_pool_total"] = pool.total()
            result["db_pool_size"] = pool.size()
            result["response_time_ms"] = round(elapsed, 2)
        except Exception as exc:
            result["db_connected"] = False
            result["response_time_ms"] = round((time.monotonic() - start) * 1000, 2)

    return result

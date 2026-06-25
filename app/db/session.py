import logging
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.settings import get_settings
from app.db.db_health import is_db_healthy, report_db_failure, report_db_success

_logger = logging.getLogger(__name__)

# Connection pool defaults (can be overridden via env: DB_POOL_SIZE / DB_MAX_OVERFLOW)
POOL_PRE_PING = True
POOL_RECYCLE_SECONDS = 3600
POOL_TIMEOUT_SECONDS = 30
# When postgres is unreachable (e.g. Docker hostname from host), fail fast
CONNECT_TIMEOUT_SECONDS = 3

# Raised when the DB circuit breaker is open
class DatabaseDegradedError(RuntimeError):
    """Database is in DEGRADED state; connection not attempted."""


def build_sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def get_engine_uncached() -> Engine:
    """Create engine without caching (used by test_mode switching)."""
    settings = get_settings()
    if settings.test_mode:
        _logger.warning("test_mode_active_using_sqlite_in_memory")
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            future=True,
        )

    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("postgres"):
        connect_args["connect_timeout"] = CONNECT_TIMEOUT_SECONDS
    return create_engine(
        build_sync_database_url(settings.database_url),
        connect_args=connect_args,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=POOL_PRE_PING,
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_timeout=POOL_TIMEOUT_SECONDS,
    )


@lru_cache
def get_engine() -> Engine:
    """Return the cached engine. In test_mode the engine is always fresh."""
    settings = get_settings()
    if settings.test_mode:
        return get_engine_uncached()
    return get_engine_uncached()


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def SessionLocal() -> Session:
    """Create a session lazily to avoid import-time engine initialization."""
    return get_sessionmaker()()


class DBSessionContext:
    """Context-aware DB session with health check and safe error reporting.

    Usage:
        with DBSessionContext() as session:
            session.execute(...)

    Raises DatabaseDegradedError if circuit breaker is open.
    Re-raises DB errors after reporting them to the health tracker.
    """

    def __enter__(self) -> Session:
        if not is_db_healthy():
            raise DatabaseDegradedError(
                "Database is in DEGRADED state. Connection not attempted to avoid thread pool exhaustion."
            )
        self._session: Session = get_sessionmaker()()
        return self._session

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            if exc_type is None:
                self._session.commit()
                report_db_success()
            else:
                self._session.rollback()
                if isinstance(exc_val, (OperationalError, DBAPIError)):
                    report_db_failure(str(exc_val))
        finally:
            self._session.close()

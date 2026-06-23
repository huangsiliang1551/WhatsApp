"""
DB health tracker with circuit-breaker style degradation.

Tracks DB connectivity state and provides fast-fail when DB is known to be
unreachable, preventing thread pool exhaustion from concurrent connection
attempts that all block for CONNECT_TIMEOUT_SECONDS.

State machine:
    UNKNOWN  → initial state, allow connection attempts
    HEALTHY  → last probe succeeded, allow normal operation
    DEGRADED → last N probes failed, fail fast without trying to connect
    RECOVERING → periodic probe succeeded, return to HEALTHY

DEGRADED → RECOVERING triggers after a cooldown interval.
Any successful real connection resets the state to HEALTHY immediately.
"""

import structlog
import time

_logger = structlog.get_logger(__name__)

# ---- Constants ----

# How many consecutive probe failures trigger DEGRADED state
_DEGRADED_THRESHOLD = 3

# How long (seconds) to wait before trying to probe again from DEGRADED state
_RECOVERY_COOLDOWN = 30

# How often to probe the DB for health (seconds)
_PROBE_INTERVAL = 15

# ---- State ----

class _DbHealthState:
    """Holds mutable DB health state (thread-safe via atomic updates)."""

    def __init__(self) -> None:
        self.status: str = "UNKNOWN"  # UNKNOWN | HEALTHY | DEGRADED | RECOVERING
        self.consecutive_failures: int = 0
        self.last_probe_time: float = 0.0
        self.last_error: str = ""
        self.last_success_time: float = 0.0
        self.recovery_check_time: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "last_probe_seconds_ago": round(time.monotonic() - self.last_probe_time, 1) if self.last_probe_time else -1,
            "last_error": self.last_error,
            "last_success_seconds_ago": round(time.monotonic() - self.last_success_time, 1) if self.last_success_time else -1,
        }


# Global singleton
_db_health = _DbHealthState()


def get_db_health() -> dict[str, object]:
    """Return current DB health state (thread-safe snapshot)."""
    return _db_health.to_dict()


def is_db_healthy() -> bool:
    """Fast check: should we attempt a DB connection, or fail fast?"""
    s = _db_health
    if s.status == "DEGRADED":
        # Check if cooldown has elapsed → allow a recovery attempt
        if time.monotonic() - s.recovery_check_time >= _RECOVERY_COOLDOWN:
            return True  # Allow one probe attempt
        return False
    return True


def report_db_success() -> None:
    """Call after a successful DB operation to reset health state."""
    s = _db_health
    s.status = "HEALTHY"
    s.consecutive_failures = 0
    s.last_success_time = time.monotonic()
    s.last_probe_time = time.monotonic()
    s.last_error = ""
    if s.consecutive_failures >= _DEGRADED_THRESHOLD:
        _logger.info("db_health_recovered", previous_failures=s.consecutive_failures)


def report_db_failure(error: str = "") -> None:
    """Call after a failed DB operation to potentially trigger DEGRADED state."""
    s = _db_health
    s.consecutive_failures += 1
    s.last_probe_time = time.monotonic()
    s.last_error = error[:500]

    if s.consecutive_failures >= _DEGRADED_THRESHOLD:
        if s.status != "DEGRADED":
            _logger.error(
                "db_health_degraded_circuit_open",
                consecutive_failures=s.consecutive_failures,
                last_error=s.last_error,
            )
        s.status = "DEGRADED"
        s.recovery_check_time = time.monotonic()
    else:
        if s.status != "UNKNOWN":
            _logger.warning(
                "db_health_failure",
                consecutive_failures=s.consecutive_failures,
                error=s.last_error,
            )
        s.status = "RECOVERING"


def probe_db_sync() -> str:
    """Synchronous DB health probe. Returns 'healthy' or 'unhealthy'."""
    from app.db.session import get_engine
    from sqlalchemy import text

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        report_db_success()
        return "healthy"
    except Exception as exc:
        report_db_failure(str(exc))
        return "unhealthy"


def record_db_bootstrap_outcome(success: bool, error: str = "") -> None:
    """Record the result of the startup bootstrap probe."""
    if success:
        report_db_success()
    else:
        _db_health.consecutive_failures = _DEGRADED_THRESHOLD  # Immediate DEGRADED
        report_db_failure(error)


# ---- Startup probe ----

def check_db_at_startup() -> bool:
    """Run a single DB connectivity probe at startup. Returns True if healthy."""
    from app.core.settings import get_settings

    settings = get_settings()

    if settings.test_mode:
        _logger.info("db_startup_skipped_test_mode")
        _db_health.status = "HEALTHY"
        return True

    _logger.info("db_startup_probe_beginning", database_url=_mask_password(str(settings.database_url)))

    result = probe_db_sync()
    if result == "healthy":
        _logger.info("db_startup_probe_success")
        return True

    _logger.error(
        "db_startup_probe_failed",
        error=_db_health.last_error,
        hint=(
            "Check that PostgreSQL is running and DATABASE_URL is correct. "
            "If running on Windows outside Docker, use 'localhost' instead of 'postgres' as the hostname."
        ),
    )
    return False


def _mask_password(url: str) -> str:
    """Mask the password portion of a database URL for logging."""
    if "://" not in url:
        return url
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.password:
            # Replace password with asterisks
            netloc = f"{parsed.username}:****@{parsed.hostname}"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        pass
    return url

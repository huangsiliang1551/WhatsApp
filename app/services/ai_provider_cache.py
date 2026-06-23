"""
AIP-002: In-memory cache for AI provider configuration with TTL-based invalidation.

TTL defaults to 60 seconds. Explicit invalidate() is called after any CRUD operation.
Thread-safe via threading.Lock.
"""

import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIProviderConfig, AccountAIProviderOverride
from app.core.settings import get_settings


class AIProviderCache:
    """Thread-safe in-memory cache for AI provider configs with TTL expiration."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._chain: list[AIProviderConfig] | None = None
        self._overrides: dict[str, str] | None = None  # account_id → provider_config_id
        self._loaded_at: float = 0.0

    def get_active_chain(self, session: Session) -> list[AIProviderConfig]:
        """Return enabled configs ordered by priority ascending."""
        self._refresh_if_expired(session)
        # Return a copy to prevent mutation
        return list(self._chain or [])

    def get_account_override(self, session: Session, account_id: str) -> AIProviderConfig | None:
        """Return the account-specific override config if active, or None."""
        self._refresh_if_expired(session)
        if not self._overrides:
            return None
        config_id = self._overrides.get(account_id)
        if not config_id:
            return None
        settings = get_settings()
        chain = self._chain or []
        for cfg in chain:
            if cfg.id == config_id and cfg.is_enabled:
                return cfg
        return None

    def invalidate(self) -> None:
        """Force cache refresh on next access. Called after CRUD."""
        with self._lock:
            self._chain = None
            self._overrides = None
            self._loaded_at = 0.0

    def _refresh_if_expired(self, session: Session) -> None:
        """Reload from DB if TTL expired or cache empty."""
        with self._lock:
            if self._chain is not None and (time.monotonic() - self._loaded_at) < self._ttl:
                return

            stmt = (
                select(AIProviderConfig)
                .where(AIProviderConfig.is_enabled.is_(True))
                .order_by(AIProviderConfig.priority.asc())
            )
            results = list(session.scalars(stmt).all())
            self._chain = results

            override_stmt = select(AccountAIProviderOverride).where(
                AccountAIProviderOverride.is_active.is_(True)
            )
            overrides: dict[str, str] = {}
            for row in session.scalars(override_stmt).all():
                overrides[row.account_id] = row.provider_config_id
            self._overrides = overrides
            self._loaded_at = time.monotonic()


# Module-level singleton
_provider_cache: AIProviderCache | None = None
_cache_lock = threading.Lock()


def get_provider_cache() -> AIProviderCache:
    global _provider_cache
    if _provider_cache is None:
        with _cache_lock:
            if _provider_cache is None:
                settings = get_settings()
                _provider_cache = AIProviderCache(
                    ttl_seconds=settings.ai_config_cache_ttl_seconds
                )
    return _provider_cache


def invalidate_provider_cache() -> None:
    """Convenience function to invalidate the global cache."""
    global _provider_cache
    if _provider_cache is not None:
        _provider_cache.invalidate()

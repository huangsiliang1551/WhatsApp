from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IPBlacklist


class IPBlacklistService:
    """Manage IP blacklist entries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_blacklist(self) -> list[IPBlacklist]:
        return list(self._session.scalars(
            select(IPBlacklist).order_by(IPBlacklist.created_at.desc())
        ).all())

    def is_blocked(self, ip_address: str) -> bool:
        entry = self._session.scalar(
            select(IPBlacklist).where(IPBlacklist.ip_address == ip_address)
        )
        if not entry:
            return False
        if entry.blocked_until and entry.blocked_until < datetime.now():
            return False
        return True

    def block_ip(
        self,
        ip_address: str,
        reason: str | None = None,
        blocked_until: datetime | None = None,
        created_by: str | None = None,
    ) -> IPBlacklist:
        entry = IPBlacklist(
            id=str(uuid4()),
            ip_address=ip_address,
            reason=reason,
            blocked_until=blocked_until,
            created_by=created_by,
        )
        self._session.add(entry)
        self._session.commit()
        return entry

    def unblock_ip(self, blacklist_id: str) -> None:
        entry = self._session.get(IPBlacklist, blacklist_id)
        if not entry:
            raise LookupError(f"IP blacklist entry '{blacklist_id}' not found.")
        self._session.delete(entry)
        self._session.commit()

    def update_entry(
        self,
        blacklist_id: str,
        reason: str | None = None,
        blocked_until: datetime | None = None,
    ) -> IPBlacklist:
        entry = self._session.get(IPBlacklist, blacklist_id)
        if not entry:
            raise LookupError(f"IP blacklist entry '{blacklist_id}' not found.")
        if reason is not None:
            entry.reason = reason
        if blocked_until is not None:
            entry.blocked_until = blocked_until
        self._session.commit()
        return entry

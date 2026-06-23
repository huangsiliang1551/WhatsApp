from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import AuditLog, ClientError, Message, MessageEvent, UptimeCheck


class DataRetentionService:
    """Clean up old messages, logs, and monitoring data."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def cleanup_old_messages(self, days: int = 90) -> int:
        """Delete messages and events older than `days`."""
        cutoff = datetime.now() - timedelta(days=days)

        # Delete message events first (child records)
        self._session.execute(
            delete(MessageEvent).where(MessageEvent.created_at < cutoff)
        )

        # Delete messages
        result = self._session.execute(
            delete(Message).where(Message.created_at < cutoff)
        )

        self._session.commit()
        return result.rowcount

    def cleanup_old_logs(self, days: int = 90) -> int:
        """Delete audit logs, client errors, and uptime checks older than `days`."""
        cutoff = datetime.now() - timedelta(days=days)

        # Audit logs
        r1 = self._session.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )

        # Client errors
        r2 = self._session.execute(
            delete(ClientError).where(ClientError.created_at < cutoff)
        )

        # Uptime checks
        r3 = self._session.execute(
            delete(UptimeCheck).where(UptimeCheck.created_at < cutoff)
        )

        self._session.commit()
        return r1.rowcount + r2.rowcount + r3.rowcount

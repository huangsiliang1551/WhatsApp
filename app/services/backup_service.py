"""Backup service for database backup and restore operations.

IV-BE-001: supports manual/auto_daily/auto_weekly backups via pg_dump,
          retains only the latest MAX_BACKUPS (default 7) backups,
          and provides a schedule_auto_backup method for the worker.
"""

from __future__ import annotations

import asyncio
import gzip
import os
import shlex
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db.models import DbBackup, utc_now

logger = structlog.get_logger()


class BackupService:
    """Manage postgres database backups using pg_dump."""

    MAX_BACKUPS = 7

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings

    # ── Public helpers ────────────────────────────────────────────────────────────

    @property
    def backup_dir(self) -> str:
        if self._settings:
            return self._settings.backup_dir
        return "/opt/whatsapp/backups"

    # ── Create backup ─────────────────────────────────────────────────────────────

    async def create_backup(
        self,
        user_id: str | None = None,
        backup_type: str = "manual",
    ) -> DbBackup:
        """Run pg_dump and save a compressed backup."""
        # Ensure backup directory exists
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.sql.gz"
        filepath = os.path.join(self.backup_dir, filename)

        record = DbBackup(
            filename=filename,
            file_path=filepath,
            backup_type=backup_type,
            status="running",
            started_at=utc_now(),
            created_by=user_id or "system",
        )
        self._session.add(record)
        self._session.flush()

        try:
            start = time.monotonic()
            # Build pg_dump command from DATABASE_URL
            db_url = self._resolve_db_url()
            cmd = f"pg_dump --no-owner --no-acl \"{db_url}\" | gzip > {shlex.quote(filepath)}"
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode() if stderr else "pg_dump failed"
                record.status = "failed"
                record.error_message = err_msg
                logger.error("backup_failed", filename=filename, error=err_msg)
            else:
                elapsed = time.monotonic() - start
                record.status = "completed"
                record.file_size = os.path.getsize(filepath)
                record.completed_at = utc_now()
                logger.info(
                    "backup_completed",
                    filename=filename,
                    size_bytes=record.file_size,
                    elapsed_seconds=round(elapsed, 2),
                )

            self._session.flush()
            self._enforce_max_backups()
            return record
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)
            self._session.flush()
            logger.error("backup_exception", filename=filename, error=str(exc))
            return record

    # ── Restore ───────────────────────────────────────────────────────────────────

    async def restore_backup(self, backup_id: str) -> dict[str, Any]:
        """Restore database from a backup record."""
        record = self._session.get(DbBackup, backup_id)
        if not record:
            return {"success": False, "error": f"Backup {backup_id} not found"}
        if record.status != "completed":
            return {"success": False, "error": f"Backup status is '{record.status}', cannot restore"}

        filepath = record.file_path
        if not os.path.exists(filepath):
            return {"success": False, "error": f"Backup file not found: {filepath}"}

        try:
            db_url = self._resolve_db_url()
            cmd = f"gunzip -c {shlex.quote(filepath)} | psql \"{db_url}\""
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                err_msg = stderr.decode() if stderr else "restore failed"
                logger.error("restore_failed", backup_id=backup_id, error=err_msg)
                return {"success": False, "error": err_msg}

            logger.info("restore_completed", backup_id=backup_id, filename=record.filename)
            return {"success": True, "filename": record.filename}
        except Exception as exc:
            logger.error("restore_exception", backup_id=backup_id, error=str(exc))
            return {"success": False, "error": str(exc)}

    # ── List backups ──────────────────────────────────────────────────────────────

    def list_backups(self) -> list[DbBackup]:
        """Return all backups ordered by creation descending."""
        return list(
            self._session.scalars(
                select(DbBackup).order_by(DbBackup.started_at.desc())
            ).all()
        )

    def get_backup(self, backup_id: str) -> DbBackup | None:
        return self._session.get(DbBackup, backup_id)

    def delete_backup(self, backup_id: str) -> bool:
        record = self._session.get(DbBackup, backup_id)
        if not record:
            return False
        # Also delete file
        if record.file_path and os.path.exists(record.file_path):
            try:
                os.remove(record.file_path)
            except OSError:
                pass
        self._session.delete(record)
        return True

    # ── Scheduled auto backup (worker) ───────────────────────────────────────────

    async def schedule_auto_backup(self) -> DbBackup | None:
        """Called by worker at 3:00 AM daily / weekly."""
        from datetime import datetime as dt

        now = dt.now()
        backup_type: str = "auto_daily"
        if now.weekday() == 6:  # Sunday
            backup_type = "auto_weekly"

        return await self.create_backup(user_id=None, backup_type=backup_type)

    # ── Internals ─────────────────────────────────────────────────────────────────

    def _enforce_max_backups(self) -> None:
        """Delete old backups beyond MAX_BACKUPS."""
        records = list(
            self._session.scalars(
                select(DbBackup)
                .where(DbBackup.status == "completed")
                .order_by(DbBackup.completed_at.desc())
            ).all()
        )
        if len(records) > self.MAX_BACKUPS:
            for old in records[self.MAX_BACKUPS :]:
                if old.file_path and os.path.exists(old.file_path):
                    try:
                        os.remove(old.file_path)
                    except OSError:
                        pass
                self._session.delete(old)
            logger.info(
                "backup_cleanup",
                removed=len(records) - self.MAX_BACKUPS,
                max_kept=self.MAX_BACKUPS,
            )

    def _resolve_db_url(self) -> str:
        """Extract the postgres connection string for CLI pg_dump/psql."""
        if self._settings:
            url = self._settings.database_url
        else:
            from app.core.settings import get_settings
            url = get_settings().database_url

        # Strip +psycopg suffix for CLI commands
        for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return url.replace(prefix, "postgresql://", 1)
        return url

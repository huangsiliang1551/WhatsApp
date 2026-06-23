from __future__ import annotations

import csv
import io
import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Account, Agent, AuditLog, Conversation, Message, MessageTemplate, Ticket,
)

logger = structlog.get_logger()


EXPORT_TYPES = {"conversations", "templates", "tickets", "customers", "users", "audit_logs"}
EXPORT_DIR = Path("storage/exports")


class ExportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    async def create_export(
        self,
        export_type: str,
        filters: dict | None = None,
        columns: list[str] | None = None,
    ) -> dict:
        if export_type not in EXPORT_TYPES:
            raise ValueError(f"Unsupported export type '{export_type}'. Supported: {', '.join(sorted(EXPORT_TYPES))}")

        export_id = f"exp-{uuid.uuid4().hex[:12]}"
        filters = filters or {}

        # Estimate row count
        row_count = self._estimate_row_count(export_type, filters)
        if row_count == 0:
            row_count = 1

        # Create metadata
        meta = {
            "export_id": export_id,
            "type": export_type,
            "filters": filters,
            "columns": columns or [],
            "status": "processing",
            "estimated_rows": row_count,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            "file_size_bytes": 0,
            "row_count": 0,
        }

        # Write metadata
        meta_path = EXPORT_DIR / f"{export_id}.json"
        meta_path.write_text(json.dumps(meta, indent=2))

        # Generate export data synchronously for now (can be moved to worker later)
        try:
            actual_rows = self._generate_export(export_id, export_type, filters, columns)
            meta["status"] = "completed"
            meta["row_count"] = actual_rows
            file_path = EXPORT_DIR / f"{export_id}.csv"
            if file_path.exists():
                meta["file_size_bytes"] = file_path.stat().st_size
            meta["download_url"] = f"/api/exports/{export_id}/download"
        except Exception as exc:
            meta["status"] = "failed"
            meta["error"] = str(exc)
            logger.error("export_failed", export_id=export_id, error=str(exc))

        meta_path.write_text(json.dumps(meta, indent=2))

        return {
            "export_id": export_id,
            "status": meta["status"],
            "estimated_rows": row_count,
        }

    def get_export_status(self, export_id: str) -> dict | None:
        meta_path = EXPORT_DIR / f"{export_id}.json"
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def get_export_file_path(self, export_id: str) -> Path | None:
        file_path = EXPORT_DIR / f"{export_id}.csv"
        if file_path.exists():
            return file_path
        return None

    def _estimate_row_count(self, export_type: str, filters: dict) -> int:
        from sqlalchemy import func
        try:
            if export_type == "conversations":
                stmt = select(func.count(Conversation.id))
                if filters.get("account_id"):
                    stmt = stmt.where(Conversation.account_id == filters["account_id"])
                if filters.get("status"):
                    stmt = stmt.where(Conversation.status == filters["status"])
                return self._session.scalar(stmt) or 0
            elif export_type == "templates":
                stmt = select(func.count(MessageTemplate.id))
                if filters.get("account_id"):
                    stmt = stmt.where(MessageTemplate.account_id == filters["account_id"])
                return self._session.scalar(stmt) or 0
            elif export_type == "tickets":
                stmt = select(func.count(Ticket.id))
                if filters.get("account_id"):
                    stmt = stmt.where(Ticket.account_id == filters["account_id"])
                return self._session.scalar(stmt) or 0
            elif export_type == "customers":
                from app.db.models import AppUser
                stmt = select(func.count(AppUser.id))
                if filters.get("account_id"):
                    stmt = stmt.where(AppUser.account_id == filters["account_id"])
                return self._session.scalar(stmt) or 0
            elif export_type == "users":
                stmt = select(func.count(Agent.id))
                return self._session.scalar(stmt) or 0
            elif export_type == "audit_logs":
                stmt = select(func.count(AuditLog.id))
                if filters.get("account_id"):
                    stmt = stmt.where(AuditLog.account_id == filters["account_id"])
                return self._session.scalar(stmt) or 0
        except Exception:
            return 0
        return 0

    def _generate_export(
        self,
        export_id: str,
        export_type: str,
        filters: dict,
        columns: list[str] | None,
    ) -> int:
        file_path = EXPORT_DIR / f"{export_id}.csv"
        rows = self._fetch_rows(export_type, filters)
        if not rows:
            # Write empty CSV with headers
            if columns:
                headers = columns
            elif rows:
                headers = list(rows[0].keys())
            else:
                headers = ["id"]
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
            return 0

        if columns:
            headers = columns
        else:
            headers = list(rows[0].keys())

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                filtered = {k: row.get(k, "") for k in headers}
                writer.writerow(filtered)

        return len(rows)

    def _fetch_rows(self, export_type: str, filters: dict) -> list[dict]:
        try:
            if export_type == "conversations":
                stmt = select(Conversation)
                if filters.get("account_id"):
                    stmt = stmt.where(Conversation.account_id == filters["account_id"])
                if filters.get("status"):
                    stmt = stmt.where(Conversation.status == filters["status"])
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "conversation_id": r.external_conversation_id,
                        "account_id": r.account_id,
                        "customer_id": r.customer_id,
                        "status": r.status,
                        "management_mode": r.management_mode,
                        "ai_enabled": str(r.ai_enabled),
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                    }
                    for r in rows
                ]
            elif export_type == "templates":
                stmt = select(MessageTemplate)
                if filters.get("account_id"):
                    stmt = stmt.where(MessageTemplate.account_id == filters["account_id"])
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "template_id": r.id,
                        "account_id": r.account_id,
                        "name": r.name,
                        "status": r.status or "",
                        "language": r.language or "",
                        "category": r.category or "",
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
            elif export_type == "tickets":
                stmt = select(Ticket)
                if filters.get("account_id"):
                    stmt = stmt.where(Ticket.account_id == filters["account_id"])
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "ticket_id": r.id,
                        "account_id": r.account_id,
                        "subject": r.title or "",
                        "status": r.status or "",
                        "priority": r.priority or "",
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
            elif export_type == "customers":
                from app.db.models import AppUser
                stmt = select(AppUser)
                if filters.get("account_id"):
                    stmt = stmt.where(AppUser.account_id == filters["account_id"])
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "id": u.id,
                        "account_id": u.account_id,
                        "public_user_id": u.public_user_id or "",
                        "display_name": u.display_name or "",
                        "phone": "",
                    }
                    for u in rows
                ]
            elif export_type == "users":
                stmt = select(Agent)
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "agent_id": r.agent_id,
                        "display_name": r.display_name or "",
                        "role": r.role or "",
                        "is_online": str(r.is_online),
                    }
                    for r in rows
                ]
            elif export_type == "audit_logs":
                stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(5000)
                if filters.get("account_id"):
                    stmt = stmt.where(AuditLog.account_id == filters["account_id"])
                rows = self._session.execute(stmt).scalars().all()
                return [
                    {
                        "id": r.id,
                        "account_id": r.account_id,
                        "action": r.action,
                        "target_type": r.target_type,
                        "target_id": r.target_id,
                        "actor_type": r.actor_type,
                        "actor_id": r.actor_id,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
        except Exception as exc:
            logger.error("export_fetch_failed", export_type=export_type, error=str(exc))
            return []
        return []

    @staticmethod
    def cleanup_expired_exports() -> int:
        """Remove expired export files. Returns number of cleaned up exports."""
        cleaned = 0
        now = datetime.now(UTC)
        for f in EXPORT_DIR.glob("*.json"):
            try:
                meta = json.loads(f.read_text())
                expires_at = datetime.fromisoformat(meta.get("expires_at", ""))
                if expires_at < now:
                    csv_path = EXPORT_DIR / f"{meta['export_id']}.csv"
                    if csv_path.exists():
                        csv_path.unlink()
                    f.unlink()
                    cleaned += 1
            except (json.JSONDecodeError, OSError):
                continue
        return cleaned

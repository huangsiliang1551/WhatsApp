"""Batch operations service — IV-BE-002.

Provides batch tag updates, conversation assignment,
template sending, and CSV product import.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Agent, Conversation, utc_now

logger = structlog.get_logger()


class BatchService:
    """Perform batch operations on entities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Batch tags ────────────────────────────────────────────────────────────────

    def batch_update_tags(
        self,
        entity_type: str,
        entity_ids: list[str],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Batch update tags for conversations / customers / tickets.

        entity_type: conversation / customer / ticket
        """
        add_tags = add_tags or []
        remove_tags = remove_tags or []
        affected = 0

        model = self._resolve_entity_model(entity_type)
        if model is None:
            return {"success": False, "error": f"Unknown entity_type: {entity_type}"}

        for eid in entity_ids:
            record = self._session.get(model, eid)
            if record is None:
                continue
            current_tags: list[str] = list(getattr(record, "tags", []) or [])
            for t in remove_tags:
                if t in current_tags:
                    current_tags.remove(t)
            for t in add_tags:
                if t not in current_tags:
                    current_tags.append(t)
            record.tags = current_tags  # type: ignore[assignment]
            affected += 1

        logger.info(
            "batch_tags_updated",
            entity_type=entity_type,
            count=affected,
            add_count=len(add_tags),
            remove_count=len(remove_tags),
        )
        return {"success": True, "affected": affected, "entity_type": entity_type}

    # ── Batch assign conversations ────────────────────────────────────────────────

    def batch_assign_conversations(
        self,
        conversation_ids: list[str],
        agent_id: str,
    ) -> dict[str, Any]:
        """Assign conversations to a specific agent."""
        agent = self._session.get(Agent, agent_id)
        if not agent:
            return {"success": False, "error": f"Agent {agent_id} not found"}

        stmt = (
            update(Conversation)
            .where(Conversation.id.in_(conversation_ids))
            .values(assigned_agent_id=agent_id, updated_at=utc_now())
        )
        result = self._session.execute(stmt)
        logger.info(
            "batch_assign_conversations",
            count=result.rowcount,
            agent_id=agent_id,
        )
        return {"success": True, "affected": result.rowcount, "agent_id": agent_id}

    # ── Batch send template ───────────────────────────────────────────────────────

    def batch_send_template(
        self,
        entity_type: str,
        entity_ids: list[str],
        template_id: str,
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Enqueue template-send jobs for the given entities.

        The actual send is delegated to the template service / worker.
        """
        from app.services.queue_service import QueueService
        from app.core.settings import get_settings

        settings = get_settings()
        queue_service = QueueService(settings)
        queued = 0

        for eid in entity_ids:
            payload = {
                "action": "send_template",
                "entity_type": entity_type,
                "entity_id": eid,
                "template_id": template_id,
                "variables": variables or {},
            }
            queue_service.enqueue_ai_generation(payload)
            queued += 1

        logger.info(
            "batch_send_template_queued",
            count=queued,
            template_id=template_id,
        )
        return {"success": True, "queued": queued, "template_id": template_id}

    # ── Batch import products (CSV) ───────────────────────────────────────────────

    def batch_import_products(
        self,
        csv_data: str,
        account_id: str,
    ) -> dict[str, Any]:
        """Parse CSV and create product records."""
        from app.services.ecommerce_service import EcommerceService
        from app.core.settings import get_settings

        settings = get_settings()
        reader = csv.DictReader(io.StringIO(csv_data))
        imported = 0
        errors: list[str] = []

        svc = EcommerceService(session=self._session, provider=None, runtime_state=None, settings=settings)  # type: ignore[arg-type]

        for row_num, row in enumerate(reader, start=2):
            try:
                name = row.get("name", "").strip()
                price = row.get("price", "0").strip()
                stock = row.get("stock", "0").strip()
                if not name:
                    errors.append(f"Row {row_num}: missing name")
                    continue
                from decimal import Decimal

                product_data = {
                    "name": name,
                    "price": Decimal(price) if price else Decimal("0"),
                    "stock": int(stock) if stock.isdigit() else 0,
                    "account_id": account_id,
                    "description": row.get("description", "").strip(),
                    "category": row.get("category", "").strip(),
                }
                # Use direct insert instead of service method for batch efficiency
                from app.db.models import Product

                product = Product(**product_data)  # type: ignore[arg-type]
                self._session.add(product)
                imported += 1
            except Exception as exc:
                errors.append(f"Row {row_num}: {exc}")

        logger.info(
            "batch_import_products",
            imported=imported,
            errors=len(errors),
            account_id=account_id,
        )
        return {
            "success": True,
            "imported": imported,
            "errors": errors,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────────

    def _resolve_entity_model(self, entity_type: str) -> Any:
        """Return the SQLAlchemy model for the entity type."""
        from app.db.models import Conversation, MessageTemplate

        mapping = {
            "conversation": Conversation,
            "customer": None,  # Customers may not be a direct model
            "ticket": None,
            "template": MessageTemplate,
        }
        return mapping.get(entity_type)

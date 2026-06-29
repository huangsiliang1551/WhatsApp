from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import PaymentChannel, PaymentReconciliationItem


def test_payment_reconciliation_creates_missing_platform_items_from_provider_bill(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.services.payment_reconciliation_service import PaymentReconciliationService

    with db_session_factory() as session:
        channel = PaymentChannel(
            id="channel-reconcile-missing-platform",
            name="Reconcile Missing Platform",
            channel_type="generic_hmac",
            callback_secret="secret",
            status="active",
            config_json={
                "reconciliation_bill": [
                    {
                        "date": "2026-06-29",
                        "order_id": "CH-ORDER-1",
                        "user_id": "user-reconcile-1",
                        "amount": "88.00",
                        "currency": "USD",
                        "status": "success",
                    }
                ]
            },
        )
        session.add(channel)
        session.commit()

        rec = PaymentReconciliationService(session).auto_reconcile(
            channel_id=channel.id,
            reconcile_date=date(2026, 6, 29),
        )
        items = PaymentReconciliationService(session).get_reconciliation_items(rec.id)

        assert rec.status == "mismatched"
        assert rec.channel_amount == Decimal("88.00")
        assert rec.platform_amount == Decimal("0")
        assert len(items) == 1
        assert items[0]["item_type"] == "missing_platform"
        assert items[0]["channel_order_no"] == "CH-ORDER-1"


def test_payment_reconciliation_can_ignore_item_and_mark_record_resolved(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.db.models import PaymentReconciliation
    from app.services.payment_reconciliation_service import PaymentReconciliationService

    with db_session_factory() as session:
        rec = PaymentReconciliation(
            id="rec-ignore-1",
            channel_id="channel-ignore-1",
            reconcile_date=date(2026, 6, 29),
            platform_amount=Decimal("0"),
            channel_amount=Decimal("88.00"),
            difference=Decimal("-88.00"),
            status="mismatched",
        )
        item = PaymentReconciliationItem(
            id="rec-item-ignore-1",
            reconciliation_id=rec.id,
            channel_id=rec.channel_id,
            item_type="missing_platform",
            channel_order_no="CH-IGNORE-1",
            channel_amount=Decimal("88.00"),
            currency="USD",
            status="open",
            raw_json={},
        )
        session.add_all([rec, item])
        session.commit()

        updated = PaymentReconciliationService(session).update_item_status(
            item_id=item.id,
            target_status="ignored",
            actor_id="operator-ignore",
            reason="known provider drift",
        )

        session.refresh(rec)
        assert updated.status == "ignored"
        assert updated.raw_json["admin_action"]["actor_id"] == "operator-ignore"
        assert updated.raw_json["admin_action"]["reason"] == "known provider drift"
        assert rec.status == "resolved"


def test_payment_reconciliation_can_resolve_open_item(
    db_session_factory: sessionmaker[Session],
) -> None:
    from app.db.models import PaymentReconciliation
    from app.services.payment_reconciliation_service import PaymentReconciliationService

    with db_session_factory() as session:
        rec = PaymentReconciliation(
            id="rec-resolve-1",
            channel_id="channel-resolve-1",
            reconcile_date=date(2026, 6, 29),
            platform_amount=Decimal("10.00"),
            channel_amount=Decimal("12.00"),
            difference=Decimal("-2.00"),
            status="mismatched",
        )
        item = PaymentReconciliationItem(
            id="rec-item-resolve-1",
            reconciliation_id=rec.id,
            channel_id=rec.channel_id,
            item_type="amount_mismatch",
            channel_order_no="CH-RESOLVE-1",
            platform_amount=Decimal("10.00"),
            channel_amount=Decimal("12.00"),
            currency="USD",
            status="open",
            raw_json={},
        )
        session.add_all([rec, item])
        session.commit()

        updated = PaymentReconciliationService(session).update_item_status(
            item_id=item.id,
            target_status="resolved",
            actor_id="operator-resolve",
            reason="verified manually",
        )

        session.refresh(rec)
        assert updated.status == "resolved"
        assert updated.raw_json["admin_action"]["target_status"] == "resolved"
        assert rec.status == "resolved"

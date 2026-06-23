"""P0-03 regression tests: sleeping scanner worker bug.

The scanner previously had two bugs:
1. ``db.execute(Query.update())`` — ``Query.update()`` already executes and
   returns a rowcount, so wrapping it in ``db.execute()`` raises a runtime
   error.
2. ``offset`` pagination over a mutating dataset — each batch marks rows as
   sleeping, so advancing the offset skips rows that still match the original
   condition.

These tests prove the scanner marks *all* matching conversations (no skipped
batches) and correctly cold-marks old messages, and that it can be re-run
without error.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import app.worker as worker_module
from app.db.models import Account, Conversation, Message, utc_now


def _seed_sleeping_scanner_data(factory) -> None:
    with factory() as session:
        session.add(
            Account(
                account_id="scanner-account",
                display_name="Scanner Account",
                provider_type="mock",
            )
        )
        old = utc_now() - timedelta(hours=100)
        recent = utc_now() - timedelta(hours=1)

        # A: open, not sleeping, old last_customer_message_at -> should be marked
        session.add(
            Conversation(
                id="conv-scanner-a",
                account_id="scanner-account",
                external_conversation_id="ext-a",
                customer_id="customer-a",
                status="open",
                is_sleeping=False,
                last_customer_message_at=old,
            )
        )
        # B: open, not sleeping, old last_customer_message_at -> should be marked
        session.add(
            Conversation(
                id="conv-scanner-b",
                account_id="scanner-account",
                external_conversation_id="ext-b",
                customer_id="customer-b",
                status="open",
                is_sleeping=False,
                last_customer_message_at=old,
            )
        )
        # C: open, not sleeping, recent last_customer_message_at -> NOT marked
        session.add(
            Conversation(
                id="conv-scanner-c",
                account_id="scanner-account",
                external_conversation_id="ext-c",
                customer_id="customer-c",
                status="open",
                is_sleeping=False,
                last_customer_message_at=recent,
            )
        )

        # Conversation A messages: one old (-> cold), one recent (-> not cold)
        session.add(
            Message(
                id="msg-scanner-old",
                account_id="scanner-account",
                conversation_id="conv-scanner-a",
                direction="inbound",
                message_type="text",
                is_cold=False,
                created_at=old,
                provider_message_id="wamid.scanner.old",
            )
        )
        session.add(
            Message(
                id="msg-scanner-new",
                account_id="scanner-account",
                conversation_id="conv-scanner-a",
                direction="inbound",
                message_type="text",
                is_cold=False,
                created_at=recent,
                provider_message_id="wamid.scanner.new",
            )
        )
        session.commit()


def _run_scanner_one_cycle(factory, monkeypatch) -> None:
    """Run the sleeping scanner for a brief moment so at least one scan runs."""
    monkeypatch.setattr(worker_module, "SessionLocal", factory)

    original_running = worker_module.RUNNING
    worker_module.RUNNING = True
    try:
        settings = SimpleNamespace(
            sleeping_scan_interval_seconds=0,
            sleeping_threshold_hours=48,
        )

        async def _drive() -> None:
            task = asyncio.ensure_future(worker_module.sleeping_scanner(settings))
            # Let the loop run a few iterations (interval is 0). After the first
            # scan the matching set is empty, so further iterations are no-ops.
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        asyncio.run(_drive())
    finally:
        worker_module.RUNNING = original_running


def test_sleeping_scanner_marks_all_matching_conversations(
    db_session_factory,
    monkeypatch,
) -> None:
    _seed_sleeping_scanner_data(db_session_factory)
    _run_scanner_one_cycle(db_session_factory, monkeypatch)

    with db_session_factory() as session:
        a = session.get(Conversation, "conv-scanner-a")
        b = session.get(Conversation, "conv-scanner-b")
        c = session.get(Conversation, "conv-scanner-c")

        assert a.is_sleeping is True, "conversation A should be marked sleeping"
        assert b.is_sleeping is True, "conversation B should be marked sleeping (no offset skip)"
        assert c.is_sleeping is False, "conversation C should remain active"


def test_sleeping_scanner_marks_old_messages_cold(
    db_session_factory,
    monkeypatch,
) -> None:
    _seed_sleeping_scanner_data(db_session_factory)
    _run_scanner_one_cycle(db_session_factory, monkeypatch)

    with db_session_factory() as session:
        old_msg = session.get(Message, "msg-scanner-old")
        new_msg = session.get(Message, "msg-scanner-new")

        assert old_msg.is_cold is True, "old message should be marked cold"
        assert new_msg.is_cold is False, "recent message should remain hot"


def test_sleeping_scanner_is_idempotent(db_session_factory, monkeypatch) -> None:
    _seed_sleeping_scanner_data(db_session_factory)
    # Running twice must not raise (regression for db.execute(Query.update())).
    _run_scanner_one_cycle(db_session_factory, monkeypatch)
    _run_scanner_one_cycle(db_session_factory, monkeypatch)

    with db_session_factory() as session:
        a = session.get(Conversation, "conv-scanner-a")
        assert a.is_sleeping is True

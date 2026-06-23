"""P1-02 regression tests: production-grade webhook/message idempotency.

Webhook dedup previously relied on a process-local ``set`` which is unsafe
across workers and restarts. Dedup is now enforced by the service layer +
the DB unique constraint on ``messages.provider_message_id``. These tests
prove that a duplicate inbound message (same ``external_message_id``) only
ever creates a single message row, and that the IntegrityError race path
also collapses to the existing message.
"""

import asyncio

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Message
from app.schemas.mock_message import NormalizedMessage
from app.services.chat import process_inbound_message
from app.services.runtime_state import RuntimeStateStore
from app.providers.messaging.mock_provider import MockMessagingProvider


def _inbound_payload(message_id: str = "wamid.dedup.mock.1") -> dict[str, object]:
    return {
        "account_id": "dedup-account",
        "conversation_id": "conv-dedup",
        "user_id": "user-dedup",
        "text": "hello dedup",
        "mode": "echo",
        "external_message_id": message_id,
    }


def test_duplicate_inbound_message_creates_only_one_row(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    payload = _inbound_payload()

    first = client.post("/dev/mock/inbound-message", json=payload)
    assert first.status_code == 200, first.text
    assert first.json().get("deduplicated") is not True

    second = client.post("/dev/mock/inbound-message", json=payload)
    assert second.status_code == 200, second.text
    # Service layer recognizes the duplicate and does not re-create.
    assert second.json().get("deduplicated") is True

    with db_session_factory() as session:
        count = (
            session.query(Message)
            .filter(Message.provider_message_id == "wamid.dedup.mock.1")
            .count()
        )
    assert count == 1, "duplicate inbound must not create a second message row"


def test_process_inbound_message_collapses_integrity_error_race(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If record_inbound_message races to a unique violation, return the
    existing message instead of propagating the IntegrityError."""
    from app.core.settings import get_settings
    from app.providers.translation.factory import get_translation_provider
    from app.services.queue_service import QueueService
    from app.services.translation_service import TranslationService

    settings = get_settings()
    session = db_session_factory()
    runtime_state = RuntimeStateStore(session)
    translation_service = TranslationService(
        settings=settings, provider=get_translation_provider(settings)
    )
    queue_service = QueueService(settings)
    provider = MockMessagingProvider()

    normalized = NormalizedMessage(
        account_id="dedup-race-account",
        provider="mock",
        conversation_id="conv-dedup-race",
        user_id="user-dedup-race",
        text="race hello",
        external_message_id="wamid.dedup.race.1",
    )

    # First call: inserts the message normally.
    asyncio.run(
        process_inbound_message(
            normalized,
            messaging_provider=provider,
            requested_mode="echo",
            settings=settings,
            runtime_state_store=runtime_state,
            translation_service=translation_service,
            queue_service=queue_service,
        )
    )

    # Simulate a race: record_inbound_message raises IntegrityError, but the
    # row already exists (from the first call), so the handler must return a
    # deduplicated result instead of raising.
    original_record = runtime_state.record_inbound_message

    async def _raising_record(*args, **kwargs):
        raise IntegrityError("simulated race", params=None, orig=Exception("unique"))

    monkeypatch.setattr(runtime_state, "record_inbound_message", _raising_record)

    result = asyncio.run(
        process_inbound_message(
            normalized,
            messaging_provider=provider,
            requested_mode="echo",
            settings=settings,
            runtime_state_store=runtime_state,
            translation_service=translation_service,
            queue_service=queue_service,
        )
    )

    assert result.get("deduplicated") is True
    assert result.get("existing_message_id") is not None

    with db_session_factory() as fresh:
        count = (
            fresh.query(Message)
            .filter(Message.provider_message_id == "wamid.dedup.race.1")
            .count()
        )
    assert count == 1, "race must not create a duplicate row"

    monkeypatch.setattr(runtime_state, "record_inbound_message", original_record)
    session.close()

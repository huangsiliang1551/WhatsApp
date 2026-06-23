"""P0-02 regression tests: conversation stats SQL comparator.

``get_conversation_stats`` previously used ``.is_(value)`` for every filter,
which is only correct for ``NULL``/boolean values. Filtering by a string
status such as ``status='open'`` must use ``==`` so the generated SQL is
portable across PostgreSQL and SQLite.
"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, Conversation, utc_now


@pytest.fixture
def seeded_client(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> TestClient:
    with db_session_factory() as session:
        session.add(
            Account(
                account_id="stats-account",
                display_name="Stats Account",
                provider_type="mock",
            )
        )
        # open + not sleeping -> counts as active
        session.add(
            Conversation(
                id="conv-stats-open",
                account_id="stats-account",
                external_conversation_id="ext-open",
                customer_id="customer-open",
                status="open",
                is_sleeping=False,
            )
        )
        # closed + not sleeping -> counts as closed
        session.add(
            Conversation(
                id="conv-stats-closed",
                account_id="stats-account",
                external_conversation_id="ext-closed",
                customer_id="customer-closed",
                status="closed",
                is_sleeping=False,
            )
        )
        # sleeping -> counts as sleeping
        session.add(
            Conversation(
                id="conv-stats-sleeping",
                account_id="stats-account",
                external_conversation_id="ext-sleeping",
                customer_id="customer-sleeping",
                status="open",
                is_sleeping=True,
                last_customer_message_at=utc_now(),
            )
        )
        session.commit()
    return client


def test_conversation_stats_supports_string_status_filter(
    seeded_client: TestClient,
) -> None:
    response = seeded_client.get("/api/conversations/stats")

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)

    # String status filter ("open") and boolean filter (is_sleeping=False) must
    # both work. Before the fix, `.is_("open")` produced wrong SQL.
    assert data["active_count"] == 1, data
    assert data["closed_count"] == 1, data
    assert data["sleeping_count"] == 1, data


def test_conversation_stats_scoped_to_account(seeded_client: TestClient) -> None:
    response = seeded_client.get(
        "/api/conversations/stats",
        params={"account_id": "stats-account"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["active_count"] == 1
    assert data["closed_count"] == 1
    assert data["sleeping_count"] == 1

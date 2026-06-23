"""Tests for AgentPresenceService with in-memory store (test mode)."""

import json
import time

import pytest

from app.core.settings import Settings, get_settings
from app.services.agent_presence_service import AgentPresenceService

pytestmark = pytest.mark.anyio


@pytest.fixture
def settings() -> Settings:
    get_settings.cache_clear()
    s = get_settings()
    s.test_mode = True
    return s


@pytest.fixture
def presence_service(settings: Settings) -> AgentPresenceService:
    return AgentPresenceService(settings)


async def test_set_online_creates_presence(presence_service: AgentPresenceService) -> None:
    record = await presence_service.set_online("agent-1", display_name="Alice")
    assert record.agent_id == "agent-1"
    assert record.status == "online"
    assert record.display_name == "Alice"
    assert record.is_online is True


async def test_set_offline_removes_presence(presence_service: AgentPresenceService) -> None:
    await presence_service.set_online("agent-1")
    await presence_service.set_offline("agent-1")
    record = await presence_service.get_presence("agent-1")
    assert record is None


async def test_presence_with_account_scope(presence_service: AgentPresenceService) -> None:
    await presence_service.set_online("agent-1", account_id="account-a", display_name="Alice")
    await presence_service.set_online("agent-1", account_id="account-b", display_name="Bob")

    scope_a = await presence_service.list_online_agents(account_id="account-a")
    assert len(scope_a) == 1
    assert scope_a[0].agent_id == "agent-1"
    assert scope_a[0].display_name == "Alice"
    assert scope_a[0].account_id == "account-a"

    all_online = await presence_service.list_online_agents()
    assert len(all_online) == 2


async def test_is_online_returns_correct_bool(presence_service: AgentPresenceService) -> None:
    assert await presence_service.is_online("unknown-agent") is False

    await presence_service.set_online("agent-1")
    assert await presence_service.is_online("agent-1") is True

    await presence_service.set_offline("agent-1")
    assert await presence_service.is_online("agent-1") is False


async def test_busy_and_away_are_considered_online(presence_service: AgentPresenceService) -> None:
    await presence_service.set_busy("agent-busy")
    assert await presence_service.is_online("agent-busy") is True

    await presence_service.set_away("agent-away")
    assert await presence_service.is_online("agent-away") is True


async def test_heartbeat_refreshes_presence(presence_service: AgentPresenceService) -> None:
    await presence_service.set_online("agent-1")
    record_1 = await presence_service.get_presence("agent-1")
    assert record_1 is not None
    first_heartbeat = record_1.last_heartbeat

    time.sleep(0.01)

    refreshed = await presence_service.heartbeat("agent-1")
    assert refreshed is not None
    assert refreshed.last_heartbeat > first_heartbeat


async def test_heartbeat_on_unknown_agent_returns_none(presence_service: AgentPresenceService) -> None:
    result = await presence_service.heartbeat("non-existent")
    assert result is None


async def test_clear_all_removes_all_presence(presence_service: AgentPresenceService) -> None:
    await presence_service.set_online("agent-1", account_id="acc-a")
    await presence_service.set_online("agent-2", account_id="acc-b")
    await presence_service.set_online("agent-3", account_id="acc-a")

    assert len(await presence_service.list_online_agents()) == 3

    cleared = await presence_service.clear_all(account_id="acc-a")
    assert cleared == 2
    assert len(await presence_service.list_online_agents()) == 1


async def test_list_online_excludes_known_offline(presence_service: AgentPresenceService) -> None:
    await presence_service.set_online("agent-online")
    await presence_service.set_busy("agent-busy")
    await presence_service.set_away("agent-away")
    await presence_service.set_offline("agent-offline")

    online = await presence_service.list_online_agents()
    agent_ids = {r.agent_id for r in online}
    assert agent_ids == {"agent-online", "agent-busy", "agent-away"}
    assert "agent-offline" not in agent_ids


async def test_deserialize_handles_bytes_input(presence_service: AgentPresenceService) -> None:
    data = json.dumps({
        "account_id": "acc-1",
        "agent_id": "agent-1",
        "status": "online",
        "last_heartbeat": time.time(),
        "display_name": "Test",
    }).encode("utf-8")

    record = presence_service._deserialize(data)  # type: ignore[attr-defined]
    assert record.agent_id == "agent-1"
    assert record.is_online is True


@pytest.mark.parametrize(
    ("status", "expected_online"),
    [("online", True), ("busy", True), ("away", True), ("offline", False)],
)
async def test_is_online_for_all_statuses(
    presence_service: AgentPresenceService,
    status: str,
    expected_online: bool,
) -> None:
    # Set presence directly on the in-memory store
    store = presence_service._redis  # type: ignore[attr-defined]
    record = {
        "account_id": None,
        "agent_id": "agent-test",
        "status": status,
        "last_heartbeat": time.time(),
        "display_name": "",
    }
    store.set("presence:__global__:agent-test", json.dumps(record))
    assert await presence_service.is_online("agent-test") is expected_online

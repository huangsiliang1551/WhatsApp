from collections.abc import Generator
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.core.settings import get_settings
from app.db.base import Base
from app.main import app


@pytest.fixture
def strict_handover_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "strict_handover.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    original_env = {
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
    }
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["LIVE_TRANSLATION_ENABLED"] = "false"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"
    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    engine.dispose()


def test_agent_status_management_and_assignment_query(client: TestClient) -> None:
    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-ops-1",
            "display_name": "Alice",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200
    assert register_agent_response.json()["status"] == "online"

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-20",
            "conversation_id": "conv-20",
            "user_id": "user-20",
            "text": "need billing help",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/mock-account-20/conv-20/assignment",
        json={
            "agent_id": "agent-ops-1",
            "assigned_by_agent_id": "lead-1",
            "reason": "billing_queue",
        },
    )
    assert assignment_response.status_code == 200
    assignment_payload = assignment_response.json()

    assert assignment_payload["status"] == "open"
    assert assignment_payload["management_mode"] == "human_managed"
    assert assignment_payload["assigned_agent_id"] == "agent-ops-1"
    assert assignment_payload["assigned_agent_name"] == "Alice"

    conversations_response = client.get(
        "/api/conversations",
        params={
            "account_id": "mock-account-20",
            "assigned_agent_id": "agent-ops-1",
            "status": "open",
            "management_mode": "human_managed",
        },
    )
    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["items"]

    assert len(conversations) == 1
    assert conversations[0]["conversation_id"] == "conv-20"
    assert conversations[0]["status"] == "open"
    assert conversations[0]["assigned_agent_name"] == "Alice"

    agents_response = client.get("/api/runtime/agents", params={"status": "online"})
    assert agents_response.status_code == 200
    agents = agents_response.json()

    assert len(agents) == 1
    assert agents[0]["agent_id"] == "agent-ops-1"


def test_assigned_conversations_endpoint_filters_current_agent_open_scope(
    client: TestClient,
) -> None:
    for agent_id in ("assigned-agent-1", "assigned-agent-2"):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    for conversation_id in (
        "assigned-open-1",
        "assigned-closed-1",
        "assigned-other-1",
        "assigned-unassigned-1",
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "assigned-endpoint-account-1",
                "conversation_id": conversation_id,
                "user_id": f"user-{conversation_id}",
                "text": "need an operator",
                "mode": "echo",
            },
        )
        assert inbound_response.status_code == 200

    assign_open = client.post(
        "/api/conversations/assigned-endpoint-account-1/assigned-open-1/assignment",
        json={"agent_id": "assigned-agent-1"},
    )
    assert assign_open.status_code == 200
    assign_closed = client.post(
        "/api/conversations/assigned-endpoint-account-1/assigned-closed-1/assignment",
        json={"agent_id": "assigned-agent-1"},
    )
    assert assign_closed.status_code == 200
    close_assigned = client.post(
        "/api/conversations/assigned-endpoint-account-1/assigned-closed-1/close",
        json={"agent_id": "assigned-agent-1", "reason": "resolved"},
    )
    assert close_assigned.status_code == 200
    assign_other = client.post(
        "/api/conversations/assigned-endpoint-account-1/assigned-other-1/assignment",
        json={"agent_id": "assigned-agent-2"},
    )
    assert assign_other.status_code == 200

    response = client.get(
        "/api/conversations/assigned",
        params={
            "account_id": "assigned-endpoint-account-1",
            "agent_id": "assigned-agent-1",
        },
    )

    assert response.status_code == 200
    conversations = response.json()
    assert [item["conversation_id"] for item in conversations] == ["assigned-open-1"]
    returned_conversation_ids = {item["conversation_id"] for item in conversations}
    assert not returned_conversation_ids.intersection(
        {"assigned-closed-1", "assigned-other-1", "assigned-unassigned-1"}
    )
    assert conversations[0]["assigned_agent_id"] == "assigned-agent-1"
    assert conversations[0]["management_mode"] == "human_managed"


def test_assigned_conversations_endpoint_rejects_agent_impersonation(
    client: TestClient,
) -> None:
    for agent_id in ("assigned-strict-agent", "assigned-strict-other"):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "assigned-strict-account",
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "assigned-strict-account",
            "conversation_id": "assigned-strict-conv",
            "user_id": "assigned-strict-user",
            "text": "need current assigned list",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/assigned-strict-account/assigned-strict-conv/assignment",
        json={"agent_id": "assigned-strict-agent"},
    )
    assert assign_response.status_code == 200

    headers = {
        "X-Actor-Id": "assigned-strict-agent",
        "X-Actor-Role": "support_agent",
        "X-Actor-Account-Ids": "assigned-strict-account",
    }
    own_response = client.get(
        "/api/conversations/assigned",
        params={"account_id": "assigned-strict-account"},
        headers=headers,
    )
    assert own_response.status_code == 200
    assert [item["conversation_id"] for item in own_response.json()] == ["assigned-strict-conv"]

    impersonation_response = client.get(
        "/api/conversations/assigned",
        params={
            "account_id": "assigned-strict-account",
            "agent_id": "assigned-strict-other",
        },
        headers=headers,
    )
    assert impersonation_response.status_code == 403
    assert "does not match request actor" in impersonation_response.json()["detail"]


def test_offline_agent_cannot_be_assigned_and_close_returns_conversation_to_ai(
    client: TestClient,
) -> None:
    client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-ops-2",
            "display_name": "Bob",
            "status": "offline",
            "is_active": True,
        },
    )
    client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-21",
            "conversation_id": "conv-21",
            "user_id": "user-21",
            "text": "need a person",
            "mode": "echo",
        },
    )

    assignment_response = client.post(
        "/api/conversations/mock-account-21/conv-21/assignment",
        json={"agent_id": "agent-ops-2"},
    )
    assert assignment_response.status_code == 409
    assert "offline" in assignment_response.json()["detail"]

    status_response = client.post(
        "/api/runtime/agents/agent-ops-2/status",
        json={"status": "online"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "online"

    reassignment_response = client.post(
        "/api/conversations/mock-account-21/conv-21/assignment",
        json={"agent_id": "agent-ops-2"},
    )
    assert reassignment_response.status_code == 200

    close_response = client.post(
        "/api/conversations/mock-account-21/conv-21/close",
        json={
            "agent_id": "agent-ops-2",
            "reason": "resolved",
        },
    )
    assert close_response.status_code == 200
    close_payload = close_response.json()

    assert close_payload["status"] == "closed"
    assert close_payload["management_mode"] == "ai_managed"
    assert close_payload["assigned_agent_id"] is None

    state_response = client.get("/api/runtime/state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    conversation = next(
        item
        for item in state_payload["conversations"]
        if item["account_id"] == "mock-account-21" and item["conversation_id"] == "conv-21"
    )
    assert conversation["status"] == "closed"

    reopen_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "mock-account-21",
            "conversation_id": "conv-21",
            "user_id": "user-21",
            "text": "still need help",
            "mode": "ai",
        },
    )
    assert reopen_response.status_code == 200
    assert reopen_response.json()["runtime"]["effective_ai_enabled"] is True
    assert reopen_response.json()["outbound"]["text"] is None
    assert reopen_response.json()["outbound"]["delivery_mode"] == "ai_async_queued"
    assert reopen_response.json()["queue"]["queue"] == "ai_generation"

    reopened_conversations_response = client.get(
        "/api/conversations",
        params={"account_id": "mock-account-21", "status": "open"},
    )
    assert reopened_conversations_response.status_code == 200
    reopened_conversations = reopened_conversations_response.json()["items"]

    assert len(reopened_conversations) == 1
    assert reopened_conversations[0]["conversation_id"] == "conv-21"
    assert reopened_conversations[0]["status"] == "open"
    assert reopened_conversations[0]["management_mode"] == "ai_managed"


def test_account_scoped_agents_allow_same_agent_key_per_account(client: TestClient) -> None:
    register_scope_a = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "scope-agent-account-a",
            "agent_id": "shared-operator-1",
            "display_name": "Scoped Operator A",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_scope_a.status_code == 200
    assert register_scope_a.json()["account_id"] == "scope-agent-account-a"

    register_scope_b = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "scope-agent-account-b",
            "agent_id": "shared-operator-1",
            "display_name": "Scoped Operator B",
            "status": "offline",
            "is_active": True,
        },
    )
    assert register_scope_b.status_code == 200
    assert register_scope_b.json()["account_id"] == "scope-agent-account-b"

    scope_a_agents = client.get(
        "/api/runtime/agents",
        params={"account_id": "scope-agent-account-a"},
    )
    assert scope_a_agents.status_code == 200
    assert scope_a_agents.json()[0]["agent_id"] == "shared-operator-1"
    assert scope_a_agents.json()[0]["account_id"] == "scope-agent-account-a"

    scope_b_agents = client.get(
        "/api/runtime/agents",
        params={"account_id": "scope-agent-account-b"},
    )
    assert scope_b_agents.status_code == 200
    assert scope_b_agents.json()[0]["agent_id"] == "shared-operator-1"
    assert scope_b_agents.json()[0]["account_id"] == "scope-agent-account-b"

    for account_id, conversation_id in (
        ("scope-agent-account-a", "scope-agent-conv-a"),
        ("scope-agent-account-b", "scope-agent-conv-b"),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conversation_id,
                "user_id": f"user-{conversation_id}",
                "text": "need operator",
                "mode": "echo",
            },
        )
        assert inbound_response.status_code == 200

    assign_scope_a = client.post(
        "/api/conversations/scope-agent-account-a/scope-agent-conv-a/assignment",
        json={"agent_id": "shared-operator-1"},
    )
    assert assign_scope_a.status_code == 200
    assert assign_scope_a.json()["assigned_agent_id"] == "shared-operator-1"

    assign_scope_b_blocked = client.post(
        "/api/conversations/scope-agent-account-b/scope-agent-conv-b/assignment",
        json={"agent_id": "shared-operator-1"},
    )
    assert assign_scope_b_blocked.status_code == 409
    assert "offline" in assign_scope_b_blocked.json()["detail"]

    scope_b_status = client.post(
        "/api/runtime/agents/shared-operator-1/status",
        params={"account_id": "scope-agent-account-b"},
        json={"status": "online"},
    )
    assert scope_b_status.status_code == 200
    assert scope_b_status.json()["account_id"] == "scope-agent-account-b"
    assert scope_b_status.json()["status"] == "online"

    assign_scope_b = client.post(
        "/api/conversations/scope-agent-account-b/scope-agent-conv-b/assignment",
        json={"agent_id": "shared-operator-1"},
    )
    assert assign_scope_b.status_code == 200
    assert assign_scope_b.json()["assigned_agent_id"] == "shared-operator-1"


def test_account_scoped_agent_registration_does_not_migrate_global_agent(client: TestClient) -> None:
    global_agent = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "legacy-shared-operator",
            "display_name": "Legacy Global Operator",
            "status": "offline",
            "is_active": True,
        },
    )
    assert global_agent.status_code == 200
    assert global_agent.json()["account_id"] is None

    scoped_agent = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "legacy-scope-account",
            "agent_id": "legacy-shared-operator",
            "display_name": "Scoped Operator",
            "status": "online",
            "is_active": True,
        },
    )
    assert scoped_agent.status_code == 200
    assert scoped_agent.json()["account_id"] == "legacy-scope-account"

    all_agents = client.get("/api/runtime/agents")
    assert all_agents.status_code == 200
    matching_agents = [
        agent for agent in all_agents.json() if agent["agent_id"] == "legacy-shared-operator"
    ]
    assert {agent["account_id"] for agent in matching_agents} == {None, "legacy-scope-account"}

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "legacy-scope-account",
            "conversation_id": "legacy-scope-conv",
            "user_id": "legacy-scope-user",
            "text": "need the scoped operator",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/legacy-scope-account/legacy-scope-conv/assignment",
        json={"agent_id": "legacy-shared-operator"},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["assigned_agent_id"] == "legacy-shared-operator"
    assert assign_response.json()["assigned_agent_name"] == "Scoped Operator"


def test_agent_workloads_show_assigned_open_conversation_counts(client: TestClient) -> None:
    register_alice_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-workload-1",
            "display_name": "Alice",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_alice_response.status_code == 200

    register_bob_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-workload-2",
            "display_name": "Bob",
            "status": "busy",
            "is_active": True,
        },
    )
    assert register_bob_response.status_code == 200

    for conversation_id in ["conv-workload-1", "conv-workload-2", "conv-workload-3"]:
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "workload-account-1",
                "conversation_id": conversation_id,
                "user_id": f"user-{conversation_id}",
                "text": "need agent assignment",
                "mode": "echo",
            },
        )
        assert inbound_response.status_code == 200

    assign_first_response = client.post(
        "/api/conversations/workload-account-1/conv-workload-1/assignment",
        json={"agent_id": "agent-workload-1"},
    )
    assert assign_first_response.status_code == 200

    assign_second_response = client.post(
        "/api/conversations/workload-account-1/conv-workload-2/assignment",
        json={"agent_id": "agent-workload-1"},
    )
    assert assign_second_response.status_code == 200

    assign_third_response = client.post(
        "/api/conversations/workload-account-1/conv-workload-3/assignment",
        json={"agent_id": "agent-workload-2"},
    )
    assert assign_third_response.status_code == 200

    close_response = client.post(
        "/api/conversations/workload-account-1/conv-workload-2/close",
        json={"agent_id": "agent-workload-1", "reason": "resolved"},
    )
    assert close_response.status_code == 200

    workloads_response = client.get("/api/runtime/agents/workloads")
    assert workloads_response.status_code == 200
    workloads = workloads_response.json()

    alice = next(item for item in workloads if item["agent_id"] == "agent-workload-1")
    bob = next(item for item in workloads if item["agent_id"] == "agent-workload-2")

    assert alice["assigned_open_conversations"] == 1
    assert alice["assigned_total_conversations"] == 1
    assert alice["assigned_account_count"] == 1

    assert bob["assigned_open_conversations"] == 1
    assert bob["assigned_total_conversations"] == 1
    assert bob["assigned_account_count"] == 1


def test_only_assigned_agent_can_reply_close_and_resume_ai(client: TestClient) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-auth-1",
            "display_name": "Owner Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    second_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-auth-2",
            "display_name": "Other Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert second_agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "auth-account-1",
            "conversation_id": "auth-conv-1",
            "user_id": "auth-user-1",
            "text": "need a human",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/auth-account-1/auth-conv-1/assignment",
        json={
            "agent_id": "agent-auth-1",
            "assigned_by_agent_id": "agent-auth-1",
            "reason": "takeover",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/auth-account-1/auth-conv-1/messages/outbound",
        json={
            "text": "人工客服处理中",
            "agent_id": "agent-auth-2",
        },
    )
    assert outbound_response.status_code == 403
    assert "assigned to 'agent-auth-1'" in outbound_response.json()["detail"]

    other_agent_headers = {
        "X-Actor-Id": "agent-auth-2",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "auth-account-1",
    }
    resume_response = client.post(
        "/api/runtime/conversations/auth-conv-1/handover?account_id=auth-account-1",
        headers=other_agent_headers,
        json={
            "management_mode": "ai_managed",
            "agent_id": "agent-auth-2",
        },
    )
    assert resume_response.status_code == 403

    missing_agent_close_response = client.post(
        "/api/conversations/auth-account-1/auth-conv-1/close",
        json={
            "reason": "close_without_identity",
        },
    )
    assert missing_agent_close_response.status_code == 409
    assert "agent_id is required" in missing_agent_close_response.json()["detail"]

    close_response = client.post(
        "/api/conversations/auth-account-1/auth-conv-1/close",
        headers=other_agent_headers,
        json={
            "agent_id": "agent-auth-2",
            "reason": "force close",
        },
    )
    assert close_response.status_code == 403


def test_non_super_admin_cannot_cross_account_view_assign_or_close(
    client: TestClient,
) -> None:
    for account_id, conversation_id in (
        ("scope-auth-account-a", "scope-auth-conv-a"),
        ("scope-auth-account-b", "scope-auth-conv-b"),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conversation_id,
                "user_id": f"user-{conversation_id}",
                "text": "needs scoped operator",
                "mode": "echo",
            },
        )
        assert inbound_response.status_code == 200

    operator_headers = {
        "X-Actor-Id": "operator-scope-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "scope-auth-account-a",
    }

    messages_response = client.get(
        "/api/conversations/scope-auth-account-b/scope-auth-conv-b/messages",
        headers=operator_headers,
    )
    assert messages_response.status_code == 403
    assert "cannot access account 'scope-auth-account-b'" in messages_response.json()["detail"]

    assign_response = client.post(
        "/api/conversations/scope-auth-account-b/scope-auth-conv-b/assignment",
        headers=operator_headers,
        json={
            "agent_id": "operator-scope-a",
            "assigned_by_agent_id": "operator-scope-a",
            "reason": "cross_scope_assign",
        },
    )
    assert assign_response.status_code == 403
    assert "cannot access account 'scope-auth-account-b'" in assign_response.json()["detail"]

    close_response = client.post(
        "/api/conversations/scope-auth-account-b/scope-auth-conv-b/close",
        headers=operator_headers,
        json={
            "agent_id": "operator-scope-a",
            "reason": "cross_scope_close",
        },
    )
    assert close_response.status_code == 403
    assert "cannot access account 'scope-auth-account-b'" in close_response.json()["detail"]


def test_runtime_handover_rejects_missing_agent_and_illegal_transition(client: TestClient) -> None:
    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-guard-account-1",
            "conversation_id": "handover-guard-conv-1",
            "user_id": "handover-user-1",
            "text": "need a human",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    missing_agent_headers = {
        "X-Actor-Id": "missing-agent",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-guard-account-1",
    }
    missing_agent_response = client.post(
        "/api/runtime/conversations/handover-guard-conv-1/handover?account_id=handover-guard-account-1",
        headers=missing_agent_headers,
        json={
            "management_mode": "human_managed",
            "agent_id": "missing-agent",
            "reason": "manual_takeover",
        },
    )
    assert missing_agent_response.status_code == 404

    illegal_transition_response = client.post(
        "/api/runtime/conversations/handover-guard-conv-1/handover?account_id=handover-guard-account-1",
        headers=missing_agent_headers,
        json={
            "management_mode": "paused",
            "agent_id": "missing-agent",
            "reason": "manual_pause",
        },
    )
    assert illegal_transition_response.status_code == 400
    assert "Illegal management transition" in illegal_transition_response.json()["detail"]


def test_runtime_handover_requires_assigned_agent_identity_for_pause_and_resume(client: TestClient) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "handover-owner-1",
            "display_name": "Owner",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-owner-account-1",
            "conversation_id": "handover-owner-conv-1",
            "user_id": "handover-owner-user-1",
            "text": "need manual support",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-owner-account-1/handover-owner-conv-1/assignment",
        json={
            "agent_id": "handover-owner-1",
            "assigned_by_agent_id": "handover-owner-1",
            "reason": "takeover",
        },
    )
    assert assign_response.status_code == 200

    missing_actor_response = client.post(
        "/api/runtime/conversations/handover-owner-conv-1/handover?account_id=handover-owner-account-1",
        json={
            "management_mode": "paused",
            "reason": "manual_pause",
        },
    )
    assert missing_actor_response.status_code == 400
    assert "agent_id is required" in missing_actor_response.json()["detail"]

    pause_response = client.post(
        "/api/runtime/conversations/handover-owner-conv-1/handover?account_id=handover-owner-account-1",
        json={
            "management_mode": "paused",
            "agent_id": "handover-owner-1",
            "reason": "manual_pause",
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"

    resume_response = client.post(
        "/api/runtime/conversations/handover-owner-conv-1/handover?account_id=handover-owner-account-1",
        json={
            "management_mode": "ai_managed",
            "agent_id": "handover-owner-1",
            "reason": "resume_ai",
        },
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["management_mode"] == "ai_managed"
    assert resume_response.json()["assigned_agent_id"] is None

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "handover-owner-account-1",
            "action": "conversation_management_updated",
            "limit": 10,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert [item["payload"]["reason"] for item in audit_logs] == ["resume_ai", "manual_pause"]


def test_runtime_handover_resumes_manual_management_from_paused_state(client: TestClient) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "handover-resume-human-1",
            "display_name": "Resume Human Owner",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-resume-human-account-1",
            "conversation_id": "handover-resume-human-conv-1",
            "user_id": "handover-resume-human-user-1",
            "text": "pause and continue with manual handling",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-resume-human-account-1/handover-resume-human-conv-1/assignment",
        json={
            "agent_id": "handover-resume-human-1",
            "assigned_by_agent_id": "handover-resume-human-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    pause_response = client.post(
        "/api/runtime/conversations/handover-resume-human-conv-1/handover?account_id=handover-resume-human-account-1",
        json={
            "management_mode": "paused",
            "agent_id": "handover-resume-human-1",
            "reason": "manual_pause",
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"

    resume_response = client.post(
        "/api/runtime/conversations/handover-resume-human-conv-1/handover?account_id=handover-resume-human-account-1",
        json={
            "management_mode": "human_managed",
            "agent_id": "handover-resume-human-1",
        },
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["management_mode"] == "human_managed"
    assert resume_response.json()["assigned_agent_id"] == "handover-resume-human-1"
    assert resume_response.json()["status"] == "open"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "handover-resume-human-account-1",
            "action": "conversation_management_updated",
            "limit": 10,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert [item["payload"]["reason"] for item in audit_logs] == [
        "resume_human_management",
        "manual_pause",
    ]
    assert [item["payload"]["transition"] for item in audit_logs] == [
        "paused->human_managed",
        "human_managed->paused",
    ]


def test_assignment_route_uses_authenticated_actor_for_reassignment(
    strict_handover_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-implicit-reassign-1",
        "X-Actor-Role": "super_admin",
    }
    owner_headers = {
        "X-Actor-Id": "implicit-reassign-owner-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "implicit-reassign-account-1",
    }

    for agent_id, display_name in (
        ("implicit-reassign-owner-1", "Shift Owner"),
        ("implicit-reassign-target-1", "Shift Relief"),
    ):
        register_response = strict_handover_client.post(
            "/api/runtime/agents",
            headers=admin_headers,
            json={
                "account_id": "implicit-reassign-account-1",
                "agent_id": agent_id,
                "display_name": display_name,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = strict_handover_client.post(
        "/dev/mock/inbound-message",
        headers=admin_headers,
        json={
            "account_id": "implicit-reassign-account-1",
            "conversation_id": "implicit-reassign-conv-1",
            "user_id": "implicit-reassign-user-1",
            "text": "needs a reassignment",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = strict_handover_client.post(
        "/api/conversations/implicit-reassign-account-1/implicit-reassign-conv-1/assignment",
        headers=owner_headers,
        json={
            "agent_id": "implicit-reassign-owner-1",
            "assigned_by_agent_id": "implicit-reassign-owner-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    reassign_response = strict_handover_client.post(
        "/api/conversations/implicit-reassign-account-1/implicit-reassign-conv-1/assignment",
        headers=owner_headers,
        json={
            "agent_id": "implicit-reassign-target-1",
            "reason": "shift_change_reassign",
        },
    )
    assert reassign_response.status_code == 200
    reassign_payload = reassign_response.json()
    assert reassign_payload["management_mode"] == "human_managed"
    assert reassign_payload["assigned_agent_id"] == "implicit-reassign-target-1"
    assert reassign_payload["assigned_agent_name"] == "Shift Relief"

    audit_response = strict_handover_client.get(
        "/api/runtime/audit-logs",
        headers=owner_headers,
        params={
            "account_id": "implicit-reassign-account-1",
            "action": "conversation_assigned",
            "limit": 10,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert audit_logs[0]["actor_id"] == "implicit-reassign-owner-1"
    assert audit_logs[0]["payload"]["agent_id"] == "implicit-reassign-target-1"
    assert audit_logs[0]["payload"]["assigned_by_agent_id"] == "implicit-reassign-owner-1"
    assert audit_logs[0]["payload"]["reason"] == "shift_change_reassign"


def test_non_assigned_agent_cannot_pause_conversation(client: TestClient) -> None:
    owner_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "handover-pause-owner-1",
            "display_name": "Pause Owner",
            "status": "online",
            "is_active": True,
        },
    )
    assert owner_response.status_code == 200

    other_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "handover-pause-other-1",
            "display_name": "Pause Other",
            "status": "online",
            "is_active": True,
        },
    )
    assert other_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-pause-account-1",
            "conversation_id": "handover-pause-conv-1",
            "user_id": "handover-pause-user-1",
            "text": "need manual support",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-pause-account-1/handover-pause-conv-1/assignment",
        json={
            "agent_id": "handover-pause-owner-1",
            "assigned_by_agent_id": "handover-pause-owner-1",
            "reason": "takeover",
        },
    )
    assert assign_response.status_code == 200

    other_agent_headers = {
        "X-Actor-Id": "handover-pause-other-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-pause-account-1",
    }
    rogue_pause_response = client.post(
        "/api/runtime/conversations/handover-pause-conv-1/handover?account_id=handover-pause-account-1",
        headers=other_agent_headers,
        json={
            "management_mode": "paused",
            "agent_id": "handover-pause-other-1",
            "reason": "manual_pause",
        },
    )
    assert rogue_pause_response.status_code == 403
    assert "assigned to 'handover-pause-owner-1'" in rogue_pause_response.json()["detail"]

    owner_headers = {
        "X-Actor-Id": "handover-pause-owner-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-pause-account-1",
    }
    owner_pause_response = client.post(
        "/api/runtime/conversations/handover-pause-conv-1/handover?account_id=handover-pause-account-1",
        headers=owner_headers,
        json={
            "management_mode": "paused",
            "agent_id": "handover-pause-owner-1",
            "reason": "manual_pause",
        },
    )
    assert owner_pause_response.status_code == 200
    assert owner_pause_response.json()["management_mode"] == "paused"


def test_runtime_handover_rejects_cross_account_actor_scope_for_pause_and_resume(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "handover-cross-account-b",
            "agent_id": "handover-cross-owner-b",
            "display_name": "Cross Owner B",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-cross-account-b",
            "conversation_id": "handover-cross-conv-b",
            "user_id": "handover-cross-user-b",
            "text": "need account-b operator",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-cross-account-b/handover-cross-conv-b/assignment",
        json={
            "agent_id": "handover-cross-owner-b",
            "assigned_by_agent_id": "handover-cross-owner-b",
            "reason": "takeover",
        },
    )
    assert assign_response.status_code == 200

    cross_scope_headers = {
        "X-Actor-Id": "handover-cross-actor-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-cross-account-a",
    }
    pause_response = client.post(
        "/api/runtime/conversations/handover-cross-conv-b/handover?account_id=handover-cross-account-b",
        headers=cross_scope_headers,
        json={
            "management_mode": "paused",
            "agent_id": "handover-cross-actor-a",
            "reason": "manual_pause",
        },
    )
    assert pause_response.status_code == 403
    assert "cannot access account 'handover-cross-account-b'" in pause_response.json()["detail"]

    owner_pause_response = client.post(
        "/api/runtime/conversations/handover-cross-conv-b/handover?account_id=handover-cross-account-b",
        json={
            "management_mode": "paused",
            "agent_id": "handover-cross-owner-b",
            "reason": "manual_pause",
        },
    )
    assert owner_pause_response.status_code == 200

    resume_response = client.post(
        "/api/runtime/conversations/handover-cross-conv-b/handover?account_id=handover-cross-account-b",
        headers=cross_scope_headers,
        json={
            "management_mode": "ai_managed",
            "agent_id": "handover-cross-actor-a",
            "reason": "resume_ai",
        },
    )
    assert resume_response.status_code == 403
    assert "cannot access account 'handover-cross-account-b'" in resume_response.json()["detail"]


def test_close_conversation_restores_ai_managed_but_respects_ai_toggle_hierarchy(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "handover-hierarchy-agent-1",
            "display_name": "Hierarchy Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-hierarchy-account-1",
            "conversation_id": "handover-hierarchy-conv-1",
            "user_id": "handover-hierarchy-user-1",
            "text": "need an operator first",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-hierarchy-account-1/handover-hierarchy-conv-1/assignment",
        json={
            "agent_id": "handover-hierarchy-agent-1",
            "assigned_by_agent_id": "handover-hierarchy-agent-1",
            "reason": "takeover",
        },
    )
    assert assign_response.status_code == 200

    disable_account_ai_response = client.post(
        "/api/runtime/accounts/handover-hierarchy-account-1/ai",
        json={"enabled": False},
    )
    assert disable_account_ai_response.status_code == 200
    assert disable_account_ai_response.json()["ai_enabled"] is False

    close_response = client.post(
        "/api/conversations/handover-hierarchy-account-1/handover-hierarchy-conv-1/close",
        json={
            "agent_id": "handover-hierarchy-agent-1",
            "reason": "resolved",
        },
    )
    assert close_response.status_code == 200
    close_payload = close_response.json()
    assert close_payload["status"] == "closed"
    assert close_payload["management_mode"] == "ai_managed"
    assert close_payload["assigned_agent_id"] is None

    reopen_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-hierarchy-account-1",
            "conversation_id": "handover-hierarchy-conv-1",
            "user_id": "handover-hierarchy-user-1",
            "text": "back again, should still obey account AI toggle",
            "mode": "ai",
        },
    )
    assert reopen_response.status_code == 200
    reopen_payload = reopen_response.json()
    assert reopen_payload["runtime"]["management_mode"] == "ai_managed"
    assert reopen_payload["runtime"]["effective_ai_enabled"] is False
    assert reopen_payload["runtime"]["primary_blocking_reason"]["code"] == "account_ai_disabled"
    assert reopen_payload["queue"] is None


def test_closed_conversation_cannot_be_reassigned_or_closed_again(client: TestClient) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "closed-agent-1",
            "display_name": "Closer",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "closed-account-1",
            "conversation_id": "closed-conv-1",
            "user_id": "closed-user-1",
            "text": "close me",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/closed-account-1/closed-conv-1/assignment",
        json={
            "agent_id": "closed-agent-1",
            "assigned_by_agent_id": "closed-agent-1",
            "reason": "takeover",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        "/api/conversations/closed-account-1/closed-conv-1/close",
        json={
            "agent_id": "closed-agent-1",
            "reason": "resolved",
        },
    )
    assert close_response.status_code == 200

    second_close_response = client.post(
        "/api/conversations/closed-account-1/closed-conv-1/close",
        json={
            "agent_id": "closed-agent-1",
            "reason": "resolved_again",
        },
    )
    assert second_close_response.status_code == 409

    reassign_response = client.post(
        "/api/conversations/closed-account-1/closed-conv-1/assignment",
        json={
            "agent_id": "closed-agent-1",
            "assigned_by_agent_id": "closed-agent-1",
            "reason": "reassign_closed",
        },
    )
    assert reassign_response.status_code == 409


def test_non_assigned_agent_cannot_pause_or_resume_conversation_handover(client: TestClient) -> None:
    for agent_id, display_name in (
        ("pause-owner-1", "Pause Owner"),
        ("pause-other-1", "Pause Other"),
    ):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "agent_id": agent_id,
                "display_name": display_name,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "pause-auth-account-1",
            "conversation_id": "pause-auth-conv-1",
            "user_id": "pause-auth-user-1",
            "text": "need assigned operator",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/pause-auth-account-1/pause-auth-conv-1/assignment",
        json={
            "agent_id": "pause-owner-1",
            "assigned_by_agent_id": "pause-owner-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    other_agent_headers = {
        "X-Actor-Id": "pause-other-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "pause-auth-account-1",
    }
    blocked_pause_response = client.post(
        "/api/runtime/conversations/pause-auth-conv-1/handover?account_id=pause-auth-account-1",
        headers=other_agent_headers,
        json={
            "management_mode": "paused",
            "agent_id": "pause-other-1",
            "reason": "unauthorized_pause",
        },
    )
    assert blocked_pause_response.status_code == 403
    assert "assigned to 'pause-owner-1'" in blocked_pause_response.json()["detail"]

    owner_headers = {
        "X-Actor-Id": "pause-owner-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "pause-auth-account-1",
    }
    owner_pause_response = client.post(
        "/api/runtime/conversations/pause-auth-conv-1/handover?account_id=pause-auth-account-1",
        headers=owner_headers,
        json={
            "management_mode": "paused",
            "agent_id": "pause-owner-1",
            "reason": "authorized_pause",
        },
    )
    assert owner_pause_response.status_code == 200
    assert owner_pause_response.json()["management_mode"] == "paused"

    blocked_resume_response = client.post(
        "/api/runtime/conversations/pause-auth-conv-1/handover?account_id=pause-auth-account-1",
        headers=other_agent_headers,
        json={
            "management_mode": "ai_managed",
            "agent_id": "pause-other-1",
            "reason": "unauthorized_resume",
        },
    )
    assert blocked_resume_response.status_code == 403
    assert "assigned to 'pause-owner-1'" in blocked_resume_response.json()["detail"]


def test_runtime_handover_rejects_cross_account_pause_and_resume(client: TestClient) -> None:
    for account_id, agent_id in (
        ("handover-scope-account-a", "handover-scope-agent-a"),
        ("handover-scope-account-b", "handover-scope-agent-b"),
    ):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": account_id,
                "agent_id": agent_id,
                "display_name": agent_id,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-scope-account-b",
            "conversation_id": "handover-scope-conv-b",
            "user_id": "handover-scope-user-b",
            "text": "need scoped handover",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/handover-scope-account-b/handover-scope-conv-b/assignment",
        json={
            "agent_id": "handover-scope-agent-b",
            "assigned_by_agent_id": "handover-scope-agent-b",
            "reason": "scoped_takeover",
        },
    )
    assert assign_response.status_code == 200

    actor_a_headers = {
        "X-Actor-Id": "handover-scope-agent-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-scope-account-a",
    }

    blocked_pause_response = client.post(
        "/api/runtime/conversations/handover-scope-conv-b/handover?account_id=handover-scope-account-b",
        headers=actor_a_headers,
        json={
            "management_mode": "paused",
            "agent_id": "handover-scope-agent-a",
            "reason": "cross_scope_pause",
        },
    )
    assert blocked_pause_response.status_code == 403
    assert "cannot access account 'handover-scope-account-b'" in blocked_pause_response.json()["detail"]

    pause_response = client.post(
        "/api/runtime/conversations/handover-scope-conv-b/handover?account_id=handover-scope-account-b",
        json={
            "management_mode": "paused",
            "agent_id": "handover-scope-agent-b",
            "reason": "owner_pause",
        },
    )
    assert pause_response.status_code == 200

    blocked_resume_response = client.post(
        "/api/runtime/conversations/handover-scope-conv-b/handover?account_id=handover-scope-account-b",
        headers=actor_a_headers,
        json={
            "management_mode": "ai_managed",
            "agent_id": "handover-scope-agent-a",
            "reason": "cross_scope_resume",
        },
    )
    assert blocked_resume_response.status_code == 403
    assert "cannot access account 'handover-scope-account-b'" in blocked_resume_response.json()["detail"]


def test_runtime_handover_rejects_cross_account_resume_human_management_for_same_agent_id(
    strict_handover_client: TestClient,
) -> None:
    admin_headers = {
        "X-Actor-Id": "admin-handover-resume-human-scope",
        "X-Actor-Role": "super_admin",
    }
    owner_account_a_headers = {
        "X-Actor-Id": "shared-handover-owner",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-resume-human-account-a",
    }
    owner_account_b_headers = {
        "X-Actor-Id": "shared-handover-owner",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "handover-resume-human-account-b",
    }

    for account_id in (
        "handover-resume-human-account-a",
        "handover-resume-human-account-b",
    ):
        register_response = strict_handover_client.post(
            "/api/runtime/agents",
            json={
                "account_id": account_id,
                "agent_id": "shared-handover-owner",
                "display_name": f"Shared Owner {account_id[-1].upper()}",
                "status": "online",
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert register_response.status_code == 200

    inbound_response = strict_handover_client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "handover-resume-human-account-b",
            "conversation_id": "handover-resume-human-conv-b",
            "user_id": "handover-resume-human-user-b",
            "text": "pause and resume manual handling",
            "mode": "echo",
        },
        headers=admin_headers,
    )
    assert inbound_response.status_code == 200

    assign_response = strict_handover_client.post(
        "/api/conversations/handover-resume-human-account-b/handover-resume-human-conv-b/assignment",
        json={
            "agent_id": "shared-handover-owner",
            "reason": "manual_takeover",
        },
        headers=owner_account_b_headers,
    )
    assert assign_response.status_code == 200

    pause_response = strict_handover_client.post(
        "/api/runtime/conversations/handover-resume-human-conv-b/handover?account_id=handover-resume-human-account-b",
        json={
            "management_mode": "paused",
            "agent_id": "shared-handover-owner",
            "reason": "manual_pause",
        },
        headers=owner_account_b_headers,
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"

    blocked_resume_response = strict_handover_client.post(
        "/api/runtime/conversations/handover-resume-human-conv-b/handover?account_id=handover-resume-human-account-b",
        json={
            "management_mode": "human_managed",
            "agent_id": "shared-handover-owner",
            "reason": "resume_human_management",
        },
        headers=owner_account_a_headers,
    )
    assert blocked_resume_response.status_code == 403
    assert (
        "cannot access account 'handover-resume-human-account-b'"
        in blocked_resume_response.json()["detail"]
    )

    resume_response = strict_handover_client.post(
        "/api/runtime/conversations/handover-resume-human-conv-b/handover?account_id=handover-resume-human-account-b",
        json={
            "management_mode": "human_managed",
            "agent_id": "shared-handover-owner",
            "reason": "resume_human_management",
        },
        headers=owner_account_b_headers,
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["management_mode"] == "human_managed"
    assert resume_response.json()["assigned_agent_id"] == "shared-handover-owner"


def test_runtime_handover_resume_human_management_keeps_assignment_and_audit_reason(
    client: TestClient,
) -> None:
    for agent_id, display_name in (
        ("resume-human-owner-1", "Resume Human Owner"),
        ("resume-human-other-1", "Resume Human Other"),
    ):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "resume-human-account-1",
                "agent_id": agent_id,
                "display_name": display_name,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "resume-human-account-1",
            "conversation_id": "resume-human-conv-1",
            "user_id": "resume-human-user-1",
            "text": "pause and return to manual handling",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/resume-human-account-1/resume-human-conv-1/assignment",
        json={
            "agent_id": "resume-human-owner-1",
            "assigned_by_agent_id": "resume-human-owner-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    owner_headers = {
        "X-Actor-Id": "resume-human-owner-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "resume-human-account-1",
    }
    pause_response = client.post(
        "/api/runtime/conversations/resume-human-conv-1/handover?account_id=resume-human-account-1",
        headers=owner_headers,
        json={
            "management_mode": "paused",
            "agent_id": "resume-human-owner-1",
            "reason": "manual_pause",
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"
    assert pause_response.json()["assigned_agent_id"] == "resume-human-owner-1"

    resume_response = client.post(
        "/api/runtime/conversations/resume-human-conv-1/handover?account_id=resume-human-account-1",
        headers=owner_headers,
        json={
            "management_mode": "human_managed",
            "agent_id": "resume-human-owner-1",
            "reason": "resume_human_management",
        },
    )
    assert resume_response.status_code == 200
    resume_payload = resume_response.json()
    assert resume_payload["status"] == "open"
    assert resume_payload["management_mode"] == "human_managed"
    assert resume_payload["assigned_agent_id"] == "resume-human-owner-1"

    blocked_pause_response = client.post(
        "/api/runtime/conversations/resume-human-conv-1/handover?account_id=resume-human-account-1",
        headers={
            "X-Actor-Id": "resume-human-other-1",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "resume-human-account-1",
        },
        json={
            "management_mode": "paused",
            "agent_id": "resume-human-other-1",
            "reason": "unauthorized_pause_after_resume",
        },
    )
    assert blocked_pause_response.status_code == 403
    assert "assigned to 'resume-human-owner-1'" in blocked_pause_response.json()["detail"]

    audit_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "resume-human-account-1",
            "action": "conversation_management_updated",
            "target_id": "resume-human-conv-1",
            "limit": 10,
        },
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    assert len(audit_logs) == 2
    assert audit_logs[0]["payload"]["transition"] == "paused->human_managed"
    assert audit_logs[0]["payload"]["reason"] == "resume_human_management"
    assert audit_logs[0]["payload"]["assigned_agent_id"] == "resume-human-owner-1"
    assert audit_logs[1]["payload"]["transition"] == "human_managed->paused"
    assert audit_logs[1]["payload"]["reason"] == "manual_pause"


def test_support_agent_can_use_actor_identity_for_handover_and_close_without_agent_id(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": "implicit-actor-account-1",
            "agent_id": "implicit-actor-agent-1",
            "display_name": "Implicit Actor Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "implicit-actor-account-1",
            "conversation_id": "implicit-actor-conv-1",
            "user_id": "implicit-actor-user-1",
            "text": "support agent identity should be enough",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/implicit-actor-account-1/implicit-actor-conv-1/assignment",
        json={
            "agent_id": "implicit-actor-agent-1",
            "assigned_by_agent_id": "implicit-actor-agent-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    support_agent_headers = {
        "X-Actor-Id": "implicit-actor-agent-1",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "implicit-actor-account-1",
    }

    pause_response = client.post(
        "/api/runtime/conversations/implicit-actor-conv-1/handover?account_id=implicit-actor-account-1",
        headers=support_agent_headers,
        json={
            "management_mode": "paused",
            "reason": "pause_with_actor_identity",
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["management_mode"] == "paused"
    assert pause_response.json()["assigned_agent_id"] == "implicit-actor-agent-1"

    resume_response = client.post(
        "/api/runtime/conversations/implicit-actor-conv-1/handover?account_id=implicit-actor-account-1",
        headers=support_agent_headers,
        json={
            "management_mode": "human_managed",
            "reason": "resume_with_actor_identity",
        },
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["management_mode"] == "human_managed"
    assert resume_response.json()["assigned_agent_id"] == "implicit-actor-agent-1"

    close_response = client.post(
        "/api/conversations/implicit-actor-account-1/implicit-actor-conv-1/close",
        headers=support_agent_headers,
        json={"reason": "close_with_actor_identity"},
    )
    assert close_response.status_code == 200
    close_payload = close_response.json()
    assert close_payload["status"] == "closed"
    assert close_payload["management_mode"] == "ai_managed"
    assert close_payload["assigned_agent_id"] is None


@pytest.mark.parametrize(
    ("disabled_scope", "expected_code"),
    [
        ("global", "global_ai_disabled"),
        ("account", "account_ai_disabled"),
        ("conversation", "conversation_ai_disabled"),
    ],
)
def test_close_returns_ai_managed_but_reopened_effective_ai_still_respects_disabled_switches(
    client: TestClient,
    disabled_scope: str,
    expected_code: str,
) -> None:
    account_id = f"close-switch-account-{disabled_scope}"
    conversation_id = f"close-switch-conv-{disabled_scope}"
    agent_id = f"close-switch-agent-{disabled_scope}"
    user_id = f"close-switch-user-{disabled_scope}"

    register_response = client.post(
        "/api/runtime/agents",
        json={
            "account_id": account_id,
            "agent_id": agent_id,
            "display_name": f"Closer {disabled_scope}",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "text": "manual first, ai later",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    if disabled_scope == "global":
        toggle_response = client.post("/api/runtime/ai/global", json={"enabled": False})
    elif disabled_scope == "account":
        toggle_response = client.post(
            f"/api/runtime/accounts/{account_id}/ai",
            json={"enabled": False},
        )
    else:
        toggle_response = client.post(
            f"/api/runtime/conversations/{conversation_id}/ai?account_id={account_id}",
            json={"enabled": False},
        )
    assert toggle_response.status_code == 200

    assign_response = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/assignment",
        json={
            "agent_id": agent_id,
            "assigned_by_agent_id": agent_id,
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/close",
        json={
            "agent_id": agent_id,
            "reason": "return_to_ai",
        },
    )
    assert close_response.status_code == 200
    close_payload = close_response.json()
    assert close_payload["status"] == "closed"
    assert close_payload["management_mode"] == "ai_managed"
    assert close_payload["assigned_agent_id"] is None

    ai_status_response = client.get(
        f"/api/runtime/conversations/{conversation_id}/ai-status",
        params={"account_id": account_id},
    )
    assert ai_status_response.status_code == 200
    ai_status_payload = ai_status_response.json()
    assert ai_status_payload["management_mode"] == "ai_managed"
    assert ai_status_payload["effective_ai_enabled"] is False
    assert ai_status_payload["primary_blocking_reason"]["code"] == expected_code

    reopen_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "text": "reopen and check ai switch",
            "mode": "ai",
        },
    )
    assert reopen_response.status_code == 200
    reopen_payload = reopen_response.json()
    assert reopen_payload["runtime"]["management_mode"] == "ai_managed"
    assert reopen_payload["runtime"]["effective_ai_enabled"] is False
    assert reopen_payload["runtime"]["primary_blocking_reason"]["code"] == expected_code
    assert reopen_payload["queue"] is None
    assert reopen_payload["outbound"]["text"] is None


def test_non_assigned_agent_cannot_toggle_conversation_ai_for_manually_assigned_conversation(
    client: TestClient,
) -> None:
    for agent_id, display_name in (
        ("toggle-owner-1", "Toggle Owner"),
        ("toggle-other-1", "Toggle Other"),
    ):
        register_response = client.post(
            "/api/runtime/agents",
            json={
                "account_id": "toggle-ai-account-1",
                "agent_id": agent_id,
                "display_name": display_name,
                "status": "online",
                "is_active": True,
            },
        )
        assert register_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "toggle-ai-account-1",
            "conversation_id": "toggle-ai-conv-1",
            "user_id": "toggle-ai-user-1",
            "text": "manual owner only",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/toggle-ai-account-1/toggle-ai-conv-1/assignment",
        json={
            "agent_id": "toggle-owner-1",
            "assigned_by_agent_id": "toggle-owner-1",
            "reason": "manual_takeover",
        },
    )
    assert assign_response.status_code == 200

    blocked_toggle_response = client.post(
        "/api/runtime/conversations/toggle-ai-conv-1/ai?account_id=toggle-ai-account-1",
        headers={
            "X-Actor-Id": "toggle-other-1",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "toggle-ai-account-1",
        },
        json={"enabled": False},
    )
    assert blocked_toggle_response.status_code == 403
    assert "assigned to 'toggle-owner-1'" in blocked_toggle_response.json()["detail"]

    owner_toggle_response = client.post(
        "/api/runtime/conversations/toggle-ai-conv-1/ai?account_id=toggle-ai-account-1",
        headers={
            "X-Actor-Id": "toggle-owner-1",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "toggle-ai-account-1",
        },
        json={"enabled": False},
    )
    assert owner_toggle_response.status_code == 200
    assert owner_toggle_response.json()["ai_enabled"] is False

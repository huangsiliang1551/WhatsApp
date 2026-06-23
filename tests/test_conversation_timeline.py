from fastapi.testclient import TestClient


def test_conversation_timeline_merges_audit_handover_and_message_events(
    client: TestClient,
) -> None:
    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "timeline-agent-1",
            "display_name": "Timeline Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "timeline-account-1",
            "conversation_id": "timeline-conv-1",
            "user_id": "timeline-user-1",
            "text": "I want to talk to a human agent now.",
            "mode": "ai",
            "language_hint": "en",
        },
    )
    assert inbound_response.status_code == 200

    other_conversation_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "timeline-account-1",
            "conversation_id": "timeline-conv-2",
            "user_id": "timeline-user-2",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
        },
    )
    assert other_conversation_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/timeline-account-1/timeline-conv-1/assignment",
        json={
            "agent_id": "timeline-agent-1",
            "assigned_by_agent_id": "timeline-agent-1",
            "reason": "timeline_review",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        "/api/conversations/timeline-account-1/timeline-conv-1/close",
        json={
            "agent_id": "timeline-agent-1",
            "reason": "timeline_resolved",
        },
    )
    assert close_response.status_code == 200

    timeline_response = client.get(
        "/api/conversations/timeline-account-1/timeline-conv-1/timeline",
        params={"limit": 20},
    )
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()

    assert timeline
    item_types = {item["item_type"] for item in timeline}
    assert "audit" in item_types
    assert "handover" in item_types
    assert "message_event" in item_types

    labels = {item["label"] for item in timeline}
    assert "audit" in labels
    assert "handover" in labels
    assert "event" in labels

    titles = {item["title"] for item in timeline}
    assert "mock_inbound_received" in titles
    assert "conversation_assigned" in titles
    assert "conversation_closed" in titles
    assert "human_managed -> ai_managed" in titles

    serialized_payload = " ".join(str(item["payload"]) for item in timeline if item["payload"])
    assert "timeline_review" in serialized_payload
    assert "timeline_resolved" in serialized_payload
    assert "customer_requested_human_support" in serialized_payload
    assert "timeline-conv-2" not in serialized_payload

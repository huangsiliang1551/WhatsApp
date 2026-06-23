from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import WhatsAppBusinessAccount
from app.services.runtime_state import RuntimeStateStore


def test_runtime_and_meta_operations_are_written_to_audit_log(client: TestClient) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "audit-account-1",
            "display_name": "Audit Account",
            "provider_type": "whatsapp",
        },
    )
    assert register_account_response.status_code == 200

    account_ai_response = client.post(
        "/api/runtime/accounts/audit-account-1/ai",
        json={"enabled": False},
    )
    assert account_ai_response.status_code == 200

    embedded_signup_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "audit-account-1",
            "display_name": "Audit Account",
            "redirect_uri": "https://example.com/audit/callback",
        },
    )
    assert embedded_signup_response.status_code == 200
    session_id = embedded_signup_response.json()["session_id"]

    fail_signup_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/fail",
        json={
            "error_message": "operator_stopped_flow",
            "event_source": "operator",
            "raw_payload": {"reason": "operator_override"},
        },
    )
    assert fail_signup_response.status_code == 200

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": "audit-account-1", "limit": 20},
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()

    actions = {item["action"] for item in audit_logs}
    assert "account_created" in actions
    assert "account_ai_updated" in actions
    assert "embedded_signup_session_created" in actions
    assert "embedded_signup_session_failed" in actions

    filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-1",
            "action": "embedded_signup_session_failed",
            "limit": 10,
        },
    )
    assert filtered_response.status_code == 200
    filtered_logs = filtered_response.json()

    assert len(filtered_logs) == 1
    assert filtered_logs[0]["payload"]["error_message"] == "operator_stopped_flow"
    assert filtered_logs[0]["payload"]["event_source"] == "operator"
    assert filtered_logs[0]["payload"]["raw_payload_present"] is True
    assert filtered_logs[0]["target_type"] == "embedded_signup_session"


def test_handover_actions_are_queryable_from_audit_log(client: TestClient) -> None:
    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "audit-agent-1",
            "display_name": "Auditor",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-account-2",
            "conversation_id": "audit-conv-2",
            "user_id": "audit-user-2",
            "text": "need audit trail",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/audit-account-2/audit-conv-2/assignment",
        json={
            "agent_id": "audit-agent-1",
            "assigned_by_agent_id": "audit-agent-1",
            "reason": "audit_review",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        "/api/conversations/audit-account-2/audit-conv-2/close",
        json={
            "agent_id": "audit-agent-1",
            "reason": "resolved_after_review",
        },
    )
    assert close_response.status_code == 200

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": "audit-account-2", "limit": 20},
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()

    actions = [item["action"] for item in audit_logs]
    assert "conversation_assigned" in actions
    assert "conversation_closed" in actions
    assigned_log = next(item for item in audit_logs if item["action"] == "conversation_assigned")
    closed_log = next(item for item in audit_logs if item["action"] == "conversation_closed")
    assert assigned_log["payload"]["reason"] == "audit_review"
    assert assigned_log["payload"]["status_before"] == "open"
    assert assigned_log["payload"]["status_after"] == "open"
    assert closed_log["payload"]["reason"] == "resolved_after_review"
    assert closed_log["payload"]["status_before"] == "open"
    assert closed_log["payload"]["status_after"] == "closed"

    actor_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-2",
            "actor_type": assigned_log["actor_type"],
            "limit": 20,
        },
    )
    assert actor_filtered_response.status_code == 200
    actor_filtered_logs = actor_filtered_response.json()
    assert len(actor_filtered_logs) >= 2
    assert all(item["actor_type"] == assigned_log["actor_type"] for item in actor_filtered_logs)


def test_audit_logs_support_actor_target_and_date_filters(client: TestClient) -> None:
    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "audit-agent-3",
            "display_name": "Auditor Three",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-account-3",
            "conversation_id": "audit-conv-3",
            "user_id": "audit-user-3",
            "text": "filter audit trail",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/audit-account-3/audit-conv-3/assignment",
        json={
            "agent_id": "audit-agent-3",
            "assigned_by_agent_id": "audit-agent-3",
            "reason": "actor_target_filter_review",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        "/api/conversations/audit-account-3/audit-conv-3/close",
        json={
            "agent_id": "audit-agent-3",
            "reason": "actor_target_filter_resolved",
        },
    )
    assert close_response.status_code == 200

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": "audit-account-3", "limit": 50},
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()

    assigned_log = next(item for item in audit_logs if item["action"] == "conversation_assigned")
    closed_log = next(item for item in audit_logs if item["action"] == "conversation_closed")
    created_at_values = [datetime.fromisoformat(item["created_at"]) for item in audit_logs]
    earliest_created_at = min(created_at_values)
    latest_created_at = max(created_at_values)

    actor_id_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-3",
            "actor_id": assigned_log["actor_id"],
            "limit": 50,
        },
    )
    assert actor_id_filtered_response.status_code == 200
    actor_id_filtered_logs = actor_id_filtered_response.json()

    assert len(actor_id_filtered_logs) >= 2
    assert all(item["actor_id"] == assigned_log["actor_id"] for item in actor_id_filtered_logs)

    target_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-3",
            "target_type": closed_log["target_type"],
            "target_id": closed_log["target_id"],
            "limit": 50,
        },
    )
    assert target_filtered_response.status_code == 200
    target_filtered_logs = target_filtered_response.json()

    assert len(target_filtered_logs) >= 2
    assert all(item["target_type"] == "conversation" for item in target_filtered_logs)
    assert all(item["target_id"] == "audit-conv-3" for item in target_filtered_logs)

    future_range_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-3",
            "date_from": (latest_created_at + timedelta(days=1)).date().isoformat(),
            "limit": 50,
        },
    )
    assert future_range_response.status_code == 200
    assert future_range_response.json() == []

    past_range_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-3",
            "date_to": (earliest_created_at - timedelta(days=1)).date().isoformat(),
            "limit": 50,
        },
    )
    assert past_range_response.status_code == 200
    assert past_range_response.json() == []

    invalid_range_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-account-3",
            "date_from": latest_created_at.date().isoformat(),
            "date_to": (latest_created_at - timedelta(days=1)).date().isoformat(),
            "limit": 50,
        },
    )
    assert invalid_range_response.status_code == 400


def test_audit_logs_support_phone_number_filter_from_payload(client: TestClient) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "audit-phone-account-1",
            "display_name": "Audit Phone Account",
            "meta_business_portfolio_id": "portfolio-audit-phone-1",
            "waba_id": "waba-audit-phone-1",
            "access_token": "token-audit-phone-1",
            "verify_token": "verify-audit-phone-1",
            "app_secret": "secret-audit-phone-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-audit-1",
                    "display_phone_number": "+1 555 200 0001",
                    "verified_name": "Audit Number 1",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
                {
                    "phone_number_id": "pn-audit-2",
                    "display_phone_number": "+1 555 200 0002",
                    "verified_name": "Audit Number 2",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                },
            ],
        },
    )
    assert manual_account_response.status_code == 200

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "audit-phone-agent-1",
            "display_name": "Phone Auditor",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_one = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-phone-account-1",
            "conversation_id": "audit-phone-conv-1",
            "user_id": "audit-phone-user-1",
            "text": "first phone audit",
            "mode": "echo",
            "phone_number_id": "pn-audit-1",
        },
    )
    assert inbound_one.status_code == 200
    inbound_two = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-phone-account-1",
            "conversation_id": "audit-phone-conv-2",
            "user_id": "audit-phone-user-2",
            "text": "second phone audit",
            "mode": "echo",
            "phone_number_id": "pn-audit-2",
        },
    )
    assert inbound_two.status_code == 200

    assign_one = client.post(
        "/api/conversations/audit-phone-account-1/audit-phone-conv-1/assignment",
        json={
            "agent_id": "audit-phone-agent-1",
            "assigned_by_agent_id": "audit-phone-agent-1",
            "reason": "phone_scope_first",
        },
    )
    assert assign_one.status_code == 200
    assign_two = client.post(
        "/api/conversations/audit-phone-account-1/audit-phone-conv-2/assignment",
        json={
            "agent_id": "audit-phone-agent-1",
            "assigned_by_agent_id": "audit-phone-agent-1",
            "reason": "phone_scope_second",
        },
    )
    assert assign_two.status_code == 200

    filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-phone-account-1",
            "phone_number_id": "pn-audit-1",
            "limit": 50,
        },
    )
    assert filtered_response.status_code == 200
    filtered_logs = filtered_response.json()

    assert filtered_logs
    assert all(item["phone_number_id"] == "pn-audit-1" for item in filtered_logs)
    assert all(item["waba_id"] == "waba-audit-phone-1" for item in filtered_logs)
    assert any(item["action"] == "conversation_assigned" for item in filtered_logs)
    assert any(item["action"] == "support_intent_evaluated" for item in filtered_logs)
    assert all(item["payload"]["phone_number_id"] == "pn-audit-1" for item in filtered_logs)
    assert all(item["payload"]["waba_id"] == "waba-audit-phone-1" for item in filtered_logs)


def test_audit_logs_support_waba_filter_from_payload_and_target(client: TestClient) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "audit-waba-account-1",
            "display_name": "Audit WABA Account",
            "meta_business_portfolio_id": "portfolio-audit-waba-1",
            "waba_id": "waba-audit-filter-1",
            "access_token": "token-audit-waba-1",
            "verify_token": "verify-audit-waba-1",
            "app_secret": "secret-audit-waba-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-audit-waba-1",
                    "display_phone_number": "+1 555 201 0001",
                    "verified_name": "Audit WABA Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "audit-waba-agent-1",
            "display_name": "WABA Auditor",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-waba-account-1",
            "conversation_id": "audit-waba-conv-1",
            "user_id": "audit-waba-user-1",
            "text": "waba filtered audit",
            "mode": "echo",
            "phone_number_id": "pn-audit-waba-1",
        },
    )
    assert inbound_response.status_code == 200

    assign_response = client.post(
        "/api/conversations/audit-waba-account-1/audit-waba-conv-1/assignment",
        json={
            "agent_id": "audit-waba-agent-1",
            "assigned_by_agent_id": "audit-waba-agent-1",
            "reason": "waba_scope_first",
        },
    )
    assert assign_response.status_code == 200

    filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-waba-account-1",
            "waba_id": "waba-audit-filter-1",
            "limit": 50,
        },
    )
    assert filtered_response.status_code == 200
    filtered_logs = filtered_response.json()

    assert filtered_logs
    assert any(item["action"] == "conversation_assigned" for item in filtered_logs)
    assert any(item["action"] == "support_intent_evaluated" for item in filtered_logs)
    assert any(item["action"] == "meta_manual_account_upserted" for item in filtered_logs)
    assert all(item["waba_id"] == "waba-audit-filter-1" for item in filtered_logs)
    assert all(
        item["payload"].get("waba_id") == "waba-audit-filter-1"
        if isinstance(item.get("payload"), dict)
        and item["action"] != "meta_manual_account_upserted"
        else True
        for item in filtered_logs
    )


def test_audit_logs_keep_phone_snapshot_waba_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "audit-waba-snapshot-account-1",
            "display_name": "Audit WABA Snapshot Account",
            "meta_business_portfolio_id": "portfolio-audit-waba-snapshot-1",
            "waba_id": "waba-audit-snapshot-1",
            "access_token": "token-audit-waba-snapshot-1",
            "verify_token": "verify-audit-waba-snapshot-1",
            "app_secret": "secret-audit-waba-snapshot-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-audit-snapshot-1",
                    "display_phone_number": "+1 555 202 0001",
                    "verified_name": "Audit Snapshot Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "audit-waba-snapshot-agent-1",
            "display_name": "WABA Snapshot Auditor",
            "status": "online",
            "is_active": True,
        },
    )
    assert agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "audit-waba-snapshot-account-1",
            "conversation_id": "audit-waba-snapshot-conv-1",
            "user_id": "audit-waba-snapshot-user-1",
            "text": "snapshot audit",
            "mode": "echo",
            "phone_number_id": "pn-audit-snapshot-1",
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "audit-waba-snapshot-account-1",
                WhatsAppBusinessAccount.waba_id == "waba-audit-snapshot-1",
            )
            .one()
        )
        waba_account.waba_id = "waba-audit-snapshot-drifted-1"
        session.commit()
    finally:
        session.close()

    assign_response = client.post(
        "/api/conversations/audit-waba-snapshot-account-1/audit-waba-snapshot-conv-1/assignment",
        json={
            "agent_id": "audit-waba-snapshot-agent-1",
            "assigned_by_agent_id": "audit-waba-snapshot-agent-1",
            "reason": "snapshot_scope_assignment",
        },
    )
    assert assign_response.status_code == 200

    close_response = client.post(
        "/api/conversations/audit-waba-snapshot-account-1/audit-waba-snapshot-conv-1/close",
        json={
            "agent_id": "audit-waba-snapshot-agent-1",
            "reason": "snapshot_scope_closed",
        },
    )
    assert close_response.status_code == 200

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": "audit-waba-snapshot-account-1", "limit": 50},
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()

    assigned_log = next(item for item in audit_logs if item["action"] == "conversation_assigned")
    closed_log = next(item for item in audit_logs if item["action"] == "conversation_closed")
    assert assigned_log["waba_id"] == "waba-audit-snapshot-1"
    assert assigned_log["payload"]["waba_id"] == "waba-audit-snapshot-1"
    assert closed_log["waba_id"] == "waba-audit-snapshot-1"
    assert closed_log["payload"]["waba_id"] == "waba-audit-snapshot-1"

    filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-waba-snapshot-account-1",
            "waba_id": "waba-audit-snapshot-1",
            "limit": 50,
        },
    )
    assert filtered_response.status_code == 200
    filtered_logs = filtered_response.json()
    assert any(item["action"] == "conversation_assigned" for item in filtered_logs)
    assert any(item["action"] == "conversation_closed" for item in filtered_logs)
    assert all(item["waba_id"] == "waba-audit-snapshot-1" for item in filtered_logs)

    drifted_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-waba-snapshot-account-1",
            "waba_id": "waba-audit-snapshot-drifted-1",
            "limit": 50,
        },
    )
    assert drifted_filtered_response.status_code == 200
    drifted_actions = {item["action"] for item in drifted_filtered_response.json()}
    assert "conversation_assigned" not in drifted_actions
    assert "conversation_closed" not in drifted_actions


def test_audit_logs_filter_nested_scope_payload_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    manual_account_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "audit-nested-scope-account-1",
            "display_name": "Audit Nested Scope Account",
            "meta_business_portfolio_id": "portfolio-audit-nested-scope-1",
            "waba_id": "waba-audit-nested-scope-1",
            "access_token": "token-audit-nested-scope-1",
            "verify_token": "verify-audit-nested-scope-1",
            "app_secret": "secret-audit-nested-scope-1",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "pn-audit-nested-scope-1",
                    "display_phone_number": "+1 555 202 0001",
                    "verified_name": "Audit Nested Scope Number",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert manual_account_response.status_code == 200

    with db_session_factory() as session:
        runtime_state = RuntimeStateStore(session)
        runtime_state.add_audit_log(
            account_id="audit-nested-scope-account-1",
            actor_type="system",
            actor_id="nested-scope-audit",
            action="nested_scope_audit_recorded",
            target_type="conversation",
            target_id="conv-audit-nested-scope-1",
            payload={
                "provider_payload": {
                    "waba_id": "waba-audit-nested-scope-1",
                    "metadata": {
                        "phone_number_id": "pn-audit-nested-scope-1",
                    },
                }
            },
        )
        session.commit()

    waba_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-nested-scope-account-1",
            "waba_id": "waba-audit-nested-scope-1",
            "action": "nested_scope_audit_recorded",
            "limit": 20,
        },
    )
    assert waba_filtered_response.status_code == 200
    waba_filtered_logs = waba_filtered_response.json()
    assert len(waba_filtered_logs) == 1
    assert waba_filtered_logs[0]["action"] == "nested_scope_audit_recorded"
    assert waba_filtered_logs[0]["waba_id"] == "waba-audit-nested-scope-1"
    assert waba_filtered_logs[0]["phone_number_id"] == "pn-audit-nested-scope-1"

    phone_filtered_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "audit-nested-scope-account-1",
            "phone_number_id": "pn-audit-nested-scope-1",
            "action": "nested_scope_audit_recorded",
            "limit": 20,
        },
    )
    assert phone_filtered_response.status_code == 200
    phone_filtered_logs = phone_filtered_response.json()
    assert len(phone_filtered_logs) == 1
    assert phone_filtered_logs[0]["action"] == "nested_scope_audit_recorded"
    assert phone_filtered_logs[0]["waba_id"] == "waba-audit-nested-scope-1"
    assert phone_filtered_logs[0]["phone_number_id"] == "pn-audit-nested-scope-1"


def test_support_knowledge_import_and_export_are_queryable_from_audit_log(
    client: TestClient,
) -> None:
    register_account_response = client.post(
        "/api/runtime/accounts",
        json={
            "account_id": "audit-knowledge-1",
            "display_name": "Audit Knowledge",
            "provider_type": "mock",
        },
    )
    assert register_account_response.status_code == 200

    create_response = client.post(
        "/api/runtime/support-knowledge",
        json={
            "account_id": "audit-knowledge-1",
            "article_id": "kb-audit-transfer-1",
            "route_name": "faq_audit_transfer",
            "category": "faq",
            "title": "Audit transfer answer",
            "answer": "Audit export and import path.",
            "source_language": "en",
            "keywords": ["audit transfer"],
            "minimum_score": 1,
            "priority": 9,
            "is_active": True,
        },
    )
    assert create_response.status_code == 200

    export_response = client.get(
        "/api/runtime/support-knowledge/export",
        params={"account_id": "audit-knowledge-1"},
    )
    assert export_response.status_code == 200
    entries = export_response.json()["entries"]

    delete_response = client.delete(
        "/api/runtime/support-knowledge/kb-audit-transfer-1",
        params={"account_id": "audit-knowledge-1"},
    )
    assert delete_response.status_code == 200

    import_response = client.post(
        "/api/runtime/support-knowledge/import",
        json={
            "entries": entries,
            "upsert_existing": True,
        },
    )
    assert import_response.status_code == 200

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": "audit-knowledge-1", "limit": 20},
    )
    assert audit_logs_response.status_code == 200
    actions = [item["action"] for item in audit_logs_response.json()]

    assert "support_knowledge_exported" in actions
    assert "support_knowledge_imported" in actions

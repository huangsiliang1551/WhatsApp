import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    Conversation,
    Message,
    MessageEvent,
    WhatsAppBusinessAccount,
    WhatsAppConversationStat,
    WhatsAppDailyStat,
    WhatsAppPhoneNumber,
)
from app.providers.messaging.whatsapp_provider import WhatsAppProvider
from app.services.whatsapp_analytics_service import WhatsAppAnalyticsService
from app.services.whatsapp_stats_aggregator import WhatsAppStatsAggregator


def register_whatsapp_analytics_account(
    client: TestClient,
    *,
    account_id: str = "wa-analytics-account-1",
    display_name: str = "WhatsApp Analytics Account",
    portfolio_id: str = "portfolio-wa-analytics-1",
    waba_id: str = "waba-wa-analytics-1",
    phone_number_id: str = "pn-wa-analytics-1",
    access_token: str = "token-wa-analytics-1",
    verify_token: str = "verify-wa-analytics-1",
    app_secret: str = "secret-wa-analytics-1",
    phone_numbers: list[dict[str, object]] | None = None,
) -> None:
    response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": account_id,
            "display_name": display_name,
            "meta_business_portfolio_id": portfolio_id,
            "waba_id": waba_id,
            "access_token": access_token,
            "verify_token": verify_token,
            "app_secret": app_secret,
            "token_source": "system_user",
            "phone_numbers": phone_numbers
            or [
                {
                    "phone_number_id": phone_number_id,
                    "display_phone_number": "+1 555 200 0001",
                    "verified_name": display_name,
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def test_whatsapp_stats_meta_filters_do_not_bypass_operator_account_scope(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-scope-a",
        display_name="WA Analytics Scope A",
        portfolio_id="portfolio-wa-analytics-scope-a",
        waba_id="waba-wa-analytics-scope-a",
        phone_number_id="pn-wa-analytics-scope-a",
        access_token="token-wa-analytics-scope-a",
        verify_token="verify-wa-analytics-scope-a",
        app_secret="secret-wa-analytics-scope-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-scope-b",
        display_name="WA Analytics Scope B",
        portfolio_id="portfolio-wa-analytics-scope-b",
        waba_id="waba-wa-analytics-scope-b",
        phone_number_id="pn-wa-analytics-scope-b",
        access_token="token-wa-analytics-scope-b",
        verify_token="verify-wa-analytics-scope-b",
        app_secret="secret-wa-analytics-scope-b",
    )

    for account_id, phone_number_id in (
        ("wa-analytics-scope-a", "pn-wa-analytics-scope-a"),
        ("wa-analytics-scope-b", "pn-wa-analytics-scope-b"),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": f"conv-{account_id}",
                "user_id": f"user-{account_id}",
                "text": "hello",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

    scoped_headers = {
        "X-Actor-Id": "operator-wa-analytics-scope-a",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "wa-analytics-scope-a",
    }

    own_daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={"waba_id": "waba-wa-analytics-scope-a"},
        headers=scoped_headers,
    )
    assert own_daily_response.status_code == 200
    assert {row["account_id"] for row in own_daily_response.json()} == {"wa-analytics-scope-a"}

    cross_waba_daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={"waba_id": "waba-wa-analytics-scope-b"},
        headers=scoped_headers,
    )
    assert cross_waba_daily_response.status_code == 200
    assert cross_waba_daily_response.json() == []

    cross_phone_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={"phone_number_id": "pn-wa-analytics-scope-b"},
        headers=scoped_headers,
    )
    assert cross_phone_summary_response.status_code == 404
    assert cross_phone_summary_response.json()["detail"] == "Phone-Number-ID 'pn-wa-analytics-scope-b' was not found."

    cross_detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={"waba_id": "waba-wa-analytics-scope-b"},
        headers=scoped_headers,
    )
    assert cross_detail_response.status_code == 200
    cross_detail = cross_detail_response.json()
    assert cross_detail["summary"]["conversation_count"] == 0
    assert cross_detail["daily_rows"] == []


def test_whatsapp_stats_routes_return_404_for_missing_account_scope(
    client: TestClient,
) -> None:
    missing_account_id = "wa-analytics-missing-account"
    expected_detail = f"Account '{missing_account_id}' was not found."

    for method, path in (
        ("get", "/api/whatsapp/stats/summary"),
        ("get", "/api/whatsapp/stats/daily"),
        ("get", "/api/whatsapp/stats/detail"),
        ("post", "/api/whatsapp/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={"account_id": missing_account_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == expected_detail


def test_whatsapp_stats_routes_reject_cross_account_waba_scope_without_phone_filter(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-waba-scope-a",
        display_name="WA Analytics WABA Scope A",
        portfolio_id="portfolio-wa-analytics-waba-scope-a",
        waba_id="waba-wa-analytics-waba-scope-a",
        phone_number_id="pn-wa-analytics-waba-scope-a",
        access_token="token-wa-analytics-waba-scope-a",
        verify_token="verify-wa-analytics-waba-scope-a",
        app_secret="secret-wa-analytics-waba-scope-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-waba-scope-b",
        display_name="WA Analytics WABA Scope B",
        portfolio_id="portfolio-wa-analytics-waba-scope-b",
        waba_id="waba-wa-analytics-waba-scope-b",
        phone_number_id="pn-wa-analytics-waba-scope-b",
        access_token="token-wa-analytics-waba-scope-b",
        verify_token="verify-wa-analytics-waba-scope-b",
        app_secret="secret-wa-analytics-waba-scope-b",
    )

    expected_detail = (
        "WABA 'waba-wa-analytics-waba-scope-b' belongs to account "
        "'wa-analytics-waba-scope-b', not 'wa-analytics-waba-scope-a'."
    )
    for method, path in (
        ("get", "/api/whatsapp/stats/summary"),
        ("get", "/api/whatsapp/stats/daily"),
        ("get", "/api/whatsapp/stats/detail"),
        ("post", "/api/whatsapp/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={
                "account_id": "wa-analytics-waba-scope-a",
                "waba_id": "waba-wa-analytics-waba-scope-b",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == expected_detail


def test_whatsapp_stats_routes_reject_invalid_date_window_filters(
    client: TestClient,
) -> None:
    for method, path in (
        ("get", "/api/whatsapp/stats/summary"),
        ("get", "/api/whatsapp/stats/daily"),
        ("get", "/api/whatsapp/stats/detail"),
        ("post", "/api/whatsapp/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={
                "date_from": "2026-06-08",
                "date_to": "2026-06-07",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "date_from must be less than or equal to date_to."


def test_whatsapp_stats_routes_reject_phone_number_scope_mismatches(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-mismatch-account",
        display_name="WA Analytics Mismatch Account",
        portfolio_id="portfolio-wa-analytics-mismatch-account",
        waba_id="waba-wa-analytics-mismatch-account-a",
        phone_number_id="pn-wa-analytics-mismatch-account-a",
        access_token="token-wa-analytics-mismatch-account-a",
        verify_token="verify-wa-analytics-mismatch-account-a",
        app_secret="secret-wa-analytics-mismatch-account-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-mismatch-account-other",
        display_name="WA Analytics Mismatch Account Other",
        portfolio_id="portfolio-wa-analytics-mismatch-account-other",
        waba_id="waba-wa-analytics-mismatch-account-other",
        phone_number_id="pn-wa-analytics-mismatch-account-other",
        access_token="token-wa-analytics-mismatch-account-other",
        verify_token="verify-wa-analytics-mismatch-account-other",
        app_secret="secret-wa-analytics-mismatch-account-other",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-mismatch-account",
        display_name="WA Analytics Mismatch Account",
        portfolio_id="portfolio-wa-analytics-mismatch-account",
        waba_id="waba-wa-analytics-mismatch-account-b",
        phone_number_id="pn-wa-analytics-mismatch-account-b",
        access_token="token-wa-analytics-mismatch-account-b",
        verify_token="verify-wa-analytics-mismatch-account-b",
        app_secret="secret-wa-analytics-mismatch-account-b",
    )

    cross_account_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": "wa-analytics-mismatch-account",
            "phone_number_id": "pn-wa-analytics-mismatch-account-other",
        },
    )
    assert cross_account_response.status_code == 400
    assert cross_account_response.json()["detail"] == (
        "Phone-Number-ID 'pn-wa-analytics-mismatch-account-other' belongs to account "
        "'wa-analytics-mismatch-account-other', not 'wa-analytics-mismatch-account'."
    )

    cross_waba_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-mismatch-account",
            "waba_id": "waba-wa-analytics-mismatch-account-a",
            "phone_number_id": "pn-wa-analytics-mismatch-account-b",
        },
    )
    assert cross_waba_response.status_code == 400
    assert cross_waba_response.json()["detail"] == (
        "Phone-Number-ID 'pn-wa-analytics-mismatch-account-b' belongs to WABA "
        "'waba-wa-analytics-mismatch-account-b', not 'waba-wa-analytics-mismatch-account-a'."
    )


def test_whatsapp_stats_detail_and_rebuild_reject_phone_number_scope_mismatches(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-mismatch-detail-account",
        display_name="WA Analytics Mismatch Detail Account",
        portfolio_id="portfolio-wa-analytics-mismatch-detail-account",
        waba_id="waba-wa-analytics-mismatch-detail-a",
        phone_number_id="pn-wa-analytics-mismatch-detail-a",
        access_token="token-wa-analytics-mismatch-detail-a",
        verify_token="verify-wa-analytics-mismatch-detail-a",
        app_secret="secret-wa-analytics-mismatch-detail-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-mismatch-detail-account",
        display_name="WA Analytics Mismatch Detail Account",
        portfolio_id="portfolio-wa-analytics-mismatch-detail-account",
        waba_id="waba-wa-analytics-mismatch-detail-b",
        phone_number_id="pn-wa-analytics-mismatch-detail-b",
        access_token="token-wa-analytics-mismatch-detail-b",
        verify_token="verify-wa-analytics-mismatch-detail-b",
        app_secret="secret-wa-analytics-mismatch-detail-b",
    )

    for method, path in (
        ("get", "/api/whatsapp/stats/detail"),
        ("post", "/api/whatsapp/stats/rebuild"),
    ):
        response = getattr(client, method)(
            path,
            params={
                "account_id": "wa-analytics-mismatch-detail-account",
                "waba_id": "waba-wa-analytics-mismatch-detail-a",
                "phone_number_id": "pn-wa-analytics-mismatch-detail-b",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Phone-Number-ID 'pn-wa-analytics-mismatch-detail-b' belongs to WABA "
            "'waba-wa-analytics-mismatch-detail-b', not 'waba-wa-analytics-mismatch-detail-a'."
        )


def test_whatsapp_stats_endpoints_aggregate_messages_and_statuses(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(client)

    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-wa-analytics-1",
            "display_name": "WA Analytics Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-1",
            "user_id": "wa-analytics-user-1",
            "text": "hola",
            "mode": "echo",
            "language_hint": "es",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/wa-analytics-account-1/wa-analytics-conv-1/assignment",
        json={
            "agent_id": "agent-wa-analytics-1",
            "assigned_by_agent_id": "agent-wa-analytics-1",
            "reason": "analytics_manual_reply",
        },
    )
    assert assignment_response.status_code == 200

    outbound_response = client.post(
        "/api/conversations/wa-analytics-account-1/wa-analytics-conv-1/messages/outbound",
        json={
            "text": "您好，订单已发货。",
            "agent_id": "agent-wa-analytics-1",
        },
    )
    assert outbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
            "name": "wa_analytics_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, your shipment has been updated.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-1",
            "variables": {"first_name": "Ana"},
            "agent_id": "agent-wa-analytics-1",
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-wa-analytics-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": "pn-wa-analytics-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345699",
                                    "recipient_id": "wa-analytics-user-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                },
                                {
                                    "id": provider_message_id,
                                    "status": "read",
                                    "timestamp": "1712345799",
                                    "recipient_id": "wa-analytics-user-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-wa-analytics-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-account-1/wabas/waba-wa-analytics-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    duplicate_status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-account-1/wabas/waba-wa-analytics-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert duplicate_status_response.status_code == 200

    session = db_session_factory()
    try:
        fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(WhatsAppConversationStat.account_id == "wa-analytics-account-1")
            .all()
        )
        daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-account-1")
            .all()
        )
        delivered_events = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "wa-analytics-account-1",
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .count()
        )
        read_events = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "wa-analytics-account-1",
                MessageEvent.event_type == "whatsapp_status_read",
            )
            .count()
        )
        assert delivered_events == 1
        assert read_events == 1
        assert any(row.inbound_message_count >= 1 for row in fact_rows)
        assert any(row.outbound_message_count >= 1 for row in fact_rows)
        assert any(
            row.outbound_message_count >= 1
            and row.conversation_origin_type == "business_initiated"
            and row.billable is True
            for row in fact_rows
        )
        assert any(row.delivered_count == 1 for row in fact_rows)
        assert any(row.read_count == 1 for row in fact_rows)
        assert any(row.billable_count == 1 for row in fact_rows)
        assert any(row.delivered_count == 1 for row in daily_rows)
        assert any(row.read_count == 1 for row in daily_rows)
        assert any(row.billable_count == 1 for row in daily_rows)
    finally:
        session.close()

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": "wa-analytics-account-1",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["unique_customer_count"] == 1
    assert summary["inbound_message_count"] == 1
    assert summary["outbound_message_count"] >= 2
    assert summary["delivered_count"] == 1
    assert summary["read_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["billable_count"] == 1
    assert summary["estimated_cost"] == 0
    assert summary["estimated_cost_status"] == "missing_provider_cost"

    daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-account-1",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert daily_response.status_code == 200
    rows = daily_response.json()
    assert len(rows) >= 1
    assert all(row["account_id"] == "wa-analytics-account-1" for row in rows)
    assert all(row["phone_number_id"] == "pn-wa-analytics-1" for row in rows)
    assert any(row["inbound_message_count"] >= 1 for row in rows)
    assert any(row["outbound_message_count"] >= 1 for row in rows)
    assert any(row["delivered_count"] == 1 for row in rows)
    assert any(row["read_count"] == 1 for row in rows)
    assert any(row["conversation_origin_type"] == "business_initiated" for row in rows)
    assert any(row["conversation_category"] == "utility" for row in rows)
    assert any(row["pricing_model"] == "CBP" for row in rows)
    assert any(row["billable"] is True for row in rows)
    billable_row = next(
        row for row in rows if row["billable"] is True and row["billable_count"] == 1
    )
    assert billable_row["billable_count"] == 1
    assert billable_row["estimated_cost"] == 0
    assert billable_row["estimated_cost_status"] == "missing_provider_cost"

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
        },
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 1
    assert detail["summary"]["unique_customer_count"] == 1
    assert detail["summary"]["inbound_message_count"] == 1
    assert detail["summary"]["delivered_count"] == 1
    assert detail["summary"]["billable_count"] == 1
    assert detail["summary"]["estimated_cost_status"] == "missing_provider_cost"
    assert detail["generated_at"] is not None
    assert len(detail["daily_rows"]) >= 1
    assert any(row["conversation_origin_type"] == "business_initiated" for row in detail["daily_rows"])

    filtered_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-account-1",
            "conversation_origin_type": "business_initiated",
            "conversation_category": "utility",
            "pricing_model": "CBP",
            "billable": "true",
            "hour_bucket": billable_row["hour_bucket"],
            "date_from": billable_row["date"],
            "date_to": billable_row["date"],
        },
    )
    assert filtered_response.status_code == 200
    filtered_rows = filtered_response.json()
    assert len(filtered_rows) >= 1
    assert all(row["conversation_origin_type"] == "business_initiated" for row in filtered_rows)
    assert all(row["conversation_category"] == "utility" for row in filtered_rows)
    assert all(row["pricing_model"] == "CBP" for row in filtered_rows)
    assert all(row["billable"] is True for row in filtered_rows)
    assert all(row["hour_bucket"] == billable_row["hour_bucket"] for row in filtered_rows)
    assert all(row["billable_count"] == 1 for row in filtered_rows)
    assert all(row["estimated_cost_status"] == "missing_provider_cost" for row in filtered_rows)

    billable_dimension_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-account-1",
            "conversation_origin_type": "business_initiated",
            "conversation_category": "utility",
            "pricing_model": "CBP",
            "billable": "true",
        },
    )
    assert billable_dimension_response.status_code == 200
    billable_dimension_rows = billable_dimension_response.json()
    assert any(row["outbound_message_count"] >= 1 for row in billable_dimension_rows)

    non_billable_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": "wa-analytics-account-1",
            "billable": "false",
        },
    )
    assert non_billable_response.status_code == 200
    non_billable_summary = non_billable_response.json()
    assert non_billable_summary["billable_count"] == 0
    assert non_billable_summary["estimated_cost"] == 0
    assert non_billable_summary["estimated_cost_status"] == "not_applicable"


def test_whatsapp_stats_summary_deduplicates_conversation_across_hour_buckets(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(client)

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
            "name": "wa_analytics_hourly_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, hourly analytics is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-hourly-1",
            "user_id": "wa-analytics-user-hourly-1",
            "text": "hola",
            "mode": "echo",
            "language_hint": "es",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert inbound_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-hourly-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-wa-analytics-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": "pn-wa-analytics-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345699",
                                    "recipient_id": "wa-analytics-user-hourly-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-hourly-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                },
                                {
                                    "id": provider_message_id,
                                    "status": "read",
                                    "timestamp": "1712349300",
                                    "recipient_id": "wa-analytics-user-hourly-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-hourly-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-wa-analytics-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-account-1/wabas/waba-wa-analytics-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={"account_id": "wa-analytics-account-1", "billable": "true"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 1
    assert detail["summary"]["unique_customer_count"] == 1
    assert detail["summary"]["billable_count"] == 1
    assert len(detail["daily_rows"]) >= 2
    assert len({row["hour_bucket"] for row in detail["daily_rows"] if row["hour_bucket"] is not None}) >= 2


def test_whatsapp_stats_cost_status_is_not_applicable_without_billable_counts(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-no-billable",
            "user_id": "wa-analytics-user-no-billable",
            "text": "hello",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert inbound_response.status_code == 200

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={"account_id": "wa-analytics-account-1"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["billable_count"] == 0
    assert summary["estimated_cost"] == 0
    assert summary["estimated_cost_status"] == "not_applicable"

    daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-account-1",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert daily_response.status_code == 200
    rows = daily_response.json()
    assert len(rows) >= 1
    assert all(row["billable_count"] == 0 for row in rows)
    assert all(row["estimated_cost"] == 0 for row in rows)
    assert all(row["estimated_cost_status"] == "not_applicable" for row in rows)

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={"account_id": "wa-analytics-account-1"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["billable_count"] == 0
    assert detail["summary"]["estimated_cost_status"] == "not_applicable"
    assert all(row["estimated_cost_status"] == "not_applicable" for row in detail["daily_rows"])


def test_whatsapp_stats_cost_status_is_provider_estimated_when_cost_is_present(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(client)

    register_agent_response = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": "agent-wa-analytics-cost-1",
            "display_name": "WA Analytics Cost Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert register_agent_response.status_code == 200

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-cost-1",
            "user_id": "wa-analytics-user-cost-1",
            "text": "hola",
            "mode": "echo",
            "language_hint": "es",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert inbound_response.status_code == 200

    assignment_response = client.post(
        "/api/conversations/wa-analytics-account-1/wa-analytics-conv-cost-1/assignment",
        json={
            "agent_id": "agent-wa-analytics-cost-1",
            "assigned_by_agent_id": "agent-wa-analytics-cost-1",
            "reason": "analytics_cost_reply",
        },
    )
    assert assignment_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
            "name": "wa_analytics_cost_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, cost analytics is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-cost-1",
            "variables": {"first_name": "Ana"},
            "agent_id": "agent-wa-analytics-cost-1",
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-wa-analytics-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": "pn-wa-analytics-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345899",
                                    "recipient_id": "wa-analytics-user-cost-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-cost-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                    "estimated_cost": 1.25,
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-wa-analytics-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-account-1/wabas/waba-wa-analytics-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={"account_id": "wa-analytics-account-1", "billable": "true"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["billable_count"] == 1
    assert summary["estimated_cost"] == 1.25
    assert summary["estimated_cost_status"] == "provider_estimated"

    daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": "wa-analytics-account-1",
            "billable": "true",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert daily_response.status_code == 200
    rows = daily_response.json()
    assert len(rows) >= 1
    assert any(row["estimated_cost"] == 1.25 for row in rows)
    assert any(row["estimated_cost_status"] == "provider_estimated" for row in rows)

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={"account_id": "wa-analytics-account-1", "billable": "true"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["estimated_cost"] == 1.25
    assert detail["summary"]["estimated_cost_status"] == "provider_estimated"
    assert any(row["estimated_cost_status"] == "provider_estimated" for row in detail["daily_rows"])


def test_rebuild_whatsapp_stats_route_recreates_deleted_aggregates(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(client)

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-rebuild-1",
            "user_id": "wa-analytics-user-rebuild-1",
            "text": "hello rebuild",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-1",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
            "name": "wa_analytics_rebuild_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, rebuild is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "wa-analytics-account-1",
            "conversation_id": "wa-analytics-conv-rebuild-1",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-wa-analytics-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": "pn-wa-analytics-1",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "1712345899",
                                    "recipient_id": "wa-analytics-user-rebuild-1",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-rebuild-1",
                                        "expiration_timestamp": "1712350000",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-wa-analytics-1", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-account-1/wabas/waba-wa-analytics-1",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    session = db_session_factory()
    try:
        assert (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-account-1")
            .count()
            >= 1
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(WhatsAppConversationStat.account_id == "wa-analytics-account-1")
            .count()
            >= 1
        )

        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == "wa-analytics-account-1"
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == "wa-analytics-account-1"
        ).delete(synchronize_session=False)
        session.commit()

        assert (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-account-1")
            .count()
            == 0
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(WhatsAppConversationStat.account_id == "wa-analytics-account-1")
            .count()
            == 0
        )
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={"account_id": "wa-analytics-account-1"},
    )
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["account_id"] == "wa-analytics-account-1"
    assert rebuild_payload["date_from"] is None
    assert rebuild_payload["date_to"] is None
    assert datetime.fromisoformat(rebuild_payload["rebuilt_at"])

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-account-1")
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(WhatsAppConversationStat.account_id == "wa-analytics-account-1")
            .all()
        )
        assert len(rebuilt_daily_rows) >= 1
        assert len(rebuilt_fact_rows) >= 1
        assert any(row.inbound_message_count == 1 for row in rebuilt_daily_rows)
        assert any(row.outbound_message_count >= 1 for row in rebuilt_daily_rows)
        assert any(row.delivered_count == 1 for row in rebuilt_daily_rows)
        assert any(row.billable_count == 1 for row in rebuilt_daily_rows)
        assert any(
            row.conversation_origin_type == "business_initiated" and row.billable is True
            for row in rebuilt_fact_rows
        )
    finally:
        session.close()

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={"account_id": "wa-analytics-account-1"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["inbound_message_count"] == 1
    assert summary["outbound_message_count"] >= 1
    assert summary["delivered_count"] == 1
    assert summary["billable_count"] == 1

    audit_logs_response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "wa-analytics-account-1",
            "action": "whatsapp_stats_rebuilt",
            "limit": 10,
        },
    )
    assert audit_logs_response.status_code == 200
    audit_logs = audit_logs_response.json()
    assert len(audit_logs) == 1
    assert audit_logs[0]["target_type"] == "whatsapp_daily_stats"


def test_rebuild_whatsapp_stats_route_respects_date_window(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-window-a",
        display_name="WA Analytics Window A",
        portfolio_id="portfolio-wa-analytics-window-a",
        waba_id="waba-wa-analytics-window-a",
        phone_numbers=[
            {
                "phone_number_id": "pn-wa-analytics-window-a-1",
                "display_phone_number": "+1 555 200 0201",
                "verified_name": "WA Analytics Window A 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-wa-analytics-window-a-2",
                "display_phone_number": "+1 555 200 0202",
                "verified_name": "WA Analytics Window A 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
        access_token="token-wa-analytics-window-a",
        verify_token="verify-wa-analytics-window-a",
        app_secret="secret-wa-analytics-window-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-window-b",
        display_name="WA Analytics Window B",
        portfolio_id="portfolio-wa-analytics-window-b",
        waba_id="waba-wa-analytics-window-b",
        phone_number_id="pn-wa-analytics-window-b-1",
        access_token="token-wa-analytics-window-b",
        verify_token="verify-wa-analytics-window-b",
        app_secret="secret-wa-analytics-window-b",
    )

    for account_id, conversation_id, user_id, phone_number_id in (
        (
            "wa-analytics-window-a",
            "conv-wa-analytics-window-target",
            "user-wa-analytics-window-target",
            "pn-wa-analytics-window-a-1",
        ),
        (
            "wa-analytics-window-a",
            "conv-wa-analytics-window-outside",
            "user-wa-analytics-window-outside",
            "pn-wa-analytics-window-a-2",
        ),
        (
            "wa-analytics-window-b",
            "conv-wa-analytics-window-cross-account",
            "user-wa-analytics-window-cross-account",
            "pn-wa-analytics-window-b-1",
        ),
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": account_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "text": f"hello {conversation_id}",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        conversation_times = {
            "conv-wa-analytics-window-target": datetime.fromisoformat("2026-06-07T10:15:00"),
            "conv-wa-analytics-window-outside": datetime.fromisoformat("2026-06-06T10:15:00"),
            "conv-wa-analytics-window-cross-account": datetime.fromisoformat("2026-06-07T11:15:00"),
        }
        for external_conversation_id, created_at in conversation_times.items():
            conversation = (
                session.query(Conversation)
                .filter(Conversation.external_conversation_id == external_conversation_id)
                .one()
            )
            session.query(Message).filter(Message.conversation_id == conversation.id).update(
                {Message.created_at: created_at},
                synchronize_session=False,
            )
            session.query(MessageEvent).filter(MessageEvent.conversation_id == conversation.id).update(
                {MessageEvent.created_at: created_at},
                synchronize_session=False,
            )

        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id.in_(
                ["wa-analytics-window-a", "wa-analytics-window-b"],
            )
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id.in_(
                ["wa-analytics-window-a", "wa-analytics-window-b"],
            )
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": "wa-analytics-window-a",
            "waba_id": "waba-wa-analytics-window-a",
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["account_id"] == "wa-analytics-window-a"
    assert rebuild_payload["waba_id"] == "waba-wa-analytics-window-a"
    assert rebuild_payload["date_from"] == "2026-06-07"
    assert rebuild_payload["date_to"] == "2026-06-07"

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-window-a")
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(WhatsAppConversationStat.account_id == "wa-analytics-window-a")
            .all()
        )
        assert rebuilt_daily_rows
        assert rebuilt_fact_rows
        assert {row.date.isoformat() for row in rebuilt_daily_rows} == {"2026-06-07"}
        assert {row.date.isoformat() for row in rebuilt_fact_rows} == {"2026-06-07"}
        assert {row.waba_id for row in rebuilt_daily_rows} == {"waba-wa-analytics-window-a"}
        assert {row.phone_number_id for row in rebuilt_daily_rows} == {"pn-wa-analytics-window-a-1"}
        assert {row.phone_number_id for row in rebuilt_fact_rows} == {"pn-wa-analytics-window-a-1"}
        assert sum(row.inbound_message_count for row in rebuilt_daily_rows) == 1
        assert sum(row.outbound_message_count for row in rebuilt_daily_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-window-b")
            .count()
            == 0
        )
    finally:
        session.close()

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": "wa-analytics-window-a",
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["inbound_message_count"] == 1
    assert summary["outbound_message_count"] == 1


def test_rebuild_whatsapp_stats_route_uses_status_payload_timestamp(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-event-window",
        display_name="WA Analytics Event Window",
        portfolio_id="portfolio-wa-analytics-event-window",
        waba_id="waba-wa-analytics-event-window",
        phone_number_id="pn-wa-analytics-event-window",
        access_token="token-wa-analytics-event-window",
        verify_token="verify-wa-analytics-event-window",
        app_secret="secret-wa-analytics-event-window",
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-event-window",
            "conversation_id": "conv-wa-analytics-event-window",
            "user_id": "user-wa-analytics-event-window",
            "text": "hello event window",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-event-window",
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": "wa-analytics-event-window",
            "waba_id": "waba-wa-analytics-event-window",
            "name": "wa_analytics_event_window_template",
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, event window is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": "wa-analytics-event-window",
            "conversation_id": "conv-wa-analytics-event-window",
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-wa-analytics-event-window",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": "pn-wa-analytics-event-window",
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": "2026-06-07T12:15:00Z",
                                    "recipient_id": "user-wa-analytics-event-window",
                                    "conversation": {
                                        "id": "wa-analytics-meta-conversation-event-window",
                                        "expiration_timestamp": "2026-06-08T12:15:00Z",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature("secret-wa-analytics-event-window", status_body)
    status_response = client.post(
        "/webhooks/whatsapp/wa-analytics-event-window/wabas/waba-wa-analytics-event-window",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == "wa-analytics-event-window",
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        event.created_at = datetime.fromisoformat("2026-06-06T12:15:00")
        event.payload = {
            **(event.payload or {}),
            "timestamp": "2026-06-07T12:15:00Z",
        }
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == "wa-analytics-event-window"
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == "wa-analytics-event-window"
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": "wa-analytics-event-window",
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-event-window")
            .all()
        )
        assert rebuilt_daily_rows
        assert {row.date.isoformat() for row in rebuilt_daily_rows} == {"2026-06-07"}
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
    finally:
        session.close()


def test_rebuild_whatsapp_stats_route_prefers_event_occurred_at_and_falls_back_to_created_at(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-occurred-at-window"
    waba_id = "waba-wa-analytics-occurred-at-window"
    phone_number_id = "pn-wa-analytics-occurred-at-window"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Occurred At Window",
        portfolio_id="portfolio-wa-analytics-occurred-at-window",
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        app_secret="secret-wa-analytics-occurred-at-window",
        conversation_id="conv-wa-analytics-occurred-at-inside",
        user_id="user-wa-analytics-occurred-at-inside",
        template_name="wa_analytics_occurred_at_inside_template",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        app_secret="secret-wa-analytics-occurred-at-window",
        conversation_id="conv-wa-analytics-occurred-at-outside",
        user_id="user-wa-analytics-occurred-at-outside",
        template_name="wa_analytics_occurred_at_outside_template",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        app_secret="secret-wa-analytics-occurred-at-window",
        conversation_id="conv-wa-analytics-created-at-fallback",
        user_id="user-wa-analytics-created-at-fallback",
        template_name="wa_analytics_created_at_fallback_template",
    )

    session = db_session_factory()
    try:
        events = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .all()
        )
        events_by_conversation_id = {
            str(event.payload["conversation_id"]): event
            for event in events
            if isinstance(event.payload, dict) and "conversation_id" in event.payload
        }
        assert set(events_by_conversation_id) == {
            "conv-wa-analytics-occurred-at-inside",
            "conv-wa-analytics-occurred-at-outside",
            "conv-wa-analytics-created-at-fallback",
        }

        occurred_inside_event = events_by_conversation_id["conv-wa-analytics-occurred-at-inside"]
        occurred_inside_event.created_at = datetime.fromisoformat("2026-06-06T09:15:00")
        occurred_inside_event.occurred_at = datetime.fromisoformat("2026-06-07T09:15:00")
        occurred_inside_event.payload = {
            "conversation_id": "conv-wa-analytics-occurred-at-inside",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }

        occurred_outside_event = events_by_conversation_id["conv-wa-analytics-occurred-at-outside"]
        occurred_outside_event.created_at = datetime.fromisoformat("2026-06-07T10:15:00")
        occurred_outside_event.occurred_at = datetime.fromisoformat("2026-06-06T10:15:00")
        occurred_outside_event.payload = {
            "conversation_id": "conv-wa-analytics-occurred-at-outside",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }

        created_fallback_event = events_by_conversation_id["conv-wa-analytics-created-at-fallback"]
        created_fallback_event.created_at = datetime.fromisoformat("2026-06-07T11:15:00")
        created_fallback_event.occurred_at = None
        created_fallback_event.payload = {
            "conversation_id": "conv-wa-analytics-created-at-fallback",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }
        session.commit()
    finally:
        session.close()

    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.date == datetime.fromisoformat("2026-06-07T00:00:00").date(),
            )
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.date == datetime.fromisoformat("2026-06-07T00:00:00").date(),
            )
            .all()
        )
        expected_conversation_ids = {
            row.external_conversation_id: row.id
            for row in session.query(Conversation)
            .filter(Conversation.account_id == account_id)
            .all()
        }

        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 2
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 2
        assert {
            row.conversation_id for row in rebuilt_fact_rows if row.delivered_count > 0
        } == {
            expected_conversation_ids["conv-wa-analytics-occurred-at-inside"],
            expected_conversation_ids["conv-wa-analytics-created-at-fallback"],
        }
    finally:
        session.close()


def test_rebuild_whatsapp_stats_route_rejects_cross_account_operator_scope(
    client: TestClient,
) -> None:
    register_whatsapp_analytics_account(client)

    response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={"account_id": "wa-analytics-account-1"},
        headers={
            "X-Actor-Id": "operator-wa-analytics-other",
            "X-Actor-Role": "operator",
            "X-Actor-Account-Ids": "wa-analytics-account-other",
        },
    )

    assert response.status_code == 403
    assert "cannot access account 'wa-analytics-account-1'" in response.json()["detail"]


def test_rebuild_whatsapp_stats_route_can_scope_to_phone_number(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        phone_numbers=[
            {
                "phone_number_id": "pn-wa-analytics-scope-rebuild-1",
                "display_phone_number": "+1 555 200 0101",
                "verified_name": "WA Analytics Scope Rebuild 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": "pn-wa-analytics-scope-rebuild-2",
                "display_phone_number": "+1 555 200 0102",
                "verified_name": "WA Analytics Scope Rebuild 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
    )

    for phone_number_id in (
        "pn-wa-analytics-scope-rebuild-1",
        "pn-wa-analytics-scope-rebuild-2",
    ):
        inbound_response = client.post(
            "/dev/mock/inbound-message",
            json={
                "account_id": "wa-analytics-account-1",
                "conversation_id": f"conv-{phone_number_id}",
                "user_id": f"user-{phone_number_id}",
                "text": "hello scoped rebuild",
                "mode": "echo",
                "language_hint": "en",
                "phone_number_id": phone_number_id,
            },
        )
        assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        phone_2_daily_before = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == "wa-analytics-account-1",
                WhatsAppDailyStat.phone_number_id == "pn-wa-analytics-scope-rebuild-2",
            )
            .count()
        )
        phone_2_fact_before = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == "wa-analytics-account-1",
                WhatsAppConversationStat.phone_number_id == "pn-wa-analytics-scope-rebuild-2",
            )
            .count()
        )
        assert phone_2_daily_before >= 1
        assert phone_2_fact_before >= 1

        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == "wa-analytics-account-1",
            WhatsAppDailyStat.phone_number_id == "pn-wa-analytics-scope-rebuild-1",
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == "wa-analytics-account-1",
            WhatsAppConversationStat.phone_number_id == "pn-wa-analytics-scope-rebuild-1",
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": "wa-analytics-account-1",
            "waba_id": "waba-wa-analytics-1",
            "phone_number_id": "pn-wa-analytics-scope-rebuild-1",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["waba_id"] == "waba-wa-analytics-1"
    assert rebuild_payload["phone_number_id"] == "pn-wa-analytics-scope-rebuild-1"

    session = db_session_factory()
    try:
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == "wa-analytics-account-1",
                WhatsAppDailyStat.phone_number_id == "pn-wa-analytics-scope-rebuild-1",
            )
            .count()
            >= 1
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == "wa-analytics-account-1",
                WhatsAppConversationStat.phone_number_id == "pn-wa-analytics-scope-rebuild-1",
            )
            .count()
            >= 1
        )
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == "wa-analytics-account-1",
                WhatsAppDailyStat.phone_number_id == "pn-wa-analytics-scope-rebuild-2",
            )
            .count()
            == phone_2_daily_before
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == "wa-analytics-account-1",
                WhatsAppConversationStat.phone_number_id == "pn-wa-analytics-scope-rebuild-2",
            )
            .count()
            == phone_2_fact_before
        )
    finally:
        session.close()


def test_rebuild_whatsapp_stats_route_scoped_phone_rebuild_keeps_other_phone_and_account_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_a = "wa-analytics-scope-preserve-a"
    waba_a = "waba-wa-analytics-scope-preserve-a"
    phone_a_1 = "pn-wa-analytics-scope-preserve-a-1"
    phone_a_2 = "pn-wa-analytics-scope-preserve-a-2"
    account_b = "wa-analytics-scope-preserve-b"
    waba_b = "waba-wa-analytics-scope-preserve-b"
    phone_b = "pn-wa-analytics-scope-preserve-b"

    register_whatsapp_analytics_account(
        client,
        account_id=account_a,
        display_name="WA Analytics Scope Preserve A",
        portfolio_id="portfolio-wa-analytics-scope-preserve-a",
        waba_id=waba_a,
        phone_numbers=[
            {
                "phone_number_id": phone_a_1,
                "display_phone_number": "+1 555 200 0301",
                "verified_name": "WA Analytics Scope Preserve A 1",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
            {
                "phone_number_id": phone_a_2,
                "display_phone_number": "+1 555 200 0302",
                "verified_name": "WA Analytics Scope Preserve A 2",
                "quality_rating": "GREEN",
                "is_registered": True,
            },
        ],
        access_token="token-wa-analytics-scope-preserve-a",
        verify_token="verify-wa-analytics-scope-preserve-a",
        app_secret="secret-wa-analytics-scope-preserve-a",
    )
    register_whatsapp_analytics_account(
        client,
        account_id=account_b,
        display_name="WA Analytics Scope Preserve B",
        portfolio_id="portfolio-wa-analytics-scope-preserve-b",
        waba_id=waba_b,
        phone_number_id=phone_b,
        access_token="token-wa-analytics-scope-preserve-b",
        verify_token="verify-wa-analytics-scope-preserve-b",
        app_secret="secret-wa-analytics-scope-preserve-b",
    )

    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_a,
        waba_id=waba_a,
        phone_number_id=phone_a_1,
        app_secret="secret-wa-analytics-scope-preserve-a",
        conversation_id="conv-wa-analytics-scope-preserve-a-1",
        user_id="user-wa-analytics-scope-preserve-a-1",
        template_name="wa_analytics_scope_preserve_a1_template",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_a,
        waba_id=waba_a,
        phone_number_id=phone_a_2,
        app_secret="secret-wa-analytics-scope-preserve-a",
        conversation_id="conv-wa-analytics-scope-preserve-a-2",
        user_id="user-wa-analytics-scope-preserve-a-2",
        template_name="wa_analytics_scope_preserve_a2_template",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_b,
        waba_id=waba_b,
        phone_number_id=phone_b,
        app_secret="secret-wa-analytics-scope-preserve-b",
        conversation_id="conv-wa-analytics-scope-preserve-b-1",
        user_id="user-wa-analytics-scope-preserve-b-1",
        template_name="wa_analytics_scope_preserve_b1_template",
    )

    session = db_session_factory()
    try:
        other_phone_daily_before = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_a,
                WhatsAppDailyStat.phone_number_id == phone_a_2,
            )
            .count()
        )
        other_phone_fact_before = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_a,
                WhatsAppConversationStat.phone_number_id == phone_a_2,
            )
            .count()
        )
        other_account_daily_before = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_b,
                WhatsAppDailyStat.phone_number_id == phone_b,
            )
            .count()
        )
        other_account_fact_before = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_b,
                WhatsAppConversationStat.phone_number_id == phone_b,
            )
            .count()
        )
        assert other_phone_daily_before >= 1
        assert other_phone_fact_before >= 1
        assert other_account_daily_before >= 1
        assert other_account_fact_before >= 1

        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == account_a,
            WhatsAppDailyStat.waba_id == waba_a,
            WhatsAppDailyStat.phone_number_id == phone_a_1,
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == account_a,
            WhatsAppConversationStat.waba_id == waba_a,
            WhatsAppConversationStat.phone_number_id == phone_a_1,
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_a,
            "waba_id": waba_a,
            "phone_number_id": phone_a_1,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_target_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_a,
                WhatsAppDailyStat.waba_id == waba_a,
                WhatsAppDailyStat.phone_number_id == phone_a_1,
            )
            .all()
        )
        rebuilt_target_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_a,
                WhatsAppConversationStat.waba_id == waba_a,
                WhatsAppConversationStat.phone_number_id == phone_a_1,
            )
            .all()
        )

        assert rebuilt_target_daily_rows
        assert rebuilt_target_fact_rows
        assert sum(row.delivered_count for row in rebuilt_target_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_target_daily_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_a,
                WhatsAppDailyStat.phone_number_id == phone_a_2,
            )
            .count()
            == other_phone_daily_before
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_a,
                WhatsAppConversationStat.phone_number_id == phone_a_2,
            )
            .count()
            == other_phone_fact_before
        )
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_b,
                WhatsAppDailyStat.phone_number_id == phone_b,
            )
            .count()
            == other_account_daily_before
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_b,
                WhatsAppConversationStat.phone_number_id == phone_b,
            )
            .count()
            == other_account_fact_before
        )
    finally:
        session.close()


def _create_whatsapp_status_stats_fixture(
    client: TestClient,
    *,
    account_id: str,
    display_name: str,
    portfolio_id: str,
    waba_id: str,
    phone_number_id: str,
    app_secret: str,
    conversation_id: str,
    user_id: str,
    template_name: str,
    status_timestamp: str = "2026-06-07T12:15:00Z",
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id=account_id,
        display_name=display_name,
        portfolio_id=portfolio_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        access_token=f"token-{account_id}",
        verify_token=f"verify-{account_id}",
        app_secret=app_secret,
    )

    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        app_secret=app_secret,
        conversation_id=conversation_id,
        user_id=user_id,
        template_name=template_name,
        status_timestamp=status_timestamp,
    )


def _create_whatsapp_status_stats_for_existing_scope(
    client: TestClient,
    *,
    account_id: str,
    waba_id: str,
    phone_number_id: str,
    app_secret: str,
    conversation_id: str,
    user_id: str,
    template_name: str,
    status_timestamp: str = "2026-06-07T12:15:00Z",
) -> None:
    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "text": "hello analytics snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": phone_number_id,
        },
    )
    assert inbound_response.status_code == 200

    template_response = client.post(
        "/api/templates/drafts",
        json={
            "account_id": account_id,
            "waba_id": waba_id,
            "name": template_name,
            "language": "en",
            "category": "UTILITY",
            "body_text": "Hello {{first_name}}, analytics snapshot is ready.",
            "sample_variables": {"first_name": "Customer"},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    approve_response = client.post(
        f"/api/templates/{template_id}/status",
        json={"status": "APPROVED"},
    )
    assert approve_response.status_code == 200

    send_template_response = client.post(
        f"/api/templates/{template_id}/send",
        json={
            "account_id": account_id,
            "conversation_id": conversation_id,
            "variables": {"first_name": "Ana"},
        },
    )
    assert send_template_response.status_code == 200
    provider_message_id = send_template_response.json()["message_id"]

    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1 555 200 0001",
                                "phone_number_id": phone_number_id,
                            },
                            "statuses": [
                                {
                                    "id": provider_message_id,
                                    "status": "delivered",
                                    "timestamp": status_timestamp,
                                    "recipient_id": user_id,
                                    "conversation": {
                                        "id": f"meta-{conversation_id}",
                                        "expiration_timestamp": "2026-06-08T12:15:00Z",
                                        "origin": {"type": "business_initiated"},
                                    },
                                    "pricing": {
                                        "billable": True,
                                        "category": "utility",
                                        "pricing_model": "CBP",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    status_body = json.dumps(status_payload, separators=(",", ":")).encode("utf-8")
    signature = WhatsAppProvider.build_signature(app_secret, status_body)
    status_response = client.post(
        f"/webhooks/whatsapp/{account_id}/wabas/{waba_id}",
        content=status_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert status_response.status_code == 200


def test_whatsapp_status_billing_key_prefers_provider_conversation_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-provider-key"
    conversation_id = "conv-wa-analytics-provider-key"
    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Provider Key",
        portfolio_id="portfolio-wa-analytics-provider-key",
        waba_id="waba-wa-analytics-provider-key",
        phone_number_id="pn-wa-analytics-provider-key",
        app_secret="secret-wa-analytics-provider-key",
        conversation_id=conversation_id,
        user_id="user-wa-analytics-provider-key",
        template_name="wa_analytics_provider_key_template",
    )

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        message = session.query(Message).filter(Message.id == event.message_id).one()
        conversation = (
            session.query(Conversation).filter(Conversation.id == message.conversation_id).one()
        )

        assert event.payload["conversation_id"] == conversation_id
        assert event.payload["provider_payload"]["conversation_id"] == f"meta-{conversation_id}"
        assert (
            WhatsAppAnalyticsService._build_billing_key(
                event=event,
                message=message,
                conversation=conversation,
            )
            == f"conversation:meta-{conversation_id}"
        )
    finally:
        session.close()


def _add_whatsapp_analytics_phone_scope(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    waba_id: str,
    phone_number_id: str,
    app_secret: str,
) -> None:
    session = db_session_factory()
    try:
        waba_account = WhatsAppBusinessAccount(
            account_id=account_id,
            waba_id=waba_id,
            onboarding_mode="manual",
            token_source="system_user",
            access_token=f"token-{waba_id}",
            verify_token=f"verify-{waba_id}",
            app_secret=app_secret,
            is_active=True,
        )
        session.add(waba_account)
        session.flush()
        session.add(
            WhatsAppPhoneNumber(
                account_id=account_id,
                waba_account_id=waba_account.id,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                display_phone_number="+1 555 200 0999",
                verified_name=f"Analytics {phone_number_id}",
                quality_rating="GREEN",
                is_registered=True,
                is_active=True,
            )
        )
        session.commit()
    finally:
        session.close()


def _recreate_whatsapp_waba_row(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    official_waba_id: str,
    phone_number_id: str,
    legacy_waba_id: str,
) -> None:
    session = db_session_factory()
    try:
        legacy_waba = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == account_id,
                WhatsAppBusinessAccount.waba_id == official_waba_id,
            )
            .one()
        )
        legacy_waba.waba_id = legacy_waba_id
        session.flush()

        recreated_waba = WhatsAppBusinessAccount(
            account_id=account_id,
            portfolio_id=legacy_waba.portfolio_id,
            waba_id=official_waba_id,
            onboarding_mode=legacy_waba.onboarding_mode,
            token_source=legacy_waba.token_source,
            access_token=legacy_waba.access_token,
            verify_token=legacy_waba.verify_token,
            app_secret=legacy_waba.app_secret,
            webhook_subscribed=legacy_waba.webhook_subscribed,
            is_active=legacy_waba.is_active,
            ai_enabled=legacy_waba.ai_enabled,
        )
        session.add(recreated_waba)
        session.flush()

        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
            .one()
        )
        phone_number.waba_account_id = recreated_waba.id
        phone_number.waba_id = official_waba_id
        session.commit()
    finally:
        session.close()


def _recreate_whatsapp_phone_number_row(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    official_phone_number_id: str,
    legacy_phone_number_id: str,
) -> None:
    session = db_session_factory()
    try:
        legacy_phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == official_phone_number_id,
            )
            .one()
        )
        legacy_phone_number.phone_number_id = legacy_phone_number_id
        session.flush()

        recreated_phone_number = WhatsAppPhoneNumber(
            account_id=account_id,
            waba_account_id=legacy_phone_number.waba_account_id,
            waba_id=legacy_phone_number.waba_id,
            phone_number_id=official_phone_number_id,
            display_phone_number=legacy_phone_number.display_phone_number,
            verified_name=legacy_phone_number.verified_name,
            quality_rating=legacy_phone_number.quality_rating,
            quality_event=legacy_phone_number.quality_event,
            previous_quality_rating=legacy_phone_number.previous_quality_rating,
            messaging_limit_tier=legacy_phone_number.messaging_limit_tier,
            max_daily_conversations_per_business=(
                legacy_phone_number.max_daily_conversations_per_business
            ),
            last_quality_event_at=legacy_phone_number.last_quality_event_at,
            last_status_payload=legacy_phone_number.last_status_payload,
            is_registered=legacy_phone_number.is_registered,
            is_active=legacy_phone_number.is_active,
        )
        session.add(recreated_phone_number)
        session.commit()
    finally:
        session.close()


def _drift_whatsapp_phone_relationship(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    phone_number_id: str,
    drifted_phone_number_id: str,
    drifted_waba_id: str,
) -> None:
    session = db_session_factory()
    try:
        phone_number = (
            session.query(WhatsAppPhoneNumber)
            .filter(
                WhatsAppPhoneNumber.account_id == account_id,
                WhatsAppPhoneNumber.phone_number_id == phone_number_id,
            )
            .one()
        )
        phone_number.phone_number_id = drifted_phone_number_id
        phone_number.waba_id = drifted_waba_id
        assert phone_number.waba_account is not None
        phone_number.waba_account.waba_id = drifted_waba_id
        session.commit()
    finally:
        session.close()


def _delete_whatsapp_stats(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
) -> None:
    session = db_session_factory()
    try:
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == account_id
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == account_id
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def test_whatsapp_stats_summary_and_detail_filters_keep_snapshot_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-filter"
    original_waba_id = "waba-wa-analytics-snapshot-filter"
    original_phone_number_id = "pn-wa-analytics-snapshot-filter"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Filter",
        portfolio_id="portfolio-wa-analytics-snapshot-filter",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-filter",
        conversation_id="conv-wa-analytics-snapshot-filter",
        user_id="user-wa-analytics-snapshot-filter",
        template_name="wa_analytics_snapshot_filter_template",
    )

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-snapshot-filter-drifted",
        drifted_waba_id="waba-wa-analytics-snapshot-filter-drifted",
    )

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["delivered_count"] == 1
    assert summary["billable_count"] == 1

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 1
    assert detail["summary"]["delivered_count"] == 1
    assert detail["summary"]["billable_count"] == 1
    assert detail["daily_rows"]
    assert {row["waba_id"] for row in detail["daily_rows"]} == {original_waba_id}
    assert {row["phone_number_id"] for row in detail["daily_rows"]} == {original_phone_number_id}

    drifted_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": "waba-wa-analytics-snapshot-filter-drifted",
            "phone_number_id": "pn-wa-analytics-snapshot-filter-drifted",
        },
    )
    assert drifted_summary_response.status_code == 200
    drifted_summary = drifted_summary_response.json()
    assert drifted_summary["conversation_count"] == 0
    assert drifted_summary["delivered_count"] == 0


def test_whatsapp_stats_filters_keep_snapshot_scope_after_local_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-recreated-filter"
    original_waba_id = "waba-wa-analytics-snapshot-recreated-filter"
    original_phone_number_id = "pn-wa-analytics-snapshot-recreated-filter"
    legacy_waba_id = "waba-wa-analytics-snapshot-recreated-filter-legacy"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Recreated Filter",
        portfolio_id="portfolio-wa-analytics-snapshot-recreated-filter",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-recreated-filter",
        conversation_id="conv-wa-analytics-snapshot-recreated-filter",
        user_id="user-wa-analytics-snapshot-recreated-filter",
        template_name="wa_analytics_snapshot_recreated_filter_template",
    )

    _recreate_whatsapp_waba_row(
        db_session_factory,
        account_id=account_id,
        official_waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        legacy_waba_id=legacy_waba_id,
    )

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["delivered_count"] == 1
    assert summary["billable_count"] == 1

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 1
    assert detail["summary"]["delivered_count"] == 1
    assert detail["daily_rows"]
    assert {row["waba_id"] for row in detail["daily_rows"]} == {original_waba_id}
    assert {row["phone_number_id"] for row in detail["daily_rows"]} == {original_phone_number_id}

    daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert daily_response.status_code == 200
    assert {row["waba_id"] for row in daily_response.json()} == {original_waba_id}

    legacy_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": legacy_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert legacy_summary_response.status_code == 200
    legacy_summary = legacy_summary_response.json()
    assert legacy_summary["conversation_count"] == 0
    assert legacy_summary["delivered_count"] == 0


def test_whatsapp_stats_filters_keep_snapshot_scope_after_local_phone_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-recreated-phone-filter"
    original_waba_id = "waba-wa-analytics-snapshot-recreated-phone-filter"
    original_phone_number_id = "pn-wa-analytics-snapshot-recreated-phone-filter"
    legacy_phone_number_id = "pn-wa-analytics-snapshot-recreated-phone-filter-legacy"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Recreated Phone Filter",
        portfolio_id="portfolio-wa-analytics-snapshot-recreated-phone-filter",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-recreated-phone-filter",
        conversation_id="conv-wa-analytics-snapshot-recreated-phone-filter",
        user_id="user-wa-analytics-snapshot-recreated-phone-filter",
        template_name="wa_analytics_snapshot_recreated_phone_filter_template",
    )

    _recreate_whatsapp_phone_number_row(
        db_session_factory,
        account_id=account_id,
        official_phone_number_id=original_phone_number_id,
        legacy_phone_number_id=legacy_phone_number_id,
    )

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["delivered_count"] == 1
    assert summary["billable_count"] == 1

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 1
    assert detail["summary"]["delivered_count"] == 1
    assert detail["daily_rows"]
    assert {row["waba_id"] for row in detail["daily_rows"]} == {original_waba_id}
    assert {row["phone_number_id"] for row in detail["daily_rows"]} == {
        original_phone_number_id
    }

    legacy_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": legacy_phone_number_id,
        },
    )
    assert legacy_summary_response.status_code == 200
    legacy_summary = legacy_summary_response.json()
    assert legacy_summary["conversation_count"] == 0
    assert legacy_summary["delivered_count"] == 0


def test_whatsapp_stats_filters_keep_phone_and_waba_snapshots_across_multi_waba_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-multi-filter"
    original_waba_id = "waba-wa-analytics-snapshot-multi-a"
    original_phone_number_id = "pn-wa-analytics-snapshot-multi-a"
    second_waba_id = "waba-wa-analytics-snapshot-multi-b"
    second_phone_number_id = "pn-wa-analytics-snapshot-multi-b"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Multi A",
        portfolio_id="portfolio-wa-analytics-snapshot-multi",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-multi-a",
        conversation_id="conv-wa-analytics-snapshot-multi-a",
        user_id="user-wa-analytics-snapshot-multi-a",
        template_name="wa_analytics_snapshot_multi_filter_a",
    )
    _add_whatsapp_analytics_phone_scope(
        db_session_factory,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-multi-b",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-multi-b",
        conversation_id="conv-wa-analytics-snapshot-multi-b",
        user_id="user-wa-analytics-snapshot-multi-b",
        template_name="wa_analytics_snapshot_multi_filter_b",
    )

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-snapshot-multi-a-drifted",
        drifted_waba_id="waba-wa-analytics-snapshot-multi-a-drifted",
    )

    account_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={"account_id": account_id, "billable": "true"},
    )
    assert account_summary_response.status_code == 200
    account_summary = account_summary_response.json()
    assert account_summary["conversation_count"] == 2
    assert account_summary["delivered_count"] == 2
    assert account_summary["billable_count"] == 2

    original_summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert original_summary_response.status_code == 200
    original_summary = original_summary_response.json()
    assert original_summary["conversation_count"] == 1
    assert original_summary["delivered_count"] == 1
    assert original_summary["billable_count"] == 1

    second_detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": account_id,
            "waba_id": second_waba_id,
            "phone_number_id": second_phone_number_id,
            "billable": "true",
        },
    )
    assert second_detail_response.status_code == 200
    second_detail = second_detail_response.json()
    assert second_detail["summary"]["conversation_count"] == 1
    assert second_detail["summary"]["delivered_count"] == 1
    assert second_detail["daily_rows"]
    assert {row["waba_id"] for row in second_detail["daily_rows"]} == {second_waba_id}
    assert {row["phone_number_id"] for row in second_detail["daily_rows"]} == {
        second_phone_number_id
    }

    drifted_daily_response = client.get(
        "/api/whatsapp/stats/daily",
        params={
            "account_id": account_id,
            "waba_id": "waba-wa-analytics-snapshot-multi-a-drifted",
            "phone_number_id": "pn-wa-analytics-snapshot-multi-a-drifted",
        },
    )
    assert drifted_daily_response.status_code == 200
    assert drifted_daily_response.json() == []


def test_rebuild_whatsapp_stats_route_prefers_snapshot_scope_after_relationship_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-rebuild"
    original_waba_id = "waba-wa-analytics-snapshot-rebuild"
    original_phone_number_id = "pn-wa-analytics-snapshot-rebuild"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Rebuild",
        portfolio_id="portfolio-wa-analytics-snapshot-rebuild",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-rebuild",
        conversation_id="conv-wa-analytics-snapshot-rebuild",
        user_id="user-wa-analytics-snapshot-rebuild",
        template_name="wa_analytics_snapshot_rebuild_template",
    )

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-snapshot-rebuild-drifted",
        drifted_waba_id="waba-wa-analytics-snapshot-rebuild-drifted",
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == original_waba_id,
                WhatsAppConversationStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert rebuilt_fact_rows
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
        assert sum(row.delivered_count for row in rebuilt_fact_rows) == 1
    finally:
        session.close()


def test_rebuild_whatsapp_stats_scoped_to_snapshot_phone_preserves_other_waba_after_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-multi-rebuild"
    original_waba_id = "waba-wa-analytics-snapshot-rebuild-a"
    original_phone_number_id = "pn-wa-analytics-snapshot-rebuild-a"
    second_waba_id = "waba-wa-analytics-snapshot-rebuild-b"
    second_phone_number_id = "pn-wa-analytics-snapshot-rebuild-b"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Rebuild A",
        portfolio_id="portfolio-wa-analytics-snapshot-multi-rebuild",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-rebuild-a",
        conversation_id="conv-wa-analytics-snapshot-rebuild-a",
        user_id="user-wa-analytics-snapshot-rebuild-a",
        template_name="wa_analytics_snapshot_multi_rebuild_a",
    )
    _add_whatsapp_analytics_phone_scope(
        db_session_factory,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-rebuild-b",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-rebuild-b",
        conversation_id="conv-wa-analytics-snapshot-rebuild-b",
        user_id="user-wa-analytics-snapshot-rebuild-b",
        template_name="wa_analytics_snapshot_multi_rebuild_b",
    )

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-snapshot-rebuild-a-drifted",
        drifted_waba_id="waba-wa-analytics-snapshot-rebuild-a-drifted",
    )

    session = db_session_factory()
    try:
        second_daily_before = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == second_waba_id,
                WhatsAppDailyStat.phone_number_id == second_phone_number_id,
            )
            .count()
        )
        second_fact_before = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == second_waba_id,
                WhatsAppConversationStat.phone_number_id == second_phone_number_id,
            )
            .count()
        )
        assert second_daily_before >= 1
        assert second_fact_before >= 1
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == account_id,
            WhatsAppDailyStat.waba_id == original_waba_id,
            WhatsAppDailyStat.phone_number_id == original_phone_number_id,
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == account_id,
            WhatsAppConversationStat.waba_id == original_waba_id,
            WhatsAppConversationStat.phone_number_id == original_phone_number_id,
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["waba_id"] == original_waba_id
    assert rebuild_payload["phone_number_id"] == original_phone_number_id

    session = db_session_factory()
    try:
        original_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        original_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == original_waba_id,
                WhatsAppConversationStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert original_daily_rows
        assert original_fact_rows
        assert sum(row.delivered_count for row in original_daily_rows) == 1
        assert sum(row.billable_count for row in original_daily_rows) == 1
        assert sum(row.delivered_count for row in original_fact_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == second_waba_id,
                WhatsAppDailyStat.phone_number_id == second_phone_number_id,
            )
            .count()
            == second_daily_before
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == second_waba_id,
                WhatsAppConversationStat.phone_number_id == second_phone_number_id,
            )
            .count()
            == second_fact_before
        )
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == "waba-wa-analytics-snapshot-rebuild-a-drifted",
            )
            .count()
            == 0
        )
    finally:
        session.close()


def test_rebuild_whatsapp_stats_route_uses_status_payload_timestamp_with_snapshot_scope_fallback(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-snapshot-event-window"
    original_waba_id = "waba-wa-analytics-snapshot-event-window"
    original_phone_number_id = "pn-wa-analytics-snapshot-event-window"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Snapshot Event Window",
        portfolio_id="portfolio-wa-analytics-snapshot-event-window",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-snapshot-event-window",
        conversation_id="conv-wa-analytics-snapshot-event-window",
        user_id="user-wa-analytics-snapshot-event-window",
        template_name="wa_analytics_snapshot_event_window_template",
    )

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        event.created_at = datetime.fromisoformat("2026-06-06T12:15:00")
        event.occurred_at = None
        event.payload = {
            **(event.payload or {}),
            "timestamp": "2026-06-07T12:15:00Z",
        }
        session.commit()
    finally:
        session.close()

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-snapshot-event-window-drifted",
        drifted_waba_id="waba-wa-analytics-snapshot-event-window-drifted",
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert {row.date.isoformat() for row in rebuilt_daily_rows} == {"2026-06-07"}
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
    finally:
        session.close()


def test_whatsapp_stats_source_summary_prefers_status_occurred_at_over_payload_timestamp_and_created_at(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-source-summary-occurred-at"
    original_waba_id = "waba-wa-analytics-source-summary-occurred-at"
    original_phone_number_id = "pn-wa-analytics-source-summary-occurred-at"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Source Summary Occurred At",
        portfolio_id="portfolio-wa-analytics-source-summary-occurred-at",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-source-summary-occurred-at",
        conversation_id="conv-wa-analytics-source-summary-occurred-at",
        user_id="user-wa-analytics-source-summary-occurred-at",
        template_name="wa_analytics_source_summary_occurred_at_template",
    )

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        event.created_at = datetime.fromisoformat("2026-06-06T12:15:00")
        event.occurred_at = datetime.fromisoformat("2026-06-08T09:30:00")
        event.payload = {
            **(event.payload or {}),
            "timestamp": "2026-06-07T12:15:00Z",
        }
        session.commit()

        service = WhatsAppAnalyticsService(session)
        occurred_at_summary = service._build_summary_from_source(
            account_id=account_id,
            waba_id=original_waba_id,
            phone_number_id=original_phone_number_id,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=True,
            hour_bucket=9,
            date_from=datetime.fromisoformat("2026-06-08").date(),
            date_to=datetime.fromisoformat("2026-06-08").date(),
            allowed_account_ids=None,
        )
        payload_timestamp_summary = service._build_summary_from_source(
            account_id=account_id,
            waba_id=original_waba_id,
            phone_number_id=original_phone_number_id,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=True,
            hour_bucket=None,
            date_from=datetime.fromisoformat("2026-06-07").date(),
            date_to=datetime.fromisoformat("2026-06-07").date(),
            allowed_account_ids=None,
        )
        created_at_summary = service._build_summary_from_source(
            account_id=account_id,
            waba_id=original_waba_id,
            phone_number_id=original_phone_number_id,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=True,
            hour_bucket=None,
            date_from=datetime.fromisoformat("2026-06-06").date(),
            date_to=datetime.fromisoformat("2026-06-06").date(),
            allowed_account_ids=None,
        )

        assert occurred_at_summary.conversation_count == 1
        assert occurred_at_summary.delivered_count == 1
        assert occurred_at_summary.billable_count == 1
        assert payload_timestamp_summary.conversation_count == 0
        assert payload_timestamp_summary.delivered_count == 0
        assert created_at_summary.conversation_count == 0
        assert created_at_summary.delivered_count == 0
    finally:
        session.close()


def test_rebuild_whatsapp_stats_route_falls_back_to_status_event_created_at_when_other_timestamps_are_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-status-created-at-fallback"
    original_waba_id = "waba-wa-analytics-status-created-at-fallback"
    original_phone_number_id = "pn-wa-analytics-status-created-at-fallback"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Status Created At Fallback",
        portfolio_id="portfolio-wa-analytics-status-created-at-fallback",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-status-created-at-fallback",
        conversation_id="conv-wa-analytics-status-created-at-fallback",
        user_id="user-wa-analytics-status-created-at-fallback",
        template_name="wa_analytics_status_created_at_fallback_template",
    )

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        event.created_at = datetime.fromisoformat("2026-06-09T03:45:00")
        event.occurred_at = None
        event.payload = {
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }
        session.commit()
    finally:
        session.close()

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-status-created-at-fallback-drifted",
        drifted_waba_id="waba-wa-analytics-status-created-at-fallback-drifted",
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "date_from": "2026-06-09",
            "date_to": "2026-06-09",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert {row.date.isoformat() for row in rebuilt_daily_rows} == {"2026-06-09"}
        assert {row.hour_bucket for row in rebuilt_daily_rows} == {3}
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == "waba-wa-analytics-status-created-at-fallback-drifted",
            )
            .count()
            == 0
        )
    finally:
        session.close()


def test_rebuild_whatsapp_stats_scoped_window_uses_nested_status_scope_without_rebuilding_other_rows(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-nested-status-window-rebuild"
    original_waba_id = "waba-wa-analytics-nested-status-window-rebuild-a"
    original_phone_number_id = "pn-wa-analytics-nested-status-window-rebuild-a"
    second_waba_id = "waba-wa-analytics-nested-status-window-rebuild-b"
    second_phone_number_id = "pn-wa-analytics-nested-status-window-rebuild-b"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Nested Status Window Rebuild A",
        portfolio_id="portfolio-wa-analytics-nested-status-window-rebuild",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-nested-status-window-rebuild-a",
        conversation_id="conv-wa-analytics-nested-status-window-rebuild-a-20260607",
        user_id="user-wa-analytics-nested-status-window-rebuild-a-20260607",
        template_name="wa_analytics_nested_status_window_rebuild_a_20260607",
        status_timestamp="2026-06-07T12:15:00Z",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-nested-status-window-rebuild-a",
        conversation_id="conv-wa-analytics-nested-status-window-rebuild-a-20260608",
        user_id="user-wa-analytics-nested-status-window-rebuild-a-20260608",
        template_name="wa_analytics_nested_status_window_rebuild_a_20260608",
        status_timestamp="2026-06-08T12:15:00Z",
    )
    _add_whatsapp_analytics_phone_scope(
        db_session_factory,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-nested-status-window-rebuild-b",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=second_waba_id,
        phone_number_id=second_phone_number_id,
        app_secret="secret-wa-analytics-nested-status-window-rebuild-b",
        conversation_id="conv-wa-analytics-nested-status-window-rebuild-b-20260607",
        user_id="user-wa-analytics-nested-status-window-rebuild-b-20260607",
        template_name="wa_analytics_nested_status_window_rebuild_b_20260607",
        status_timestamp="2026-06-07T16:45:00Z",
    )

    session = db_session_factory()
    try:
        target_event = (
            session.query(MessageEvent)
            .join(Message, MessageEvent.message_id == Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
                Conversation.external_conversation_id
                == "conv-wa-analytics-nested-status-window-rebuild-a-20260607",
            )
            .one()
        )
        target_event.waba_id = None
        target_event.phone_number_id = None
        target_event.payload = {
            "timestamp": "2026-06-07T12:15:00Z",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
            "provider_payload": {
                "waba_id": original_waba_id,
                "metadata": {
                    "phone_number_id": original_phone_number_id,
                },
            },
        }
        second_daily_before = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == second_waba_id,
                WhatsAppDailyStat.phone_number_id == second_phone_number_id,
            )
            .count()
        )
        second_fact_before = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == second_waba_id,
                WhatsAppConversationStat.phone_number_id == second_phone_number_id,
            )
            .count()
        )
        assert second_daily_before >= 1
        assert second_fact_before >= 1
        session.commit()
    finally:
        session.close()

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-nested-status-window-rebuild-a-drifted",
        drifted_waba_id="waba-wa-analytics-nested-status-window-rebuild-a-drifted",
    )

    session = db_session_factory()
    try:
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == account_id,
            WhatsAppDailyStat.waba_id == original_waba_id,
            WhatsAppDailyStat.phone_number_id == original_phone_number_id,
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == account_id,
            WhatsAppConversationStat.waba_id == original_waba_id,
            WhatsAppConversationStat.phone_number_id == original_phone_number_id,
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "date_from": "2026-06-07",
            "date_to": "2026-06-07",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == original_waba_id,
                WhatsAppConversationStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert rebuilt_fact_rows
        assert {row.date.isoformat() for row in rebuilt_daily_rows} == {"2026-06-07"}
        assert {row.date.isoformat() for row in rebuilt_fact_rows} == {"2026-06-07"}
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
        assert sum(row.delivered_count for row in rebuilt_fact_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
                WhatsAppDailyStat.date == datetime.fromisoformat("2026-06-08").date(),
            )
            .count()
            == 0
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == original_waba_id,
                WhatsAppConversationStat.phone_number_id == original_phone_number_id,
                WhatsAppConversationStat.date == datetime.fromisoformat("2026-06-08").date(),
            )
            .count()
            == 0
        )
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == second_waba_id,
                WhatsAppDailyStat.phone_number_id == second_phone_number_id,
            )
            .count()
            == second_daily_before
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == second_waba_id,
                WhatsAppConversationStat.phone_number_id == second_phone_number_id,
            )
            .count()
            == second_fact_before
        )
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == "waba-wa-analytics-nested-status-window-rebuild-a-drifted",
            )
            .count()
            == 0
        )
    finally:
        session.close()


def test_whatsapp_stats_summary_prefers_phone_snapshot_waba_when_relationship_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-snapshot-summary",
        display_name="WA Analytics Snapshot Summary",
        portfolio_id="portfolio-wa-analytics-snapshot-summary",
        waba_id="waba-wa-analytics-snapshot-summary",
        phone_number_id="pn-wa-analytics-snapshot-summary",
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-snapshot-summary",
            "conversation_id": "conv-wa-analytics-snapshot-summary",
            "user_id": "user-wa-analytics-snapshot-summary",
            "text": "hello summary snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-snapshot-summary",
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "wa-analytics-snapshot-summary",
                WhatsAppBusinessAccount.waba_id == "waba-wa-analytics-snapshot-summary",
            )
            .one()
        )
        waba_account.waba_id = "waba-wa-analytics-relationship-drifted-summary"
        session.commit()
    finally:
        session.close()

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": "wa-analytics-snapshot-summary",
            "waba_id": "waba-wa-analytics-snapshot-summary",
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["inbound_message_count"] == 1


def test_rebuild_whatsapp_stats_prefers_phone_snapshot_waba_when_relationship_drifts(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-snapshot-rebuild",
        display_name="WA Analytics Snapshot Rebuild",
        portfolio_id="portfolio-wa-analytics-snapshot-rebuild",
        waba_id="waba-wa-analytics-snapshot-rebuild",
        phone_number_id="pn-wa-analytics-snapshot-rebuild",
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-snapshot-rebuild",
            "conversation_id": "conv-wa-analytics-snapshot-rebuild",
            "user_id": "user-wa-analytics-snapshot-rebuild",
            "text": "hello rebuild snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-snapshot-rebuild",
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        waba_account = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "wa-analytics-snapshot-rebuild",
                WhatsAppBusinessAccount.waba_id == "waba-wa-analytics-snapshot-rebuild",
            )
            .one()
        )
        waba_account.waba_id = "waba-wa-analytics-relationship-drifted-rebuild"
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == "wa-analytics-snapshot-rebuild"
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == "wa-analytics-snapshot-rebuild"
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": "wa-analytics-snapshot-rebuild",
            "waba_id": "waba-wa-analytics-snapshot-rebuild",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-snapshot-rebuild")
            .all()
        )
        assert rebuilt_daily_rows
        assert {row.waba_id for row in rebuilt_daily_rows} == {
            "waba-wa-analytics-snapshot-rebuild"
        }
        assert sum(row.inbound_message_count for row in rebuilt_daily_rows) == 1
    finally:
        session.close()


def test_rebuild_whatsapp_stats_uses_event_snapshot_columns_when_status_payload_scope_is_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-status-column-snapshot"
    original_waba_id = "waba-wa-analytics-status-column-snapshot"
    original_phone_number_id = "pn-wa-analytics-status-column-snapshot"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Status Column Snapshot",
        portfolio_id="portfolio-wa-analytics-status-column-snapshot",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-status-column-snapshot",
        conversation_id="conv-wa-analytics-status-column-snapshot",
        user_id="user-wa-analytics-status-column-snapshot",
        template_name="wa_analytics_status_column_snapshot_template",
    )

    session = db_session_factory()
    try:
        event = (
            session.query(MessageEvent)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
            )
            .one()
        )
        assert event.waba_id == original_waba_id
        assert event.phone_number_id == original_phone_number_id
        event.payload = {
            "timestamp": "2026-06-07T12:15:00Z",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }
        session.commit()
    finally:
        session.close()

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-status-column-snapshot-current",
        drifted_waba_id="waba-wa-analytics-status-column-snapshot-current",
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == "waba-wa-analytics-status-column-snapshot-current",
            )
            .count()
            == 0
        )
    finally:
        session.close()


def test_rebuild_whatsapp_stats_mixes_relationship_fallback_with_snapshot_scope_under_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-history-fallback-mixed"
    original_waba_id = "waba-wa-analytics-history-fallback-mixed"
    original_phone_number_id = "pn-wa-analytics-history-fallback-mixed"
    drifted_waba_id = "waba-wa-analytics-history-fallback-mixed-current"
    drifted_phone_number_id = "pn-wa-analytics-history-fallback-mixed-current"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics History Fallback Mixed",
        portfolio_id="portfolio-wa-analytics-history-fallback-mixed",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-history-fallback-mixed",
        conversation_id="conv-wa-analytics-history-fallback-mixed-fallback",
        user_id="user-wa-analytics-history-fallback-mixed-fallback",
        template_name="wa_analytics_history_fallback_mixed_fallback_template",
    )
    _create_whatsapp_status_stats_for_existing_scope(
        client,
        account_id=account_id,
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-history-fallback-mixed",
        conversation_id="conv-wa-analytics-history-fallback-mixed-snapshot",
        user_id="user-wa-analytics-history-fallback-mixed-snapshot",
        template_name="wa_analytics_history_fallback_mixed_snapshot_template",
    )

    session = db_session_factory()
    try:
        fallback_inbound_message = (
            session.query(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Message.account_id == account_id,
                Message.direction == "inbound",
                Conversation.external_conversation_id
                == "conv-wa-analytics-history-fallback-mixed-fallback",
            )
            .one()
        )
        fallback_inbound_message.payload = {"provider_payload": {"metadata": {}}}
        for message_event in fallback_inbound_message.events:
            message_event.waba_id = None
            message_event.phone_number_id = None
            message_event.payload = {"provider_payload": {"metadata": {}}}

        fallback_event = (
            session.query(MessageEvent)
            .join(Message, MessageEvent.message_id == Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
                Conversation.external_conversation_id
                == "conv-wa-analytics-history-fallback-mixed-fallback",
            )
            .one()
        )
        fallback_event.waba_id = None
        fallback_event.phone_number_id = None
        fallback_event.payload = {
            "timestamp": "2026-06-07T12:15:00Z",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }

        snapshot_event = (
            session.query(MessageEvent)
            .join(Message, MessageEvent.message_id == Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == "whatsapp_status_delivered",
                Conversation.external_conversation_id
                == "conv-wa-analytics-history-fallback-mixed-snapshot",
            )
            .one()
        )
        assert snapshot_event.waba_id == original_waba_id
        assert snapshot_event.phone_number_id == original_phone_number_id
        snapshot_event.payload = {
            "timestamp": "2026-06-07T12:15:00Z",
            "conversation": {"origin": {"type": "business_initiated"}},
            "pricing": {
                "billable": True,
                "category": "utility",
                "pricing_model": "CBP",
            },
        }
        session.commit()
    finally:
        session.close()

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id=drifted_phone_number_id,
        drifted_waba_id=drifted_waba_id,
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={"account_id": account_id},
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        original_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        drifted_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == drifted_waba_id,
                WhatsAppDailyStat.phone_number_id == drifted_phone_number_id,
            )
            .all()
        )

        assert original_daily_rows
        assert drifted_daily_rows
        assert sum(row.delivered_count for row in original_daily_rows) == 1
        assert sum(row.billable_count for row in original_daily_rows) == 1
        assert sum(row.delivered_count for row in drifted_daily_rows) >= 1
        assert sum(row.inbound_message_count for row in drifted_daily_rows) >= 1
        assert (
            sum(row.delivered_count for row in original_daily_rows)
            + sum(row.delivered_count for row in drifted_daily_rows)
            == 2
        )
    finally:
        session.close()


def test_whatsapp_stats_summary_and_detail_allow_source_only_historical_scope_after_drift(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-source-only-history"
    original_waba_id = "waba-wa-analytics-source-only-history"
    original_phone_number_id = "pn-wa-analytics-source-only-history"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Source Only History",
        portfolio_id="portfolio-wa-analytics-source-only-history",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-source-only-history",
        conversation_id="conv-wa-analytics-source-only-history",
        user_id="user-wa-analytics-source-only-history",
        template_name="wa_analytics_source_only_history_template",
    )

    _drift_whatsapp_phone_relationship(
        db_session_factory,
        account_id=account_id,
        phone_number_id=original_phone_number_id,
        drifted_phone_number_id="pn-wa-analytics-source-only-history-current",
        drifted_waba_id="waba-wa-analytics-source-only-history-current",
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["conversation_count"] == 0
    assert summary["delivered_count"] == 0
    assert summary["billable_count"] == 0

    detail_response = client.get(
        "/api/whatsapp/stats/detail",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
            "billable": "true",
        },
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["summary"]["conversation_count"] == 0
    assert detail["summary"]["delivered_count"] == 0
    assert detail["daily_rows"] == []


def test_rebuild_whatsapp_stats_keeps_official_waba_after_local_waba_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_whatsapp_analytics_account(
        client,
        account_id="wa-analytics-recreated-waba-rebuild",
        display_name="WA Analytics Recreated WABA Rebuild",
        portfolio_id="portfolio-wa-analytics-recreated-waba-rebuild",
        waba_id="waba-wa-analytics-recreated-waba-rebuild",
        phone_number_id="pn-wa-analytics-recreated-waba-rebuild",
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "wa-analytics-recreated-waba-rebuild",
            "conversation_id": "conv-wa-analytics-recreated-waba-rebuild",
            "user_id": "user-wa-analytics-recreated-waba-rebuild",
            "text": "hello recreated rebuild snapshot",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": "pn-wa-analytics-recreated-waba-rebuild",
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        legacy_waba = (
            session.query(WhatsAppBusinessAccount)
            .filter(
                WhatsAppBusinessAccount.account_id == "wa-analytics-recreated-waba-rebuild",
                WhatsAppBusinessAccount.waba_id == "waba-wa-analytics-recreated-waba-rebuild",
            )
            .one()
        )
        legacy_waba.waba_id = "waba-wa-analytics-recreated-waba-rebuild-legacy"
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == "wa-analytics-recreated-waba-rebuild"
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == "wa-analytics-recreated-waba-rebuild"
        ).delete(synchronize_session=False)
        session.flush()

        recreated_waba = WhatsAppBusinessAccount(
            account_id="wa-analytics-recreated-waba-rebuild",
            portfolio_id=legacy_waba.portfolio_id,
            waba_id="waba-wa-analytics-recreated-waba-rebuild",
            onboarding_mode="manual",
            token_source="system_user",
            access_token="token-wa-analytics-recreated-waba-rebuild",
            verify_token="verify-wa-analytics-recreated-waba-rebuild",
            app_secret="secret-wa-analytics-recreated-waba-rebuild",
            webhook_subscribed=False,
            is_active=True,
            ai_enabled=True,
        )
        session.add(recreated_waba)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": "wa-analytics-recreated-waba-rebuild",
            "waba_id": "waba-wa-analytics-recreated-waba-rebuild",
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(WhatsAppDailyStat.account_id == "wa-analytics-recreated-waba-rebuild")
            .all()
        )
        assert rebuilt_daily_rows
        assert {row.waba_id for row in rebuilt_daily_rows} == {
            "waba-wa-analytics-recreated-waba-rebuild"
        }
        assert sum(row.inbound_message_count for row in rebuilt_daily_rows) == 1
    finally:
        session.close()


def test_rebuild_whatsapp_stats_keeps_official_phone_after_local_phone_row_recreation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-recreated-phone-rebuild"
    original_waba_id = "waba-wa-analytics-recreated-phone-rebuild"
    original_phone_number_id = "pn-wa-analytics-recreated-phone-rebuild"
    legacy_phone_number_id = "pn-wa-analytics-recreated-phone-rebuild-legacy"

    _create_whatsapp_status_stats_fixture(
        client,
        account_id=account_id,
        display_name="WA Analytics Recreated Phone Rebuild",
        portfolio_id="portfolio-wa-analytics-recreated-phone-rebuild",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        app_secret="secret-wa-analytics-recreated-phone-rebuild",
        conversation_id="conv-wa-analytics-recreated-phone-rebuild",
        user_id="user-wa-analytics-recreated-phone-rebuild",
        template_name="wa_analytics_snapshot_recreated_phone_rebuild_template",
    )

    _recreate_whatsapp_phone_number_row(
        db_session_factory,
        account_id=account_id,
        official_phone_number_id=original_phone_number_id,
        legacy_phone_number_id=legacy_phone_number_id,
    )
    _delete_whatsapp_stats(db_session_factory, account_id=account_id)

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    session = db_session_factory()
    try:
        rebuilt_daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == original_waba_id,
                WhatsAppDailyStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        rebuilt_fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == original_waba_id,
                WhatsAppConversationStat.phone_number_id == original_phone_number_id,
            )
            .all()
        )
        assert rebuilt_daily_rows
        assert rebuilt_fact_rows
        assert sum(row.delivered_count for row in rebuilt_daily_rows) == 1
        assert sum(row.billable_count for row in rebuilt_daily_rows) == 1
        assert sum(row.delivered_count for row in rebuilt_fact_rows) == 1
        assert (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.phone_number_id == legacy_phone_number_id,
            )
            .count()
            == 0
        )
        assert (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.phone_number_id == legacy_phone_number_id,
            )
            .count()
            == 0
        )
    finally:
        session.close()


def test_rebuild_whatsapp_stats_extracts_scope_from_nested_message_payload(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-nested-message-scope"
    original_waba_id = "waba-wa-analytics-nested-message-scope"
    original_phone_number_id = "pn-wa-analytics-nested-message-scope"

    register_whatsapp_analytics_account(
        client,
        account_id=account_id,
        display_name="WA Analytics Nested Message Scope",
        portfolio_id="portfolio-wa-analytics-nested-message-scope",
        waba_id=original_waba_id,
        phone_number_id=original_phone_number_id,
        access_token="token-wa-analytics-nested-message-scope",
        verify_token="verify-wa-analytics-nested-message-scope",
        app_secret="secret-wa-analytics-nested-message-scope",
    )

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": account_id,
            "conversation_id": "conv-wa-analytics-nested-message-scope",
            "user_id": "user-wa-analytics-nested-message-scope",
            "text": "hello nested analytics scope",
            "mode": "echo",
            "language_hint": "en",
            "phone_number_id": original_phone_number_id,
        },
    )
    assert inbound_response.status_code == 200

    session = db_session_factory()
    try:
        message = (
            session.query(Message)
            .filter(
                Message.account_id == account_id,
                Message.direction == "inbound",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .first()
        )
        assert message is not None
        message.payload = {
            "provider_payload": {
                "waba_id": original_waba_id,
                "metadata": {
                    "phone_number_id": original_phone_number_id,
                },
            }
        }
        session.query(WhatsAppDailyStat).filter(
            WhatsAppDailyStat.account_id == account_id
        ).delete(synchronize_session=False)
        session.query(WhatsAppConversationStat).filter(
            WhatsAppConversationStat.account_id == account_id
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

    rebuild_response = client.post(
        "/api/whatsapp/stats/rebuild",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert rebuild_response.status_code == 200, rebuild_response.text

    summary_response = client.get(
        "/api/whatsapp/stats/summary",
        params={
            "account_id": account_id,
            "waba_id": original_waba_id,
            "phone_number_id": original_phone_number_id,
        },
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["conversation_count"] == 1
    assert summary["inbound_message_count"] == 1


def test_whatsapp_stats_aggregator_records_nested_message_scope_without_phone_relationship(
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "wa-analytics-aggregator-nested-account"
    waba_account_id = "wa-analytics-aggregator-nested-waba-account"
    conversation_id = "wa-analytics-aggregator-nested-conversation"
    provider_phone_number_id = "pn-wa-analytics-aggregator-nested"
    nested_waba_id = "waba-wa-analytics-aggregator-nested"

    with db_session_factory() as session:
        session.add(
            Account(
                account_id=account_id,
                display_name="WA Analytics Aggregator Nested",
                provider_type="whatsapp",
                is_active=True,
                ai_enabled=True,
            )
        )
        session.add(
            WhatsAppBusinessAccount(
                id=waba_account_id,
                account_id=account_id,
                portfolio_id=None,
                waba_id=nested_waba_id,
                onboarding_mode="manual",
                token_source="system_user",
                access_token=None,
                verify_token=None,
                app_secret=None,
                webhook_subscribed=False,
                webhook_verification_status="pending",
                webhook_runtime_status="pending",
                is_active=True,
                ai_enabled=True,
            )
        )
        session.add(
            Conversation(
                id=conversation_id,
                account_id=account_id,
                external_conversation_id="ext-wa-analytics-aggregator-nested",
                phone_number_id=None,
                customer_id="wa-analytics-aggregator-nested-user",
                customer_language="en",
                customer_language_source="test",
                status="open",
                ai_enabled=True,
                management_mode="ai_managed",
                assigned_agent_id=None,
                last_message_at=None,
            )
        )
        message = Message(
            account_id=account_id,
            conversation_id=conversation_id,
            phone_number_id=None,
            provider_message_id="provider-message-wa-analytics-aggregator-nested",
            direction="outbound",
            message_type="text",
            language_code="en",
            translated_text=None,
            translated_language_code=None,
            sender_id="agent-test",
            recipient_id="wa-analytics-aggregator-nested-user",
            content_text="nested scope message",
            payload={
                "provider_payload": {
                    "metadata": {
                        "waba_id": nested_waba_id,
                        "phone_number_id": provider_phone_number_id,
                    }
                }
            },
            ai_generated=False,
            sent_by_agent_id=None,
        )
        session.add(message)
        session.flush()

        aggregator = WhatsAppStatsAggregator(session)
        aggregator.record_message_created(message=message, conversation=None)
        session.commit()

        fact_rows = (
            session.query(WhatsAppConversationStat)
            .filter(
                WhatsAppConversationStat.account_id == account_id,
                WhatsAppConversationStat.waba_id == nested_waba_id,
                WhatsAppConversationStat.phone_number_id == provider_phone_number_id,
            )
            .all()
        )
        daily_rows = (
            session.query(WhatsAppDailyStat)
            .filter(
                WhatsAppDailyStat.account_id == account_id,
                WhatsAppDailyStat.waba_id == nested_waba_id,
                WhatsAppDailyStat.phone_number_id == provider_phone_number_id,
            )
            .all()
        )

        assert len(fact_rows) == 1
        assert fact_rows[0].outbound_message_count == 1
        assert len(daily_rows) == 1
        assert daily_rows[0].outbound_message_count == 1

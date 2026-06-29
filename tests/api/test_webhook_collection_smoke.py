from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_whatsapp_webhooks import (
    register_meta_account_with_webhook_secret,
    subscribe_meta_webhook,
)


def test_webhook_verify_smoke_is_collected_in_api_suite(client: TestClient) -> None:
    register_meta_account_with_webhook_secret(client)
    subscribe_meta_webhook(client)

    response = client.get(
        "/webhooks/whatsapp/meta-webhook-account/wabas/waba-webhook-1",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-webhook-1",
            "hub.challenge": "ci-webhook-smoke",
        },
    )

    assert response.status_code == 200
    assert response.text == "ci-webhook-smoke"

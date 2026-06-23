from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    EmbeddedSignupSession as EmbeddedSignupSessionModel,
    WebhookSubscription,
    WhatsAppBusinessAccount,
)


def _create_manual_meta_account(
    client: TestClient,
    *,
    account_id: str,
    display_name: str,
    meta_business_portfolio_id: str,
    waba_id: str,
    verify_token: str | None = None,
    app_secret: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "account_id": account_id,
        "display_name": display_name,
        "meta_business_portfolio_id": meta_business_portfolio_id,
        "waba_id": waba_id,
        "access_token": f"token-{account_id}",
        "token_source": "system_user",
        "phone_numbers": [],
    }
    if verify_token is not None:
        payload["verify_token"] = verify_token
    if app_secret is not None:
        payload["app_secret"] = app_secret

    response = client.post("/api/meta/accounts/manual", json=payload)
    assert response.status_code == 200


def _assert_verify_token_conflict(response_detail: str) -> None:
    normalized_detail = response_detail.lower()
    assert "verify" in normalized_detail
    assert any(
        keyword in normalized_detail
        for keyword in ("waba", "shared", "conflict", "already")
    )


def test_manual_meta_account_rejects_verify_token_reuse_across_wabas(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="meta-verify-create-a",
        display_name="Meta Verify Create A",
        meta_business_portfolio_id="portfolio-verify-create-a",
        waba_id="waba-verify-create-a",
        verify_token="verify-create-shared",
        app_secret="secret-verify-create-a",
    )

    conflicting_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "meta-verify-create-b",
            "display_name": "Meta Verify Create B",
            "meta_business_portfolio_id": "portfolio-verify-create-b",
            "waba_id": "waba-verify-create-b",
            "access_token": "token-meta-verify-create-b",
            "verify_token": "verify-create-shared",
            "app_secret": "secret-verify-create-b",
            "token_source": "system_user",
            "phone_numbers": [],
        },
    )

    assert conflicting_response.status_code == 409
    _assert_verify_token_conflict(conflicting_response.json()["detail"])

    with db_session_factory() as session:
        stored_rows = session.execute(
            select(WhatsAppBusinessAccount)
            .where(WhatsAppBusinessAccount.verify_token == "verify-create-shared")
            .order_by(WhatsAppBusinessAccount.account_id, WhatsAppBusinessAccount.waba_id)
        ).scalars().all()

    assert len(stored_rows) == 1
    assert stored_rows[0].account_id == "meta-verify-create-a"
    assert stored_rows[0].waba_id == "waba-verify-create-a"


def test_update_meta_account_rejects_verify_token_taken_by_another_waba(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="meta-verify-update-a",
        display_name="Meta Verify Update A",
        meta_business_portfolio_id="portfolio-verify-update-a",
        waba_id="waba-verify-update-a",
        verify_token="verify-update-a",
        app_secret="secret-verify-update-a",
    )
    _create_manual_meta_account(
        client,
        account_id="meta-verify-update-b",
        display_name="Meta Verify Update B",
        meta_business_portfolio_id="portfolio-verify-update-b",
        waba_id="waba-verify-update-b",
        verify_token="verify-update-b",
        app_secret="secret-verify-update-b",
    )

    conflicting_response = client.patch(
        "/api/meta/accounts/meta-verify-update-a/wabas/waba-verify-update-a",
        json={
            "display_name": "Meta Verify Update A Revised",
            "meta_business_portfolio_id": "portfolio-verify-update-a-revised",
            "verify_token": "verify-update-b",
            "phone_numbers": [],
        },
    )

    assert conflicting_response.status_code == 409
    _assert_verify_token_conflict(conflicting_response.json()["detail"])

    with db_session_factory() as session:
        waba_a = session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == "meta-verify-update-a",
                WhatsAppBusinessAccount.waba_id == "waba-verify-update-a",
            )
        ).scalar_one()
        waba_b = session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == "meta-verify-update-b",
                WhatsAppBusinessAccount.waba_id == "waba-verify-update-b",
            )
        ).scalar_one()

    assert waba_a.verify_token == "verify-update-a"
    assert waba_b.verify_token == "verify-update-b"


def test_webhook_subscription_rejects_verify_token_that_would_conflict_cross_waba(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="meta-verify-webhook-a",
        display_name="Meta Verify Webhook A",
        meta_business_portfolio_id="portfolio-verify-webhook-a",
        waba_id="waba-verify-webhook-a",
        verify_token="verify-webhook-a",
        app_secret="secret-verify-webhook-a",
    )
    _create_manual_meta_account(
        client,
        account_id="meta-verify-webhook-b",
        display_name="Meta Verify Webhook B",
        meta_business_portfolio_id="portfolio-verify-webhook-b",
        waba_id="waba-verify-webhook-b",
        verify_token="verify-webhook-b",
        app_secret="secret-verify-webhook-b",
    )

    initial_subscription_response = client.post(
        "/api/meta/accounts/meta-verify-webhook-b/wabas/waba-verify-webhook-b/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhooks/verify-webhook-b",
            "verify_token": "verify-webhook-b",
            "app_id": "app-verify-webhook-b",
        },
    )
    assert initial_subscription_response.status_code == 200

    conflicting_response = client.post(
        "/api/meta/accounts/meta-verify-webhook-b/wabas/waba-verify-webhook-b/webhook-subscription",
        json={
            "callback_url": "https://example.com/webhooks/verify-webhook-b",
            "verify_token": "verify-webhook-a",
            "app_id": "app-verify-webhook-b-conflict",
        },
    )

    assert conflicting_response.status_code == 409
    _assert_verify_token_conflict(conflicting_response.json()["detail"])

    with db_session_factory() as session:
        waba_b = session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == "meta-verify-webhook-b",
                WhatsAppBusinessAccount.waba_id == "waba-verify-webhook-b",
            )
        ).scalar_one()
        subscriptions = session.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.account_id == "meta-verify-webhook-b",
                WebhookSubscription.waba_id == "waba-verify-webhook-b",
            )
        ).scalars().all()

    assert waba_b.verify_token == "verify-webhook-b"
    assert len(subscriptions) == 1
    assert subscriptions[0].callback_url == "https://example.com/webhooks/verify-webhook-b"
    assert subscriptions[0].verify_token == "verify-webhook-b"
    assert subscriptions[0].app_id == "app-verify-webhook-b"


def test_embedded_signup_callback_rejects_verify_token_that_would_conflict_cross_waba(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="meta-verify-signup-a",
        display_name="Meta Verify Signup A",
        meta_business_portfolio_id="portfolio-verify-signup-a",
        waba_id="waba-verify-signup-a",
        verify_token="verify-signup-shared",
        app_secret="secret-verify-signup-a",
    )

    create_session_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-verify-signup-b",
            "display_name": "Meta Verify Signup B",
            "redirect_uri": "https://example.com/embedded-signup/verify-token-conflict",
            "webhook_subscription": {
                "callback_url": "https://example.com/webhooks/embedded-signup-verify-conflict",
                "verify_token": "verify-signup-shared",
                "app_id": "app-verify-signup-b",
            },
        },
    )
    assert create_session_response.status_code == 200
    session_id = create_session_response.json()["session_id"]

    conflicting_response = client.post(
        f"/webhooks/meta/embedded-signup/session/{session_id}",
        json={
            "status": "completed",
            "waba_id": "waba-verify-signup-b",
            "meta_business_portfolio_id": "portfolio-verify-signup-b",
            "phone_number_ids": ["pn-verify-signup-b"],
            "system_user_access_token": "token-verify-signup-b",
        },
    )

    assert conflicting_response.status_code == 409
    _assert_verify_token_conflict(conflicting_response.json()["detail"])

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-verify-signup-b"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["webhook_verify_token_present"] is True

    with db_session_factory() as session:
        stored_signup_session = session.execute(
            select(EmbeddedSignupSessionModel).where(
                EmbeddedSignupSessionModel.session_id == session_id
            )
        ).scalar_one()
        created_wabas = session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == "meta-verify-signup-b"
            )
        ).scalars().all()
        created_subscriptions = session.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.account_id == "meta-verify-signup-b"
            )
        ).scalars().all()

    assert stored_signup_session.status == "created"
    assert stored_signup_session.completion_stage == "pending_callback"
    assert created_wabas == []
    assert created_subscriptions == []


def test_embedded_signup_complete_rejects_verify_token_that_would_conflict_cross_waba(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_manual_meta_account(
        client,
        account_id="meta-verify-signup-complete-a",
        display_name="Meta Verify Signup Complete A",
        meta_business_portfolio_id="portfolio-verify-signup-complete-a",
        waba_id="waba-verify-signup-complete-a",
        verify_token="verify-signup-complete-shared",
        app_secret="secret-verify-signup-complete-a",
    )

    create_session_response = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": "meta-verify-signup-complete-b",
            "display_name": "Meta Verify Signup Complete B",
            "redirect_uri": "https://example.com/embedded-signup/verify-token-conflict-complete",
            "webhook_subscription": {
                "callback_url": "https://example.com/webhooks/embedded-signup-verify-conflict-complete",
                "verify_token": "verify-signup-complete-shared",
                "app_id": "app-verify-signup-complete-b",
            },
        },
    )
    assert create_session_response.status_code == 200
    session_id = create_session_response.json()["session_id"]

    conflicting_response = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/complete",
        json={
            "waba_id": "waba-verify-signup-complete-b",
            "meta_business_portfolio_id": "portfolio-verify-signup-complete-b",
            "phone_number_ids": ["pn-verify-signup-complete-b"],
            "system_user_access_token": "token-verify-signup-complete-b",
        },
    )

    assert conflicting_response.status_code == 409
    _assert_verify_token_conflict(conflicting_response.json()["detail"])

    sessions_response = client.get(
        "/api/meta/accounts/embedded-signup/sessions",
        params={"account_id": "meta-verify-signup-complete-b"},
    )
    assert sessions_response.status_code == 200
    session_payload = sessions_response.json()[0]
    assert session_payload["session_id"] == session_id
    assert session_payload["status"] == "created"
    assert session_payload["completion_stage"] == "pending_callback"
    assert session_payload["webhook_verify_token_present"] is True

    with db_session_factory() as session:
        stored_signup_session = session.execute(
            select(EmbeddedSignupSessionModel).where(
                EmbeddedSignupSessionModel.session_id == session_id
            )
        ).scalar_one()
        created_wabas = session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.account_id == "meta-verify-signup-complete-b"
            )
        ).scalars().all()
        created_subscriptions = session.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.account_id == "meta-verify-signup-complete-b"
            )
        ).scalars().all()

    assert stored_signup_session.status == "created"
    assert stored_signup_session.completion_stage == "pending_callback"
    assert created_wabas == []
    assert created_subscriptions == []

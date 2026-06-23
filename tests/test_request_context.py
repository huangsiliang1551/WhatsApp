from fastapi.testclient import TestClient

from app.core.request_context import REQUEST_ID_HEADER
from app.main import app


def test_health_response_includes_generated_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]


def test_validation_error_preserves_request_id_header(client: TestClient) -> None:
    response = client.get(
        "/api/ecommerce/orders/MOCK-1001",
        headers={REQUEST_ID_HEADER: "req-validation-123"},
    )

    assert response.status_code == 422
    assert response.headers[REQUEST_ID_HEADER] == "req-validation-123"
    assert response.json()["request_id"] == "req-validation-123"
    assert isinstance(response.json()["detail"], list)


def test_validation_error_serializes_exception_context(client: TestClient) -> None:
    register_response = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": "req-validation-media-account",
            "display_name": "Request Validation Media Account",
            "meta_business_portfolio_id": "req-validation-portfolio",
            "waba_id": "req-validation-waba",
            "access_token": "req-validation-token",
            "verify_token": "req-validation-verify",
            "app_secret": "req-validation-secret",
            "token_source": "system_user",
            "phone_numbers": [
                {
                    "phone_number_id": "req-validation-phone",
                    "display_phone_number": "+1 555 200 0001",
                    "verified_name": "Validation Phone",
                    "quality_rating": "GREEN",
                    "is_registered": True,
                }
            ],
        },
    )
    assert register_response.status_code == 200

    response = client.post(
        "/api/media/assets",
        headers={REQUEST_ID_HEADER: "req-validation-json-safe"},
        json={
            "account_id": "req-validation-media-account",
            "waba_id": "req-validation-waba",
            "name": "invalid-provider-reference",
            "asset_type": "image",
            "mime_type": "image/jpeg",
            "meta_media_id": "legacy-provider-reference",
            "source": "manual_import",
        },
    )

    assert response.status_code == 422
    assert response.headers[REQUEST_ID_HEADER] == "req-validation-json-safe"
    assert response.json()["request_id"] == "req-validation-json-safe"
    assert response.json()["detail"][0]["ctx"]["error"] == (
        "provider_media_id requires phone_number_id so the media reference stays scoped "
        "to a Phone-Number-ID."
    )


def test_http_exception_response_includes_request_id(client: TestClient) -> None:
    response = client.get(
        "/api/ecommerce/orders/missing-order",
        params={"account_id": "demo-account-es"},
        headers={REQUEST_ID_HEADER: "req-http-404"},
    )

    assert response.status_code == 404
    assert response.headers[REQUEST_ID_HEADER] == "req-http-404"
    assert response.json()["request_id"] == "req-http-404"
    assert "missing-order" in response.json()["detail"]


def test_unhandled_exception_returns_internal_server_error_with_request_id(
    client: TestClient,
    monkeypatch,
) -> None:
    def broken_get_settings():
        raise RuntimeError("unexpected test failure")

    monkeypatch.setattr("app.api.routes.health.get_settings", broken_get_settings)

    with TestClient(app, raise_server_exceptions=False) as unsafe_client:
        response = unsafe_client.get(
            "/health",
            headers={REQUEST_ID_HEADER: "req-internal-500"},
        )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "req-internal-500"
    assert response.json()["request_id"] == "req-internal-500"
    assert response.json()["detail"] == "Internal server error."

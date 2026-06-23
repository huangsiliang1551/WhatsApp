from fastapi.testclient import TestClient

from app.core.settings import get_settings


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_preflight(client: TestClient) -> None:
    """CORS preflight request returns correct headers."""
    settings = get_settings()
    allow_origin = settings.cors_origins.split(",")[0].strip()
    response = client.options(
        "/health",
        headers={
            "Origin": allow_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allow_origin


def test_cors_allowed_origin(client: TestClient) -> None:
    """CORS allows configured origins."""
    settings = get_settings()
    allow_origin = settings.cors_origins.split(",")[0].strip()
    response = client.get(
        "/health",
        headers={"Origin": allow_origin},
    )
    assert response.headers.get("access-control-allow-origin") == allow_origin

from __future__ import annotations

import pytest

from app.core.settings import Settings


def _build_settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "APP_ENV": "development",
        "ADMIN_JWT_SECRET": "x" * 32,
        "ADMIN_DEFAULT_USERNAME": "ops-root",
        "ADMIN_DEFAULT_PASSWORD": "very-secure-password",
        "MESSAGING_PROVIDER": "whatsapp",
        "AI_PROVIDER": "openai",
        "WEBHOOK_SIGNATURE_ENABLED": True,
        "H5_MEMBER_COOKIE_SECURE": True,
        "H5_MEMBER_COOKIE_SAMESITE": "lax",
        "CORS_ORIGINS": "https://console.example.com",
    }
    payload.update(overrides)
    return Settings.model_validate(payload)


def test_production_guard_collects_blocking_issues_for_unsafe_production() -> None:
    from app.core.production_guard import collect_production_issues

    settings = _build_settings(
        APP_ENV="production",
        ADMIN_JWT_SECRET="change-me-in-production",
        ADMIN_DEFAULT_USERNAME="admin",
        ADMIN_DEFAULT_PASSWORD="admin123",
        MESSAGING_PROVIDER="mock",
        AI_PROVIDER="mock",
        WEBHOOK_SIGNATURE_ENABLED=False,
        H5_MEMBER_COOKIE_SECURE=False,
        CORS_ORIGINS="http://localhost:5173",
    )

    issue_codes = {item.code for item in collect_production_issues(settings)}

    assert "UNSAFE_ADMIN_JWT_SECRET" in issue_codes
    assert "DEFAULT_ADMIN_USERNAME_ENABLED" in issue_codes
    assert "DEFAULT_ADMIN_PASSWORD_ENABLED" in issue_codes
    assert "MOCK_MESSAGING_PROVIDER" in issue_codes
    assert "MOCK_AI_PROVIDER" in issue_codes
    assert "WEBHOOK_SIGNATURE_DISABLED" in issue_codes
    assert "H5_COOKIE_INSECURE" in issue_codes
    assert "UNSAFE_CORS_ORIGIN" in issue_codes
    assert "NON_HTTPS_CORS_ORIGIN" in issue_codes


def test_production_guard_blocks_unsafe_production() -> None:
    from app.core.production_guard import ProductionGuardError, assert_production_safe

    settings = _build_settings(
        APP_ENV="production",
        ADMIN_JWT_SECRET="short-secret",
        MESSAGING_PROVIDER="mock",
    )

    with pytest.raises(ProductionGuardError, match="Production guard failed"):
        assert_production_safe(settings)


def test_production_guard_allows_development_defaults() -> None:
    from app.core.production_guard import assert_production_safe, collect_production_issues

    settings = _build_settings(
        APP_ENV="development",
        ADMIN_JWT_SECRET="change-me-in-production",
        ADMIN_DEFAULT_USERNAME="admin",
        ADMIN_DEFAULT_PASSWORD="admin123",
        MESSAGING_PROVIDER="mock",
        AI_PROVIDER="mock",
        WEBHOOK_SIGNATURE_ENABLED=False,
        H5_MEMBER_COOKIE_SECURE=False,
        CORS_ORIGINS="http://localhost:5173",
    )

    assert collect_production_issues(settings) == []
    assert_production_safe(settings)

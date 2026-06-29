from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.settings import Settings


@dataclass(frozen=True, slots=True)
class ProductionGuardIssue:
    code: str
    message: str
    severity: str = "S"


class ProductionGuardError(RuntimeError):
    """Raised when production startup safety checks fail."""


UNSAFE_ADMIN_SECRETS = {
    "",
    "change-me-in-production",
    "changeme",
    "secret",
    "admin",
}

UNSAFE_PASSWORDS = {
    "",
    "admin",
    "admin123",
    "password",
    "123456",
}


def collect_production_issues(settings: Settings) -> list[ProductionGuardIssue]:
    issues: list[ProductionGuardIssue] = []
    env = (settings.app_env or "").strip().lower()
    if env != "production" or settings.test_mode:
        return issues

    if settings.admin_jwt_secret.strip() in UNSAFE_ADMIN_SECRETS or len(settings.admin_jwt_secret.strip()) < 32:
        issues.append(
            ProductionGuardIssue(
                code="UNSAFE_ADMIN_JWT_SECRET",
                message="ADMIN_JWT_SECRET is empty/default/too short.",
            )
        )

    if (settings.admin_default_username or "").strip().lower() == "admin":
        issues.append(
            ProductionGuardIssue(
                code="DEFAULT_ADMIN_USERNAME_ENABLED",
                message="ADMIN_DEFAULT_USERNAME must not be 'admin' in production.",
            )
        )

    if (settings.admin_default_password or "").strip() in UNSAFE_PASSWORDS:
        issues.append(
            ProductionGuardIssue(
                code="DEFAULT_ADMIN_PASSWORD_ENABLED",
                message="ADMIN_DEFAULT_PASSWORD is default/empty in production.",
            )
        )

    if (settings.messaging_provider or "").strip().lower() == "mock":
        issues.append(
            ProductionGuardIssue(
                code="MOCK_MESSAGING_PROVIDER",
                message="MESSAGING_PROVIDER=mock is not allowed in production.",
            )
        )

    if (settings.ai_provider or "").strip().lower() == "mock":
        issues.append(
            ProductionGuardIssue(
                code="MOCK_AI_PROVIDER",
                message="AI_PROVIDER=mock is not allowed in production.",
                severity="A",
            )
        )

    if not settings.webhook_signature_enabled:
        issues.append(
            ProductionGuardIssue(
                code="WEBHOOK_SIGNATURE_DISABLED",
                message="WEBHOOK_SIGNATURE_ENABLED must be true in production.",
            )
        )

    if not settings.h5_member_cookie_secure:
        issues.append(
            ProductionGuardIssue(
                code="H5_COOKIE_INSECURE",
                message="H5_MEMBER_COOKIE_SECURE must be true in production.",
            )
        )

    if settings.h5_member_cookie_samesite.lower() not in {"lax", "strict", "none"}:
        issues.append(
            ProductionGuardIssue(
                code="INVALID_COOKIE_SAMESITE",
                message="H5_MEMBER_COOKIE_SAMESITE must be lax/strict/none.",
            )
        )

    cors_origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    if not cors_origins:
        issues.append(
            ProductionGuardIssue(
                code="EMPTY_CORS_ORIGINS",
                message="CORS_ORIGINS must be configured in production.",
            )
        )
    for origin in cors_origins:
        parsed = urlparse(origin)
        if origin == "*" or parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
            issues.append(
                ProductionGuardIssue(
                    code="UNSAFE_CORS_ORIGIN",
                    message=f"Unsafe production CORS origin: {origin}",
                )
            )
        if parsed.scheme != "https":
            issues.append(
                ProductionGuardIssue(
                    code="NON_HTTPS_CORS_ORIGIN",
                    message=f"Production CORS origin must be https: {origin}",
                    severity="A",
                )
            )

    if (settings.meta_management_provider or "").strip().lower() == "whatsapp":
        if not settings.meta_app_secret.strip():
            issues.append(
                ProductionGuardIssue(
                    code="MISSING_META_APP_SECRET",
                    message="META_APP_SECRET is required when META_MANAGEMENT_PROVIDER=whatsapp.",
                )
            )
        if not settings.meta_global_webhook_verify_token.strip():
            issues.append(
                ProductionGuardIssue(
                    code="MISSING_META_VERIFY_TOKEN",
                    message="META_GLOBAL_WEBHOOK_VERIFY_TOKEN is required in production.",
                )
            )

    payment_key = os.environ.get("PAYMENT_CONFIG_ENCRYPTION_KEY", "").strip() or settings.secret_encryption_key.strip()
    if not payment_key:
        issues.append(
            ProductionGuardIssue(
                code="MISSING_PAYMENT_CONFIG_ENCRYPTION_KEY",
                message="PAYMENT_CONFIG_ENCRYPTION_KEY is required in production.",
            )
        )

    allow_default_admin_bootstrap = os.environ.get("ALLOW_DEFAULT_ADMIN_BOOTSTRAP", "true").strip().lower()
    if allow_default_admin_bootstrap not in {"false", "0", "no"}:
        issues.append(
            ProductionGuardIssue(
                code="DEFAULT_ADMIN_BOOTSTRAP_ENABLED",
                message="ALLOW_DEFAULT_ADMIN_BOOTSTRAP must be false in production.",
                severity="A",
            )
        )

    return issues


def assert_production_safe(settings: Settings) -> None:
    issues = collect_production_issues(settings)
    blocking = [issue for issue in issues if issue.severity == "S"]
    if blocking:
        detail = "; ".join(f"{item.code}: {item.message}" for item in blocking)
        raise ProductionGuardError(f"Production guard failed: {detail}")

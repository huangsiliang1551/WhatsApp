"""Admin JWT authentication middleware and FastAPI dependencies."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.settings import Settings, get_settings

WHITELIST_PATHS = {
    "/health",
    "/metrics",
    "/api/admin/auth/login",
    "/api/admin/auth/refresh",
}


def _is_whitelisted(path: str) -> bool:
    if path in WHITELIST_PATHS:
        return True
    if path.startswith("/api/dev/mock/"):
        return True
    if path.startswith("/api/webhooks/"):
        return True
    return False


class AdminUser(BaseModel):
    """Authenticated admin user info extracted from JWT token."""

    user_id: str
    username: str
    role: str = "admin"
    user_type: str = "admin"
    agency_id: str | None = None
    display_name: str | None = None


class AdminAuthDependency:
    """FastAPI dependency for admin JWT authentication.

    Usage:
        @router.get("/api/admin/something")
        async def handler(admin: AdminUser = Depends(get_admin_auth().require_admin)):
            ...
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    def require_admin(self, request: Request) -> AdminUser:
        """Validate JWT token from Authorization header.

        Extracts and validates the Bearer token against the admin_jwt_secret.
        Returns AdminUser on success.

        In test mode, returns a default admin user if no token is provided.
        If a token IS provided in test mode, it is validated normally.
        """
        settings = self._settings or get_settings()

        path = request.url.path
        if _is_whitelisted(path):
            return AdminUser(user_id="system", username="system", role="system")

        auth_header = request.headers.get("Authorization", "")

        # In test mode, allow requests without any Authorization header
        if settings.test_mode and not auth_header:
            return AdminUser(user_id="test-admin", username="test-admin", role="admin")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header.",
            )
        token = auth_header[7:]

        from app.services.admin_auth_service import AdminAuthService

        service = AdminAuthService(
            jwt_secret=settings.admin_jwt_secret,
            access_token_ttl_minutes=settings.admin_access_token_ttl_minutes,
            refresh_token_ttl_days=settings.admin_refresh_token_ttl_days,
            default_username=settings.admin_default_username,
            default_password=settings.admin_default_password,
        )
        admin_user = service.verify_token(token)
        request.state.admin_user = admin_user
        return admin_user


_dependency_instance: AdminAuthDependency | None = None


def get_admin_auth(settings: Settings | None = None) -> AdminAuthDependency:
    global _dependency_instance
    if _dependency_instance is None:
        _dependency_instance = AdminAuthDependency(settings)
    return _dependency_instance


def require_admin(request: Request) -> AdminUser:
    """Convenience dependency for requiring admin auth."""
    return get_admin_auth().require_admin(request)

"""Admin authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.admin_auth import AdminUser, get_admin_auth, require_admin
from app.core.rate_limiter import rate_limit
from app.core.settings import Settings, get_settings
from app.services.admin_auth_service import AdminAuthService

router = APIRouter(prefix="/api/admin/auth", tags=["admin_auth"])


def _get_auth_service(settings: Settings = Depends(get_settings)) -> AdminAuthService:
    return AdminAuthService(
        jwt_secret=settings.admin_jwt_secret,
        access_token_ttl_minutes=settings.admin_access_token_ttl_minutes,
        refresh_token_ttl_days=settings.admin_refresh_token_ttl_days,
        default_username=settings.admin_default_username,
        default_password=settings.admin_default_password,
    )


@router.post("/login", summary="Admin login", description="Authenticate admin user and return JWT token pair.")
async def login(
    request: Request,
    _: None = Depends(rate_limit("auth")),
    settings: Settings = Depends(get_settings),
    auth_service: AdminAuthService = Depends(_get_auth_service),
) -> dict:
    """Login with username and password from request body."""
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    tokens = auth_service.authenticate(username, password)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


@router.post("/refresh", summary="Refresh token", description="Refresh an expired access token using a refresh token.")
async def refresh(
    request: Request,
    _: None = Depends(rate_limit("auth")),
    auth_service: AdminAuthService = Depends(_get_auth_service),
) -> dict:
    """Refresh access token."""
    body = await request.json()
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="refresh_token is required.")
    tokens = auth_service.refresh(refresh_token)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


@router.post("/logout", summary="Admin logout", description="Logout and revoke refresh token.")
async def logout(
    request: Request,
    admin: AdminUser = Depends(require_admin),
    auth_service: AdminAuthService = Depends(_get_auth_service),
) -> dict:
    """Logout and revoke the refresh token."""
    body = await request.json()
    refresh_token = body.get("refresh_token", "")
    if refresh_token:
        auth_service.revoke_refresh_token(refresh_token)
    return {"message": "Logged out successfully."}


@router.get("/me", summary="Current user info", description="Get current authenticated user info.")
async def me(
    admin: AdminUser = Depends(require_admin),
) -> dict:
    """Return current user information."""
    return {
        "user_id": admin.user_id,
        "username": admin.username,
        "role": admin.role,
        "user_type": admin.user_type,
        "agency_id": admin.agency_id,
        "display_name": admin.display_name or admin.username,
    }

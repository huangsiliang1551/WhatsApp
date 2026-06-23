"""Agent authentication API with JWT-based login/me/logout/reset-password."""

import hashlib
import hmac
import json as json_lib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text as sa_text

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings
from app.db.models import Agency
from app.services.agency_service import AgencyService, verify_password

router = APIRouter(prefix="/api/agent-auth", tags=["agent-auth"])

# Unified auth router (prefix = /api/auth)
unified_router = APIRouter(prefix="/api/auth", tags=["auth"])


class AgentLoginRequest(BaseModel):
    username: str
    password: str


class AgentPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# ─── JWT Helpers ────────────────────────────────────────────────────────────


def _base64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    import base64
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _encode_agent_jwt(payload: dict[str, Any], secret: str, expiry_minutes: int) -> str:
    """Encode a JWT token for agent authentication."""
    header = '{"alg":"HS256","typ":"JWT"}'
    header_b64 = _base64url_encode(header.encode("utf-8"))

    now = datetime.now(UTC)
    exp = int((now + timedelta(minutes=expiry_minutes)).timestamp())
    iat = int(now.timestamp())

    payload_with_claims = {**payload, "iat": iat, "exp": exp}
    payload_str = json_lib.dumps(payload_with_claims, separators=(",", ":"))
    payload_b64 = _base64url_encode(payload_str.encode("utf-8"))

    signature_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signature_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _decode_agent_jwt(token: str, secret: str) -> dict[str, Any] | None:
    """Decode and verify an agent JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        signature_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signature_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_signature = _base64url_decode(signature_b64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None

        payload = json_lib.loads(_base64url_decode(payload_b64).decode("utf-8"))

        now_ts = int(datetime.now(UTC).timestamp())
        if payload.get("exp", 0) < now_ts:
            return None

        return payload
    except Exception:
        return None


def _get_agent_from_token(request: Request, settings: Settings) -> Agency:
    """Extract and validate JWT token, return the Agency."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    token = auth_header[7:]
    payload = _decode_agent_jwt(token, settings.admin_jwt_secret)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    from app.db.session import get_sessionmaker

    session = get_sessionmaker()()
    try:
        agency = session.get(Agency, payload.get("agency_id"))
        if agency is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Agency not found.",
            )
        return agency
    finally:
        session.close()


# ─── Routes ─────────────────────────────────────────────────────────────────


@router.post("/login")
async def agent_login(
    data: AgentLoginRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Authenticate an agency by username+password and return JWT token."""
    svc = AgencyService(session)
    agency = svc.get_agency_by_username(data.username)
    if agency is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if agency.password_hash is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if not verify_password(data.password, agency.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if agency.status != "active":
        raise HTTPException(status_code=403, detail="Account has been disabled.")

    access_token = _encode_agent_jwt(
        {
            "sub": agency.id,
            "agency_id": agency.id,
            "username": agency.username or "",
            "user_type": "agent",
            "role": "agent",
        },
        settings.admin_jwt_secret,
        settings.admin_access_token_ttl_minutes,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.admin_access_token_ttl_minutes * 60,
        "agency_id": agency.id,
        "agency_name": agency.name,
        "brand_name": agency.brand_name,
        "username": agency.username,
    }


@router.get("/me")
async def agent_me(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get current agent info from JWT token."""
    agency = _get_agent_from_token(request, settings)

    # Count sites for this agency
    from app.db.models import H5Site
    from sqlalchemy import select, func
    site_count = session.scalar(
        select(func.count()).select_from(select(H5Site).where(H5Site.agency_id == agency.id).subquery())
    ) or 0

    return {
        "id": agency.id,
        "name": agency.name,
        "username": agency.username,
        "brand_name": agency.brand_name,
        "logo_url": agency.logo_url,
        "contact_name": agency.contact_name,
        "contact_phone": agency.contact_phone,
        "contact_email": agency.contact_email,
        "status": agency.status,
        "site_count": site_count,
        "created_at": agency.created_at.isoformat() if agency.created_at else None,
    }


@router.post("/logout")
async def agent_logout(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Logout - client should discard the token."""
    # Token is client-managed; we just acknowledge the logout
    return {"message": "Logged out successfully"}


@router.post("/reset-password")
async def agent_reset_password(
    data: AgentPasswordChangeRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Agent changes own password."""
    agency = _get_agent_from_token(request, settings)

    # Verify current password
    if agency.password_hash is None or not verify_password(data.current_password, agency.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    svc = AgencyService(session)
    svc.reset_password(agency.id, data.new_password)
    return {"message": "Password changed successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
#  Unified Auth Endpoints  (/api/auth)
# ═══════════════════════════════════════════════════════════════════════════════


@unified_router.post("/login")
async def unified_login(
    data: AgentLoginRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Unified login — auto detects super_admin / agent / agent_member.

    Returns a JWT token with user_type, agency_id, role information
    so the frontend can render appropriate menus and permissions.
    """
    username = data.username
    password = data.password

    # 1. Try super_admin
    if username == settings.admin_default_username:
        from app.services.admin_auth_service import AdminAuthService

        auth_service = AdminAuthService(
            jwt_secret=settings.admin_jwt_secret,
            access_token_ttl_minutes=settings.admin_access_token_ttl_minutes,
            refresh_token_ttl_days=settings.admin_refresh_token_ttl_days,
            default_username=settings.admin_default_username,
            default_password=settings.admin_default_password,
        )
        tokens = auth_service.authenticate(username, password)
        return {
            "access_token": tokens.access_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
            "user_type": "super_admin",
            "role": "super_admin",
            "agency_id": None,
            "agency_name": None,
            "account_ids": [],
        }

    # 2. Try agent (Agencies table)
    svc = AgencyService(session)
    agency = svc.get_agency_by_username(username)
    if agency is not None and agency.password_hash is not None:
        if verify_password(password, agency.password_hash):
            access_token = _encode_agent_jwt(
                {
                    "sub": agency.id,
                    "agency_id": agency.id,
                    "username": agency.username or "",
                    "user_type": "agent",
                    "role": "agent",
                },
                settings.admin_jwt_secret,
                settings.admin_access_token_ttl_minutes,
            )
            refresh_token = _encode_agent_jwt(
                {
                    "sub": agency.id,
                    "agency_id": agency.id,
                    "user_type": "agent",
                    "type": "refresh",
                },
                settings.admin_jwt_secret,
                settings.admin_access_token_ttl_minutes * 24 * 7,
            )
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": settings.admin_access_token_ttl_minutes * 60,
                "user_type": "agent",
                "role": "agent",
                "agency_id": agency.id,
                "agency_name": agency.name,
                "brand_name": agency.brand_name,
                "username": agency.username,
                "account_ids": [
                    row[0] for row in session.execute(
                        sa_text("SELECT DISTINCT account_id FROM h5_sites WHERE agency_id = :aid AND account_id IS NOT NULL"),
                        {"aid": agency.id},
                    ).fetchall()
                ],
            }

    # 3. Try agent_member (agents table user_type=agent_member)
    agent_row = session.execute(
        sa_text("""
            SELECT a.id, a.agent_key, a.display_name, a.agency_id, a.is_active,
                   am.role AS member_role
            FROM agents a
            LEFT JOIN agency_members am ON am.user_id = a.id
            WHERE a.agent_key = :username AND a.user_type = 'agent_member'
        """),
        {"username": username},
    ).mappings().first()

    if agent_row is not None and agent_row["is_active"]:
        # Verify password from admin_users
        user_row = session.execute(
            sa_text("""
                SELECT password_hash FROM admin_users
                WHERE username = :username
            """),
            {"username": username},
        ).mappings().first()

        if user_row is not None:
            # Reuse workspace's verify logic
            from app.api.routes.workspace_auth import _verify_password as workspace_verify

            if workspace_verify(password, user_row["password_hash"]):
                agency_row = session.execute(
                    sa_text("SELECT name FROM agencies WHERE id = :aid"),
                    {"aid": agent_row["agency_id"]},
                ).mappings().first()
                agency_name = agency_row["name"] if agency_row else ""

                access_token = _encode_agent_jwt(
                    {
                        "sub": agent_row["id"],
                        "user_type": "agent_member",
                        "agency_id": agent_row["agency_id"],
                        "role": agent_row["member_role"] or "support",
                        "agent_key": agent_row["agent_key"],
                    },
                    settings.admin_jwt_secret,
                    settings.admin_access_token_ttl_minutes,
                )
                refresh_token = _encode_agent_jwt(
                    {
                        "sub": agent_row["id"],
                        "agency_id": agent_row["agency_id"],
                        "user_type": "agent_member",
                        "role": agent_row["member_role"] or "support",
                        "type": "refresh",
                    },
                    settings.admin_jwt_secret,
                    settings.admin_access_token_ttl_minutes * 24 * 7,
                )
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": settings.admin_access_token_ttl_minutes * 60,
                    "user_type": "agent_member",
                    "role": agent_row["member_role"] or "support",
                    "user_id": agent_row["id"],
                    "username": agent_row["agent_key"],
                    "display_name": agent_row["display_name"],
                    "agency_id": agent_row["agency_id"],
                    "agency_name": agency_name,
                    "account_ids": [
                        row[0] for row in session.execute(
                            sa_text("SELECT DISTINCT account_id FROM h5_sites WHERE agency_id = :aid AND account_id IS NOT NULL"),
                            {"aid": agent_row["agency_id"]},
                        ).fetchall()
                    ],
                }

    # 4. Authentication failed
    raise HTTPException(status_code=401, detail="Invalid username or password.")


@unified_router.post("/logout")
async def unified_logout() -> dict:
    """Unified logout — client should discard the token."""
    return {"message": "Logged out successfully"}


@unified_router.post("/refresh")
async def unified_refresh(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Refresh access token for agent/agent_member users."""
    body = await request.json()
    refresh_token = body.get("refresh_token", "")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="refresh_token is required.")

    payload = _decode_agent_jwt(refresh_token, settings.admin_jwt_secret)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token.")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_type = payload.get("user_type", "agent")
    agency_id = payload.get("agency_id")
    sub = payload.get("sub", "")

    # Generate new access token
    new_payload = {
        "sub": sub,
        "agency_id": agency_id,
        "user_type": user_type,
        "role": payload.get("role", user_type if user_type in ("agent", "agent_member") else "agent"),
    }
    if user_type == "agent_member":
        new_payload["agent_key"] = payload.get("agent_key", "")

    new_access_token = _encode_agent_jwt(
        new_payload,
        settings.admin_jwt_secret,
        settings.admin_access_token_ttl_minutes,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.admin_access_token_ttl_minutes * 60,
        "user_type": user_type,
    }


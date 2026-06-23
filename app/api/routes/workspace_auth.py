"""Workspace authentication API for agent_member (subordinate) users.

Provides login/me/logout/reset-password endpoints for
客服 (support), 财务 (finance), 经理 (manager) roles.
"""

import hashlib
import hmac
import json as json_lib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings

router = APIRouter(prefix="/api/workspace-auth", tags=["workspace-auth"])


class WorkspaceLoginRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
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


def _encode_workspace_jwt(payload: dict[str, Any], secret: str, expiry_minutes: int) -> str:
    """Encode a JWT token for workspace (agent_member) authentication."""
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


def _decode_workspace_jwt(token: str, secret: str) -> dict[str, Any] | None:
    """Decode and verify a workspace JWT token."""
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


# ─── Auth dependency ─────────────────────────────────────────────────────────


def _get_workspace_member_from_token(
    request: Request,
    settings: Settings,
    session: Session,
) -> dict[str, Any]:
    """Extract and validate JWT token, return agent_member info dict."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
        )
    token = auth_header[7:]
    payload = _decode_workspace_jwt(token, settings.admin_jwt_secret)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    # Verify the agent_member still exists and is active
    agent_id = payload.get("sub", "")
    row = session.execute(
        text("""
            SELECT a.id, a.agent_key, a.display_name, a.agency_id, a.is_active,
                   am.role AS member_role
            FROM agents a
            LEFT JOIN agency_members am ON am.user_id = a.id
            WHERE a.id = :agent_id AND a.user_type = 'agent_member'
        """),
        {"agent_id": agent_id},
    ).mappings().first()

    if row is None or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return {
        "id": row["id"],
        "agent_key": row["agent_key"],
        "display_name": row["display_name"],
        "agency_id": row["agency_id"],
        "role": row["member_role"],
        "user_type": "agent_member",
    }


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ─── Routes ─────────────────────────────────────────────────────────────────


@router.post("/login")
async def workspace_login(
    data: WorkspaceLoginRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Authenticate an agent_member by username+password and return JWT token."""

    # 1. Query the agents table for user_type='agent_member'
    agent_row = session.execute(
        text("""
            SELECT a.id, a.agent_key, a.display_name, a.agency_id, a.is_active,
                   am.role AS member_role
            FROM agents a
            LEFT JOIN agency_members am ON am.user_id = a.id
            WHERE a.agent_key = :username AND a.user_type = 'agent_member'
        """),
        {"username": data.username},
    ).mappings().first()

    if agent_row is None or not agent_row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # 2. Verify password from admin_users table
    user_row = session.execute(
        text("""
            SELECT password_hash FROM admin_users
            WHERE username = :username
        """),
        {"username": data.username},
    ).mappings().first()

    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not _verify_password(data.password, user_row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    # 3. Get agency name and status
    agency_row = session.execute(
        text("SELECT name, status FROM agencies WHERE id = :aid"),
        {"aid": agent_row["agency_id"]},
    ).mappings().first()
    agency_name = agency_row["name"] if agency_row else ""

    if agency_row and agency_row["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled.",
        )
    # 4. Issue JWT
    access_token = _encode_workspace_jwt(
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

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.admin_access_token_ttl_minutes * 60,
        "user_id": agent_row["id"],
        "username": agent_row["agent_key"],
        "display_name": agent_row["display_name"],
        "role": agent_row["member_role"] or "support",
        "agency_id": agent_row["agency_id"],
        "agency_name": agency_name,
    }


@router.get("/me")
async def workspace_me(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get current agent_member info from JWT token."""
    member = _get_workspace_member_from_token(request, settings, session)

    # Get agency name
    agency_row = session.execute(
        text("SELECT name, brand_name FROM agencies WHERE id = :aid"),
        {"aid": member["agency_id"]},
    ).mappings().first()

    return {
        "id": member["id"],
        "username": member["agent_key"],
        "display_name": member["display_name"],
        "role": member["role"],
        "agency_id": member["agency_id"],
        "agency_name": agency_row["name"] if agency_row else "",
        "brand_name": agency_row["brand_name"] if agency_row else "",
        "user_type": "agent_member",
    }


@router.post("/logout")
async def workspace_logout() -> dict:
    """Logout - client should discard the token."""
    return {"message": "Logged out successfully"}


@router.post("/reset-password")
async def workspace_reset_password(
    data: ResetPasswordRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Agent_member changes own password."""
    member = _get_workspace_member_from_token(request, settings, session)

    # Verify current password from admin_users
    user_row = session.execute(
        text("""
            SELECT password_hash FROM admin_users
            WHERE username = :username
        """),
        {"username": member["agent_key"]},
    ).mappings().first()

    if user_row is None or not _verify_password(data.current_password, user_row["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    # Update password in admin_users
    new_hash = _hash_password(data.new_password)
    session.execute(
        text("""
            UPDATE admin_users SET password_hash = :pw, updated_at = NOW()
            WHERE username = :username
        """),
        {"pw": new_hash, "username": member["agent_key"]},
    )

    return {"message": "Password changed successfully"}

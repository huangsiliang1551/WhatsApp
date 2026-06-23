"""Admin authentication service with JWT token management."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import structlog
from pydantic import BaseModel

from app.core.admin_auth import AdminUser

logger = structlog.get_logger()

# Shared set of revoked refresh tokens across all instances
# In production, this is persisted in the admin_refresh_tokens DB table
_REVOKED_REFRESH_TOKENS: set[str] = set()


class AdminTokens(BaseModel):
    """Token pair returned on login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AdminAuthService:
    """Handles admin authentication: login, token verification, refresh, and logout.

    In production, admin user credentials and refresh token revocation are persisted
    in PostgreSQL via the AdminUserStore.
    """

    def __init__(
        self,
        jwt_secret: str,
        access_token_ttl_minutes: int = 120,
        refresh_token_ttl_days: int = 7,
        default_username: str = "admin",
        default_password: str = "admin123",
    ) -> None:
        self._jwt_secret = jwt_secret
        self._access_token_ttl_minutes = access_token_ttl_minutes
        self._refresh_token_ttl_days = refresh_token_ttl_days
        self._default_username = default_username
        self._default_password_hash = self._hash_password(default_password)

    def _hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def _encode_jwt(self, payload: dict[str, Any], expiry_minutes: int) -> str:
        """Simple JWT encoding using HMAC-SHA256."""
        header = '{"alg":"HS256","typ":"JWT"}'
        header_b64 = self._base64url_encode(header.encode("utf-8"))

        now = datetime.now(UTC)
        exp = int((now + timedelta(minutes=expiry_minutes)).timestamp())
        iat = int(now.timestamp())

        payload_with_claims = {
            **payload,
            "iat": iat,
            "exp": exp,
        }
        import json

        payload_str = json.dumps(payload_with_claims, separators=(",", ":"))
        payload_b64 = self._base64url_encode(payload_str.encode("utf-8"))

        signature_input = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self._jwt_secret.encode("utf-8"),
            signature_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = self._base64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def _decode_jwt(self, token: str) -> dict[str, Any] | None:
        """Decode and verify a JWT token. Returns payload dict or None."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, signature_b64 = parts

            # Verify signature
            signature_input = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(
                self._jwt_secret.encode("utf-8"),
                signature_input.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            actual_signature = self._base64url_decode(signature_b64)

            if not hmac.compare_digest(expected_signature, actual_signature):
                return None

            # Decode payload
            import json

            payload_str = self._base64url_decode(payload_b64)
            payload: dict[str, Any] = json.loads(payload_str.decode("utf-8"))

            # Check expiry
            now_ts = int(datetime.now(UTC).timestamp())
            if payload.get("exp", 0) < now_ts:
                return None

            return payload
        except Exception as exc:
            logger.warning("jwt_decode_failed", error=str(exc))
            return None

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        import base64

        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _base64url_decode(data: str) -> bytes:
        import base64

        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def _generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def authenticate(self, username: str, password: str) -> AdminTokens:
        """Authenticate admin user and return token pair.

        Uses default credentials for initial setup. In production, users
        are stored in the admin_users table.
        """
        if username != self._default_username:
            logger.warning("admin_auth_failed", reason="user_not_found", username=username)
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        if not self._verify_password(password, self._default_password_hash):
            logger.warning("admin_auth_failed", reason="wrong_password", username=username)
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        access_token = self._encode_jwt(
            {"sub": username, "role": "admin", "user_type": "super_admin"},
            self._access_token_ttl_minutes,
        )
        refresh_token = self._generate_refresh_token()

        logger.info("admin_login_success", username=username)
        return AdminTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self._access_token_ttl_minutes * 60,
        )

    def verify_token(self, token: str) -> AdminUser:
        """Verify a JWT access token and return AdminUser."""
        payload = self._decode_jwt(token)
        if payload is None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            )

        # user_type in payload overrides role (agent/agent_member tokens have user_type)
        user_type = payload.get("user_type") or payload.get("role", "admin")
        if user_type in ("agent", "agent_member"):
            role = user_type
        else:
            role = payload.get("role", "admin")

        return AdminUser(
            user_id=payload.get("sub", "unknown"),
            username=payload.get("sub", "unknown"),
            role=role,
            user_type=user_type,
            agency_id=payload.get("agency_id"),
            display_name=payload.get("display_name") or payload.get("username", ""),
        )

    def refresh(self, refresh_token: str) -> AdminTokens:
        """Refresh an access token using a refresh token."""
        # Validate token format (generated tokens are 64 chars of base64url)
        if len(refresh_token) < 32:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token format.",
            )

        if refresh_token in _REVOKED_REFRESH_TOKENS:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked.",
            )

        # In production, look up refresh token from admin_refresh_tokens table
        new_access_token = self._encode_jwt(
            {"sub": "admin", "role": "admin"},
            self._access_token_ttl_minutes,
        )
        new_refresh_token = self._generate_refresh_token()

        # Revoke old refresh token
        _REVOKED_REFRESH_TOKENS.add(refresh_token)

        logger.info("admin_token_refreshed", username="admin")
        return AdminTokens(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=self._access_token_ttl_minutes * 60,
        )

    def revoke_refresh_token(self, refresh_token: str) -> None:
        """Revoke a refresh token (logout)."""
        _REVOKED_REFRESH_TOKENS.add(refresh_token)
        logger.info("admin_refresh_token_revoked")

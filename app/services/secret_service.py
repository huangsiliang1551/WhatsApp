from __future__ import annotations

from uuid import uuid4

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Secret
from app.core.settings import get_settings


class SecretService:
    """Manage Fernet-encrypted secrets in the database."""

    def __init__(self, session: Session) -> None:
        self._session = session
        # Derive Fernet key from settings secret key (must be 32 bytes, base64-encoded)
        settings = get_settings()
        raw = settings.admin_jwt_secret.encode("utf-8")
        # Pad/truncate to 32 bytes for Fernet
        key_bytes = raw.ljust(32, b"\0")[:32]
        import base64
        self._fernet = Fernet(base64.urlsafe_b64encode(key_bytes))

    def list_secrets(self) -> list[Secret]:
        return list(self._session.scalars(
            select(Secret).order_by(Secret.name)
        ).all())

    def get_secret(self, secret_id: str) -> Secret:
        secret = self._session.get(Secret, secret_id)
        if not secret:
            raise LookupError(f"Secret '{secret_id}' not found.")
        return secret

    def get_decrypted_value(self, secret_id: str) -> str:
        secret = self.get_secret(secret_id)
        return self._fernet.decrypt(secret.encrypted_value.encode("utf-8")).decode("utf-8")

    def get_decrypted_by_name(self, name: str) -> str | None:
        secret = self._session.scalar(
            select(Secret).where(Secret.name == name)
        )
        if not secret:
            return None
        return self._fernet.decrypt(secret.encrypted_value.encode("utf-8")).decode("utf-8")

    def create_secret(
        self,
        name: str,
        plain_value: str,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Secret:
        encrypted = self._fernet.encrypt(plain_value.encode("utf-8")).decode("utf-8")
        secret = Secret(
            id=str(uuid4()),
            name=name,
            encrypted_value=encrypted,
            description=description,
            created_by=created_by,
        )
        self._session.add(secret)
        self._session.commit()
        return secret

    def update_secret(self, secret_id: str, plain_value: str | None = None, description: str | None = None) -> Secret:
        secret = self.get_secret(secret_id)
        if plain_value is not None:
            secret.encrypted_value = self._fernet.encrypt(plain_value.encode("utf-8")).decode("utf-8")
        if description is not None:
            secret.description = description
        self._session.commit()
        return secret

    def delete_secret(self, secret_id: str) -> None:
        secret = self.get_secret(secret_id)
        self._session.delete(secret)
        self._session.commit()

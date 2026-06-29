from __future__ import annotations

from app.core.encryption import decrypt_key, encrypt_key
from app.db.models import H5GatewayCredential
from sqlalchemy.orm import Session


class H5GatewayCredentialService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_credential(
        self,
        *,
        name: str,
        credential_type: str,
        secret: str,
        created_by: str,
        metadata_json: dict[str, object] | None = None,
    ) -> H5GatewayCredential:
        masked_tail = self._derive_secret_last4(secret)
        credential = H5GatewayCredential(
            name=name,
            credential_type=credential_type,
            encrypted_secret=encrypt_key(secret),
            secret_last4=masked_tail,
            created_by=created_by,
            metadata_json=metadata_json or {},
        )
        self.session.add(credential)
        self.session.commit()
        self.session.refresh(credential)
        return credential

    def get_secret(self, credential_id: str) -> str:
        credential = self.session.get(H5GatewayCredential, credential_id)
        if credential is None:
            raise ValueError(f"H5 gateway credential '{credential_id}' not found.")
        return decrypt_key(credential.encrypted_secret)

    def serialize_credential(self, credential: H5GatewayCredential) -> dict[str, object]:
        return {
            "id": credential.id,
            "name": credential.name,
            "credential_type": credential.credential_type,
            "secret_last4": credential.secret_last4,
            "status": credential.status,
            "created_by": credential.created_by,
            "has_secret": bool(credential.encrypted_secret),
            "rotated_at": credential.rotated_at.isoformat() if credential.rotated_at else None,
            "metadata_json": credential.metadata_json or {},
        }

    @staticmethod
    def _derive_secret_last4(secret: str) -> str | None:
        normalized = secret.rstrip()
        if not normalized:
            return None
        if normalized.endswith("-----") and len(normalized) >= 8:
            return normalized[-8:-4]
        return normalized[-4:]

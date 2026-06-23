"""Service layer for Translation Provider Configuration CRUD.

SecretId/SecretKey are encrypted via Fernet at rest.
API responses expose has_secret only.
"""

import uuid
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_key, decrypt_key
from app.db.models import TranslationProviderConfig
from app.schemas.translation_providers import (
    CreateTranslationProviderConfigRequest,
    UpdateTranslationProviderConfigRequest,
)

logger = logging.getLogger(__name__)


class TranslationProviderConfigService:
    """Service for managing translation provider configurations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── CRUD ──

    def list_configs(self, include_disabled: bool = False) -> list[TranslationProviderConfig]:
        stmt = select(TranslationProviderConfig).order_by(TranslationProviderConfig.priority.asc())
        if not include_disabled:
            stmt = stmt.where(TranslationProviderConfig.is_enabled.is_(True))
        return list(self._session.scalars(stmt).all())

    def get_config(self, config_id: str) -> TranslationProviderConfig:
        config = self._session.get(TranslationProviderConfig, config_id)
        if not config:
            raise ValueError(f"Translation provider config '{config_id}' not found.")
        return config

    def create_config(self, data: CreateTranslationProviderConfigRequest) -> TranslationProviderConfig:
        config = TranslationProviderConfig(
            id=str(uuid.uuid4()),
            name=data.name,
            provider_type=data.provider_type,
            secret_id_encrypted=encrypt_key(data.secret_id) if data.secret_id else None,
            secret_key_encrypted=encrypt_key(data.secret_key) if data.secret_key else None,
            region=data.region,
            priority=data.priority,
            is_enabled=data.is_enabled,
            timeout_seconds=data.timeout_seconds,
            metadata_json=data.metadata_json,
        )
        self._session.add(config)
        self._session.commit()
        return config

    def update_config(self, config_id: str, data: UpdateTranslationProviderConfigRequest) -> TranslationProviderConfig:
        config = self.get_config(config_id)

        updates: dict = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.provider_type is not None:
            updates["provider_type"] = data.provider_type
        if data.secret_id is not None:
            if data.secret_id.strip():
                updates["secret_id_encrypted"] = encrypt_key(data.secret_id)
        if data.secret_key is not None:
            if data.secret_key.strip():
                updates["secret_key_encrypted"] = encrypt_key(data.secret_key)
        if data.region is not None:
            updates["region"] = data.region
        if data.priority is not None:
            updates["priority"] = data.priority
        if data.is_enabled is not None:
            updates["is_enabled"] = data.is_enabled
        if data.timeout_seconds is not None:
            updates["timeout_seconds"] = data.timeout_seconds
        if data.metadata_json is not None:
            updates["metadata_json"] = data.metadata_json

        if updates:
            stmt = (
                update(TranslationProviderConfig)
                .where(TranslationProviderConfig.id == config_id)
                .values(**updates)
            )
            self._session.execute(stmt)
            self._session.commit()

        return self.get_config(config_id)

    def delete_config(self, config_id: str) -> None:
        config = self.get_config(config_id)
        self._session.delete(config)
        self._session.commit()

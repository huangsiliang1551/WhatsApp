"""
AIP-002: Service layer for AI Provider Configuration CRUD, account overrides, test connection, and seeding.

API Key is encrypted via Fernet at rest. API responses expose has_api_key only.
"""

import time
import uuid
import logging

from openai import AsyncOpenAI, APITimeoutError, APIError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_key, decrypt_key
from app.core.settings import Settings
from app.db.models import AIProviderConfig, AccountAIProviderOverride
from app.schemas.ai_providers import (
    CreateAIProviderConfigRequest,
    UpdateAIProviderConfigRequest,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.services.ai_provider_cache import get_provider_cache, invalidate_provider_cache

logger = logging.getLogger(__name__)


class AIProviderConfigService:
    """Service for managing AI provider configurations and account-level overrides."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── CRUD ────────────────────────────────────────────────────────────

    def list_configs(self, include_disabled: bool = False) -> list[AIProviderConfig]:
        stmt = select(AIProviderConfig).order_by(AIProviderConfig.priority.asc())
        if not include_disabled:
            stmt = stmt.where(AIProviderConfig.is_enabled.is_(True))
        return list(self._session.scalars(stmt).all())

    def get_config(self, config_id: str) -> AIProviderConfig:
        config = self._session.get(AIProviderConfig, config_id)
        if not config:
            raise ValueError(f"AI provider config '{config_id}' not found.")
        return config

    def create_config(self, data: CreateAIProviderConfigRequest) -> AIProviderConfig:
        config = AIProviderConfig(
            id=str(uuid.uuid4()),
            name=data.name,
            provider_type=data.provider_type,
            api_base_url=data.api_base_url,
            api_key_encrypted=encrypt_key(data.api_key) if data.api_key else None,
            model=data.model,
            priority=data.priority,
            is_enabled=data.is_enabled,
            timeout_seconds=data.timeout_seconds,
            use_responses_api=data.use_responses_api,
            metadata_json=data.metadata_json,
        )
        self._session.add(config)
        self._session.commit()
        invalidate_provider_cache()
        return config

    def update_config(self, config_id: str, data: UpdateAIProviderConfigRequest) -> AIProviderConfig:
        config = self.get_config(config_id)

        updates: dict = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.provider_type is not None:
            updates["provider_type"] = data.provider_type
        if data.api_base_url is not None:
            updates["api_base_url"] = data.api_base_url
        if data.api_key is not None:
            if data.api_key.strip():
                updates["api_key_encrypted"] = encrypt_key(data.api_key)
            # If api_key is empty string, preserve existing key (no change)
        if data.model is not None:
            updates["model"] = data.model
        if data.priority is not None:
            updates["priority"] = data.priority
        if data.is_enabled is not None:
            updates["is_enabled"] = data.is_enabled
        if data.timeout_seconds is not None:
            updates["timeout_seconds"] = data.timeout_seconds
        if data.use_responses_api is not None:
            updates["use_responses_api"] = data.use_responses_api
        if data.metadata_json is not None:
            updates["metadata_json"] = data.metadata_json

        if updates:
            stmt = (
                update(AIProviderConfig)
                .where(AIProviderConfig.id == config_id)
                .values(**updates)
            )
            self._session.execute(stmt)
            self._session.commit()
            invalidate_provider_cache()

        return self.get_config(config_id)

    def delete_config(self, config_id: str) -> None:
        config = self.get_config(config_id)
        # Cascade delete account overrides
        del_stmt = select(AccountAIProviderOverride).where(
            AccountAIProviderOverride.provider_config_id == config_id
        )
        for override in self._session.scalars(del_stmt).all():
            self._session.delete(override)
        self._session.delete(config)
        self._session.commit()
        invalidate_provider_cache()

    def reorder_configs(self, ordered_ids: list[str]) -> None:
        """Set priority based on position in ordered_ids list (0 = highest)."""
        for index, config_id in enumerate(ordered_ids):
            config = self._session.get(AIProviderConfig, config_id)
            if not config:
                raise ValueError(f"AI provider config '{config_id}' not found during reorder.")
            config.priority = index
        self._session.commit()
        invalidate_provider_cache()

    # ── Account Overrides ───────────────────────────────────────────────

    def get_account_override(self, account_id: str) -> AccountAIProviderOverride | None:
        stmt = select(AccountAIProviderOverride).where(
            AccountAIProviderOverride.account_id == account_id,
            AccountAIProviderOverride.is_active.is_(True),
        )
        return self._session.scalars(stmt).first()

    def set_account_override(self, account_id: str, provider_config_id: str) -> AccountAIProviderOverride:
        # Verify config exists
        self.get_config(provider_config_id)

        existing = self._session.scalars(
            select(AccountAIProviderOverride).where(
                AccountAIProviderOverride.account_id == account_id
            )
        ).first()

        if existing:
            existing.provider_config_id = provider_config_id
            existing.is_active = True
        else:
            existing = AccountAIProviderOverride(
                id=str(uuid.uuid4()),
                account_id=account_id,
                provider_config_id=provider_config_id,
                is_active=True,
            )
            self._session.add(existing)

        self._session.commit()
        invalidate_provider_cache()
        return existing

    def clear_account_override(self, account_id: str) -> None:
        existing = self._session.scalars(
            select(AccountAIProviderOverride).where(
                AccountAIProviderOverride.account_id == account_id
            )
        ).first()
        if existing:
            self._session.delete(existing)
            self._session.commit()
            invalidate_provider_cache()

    # ── Test Connection ─────────────────────────────────────────────────

    async def test_connection(self, request: TestConnectionRequest) -> TestConnectionResponse:
        """Test connectivity to an AI provider by sending a minimal chat completion request."""

        # Resolve config
        api_key: str | None = None
        base_url: str | None = None
        model: str | None = None
        timeout: int = request.timeout_seconds

        if request.config_id:
            config = self.get_config(request.config_id)
            api_key = decrypt_key(config.api_key_encrypted) if config.api_key_encrypted else None
            base_url = config.api_base_url
            model = config.model
            timeout = config.timeout_seconds
        else:
            api_key = request.api_key
            base_url = request.api_base_url
            model = request.model

        if not api_key:
            return TestConnectionResponse(
                status="error",
                error_type="auth_failed",
                message="No API key provided.",
            )
        if not model:
            return TestConnectionResponse(
                status="error",
                error_type="model_not_found",
                message="No model specified.",
            )

        client_kwargs: dict = {"api_key": api_key, "timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = AsyncOpenAI(**client_kwargs)
        start = time.monotonic()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            echoed = response.choices[0].message.content if response.choices else None
            await client.close()
            return TestConnectionResponse(
                status="ok",
                latency_ms=elapsed,
                model_echoed=model,
            )
        except APITimeoutError:
            await client.close()
            return TestConnectionResponse(
                status="error",
                error_type="timeout",
                message=f"Request timed out after {timeout}s.",
            )
        except APIError as exc:
            await client.close()
            error_type = "unknown"
            status_code = getattr(exc, "status_code", 0)
            if status_code == 401:
                error_type = "auth_failed"
            elif status_code == 404:
                error_type = "model_not_found"
            return TestConnectionResponse(
                status="error",
                error_type=error_type,  # type: ignore[assignment]
                message=str(exc),
            )
        except Exception as exc:
            await client.close()
            return TestConnectionResponse(
                status="error",
                error_type="unknown",
                message=str(exc),
            )

    # ── Seed from .env ──────────────────────────────────────────────────

    def seed_from_env(self, settings: Settings) -> int:
        """Seed AI provider configs from .env if the table is empty.

        Returns the number of newly created configs.
        """
        existing_count = self._session.scalar(select(AIProviderConfig).limit(1))
        if existing_count is not None:
            return 0  # Already populated

        count = 0
        openai_key = settings.openai_api_key.strip() if settings.openai_api_key else ""
        deepseek_key = settings.deepseek_api_key.strip() if settings.deepseek_api_key else ""

        if openai_key:
            self._session.add(
                AIProviderConfig(
                    id=str(uuid.uuid4()),
                    name="OpenAI (from .env)",
                    provider_type="openai",
                    api_base_url=None,
                    api_key_encrypted=encrypt_key(openai_key),
                    model=settings.openai_model,
                    priority=0,
                    is_enabled=True,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                    use_responses_api=True,
                )
            )
            count += 1

        if deepseek_key:
            self._session.add(
                AIProviderConfig(
                    id=str(uuid.uuid4()),
                    name="DeepSeek (from .env)",
                    provider_type="deepseek",
                    api_base_url=settings.deepseek_api_base,
                    api_key_encrypted=encrypt_key(deepseek_key),
                    model=settings.deepseek_model,
                    priority=10,
                    is_enabled=True,
                    timeout_seconds=settings.llm_request_timeout_seconds,
                    use_responses_api=False,
                )
            )
            count += 1

        if count > 0:
            self._session.commit()
            invalidate_provider_cache()

        return count

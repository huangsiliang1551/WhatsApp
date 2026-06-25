from collections.abc import Callable, Generator

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db_session, get_db_session_factory, get_meta_management_service
from app.core.rate_limiter import reset_rate_limiter
from app.core.settings import get_settings
from app.db.base import Base
from app.main import app
from app.providers.meta_management.base import (
    MetaEmbeddedSignupCompletionCommand,
    MetaEmbeddedSignupCompletionResult,
    MetaManagementProvider,
    MetaPhoneNumberRecord,
    MetaPhoneNumberSyncCommand,
    MetaPhoneNumberSyncResult,
    MetaWebhookSubscriptionCommand,
    MetaWebhookSubscriptionResult,
)
from app.services.queue_service import QueueService
from tests.fake_redis import FakeRedis


@pytest.fixture
def db_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    yield factory

    engine.dispose()


@pytest.fixture
def client(db_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()

    original_env = {
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
    }
    os.environ["LIVE_TRANSLATION_ENABLED"] = "true"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"
    os.environ["TEST_MODE"] = "true"
    QueueService(get_settings()).reset()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_db_session_factory] = lambda: db_session_factory
    # 默认安装 mock Meta 管理 Provider，避免 helper（subscribe_meta_webhook / manual 注册）
    # 在没显式 override 的测试中真实去调 Meta API。
    app.dependency_overrides[get_meta_management_service] = lambda: StubMetaManagementProvider()

    reset_rate_limiter()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    QueueService(get_settings()).reset()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


class StubMetaManagementProvider(MetaManagementProvider):
    provider_name = "whatsapp"

    def __init__(
        self,
        *,
        subscription_status: str = "remote_subscribed",
        subscription_remote_confirmed: bool = True,
        sync_phone_numbers: list[MetaPhoneNumberRecord] | None = None,
        sync_status: str = "success",
        sync_mode: str = "remote_fetch",
        completion_status: str = "remote_confirmed",
        completion_remote_confirmed: bool = True,
        completion_phone_number_ids: list[str] | None = None,
        completion_resolved_waba_id: str | None = None,
        completion_resolved_portfolio_id: str | None = None,
    ) -> None:
        self._subscription_status = subscription_status
        self._subscription_remote_confirmed = subscription_remote_confirmed
        self._sync_phone_numbers = list(sync_phone_numbers or [])
        self._sync_status = sync_status
        self._sync_mode = sync_mode
        self._completion_status = completion_status
        self._completion_remote_confirmed = completion_remote_confirmed
        self._completion_phone_number_ids = completion_phone_number_ids
        self._completion_resolved_waba_id = completion_resolved_waba_id
        self._completion_resolved_portfolio_id = completion_resolved_portfolio_id

    async def subscribe_webhook(
        self,
        payload: MetaWebhookSubscriptionCommand,
    ) -> MetaWebhookSubscriptionResult:
        return MetaWebhookSubscriptionResult(
            provider_name=self.provider_name,
            subscription_status=self._subscription_status,
            remote_confirmed=self._subscription_remote_confirmed,
            raw_response={
                "callback_url": payload.callback_url,
                "waba_id": payload.waba_id,
            },
            message="Stub remote webhook subscription completed.",
        )

    async def sync_phone_numbers(
        self,
        payload: MetaPhoneNumberSyncCommand,
    ) -> MetaPhoneNumberSyncResult:
        phone_numbers = (
            list(self._sync_phone_numbers)
            if self._sync_phone_numbers
            else list(payload.existing_phone_numbers)
        )
        return MetaPhoneNumberSyncResult(
            provider_name=self.provider_name,
            sync_mode=self._sync_mode,
            status=self._sync_status,
            phone_numbers=phone_numbers,
            raw_response={"count": len(phone_numbers), "waba_id": payload.waba_id},
            message="Stub remote phone-number sync completed.",
        )

    async def complete_embedded_signup_session(
        self,
        payload: MetaEmbeddedSignupCompletionCommand,
    ) -> MetaEmbeddedSignupCompletionResult:
        resolved_phone_number_ids = (
            list(self._completion_phone_number_ids)
            if self._completion_phone_number_ids is not None
            else list(payload.phone_number_ids)
        )
        return MetaEmbeddedSignupCompletionResult(
            provider_name=self.provider_name,
            completion_status=self._completion_status,
            remote_confirmed=self._completion_remote_confirmed,
            resolved_waba_id=self._completion_resolved_waba_id or payload.requested_waba_id,
            resolved_portfolio_id=(
                self._completion_resolved_portfolio_id or payload.meta_business_portfolio_id
            ),
            phone_number_ids=resolved_phone_number_ids,
            raw_response={"session_id": payload.session_id},
            message="Stub embedded-signup confirmation completed.",
        )

    async def health_check(
        self,
        waba_id: str,
        access_token: str,
    ) -> dict[str, object]:
        return {"status": "healthy", "waba_id": waba_id}

    async def send_test_message(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
        to: str,
        text: str,
    ) -> dict[str, object]:
        return {"status": "sent", "phone_id": phone_id, "to": to}

    async def query_phone_detail(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        return {"waba_id": waba_id, "phone_id": phone_id}

    async def query_business_profile(
        self,
        waba_id: str,
        access_token: str,
        phone_id: str,
    ) -> dict[str, object]:
        return {"waba_id": waba_id, "phone_id": phone_id}


@pytest.fixture
def override_meta_management_provider() -> Generator[
    Callable[[TestClient, MetaManagementProvider], None],
    None,
    None,
]:
    def _override(client: TestClient, provider: MetaManagementProvider) -> None:
        client.app.dependency_overrides[get_meta_management_service] = lambda: provider

    yield _override

    app.dependency_overrides.pop(get_meta_management_service, None)

"""Test auto-generated account_id and global webhook config"""
import os, sys, tempfile, shutil, asyncio
os.environ["TEST_MODE"] = "true"
os.environ["AUTH_REQUIRED"] = "false"
os.environ["META_GLOBAL_WEBHOOK_VERIFY_TOKEN"] = "global_verify_123"
os.environ["META_GLOBAL_WEBHOOK_APP_SECRET"] = "global_secret_abc"

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings
from app.db.base import Base
from app.db import models  # noqa
from app.services.meta_account_registry import MetaAccountRegistry
from app.services.runtime_state import RuntimeStateStore
from app.schemas.meta_accounts import ManualMetaAccountRequest, MetaPhoneNumber
from app.providers.meta_management.mock_provider import MockMetaManagementProvider


async def main():
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    get_settings.cache_clear()

    with SessionLocal() as session:
        runtime = RuntimeStateStore(session=session)
        provider = MockMetaManagementProvider()
        registry = MetaAccountRegistry(
            settings=get_settings(),
            meta_management_provider=provider,
            runtime_state=runtime,
            session=session,
        )

        # Test 1: Auto-generate account_id
        print("=== Test 1: Auto-generate account_id ===")
        payload = ManualMetaAccountRequest(
            display_name="Auto Account",
            meta_business_portfolio_id="pf-001",
            waba_id="waba-001",
            access_token="tok-001",
            phone_numbers=[MetaPhoneNumber(phone_number_id="pn-001", display_phone_number="+86138001")],
        )
        result = await registry.create_manual_account(payload)
        assert result.account_id.startswith("acc-"), f"Expected acc- prefix, got: {result.account_id}"
        assert result.has_verify_token is True, "Expected verify_token from global config"
        assert result.has_app_secret is True, "Expected app_secret from global config"
        print(f"  PASS: account_id={result.account_id}, verify_token={result.has_verify_token}, app_secret={result.has_app_secret}")

        # Test 2: Explicit account_id
        print("=== Test 2: Explicit account_id ===")
        payload2 = ManualMetaAccountRequest(
            account_id="custom-123",
            display_name="Custom",
            meta_business_portfolio_id="pf-002",
            waba_id="waba-002",
            access_token="tok-002",
            phone_numbers=[],
        )
        result2 = await registry.create_manual_account(payload2)
        assert result2.account_id == "custom-123"
        print(f"  PASS: account_id={result2.account_id}")

        session.commit()
        print("=== ALL TESTS PASSED ===")

    shutil.rmtree(tmpdir, ignore_errors=True)


asyncio.run(main())

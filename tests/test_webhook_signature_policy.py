"""P1-04 regression tests: webhook signature enforcement policy.

``WEBHOOK_SIGNATURE_ENABLED`` previously existed as a setting but did not
actually control signature verification. Now:

* Production always enforces verification, even when the flag is ``false``.
* Development/test may disable verification for local integration work.
"""

import os
from collections.abc import Generator

import pytest

from app.api.routes.webhooks import _should_verify_webhook_signature
from app.core.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_sig_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("WEBHOOK_SIGNATURE_ENABLED", raising=False)
    yield


def test_webhook_signature_forced_in_production() -> None:
    os.environ["APP_ENV"] = "production"
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is True


def test_webhook_signature_forced_in_production_when_enabled() -> None:
    os.environ["APP_ENV"] = "production"
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "true"

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is True


def test_webhook_signature_can_be_disabled_in_development() -> None:
    os.environ["APP_ENV"] = "development"
    os.environ["WEBHOOK_SIGNATURE_ENABLED"] = "false"

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is False


def test_webhook_signature_enabled_in_development_by_default() -> None:
    os.environ["APP_ENV"] = "development"

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is True

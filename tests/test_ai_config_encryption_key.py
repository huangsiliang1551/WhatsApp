"""P1-03 regression tests: AI config encryption key env name.

The setting was previously aliased only to the typo ``AI_CONFIG_ENCRY_KEY``,
so the correctly-spelled ``AI_CONFIG_ENCRYPTION_KEY`` was silently ignored.
Now both are accepted, with the correctly-spelled variant preferred.
"""

import os
from collections.abc import Generator

import pytest

from app.core.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_encryption_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # Ensure no stale env leaks between tests.
    monkeypatch.delenv("AI_CONFIG_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("AI_CONFIG_ENCRY_KEY", raising=False)
    yield


def test_ai_config_encryption_key_prefers_correct_env_name() -> None:
    os.environ["AI_CONFIG_ENCRYPTION_KEY"] = "new-key"

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "new-key"


def test_ai_config_encryption_key_supports_legacy_typo() -> None:
    os.environ["AI_CONFIG_ENCRY_KEY"] = "legacy-key"

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "legacy-key"


def test_ai_config_encryption_key_prefers_new_over_legacy() -> None:
    os.environ["AI_CONFIG_ENCRYPTION_KEY"] = "new-key"
    os.environ["AI_CONFIG_ENCRY_KEY"] = "legacy-key"

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "new-key"


def test_template_static_root_is_configurable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # P2-03 sanity check: static roots come from settings, not hard-coded.
    monkeypatch.setenv("TEMPLATE_STATIC_ROOT", str(tmp_path / "static"))
    monkeypatch.setenv("TEMPLATE_UPLOAD_ROOT", str(tmp_path / "uploads"))

    settings = Settings(_env_file=None)

    assert settings.template_static_root == str(tmp_path / "static")
    assert settings.template_upload_root == str(tmp_path / "uploads")

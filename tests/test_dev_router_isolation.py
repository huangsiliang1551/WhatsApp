"""P2-01 regression tests: dev/mock routes must not be registered in production.

The dev router is now only included when ``APP_ENV != production`` (or when
``TEST_MODE=true``). In a production deployment the mock inbound endpoint
must return 404, not be reachable.
"""

import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dev_router_available_in_development(client: TestClient) -> None:
    """In the default (development) test app, the dev route is registered."""
    # An empty body yields a 422 validation error, proving the route exists
    # (a missing route would be 404).
    response = client.post("/dev/mock/inbound-message", json={})
    assert response.status_code != 404, response.text


def test_dev_router_not_registered_in_production(tmp_path: Path) -> None:
    """A fresh app built under APP_ENV=production excludes the dev router."""
    snippet = (
        "import os, json\n"
        f"os.environ['TEMPLATE_STATIC_ROOT'] = {str(tmp_path / 'static')!r}\n"
        f"os.environ['TEMPLATE_UPLOAD_ROOT'] = {str(tmp_path / 'uploads')!r}\n"
        "os.environ['APP_ENV'] = 'production'\n"
        "os.environ['TEST_MODE'] = 'false'\n"
        "os.environ['LIVE_TRANSLATION_ENABLED'] = 'false'\n"
        "os.environ['TRANSLATION_PROVIDER'] = 'fallback'\n"
        "from app.main import app\n"
        "paths = [getattr(r, 'path', '') for r in app.routes]\n"
        "print(json.dumps('/dev/mock/inbound-message' in paths))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "false", result.stdout + result.stderr


def test_dev_router_still_registered_when_test_mode_overrides_production(
    tmp_path: Path,
) -> None:
    """TEST_MODE=true keeps the dev router even under APP_ENV=production."""
    snippet = (
        "import os, json\n"
        f"os.environ['TEMPLATE_STATIC_ROOT'] = {str(tmp_path / 'static')!r}\n"
        f"os.environ['TEMPLATE_UPLOAD_ROOT'] = {str(tmp_path / 'uploads')!r}\n"
        "os.environ['APP_ENV'] = 'production'\n"
        "os.environ['TEST_MODE'] = 'true'\n"
        "os.environ['LIVE_TRANSLATION_ENABLED'] = 'false'\n"
        "os.environ['TRANSLATION_PROVIDER'] = 'fallback'\n"
        "from app.main import app\n"
        "paths = [getattr(r, 'path', '') for r in app.routes]\n"
        "print(json.dumps('/dev/mock/inbound-message' in paths))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "true", result.stdout + result.stderr

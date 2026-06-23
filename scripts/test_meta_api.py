"""Manual Meta API smoke-check script.

This script is intentionally executable as a standalone tool and should not run
as part of pytest collection.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

__test__ = False

BASE = "http://localhost:8000/api/meta/accounts"
LOGIN_URL = "http://localhost:8000/api/admin/auth/login"


class MetaApiSmokeTest:
    def __init__(self) -> None:
        self.token: str | None = None
        self.passed = 0
        self.failed = 0
        self.fail_details: list[str] = []

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        url = f"{BASE}{path}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode()
                return resp.status, json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            content = exc.read().decode()
            return exc.code, {"error": content}
        except Exception as exc:  # pragma: no cover - manual smoke helper
            return 0, {"error": str(exc)}

    def run_step(
        self,
        step: int,
        method: str,
        path: str,
        body: dict | None,
        description: str,
    ) -> dict:
        status, result = self.request(method, path, body)
        if 200 <= status < 400:
            print(f"  [PASS] {description} (HTTP {status})")
            self.passed += 1
        else:
            print(f"  [FAIL] {description} (HTTP {status}) -> {json.dumps(result, ensure_ascii=False)[:200]}")
            self.failed += 1
            self.fail_details.append(f"Step {step}: {description} => HTTP {status}: {result}")
        return result

    def login(self) -> bool:
        print("\n=== Step 1: Login as Admin ===")
        login_body = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(
            LOGIN_URL,
            data=login_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            print(f"  [FAIL] Login HTTP {exc.code}: {exc.read().decode()}")
            return False

        self.token = data.get("access_token", "")
        if self.token:
            print(f"  [PASS] Login OK (token len={len(self.token)})")
            return True

        print(f"  [FAIL] No token in response: {data}")
        return False

    def print_summary(self) -> int:
        total = self.passed + self.failed
        print("\n" + "=" * 50)
        print("  Meta API smoke test summary")
        print("=" * 50)
        print(f"  Total: {total}")
        print(f"  Passed: {self.passed}")
        print(f"  Failed: {self.failed}")
        if self.fail_details:
            print("\n  Failure details:")
            for detail in self.fail_details:
                print(f"    - {detail}")
        print("=" * 50)
        return 0 if self.failed == 0 else 1


def main() -> int:
    runner = MetaApiSmokeTest()
    if not runner.login():
        return 1

    steps: list[tuple[int, str, str, dict | None, str]] = [
        (2, "GET", "", None, "GET / (list accounts)"),
        (
            3,
            "POST",
            "/manual",
            {
                "account_id": "test-acc-metatest",
                "display_name": "Test Account MetaTest",
                "meta_business_portfolio_id": "pf-test-metatest-001",
                "waba_id": "waba-test-metatest-001",
                "access_token": "EAATestTokenDummy123",
                "verify_token": "verify_dummy_123",
                "app_secret": "app_secret_dummy",
                "token_source": "system_user",
                "phone_numbers": [
                    {
                        "phone_number_id": "pn-test-metatest-001",
                        "display_phone_number": "+8613800138001",
                        "verified_name": "Test Phone 1",
                        "quality_rating": "GREEN",
                        "is_registered": True,
                        "is_active": True,
                    },
                    {
                        "phone_number_id": "pn-test-metatest-002",
                        "display_phone_number": "+8613800138002",
                        "verified_name": "Test Phone 2",
                        "quality_rating": "UNKNOWN",
                        "is_registered": False,
                        "is_active": True,
                    },
                ],
            },
            "POST /manual (create account)",
        ),
        (4, "GET", "", None, "GET / (list after create)"),
        (5, "GET", "/phone-numbers", None, "GET /phone-numbers"),
        (6, "GET", "/test-acc-metatest/phone-numbers", None, "GET /{account_id}/phone-numbers"),
        (
            7,
            "GET",
            "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers",
            None,
            "GET /{account_id}/wabas/{waba_id}/phone-numbers",
        ),
        (8, "PATCH", "/test-acc-metatest/status", {"is_active": False}, "PATCH /{account_id}/status (disable)"),
        (9, "PATCH", "/test-acc-metatest/status", {"is_active": True}, "PATCH /{account_id}/status (enable)"),
        (
            10,
            "PATCH",
            "/test-acc-metatest/wabas/waba-test-metatest-001/status",
            {"is_active": False},
            "PATCH /{account_id}/wabas/{waba_id}/status (disable)",
        ),
        (
            11,
            "PATCH",
            "/test-acc-metatest/wabas/waba-test-metatest-001/status",
            {"is_active": True},
            "PATCH /{account_id}/wabas/{waba_id}/status (enable)",
        ),
        (
            12,
            "PATCH",
            "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/pn-test-metatest-001/status",
            {"is_active": False},
            "PATCH phone status (disable)",
        ),
        (
            13,
            "PATCH",
            "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/pn-test-metatest-001/status",
            {"is_active": True},
            "PATCH phone status (enable)",
        ),
        (14, "POST", "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/sync", None, "POST sync phone numbers"),
        (
            15,
            "POST",
            "/test-acc-metatest/wabas/waba-test-metatest-001/webhook-subscription",
            {"callback_url": "https://example.com/webhook", "verify_token": "test_verify_123"},
            "POST webhook-subscription",
        ),
        (16, "GET", "/webhook-subscriptions", None, "GET /webhook-subscriptions"),
        (17, "POST", "/test-acc-metatest/wabas/waba-test-metatest-001/health-check", None, "POST health-check"),
        (18, "GET", "/global-webhook-config", None, "GET /global-webhook-config"),
        (
            19,
            "PUT",
            "/global-webhook-config",
            {"callback_url": "https://my-server.com/webhooks/whatsapp", "verify_token": "new_verify_token"},
            "PUT /global-webhook-config",
        ),
        (20, "GET", "/global-webhook-config", None, "GET /global-webhook-config (verify)"),
        (21, "GET", "/embedded-signup/sessions", None, "GET /embedded-signup/sessions"),
        (
            22,
            "POST",
            "/embedded-signup/session",
            {"account_id": "test-acc-metatest", "redirect_uri": "https://example.com/callback"},
            "POST /embedded-signup/session",
        ),
        (
            23,
            "DELETE",
            "/test-acc-metatest/wabas/waba-test-metatest-001",
            None,
            "DELETE /{account_id}/wabas/{waba_id}",
        ),
        (24, "GET", "", None, "GET / (verify empty)"),
    ]

    print("\n=== Running Meta API smoke steps ===")
    verify_config: dict | None = None
    for step, method, path, body, description in steps:
        result = runner.run_step(step, method, path, body, description)
        if step == 20:
            verify_config = result

    if isinstance(verify_config, dict) and verify_config.get("callback_url") == "https://my-server.com/webhooks/whatsapp":
        print("    -> callback_url updated correctly")
    elif verify_config is not None:
        print(f"    -> [WARN] callback_url mismatch: {verify_config}")

    return runner.print_summary()


if __name__ == "__main__":
    raise SystemExit(main())

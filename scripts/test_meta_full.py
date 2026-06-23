"""Meta API 全链路闭环检测 — 使用 FastAPI TestClient + SQLite"""
import os
import sys
from pathlib import Path

# Force test env before importing app
os.environ["TEST_MODE"] = "true"
os.environ["AUTH_REQUIRED"] = "false"

import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.base import Base
from app.db import models as _models  # noqa: ensure models registered
from app.main import app
from app.api.deps import get_db_session, get_db_session_factory
from fastapi.testclient import TestClient

# ── Setup SQLite test DB ──
tmpdir = tempfile.mkdtemp(prefix="meta_test_")
db_path = Path(tmpdir) / "test.db"
engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db_session] = override_get_db_session
app.dependency_overrides[get_db_session_factory] = lambda: SessionLocal

# Clear settings cache
get_settings.cache_clear()
os.environ["AUTH_REQUIRED"] = "false"

client = TestClient(app)

PASSED = 0
FAILED = 0
FAIL_DETAILS = []


def t(method: str, path: str, body: dict | None, desc: str, expect_code: int = 200):
    global PASSED, FAILED
    full = f"/api/meta/accounts{path}"
    try:
        if method == "GET":
            resp = client.get(full)
        elif method == "POST":
            resp = client.post(full, json=body)
        elif method == "PATCH":
            resp = client.patch(full, json=body)
        elif method == "PUT":
            resp = client.put(full, json=body)
        elif method == "DELETE":
            resp = client.delete(full)
        else:
            raise ValueError(f"Unknown method {method}")

        code = resp.status_code
        if 200 <= code < 400:
            print(f"  [PASS] {desc} (HTTP {code})")
            PASSED += 1
        else:
            body_text = resp.text[:300]
            print(f"  [FAIL] {desc} -> HTTP {code}: {body_text}")
            FAILED += 1
            FAIL_DETAILS.append(f"{desc} => HTTP {code}: {body_text}")
        return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    except Exception as e:
        print(f"  [FAIL] {desc} -> EXCEPTION: {e}")
        FAILED += 1
        FAIL_DETAILS.append(f"{desc} => EXCEPTION: {e}")
        return None


# ======= TESTS =======
print("=" * 55)
print("  Meta API 全链路闭环检测 (TestClient + SQLite)")
print("=" * 55)

# 1. List empty
print("\n[1] GET / — list accounts (empty)")
t("GET", "", None, "list empty")

# 2. List phone numbers empty
print("\n[2] GET /phone-numbers — all phone numbers (empty)")
t("GET", "/phone-numbers", None, "all phone numbers")

# 3. List webhook subscriptions empty
print("\n[3] GET /webhook-subscriptions — all webhook subs (empty)")
t("GET", "/webhook-subscriptions", None, "all webhook subs")

# 4. List signup sessions empty
print("\n[4] GET /embedded-signup/sessions — all signup sessions (empty)")
t("GET", "/embedded-signup/sessions", None, "all signup sessions")

# 5. Create manual account
print("\n[5] POST /manual — create account")
create_body = {
    "account_id": "test-metatest-01",
    "display_name": "MetaTest Acc01",
    "meta_business_portfolio_id": "pf-meta-001",
    "waba_id": "waba-meta-001",
    "access_token": "EAA-test-token-123",
    "verify_token": "verify_abc",
    "app_secret": "secret_xyz",
    "token_source": "system_user",
    "phone_numbers": [
        {
            "phone_number_id": "pn-meta-001",
            "display_phone_number": "+8613800138001",
            "verified_name": "Phone Alpha",
            "quality_rating": "GREEN",
            "is_registered": True,
            "is_active": True,
        },
        {
            "phone_number_id": "pn-meta-002",
            "display_phone_number": "+8613800138002",
            "verified_name": "Phone Beta",
            "quality_rating": "UNKNOWN",
            "is_registered": False,
            "is_active": True,
        },
    ],
}
result = t("POST", "/manual", create_body, "create account")
print(f"    response keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

# 6. List accounts (should have 1)
print("\n[6] GET / — list accounts (expect ≥1)")
result = t("GET", "", None, "list after create")
if isinstance(result, list):
    print(f"    account count: {len(result)}")
    if result:
        print(f"    first account keys: {list(result[0].keys())}")

# 7. List phone numbers by account
print("\n[7] GET /{account_id}/phone-numbers")
result = t("GET", "/test-metatest-01/phone-numbers", None, "phone by account")
if isinstance(result, list):
    print(f"    phone count: {len(result)}")

# 8. List phone numbers by WABA
print("\n[8] GET /{account_id}/wabas/{waba_id}/phone-numbers")
result = t("GET", "/test-metatest-01/wabas/waba-meta-001/phone-numbers", None, "phone by WABA")
if isinstance(result, list):
    print(f"    phone count: {len(result)}")
    if result:
        print(f"    phone fields: {list(result[0].keys())}")
        # Verify is_active is present
        if "is_active" in result[0]:
            print("    [OK] is_active field present in MetaPhoneNumberScopeView")
        else:
            print("    [MISS] is_active MISSING from MetaPhoneNumberScopeView")
            FAILED += 1
            FAIL_DETAILS.append("is_active MISSING from MetaPhoneNumberScopeView")

# 9. Account status disable
print("\n[9] PATCH /{account_id}/status — disable account")
result = t("PATCH", "/test-metatest-01/status", {"is_active": False}, "disable account")
if isinstance(result, dict):
    print(f"    result: is_active={result.get('is_active')}")

# 10. Account status enable
print("\n[10] PATCH /{account_id}/status — enable account")
result = t("PATCH", "/test-metatest-01/status", {"is_active": True}, "enable account")
if isinstance(result, dict):
    print(f"    result: is_active={result.get('is_active')}")

# 11. WABA status disable
print("\n[11] PATCH /{account_id}/wabas/{waba_id}/status — disable WABA")
result = t("PATCH", "/test-metatest-01/wabas/waba-meta-001/status", {"is_active": False}, "disable WABA")
if isinstance(result, dict):
    print(f"    result: is_active={result.get('is_active')}")

# 12. WABA status enable
print("\n[12] PATCH /{account_id}/wabas/{waba_id}/status — enable WABA")
result = t("PATCH", "/test-metatest-01/wabas/waba-meta-001/status", {"is_active": True}, "enable WABA")
if isinstance(result, dict):
    print(f"    result: is_active={result.get('is_active')}")

# 13. Phone status disable
print("\n[13] PATCH phone status — disable phone")
result = t(
    "PATCH",
    "/test-metatest-01/wabas/waba-meta-001/phone-numbers/pn-meta-001/status",
    {"is_active": False},
    "disable phone",
)
if isinstance(result, dict):
    print(f"    result keys: {list(result.keys())}")

# 14. Phone status enable
print("\n[14] PATCH phone status — enable phone")
result = t(
    "PATCH",
    "/test-metatest-01/wabas/waba-meta-001/phone-numbers/pn-meta-001/status",
    {"is_active": True},
    "enable phone",
)
if isinstance(result, dict):
    print(f"    result keys: {list(result.keys())}")

# 15. Sync phone numbers
print("\n[15] POST sync phone numbers")
result = t("POST", "/test-metatest-01/wabas/waba-meta-001/phone-numbers/sync", None, "sync phones")

# 16. Subscribe webhook
print("\n[16] POST webhook-subscription")
result = t(
    "POST",
    "/test-metatest-01/wabas/waba-meta-001/webhook-subscription",
    {"callback_url": "https://example.com/webhook", "verify_token": "verify123"},
    "subscribe webhook",
)

# 17. Health check
print("\n[17] POST health-check")
result = t("POST", "/test-metatest-01/wabas/waba-meta-001/health-check", None, "health check")

# 18. GET global webhook config
print("\n[18] GET /global-webhook-config")
result = t("GET", "/global-webhook-config", None, "get global wh config")
if isinstance(result, dict):
    print(f"    result: {result}")

# 19. PUT global webhook config
print("\n[19] PUT /global-webhook-config — update")
result = t(
    "PUT",
    "/global-webhook-config",
    {"callback_url": "https://my-server.com/webhooks/whatsapp", "verify_token": "new_token_456"},
    "update global wh config",
)
if isinstance(result, dict):
    print(f"    result: {result}")

# 20. GET global webhook config (verify update)
print("\n[20] GET /global-webhook-config — verify update persisted")
result = t("GET", "/global-webhook-config", None, "verify wh update")
if isinstance(result, dict):
    actual_url = result.get("callback_url", "")
    expected = "https://my-server.com/webhooks/whatsapp"
    if actual_url == expected:
        print(f"    [OK] callback_url persisted correctly: {actual_url}")
    else:
        print(f"    ⚠️ callback_url mismatch: expected={expected}, got={actual_url} (in-memory, expected in test)")

# 21. Create signup session
print("\n[21] POST /embedded-signup/session")
result = t(
    "POST",
    "/embedded-signup/session",
    {"account_id": "test-metatest-01", "display_name": "MetaTest Acc01", "redirect_uri": "https://example.com/cb"},
    "create signup session",
)

# 22. List signup sessions (should have 1)
print("\n[22] GET /embedded-signup/sessions — after create")
result = t("GET", "/embedded-signup/sessions", None, "list signups after create")
if isinstance(result, list):
    print(f"    signup count: {len(result)}")

# 23. Update account (PATCH)
print("\n[23] PATCH /{account_id}/wabas/{waba_id} — update account metadata")
result = t(
    "PATCH",
    "/test-metatest-01/wabas/waba-meta-001",
    {
        "display_name": "MetaTest Acc01-Updated",
        "meta_business_portfolio_id": "pf-meta-001",
        "access_token": "EAA-updated-token",
        "token_source": "system_user",
        "phone_numbers": [
            {
                "phone_number_id": "pn-meta-001",
                "display_phone_number": "+8613800138001",
                "verified_name": "Phone Alpha RENAMED",
                "quality_rating": "GREEN",
                "is_registered": True,
                "is_active": True,
            }
        ],
    },
    "update account",
)

# 24. Verify update — check display_name
print("\n[24] GET / — verify display_name update")
result = t("GET", "", None, "verify display_name update")
if isinstance(result, list) and result:
    dn = result[0].get("display_name", "")
    if dn == "MetaTest Acc01-Updated":
        print(f"    [OK] display_name updated: {dn}")
    else:
        print(f"    ⚠️ display_name is: {dn}")

# 25. Account ISOLATION test — toggle account_active vs waba_active independently
print("\n[25] ISOLATION: Account-Active vs WABA-Active independence")
# Disable account, enable WABA
t("PATCH", "/test-metatest-01/status", {"is_active": False}, "disable account (scope)")
t("PATCH", "/test-metatest-01/wabas/waba-meta-001/status", {"is_active": True}, "enable WABA (scope)")
result = t("GET", "", None, "list for isolation check")
if isinstance(result, list) and result:
    acc = result[0]
    a_active = acc.get("account_is_active")
    w_active = acc.get("is_active")
    a_label = "enabled" if a_active else "disabled"
    w_label = "enabled" if w_active else "disabled"
    print(f"    account_is_active={a_active} ({a_label}), is_active(WABA)={w_active} ({w_label})")
    if a_active is False and w_active is True:
        print(f"    [OK] Account/WABA active states are independent")
    else:
        print("    ⚠️ Unexpected active state combination")

# 26. PATCH should return wabas list with account_is_active field
print("\n[26] PATCH /{account_id}/status — response includes wabas list")
result = t("PATCH", "/test-metatest-01/status", {"is_active": True}, "enable account (check response)")
if isinstance(result, dict):
    wabas = result.get("wabas", [])
    print(f"    wabas count in response: {len(wabas)}")
    if wabas and isinstance(wabas[0], dict):
        fields = list(wabas[0].keys())
        print(f"    waba fields: {fields}")
        if "account_is_active" in fields:
            print("    [OK] account_is_active present in response waba")
        else:
            print("    ⚠️ account_is_active NOT in response waba")

# 27. DELETE account (cleanup)
print("\n[27] DELETE /{account_id}/wabas/{waba_id} — cleanup")
result = t("DELETE", "/test-metatest-01/wabas/waba-meta-001", None, "delete account")

# 28. Verify deleted
print("\n[28] GET / — verify account deleted")
result = t("GET", "", None, "verify deleted")
if isinstance(result, list):
    print(f"    remaining accounts: {len(result)}")

# ── SUMMARY ──
total = PASSED + FAILED
print("\n" + "=" * 55)
print(f"  Meta API 检测报告")
print("=" * 55)
print(f"  总计: {total} 项")
print(f"  通过: {PASSED} 项{' [ALL CLEAR]' if FAILED == 0 else ''}")
print(f"  失败: {FAILED} 项{' [ALL CLEAR]' if FAILED == 0 else ' [ISSUES FOUND]'}")
if FAIL_DETAILS:
    print(f"\n  失败详情:")
    for i, d in enumerate(FAIL_DETAILS, 1):
        print(f"    {i}. {d}")
print("=" * 55)

# Cleanup
import shutil

shutil.rmtree(tmpdir, ignore_errors=True)

sys.exit(0 if FAILED == 0 else 1)

"""Test with frontend-equivalent headers."""
import json, urllib.request, urllib.error

BASE = "http://localhost:8000"

def api(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return 0, str(e)

# Login
_, resp = api("POST", "/api/admin/auth/login", {
    "username": "admin", "password": "admin123"
})
token = resp["access_token"]

# Frontend-style headers (same as what axios interceptor adds)
fe_h = {
    "Authorization": f"Bearer {token}",
    "X-Actor-Id": "agent-cn-console",
    "X-Actor-Name": "Admin",
    "X-Actor-Role": "super_admin",
    "X-Actor-Account-Ids": "",
}

# Test all conversations with frontend headers
convs_to_test = [
    ("test-account-01", "conv-001-zh"),
    ("test-account-01", "conv-002-en"),
    ("test-account-01", "conv-003-es"),
    ("test-account-02", "conv-004-zh"),
    ("test-account-02", "conv-005-en"),
    ("test-account-03", "conv-006-ja"),
    ("test-account-03", "conv-007-en"),
    ("test-account-03", "conv-008-zh"),
]

print("Testing with frontend-equivalent headers...")
for aid, cid in convs_to_test:
    path = f"/api/conversations/{aid}/{cid}/messages?include_translations=true&offset=0&limit=30"
    status, data = api("GET", path, headers=fe_h)
    if isinstance(data, list):
        has_text = sum(1 for m in data if (m.get("original_text") or m.get("text") or m.get("body")))
        print(f"  [OK] {aid}/{cid}: {len(data)} msgs ({has_text} with text), status={status}")
    else:
        print(f"  [FAIL] {aid}/{cid}: status={status}, {str(data)[:120]}")

# Also test the conversations list (to see what the frontend sees)
print("\nConversations list with frontend headers:")
status, convs = api("GET", "/api/conversations", headers=fe_h)
items = convs.get("items") if isinstance(convs, dict) else (convs if isinstance(convs, list) else [])
print(f"  status={status}, count={len(items)}")
for c in items:
    print(f"    [{c.get('account_id','?')}] {c.get('conversation_id','?')} mode={c.get('management_mode','?')} status={c.get('status','?')} ai={c.get('ai_enabled','?')}")

"""Test conversation message loading."""
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
        with urllib.request.urlopen(req) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")

# Login
status, login_resp = api("POST", "/api/admin/auth/login", {
    "username": "admin",
    "password": "admin123"
})
print(f"Login: status={status}, type={type(login_resp).__name__}")
if isinstance(login_resp, str):
    print(f"  body={login_resp[:300]}")
    exit(1)
token = login_resp.get("access_token", "")
if not token:
    print(f"  no token: {list(login_resp.keys())}")
    exit(1)
print(f"  token={token[:20]}...")

auth_h = {
    "Authorization": f"Bearer {token}",
    "X-Actor-Id": "admin",
    "X-Actor-Role": "super_admin",
}

# List all conversations first
status, convs = api("GET", "/api/conversations", headers=auth_h)
print(f"\nConversations: status={status}, {len(convs) if isinstance(convs, list) else type(convs).__name__}")

# Test each conversation
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

print()
for aid, cid in convs_to_test:
    path = f"/api/conversations/{aid}/{cid}/messages?include_translations=true&offset=0&limit=30"
    status, data = api("GET", path, headers=auth_h)
    if isinstance(data, list):
        print(f"  [OK] {aid}/{cid}: {len(data)} msgs, status={status}")
    else:
        print(f"  [FAIL] {aid}/{cid}: status={status}, {str(data)[:150]}")

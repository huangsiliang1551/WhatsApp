"""Check conversation data structure from REST API."""
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
_, resp = api("POST", "/api/admin/auth/login", {
    "username": "admin",
    "password": "admin123"
})
token = resp["access_token"]
auth_h = {
    "Authorization": f"Bearer {token}",
    "X-Actor-Id": "admin",
    "X-Actor-Role": "super_admin",
}

# Get conversations
status, convs = api("GET", "/api/conversations", headers=auth_h)
print(f"Type: {type(convs).__name__}")
if isinstance(convs, dict):
    convs = convs.get("items", [])
print(f"Count: {len(convs)}")

# Print key fields for each
for c in convs:
    aid = c.get("account_id", "?")
    cid = c.get("conversation_id", "?")
    status_val = c.get("status", "?")
    mode = c.get("management_mode", "?")
    customer = c.get("customer_id", "?")
    last_msg_at = c.get("last_message_at", "?")
    last_preview = (c.get("last_message_preview") or "")[:40]
    ai_enabled = c.get("ai_enabled")
    assigned = c.get("assigned_agent_name", "?")
    waba = c.get("waba_id", "?")
    phone = c.get("phone_number_id", "?")
    print(f"\n[{aid}] {cid}")
    print(f"  customer={customer}, status={status_val}, mode={mode}")
    print(f"  last_at={last_msg_at}, preview={last_preview}")
    print(f"  ai_enabled={ai_enabled}, assigned={assigned}")
    print(f"  waba={waba}, phone={phone}")

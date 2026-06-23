"""Debug script to test APIs"""
import json
import urllib.request

BASE = "http://localhost:8000"
ACTOR_HEADERS = {
    "X-Actor-Id": "agent-cn-console",
    "X-Actor-Name": "CNConsole",
    "X-Actor-Role": "super_admin",
    "X-Actor-Account-Ids": "",
}

def api(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in ACTOR_HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return {"error": e.code, "detail": body_text}

# Test #5: Block customer-en-03
print("=== #5 Test Block ===")
r = api("PATCH", "/api/customers/customer-en-03/lifecycle-status?account_id=test-account-03", {"lifecycle_status": "blacklisted"})
print(json.dumps(r, indent=2, ensure_ascii=False))

# Test #6: Close then reopen conv-007-en
print("\n=== #6 Test Close ===")
r = api("POST", "/api/conversations/test-account-03/conv-007-en/close", {"agent_id": "agent-cn-console", "reason": "testing"})
print(json.dumps(r, indent=2, ensure_ascii=False))

print("\n=== #6 Test Reopen ===")
r = api("POST", "/api/conversations/test-account-03/conv-007-en/reopen", {"agent_id": "agent-cn-console", "reason": "testing"})
print(json.dumps(r, indent=2, ensure_ascii=False))

# Test messages for different conversations
print("\n=== Messages for conv-001-zh ===")
r = api("GET", "/api/conversations/test-account-01/conv-001-zh/messages?paginated=true&offset=0&limit=5")
msgs = r.get("items", r) if isinstance(r, dict) else r
print(f"Count: {len(msgs)}")

print("\n=== Messages for conv-007-en ===")
r = api("GET", "/api/conversations/test-account-03/conv-007-en/messages?paginated=true&offset=0&limit=5")
msgs = r.get("items", r) if isinstance(r, dict) else r
print(f"Count: {len(msgs)}")

# Check AppUser for customer-en-03
print("\n=== Check customer-en-03 in DB (via summary) ===")
r = api("GET", "/api/customers/customer-en-03/summary?account_id=test-account-03")
print(json.dumps(r, indent=2, ensure_ascii=False)[:500])

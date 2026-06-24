"""SSE endpoint test via HTTP."""
import urllib.request, ssl, json, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Login
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/admin/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
)
r = urllib.request.urlopen(req, context=ctx)
token = json.loads(r.read())["access_token"]
print("TOKEN OK:", token[:20] + "...")

# Test SSE via HTTP
try:
    r2 = urllib.request.urlopen(
        f"http://localhost:8000/api/conversations/stream?token={token}",
        context=ctx,
    )
    print(f"STATUS: {r2.status}")
    print(f"Content-Type: {r2.headers.get('Content-Type', 'N/A')}")
    print(f"Cache-Control: {r2.headers.get('Cache-Control', 'N/A')}")
    print()

    # Read first few SSE lines
    start = time.time()
    lines = []
    while time.time() - start < 5:
        line = r2.readline().decode(errors="ignore")
        if not line:
            break
        lines.append(line.rstrip())
        if len(lines) >= 20:
            break

    for line in lines:
        if line.strip():
            print(line)
    print(f"\nTOTAL LINES: {len(lines)}")
except urllib.error.HTTPError as e:
    print(f"HTTP ERROR: {e.code} - {e.read().decode()[:300]}")

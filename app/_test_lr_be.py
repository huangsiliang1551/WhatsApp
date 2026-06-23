"""Verify LR-BE API endpoints."""
import requests

BASE = "http://localhost:8000"

def test_all():
    # Test 1: Health
    r = requests.get(f"{BASE}/health")
    print(f"[1] Health: {r.status_code}")
    assert r.status_code == 200

    # Test 2: Create agency with username+password
    agency_data = {
        "name": "Test Agency",
        "username": "testagent",
        "password": "password123",
        "brand_name": "Test Brand",
        "contact_name": "John",
        "contact_email": "john@test.com",
    }
    r = requests.post(
        f"{BASE}/api/agents",
        json=agency_data,
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[2] Create agency: {r.status_code}")
    resp = r.json()
    print(f"    Response: id={resp.get('id')}, username={resp.get('username')}")
    assert r.status_code == 200
    assert resp.get("username") == "testagent"
    agency_id = resp["id"]

    # Test 3: Agent login with correct credentials
    r = requests.post(
        f"{BASE}/api/agent-auth/login",
        json={"username": "testagent", "password": "password123"},
    )
    print(f"[3] Login: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert "access_token" in resp
    token = resp["access_token"]

    # Test 4: Agent me (JWT)
    r = requests.get(
        f"{BASE}/api/agent-auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"[4] Me: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert resp.get("username") == "testagent"
    assert resp.get("site_count") is not None

    # Test 5: Login with wrong password
    r = requests.post(
        f"{BASE}/api/agent-auth/login",
        json={"username": "testagent", "password": "wrongpassword"},
    )
    print(f"[5] Login (wrong pwd): {r.status_code}")
    assert r.status_code == 401

    # Test 6: PATCH /api/agents/me (self update)
    r = requests.patch(
        f"{BASE}/api/agents/me",
        json={"brand_name": "Updated Brand", "contact_name": "John Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"[6] Self update: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert resp.get("brand_name") == "Updated Brand"

    # Test 7: Reset password (super admin)
    r = requests.post(
        f"{BASE}/api/agents/{agency_id}/reset-password",
        json={"new_password": "newpassword123"},
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[7] Reset password: {r.status_code}")
    assert r.status_code == 200

    # Test 8: Login with new password
    r = requests.post(
        f"{BASE}/api/agent-auth/login",
        json={"username": "testagent", "password": "newpassword123"},
    )
    print(f"[8] Login (new pwd): {r.status_code}")
    assert r.status_code == 200
    new_token = r.json()["access_token"]

    # Test 9: Agent logout
    r = requests.post(
        f"{BASE}/api/agent-auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"[9] Logout: {r.status_code}")
    assert r.status_code == 200

    # Test 10: Agent change own password
    r = requests.post(
        f"{BASE}/api/agent-auth/reset-password",
        json={"current_password": "newpassword123", "new_password": "changedpwd123"},
        headers={"Authorization": f"Bearer {new_token}"},
    )
    print(f"[10] Change own pwd: {r.status_code}")
    assert r.status_code == 200

    # Test 11: List agencies (should show username)
    r = requests.get(
        f"{BASE}/api/agents",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[11] List agencies: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert len(resp) > 0
    print(f"     First agency username: {resp[0].get('username')}")

    # Test 12: Create scoped billing with line_items
    r = requests.post(
        f"{BASE}/api/agents/{agency_id}/billing",
        json={
            "billing_type": "monthly",
            "amount": 5999.00,
            "billing_period_start": "2026-06-01",
            "billing_period_end": "2026-06-30",
            "line_items": [
                {"description": "月费", "quantity": 1, "unit_price": 2999.00},
                {"description": "站点费用 (3个站点)", "quantity": 3, "unit_price": 1000.00},
            ],
        },
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[12] Create billing: {r.status_code}")
    resp = r.json()
    assert r.status_code == 201
    assert len(resp["line_items"]) == 2
    billing_id = resp["id"]
    print(f"     Line items: {resp['line_items']}")

    # Test 13: Get billing with line_items
    r = requests.get(
        f"{BASE}/api/agents/{agency_id}/billing/{billing_id}",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[13] Get billing: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert resp.get("line_items") is not None
    print(f"     Line items: {resp['line_items']}")

    # Test 14: List billing (should show line_items)
    r = requests.get(
        f"{BASE}/api/agents/{agency_id}/billing",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[14] List billing: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    assert len(resp) > 0
    assert resp[0].get("line_items") is not None

    # Test 15: WABA revoke endpoint (if WABA exists)
    # Create a test WABA first
    from app.db.session import get_sessionmaker
    from app.db.models import WhatsAppBusinessAccount, H5Site

    session = get_sessionmaker()()
    try:
        # Create a test site
        site = H5Site(
            id=__import__("uuid").uuid4().hex[:36],
            site_key="test-site",
            domain="test.example.com",
            name="Test Site",
            status="active",
            agency_id=agency_id,
        )
        session.add(site)
        session.flush()
        site_id = site.id

        # Assign WABA to site
        waba = WhatsAppBusinessAccount(
            id=__import__("uuid").uuid4().hex[:36],
            waba_id="test-waba-123",
            account_id="test-account",
            is_active=True,
        )
        session.add(waba)
        session.commit()
        waba_id = waba.id

        # Test assign WABA
        r = requests.post(
            f"{BASE}/api/waba/{waba_id}/assign",
            json={"site_id": site_id},
            headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
        )
        print(f"[15] Assign WABA: {r.status_code}")
        assert r.status_code == 200

        # Test revoke WABA
        r = requests.post(
            f"{BASE}/api/waba/{waba_id}/revoke",
            headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
        )
        print(f"[16] Revoke WABA: {r.status_code}")
        resp = r.json()
        assert r.status_code == 200
        assert len(resp["revoked_sites"]) > 0
        print(f"     Revoked sites: {resp['revoked_sites']}")

        # Test WABA assignment status
        r = requests.get(
            f"{BASE}/api/waba/{waba_id}/assignment",
            headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
        )
        print(f"[17] WABA assignment: {r.status_code}")
        resp = r.json()
        assert r.status_code == 200
        assert resp.get("is_assigned") == False
        print(f"     Is assigned: {resp['is_assigned']}")

        # Test no-duplicate: assign to site, then try assign to different site
        r = requests.post(
            f"{BASE}/api/waba/{waba_id}/assign",
            json={"site_id": site_id},
            headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
        )
        print(f"[18] Assign again: {r.status_code}")
        assert r.status_code == 200

        # Create another site and try to assign the same WABA
        site2 = H5Site(
            id=__import__("uuid").uuid4().hex[:36],
            site_key="test-site-2",
            domain="test2.example.com",
            name="Test Site 2",
            status="active",
            agency_id=agency_id,
        )
        session.add(site2)
        session.commit()
        site2_id = site2.id

        r = requests.post(
            f"{BASE}/api/waba/{waba_id}/assign",
            json={"site_id": site2_id},
            headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
        )
        print(f"[19] Assign to different site (should fail): {r.status_code}")
        assert r.status_code == 409  # Conflict - WABA already assigned
        print(f"     Detail: {r.json().get('detail')}")

    finally:
        session.close()

    # Test 20: Performance backend
    r = requests.get(
        f"{BASE}/api/performance/backend",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[20] Performance backend: {r.status_code}")
    resp = r.json()
    assert r.status_code == 200
    print(f"     CPU: {resp.get('cpu_percent')}%, Memory: {resp.get('memory_mb')}MB")

    # Test 21: Performance summary
    r = requests.get(
        f"{BASE}/api/performance/summary",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[21] Performance summary: {r.status_code}")
    assert r.status_code == 200

    # Test 22: Language batch init
    r = requests.post(
        f"{BASE}/api/h5/languages/batch-init",
        headers={"X-Actor-Id": "admin", "X-Actor-Role": "super_admin"},
    )
    print(f"[22] Language batch init: {r.status_code}")
    resp = r.json()
    assert r.status_code == 201
    print(f"     Created: {resp.get('created')}, Skipped: {resp.get('skipped')}")

    print()
    print("=== All LR-BE tests passed! ===")


if __name__ == "__main__":
    test_all()

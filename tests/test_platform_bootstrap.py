from typing import Any

from fastapi.testclient import TestClient


def _actor_headers(
    actor_id: str,
    role: str,
    *,
    account_ids: str | None = None,
) -> dict[str, str]:
    headers = {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": role,
    }
    if account_ids is not None:
        headers["X-Actor-Account-Ids"] = account_ids
    return headers


def _create_site(
    client: TestClient,
    headers: dict[str, str],
    *,
    account_id: str,
    site_key: str,
    domain: str,
    brand_name: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/platform/sites",
        json={
            "account_id": account_id,
            "site_key": site_key,
            "domain": domain,
            "brand_name": brand_name,
            "default_language": "zh-CN",
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_user(
    client: TestClient,
    headers: dict[str, str],
    *,
    account_id: str | None = None,
    public_user_id: str,
    registration_site_id: str | None,
    display_name: str,
    identity_value: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "public_user_id": public_user_id,
        "display_name": display_name,
        "language_code": "zh-CN",
    }
    if account_id is not None:
        payload["account_id"] = account_id
    if registration_site_id is not None:
        payload["registration_site_id"] = registration_site_id
    if identity_value is not None:
        payload["identities"] = [
            {
                "identity_type": "phone",
                "identity_value": identity_value,
                "country_code": "PH",
                "is_verified": True,
                "is_primary": True,
            }
        ]

    response = client.post("/api/platform/users", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _get_audit_logs(
    client: TestClient,
    headers: dict[str, str],
    *,
    account_id: str,
    target_type: str,
    target_id: str,
) -> list[dict[str, Any]]:
    response = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": account_id,
            "target_type": target_type,
            "target_id": target_id,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_operator_can_create_platform_bootstrap_entities(client: TestClient) -> None:
    account_id = "platform-bootstrap-account-1"
    headers = _actor_headers(
        "operator-platform-1",
        "operator",
        account_ids=account_id,
    )

    site = _create_site(
        client,
        headers,
        account_id=account_id,
        site_key="site-alpha",
        domain="alpha.example.com",
        brand_name="Alpha Hub",
    )
    assert site["account_id"] == account_id

    create_tag_response = client.post(
        "/api/platform/tags",
        json={
            "tag_key": "vip",
            "name": "VIP",
            "description": "High value user",
            "source_type": "manual",
            "is_active": True,
        },
        headers=headers,
    )
    assert create_tag_response.status_code == 200

    create_rule_response = client.post(
        "/api/platform/audience-rules",
        json={
            "rule_key": "new-user-whatsapp",
            "name": "New user with WhatsApp",
            "scope_type": "task_template",
            "status": "draft",
            "rules_json": {
                "site_keys": ["site-alpha"],
                "requires_whatsapp": True,
                "is_new_user": True,
            },
        },
        headers=headers,
    )
    assert create_rule_response.status_code == 200

    user = _create_user(
        client,
        headers,
        public_user_id="user-alpha",
        registration_site_id=site["id"],
        display_name="Alpha User",
        identity_value="+63900111222",
    )
    assert user["registration_site_key"] == "site-alpha"
    assert user["account_id"] == account_id
    assert user["has_phone"] is True
    assert user["has_whatsapp"] is False
    assert user["has_email"] is False

    list_sites_response = client.get("/api/platform/sites", headers=headers)
    assert list_sites_response.status_code == 200
    list_sites_payload = list_sites_response.json()
    assert [item["site_key"] for item in list_sites_payload] == ["site-alpha"]
    assert [item["account_id"] for item in list_sites_payload] == [account_id]

    list_users_response = client.get("/api/platform/users", headers=headers)
    assert list_users_response.status_code == 200
    assert [item["public_user_id"] for item in list_users_response.json()] == ["user-alpha"]
    assert [item["account_id"] for item in list_users_response.json()] == [account_id]

    list_tags_response = client.get("/api/platform/tags", headers=headers)
    assert list_tags_response.status_code == 200
    assert list_tags_response.json()[0]["tag_key"] == "vip"

    site_audit_logs = _get_audit_logs(
        client,
        headers,
        account_id=account_id,
        target_type="h5_site",
        target_id="site-alpha",
    )
    assert [item["action"] for item in site_audit_logs] == ["platform_site_created"]
    assert all(item["account_id"] == account_id for item in site_audit_logs)

    user_audit_logs = _get_audit_logs(
        client,
        headers,
        account_id=account_id,
        target_type="app_user",
        target_id="user-alpha",
    )
    assert [item["action"] for item in user_audit_logs] == ["platform_user_created"]
    assert all(item["account_id"] == account_id for item in user_audit_logs)


def test_readonly_can_view_platform_bootstrap_entities_but_cannot_create(client: TestClient) -> None:
    account_id = "platform-readonly-account"
    admin_headers = _actor_headers("admin-platform-1", "super_admin")
    readonly_headers = _actor_headers(
        "readonly-platform-1",
        "readonly",
        account_ids=account_id,
    )

    _create_site(
        client,
        admin_headers,
        account_id=account_id,
        site_key="site-beta",
        domain="beta.example.com",
        brand_name="Beta Hub",
    )

    list_response = client.get("/api/platform/sites", headers=readonly_headers)
    assert list_response.status_code == 200
    assert [item["site_key"] for item in list_response.json()] == ["site-beta"]

    create_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": account_id,
            "site_key": "site-gamma",
            "domain": "gamma.example.com",
            "brand_name": "Gamma Hub",
        },
        headers=readonly_headers,
    )
    assert create_response.status_code == 403
    assert "sites.create" in create_response.json()["detail"]


def test_non_super_admin_only_sees_sites_and_users_in_own_account_scope(client: TestClient) -> None:
    admin_headers = _actor_headers("admin-platform-scope", "super_admin")
    scoped_headers = _actor_headers(
        "operator-platform-scope-a",
        "operator",
        account_ids="platform-scope-account-a",
    )

    site_a = _create_site(
        client,
        admin_headers,
        account_id="platform-scope-account-a",
        site_key="site-scope-a",
        domain="scope-a.example.com",
        brand_name="Scope A",
    )
    site_b = _create_site(
        client,
        admin_headers,
        account_id="platform-scope-account-b",
        site_key="site-scope-b",
        domain="scope-b.example.com",
        brand_name="Scope B",
    )

    _create_user(
        client,
        admin_headers,
        account_id="platform-scope-account-a",
        public_user_id="user-scope-a",
        registration_site_id=site_a["id"],
        display_name="Scope User A",
        identity_value="+63900110001",
    )
    _create_user(
        client,
        admin_headers,
        account_id="platform-scope-account-b",
        public_user_id="user-scope-b",
        registration_site_id=site_b["id"],
        display_name="Scope User B",
        identity_value="+63900110002",
    )
    _create_user(
        client,
        admin_headers,
        account_id="platform-scope-account-b",
        public_user_id="user-unscoped",
        registration_site_id=None,
        display_name="Unscoped User",
    )

    sites_response = client.get("/api/platform/sites", headers=scoped_headers)
    assert sites_response.status_code == 200, sites_response.text
    sites_payload = sites_response.json()
    assert {item["site_key"] for item in sites_payload} == {"site-scope-a"}
    assert {item["account_id"] for item in sites_payload} == {"platform-scope-account-a"}

    users_response = client.get("/api/platform/users", headers=scoped_headers)
    assert users_response.status_code == 200, users_response.text
    users_payload = users_response.json()
    assert {item["public_user_id"] for item in users_payload} == {"user-scope-a"}
    assert {item["account_id"] for item in users_payload} == {"platform-scope-account-a"}
    assert {item["registration_site_key"] for item in users_payload} == {"site-scope-a"}


def test_non_super_admin_cannot_create_sites_or_users_across_account_scope(client: TestClient) -> None:
    admin_headers = _actor_headers("admin-platform-cross-account", "super_admin")
    scoped_headers = _actor_headers(
        "operator-platform-cross-account-a",
        "operator",
        account_ids="platform-create-account-a",
    )

    foreign_site = _create_site(
        client,
        admin_headers,
        account_id="platform-create-account-b",
        site_key="site-cross-account-b",
        domain="cross-account-b.example.com",
        brand_name="Cross Account B",
    )

    cross_site_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "platform-create-account-b",
            "site_key": "site-cross-account-forbidden",
            "domain": "cross-account-forbidden.example.com",
            "brand_name": "Cross Account Forbidden",
        },
        headers=scoped_headers,
    )
    assert cross_site_response.status_code == 403
    cross_site_detail = str(cross_site_response.json()["detail"]).lower()
    assert "cannot access account" in cross_site_detail
    assert "platform-create-account-b" in cross_site_detail

    cross_user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": "user-cross-account-forbidden",
            "registration_site_id": foreign_site["id"],
            "display_name": "Cross Account Forbidden User",
            "language_code": "zh-CN",
            "identities": [
                {
                    "identity_type": "phone",
                    "identity_value": "+63900119999",
                    "country_code": "PH",
                    "is_verified": True,
                    "is_primary": True,
                }
            ],
        },
        headers=scoped_headers,
    )
    assert cross_user_response.status_code == 403
    cross_user_detail = str(cross_user_response.json()["detail"]).lower()
    assert "cannot access account" in cross_user_detail
    assert "platform-create-account-b" in cross_user_detail


def test_non_super_admin_cannot_create_unscoped_site_or_user(client: TestClient) -> None:
    scoped_headers = _actor_headers(
        "operator-platform-unscoped",
        "operator",
        account_ids="platform-unscoped-account-a",
    )

    unscoped_site_response = client.post(
        "/api/platform/sites",
        json={
            "site_key": "site-unscoped-forbidden",
            "domain": "site-unscoped-forbidden.example.com",
            "brand_name": "Unscoped Site Forbidden",
        },
        headers=scoped_headers,
    )
    assert unscoped_site_response.status_code == 403
    assert "explicit account scope" in str(unscoped_site_response.json()["detail"]).lower()

    unscoped_user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": "user-unscoped-forbidden",
            "display_name": "Unscoped User Forbidden",
            "language_code": "zh-CN",
        },
        headers=scoped_headers,
    )
    assert unscoped_user_response.status_code == 409
    assert "resolved account scope" in str(unscoped_user_response.json()["detail"]).lower()


def test_operator_can_create_and_list_explicitly_scoped_user_without_site(client: TestClient) -> None:
    account_id = "platform-explicit-user-account"
    headers = _actor_headers(
        "operator-platform-explicit-user",
        "operator",
        account_ids=account_id,
    )

    user = _create_user(
        client,
        headers,
        account_id=account_id,
        public_user_id="user-explicit-account",
        registration_site_id=None,
        display_name="Explicit Account User",
        identity_value="+63900115555",
    )
    assert user["account_id"] == account_id
    assert user["registration_site_id"] is None
    assert user["registration_site_key"] is None
    assert user["registration_site_domain"] is None

    list_users_response = client.get("/api/platform/users", headers=headers)
    assert list_users_response.status_code == 200, list_users_response.text
    list_users_payload = list_users_response.json()
    assert [item["public_user_id"] for item in list_users_payload] == ["user-explicit-account"]
    assert [item["account_id"] for item in list_users_payload] == [account_id]
    assert [item["registration_site_id"] for item in list_users_payload] == [None]

    user_audit_logs = _get_audit_logs(
        client,
        headers,
        account_id=account_id,
        target_type="app_user",
        target_id="user-explicit-account",
    )
    assert [item["action"] for item in user_audit_logs] == ["platform_user_created"]
    assert all(item["account_id"] == account_id for item in user_audit_logs)


def test_non_super_admin_cannot_create_explicitly_scoped_user_outside_account_scope(client: TestClient) -> None:
    scoped_headers = _actor_headers(
        "operator-platform-explicit-user-forbidden",
        "operator",
        account_ids="platform-explicit-user-account-a",
    )

    response = client.post(
        "/api/platform/users",
        json={
            "account_id": "platform-explicit-user-account-b",
            "public_user_id": "user-explicit-account-forbidden",
            "display_name": "Explicit Account Forbidden User",
            "language_code": "zh-CN",
        },
        headers=scoped_headers,
    )
    assert response.status_code == 403
    detail = str(response.json()["detail"]).lower()
    assert "cannot access account" in detail
    assert "platform-explicit-user-account-b" in detail

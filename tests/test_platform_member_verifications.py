from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.test_h5_member_auth import _create_site, _operator_headers, _register_member


def _seed_member_verification_request(
    client: TestClient,
    *,
    account_id: str,
    site_key: str,
    phone: str,
    display_name: str,
    notes: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    site = _create_site(client, account_id=account_id, site_key=site_key)
    auth_payload = _register_member(
        client,
        site_key=site_key,
        phone=phone,
        display_name=display_name,
    )
    create_response = client.post(
        "/api/h5/member/verification/requests",
        json={
            "request_type": "identity",
            "notes": notes,
            "documents": [
                {
                    "file_name": f"{site_key}-identity-front.jpg",
                    "mime_type": "image/jpeg",
                    "storage_key": f"member-verification/{site_key}-identity-front.jpg",
                    "metadata_json": {"side": "front"},
                }
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    return site, auth_payload, create_response.json()


def test_platform_can_list_account_scoped_member_verifications(
    client: TestClient,
) -> None:
    _, _, first = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-a",
        site_key="platform-member-verifications-a",
        phone="+86139000678801",
        display_name="Verification Member A",
        notes="Please review member A.",
    )
    _, _, second = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-b",
        site_key="platform-member-verifications-b",
        phone="+86139000678802",
        display_name="Verification Member B",
        notes="Please review member B.",
    )

    response = client.get(
        "/api/platform/member-verifications",
        headers=_operator_headers("acct-platform-member-verifications-a"),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == first["id"]
    assert items[0]["accountId"] == "acct-platform-member-verifications-a"
    assert items[0]["memberNo"]
    assert items[0]["displayName"] == "Verification Member A"
    assert items[0]["status"] == "pending"
    assert items[0]["reviewNote"] is None
    assert items[0]["reviewerActorId"] is None

    filtered = client.get(
        "/api/platform/member-verifications",
        params={"status": "pending"},
        headers=_operator_headers("acct-platform-member-verifications-a"),
    )
    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()) == 1

    denied = client.get(
        "/api/platform/member-verifications",
        params={"account_id": "acct-platform-member-verifications-b"},
        headers=_operator_headers("acct-platform-member-verifications-a"),
    )
    assert denied.status_code == 403, denied.text
    assert second["id"] != first["id"]


def test_platform_member_verification_status_flow_updates_member_summary_and_messages(
    client: TestClient,
) -> None:
    _, _, created = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-flow",
        site_key="platform-member-verifications-flow",
        phone="+86139000678803",
        display_name="Verification Flow Member",
        notes="Please review my verification flow.",
    )
    headers = _operator_headers("acct-platform-member-verifications-flow")

    reviewing = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "under_review", "note": "Manual review started."},
        headers=headers,
    )
    assert reviewing.status_code == 200, reviewing.text
    reviewing_payload = reviewing.json()
    assert reviewing_payload["status"] == "under_review"
    assert reviewing_payload["reviewedAt"] is None
    assert reviewing_payload["reviewNote"] == "Manual review started."
    assert reviewing_payload["reviewerActorId"] == "operator-h5-member-auth"

    reviewing_detail = client.get(
        f"/api/platform/member-verifications/{created['id']}",
        headers=headers,
    )
    assert reviewing_detail.status_code == 200, reviewing_detail.text
    reviewing_detail_payload = reviewing_detail.json()
    assert reviewing_detail_payload["reviewNote"] == "Manual review started."
    assert reviewing_detail_payload["reviewerActorId"] == "operator-h5-member-auth"

    approved = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "approved", "note": "Identity check approved."},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    approved_payload = approved.json()
    assert approved_payload["status"] == "approved"
    assert approved_payload["reviewedAt"] is not None
    assert approved_payload["reviewNote"] == "Identity check approved."
    assert approved_payload["reviewerActorId"] == "operator-h5-member-auth"

    listed_response = client.get(
        "/api/platform/member-verifications",
        headers=headers,
    )
    assert listed_response.status_code == 200, listed_response.text
    listed_payload = listed_response.json()
    assert listed_payload[0]["id"] == created["id"]
    assert listed_payload[0]["reviewNote"] == "Identity check approved."
    assert listed_payload[0]["reviewerActorId"] == "operator-h5-member-auth"

    approved_detail = client.get(
        f"/api/platform/member-verifications/{created['id']}",
        headers=headers,
    )
    assert approved_detail.status_code == 200, approved_detail.text
    approved_detail_payload = approved_detail.json()
    assert approved_detail_payload["reviewNote"] == "Identity check approved."
    assert approved_detail_payload["reviewerActorId"] == "operator-h5-member-auth"

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    summary_payload = summary_response.json()
    assert summary_payload["currentStatus"] == "approved"
    assert summary_payload["hasActiveRequest"] is False
    assert summary_payload["history"][0]["reviewNote"] == "Identity check approved."
    assert summary_payload["history"][0]["reviewerActorId"] == "operator-h5-member-auth"

    h5_detail_response = client.get(f"/api/h5/member/verification/requests/{created['id']}")
    assert h5_detail_response.status_code == 200, h5_detail_response.text
    h5_detail_payload = h5_detail_response.json()
    assert h5_detail_payload["reviewNote"] == "Identity check approved."
    assert h5_detail_payload["reviewerActorId"] == "operator-h5-member-auth"

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert any(item["title"] == "会员认证审核中" for item in messages)
    assert any(item["title"] == "会员认证已通过" for item in messages)


def test_platform_member_verification_compat_action_routes_reuse_status_flow(
    client: TestClient,
) -> None:
    _, _, created = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-compat",
        site_key="platform-member-verifications-compat",
        phone="+86139000678806",
        display_name="Verification Compat Member",
        notes="Please review via compatibility action routes.",
    )
    headers = _operator_headers("acct-platform-member-verifications-compat")

    approve_response = client.post(
        f"/api/platform/member-verification/requests/{created['id']}/approve",
        json={"reason": "legacy_approve", "comment": "Approved through legacy action route."},
        headers=headers,
    )
    assert approve_response.status_code == 200, approve_response.text
    approved_payload = approve_response.json()
    assert approved_payload["status"] == "approved"
    assert approved_payload["reviewNote"] == "Approved through legacy action route."
    assert approved_payload["reviewerActorId"] == "operator-h5-member-auth"

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["history"][0]["reviewNote"] == "Approved through legacy action route."


def test_platform_member_verification_reject_requires_note_and_terminal_status_cannot_change(
    client: TestClient,
) -> None:
    _, _, created = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-guard",
        site_key="platform-member-verifications-guard",
        phone="+86139000678804",
        display_name="Verification Guard Member",
        notes="Please review my guarded verification.",
    )
    headers = _operator_headers("acct-platform-member-verifications-guard")

    missing_note = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "rejected"},
        headers=headers,
    )
    assert missing_note.status_code == 409, missing_note.text
    assert "review note" in missing_note.json()["detail"].lower()

    rejected = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "rejected", "note": "Document mismatch."},
        headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    rejected_payload = rejected.json()
    assert rejected_payload["status"] == "rejected"
    assert rejected_payload["reviewedAt"] is not None
    assert rejected_payload["reviewNote"] == "Document mismatch."
    assert rejected_payload["reviewerActorId"] == "operator-h5-member-auth"

    illegal = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "approved", "note": "Too late to approve."},
        headers=headers,
    )
    assert illegal.status_code == 409, illegal.text
    assert "cannot transition" in illegal.json()["detail"].lower()

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    summary_payload = summary_response.json()
    assert summary_payload["currentStatus"] == "rejected"
    assert summary_payload["history"][0]["reviewNote"] == "Document mismatch."
    assert summary_payload["history"][0]["reviewerActorId"] == "operator-h5-member-auth"

    messages_response = client.get("/api/h5/messages")
    assert messages_response.status_code == 200, messages_response.text
    assert any(item["title"] == "会员认证已驳回" for item in messages_response.json())


def test_platform_member_verification_status_update_rejects_cross_account_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, auth_payload, created = _seed_member_verification_request(
        client,
        account_id="acct-platform-member-verifications-scope-a",
        site_key="platform-member-verifications-scope-a",
        phone="+86139000678805",
        display_name="Verification Scope Member",
        notes="Please review my scoped verification.",
    )
    _ = db_session_factory

    denied = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "approved", "note": "Wrong operator scope."},
        headers=_operator_headers("acct-platform-member-verifications-scope-b"),
    )
    assert denied.status_code == 403, denied.text

    detail = client.get("/api/h5/member/verification")
    assert detail.status_code == 200, detail.text
    assert detail.json()["activeRequest"]["id"] == created["id"]
    assert auth_payload["member"]["publicUserId"]

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import MemberVerificationRequest
from tests.test_h5_member_auth import (
    _create_site,
    _operator_headers,
    _register_member,
    _strict_h5_member_auth,
)


def _create_verification_request(
    client: TestClient,
    *,
    notes: str,
    file_name: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/h5/member/verification/requests",
        json={
            "request_type": "identity",
            "notes": notes,
            "documents": [{"file_name": file_name}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _openapi_paths(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    return response.json()["paths"]


def _openapi_document(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    return response.json()


def _resolve_openapi_schema(openapi_document: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in schema:
        return schema

    ref = schema["$ref"]
    assert ref.startswith("#/components/schemas/"), ref
    schema_name = ref.rsplit("/", maxsplit=1)[-1]
    return openapi_document["components"]["schemas"][schema_name]


def _resolve_review_action_operation(client: TestClient, *, action: str) -> tuple[str, dict[str, Any]]:
    candidates = (
        f"/api/platform/member-verifications/{{request_id}}/status",
        f"/api/reviews/member-verification/requests/{{request_id}}/{action}",
        f"/api/member-verification/requests/{{request_id}}/{action}",
        f"/api/platform/member-verification/requests/{{request_id}}/{action}",
    )
    openapi_document = _openapi_document(client)
    paths = openapi_document["paths"]
    for candidate in candidates:
        operation = paths.get(candidate, {}).get("post")
        if operation is not None:
            return candidate, operation
    pytest.fail(f"Member verification review route for '{action}' is not registered.")


def _build_review_payload(
    client: TestClient,
    *,
    action: str,
    operation: dict[str, Any],
) -> dict[str, Any]:
    openapi_document = _openapi_document(client)
    request_body = operation.get("requestBody")
    assert request_body is not None, f"Member verification review route for '{action}' must declare a request body."

    content = request_body.get("content", {})
    assert "application/json" in content, (
        f"Member verification review route for '{action}' must accept application/json."
    )

    schema = _resolve_openapi_schema(openapi_document, content["application/json"]["schema"])
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    payload: dict[str, Any] = {}

    if "status" in properties:
        payload["status"] = "approved" if action == "approve" else "rejected"
    if "note" in properties:
        payload["note"] = f"member verification {action} review"
    if "reason" in properties:
        payload["reason"] = f"member_verification_{action}"
    if "comment" in properties:
        payload["comment"] = f"member verification {action} review"

    missing_required_fields = required_fields - payload.keys()
    assert not missing_required_fields, (
        f"Member verification review route for '{action}' is missing test payload support for "
        f"required fields: {sorted(missing_required_fields)}"
    )
    return payload


def _review_request(
    client: TestClient,
    *,
    action: str,
    request_id: str,
    account_id: str,
    expected_status: int,
    headers: dict[str, str] | None = None,
) -> Any:
    review_path, operation = _resolve_review_action_operation(client, action=action)
    response = client.post(
        review_path.format(request_id=request_id),
        json=_build_review_payload(client, action=action, operation=operation),
        headers=headers if headers is not None else _operator_headers(account_id),
    )
    assert response.status_code == expected_status, response.text
    return response


def test_h5_member_verification_review_route_family_exposes_supported_contract(
    client: TestClient,
) -> None:
    approve_path, approve_operation = _resolve_review_action_operation(client, action="approve")
    reject_path, reject_operation = _resolve_review_action_operation(client, action="reject")

    assert approve_path == reject_path

    approve_payload = _build_review_payload(client, action="approve", operation=approve_operation)
    reject_payload = _build_review_payload(client, action="reject", operation=reject_operation)

    if approve_path == "/api/platform/member-verifications/{request_id}/status":
        assert approve_payload == {"status": "approved", "note": "member verification approve review"}
        assert reject_payload == {"status": "rejected", "note": "member verification reject review"}
        return

    assert approve_payload["comment"] == "member verification approve review"
    assert reject_payload["comment"] == "member verification reject review"


def test_h5_member_verification_submit_and_list_current_member_requests(
    client: TestClient,
) -> None:
    _create_site(client, account_id="acct-h5-member-verification", site_key="h5-member-verification")
    _register_member(
        client,
        site_key="h5-member-verification",
        phone="+86139000677801",
        display_name="Verification Member",
    )

    summary_before = client.get("/api/h5/member/verification")
    assert summary_before.status_code == 200, summary_before.text
    assert summary_before.json()["currentStatus"] == "not_submitted"
    assert summary_before.json()["activeRequest"] is None
    assert summary_before.json()["history"] == []

    create_response = client.post(
        "/api/h5/member/verification/requests",
        json={
            "request_type": "identity",
            "notes": "Please review my identity documents.",
            "documents": [
                {
                    "file_name": "passport-front.jpg",
                    "mime_type": "image/jpeg",
                    "storage_key": "member-verification/passport-front.jpg",
                    "metadata_json": {"side": "front"},
                },
                {
                    "file_name": "passport-back.jpg",
                    "mime_type": "image/jpeg",
                    "storage_key": "member-verification/passport-back.jpg",
                    "metadata_json": {"side": "back"},
                },
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["requestType"] == "identity"
    assert created["status"] == "pending"
    assert created["notes"] == "Please review my identity documents."
    assert len(created["documents"]) == 2
    assert created["documents"][0]["fileName"] == "passport-front.jpg"

    summary_after = client.get("/api/h5/member/verification")
    assert summary_after.status_code == 200, summary_after.text
    summary_payload = summary_after.json()
    assert summary_payload["currentStatus"] == "pending"
    assert summary_payload["hasActiveRequest"] is True
    assert summary_payload["activeRequest"]["id"] == created["id"]
    assert len(summary_payload["history"]) == 1

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    home_payload = home_response.json()
    assert home_payload["verification"]["currentStatus"] == "pending"
    assert home_payload["verification"]["hasActiveRequest"] is True

    list_response = client.get("/api/h5/member/verification/requests")
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]

    detail_response = client.get(f"/api/h5/member/verification/requests/{created['id']}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["id"] == created["id"]


def test_h5_member_verification_rejects_duplicate_pending_request(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-pending"
    _create_site(
        client,
        account_id=account_id,
        site_key="h5-member-verification-pending",
    )
    _register_member(
        client,
        site_key="h5-member-verification-pending",
        phone="+86139000677802",
        display_name="Pending Verification Member",
    )

    first_request = _create_verification_request(
        client,
        notes="Initial submission",
        file_name="identity-card.png",
    )

    duplicate_response = client.post(
        "/api/h5/member/verification/requests",
        json={
            "request_type": "identity",
            "notes": "Duplicate submission",
            "documents": [{"file_name": "identity-card-duplicate.png"}],
        },
    )
    assert duplicate_response.status_code == 409, duplicate_response.text
    assert duplicate_response.json()["detail"] == "An active verification request already exists."

    reject_response = _review_request(
        client,
        action="reject",
        request_id=first_request["id"],
        account_id=account_id,
        expected_status=200,
    )
    assert reject_response.json()["status"] == "rejected"

    summary_after_reject = client.get("/api/h5/member/verification")
    assert summary_after_reject.status_code == 200, summary_after_reject.text
    assert summary_after_reject.json()["currentStatus"] == "rejected"
    assert summary_after_reject.json()["hasActiveRequest"] is False

    resubmitted_request = _create_verification_request(
        client,
        notes="Resubmission after rejection",
        file_name="identity-card-resubmitted.png",
    )
    assert resubmitted_request["notes"] == "Resubmission after rejection"
    assert resubmitted_request["status"] == "pending"


def test_h5_member_verification_request_scope_is_isolated_per_member(
    client: TestClient,
) -> None:
    _create_site(client, account_id="acct-h5-member-verification-scope", site_key="h5-member-verification-scope")
    _register_member(
        client,
        site_key="h5-member-verification-scope",
        phone="+86139000677803",
        display_name="Verification Member A",
    )
    create_response = client.post(
        "/api/h5/member/verification/requests",
        json={
            "request_type": "identity",
            "notes": "Member A submission",
            "documents": [{"file_name": "member-a-id.png"}],
        },
    )
    assert create_response.status_code == 200, create_response.text
    request_id = create_response.json()["id"]

    client.post("/api/h5/auth/logout")
    _register_member(
        client,
        site_key="h5-member-verification-scope",
        phone="+86139000677804",
        display_name="Verification Member B",
    )

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["history"] == []

    detail_response = client.get(f"/api/h5/member/verification/requests/{request_id}")
    assert detail_response.status_code == 404, detail_response.text
    assert detail_response.json()["detail"] == f"Verification request '{request_id}' was not found."


def test_h5_member_verification_review_approve_refreshes_member_summary(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "acct-h5-member-verification-approve"
    _create_site(client, account_id=account_id, site_key="h5-member-verification-approve")
    _register_member(
        client,
        site_key="h5-member-verification-approve",
        phone="+86139000677805",
        display_name="Verification Member Approve",
    )

    created = _create_verification_request(
        client,
        notes="Approve this verification",
        file_name="identity-card-approve.png",
    )

    approve_response = _review_request(
        client,
        action="approve",
        request_id=created["id"],
        account_id=account_id,
        expected_status=200,
    )
    approved = approve_response.json()
    assert approved["id"] == created["id"]
    assert approved["status"] == "approved"
    assert approved["reviewedAt"] is not None

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    summary_payload = summary_response.json()
    assert summary_payload["currentStatus"] == "approved"
    assert summary_payload["hasActiveRequest"] is False
    assert summary_payload["activeRequest"] is None
    assert summary_payload["history"][0]["id"] == created["id"]
    assert summary_payload["history"][0]["status"] == "approved"

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    home_payload = home_response.json()
    assert home_payload["verification"]["currentStatus"] == "approved"
    assert home_payload["verification"]["hasActiveRequest"] is False

    with db_session_factory() as session:
        request = session.query(MemberVerificationRequest).filter(
            MemberVerificationRequest.id == created["id"]
        ).one()
        assert request.status == "approved"
        assert request.reviewed_at is not None


def test_h5_member_verification_summary_and_detail_include_platform_review_metadata(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-platform-review-metadata"
    _create_site(
        client,
        account_id=account_id,
        site_key="h5-member-verification-platform-review-metadata",
    )
    _register_member(
        client,
        site_key="h5-member-verification-platform-review-metadata",
        phone="+86139000677810",
        display_name="Verification Member Platform Metadata",
    )

    created = _create_verification_request(
        client,
        notes="Submission for platform review metadata",
        file_name="identity-card-platform-review-metadata.png",
    )

    review_response = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "rejected", "note": "Document mismatch from platform review."},
        headers=_operator_headers(account_id),
    )
    assert review_response.status_code == 200, review_response.text
    review_payload = review_response.json()
    assert review_payload["reviewNote"] == "Document mismatch from platform review."
    assert review_payload["reviewerActorId"] == "operator-h5-member-auth"

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    summary_payload = summary_response.json()
    assert summary_payload["currentStatus"] == "rejected"
    assert summary_payload["history"][0]["reviewNote"] == "Document mismatch from platform review."
    assert summary_payload["history"][0]["reviewerActorId"] == "operator-h5-member-auth"

    detail_response = client.get(f"/api/h5/member/verification/requests/{created['id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["reviewNote"] == "Document mismatch from platform review."
    assert detail_payload["reviewerActorId"] == "operator-h5-member-auth"


def test_h5_member_verification_review_reject_allows_resubmission_and_history_refresh(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-review-reject"
    _create_site(client, account_id=account_id, site_key="h5-member-verification-review-reject")
    _register_member(
        client,
        site_key="h5-member-verification-review-reject",
        phone="+86139000677806",
        display_name="Verification Member Reject",
    )

    first_request = _create_verification_request(
        client,
        notes="First submission for rejection",
        file_name="identity-card-review-reject.png",
    )
    reject_response = _review_request(
        client,
        action="reject",
        request_id=first_request["id"],
        account_id=account_id,
        expected_status=200,
    )
    rejected = reject_response.json()
    assert rejected["status"] == "rejected"
    assert rejected["reviewedAt"] is not None
    assert rejected["reviewNote"] == "member verification reject review"
    assert rejected["reviewerActorId"] == "operator-h5-member-auth"

    summary_after_reject = client.get("/api/h5/member/verification")
    assert summary_after_reject.status_code == 200, summary_after_reject.text
    reject_summary_payload = summary_after_reject.json()
    assert reject_summary_payload["currentStatus"] == "rejected"
    assert reject_summary_payload["hasActiveRequest"] is False
    assert reject_summary_payload["activeRequest"] is None
    assert reject_summary_payload["history"][0]["reviewNote"] == "member verification reject review"
    assert reject_summary_payload["history"][0]["reviewerActorId"] == "operator-h5-member-auth"

    rejected_detail_response = client.get(
        f"/api/h5/member/verification/requests/{first_request['id']}"
    )
    assert rejected_detail_response.status_code == 200, rejected_detail_response.text
    rejected_detail_payload = rejected_detail_response.json()
    assert rejected_detail_payload["reviewNote"] == "member verification reject review"
    assert rejected_detail_payload["reviewerActorId"] == "operator-h5-member-auth"

    resubmitted = _create_verification_request(
        client,
        notes="Second submission after rejection",
        file_name="identity-card-review-resubmit.png",
    )
    assert resubmitted["status"] == "pending"

    summary_after_resubmit = client.get("/api/h5/member/verification")
    assert summary_after_resubmit.status_code == 200, summary_after_resubmit.text
    resubmit_summary_payload = summary_after_resubmit.json()
    assert resubmit_summary_payload["currentStatus"] == "pending"
    assert resubmit_summary_payload["hasActiveRequest"] is True
    assert resubmit_summary_payload["activeRequest"]["id"] == resubmitted["id"]
    assert resubmit_summary_payload["history"][1]["reviewNote"] == "member verification reject review"
    assert resubmit_summary_payload["history"][1]["reviewerActorId"] == "operator-h5-member-auth"
    assert [item["status"] for item in resubmit_summary_payload["history"]] == ["pending", "rejected"]


def test_h5_member_verification_review_requires_actor_headers(
    client: TestClient,
) -> None:
    with _strict_h5_member_auth():
        account_id = "acct-h5-member-verification-review-auth"
        _create_site(client, account_id=account_id, site_key="h5-member-verification-review-auth")
        _register_member(
            client,
            site_key="h5-member-verification-review-auth",
            phone="+86139000677807",
            display_name="Verification Member Review Auth",
        )
        created = _create_verification_request(
            client,
            notes="Missing actor header check",
            file_name="identity-card-review-auth.png",
        )

        unauthorized_response = _review_request(
            client,
            action="approve",
            request_id=created["id"],
            account_id=account_id,
            expected_status=401,
            headers={},
        )
        assert "Missing request actor headers" in unauthorized_response.json()["detail"]


def test_h5_member_verification_review_rejects_unknown_or_cross_account_scope(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-review-scope"
    _create_site(client, account_id=account_id, site_key="h5-member-verification-review-scope")
    _register_member(
        client,
        site_key="h5-member-verification-review-scope",
        phone="+86139000677808",
        display_name="Verification Member Review Scope",
    )
    created = _create_verification_request(
        client,
        notes="Scope check submission",
        file_name="identity-card-review-scope.png",
    )

    missing_response = _review_request(
        client,
        action="approve",
        request_id="missing-member-verification-request",
        account_id=account_id,
        expected_status=404,
    )
    assert "not found" in missing_response.json()["detail"].lower()

    forbidden_response = _review_request(
        client,
        action="approve",
        request_id=created["id"],
        account_id=account_id,
        expected_status=403,
        headers=_operator_headers("acct-h5-member-verification-review-other"),
    )
    assert "account" in forbidden_response.json()["detail"].lower()


def test_h5_member_verification_review_rejects_terminal_transition(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-review-terminal"
    _create_site(client, account_id=account_id, site_key="h5-member-verification-review-terminal")
    _register_member(
        client,
        site_key="h5-member-verification-review-terminal",
        phone="+86139000677809",
        display_name="Verification Member Review Terminal",
    )
    created = _create_verification_request(
        client,
        notes="Terminal transition submission",
        file_name="identity-card-review-terminal.png",
    )

    first_approve = _review_request(
        client,
        action="approve",
        request_id=created["id"],
        account_id=account_id,
        expected_status=200,
    )
    assert first_approve.json()["status"] == "approved"

    terminal_response = _review_request(
        client,
        action="reject",
        request_id=created["id"],
        account_id=account_id,
        expected_status=409,
    )
    assert "cannot transition" in terminal_response.json()["detail"].lower()


def test_h5_member_verification_summary_and_detail_include_platform_review_metadata(
    client: TestClient,
) -> None:
    account_id = "acct-h5-member-verification-platform-metadata"
    _create_site(client, account_id=account_id, site_key="h5-member-verification-platform-metadata")
    _register_member(
        client,
        site_key="h5-member-verification-platform-metadata",
        phone="+86139000677810",
        display_name="Verification Metadata Member",
    )
    created = _create_verification_request(
        client,
        notes="Submitted document note.",
        file_name="identity-card-platform-metadata.png",
    )

    review_response = client.post(
        f"/api/platform/member-verifications/{created['id']}/status",
        json={"status": "rejected", "note": "Please upload a clearer back-side document."},
        headers=_operator_headers(account_id),
    )
    assert review_response.status_code == 200, review_response.text
    reviewed = review_response.json()
    assert reviewed["reviewNote"] == "Please upload a clearer back-side document."
    assert reviewed["reviewerActorId"] == "operator-h5-member-auth"

    summary_response = client.get("/api/h5/member/verification")
    assert summary_response.status_code == 200, summary_response.text
    summary_payload = summary_response.json()
    assert summary_payload["currentStatus"] == "rejected"
    assert summary_payload["history"][0]["reviewNote"] == "Please upload a clearer back-side document."
    assert summary_payload["history"][0]["reviewerActorId"] == "operator-h5-member-auth"

    detail_response = client.get(f"/api/h5/member/verification/requests/{created['id']}")
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["notes"] == "Submitted document note."
    assert detail_payload["reviewNote"] == "Please upload a clearer back-side document."
    assert detail_payload["reviewerActorId"] == "operator-h5-member-auth"

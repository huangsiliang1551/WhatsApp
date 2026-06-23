from typing import Any

from fastapi.testclient import TestClient

from tests.test_review_ticket_contract import (
    _actor_headers,
    _create_site_user_template_instance,
    _request,
    _request_or_payload_xfail,
    _resolve_path,
    review_contract_client,
)


def _create_under_review_submission(
    client: TestClient,
    *,
    account_id: str,
    suffix: str,
) -> dict[str, Any]:
    operator_headers = _actor_headers(
        f"operator-{suffix}",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        client,
        operator_headers,
        suffix=suffix,
        account_id=account_id,
    )
    submit_path = _resolve_path(
        client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=setup["instance"]["id"])
    submit_response = _request(
        client,
        "POST",
        submit_path,
        json={
            "submission_text": f"submission for {suffix}",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context=f"create submission for {suffix}",
    )
    submission = submit_response.json()
    assert submission["status"] == "under_review"
    return {
        "setup": setup,
        "submission": submission,
        "operator_headers": operator_headers,
    }


def _create_ticket(
    client: TestClient,
    *,
    account_id: str,
    suffix: str,
    ticket_type: str = "help",
) -> dict[str, Any]:
    operator_headers = _actor_headers(
        f"operator-ticket-{suffix}",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        client,
        operator_headers,
        suffix=f"ticket-scope-{suffix}",
        account_id=account_id,
        review_required=False,
    )
    ticket_response = _request_or_payload_xfail(
        client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": ticket_type,
            "title": f"{ticket_type} title {suffix}",
            "body_text": f"{ticket_type} body {suffix}",
            "linked_task_instance_id": setup["instance"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context=f"create {ticket_type} ticket for {suffix}",
    )
    ticket = ticket_response.json()
    assert ticket["account_id"] == account_id
    return {
        "setup": setup,
        "ticket": ticket,
        "operator_headers": operator_headers,
    }


def test_review_queue_and_submission_detail_are_account_scoped(
    review_contract_client: TestClient,
) -> None:
    alpha = _create_under_review_submission(
        review_contract_client,
        account_id="review-scope-alpha",
        suffix="review-scope-alpha",
    )
    beta = _create_under_review_submission(
        review_contract_client,
        account_id="review-scope-beta",
        suffix="review-scope-beta",
    )

    alpha_reviewer_headers = _actor_headers(
        "reviewer-scope-alpha",
        "reviewer",
        account_ids="review-scope-alpha",
    )
    beta_reviewer_headers = _actor_headers(
        "reviewer-scope-beta",
        "reviewer",
        account_ids="review-scope-beta",
    )

    queue_response = review_contract_client.get("/api/reviews/queue", headers=alpha_reviewer_headers)
    assert queue_response.status_code == 200, queue_response.text
    queue_items = queue_response.json()
    assert queue_items
    assert {item["account_id"] for item in queue_items} == {"review-scope-alpha"}
    assert {item["submission"]["id"] for item in queue_items} == {alpha["submission"]["id"]}
    assert beta["submission"]["id"] not in {item["submission"]["id"] for item in queue_items}

    detail_response = review_contract_client.get(
        f"/api/reviews/submissions/{alpha['submission']['id']}",
        headers=alpha_reviewer_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_body = detail_response.json()
    assert detail_body["account_id"] == "review-scope-alpha"
    assert detail_body["submission"]["id"] == alpha["submission"]["id"]

    forbidden_detail_response = review_contract_client.get(
        f"/api/reviews/submissions/{alpha['submission']['id']}",
        headers=beta_reviewer_headers,
    )
    assert forbidden_detail_response.status_code == 403
    assert "review-scope-alpha" in str(forbidden_detail_response.json()["detail"])


def test_review_actions_require_authorized_account_scope(
    review_contract_client: TestClient,
) -> None:
    alpha = _create_under_review_submission(
        review_contract_client,
        account_id="review-action-alpha",
        suffix="review-action-alpha",
    )
    beta = _create_under_review_submission(
        review_contract_client,
        account_id="review-action-beta",
        suffix="review-action-beta",
    )

    alpha_reviewer_headers = _actor_headers(
        "reviewer-action-alpha",
        "reviewer",
        account_ids="review-action-alpha",
    )
    beta_reviewer_headers = _actor_headers(
        "reviewer-action-beta",
        "reviewer",
        account_ids="review-action-beta",
    )

    approve_forbidden = review_contract_client.post(
        f"/api/reviews/submissions/{alpha['submission']['id']}/approve",
        json={"reason_code": "cross_account_denied"},
        headers=beta_reviewer_headers,
    )
    assert approve_forbidden.status_code == 403
    assert "review-action-alpha" in str(approve_forbidden.json()["detail"])

    approve_allowed = review_contract_client.post(
        f"/api/reviews/submissions/{alpha['submission']['id']}/approve",
        json={"reason_code": "evidence_valid"},
        headers=alpha_reviewer_headers,
    )
    assert approve_allowed.status_code == 200, approve_allowed.text
    assert approve_allowed.json()["account_id"] == "review-action-alpha"
    assert approve_allowed.json()["decision"] == "approved"

    reject_forbidden = review_contract_client.post(
        f"/api/reviews/submissions/{beta['submission']['id']}/reject",
        json={"reason_code": "cross_account_denied"},
        headers=alpha_reviewer_headers,
    )
    assert reject_forbidden.status_code == 403
    assert "review-action-beta" in str(reject_forbidden.json()["detail"])

    reject_allowed = review_contract_client.post(
        f"/api/reviews/submissions/{beta['submission']['id']}/reject",
        json={"reason_code": "missing_proof", "reason_text": "manual scope review"},
        headers=beta_reviewer_headers,
    )
    assert reject_allowed.status_code == 200, reject_allowed.text
    assert reject_allowed.json()["account_id"] == "review-action-beta"
    assert reject_allowed.json()["decision"] == "rejected"


def test_ticket_list_detail_and_mutations_are_account_scoped(
    review_contract_client: TestClient,
) -> None:
    alpha = _create_ticket(
        review_contract_client,
        account_id="ticket-scope-alpha",
        suffix="alpha",
    )
    beta = _create_ticket(
        review_contract_client,
        account_id="ticket-scope-beta",
        suffix="beta",
    )

    alpha_support_headers = _actor_headers(
        "support-ticket-alpha",
        "support_agent",
        account_ids="ticket-scope-alpha",
    )
    beta_support_headers = _actor_headers(
        "support-ticket-beta",
        "support_agent",
        account_ids="ticket-scope-beta",
    )

    list_response = review_contract_client.get("/api/tickets", headers=alpha_support_headers)
    assert list_response.status_code == 200, list_response.text
    listed_tickets = list_response.json()
    assert listed_tickets
    assert {item["account_id"] for item in listed_tickets} == {"ticket-scope-alpha"}
    assert {item["id"] for item in listed_tickets} == {alpha["ticket"]["id"]}
    assert beta["ticket"]["id"] not in {item["id"] for item in listed_tickets}

    explicit_cross_scope_list = review_contract_client.get(
        "/api/tickets",
        params={"account_id": "ticket-scope-alpha"},
        headers=beta_support_headers,
    )
    assert explicit_cross_scope_list.status_code == 403
    assert "ticket-scope-alpha" in str(explicit_cross_scope_list.json()["detail"])

    detail_response = review_contract_client.get(
        f"/api/tickets/{alpha['ticket']['id']}",
        headers=alpha_support_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["account_id"] == "ticket-scope-alpha"

    forbidden_detail_response = review_contract_client.get(
        f"/api/tickets/{alpha['ticket']['id']}",
        headers=beta_support_headers,
    )
    assert forbidden_detail_response.status_code == 403
    assert "ticket-scope-alpha" in str(forbidden_detail_response.json()["detail"])

    reply_forbidden = review_contract_client.post(
        f"/api/tickets/{alpha['ticket']['id']}/messages",
        json={
            "sender_type": "agent",
            "sender_id": "support-ticket-beta",
            "body_text": "cross account reply",
            "is_internal": False,
        },
        headers=beta_support_headers,
    )
    assert reply_forbidden.status_code == 403
    assert "ticket-scope-alpha" in str(reply_forbidden.json()["detail"])

    reply_allowed = review_contract_client.post(
        f"/api/tickets/{alpha['ticket']['id']}/messages",
        json={
            "sender_type": "agent",
            "sender_id": "support-ticket-alpha",
            "body_text": "authorized reply",
            "is_internal": False,
        },
        headers=alpha_support_headers,
    )
    assert reply_allowed.status_code == 200, reply_allowed.text
    assert reply_allowed.json()["account_id"] == "ticket-scope-alpha"

    status_forbidden = review_contract_client.post(
        f"/api/tickets/{alpha['ticket']['id']}/status",
        json={"status": "in_progress"},
        headers=beta_support_headers,
    )
    assert status_forbidden.status_code == 403
    assert "ticket-scope-alpha" in str(status_forbidden.json()["detail"])

    status_allowed = review_contract_client.post(
        f"/api/tickets/{alpha['ticket']['id']}/status",
        json={"status": "in_progress"},
        headers=alpha_support_headers,
    )
    assert status_allowed.status_code == 200, status_allowed.text
    assert status_allowed.json()["account_id"] == "ticket-scope-alpha"
    assert status_allowed.json()["status"] == "in_progress"

from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_review_service
from app.db.models import AppUser, TaskInstance, TaskSubmissionProof
from app.main import app

from tests.test_review_ticket_contract import (
    _actor_headers,
    _create_site_user_template_instance,
    review_contract_client,
)


def _create_h5_task_setup(client: TestClient) -> dict[str, object]:
    operator_headers = {
        "X-Actor-Id": "operator-h5-scope",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "acct-h5-alpha,acct-h5-beta",
    }
    admin_headers = {
        "X-Actor-Id": "admin-h5-scope",
        "X-Actor-Role": "super_admin",
    }

    site_alpha_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "acct-h5-alpha",
            "site_key": "h5-alpha",
            "domain": "h5-alpha.example.com",
            "brand_name": "H5 Alpha",
        },
        headers=operator_headers,
    )
    assert site_alpha_response.status_code == 200
    site_alpha = site_alpha_response.json()

    site_beta_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "acct-h5-beta",
            "site_key": "h5-beta",
            "domain": "h5-beta.example.com",
            "brand_name": "H5 Beta",
        },
        headers=operator_headers,
    )
    assert site_beta_response.status_code == 200
    site_beta = site_beta_response.json()

    user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": "h5-user-alpha",
            "registration_site_id": site_alpha["id"],
            "display_name": "H5 User Alpha",
            "language_code": "zh-CN",
            "identities": [
                {
                    "identity_type": "phone",
                    "identity_value": "+8613900012345",
                    "is_verified": True,
                    "is_primary": True,
                }
            ],
        },
        headers=operator_headers,
    )
    assert user_response.status_code == 200
    user = user_response.json()

    unbound_user_response = client.post(
        "/api/platform/users",
        json={
            "account_id": "acct-h5-alpha",
            "public_user_id": "h5-user-unbound",
            "display_name": "H5 User Unbound",
            "language_code": "zh-CN",
        },
        headers=admin_headers,
    )
    assert unbound_user_response.status_code == 200
    unbound_user = unbound_user_response.json()

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": "acct-h5-alpha",
            "task_key": "h5-proof-task",
            "name": "H5 Proof Task",
            "title": "H5 Proof Task",
            "description": "H5 scope verification task",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 3600,
            "auto_review_enabled": True,
        },
        headers=operator_headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": "acct-h5-alpha",
            "template_id": template["id"],
            "user_id": user["id"],
            "site_id": site_alpha["id"],
            "review_required": True,
        },
        headers=operator_headers,
    )
    assert instance_response.status_code == 200
    instance = instance_response.json()

    claim_response = client.post(
        f"/api/tasks/instances/{instance['id']}/claim",
        json={},
        headers=operator_headers,
    )
    assert claim_response.status_code == 200

    return {
        "site_alpha": site_alpha,
        "site_beta": site_beta,
        "user": user,
        "unbound_user": unbound_user,
        "template": template,
        "instance": claim_response.json(),
    }


def test_task_routes_are_account_scoped(review_contract_client: TestClient) -> None:
    alpha_headers = _actor_headers("operator-task-alpha", "operator", account_ids="task-scope-alpha")
    beta_headers = _actor_headers("operator-task-beta", "operator", account_ids="task-scope-beta")

    alpha_setup = _create_site_user_template_instance(
        review_contract_client,
        alpha_headers,
        suffix="task-scope-alpha",
        account_id="task-scope-alpha",
    )
    beta_setup = _create_site_user_template_instance(
        review_contract_client,
        beta_headers,
        suffix="task-scope-beta",
        account_id="task-scope-beta",
    )

    templates_response = review_contract_client.get("/api/tasks/templates", headers=alpha_headers)
    assert templates_response.status_code == 200, templates_response.text
    templates = templates_response.json()
    assert templates
    assert {item["account_id"] for item in templates} == {"task-scope-alpha"}
    assert {item["id"] for item in templates} == {alpha_setup["template"]["id"]}
    assert beta_setup["template"]["id"] not in {item["id"] for item in templates}

    instances_response = review_contract_client.get("/api/tasks/instances", headers=alpha_headers)
    assert instances_response.status_code == 200, instances_response.text
    instances = instances_response.json()
    assert instances
    assert {item["account_id"] for item in instances} == {"task-scope-alpha"}
    assert {item["id"] for item in instances} == {alpha_setup["instance"]["id"]}
    assert beta_setup["instance"]["id"] not in {item["id"] for item in instances}

    cross_scope_template_list = review_contract_client.get(
        "/api/tasks/templates",
        params={"account_id": "task-scope-beta"},
        headers=alpha_headers,
    )
    assert cross_scope_template_list.status_code == 403

    cross_scope_instance_list = review_contract_client.get(
        "/api/tasks/instances",
        params={"account_id": "task-scope-beta"},
        headers=alpha_headers,
    )
    assert cross_scope_instance_list.status_code == 403


def test_task_mutations_require_authorized_account_scope(review_contract_client: TestClient) -> None:
    alpha_headers = _actor_headers("operator-task-create-alpha", "operator", account_ids="task-create-alpha")
    beta_headers = _actor_headers("operator-task-create-beta", "operator", account_ids="task-create-beta")

    alpha_setup = _create_site_user_template_instance(
        review_contract_client,
        alpha_headers,
        suffix="task-create-alpha",
        account_id="task-create-alpha",
    )

    create_template_forbidden = review_contract_client.post(
        "/api/tasks/templates",
        json={
            "account_id": "task-create-alpha",
            "task_key": "task-create-forbidden",
            "name": "Forbidden Template",
            "title": "Forbidden Template",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 3600,
        },
        headers=beta_headers,
    )
    assert create_template_forbidden.status_code == 403

    create_instance_forbidden = review_contract_client.post(
        "/api/tasks/instances",
        json={
            "account_id": "task-create-alpha",
            "template_id": alpha_setup["template"]["id"],
            "user_id": alpha_setup["user"]["id"],
            "site_id": alpha_setup["site"]["id"],
            "review_required": False,
        },
        headers=beta_headers,
    )
    assert create_instance_forbidden.status_code == 403

    create_available_instance = review_contract_client.post(
        "/api/tasks/instances",
        json={
            "account_id": "task-create-alpha",
            "template_id": alpha_setup["template"]["id"],
            "user_id": alpha_setup["user"]["id"],
            "site_id": alpha_setup["site"]["id"],
            "review_required": False,
        },
        headers=alpha_headers,
    )
    assert create_available_instance.status_code == 200, create_available_instance.text
    available_instance = create_available_instance.json()
    assert available_instance["status"] == "available"

    claim_forbidden = review_contract_client.post(
        f"/api/tasks/instances/{available_instance['id']}/claim",
        json={},
        headers=beta_headers,
    )
    assert claim_forbidden.status_code == 403

    claim_allowed = review_contract_client.post(
        f"/api/tasks/instances/{available_instance['id']}/claim",
        json={},
        headers=alpha_headers,
    )
    assert claim_allowed.status_code == 200, claim_allowed.text
    assert claim_allowed.json()["account_id"] == "task-create-alpha"


def test_h5_routes_require_matching_site_context(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)

    wrong_site_bootstrap = client.get(
        "/api/h5/bootstrap",
        params={"site_key": "h5-beta", "public_user_id": "h5-user-alpha"},
    )
    assert wrong_site_bootstrap.status_code == 403

    wrong_site_tasks = client.get(
        "/api/h5/tasks",
        params={"site_key": "h5-beta", "public_user_id": "h5-user-alpha"},
    )
    assert wrong_site_tasks.status_code == 403

    wrong_site_detail = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-beta", "public_user_id": "h5-user-alpha"},
    )
    assert wrong_site_detail.status_code == 403

    wrong_site_ticket_create = client.post(
        "/api/h5/tickets",
        json={
            "account_id": "acct-h5-beta",
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-beta",
            "ticket_type": "help",
            "title": "wrong site",
            "body_text": "should be rejected",
            "priority": "normal",
        },
    )
    assert wrong_site_ticket_create.status_code == 403


def test_h5_routes_reject_user_site_account_scope_mismatch(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    setup = _create_h5_task_setup(client)

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == "h5-user-alpha").one()
        user.account_id = "acct-h5-beta"
        session.add(user)
        session.commit()

    bootstrap_response = client.get(
        "/api/h5/bootstrap",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert bootstrap_response.status_code == 403
    assert "current H5 account scope" in str(bootstrap_response.json()["detail"])

    tasks_response = client.get(
        "/api/h5/tasks",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert tasks_response.status_code == 403
    assert "current H5 account scope" in str(tasks_response.json()["detail"])

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "account scope mismatch should fail",
            "payload_json": {"notes": "account scope mismatch should fail"},
        },
    )
    assert submit_response.status_code == 403
    assert "current H5 account scope" in str(submit_response.json()["detail"])


def test_h5_unbound_user_and_missing_site_context_are_rejected(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)

    unbound_bootstrap = client.get(
        "/api/h5/bootstrap",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-unbound"},
    )
    assert unbound_bootstrap.status_code == 403
    assert "not bound to an H5 site" in str(unbound_bootstrap.json()["detail"])

    missing_site_submit = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "proof_file_ids": [],
            "notes": "missing site context",
            "payload_json": {},
        },
    )
    assert missing_site_submit.status_code == 404
    assert "requires a valid site" in str(missing_site_submit.json()["detail"])

    missing_site_proof = client.post(
        "/api/h5/task-proofs",
        data={
            "task_instance_id": setup["instance"]["id"],
            "public_user_id": "h5-user-alpha",
        },
        files={"file": ("proof.txt", BytesIO(b"proof"), "text/plain")},
    )
    assert missing_site_proof.status_code == 404
    assert "requires a valid site" in str(missing_site_proof.json()["detail"])


def test_h5_task_detail_includes_latest_submission_and_review_decision(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    reviewer_headers = _actor_headers("reviewer-h5-alpha", "reviewer", account_ids=account_id)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "h5 detail coverage",
            "payload_json": {"notes": "h5 detail coverage"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    submission = submit_response.json()
    assert submission["status"] == "under_review"

    detail_after_submit = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_after_submit.status_code == 200, detail_after_submit.text
    detail_payload = detail_after_submit.json()
    assert detail_payload["latest_submission_id"] == submission["id"]
    assert detail_payload["latest_submission"]["id"] == submission["id"]
    assert detail_payload["latest_submission"]["status"] == "under_review"
    assert detail_payload["latest_review_decision"] is not None
    assert detail_payload["latest_review_decision"]["decision_source"] == "placeholder_auto"

    reject_response = client.post(
        f"/api/tasks/reviews/{setup['instance']['id']}/reject",
        json={"reason": "missing_proof", "comment": "need more evidence"},
        headers=reviewer_headers,
    )
    assert reject_response.status_code == 200, reject_response.text

    detail_after_reject = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_after_reject.status_code == 200, detail_after_reject.text
    rejected_payload = detail_after_reject.json()
    assert rejected_payload["status"] == "rejected"
    assert rejected_payload["latest_submission"]["id"] == submission["id"]
    assert rejected_payload["latest_submission"]["status"] == "rejected"
    assert rejected_payload["latest_review_decision"]["decision"] == "rejected"
    assert rejected_payload["latest_review_decision"]["reason_text"] == "need more evidence"

    resubmit_after_reject = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "trying to resubmit after rejection",
            "payload_json": {"notes": "trying to resubmit after rejection"},
        },
    )
    assert resubmit_after_reject.status_code == 409, resubmit_after_reject.text
    assert "cannot be submitted from status 'rejected'" in str(resubmit_after_reject.json()["detail"])

    detail_after_failed_resubmit = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_after_failed_resubmit.status_code == 200, detail_after_failed_resubmit.text
    assert detail_after_failed_resubmit.json()["latest_submission"]["id"] == submission["id"]
    assert detail_after_failed_resubmit.json()["latest_submission"]["status"] == "rejected"


def test_h5_task_detail_keeps_latest_submission_keys_when_submission_detail_is_missing(
    client: TestClient,
) -> None:
    setup = _create_h5_task_setup(client)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "missing detail fallback coverage",
            "payload_json": {"notes": "missing detail fallback coverage"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    submission_id = submit_response.json()["id"]

    class _MissingSubmissionReviewService:
        async def get_submission_detail(self, submission_id: str) -> object:
            raise LookupError(f"submission '{submission_id}' was not found")

    app.dependency_overrides[get_review_service] = lambda: _MissingSubmissionReviewService()
    try:
        detail_response = client.get(
            f"/api/h5/tasks/{setup['instance']['id']}",
            params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
        )
    finally:
        app.dependency_overrides.pop(get_review_service, None)

    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["latest_submission_id"] == submission_id
    assert "latest_submission" in detail_payload
    assert "latest_review_decision" in detail_payload
    assert detail_payload["latest_submission"] is None
    assert detail_payload["latest_review_decision"] is None


def test_h5_submit_rejects_proof_files_from_another_task_instance(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    operator_headers = _actor_headers(
        "operator-h5-proof-scope",
        "operator",
        account_ids=account_id,
    )

    second_instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": account_id,
            "template_id": setup["template"]["id"],
            "user_id": setup["user"]["id"],
            "site_id": setup["site_alpha"]["id"],
            "review_required": True,
        },
        headers=operator_headers,
    )
    assert second_instance_response.status_code == 200, second_instance_response.text
    second_instance = second_instance_response.json()

    second_claim_response = client.post(
        f"/api/tasks/instances/{second_instance['id']}/claim",
        json={},
        headers=operator_headers,
    )
    assert second_claim_response.status_code == 200, second_claim_response.text
    second_instance_id = second_claim_response.json()["id"]

    upload_response = client.post(
        "/api/h5/task-proofs",
        data={
            "task_instance_id": setup["instance"]["id"],
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
        },
        files={"file": ("proof.txt", BytesIO(b"proof for first task"), "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text
    proof_id = upload_response.json()["id"]

    submit_response = client.post(
        f"/api/h5/tasks/{second_instance_id}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [proof_id],
            "notes": "cross-task proof should be rejected",
            "payload_json": {"notes": "cross-task proof should be rejected"},
        },
    )
    assert submit_response.status_code == 403, submit_response.text
    assert proof_id in str(submit_response.json()["detail"])
    assert second_instance_id in str(submit_response.json()["detail"])


def test_h5_submit_persists_proof_link_with_submission_task_and_account_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    setup = _create_h5_task_setup(client)

    upload_response = client.post(
        "/api/h5/task-proofs",
        data={
            "task_instance_id": setup["instance"]["id"],
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
        },
        files={"file": ("proof-success.txt", BytesIO(b"proof for same task"), "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text
    proof_id = upload_response.json()["id"]

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [proof_id],
            "notes": "proof persistence scope check",
            "payload_json": {"notes": "proof persistence scope check"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    submission = submit_response.json()

    with db_session_factory() as session:
        proof_link = (
            session.query(TaskSubmissionProof)
            .filter(TaskSubmissionProof.submission_id == submission["id"])
            .one()
        )

    assert proof_link.proof_file_id == proof_id
    assert proof_link.task_instance_id == setup["instance"]["id"]
    assert proof_link.account_id == "acct-h5-alpha"


def test_h5_appeal_ticket_can_resolve_rejected_submission_from_task_scope(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    reviewer_headers = _actor_headers("reviewer-h5-appeal", "reviewer", account_ids=account_id)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "appeal binding coverage",
            "payload_json": {"notes": "appeal binding coverage"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text

    reject_response = client.post(
        f"/api/tasks/reviews/{setup['instance']['id']}/reject",
        json={"reason": "missing_proof", "comment": "appeal route check"},
        headers=reviewer_headers,
    )
    assert reject_response.status_code == 200, reject_response.text

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": "acct-h5-alpha",
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "appeal",
            "title": "appeal from h5",
            "body_text": "please review again",
            "linked_task_instance_id": setup["instance"]["id"],
            "priority": "high",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket_payload = ticket_response.json()
    assert ticket_payload["ticket_type"] == "appeal"
    assert ticket_payload["linked_task_instance_id"] == setup["instance"]["id"]
    assert ticket_payload["linked_submission_id"] == submit_response.json()["id"]
    assert ticket_payload["review_decision_id"] == reject_response.json()["id"]

    detail_response = client.get(
        f"/api/h5/tickets/{ticket_payload['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["linked_submission_id"] == submit_response.json()["id"]
    assert detail_response.json()["review_decision_id"] == reject_response.json()["id"]


def test_h5_appeal_ticket_accepts_matching_linked_submission_binding(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    reviewer_headers = _actor_headers("reviewer-h5-appeal-match", "reviewer", account_ids=account_id)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "appeal explicit matching binding coverage",
            "payload_json": {"notes": "appeal explicit matching binding coverage"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text

    reject_response = client.post(
        f"/api/tasks/reviews/{setup['instance']['id']}/reject",
        json={"reason": "missing_proof", "comment": "appeal explicit binding route check"},
        headers=reviewer_headers,
    )
    assert reject_response.status_code == 200, reject_response.text

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": "acct-h5-alpha",
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "appeal",
            "title": "appeal from h5 with explicit submission",
            "body_text": "please review again with explicit linked submission",
            "linked_task_instance_id": setup["instance"]["id"],
            "linked_submission_id": submit_response.json()["id"],
            "priority": "high",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket_payload = ticket_response.json()
    assert ticket_payload["ticket_type"] == "appeal"
    assert ticket_payload["linked_task_instance_id"] == setup["instance"]["id"]
    assert ticket_payload["linked_submission_id"] == submit_response.json()["id"]
    assert ticket_payload["review_decision_id"] == reject_response.json()["id"]

    detail_response = client.get(
        f"/api/h5/tickets/{ticket_payload['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["linked_submission_id"] == submit_response.json()["id"]
    assert detail_response.json()["review_decision_id"] == reject_response.json()["id"]


def test_h5_submit_is_blocked_while_task_is_appealing(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    reviewer_headers = _actor_headers("reviewer-h5-appealing", "reviewer", account_ids=account_id)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "appealing resubmit guard setup",
            "payload_json": {"notes": "appealing resubmit guard setup"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text

    reject_response = client.post(
        f"/api/tasks/reviews/{setup['instance']['id']}/reject",
        json={"reason": "missing_proof", "comment": "create appeal before resubmit"},
        headers=reviewer_headers,
    )
    assert reject_response.status_code == 200, reject_response.text

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": account_id,
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "appeal",
            "title": "appeal before resubmit",
            "body_text": "appeal is active, direct resubmit must stay blocked",
            "linked_task_instance_id": setup["instance"]["id"],
            "linked_submission_id": submit_response.json()["id"],
            "priority": "high",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text

    detail_after_appeal = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_after_appeal.status_code == 200, detail_after_appeal.text
    assert detail_after_appeal.json()["status"] == "appealing"

    resubmit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "resubmit during appeal should fail",
            "payload_json": {"notes": "resubmit during appeal should fail"},
        },
    )
    assert resubmit_response.status_code == 409, resubmit_response.text
    assert "cannot be submitted from status 'appealing'" in str(
        resubmit_response.json()["detail"]
    )
    assert "appeal" in str(resubmit_response.json()["detail"]).lower()


def test_h5_submit_is_blocked_for_legacy_changes_requested_task(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    setup = _create_h5_task_setup(client)

    with db_session_factory() as session:
        instance = session.get(TaskInstance, setup["instance"]["id"])
        assert instance is not None
        instance.status = "changes_requested"
        session.add(instance)
        session.commit()

    detail_response = client.get(
        f"/api/h5/tasks/{setup['instance']['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "changes_requested"

    resubmit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "legacy changes requested resubmit should fail",
            "payload_json": {"notes": "legacy changes requested resubmit should fail"},
        },
    )
    assert resubmit_response.status_code == 409, resubmit_response.text
    assert "changes_requested" in str(resubmit_response.json()["detail"])
    assert "help ticket" in str(resubmit_response.json()["detail"]).lower()


def test_h5_appeal_ticket_is_blocked_before_task_rejection(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)

    submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "appeal should fail before rejection",
            "payload_json": {"notes": "appeal should fail before rejection"},
        },
    )
    assert submit_response.status_code == 200, submit_response.text

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": "acct-h5-alpha",
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "appeal",
            "title": "appeal before reject",
            "body_text": "should be blocked until the task is rejected",
            "linked_task_instance_id": setup["instance"]["id"],
            "linked_submission_id": submit_response.json()["id"],
            "priority": "high",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 409, ticket_response.text
    assert "rejected" in str(ticket_response.json()["detail"]).lower()


def test_h5_appeal_ticket_rejects_mismatched_linked_submission_binding(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    operator_headers = _actor_headers(
        "operator-h5-appeal-binding",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers("reviewer-h5-appeal-binding", "reviewer", account_ids=account_id)

    second_instance_response = client.post(
        "/api/tasks/instances",
        json={
            "account_id": account_id,
            "template_id": setup["template"]["id"],
            "user_id": setup["user"]["id"],
            "site_id": setup["site_alpha"]["id"],
            "review_required": True,
        },
        headers=operator_headers,
    )
    assert second_instance_response.status_code == 200, second_instance_response.text
    second_instance = second_instance_response.json()

    second_claim_response = client.post(
        f"/api/tasks/instances/{second_instance['id']}/claim",
        json={},
        headers=operator_headers,
    )
    assert second_claim_response.status_code == 200, second_claim_response.text
    second_instance_id = second_claim_response.json()["id"]

    first_submit_response = client.post(
        f"/api/h5/tasks/{setup['instance']['id']}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "primary rejected submission",
            "payload_json": {"notes": "primary rejected submission"},
        },
    )
    assert first_submit_response.status_code == 200, first_submit_response.text

    second_submit_response = client.post(
        f"/api/h5/tasks/{second_instance_id}/submit",
        json={
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "proof_file_ids": [],
            "notes": "secondary rejected submission",
            "payload_json": {"notes": "secondary rejected submission"},
        },
    )
    assert second_submit_response.status_code == 200, second_submit_response.text

    first_reject_response = client.post(
        f"/api/tasks/reviews/{setup['instance']['id']}/reject",
        json={"reason": "missing_proof", "comment": "reject primary before appeal binding check"},
        headers=reviewer_headers,
    )
    assert first_reject_response.status_code == 200, first_reject_response.text

    second_reject_response = client.post(
        f"/api/tasks/reviews/{second_instance_id}/reject",
        json={"reason": "missing_proof", "comment": "reject secondary before appeal binding check"},
        headers=reviewer_headers,
    )
    assert second_reject_response.status_code == 200, second_reject_response.text

    mismatched_ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": account_id,
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "appeal",
            "title": "appeal with mismatched submission",
            "body_text": "submission binding must match the linked rejected task",
            "linked_task_instance_id": setup["instance"]["id"],
            "linked_submission_id": second_submit_response.json()["id"],
            "priority": "high",
            "attachments_json": [],
        },
    )
    assert mismatched_ticket_response.status_code == 409, mismatched_ticket_response.text
    assert "linked_submission_id" in str(mismatched_ticket_response.json()["detail"]).lower()


def test_h5_bootstrap_treats_pending_user_ticket_as_open(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    operator_headers = _actor_headers("operator-h5-pending-user", "operator", account_ids=account_id)

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": account_id,
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "help",
            "title": "pending user alias in h5",
            "body_text": "waiting_user should remain open in h5 views",
            "linked_task_instance_id": setup["instance"]["id"],
            "priority": "normal",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket_id = ticket_response.json()["id"]

    status_response = client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "pending_user"},
        headers=operator_headers,
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "pending_user"

    detail_response = client.get(
        f"/api/h5/tickets/{ticket_id}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "pending_user"

    bootstrap_response = client.get(
        "/api/h5/bootstrap",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert bootstrap_response.status_code == 200, bootstrap_response.text
    assert bootstrap_response.json()["open_ticket_count"] == 1

    tickets_response = client.get(
        "/api/h5/tickets",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert tickets_response.status_code == 200, tickets_response.text
    tickets = tickets_response.json()
    assert [item["id"] for item in tickets] == [ticket_id]
    assert [item["status"] for item in tickets] == ["pending_user"]

    pending_filter_response = client.get(
        "/api/h5/tickets",
        params={
            "site_key": "h5-alpha",
            "public_user_id": "h5-user-alpha",
            "status": "pending_user",
        },
    )
    assert pending_filter_response.status_code == 200, pending_filter_response.text
    assert [item["id"] for item in pending_filter_response.json()] == [ticket_id]
    assert [item["status"] for item in pending_filter_response.json()] == ["pending_user"]


def test_h5_ticket_user_reply_reopens_pending_user_to_in_progress(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    operator_headers = _actor_headers("operator-h5-reopen-pending-user", "operator", account_ids=account_id)

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": account_id,
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "help",
            "title": "pending user reopen in h5",
            "body_text": "ticket should reopen after the user replies in h5",
            "linked_task_instance_id": setup["instance"]["id"],
            "priority": "normal",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket_id = ticket_response.json()["id"]

    status_response = client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "pending_user"},
        headers=operator_headers,
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "pending_user"

    reply_response = client.post(
        f"/api/h5/tickets/{ticket_id}/messages",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
        data={"body_text": "here is the missing proof from the h5 user"},
    )
    assert reply_response.status_code == 200, reply_response.text
    assert reply_response.json()["sender_type"] == "user"

    detail_response = client.get(
        f"/api/h5/tickets/{ticket_id}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "in_progress"

    bootstrap_response = client.get(
        "/api/h5/bootstrap",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert bootstrap_response.status_code == 200, bootstrap_response.text
    assert bootstrap_response.json()["open_ticket_count"] == 1

    tickets_response = client.get(
        "/api/h5/tickets",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert tickets_response.status_code == 200, tickets_response.text
    tickets = tickets_response.json()
    assert [item["id"] for item in tickets] == [ticket_id]
    assert [item["status"] for item in tickets] == ["in_progress"]

    pending_filter_response = client.get(
        "/api/h5/tickets",
        params={
            "site_key": "h5-alpha",
            "public_user_id": "h5-user-alpha",
            "status": "pending_user",
        },
    )
    assert pending_filter_response.status_code == 200, pending_filter_response.text
    assert pending_filter_response.json() == []


def test_h5_ticket_list_rejects_waiting_user_alias_filter(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    account_id = "acct-h5-alpha"
    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": account_id,
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "help",
            "title": "pending user alias filter contract in h5",
            "body_text": "h5 filters should only accept canonical pending_user",
            "linked_task_instance_id": setup["instance"]["id"],
            "priority": "normal",
            "attachments_json": [],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text

    pending_filter_response = client.get(
        "/api/h5/tickets",
        params={
            "site_key": "h5-alpha",
            "public_user_id": "h5-user-alpha",
            "status": "pending_user",
        },
    )
    assert pending_filter_response.status_code == 200, pending_filter_response.text
    assert len(pending_filter_response.json()) == 0

    alias_filter_response = client.get(
        "/api/h5/tickets",
        params={
            "site_key": "h5-alpha",
            "public_user_id": "h5-user-alpha",
            "status": "waiting_user",
        },
    )
    assert alias_filter_response.status_code == 400, alias_filter_response.text
    assert "waiting_user" in str(alias_filter_response.json()["detail"]).lower()

def test_h5_ticket_preserves_provider_media_reference_attachments(client: TestClient) -> None:
    setup = _create_h5_task_setup(client)
    attachment = {
        "asset_id": "asset-h5-provider-reference-1",
        "provider_name": "whatsapp",
        "provider_media_id": "provider-media-h5-1",
        "phone_number_id": "pn-h5-provider-reference",
        "media_type": "image",
        "mime_type": "image/jpeg",
    }

    ticket_response = client.post(
        "/api/h5/tickets",
        json={
            "account_id": "acct-h5-alpha",
            "public_user_id": "h5-user-alpha",
            "site_key": "h5-alpha",
            "ticket_type": "help",
            "title": "h5 provider reference attachment",
            "body_text": "H5 ticket should preserve provider media references",
            "linked_task_instance_id": setup["instance"]["id"],
            "priority": "normal",
            "attachments_json": [attachment],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket_payload = ticket_response.json()
    assert ticket_payload["messages"][0]["attachments_json"] == [attachment]

    detail_response = client.get(
        f"/api/h5/tickets/{ticket_payload['id']}",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["messages"][0]["attachments_json"] == [attachment]

    list_response = client.get(
        "/api/h5/tickets",
        params={"site_key": "h5-alpha", "public_user_id": "h5-user-alpha"},
    )
    assert list_response.status_code == 200, list_response.text
    listed_ticket = next(
        item for item in list_response.json() if item["id"] == ticket_payload["id"]
    )
    assert listed_ticket["messages"][0]["attachments_json"] == [attachment]


def test_task_instance_creation_rejects_fallback_site_account_mismatch(client: TestClient) -> None:
    headers = {
        "X-Actor-Id": "operator-task-mismatch",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": "task-account-alpha,task-account-beta",
    }

    site_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "task-account-beta",
            "site_key": "task-account-beta-site",
            "domain": "task-beta.example.com",
            "brand_name": "Task Beta Site",
        },
        headers=headers,
    )
    assert site_response.status_code == 200
    site = site_response.json()

    user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": "task-account-beta-user",
            "registration_site_id": site["id"],
            "display_name": "Task Beta User",
            "language_code": "zh-CN",
        },
        headers=headers,
    )
    assert user_response.status_code == 200
    user = user_response.json()

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": "task-account-alpha",
            "task_key": "task-account-alpha-template",
            "name": "Task Alpha Template",
            "title": "Task Alpha Template",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 3600,
        },
        headers=headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()

    create_instance_response = client.post(
        "/api/tasks/instances",
        json={
            "template_id": template["id"],
            "user_id": user["id"],
            "review_required": False,
        },
        headers=headers,
    )
    assert create_instance_response.status_code == 409
    assert "registration site account_id does not match" in str(create_instance_response.json()["detail"])

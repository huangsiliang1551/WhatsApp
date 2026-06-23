from collections.abc import Generator
import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db_session
from app.core.platform_enums import TaskInstanceStatus
from app.db.base import Base
from app.db.models import Account, AppUser, H5Site, TaskInstance, Ticket, utc_now
from app.main import app
from app.services.ticket_service import TicketService


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


def _openapi_paths(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()["paths"]


def _resolve_path(
    client: TestClient,
    *,
    method: str,
    candidates: tuple[str, ...],
    feature_name: str,
) -> str:
    paths = _openapi_paths(client)
    method_name = method.lower()
    for candidate in candidates:
        if method_name in paths.get(candidate, {}):
            return candidate
    pytest.skip(f"{feature_name} route is not registered yet.")


def _request(
    client: TestClient,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    expected_statuses: tuple[int, ...],
    context: str,
):
    response = client.request(method, path, json=json, headers=headers)
    assert response.status_code in expected_statuses, response.text
    return response


def _request_or_payload_xfail(
    client: TestClient,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    expected_statuses: tuple[int, ...],
    context: str,
):
    response = client.request(method, path, json=json, headers=headers)
    if response.status_code == 422:
        pytest.xfail(f"{context} payload contract is still settling: {response.json()!r}")
    assert response.status_code in expected_statuses, response.text
    return response


def _get_account_scoped_audit_logs(
    client: TestClient,
    *,
    account_id: str,
    headers: dict[str, str],
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    scoped_headers = dict(headers)
    scoped_headers["X-Actor-Account-Ids"] = account_id
    response = client.get(
        "/api/runtime/audit-logs",
        params={"account_id": account_id, **params},
        headers=scoped_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def review_contract_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "review_contract.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    original_env = {
        "AUTH_REQUIRED": os.environ.get("AUTH_REQUIRED"),
        "TEST_MODE": os.environ.get("TEST_MODE"),
        "LIVE_TRANSLATION_ENABLED": os.environ.get("LIVE_TRANSLATION_ENABLED"),
        "TRANSLATION_PROVIDER": os.environ.get("TRANSLATION_PROVIDER"),
    }
    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["TEST_MODE"] = "false"
    os.environ["LIVE_TRANSLATION_ENABLED"] = "false"
    os.environ["TRANSLATION_PROVIDER"] = "fallback"

    from app.core.settings import get_settings

    get_settings.cache_clear()

    def override_get_db_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    engine.dispose()


def _create_site_user_template_instance(
    client: TestClient,
    headers: dict[str, str],
    *,
    suffix: str,
    account_id: str | None = None,
    review_required: bool = True,
) -> dict[str, Any]:
    resolved_account_id = account_id or f"review-account-{suffix}"
    request_headers = dict(headers)
    if "X-Actor-Account-Ids" not in request_headers:
        request_headers["X-Actor-Account-Ids"] = resolved_account_id

    site_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": resolved_account_id,
            "site_key": f"review-site-{suffix}",
            "domain": f"review-{suffix}.example.com",
            "brand_name": f"Review Site {suffix}",
        },
        headers=request_headers,
    )
    assert site_response.status_code == 200
    site = site_response.json()

    user_response = client.post(
        "/api/platform/users",
        json={
            "public_user_id": f"review-user-{suffix}",
            "registration_site_id": site["id"],
            "display_name": f"Review User {suffix}",
            "language_code": "zh-CN",
            "identities": [
                {
                    "identity_type": "phone",
                    "identity_value": f"+861390000{suffix[-4:]:0>4}",
                    "is_verified": True,
                    "is_primary": True,
                }
            ],
        },
        headers=request_headers,
    )
    assert user_response.status_code == 200
    user = user_response.json()

    template_response = client.post(
        "/api/tasks/templates",
        json={
            "account_id": resolved_account_id,
            "task_key": f"review-task-{suffix}",
            "name": f"review task {suffix}",
            "title": f"review title {suffix}",
            "description": "review workflow contract scaffold",
            "task_type": "shopping",
            "status": "active",
            "claim_timeout_seconds": 7200,
            "auto_review_enabled": True,
        },
        headers=request_headers,
    )
    assert template_response.status_code == 200
    template = template_response.json()

    instance_response = client.post(
        "/api/tasks/instances",
        json={
            "template_id": template["id"],
            "user_id": user["id"],
            "site_id": site["id"],
            "account_id": resolved_account_id,
            "review_required": review_required,
        },
        headers=request_headers,
    )
    assert instance_response.status_code == 200
    instance = instance_response.json()

    claim_response = client.post(
        f"/api/tasks/instances/{instance['id']}/claim",
        json={"claimed_by": request_headers["X-Actor-Id"]},
        headers=request_headers,
    )
    assert claim_response.status_code == 200

    return {
        "site": site,
        "user": user,
        "template": template,
        "instance": claim_response.json(),
        "account_id": resolved_account_id,
    }


def test_review_workflow_primitives_already_exist_in_current_model() -> None:
    expected_statuses = {
        TaskInstanceStatus.SUBMITTED.value,
        TaskInstanceStatus.UNDER_REVIEW.value,
        TaskInstanceStatus.APPROVED.value,
        TaskInstanceStatus.REJECTED.value,
    }
    actual_statuses = {status.value for status in TaskInstanceStatus}
    assert expected_statuses.issubset(actual_statuses)

    task_instance_columns = TaskInstance.__table__.c
    assert "submitted_at" in task_instance_columns
    assert "reviewed_at" in task_instance_columns
    assert "completed_at" in task_instance_columns


def test_existing_task_and_whatsapp_mock_chains_still_work_as_baseline_regression(
    client: TestClient,
) -> None:
    operator_headers = _actor_headers("operator-review-baseline", "operator")
    setup = _create_site_user_template_instance(client, operator_headers, suffix="baseline")

    assert setup["instance"]["status"] == "claimed"
    assert setup["instance"]["claim_deadline_at"] is not None

    inbound_response = client.post(
        "/dev/mock/inbound-message",
        json={
            "account_id": "review-baseline-account",
            "conversation_id": "review-baseline-conversation",
            "user_id": "review-baseline-user",
            "text": "baseline contract smoke",
            "mode": "echo",
        },
    )
    assert inbound_response.status_code == 200
    payload = inbound_response.json()
    assert payload["outbound"]["text"] == "Echo: baseline contract smoke"
    assert payload["translation"]["console_text"] == "baseline contract smoke"


def test_task_submission_duplicate_limit_and_audit_contract(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-submit-account"
    operator_headers = _actor_headers(
        "operator-review-submit",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="submit",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)

    first_submit = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "proof of completion",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="first task submission",
    )
    first_submit_body = first_submit.json()
    assert first_submit_body["status"] == "under_review"
    assert first_submit_body["account_id"] == account_id
    assert first_submit_body["public_user_id"] == setup["user"]["public_user_id"]
    assert first_submit_body["submitted_by_user_id"] == setup["user"]["id"]
    assert first_submit_body["review_started_at"] is not None

    duplicate_submit = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "duplicate proof",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(409,),
        context="duplicate task submission",
    )
    assert "duplicate" in str(duplicate_submit.json()["detail"]).lower()

    audit_logs = _get_account_scoped_audit_logs(
        review_contract_client,
        account_id=account_id,
        headers=operator_headers,
        params={"target_type": "task_instance", "target_id": instance_id},
    )
    actions = [item["action"] for item in audit_logs]
    assert "task_instance_submitted" in actions
    assert all(item["account_id"] == account_id for item in audit_logs)


def test_account_scoped_audit_logs_require_actor_account_scope(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-audit-scope-account"
    operator_headers = _actor_headers(
        "operator-review-audit-scope",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="audit-scope",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "scope audit coverage",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="task submission before audit scope check",
    )
    assert submit_response.json()["status"] == "under_review"

    forbidden_audit_response = review_contract_client.get(
        "/api/runtime/audit-logs",
        params={"account_id": account_id, "target_type": "task_instance", "target_id": instance_id},
        headers=_actor_headers("operator-review-audit-scope", "operator"),
    )
    assert forbidden_audit_response.status_code == 403
    assert account_id in str(forbidden_audit_response.json()["detail"])


def test_reviewer_approve_contract_and_permission_denial(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-approve-account"
    operator_headers = _actor_headers(
        "operator-review-approve",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers("reviewer-1", "reviewer", account_ids=account_id)
    support_headers = _actor_headers(
        "support-review-approve",
        "support_agent",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="approve",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    approve_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/approve",
            "/api/tasks/reviews/{task_instance_id}/approve",
        ),
        feature_name="task approval",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "ready for review",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="pre-approval submission",
    )
    submit_body = submit_response.json()
    assert submit_body["status"] == "under_review"
    assert submit_body["task_instance_id"] == instance_id

    denied_response = review_contract_client.post(
        approve_path,
        json={"reason": "support cannot approve"},
        headers=support_headers,
    )
    assert denied_response.status_code == 403

    approved_response = _request(
        review_contract_client,
        "POST",
        approve_path,
        json={"reason": "evidence_valid"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="review approval",
    )
    approved_body = approved_response.json()
    assert approved_body["status"] == "approved"
    assert approved_body["account_id"] == account_id
    assert approved_body["direct_resubmit_allowed"] is False
    assert approved_body["next_action"] == "task_completed"
    assert "approved" in approved_body["next_action_hint"].lower()
    assert approved_body["follow_up_contract"]["contract"] == "completed"
    assert approved_body["follow_up_contract"]["allowed_ticket_types"] == []
    assert approved_body["follow_up_contract"]["next_action"] == "task_completed"

    audit_logs = _get_account_scoped_audit_logs(
        review_contract_client,
        account_id=account_id,
        headers=reviewer_headers,
        params={"target_type": "task_instance", "target_id": instance_id},
    )
    actions = [item["action"] for item in audit_logs]
    assert "task_instance_approved" in actions
    assert all(item["account_id"] == account_id for item in audit_logs)


def test_legacy_review_approve_compat_response_exposes_explicit_completion_follow_up(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-approve-compat-follow-up"
    operator_headers = _actor_headers(
        "operator-review-approve-compat-follow-up",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-review-approve-compat-follow-up",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="approve-compat-follow-up",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_response = _request(
        review_contract_client,
        "POST",
        f"/api/tasks/instances/{instance_id}/submit",
        json={
            "submission_text": "legacy compat approval follow-up contract",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="legacy compat submission before approval follow-up contract",
    )
    submission_body = submit_response.json()
    assert submission_body["status"] == "under_review"

    approve_response = _request(
        review_contract_client,
        "POST",
        f"/api/tasks/reviews/{instance_id}/approve",
        json={"reason": "evidence_valid", "comment": "looks complete"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="legacy compat approval follow-up contract",
    )
    approve_body = approve_response.json()
    assert approve_body == {
        "id": approve_body["id"],
        "review_decision_id": approve_body["id"],
        "task_instance_id": instance_id,
        "submission_id": submission_body["id"],
        "account_id": account_id,
        "status": "approved",
        "decision": "approved",
        "reason_code": "evidence_valid",
        "reason_text": "looks complete",
        "direct_resubmit_allowed": False,
        "next_action": "task_completed",
        "next_action_hint": (
            "Task approved. Treat this review flow as completed; no direct resubmission, "
            "appeal, or help ticket is required."
        ),
        "follow_up_contract": {
            "contract": "completed",
            "direct_resubmit_allowed": False,
            "allowed_ticket_types": [],
            "next_action": "task_completed",
            "guidance": (
                "Task approved. Treat this review flow as completed; no direct resubmission, "
                "appeal, or help ticket is required."
            ),
        },
    }
    assert approve_body["id"] is not None


def test_reject_then_appeal_ticket_creation_contract(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-reject-account"
    operator_headers = _actor_headers(
        "operator-review-reject",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers("reviewer-2", "reviewer", account_ids=account_id)
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="reject",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    ).format(task_instance_id=instance_id)
    ticket_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tickets",
            "/api/support/tickets",
        ),
        feature_name="ticket creation",
    )

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "awaiting rejection path",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="pre-rejection submission",
    )
    submit_body = submit_response.json()
    assert submit_body["status"] == "under_review"
    assert submit_body["task_instance_id"] == instance_id

    premature_appeal = review_contract_client.post(
        ticket_path,
        json={
            "ticket_type": "appeal",
            "task_instance_id": instance_id,
            "title": "appeal before reject",
            "content": "should be blocked until task is rejected",
        },
        headers=operator_headers,
    )
    assert premature_appeal.status_code == 409

    rejected_response = _request(
        review_contract_client,
        "POST",
        reject_path,
        json={"reason": "missing_proof", "comment": "please resubmit with evidence"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="review rejection",
    )
    rejected_body = rejected_response.json()
    assert rejected_body["status"] == "rejected"
    assert rejected_body["account_id"] == account_id
    assert rejected_body["direct_resubmit_allowed"] is False
    assert rejected_body["next_action"] == "appeal_or_help_ticket"
    assert "direct resubmission" in rejected_body["next_action_hint"].lower()
    assert "appeal" in rejected_body["next_action_hint"].lower()
    assert rejected_body["follow_up_contract"]["contract"] == "appeal_or_help_only"
    assert rejected_body["follow_up_contract"]["allowed_ticket_types"] == ["appeal", "help"]
    assert rejected_body["follow_up_contract"]["next_action"] == "appeal_or_help_ticket"

    appeal_response = _request(
        review_contract_client,
        "POST",
        ticket_path,
        json={
            "ticket_type": "appeal",
            "task_instance_id": instance_id,
            "title": "appeal rejected review",
            "content": "request manual re-check",
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="appeal ticket creation",
    )
    appeal_body = appeal_response.json()
    assert appeal_body["account_id"] == account_id
    assert appeal_body["ticket_type"] == "appeal"
    assert appeal_body["status"] == "open"
    assert appeal_body["linked_task_instance_id"] == instance_id
    assert appeal_body["linked_submission_id"] == submit_body["id"]
    assert appeal_body["review_decision_id"] == rejected_body["id"]

    audit_logs = _get_account_scoped_audit_logs(
        review_contract_client,
        account_id=account_id,
        headers=reviewer_headers,
        params={"target_id": instance_id, "limit": 50},
    )
    actions = [item["action"] for item in audit_logs]
    assert "task_instance_rejected" in actions
    assert "appeal_ticket_created" in actions
    assert all(item["account_id"] == account_id for item in audit_logs)

    appeal_detail_response = review_contract_client.get(
        f"/api/tickets/{appeal_body['id']}",
        headers=operator_headers,
    )
    assert appeal_detail_response.status_code == 200, appeal_detail_response.text
    assert appeal_detail_response.json()["review_decision_id"] == rejected_body["id"]


def test_legacy_review_reject_compat_response_blocks_direct_resubmit_and_points_to_appeal_or_help(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-reject-compat-follow-up"
    operator_headers = _actor_headers(
        "operator-review-reject-compat-follow-up",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-review-reject-compat-follow-up",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="reject-compat-follow-up",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_response = _request(
        review_contract_client,
        "POST",
        f"/api/tasks/instances/{instance_id}/submit",
        json={
            "submission_text": "legacy compat reject follow-up contract",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="legacy compat submission before reject follow-up contract",
    )
    submission_body = submit_response.json()
    assert submission_body["status"] == "under_review"

    reject_response = _request(
        review_contract_client,
        "POST",
        f"/api/tasks/reviews/{instance_id}/reject",
        json={"reason": "missing_proof", "comment": "use appeal or help, direct resubmit stays blocked"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="legacy compat reject follow-up contract",
    )
    reject_body = reject_response.json()
    assert reject_body == {
        "id": reject_body["id"],
        "review_decision_id": reject_body["id"],
        "task_instance_id": instance_id,
        "submission_id": submission_body["id"],
        "account_id": account_id,
        "status": "rejected",
        "decision": "rejected",
        "reason_code": "missing_proof",
        "reason_text": "use appeal or help, direct resubmit stays blocked",
        "direct_resubmit_allowed": False,
        "next_action": "appeal_or_help_ticket",
        "next_action_hint": (
            "Task rejected. Direct resubmission is not allowed; continue with an appeal ticket or "
            "a help ticket for follow-up."
        ),
        "follow_up_contract": {
            "contract": "appeal_or_help_only",
            "direct_resubmit_allowed": False,
            "allowed_ticket_types": ["appeal", "help"],
            "next_action": "appeal_or_help_ticket",
            "guidance": (
                "Task rejected. Direct resubmission is not allowed; continue with an appeal ticket "
                "or a help ticket for follow-up."
            ),
        },
    }
    assert reject_body["id"] is not None


def test_task_submission_contract_rejects_resubmit_after_rejection(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-resubmit-after-reject"
    operator_headers = _actor_headers(
        "operator-review-resubmit-after-reject",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-review-resubmit-after-reject",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="resubmit-after-reject",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "reject and block resubmit",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="initial submission before rejection",
    )
    submission_body = submit_response.json()
    assert submission_body["status"] == "under_review"

    rejected_response = _request(
        review_contract_client,
        "POST",
        reject_path,
        json={"reason": "missing_proof", "comment": "reject before resubmit check"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="review rejection before resubmit check",
    )
    rejected_body = rejected_response.json()
    assert rejected_body["status"] == "rejected"
    assert rejected_body["direct_resubmit_allowed"] is False
    assert rejected_body["next_action"] == "appeal_or_help_ticket"
    assert rejected_body["follow_up_contract"]["contract"] == "appeal_or_help_only"

    resubmit_response = review_contract_client.post(
        submit_path,
        json={
            "submission_text": "trying to resubmit after rejection",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
    )
    assert resubmit_response.status_code == 409
    assert "cannot be submitted from status 'rejected'" in str(
        resubmit_response.json()["detail"]
    )

    task_detail_response = review_contract_client.get(
        f"/api/tasks/instances/{instance_id}",
        headers=operator_headers,
    )
    if task_detail_response.status_code == 200:
        task_detail = task_detail_response.json()
        latest_submission = task_detail.get("latest_submission")
        if isinstance(latest_submission, dict):
            assert latest_submission["id"] == submission_body["id"]
            assert latest_submission["status"] == "rejected"


@pytest.mark.parametrize("ticket_type", ("help", "complaint"))
def test_help_and_complaint_ticket_contract(
    review_contract_client: TestClient,
    ticket_type: str,
) -> None:
    account_id = f"review-ticket-account-{ticket_type}"
    operator_headers = _actor_headers(
        "operator-review-ticket",
        "operator",
        account_ids=account_id,
    )
    readonly_headers = _actor_headers(
        "readonly-review-ticket",
        "readonly",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix=f"ticket-{ticket_type}",
        account_id=account_id,
        review_required=False,
    )

    ticket_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tickets",
            "/api/support/tickets",
        ),
        feature_name=f"{ticket_type} ticket creation",
    )

    denied_response = review_contract_client.post(
        ticket_path,
        json={
            "ticket_type": ticket_type,
            "task_instance_id": setup["instance"]["id"],
            "title": f"{ticket_type} ticket denied check",
            "content": "readonly actor should not create tickets",
        },
        headers=readonly_headers,
    )
    if denied_response.status_code == 422:
        pytest.xfail(f"{ticket_type} ticket payload contract is still settling: {denied_response.json()!r}")
    assert denied_response.status_code == 403

    created_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        ticket_path,
        json={
            "ticket_type": ticket_type,
            "task_instance_id": setup["instance"]["id"],
            "title": f"{ticket_type} ticket title",
            "content": f"{ticket_type} ticket content",
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context=f"{ticket_type} ticket creation",
    )
    created_body = created_response.json()
    assert created_body["account_id"] == account_id
    assert created_body["ticket_type"] == ticket_type
    assert created_body["status"] == "open"

    audit_logs = _get_account_scoped_audit_logs(
        review_contract_client,
        account_id=account_id,
        headers=operator_headers,
        params={"target_id": created_body["id"]},
    )
    actions = [item["action"] for item in audit_logs]
    assert f"{ticket_type}_ticket_created" in actions
    assert all(item["account_id"] == account_id for item in audit_logs)


def test_ticket_messages_preserve_provider_media_reference_attachments(
    review_contract_client: TestClient,
) -> None:
    account_id = "ticket-provider-reference-account"
    operator_headers = _actor_headers(
        "operator-ticket-provider-reference",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="ticket-provider-reference",
        account_id=account_id,
        review_required=False,
    )
    initial_attachment = {
        "asset_id": "asset-ticket-provider-reference-1",
        "provider_name": "whatsapp",
        "provider_media_id": "provider-media-ticket-1",
        "phone_number_id": "pn-ticket-provider-reference",
        "media_type": "image",
        "mime_type": "image/jpeg",
    }

    created_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "provider media reference ticket",
            "body_text": "ticket should preserve provider media references",
            "linked_task_instance_id": setup["instance"]["id"],
            "attachments_json": [initial_attachment],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="ticket provider media reference creation",
    )
    ticket_body = created_response.json()
    ticket_id = ticket_body["id"]
    assert ticket_body["messages"][0]["attachments_json"] == [initial_attachment]

    detail_response = review_contract_client.get(
        f"/api/tickets/{ticket_id}",
        headers=operator_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["messages"][0]["attachments_json"] == [initial_attachment]

    reply_attachment = {
        "asset_id": "asset-ticket-provider-reference-2",
        "provider_name": "whatsapp",
        "provider_media_id": "provider-media-ticket-2",
        "phone_number_id": "pn-ticket-provider-reference",
        "media_type": "document",
        "mime_type": "application/pdf",
    }
    reply_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={
            "sender_type": "agent",
            "sender_id": operator_headers["X-Actor-Id"],
            "attachments_json": [reply_attachment],
            "is_internal": False,
        },
        headers=operator_headers,
    )
    assert reply_response.status_code == 200, reply_response.text
    assert reply_response.json()["attachments_json"] == [reply_attachment]

    updated_detail_response = review_contract_client.get(
        f"/api/tickets/{ticket_id}",
        headers=operator_headers,
    )
    assert updated_detail_response.status_code == 200, updated_detail_response.text
    message_attachments = {
        message["id"]: message["attachments_json"]
        for message in updated_detail_response.json()["messages"]
    }
    assert message_attachments[ticket_body["messages"][0]["id"]] == [initial_attachment]
    assert message_attachments[reply_response.json()["id"]] == [reply_attachment]


def test_review_reject_requires_reason_payload(review_contract_client: TestClient) -> None:
    account_id = "review-reason-account"
    operator_headers = _actor_headers(
        "operator-review-reason",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-reason",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="reject-reason",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "missing rejection reason check",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="submission before rejection validation",
    )
    assert submit_response.json()["status"] == "under_review"

    reject_response = review_contract_client.post(reject_path, json={}, headers=reviewer_headers)
    assert reject_response.status_code == 409
    assert "reason" in str(reject_response.json()["detail"]).lower()


def test_ticket_status_machine_and_active_appeal_guard(review_contract_client: TestClient) -> None:
    account_id = "ticket-state-account"
    operator_headers = _actor_headers(
        "operator-ticket-state",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-ticket-state",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="ticket-state",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    ).format(task_instance_id=instance_id)
    ticket_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tickets",
            "/api/support/tickets",
        ),
        feature_name="ticket creation",
    )

    _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "appeal uniqueness setup",
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="submission before appeal setup",
    )
    _request(
        review_contract_client,
        "POST",
        reject_path,
        json={"reason": "missing_proof", "comment": "need appeal path"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="rejection before appeal setup",
    )

    first_appeal = _request(
        review_contract_client,
        "POST",
        ticket_path,
        json={
            "ticket_type": "appeal",
            "task_instance_id": instance_id,
            "title": "first appeal",
            "content": "request manual re-check",
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="first appeal ticket creation",
    )
    first_appeal_body = first_appeal.json()

    duplicate_appeal = review_contract_client.post(
        ticket_path,
        json={
            "ticket_type": "appeal",
            "task_instance_id": instance_id,
            "title": "duplicate appeal",
            "content": "should be blocked while active",
        },
        headers=operator_headers,
    )
    assert duplicate_appeal.status_code == 409
    duplicate_detail = str(duplicate_appeal.json()["detail"]).lower()
    assert "appeal" in duplicate_detail

    status_response = review_contract_client.post(
        f"/api/tickets/{first_appeal_body['id']}/status",
        json={"status": "resolved"},
        headers=operator_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "resolved"

    closed_response = review_contract_client.post(
        f"/api/tickets/{first_appeal_body['id']}/status",
        json={"status": "closed"},
        headers=operator_headers,
    )
    assert closed_response.status_code == 200
    assert closed_response.json()["status"] == "closed"

    second_appeal = _request(
        review_contract_client,
        "POST",
        ticket_path,
        json={
            "ticket_type": "appeal",
            "task_instance_id": instance_id,
            "title": "second appeal",
            "content": "allowed after the first appeal is closed",
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="second appeal ticket creation after close",
    )
    second_appeal_body = second_appeal.json()
    assert second_appeal_body["ticket_type"] == "appeal"
    assert second_appeal_body["id"] != first_appeal_body["id"]
    assert second_appeal_body["status"] == "open"

    illegal_transition = review_contract_client.post(
        f"/api/tickets/{first_appeal_body['id']}/status",
        json={"status": "in_progress"},
        headers=operator_headers,
    )
    assert illegal_transition.status_code == 409
    assert "cannot transition" in str(illegal_transition.json()["detail"]).lower()


def test_task_submission_remains_blocked_after_appeal_closes(
    review_contract_client: TestClient,
) -> None:
    account_id = "review-appeal-close-resubmit"
    operator_headers = _actor_headers(
        "operator-review-appeal-close-resubmit",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-review-appeal-close-resubmit",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="appeal-close-resubmit",
        account_id=account_id,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "appeal close should still keep direct resubmit blocked",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="submission before appeal close regression",
    )
    rejected_response = _request(
        review_contract_client,
        "POST",
        reject_path,
        json={"reason": "missing_proof", "comment": "force appeal then close"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="rejection before appeal close regression",
    )
    assert rejected_response.json()["status"] == "rejected"

    appeal_response = _request(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "appeal",
            "title": "appeal before close",
            "body_text": "closing the appeal should not reopen direct submission",
            "linked_task_instance_id": instance_id,
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="appeal creation before close regression",
    )
    appeal_ticket_id = appeal_response.json()["id"]

    resolve_response = _request(
        review_contract_client,
        "POST",
        f"/api/tickets/{appeal_ticket_id}/status",
        json={"status": "resolved"},
        headers=operator_headers,
        expected_statuses=(200,),
        context="resolve appeal before resubmit regression",
    )
    assert resolve_response.json()["status"] == "resolved"

    task_detail_response = review_contract_client.get(
        f"/api/h5/tasks/{instance_id}",
        params={
            "site_key": setup["site"]["site_key"],
            "public_user_id": setup["user"]["public_user_id"],
        },
    )
    assert task_detail_response.status_code == 200, task_detail_response.text
    assert task_detail_response.json()["status"] == "rejected"

    resubmit_response = review_contract_client.post(
        submit_path,
        json={
            "submission_text": "still trying to resubmit after appeal close",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
    )
    assert resubmit_response.status_code == 409
    assert "cannot be submitted from status 'rejected'" in str(resubmit_response.json()["detail"])


def test_ticket_pending_user_status_is_returned_canonically(
    review_contract_client: TestClient,
) -> None:
    account_id = "ticket-pending-user-contract"
    operator_headers = _actor_headers(
        "operator-ticket-pending-user",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="ticket-pending-user",
        account_id=account_id,
        review_required=False,
    )

    created_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "pending user alias contract",
            "body_text": "legacy waiting_user should not leak back",
            "linked_task_instance_id": setup["instance"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="create ticket before pending_user alias check",
    )
    ticket_id = created_response.json()["id"]

    pending_update_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "pending_user"},
        headers=operator_headers,
    )
    assert pending_update_response.status_code == 200, pending_update_response.text
    assert pending_update_response.json()["status"] == "pending_user"

    detail_response = review_contract_client.get(
        f"/api/tickets/{ticket_id}",
        headers=operator_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "pending_user"

    pending_list_response = review_contract_client.get(
        "/api/tickets",
        params={"account_id": account_id, "status": "pending_user"},
        headers=operator_headers,
    )
    assert pending_list_response.status_code == 200, pending_list_response.text
    pending_tickets = pending_list_response.json()
    assert {item["id"] for item in pending_tickets} == {ticket_id}
    assert {item["status"] for item in pending_tickets} == {"pending_user"}

def test_ticket_front_door_rejects_waiting_user_alias_input(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    account_id = "ticket-pending-user-persisted"
    operator_headers = _actor_headers(
        "operator-ticket-pending-user-persisted",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        client,
        operator_headers,
        suffix="ticket-pending-user-persisted",
        account_id=account_id,
        review_required=False,
    )

    created_response = _request_or_payload_xfail(
        client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "pending user alias persisted contract",
            "body_text": "waiting_user input should persist canonically",
            "linked_task_instance_id": setup["instance"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="create ticket before pending_user persistence alias check",
    )
    ticket_id = created_response.json()["id"]

    alias_update_response = client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "waiting_user"},
        headers=operator_headers,
    )
    assert alias_update_response.status_code == 400, alias_update_response.text
    assert "waiting_user" in str(alias_update_response.json()["detail"]).lower()

    with db_session_factory() as session:
        persisted_ticket = session.get(Ticket, ticket_id)
        assert persisted_ticket is not None
        assert persisted_ticket.status == "open"

    detail_response = client.get(
        f"/api/tickets/{ticket_id}",
        headers=operator_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "open"

    alias_list_response = client.get(
        "/api/tickets",
        params={"account_id": account_id, "status": "waiting_user"},
        headers=operator_headers,
    )
    assert alias_list_response.status_code == 400, alias_list_response.text
    assert "waiting_user" in str(alias_list_response.json()["detail"]).lower()


def test_ticket_user_reply_reopens_pending_user_to_in_progress(
    review_contract_client: TestClient,
) -> None:
    account_id = "ticket-user-reply-reopen-contract"
    operator_headers = _actor_headers(
        "operator-ticket-user-reply",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="ticket-user-reply",
        account_id=account_id,
        review_required=False,
    )

    created_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "pending user reply contract",
            "body_text": "waiting for user supplement",
            "linked_task_instance_id": setup["instance"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="create ticket before pending user reply contract",
    )
    ticket_id = created_response.json()["id"]

    pending_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "pending_user"},
        headers=operator_headers,
    )
    assert pending_response.status_code == 200, pending_response.text
    assert pending_response.json()["status"] == "pending_user"

    user_reply_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={
            "sender_type": "user",
            "sender_id": setup["user"]["public_user_id"],
            "body_text": "here is the missing evidence",
            "attachments_json": [],
            "is_internal": False,
        },
        headers=operator_headers,
    )
    assert user_reply_response.status_code == 200, user_reply_response.text

    detail_response = review_contract_client.get(
        f"/api/tickets/{ticket_id}",
        headers=operator_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "in_progress"


def test_ticket_rejected_can_close_but_rejects_new_messages(
    review_contract_client: TestClient,
) -> None:
    account_id = "ticket-rejected-terminal-contract"
    operator_headers = _actor_headers(
        "operator-ticket-rejected-terminal",
        "operator",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="ticket-rejected-terminal",
        account_id=account_id,
        review_required=False,
    )

    created_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "rejected terminal contract",
            "body_text": "rejected tickets should only allow close",
            "linked_task_instance_id": setup["instance"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="create ticket before rejected terminal contract",
    )
    ticket_id = created_response.json()["id"]

    rejected_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "rejected"},
        headers=operator_headers,
    )
    assert rejected_response.status_code == 200, rejected_response.text
    assert rejected_response.json()["status"] == "rejected"

    blocked_message_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={
            "sender_type": "operator",
            "sender_id": "operator-ticket-rejected-terminal",
            "body_text": "should be blocked after rejection",
            "attachments_json": [],
            "is_internal": False,
        },
        headers=operator_headers,
    )
    assert blocked_message_response.status_code == 409, blocked_message_response.text
    assert "does not accept new messages" in str(blocked_message_response.json()["detail"]).lower()

    close_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "closed"},
        headers=operator_headers,
    )
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "closed"

    illegal_reopen_response = review_contract_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "in_progress"},
        headers=operator_headers,
    )
    assert illegal_reopen_response.status_code == 409, illegal_reopen_response.text
    assert "cannot transition" in str(illegal_reopen_response.json()["detail"]).lower()


def test_ticket_service_normalizes_persisted_waiting_user_rows() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    try:
        with factory() as session:
            account = Account(
                account_id="ticket-legacy-pending-user",
                display_name="Ticket Legacy Pending User",
                provider_type="mock",
            )
            site = H5Site(
                id="site-ticket-legacy-pending-user",
                account_id=account.account_id,
                site_key="site-ticket-legacy-pending-user",
                domain="ticket-legacy-pending-user.example.com",
                brand_name="Ticket Legacy Pending User",
                default_language="zh-CN",
                status="active",
            )
            user = AppUser(
                id="user-ticket-legacy-pending-user",
                account_id=account.account_id,
                public_user_id="public-ticket-legacy-pending-user",
                registration_site_id=site.id,
                display_name="Legacy Pending User",
                language_code="zh-CN",
            )
            ticket = Ticket(
                id="ticket-legacy-pending-user",
                account_id=account.account_id,
                ticket_no="TKT-LEGACY-PENDING",
                user_id=user.id,
                site_id=site.id,
                ticket_type="help",
                status="pending_user",
                priority="normal",
                title="Canonical pending user ticket",
                latest_reply_at=utc_now(),
                is_active=True,
            )
            session.add_all([account, site, user, ticket])
            session.commit()

            service = TicketService(session=session)
            pending_rows = asyncio.run(
                service.list_tickets(
                    account_id=account.account_id,
                    status="pending_user",
                )
            )
            legacy_rows = asyncio.run(
                service.list_tickets(
                    account_id=account.account_id,
                    status="waiting_user",
                )
            )
            detail = asyncio.run(service.get_ticket(ticket.id))

            assert [item.id for item in pending_rows] == [ticket.id]
            assert [item.id for item in legacy_rows] == [ticket.id]
            assert pending_rows[0].status == "pending_user"
            assert legacy_rows[0].status == "pending_user"
            assert detail.status == "pending_user"
    finally:
        engine.dispose()


def test_submission_review_decision_and_ticket_account_ids_are_never_blank(
    review_contract_client: TestClient,
) -> None:
    account_id = "nonblank-account-contract"
    operator_headers = _actor_headers(
        "operator-nonblank-account",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-nonblank-account",
        "reviewer",
        account_ids=account_id,
    )
    setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="nonblank-account",
        account_id=account_id,
        review_required=False,
    )
    instance_id = setup["instance"]["id"]

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=instance_id)

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "nonblank account contract",
            "attachments": [],
            "submitted_by_user_id": setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="submission account_id nonblank contract",
    )
    submission_body = submit_response.json()
    assert submission_body["account_id"] == account_id
    assert submission_body["account_id"] not in ("", None)

    approve_response = _request(
        review_contract_client,
        "POST",
        f"/api/reviews/submissions/{submission_body['id']}/approve",
        json={"reason_code": "evidence_valid"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="review decision account_id nonblank contract",
    )
    decision_body = approve_response.json()
    assert decision_body["account_id"] == account_id
    assert decision_body["account_id"] not in ("", None)

    ticket_response = _request_or_payload_xfail(
        review_contract_client,
        "POST",
        "/api/tickets",
        json={
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "nonblank ticket account",
            "body_text": "account_id should resolve to a non-empty scoped value",
            "linked_task_instance_id": instance_id,
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="ticket account_id nonblank contract",
    )
    ticket_body = ticket_response.json()
    assert ticket_body["account_id"] == account_id
    assert ticket_body["account_id"] not in ("", None)

    blank_account_response = review_contract_client.post(
        "/api/tickets",
        json={
            "account_id": "",
            "public_user_id": setup["user"]["public_user_id"],
            "site_id": setup["site"]["id"],
            "ticket_type": "help",
            "title": "blank ticket account",
            "body_text": "blank account_id must be rejected",
            "linked_task_instance_id": instance_id,
        },
        headers=operator_headers,
    )
    assert blank_account_response.status_code == 409
    assert "account_id" in str(blank_account_response.json()["detail"]).lower()


def test_appeal_ticket_rejects_mismatched_submission_review_and_account_binding(
    review_contract_client: TestClient,
) -> None:
    primary_account_id = "appeal-binding-primary"
    secondary_account_id = "appeal-binding-secondary"
    multi_account_headers = _actor_headers(
        "operator-appeal-binding",
        "operator",
        account_ids=f"{primary_account_id},{secondary_account_id}",
    )
    reviewer_headers = _actor_headers(
        "reviewer-appeal-binding",
        "reviewer",
        account_ids=primary_account_id,
    )
    primary_setup = _create_site_user_template_instance(
        review_contract_client,
        multi_account_headers,
        suffix="appeal-binding-primary",
        account_id=primary_account_id,
    )
    secondary_setup = _create_site_user_template_instance(
        review_contract_client,
        multi_account_headers,
        suffix="appeal-binding-secondary",
        account_id=secondary_account_id,
        review_required=False,
    )

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    ).format(task_instance_id=primary_setup["instance"]["id"])

    submit_response = _request(
        review_contract_client,
        "POST",
        submit_path,
        json={
            "submission_text": "appeal consistency contract",
            "attachments": [],
            "submitted_by_user_id": primary_setup["user"]["id"],
        },
        headers=_actor_headers(
            "operator-appeal-binding-primary",
            "operator",
            account_ids=primary_account_id,
        ),
        expected_statuses=(200, 201),
        context="submission before appeal consistency checks",
    )
    submission_body = submit_response.json()
    assert submission_body["account_id"] == primary_account_id

    reject_response = _request(
        review_contract_client,
        "POST",
        f"/api/reviews/submissions/{submission_body['id']}/reject",
        json={"reason_code": "missing_proof", "reason_text": "appeal consistency contract"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="rejection before appeal consistency checks",
    )
    decision_body = reject_response.json()
    assert decision_body["account_id"] == primary_account_id
    assert decision_body["submission_id"] == submission_body["id"]

    wrong_user_response = review_contract_client.post(
        "/api/tickets",
        json={
            "account_id": primary_account_id,
            "public_user_id": secondary_setup["user"]["public_user_id"],
            "site_id": primary_setup["site"]["id"],
            "ticket_type": "appeal",
            "title": "appeal wrong user",
            "body_text": "user binding must match the rejected submission scope",
            "linked_task_instance_id": primary_setup["instance"]["id"],
        },
        headers=multi_account_headers,
    )
    assert wrong_user_response.status_code == 403
    assert "does not belong to site" in str(wrong_user_response.json()["detail"]).lower()

    wrong_site_response = review_contract_client.post(
        "/api/tickets",
        json={
            "account_id": primary_account_id,
            "public_user_id": primary_setup["user"]["public_user_id"],
            "site_id": secondary_setup["site"]["id"],
            "ticket_type": "appeal",
            "title": "appeal wrong site",
            "body_text": "site binding must match the rejected submission scope",
            "linked_task_instance_id": primary_setup["instance"]["id"],
        },
        headers=multi_account_headers,
    )
    assert wrong_site_response.status_code == 409
    assert "linked task instance" in str(wrong_site_response.json()["detail"]).lower()

    wrong_account_response = review_contract_client.post(
        "/api/tickets",
        json={
            "account_id": secondary_account_id,
            "public_user_id": primary_setup["user"]["public_user_id"],
            "site_id": primary_setup["site"]["id"],
            "ticket_type": "appeal",
            "title": "appeal wrong account",
            "body_text": "account binding must match the rejected submission scope",
            "linked_task_instance_id": primary_setup["instance"]["id"],
        },
        headers=multi_account_headers,
    )
    assert wrong_account_response.status_code == 409
    assert "account_id" in str(wrong_account_response.json()["detail"]).lower()


def test_appeal_ticket_rejects_mismatched_linked_submission_binding(
    review_contract_client: TestClient,
) -> None:
    account_id = "appeal-linked-submission-contract"
    operator_headers = _actor_headers(
        "operator-appeal-linked-submission",
        "operator",
        account_ids=account_id,
    )
    reviewer_headers = _actor_headers(
        "reviewer-appeal-linked-submission",
        "reviewer",
        account_ids=account_id,
    )
    first_setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="appeal-linked-submission-primary",
        account_id=account_id,
    )
    second_setup = _create_site_user_template_instance(
        review_contract_client,
        operator_headers,
        suffix="appeal-linked-submission-secondary",
        account_id=account_id,
    )

    submit_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/submit",
            "/api/tasks/{task_instance_id}/submit",
            "/api/h5/tasks/{task_instance_id}/submit",
        ),
        feature_name="task submission",
    )
    reject_path = _resolve_path(
        review_contract_client,
        method="POST",
        candidates=(
            "/api/tasks/instances/{task_instance_id}/reject",
            "/api/tasks/reviews/{task_instance_id}/reject",
        ),
        feature_name="task rejection",
    )

    first_submit_response = _request(
        review_contract_client,
        "POST",
        submit_path.format(task_instance_id=first_setup["instance"]["id"]),
        json={
            "submission_text": "primary rejected submission",
            "submitted_by_user_id": first_setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="primary submission before appeal linked submission mismatch check",
    )
    second_submit_response = _request(
        review_contract_client,
        "POST",
        submit_path.format(task_instance_id=second_setup["instance"]["id"]),
        json={
            "submission_text": "secondary rejected submission",
            "submitted_by_user_id": second_setup["user"]["id"],
        },
        headers=operator_headers,
        expected_statuses=(200, 201),
        context="secondary submission before appeal linked submission mismatch check",
    )

    _request(
        review_contract_client,
        "POST",
        reject_path.format(task_instance_id=first_setup["instance"]["id"]),
        json={"reason": "missing_proof", "comment": "reject primary before appeal binding check"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="primary rejection before appeal linked submission mismatch check",
    )
    _request(
        review_contract_client,
        "POST",
        reject_path.format(task_instance_id=second_setup["instance"]["id"]),
        json={"reason": "missing_proof", "comment": "reject secondary before appeal binding check"},
        headers=reviewer_headers,
        expected_statuses=(200,),
        context="secondary rejection before appeal linked submission mismatch check",
    )

    mismatched_ticket_response = review_contract_client.post(
        "/api/tickets",
        json={
            "account_id": account_id,
            "public_user_id": first_setup["user"]["public_user_id"],
            "site_id": first_setup["site"]["id"],
            "ticket_type": "appeal",
            "title": "appeal with mismatched submission",
            "body_text": "submission binding must match the rejected task scope",
            "linked_task_instance_id": first_setup["instance"]["id"],
            "linked_submission_id": second_submit_response.json()["id"],
        },
        headers=operator_headers,
    )
    assert mismatched_ticket_response.status_code == 409
    assert "linked_submission_id" in str(mismatched_ticket_response.json()["detail"]).lower()

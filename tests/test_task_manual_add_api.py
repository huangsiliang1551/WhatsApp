from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.models import MemberTaskBatch, MemberTaskDayQuota, TaskPackageInstance
from tests.test_h5_member_auth import _operator_headers
from tests.test_task_manual_add_service import _seed_manual_add_scope


def test_task_manual_add_candidates_api_filters_existing_batch_products(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    response = client.get(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add/candidates",
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert [item["productId"] for item in items] == ["manual-product-3", "manual-product-4"]


def test_task_manual_add_create_api_appends_items_and_returns_updated_amounts(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "客服追加任务商品",
            "notify_user": True,
            "user_notice_text": "后台记录已通知用户",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["packageId"] == seeded["package_id"]
    assert payload["addedItemCount"] == 2
    assert payload["addedAmount"] == 90.0
    assert payload["packageManualAddedAmount"] == 90.0
    assert payload["packageEffectiveAmount"] == 140.0
    assert payload["batchManualAddedAmount"] == 90.0
    assert payload["batchEffectiveDayAmount"] == 140.0


def test_task_manual_add_preview_api_returns_amount_impact_without_persisting_items(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add/preview",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "预览追加商品",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["packageId"] == seeded["package_id"]
    assert payload["candidateCount"] == 2
    assert payload["addedItemCount"] == 2
    assert payload["addedAmount"] == 90.0
    assert payload["packageManualAddedAmountBefore"] == 0.0
    assert payload["packageManualAddedAmountAfter"] == 90.0
    assert payload["packageEffectiveAmountBefore"] == 50.0
    assert payload["packageEffectiveAmountAfter"] == 140.0
    assert payload["estimatedRewardAmountBefore"] == 5.0
    assert payload["estimatedRewardAmountAfter"] == 14.0
    assert [item["productId"] for item in payload["items"]] == ["manual-product-3", "manual-product-4"]

    detail_response = client.get(
        f"/api/tasks/packages/{seeded['package_id']}",
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["manualAddedAmount"] == 0.0
    assert len(detail_payload["items"]) == 2


def test_task_package_detail_api_includes_amount_breakdown_items_and_manual_add_logs(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "客服追加任务商品",
            "notify_user": True,
            "user_notice_text": "后台记录已通知用户",
        },
    )
    assert create_response.status_code == 200, create_response.text
    log_id = create_response.json()["id"]

    response = client.get(
        f"/api/tasks/packages/{seeded['package_id']}",
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == seeded["package_id"]
    assert payload["dayNo"] == 1
    assert payload["progressLabel"] == "1/1"
    assert payload["systemGeneratedAmount"] == 50.0
    assert payload["manualAddedAmount"] == 90.0
    assert payload["effectiveAmount"] == 140.0
    assert payload["estimatedRewardAmount"] == 14.0
    assert payload["items"][-2]["origin"] == "manual_added"
    assert payload["items"][-1]["origin"] == "manual_added"
    assert payload["manualAddLogs"][0]["id"] == log_id
    assert payload["manualAddLogs"][0]["addedItemCount"] == 2


def test_task_packages_api_lists_package_amount_breakdown_and_progress(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "客服追加任务商品",
            "notify_user": True,
            "user_notice_text": "后台记录已通知用户",
        },
    )
    assert create_response.status_code == 200, create_response.text

    response = client.get(
        "/api/tasks/packages",
        params={"account_id": "acct-task-manual-add"},
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == seeded["package_id"]
    assert payload[0]["publicUserId"] == "user-task-manual-add"
    assert payload[0]["dayNo"] == 1
    assert payload[0]["progressLabel"] == "1/1"
    assert payload[0]["manualAddedAmount"] == 90.0
    assert payload[0]["effectiveAmount"] == 140.0
    assert payload[0]["estimatedRewardAmount"] == 14.0
    assert payload[0]["hasManualAdd"] is True


def test_task_manual_add_logs_api_lists_logs_for_package(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "客服追加任务商品",
            "notify_user": True,
            "user_notice_text": "后台记录已通知用户",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    response = client.get(
        "/api/tasks/manual-add/logs",
        params={"package_id": seeded["package_id"]},
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == created["id"]
    assert payload[0]["packageId"] == seeded["package_id"]
    assert payload[0]["addedAmount"] == 90.0
    assert payload[0]["notifyUser"] is True
    assert payload[0]["userNoticeText"] == "后台记录已通知用户"
    assert payload[0]["userNotifiedAt"] is not None


def test_task_manual_add_create_api_writes_runtime_audit_log_with_before_after_snapshots(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    create_response = client.post(
        f"/api/tasks/packages/{seeded['package_id']}/manual-add",
        headers=_operator_headers("acct-task-manual-add"),
        json={
            "pool_item_ids": [seeded["pool_item_3_id"], seeded["pool_item_4_id"]],
            "reason_text": "客服追加任务商品",
            "notify_user": True,
            "user_notice_text": "后台记录已通知用户",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=_operator_headers("acct-task-manual-add"),
        params={
            "account_id": "acct-task-manual-add",
            "target_type": "task_package_instance",
            "target_id": seeded["package_id"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "task_package_manual_add_created"]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["log_id"] == created["id"]
    assert payload["added_item_count"] == 2
    assert payload["added_amount"] == 90.0
    assert payload["before_manual_added_amount"] == 0.0
    assert payload["after_manual_added_amount"] == 90.0
    assert payload["before_effective_amount"] == 50.0
    assert payload["after_effective_amount"] == 140.0
    assert payload["notify_user"] is True
    assert payload["user_notice_text"] == "后台记录已通知用户"


def test_task_packages_api_without_account_filter_ignores_other_accounts(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)
    other = _seed_manual_add_scope(db_session_factory, suffix="-other")
    assert other["package_id"] != seeded["package_id"]

    response = client.get(
        "/api/tasks/packages",
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["accountId"] == "acct-task-manual-add"


def test_task_member_instance_pause_and_resume_actions_update_package_status(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory)

    pause_response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/pause",
        headers=_operator_headers("acct-task-manual-add"),
        json={"reason_text": "人工暂停观察"},
    )
    assert pause_response.status_code == 200, pause_response.text
    paused = pause_response.json()
    assert paused["id"] == seeded["package_id"]
    assert paused["status"] == "paused"

    detail_paused = client.get(
        f"/api/tasks/packages/{seeded['package_id']}",
        headers=_operator_headers("acct-task-manual-add"),
    )
    assert detail_paused.status_code == 200, detail_paused.text
    assert detail_paused.json()["status"] == "paused"

    resume_response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/resume",
        headers=_operator_headers("acct-task-manual-add"),
        json={"reason_text": "恢复任务"},
    )
    assert resume_response.status_code == 200, resume_response.text
    resumed = resume_response.json()
    assert resumed["id"] == seeded["package_id"]
    assert resumed["status"] == "active"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=_operator_headers("acct-task-manual-add"),
        params={
            "account_id": "acct-task-manual-add",
            "target_type": "task_package_instance",
            "target_id": seeded["package_id"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    pause_items = [item for item in items if item["action"] == "task_package_paused"]
    resume_items = [item for item in items if item["action"] == "task_package_resumed"]
    assert len(pause_items) == 1
    assert pause_items[0]["payload"]["reason_text"] == "人工暂停观察"
    assert len(resume_items) == 1
    assert resume_items[0]["payload"]["reason_text"] == "恢复任务"


def test_task_member_instance_cancel_action_sets_cancelled_status(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory, suffix="-cancel")

    cancel_response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/cancel",
        headers=_operator_headers("acct-task-manual-add-cancel"),
        json={"reason_text": "人工取消任务"},
    )
    assert cancel_response.status_code == 200, cancel_response.text
    cancelled = cancel_response.json()
    assert cancelled["id"] == seeded["package_id"]
    assert cancelled["status"] == "cancelled"

    detail_response = client.get(
        f"/api/tasks/packages/{seeded['package_id']}",
        headers=_operator_headers("acct-task-manual-add-cancel"),
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["status"] == "cancelled"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=_operator_headers("acct-task-manual-add-cancel"),
        params={
            "account_id": "acct-task-manual-add-cancel",
            "target_type": "task_package_instance",
            "target_id": seeded["package_id"],
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    cancel_items = [item for item in items if item["action"] == "task_package_cancelled"]
    assert len(cancel_items) == 1
    assert cancel_items[0]["payload"]["reason_text"] == "人工取消任务"


def test_task_member_instance_pause_next_batch_action_cancels_next_pending_quota(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory, suffix="-pause-next")

    with db_session_factory() as session:
        package = session.get(TaskPackageInstance, seeded["package_id"])
        assert package is not None
        batch = session.get(MemberTaskBatch, package.batch_id)
        assert batch is not None
        batch.plan_id = "plan-next"
        session.add(batch)
        next_quota = MemberTaskDayQuota(
            account_id=package.account_id,
            site_id=package.site_id,
            user_id=package.user_id,
            plan_id="plan-next",
            day_no=(package.batch_day_no or 1) + 1,
            package_count=2,
            day_total_amount=Decimal("200.00"),
            tolerance_amount=Decimal("5.00"),
            amount_allocation_mode="average",
            package_amounts_json=["100.00", "100.00"],
            product_pool_id=seeded["pool_id"],
            product_count_mode="range",
            product_count_min=1,
            product_count_max=2,
            reward_ratio=Decimal("0.15"),
            status="pending",
            created_by="operator-next",
            metadata_json={"source": "test"},
        )
        session.add(next_quota)
        session.commit()
        next_quota_id = next_quota.id

    response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/pause-next-batch",
        headers=_operator_headers("acct-task-manual-add-pause-next"),
        json={"reason": "manual_pause_next_batch_from_monitor"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == next_quota_id
    assert payload["status"] == "cancelled"
    assert payload["dayNo"] == 2
    assert payload["metadataJson"]["cancel_reason"] == "manual_pause_next_batch_from_monitor"

    with db_session_factory() as session:
        refreshed = session.get(MemberTaskDayQuota, next_quota_id)
        assert refreshed is not None
        assert refreshed.status == "cancelled"

    audit_response = client.get(
        "/api/runtime/audit-logs",
        headers=_operator_headers("acct-task-manual-add-pause-next"),
        params={
            "account_id": "acct-task-manual-add-pause-next",
            "target_type": "member_task_day_quota",
            "target_id": next_quota_id,
        },
    )
    assert audit_response.status_code == 200, audit_response.text
    items = audit_response.json()
    matching = [item for item in items if item["action"] == "member_task_day_quota_cancelled_from_monitor"]
    assert len(matching) == 1
    assert matching[0]["payload"]["package_id"] == seeded["package_id"]
    assert matching[0]["payload"]["reason"] == "manual_pause_next_batch_from_monitor"
    assert matching[0]["payload"]["day_no"] == 2


def test_task_member_instance_pause_next_batch_action_returns_409_without_pending_quota(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory, suffix="-pause-next-missing")

    with db_session_factory() as session:
        package = session.get(TaskPackageInstance, seeded["package_id"])
        assert package is not None
        batch = session.get(MemberTaskBatch, package.batch_id)
        assert batch is not None
        batch.plan_id = "plan-next-missing"
        session.add(batch)
        session.commit()

    response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/pause-next-batch",
        headers=_operator_headers("acct-task-manual-add-pause-next-missing"),
        json={"reason": "manual_pause_next_batch_from_monitor"},
    )
    assert response.status_code == 409, response.text
    assert "No next pending quota is available to pause." in response.text


def test_task_member_instance_documented_alias_routes_remain_available(
    client: TestClient,
    db_session_factory,
) -> None:
    seeded = _seed_manual_add_scope(db_session_factory, suffix="-aliases")
    headers = _operator_headers("acct-task-manual-add-aliases")

    detail_response = client.get(
        f"/api/tasks/member-instances/{seeded['package_id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["id"] == seeded["package_id"]
    assert detail_payload["dayPlannedAmount"] == 50.0
    assert detail_payload["daySystemGeneratedAmount"] == 50.0
    assert detail_payload["dayManualAddedAmount"] == 0.0
    assert detail_payload["dayEffectiveAmount"] == 50.0

    available_response = client.get(
        f"/api/tasks/member-instances/{seeded['package_id']}/available-add-items",
        headers=headers,
    )
    assert available_response.status_code == 200, available_response.text
    assert [item["productId"] for item in available_response.json()] == [
        "manual-product-3-aliases",
        "manual-product-4-aliases",
    ]

    preview_response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/preview-add-items",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"]],
            "reason_text": "preview-alias",
        },
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_payload = preview_response.json()
    assert preview_payload["addedItemCount"] == 1
    assert preview_payload["packagePlannedAmount"] == 50.0
    assert preview_payload["packageSystemGeneratedAmount"] == 50.0
    assert preview_payload["rewardRatio"] == 0.1

    add_response = client.post(
        f"/api/tasks/member-instances/{seeded['package_id']}/add-items",
        headers=headers,
        json={
            "pool_item_ids": [seeded["pool_item_3_id"]],
            "reason_text": "add-alias",
        },
    )
    assert add_response.status_code == 200, add_response.text
    assert add_response.json()["addedItemCount"] == 1

    logs_response = client.get(
        f"/api/tasks/member-instances/{seeded['package_id']}/manual-add-logs",
        headers=headers,
    )
    assert logs_response.status_code == 200, logs_response.text
    payload = logs_response.json()
    assert len(payload) == 1
    assert payload[0]["packageId"] == seeded["package_id"]

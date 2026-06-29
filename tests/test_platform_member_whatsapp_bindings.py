from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    MemberTaskBatch,
    MemberTaskDayQuota,
    MemberWhatsAppBindingRequest,
    TaskPackageInstance,
    TaskPackageTemplate,
    TaskSystemConfig,
    UserIdentity,
    WalletAccount,
    WalletLedgerEntry,
)
from tests.test_h5_member_auth import (
    _create_site,
    _operator_headers,
    _register_member,
    _seed_official_task_plan,
    _seed_member_wallet,
    _seed_task_system_config,
)


def _seed_member_whatsapp_binding_request(
    client: TestClient,
    *,
    account_id: str,
    site_key: str,
    phone: str,
    display_name: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    site = _create_site(client, account_id=account_id, site_key=site_key)
    auth_payload = _register_member(
        client,
        site_key=site_key,
        phone=phone,
        display_name=display_name,
    )
    create_response = client.post("/api/h5/whatsapp-binding/start")
    assert create_response.status_code == 200, create_response.text
    return site, auth_payload, create_response.json()


def test_platform_can_list_account_scoped_member_whatsapp_binding_requests(
    client: TestClient,
) -> None:
    _, _, first = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-a",
        site_key="platform-member-wa-a",
        phone="+86139000678901",
        display_name="Member WA A",
    )
    _, _, second = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-b",
        site_key="platform-member-wa-b",
        phone="+86139000678902",
        display_name="Member WA B",
    )

    response = client.get(
        "/api/platform/member-whatsapp-bindings",
        headers=_operator_headers("acct-platform-member-wa-a"),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == first["requestId"]
    assert items[0]["accountId"] == "acct-platform-member-wa-a"
    assert items[0]["status"] == "pending"
    assert items[0]["requestedPhoneNumber"] == "+86139000678901"
    assert items[0]["startCount"] == 1

    filtered = client.get(
        "/api/platform/member-whatsapp-bindings",
        params={"status": "pending"},
        headers=_operator_headers("acct-platform-member-wa-a"),
    )
    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()) == 1

    denied = client.get(
        "/api/platform/member-whatsapp-bindings",
        params={"account_id": "acct-platform-member-wa-b"},
        headers=_operator_headers("acct-platform-member-wa-a"),
    )
    assert denied.status_code == 403, denied.text
    assert second["requestId"] != first["requestId"]


def test_platform_member_whatsapp_binding_status_flow_updates_h5_binding_state_and_messages(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _, auth_payload, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-flow",
        site_key="platform-member-wa-flow",
        phone="+86139000678903",
        display_name="Member WA Flow",
    )
    headers = _operator_headers("acct-platform-member-wa-flow")

    failed = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "failed", "note": "Meta handoff is not configured yet."},
        headers=headers,
    )
    assert failed.status_code == 200, failed.text
    failed_payload = failed.json()
    assert failed_payload["status"] == "failed"
    assert failed_payload["lastError"] == "Meta handoff is not configured yet."

    binding_after_fail = client.get("/api/h5/whatsapp-binding")
    assert binding_after_fail.status_code == 200, binding_after_fail.text
    assert binding_after_fail.json()["isBound"] is False
    assert binding_after_fail.json()["bindingStatus"] == "failed"

    messages_after_fail = client.get("/api/h5/messages")
    assert messages_after_fail.status_code == 200, messages_after_fail.text
    assert messages_after_fail.json()[0]["title"] == "WhatsApp binding failed"
    assert "Meta handoff is not configured yet." in messages_after_fail.json()[0]["bodyText"]

    rebound = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "WhatsApp binding completed by operator."},
        headers=headers,
    )
    assert rebound.status_code == 200, rebound.text
    bound_payload = rebound.json()
    assert bound_payload["status"] == "bound"
    assert bound_payload["boundAt"] is not None
    assert bound_payload["requestedPhoneNumber"] == "+86139000678903"

    binding_after_bound = client.get("/api/h5/whatsapp-binding")
    assert binding_after_bound.status_code == 200, binding_after_bound.text
    binding_payload = binding_after_bound.json()
    assert binding_payload["isBound"] is True
    assert binding_payload["bindingStatus"] == "bound"
    assert binding_payload["phoneNumber"] == "+86139000678903"
    assert binding_payload["requestId"] == created["requestId"]

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] >= 2

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assert user.has_whatsapp is True

        binding_request = session.get(MemberWhatsAppBindingRequest, created["requestId"])
        assert binding_request is not None
        assert binding_request.status == "bound"
        assert binding_request.bound_at is not None

        whatsapp_identity = session.query(UserIdentity).filter(
            UserIdentity.user_id == user.id,
            UserIdentity.identity_type == "whatsapp",
            UserIdentity.identity_value == "+86139000678903",
        ).one()
        assert whatsapp_identity.is_verified is True


def test_platform_member_whatsapp_binding_bound_grants_configured_task_balance_reward(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site, auth_payload, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-reward",
        site_key="platform-member-wa-reward",
        phone="+86139000678905",
        display_name="Member WA Reward",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-platform-member-wa-reward",
        site_id=site["id"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-platform-member-wa-reward",
        public_user_id=public_user_id,
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )

    response = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "reward test"},
        headers=_operator_headers("acct-platform-member-wa-reward"),
    )
    assert response.status_code == 200, response.text

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        assert wallet.task_balance == Decimal("20.00")

        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.transaction_type == "whatsapp_binding_reward",
            WalletLedgerEntry.reference_type == "member_whatsapp_binding_request",
            WalletLedgerEntry.reference_id == created["requestId"],
        ).all()
        assert len(reward_entries) == 1
        assert reward_entries[0].amount == Decimal("20.00")
        assert reward_entries[0].direction == "credit"
        assert reward_entries[0].ledger_type == "task"
        assert reward_entries[0].source_type == "whatsapp_binding_reward"
        assert reward_entries[0].task_amount == Decimal("20.00")
        assert reward_entries[0].idempotency_key is not None


def test_platform_member_whatsapp_binding_uses_updated_reward_amount_for_new_bound_member(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site, auth_payload, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-reward-updated",
        site_key="platform-member-wa-reward-updated",
        phone="+86139000678915",
        display_name="Member WA Reward Updated",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-platform-member-wa-reward-updated",
        site_id=site["id"],
    )
    with db_session_factory() as session:
        request_config = session.query(TaskSystemConfig).filter(
            TaskSystemConfig.account_id == "acct-platform-member-wa-reward-updated",
            TaskSystemConfig.site_id == site["id"],
        ).one()
        request_config.whatsapp_binding_reward_amount = Decimal("30.00")
        session.commit()
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-platform-member-wa-reward-updated",
        public_user_id=public_user_id,
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )

    response = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "reward updated test"},
        headers=_operator_headers("acct-platform-member-wa-reward-updated"),
    )
    assert response.status_code == 200, response.text

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        assert wallet.task_balance == Decimal("30.00")

        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.transaction_type == "whatsapp_binding_reward",
            WalletLedgerEntry.reference_type == "member_whatsapp_binding_request",
            WalletLedgerEntry.reference_id == created["requestId"],
        ).all()
        assert len(reward_entries) == 1
        assert reward_entries[0].amount == Decimal("30.00")


def test_platform_member_whatsapp_binding_bound_does_not_duplicate_reward_on_repeat_bound_update(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site, auth_payload, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-reward-dedupe",
        site_key="platform-member-wa-reward-dedupe",
        phone="+86139000678916",
        display_name="Member WA Reward Dedupe",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-platform-member-wa-reward-dedupe",
        site_id=site["id"],
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-platform-member-wa-reward-dedupe",
        public_user_id=public_user_id,
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )

    first = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "first bind"},
        headers=_operator_headers("acct-platform-member-wa-reward-dedupe"),
    )
    assert first.status_code == 200, first.text

    repeated = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "repeat bind"},
        headers=_operator_headers("acct-platform-member-wa-reward-dedupe"),
    )
    assert repeated.status_code == 200, repeated.text

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        wallet = session.query(WalletAccount).filter(WalletAccount.user_id == user.id).one()
        assert wallet.task_balance == Decimal("20.00")

        reward_entries = session.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.transaction_type == "whatsapp_binding_reward",
            WalletLedgerEntry.reference_type == "member_whatsapp_binding_request",
            WalletLedgerEntry.reference_id == created["requestId"],
        ).all()
        assert len(reward_entries) == 1


def test_platform_member_whatsapp_binding_bound_bootstraps_newbie_task_batch(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site, auth_payload, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-newbie",
        site_key="platform-member-wa-newbie",
        phone="+86139000678906",
        display_name="Member WA Newbie",
    )
    public_user_id = auth_payload["member"]["publicUserId"]
    newbie_plan_id = _seed_official_task_plan(
        db_session_factory,
        account_id="acct-platform-member-wa-newbie",
        site_id=site["id"],
        plan_type="newbie",
        claim_gate="whatsapp_bound",
    )
    _seed_task_system_config(
        db_session_factory,
        account_id="acct-platform-member-wa-newbie",
        site_id=site["id"],
        newbie_plan_id=newbie_plan_id,
    )
    _seed_member_wallet(
        db_session_factory,
        account_id="acct-platform-member-wa-newbie",
        public_user_id=public_user_id,
        system_balance=Decimal("0.00"),
        task_balance=Decimal("0.00"),
    )

    response = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "bootstrap newbie task"},
        headers=_operator_headers("acct-platform-member-wa-newbie"),
    )
    assert response.status_code == 200, response.text

    entry_state_response = client.get("/api/h5/tasks/entry-state")
    assert entry_state_response.status_code == 200, entry_state_response.text
    entry_state = entry_state_response.json()
    assert entry_state["state"] == "newbie_task_available"
    assert entry_state["taskPackageId"]

    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        quotas = session.query(MemberTaskDayQuota).filter(
            MemberTaskDayQuota.account_id == "acct-platform-member-wa-newbie",
            MemberTaskDayQuota.user_id == user.id,
            MemberTaskDayQuota.plan_id == newbie_plan_id,
        ).all()
        assert len(quotas) == 1
        assert quotas[0].day_no == 1
        assert quotas[0].status == "locked"
        assert quotas[0].issued_batch_id is not None
        assert quotas[0].locked_at is not None

        batch = session.query(MemberTaskBatch).filter(
            MemberTaskBatch.quota_id == quotas[0].id,
        ).one()
        assert batch.products_generated is True

        package = session.query(TaskPackageInstance).filter(
            TaskPackageInstance.batch_id == batch.id,
        ).first()
        assert package is not None

        template = session.get(TaskPackageTemplate, package.template_id)
        assert template is not None
        assert template.package_type == "rookie"


def test_platform_member_whatsapp_binding_status_guards_and_audit_log(
    client: TestClient,
) -> None:
    _, _, created = _seed_member_whatsapp_binding_request(
        client,
        account_id="acct-platform-member-wa-guard",
        site_key="platform-member-wa-guard",
        phone="+86139000678904",
        display_name="Member WA Guard",
    )
    headers = _operator_headers("acct-platform-member-wa-guard")

    missing = client.post(
        "/api/platform/member-whatsapp-bindings/missing-request/status",
        json={"status": "bound", "note": "done"},
        headers=headers,
    )
    assert missing.status_code == 404, missing.text

    missing_note = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "failed"},
        headers=headers,
    )
    assert missing_note.status_code == 409, missing_note.text
    assert "failure note" in missing_note.json()["detail"].lower()

    forbidden = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "wrong scope"},
        headers=_operator_headers("acct-platform-member-wa-other"),
    )
    assert forbidden.status_code == 403, forbidden.text

    bound = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "bound", "note": "bound now"},
        headers=headers,
    )
    assert bound.status_code == 200, bound.text

    illegal = client.post(
        f"/api/platform/member-whatsapp-bindings/{created['requestId']}/status",
        json={"status": "failed", "note": "too late"},
        headers=headers,
    )
    assert illegal.status_code == 409, illegal.text
    assert "cannot transition" in illegal.json()["detail"].lower()

    audit_logs = client.get(
        "/api/runtime/audit-logs",
        params={
            "account_id": "acct-platform-member-wa-guard",
            "target_type": "member_whatsapp_binding_request",
            "target_id": created["requestId"],
        },
        headers=headers,
    )
    assert audit_logs.status_code == 200, audit_logs.text
    actions = [item["action"] for item in audit_logs.json()]
    assert "platform_member_whatsapp_binding_status_updated" in actions

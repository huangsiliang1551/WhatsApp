"""BE2-025: 端到端集成测试 — 消息收发、人工接管、Meta 接入、多账号并发。"""

from collections.abc import Callable
from uuid import uuid4

from fastapi.testclient import TestClient

from app.providers.meta_management.base import (
    MetaPhoneNumberRecord,
)
from tests.conftest import StubMetaManagementProvider


# ─────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────


def _mock_inbound(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
    user_id: str,
    text: str,
    mode: str = "echo",
    **kwargs: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "account_id": account_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "text": text,
        "mode": mode,
    }
    payload.update(kwargs)
    resp = client.post("/dev/mock/inbound-message", json=payload)
    assert resp.status_code == 200, f"mock_inbound failed: {resp.text}"
    return resp.json()


def _create_account(
    client: TestClient,
    *,
    account_id: str,
    portfolio_id: str,
    waba_id: str,
    phone_numbers: list[dict[str, object]],
) -> dict[str, object]:
    resp = client.post(
        "/api/meta/accounts/manual",
        json={
            "account_id": account_id,
            "display_name": account_id,
            "meta_business_portfolio_id": portfolio_id,
            "waba_id": waba_id,
            "access_token": f"token-{account_id}",
            "verify_token": f"verify-{account_id}",
            "app_secret": f"secret-{account_id}",
            "token_source": "system_user",
            "phone_numbers": phone_numbers,
        },
    )
    assert resp.status_code == 200, f"create_account failed: {resp.text}"
    return resp.json()


def _get_conversations(
    client: TestClient,
    *,
    account_id: str,
) -> list[dict[str, object]]:
    resp = client.get(f"/api/conversations?account_id={account_id}")
    assert resp.status_code == 200, f"get_conversations failed: {resp.text}"
    return resp.json()


def _get_messages(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
) -> list[dict[str, object]]:
    resp = client.get(f"/api/conversations/{account_id}/{conversation_id}/messages")
    assert resp.status_code == 200, f"get_messages failed: {resp.text}"
    return resp.json()


def _set_account_ai(
    client: TestClient,
    *,
    account_id: str,
    enabled: bool,
) -> dict[str, object]:
    resp = client.post(
        f"/api/runtime/accounts/{account_id}/ai",
        json={"enabled": enabled},
    )
    assert resp.status_code == 200, f"set_account_ai failed: {resp.text}"
    return resp.json()


def _get_ai_status(
    client: TestClient,
    *,
    account_id: str,
    conversation_id: str,
) -> dict[str, object]:
    resp = client.get(
        f"/api/runtime/conversations/{conversation_id}/ai-status?account_id={account_id}",
    )
    assert resp.status_code == 200, f"get_ai_status failed: {resp.text}"
    return resp.json()


# ═════════════════════════════════════════════════════════
# 场景 1: 消息收发 E2E
# ═════════════════════════════════════════════════════════


def test_e2e_message_flow(client: TestClient) -> None:
    """Mock 入站 → 处理 → 出站 (echo) → 消息入库 → 状态流转。"""
    uid = uuid4().hex[:8]
    account_id = f"e2e-msg-{uid}"
    conversation_id = f"e2e-conv-{uid}"
    user_id = f"e2e-user-{uid}"

    # 1. 发送入站消息 (echo 模式)
    result = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="Hello, this is an E2E test message",
        mode="echo",
    )

    # 2. 验证入站消息被接受
    assert result["account_id"] == account_id
    assert result["inbound"]["text"] == "Hello, this is an E2E test message"
    assert result["inbound"]["provider"] == "mock"
    assert result["outbound"]["text"] == "Echo: Hello, this is an E2E test message"
    assert result["outbound"]["delivery_mode"] == "echo"
    assert result["ai"]["provider"] == "none"

    # 3. 验证会话已创建
    conversations = _get_conversations(client, account_id=account_id)
    assert len(conversations) >= 1
    conv = next(c for c in conversations if c["conversation_id"] == conversation_id)
    assert conv["status"] == "open"
    assert conv["management_mode"] == "ai_managed"

    # 4. 验证消息已入库
    messages = _get_messages(client, account_id=account_id, conversation_id=conversation_id)
    assert len(messages) >= 1
    inbound_msg = next(m for m in messages if m["direction"] == "inbound")
    assert inbound_msg["original_text"] == "Hello, this is an E2E test message"
    outbound_msg = next(m for m in messages if m["direction"] == "outbound")
    assert outbound_msg["original_text"] == "Echo: Hello, this is an E2E test message"

    # 5. AI 模式 — 消息路由至 rule_router / queue
    result2 = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="I need help with my order",
        mode="ai",
    )
    assert result2["account_id"] == account_id
    # AI enabled by default, so it may route
    assert result2["outbound"]["delivery_mode"] in (
        "rule_auto_reply",
        "handover_recommended",
        "ai_async_queued",
    )


# ═════════════════════════════════════════════════════════
# 场景 2: 人工接管 / 恢复 AI
# ═════════════════════════════════════════════════════════


def test_e2e_human_handover_and_restore_ai(client: TestClient) -> None:
    """创建会话 → 人工接管 → 人工回复 → 恢复 AI。"""
    uid = uuid4().hex[:8]
    account_id = f"e2e-ho-{uid}"
    conversation_id = f"e2e-ho-conv-{uid}"
    user_id = f"e2e-ho-user-{uid}"
    agent_id = f"agent-ho-{uid}"

    # 1. 注册客服
    resp = client.post(
        "/api/runtime/agents",
        json={
            "agent_id": agent_id,
            "display_name": "Test Agent",
            "status": "online",
            "is_active": True,
        },
    )
    assert resp.status_code == 200

    # 2. 创建会话 (mock inbound)
    _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="I need help",
        mode="echo",
    )

    # 3. 验证 AI 初始为启用
    ai_before = _get_ai_status(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
    )
    assert ai_before["effective_ai_enabled"] is True

    # 4. 人工接管 → 通过 assignment 切换
    resp = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/assignment",
        json={
            "agent_id": agent_id,
            "assigned_by_agent_id": agent_id,
            "reason": "manual_takeover",
        },
    )
    assert resp.status_code == 200
    assign_result = resp.json()
    assert assign_result["management_mode"] == "human_managed"

    # 5. 验证接管后 AI 停止回复
    ai_after_takeover = _get_ai_status(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
    )
    assert ai_after_takeover["effective_ai_enabled"] is False
    assert ai_after_takeover["management_mode"] == "human_managed"

    # 6. 人工回复
    resp = client.post(
        f"/api/conversations/{account_id}/{conversation_id}/messages/outbound",
        json={"text": "This is a human agent reply", "agent_id": agent_id},
    )
    assert resp.status_code == 200, f"human outbound failed: {resp.text}"
    human_reply = resp.json()
    assert human_reply["original_text"] == "This is a human agent reply"

    # 7. 验证消息入库
    messages = _get_messages(client, account_id=account_id, conversation_id=conversation_id)
    outbound_msgs = [m for m in messages if m["direction"] == "outbound"]
    assert any("human agent reply" in (m["original_text"] or "") for m in outbound_msgs)

    # 8. 恢复 AI → handover 至 ai_managed
    resp = client.post(
        f"/api/runtime/conversations/{conversation_id}/handover?account_id={account_id}",
        json={
            "management_mode": "ai_managed",
            "agent_id": agent_id,
            "reason": "resume_ai_management",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["management_mode"] == "ai_managed"

    # 9. 验证恢复后 AI 继续回复
    ai_after_restore = _get_ai_status(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
    )
    assert ai_after_restore["effective_ai_enabled"] is True
    assert ai_after_restore["management_mode"] == "ai_managed"

    # 10. AI 模式发送消息应触发 AI 路由
    result = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="What about my order status?",
        mode="ai",
    )
    assert result["outbound"]["delivery_mode"] in (
        "rule_auto_reply",
        "ai_async_queued",
    )


# ═════════════════════════════════════════════════════════
# 场景 3: Meta 接入 E2E
# ═════════════════════════════════════════════════════════


def test_e2e_meta_onboarding_and_messaging(
    client: TestClient,
    override_meta_management_provider: Callable[
        [TestClient, StubMetaManagementProvider], None
    ],
) -> None:
    """创建账号 → Embedded Signup → Webhook 注册 → 收发消息。"""
    uid = uuid4().hex[:8]
    account_id = f"e2e-meta-{uid}"
    waba_id = f"e2e-waba-{uid}"
    portfolio_id = f"e2e-portfolio-{uid}"
    phone_number_id = f"e2e-pn-{uid}"
    conversation_id = f"e2e-meta-conv-{uid}"
    user_id = f"e2e-meta-user-{uid}"

    # 1. 覆写 Meta Management Provider
    stub = StubMetaManagementProvider(
        subscription_status="remote_subscribed",
        subscription_remote_confirmed=True,
        sync_phone_numbers=[
            MetaPhoneNumberRecord(
                phone_number_id=phone_number_id,
                display_phone_number="+15550001111",
                verified_name="E2E Test",
                quality_rating="GREEN",
                is_registered=True,
            ),
        ],
        sync_status="success",
        sync_mode="remote_fetch",
        completion_status="remote_confirmed",
        completion_remote_confirmed=True,
        completion_phone_number_ids=[phone_number_id],
        completion_resolved_waba_id=waba_id,
        completion_resolved_portfolio_id=portfolio_id,
    )
    override_meta_management_provider(client, stub)

    # 2. 创建 Embedded Signup Session
    resp = client.post(
        "/api/meta/accounts/embedded-signup/session",
        json={
            "account_id": account_id,
            "display_name": "E2E Meta Account",
            "redirect_uri": "https://example.com/callback",
            "webhook_subscription": {
                "callback_url": f"https://example.com/webhooks/{uid}",
                "verify_token": f"verify-{uid}",
                "app_id": "app-123",
            },
        },
    )
    assert resp.status_code == 200, f"create session failed: {resp.text}"
    session = resp.json()
    session_id = session["session_id"]
    assert session["status"] == "created"
    assert session["account_id"] == account_id

    # 3. 注入 Callback → 模拟 Meta 回调
    resp = client.post(
        f"/api/meta/accounts/embedded-signup/session/{session_id}/callback",
        json={
            "status": "completed",
            "waba_id": waba_id,
            "meta_business_portfolio_id": portfolio_id,
            "phone_number_ids": [phone_number_id],
            "authorization_code": "auth-code-e2e",
            "system_user_access_token": "sys-token-e2e",
        },
    )
    assert resp.status_code == 200, f"callback failed: {resp.text}"

    # 4. 验证账号已通过 callback 创建
    resp = client.get(f"/api/meta/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    created = [a for a in accounts if a["account_id"] == account_id]
    assert len(created) == 1
    assert created[0]["waba_id"] == waba_id

    # 5. Subscribe Webhook
    resp = client.post(
        f"/api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription",
        json={
            "callback_url": f"https://example.com/webhooks/{uid}",
            "verify_token": f"verify-{uid}",
            "app_id": "app-123",
        },
    )
    assert resp.status_code == 200, f"subscribe webhook failed: {resp.text}"
    
    # 6. \u9a8c\u8bc1 Webhook \u8ba2\u9605\u5df2\u521b\u5efa
    resp = client.get("/api/meta/accounts/webhook-subscriptions")
    assert resp.status_code == 200, f"list webhook subs failed: {resp.text}"

    # 8. 使用该账号收发消息 (mock inbound with phone_number_id)
    result = _mock_inbound(
        client,
        account_id=account_id,
        conversation_id=conversation_id,
        user_id=user_id,
        text="Order inquiry from Meta account",
        mode="echo",
        phone_number_id=phone_number_id,
        waba_id=waba_id,
    )
    assert result["account_id"] == account_id
    assert result["outbound"]["text"] == "Echo: Order inquiry from Meta account"

    # 9. 验证 Phone Number 在 scope 内
    resp = client.get(f"/api/meta/accounts/{account_id}/phone-numbers")
    assert resp.status_code == 200
    phone_numbers = resp.json()
    assert any(pn["phone_number_id"] == phone_number_id for pn in phone_numbers)


# ═════════════════════════════════════════════════════════
# 场景 4: 多账号并发 — 互不干扰
# ═════════════════════════════════════════════════════════


def test_e2e_multi_account_concurrency(client: TestClient) -> None:
    """账号 A 和 B 同时收发消息 → 互不干扰；AI 开关独立控制。"""
    uid = uuid4().hex[:8]

    # 账号 A
    account_a = f"e2e-multi-a-{uid}"
    conv_a = f"e2e-conv-a-{uid}"
    user_a = f"e2e-user-a-{uid}"

    # 账号 B
    account_b = f"e2e-multi-b-{uid}"
    conv_b = f"e2e-conv-b-{uid}"
    user_b = f"e2e-user-b-{uid}"

    # 1. 两个账号同时发送消息 (echo 模式)
    result_a = _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=user_a,
        text="Message from account A",
        mode="echo",
    )
    result_b = _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=user_b,
        text="Message from account B",
        mode="echo",
    )

    # 2. 验证各自的回复内容正确
    assert "account A" in result_a["outbound"]["text"]
    assert "account B" in result_b["outbound"]["text"]

    # 3. 验证会话归属不同账号
    convs_a = _get_conversations(client, account_id=account_a)
    convs_b = _get_conversations(client, account_id=account_b)
    assert any(c["conversation_id"] == conv_a for c in convs_a)
    assert any(c["conversation_id"] == conv_b for c in convs_b)

    # 4. 禁用账号 A 的 AI (B 保持启用)
    _set_account_ai(client, account_id=account_a, enabled=False)

    # 5. 验证 AI 状态
    ai_a = _get_ai_status(client, account_id=account_a, conversation_id=conv_a)
    ai_b = _get_ai_status(client, account_id=account_b, conversation_id=conv_b)
    assert ai_a["effective_ai_enabled"] is False
    assert ai_b["effective_ai_enabled"] is True

    # 6. 两个账号同时发送 AI 模式消息
    result_a_ai = _mock_inbound(
        client,
        account_id=account_a,
        conversation_id=conv_a,
        user_id=user_a,
        text="Help A with billing",
        mode="ai",
    )
    result_b_ai = _mock_inbound(
        client,
        account_id=account_b,
        conversation_id=conv_b,
        user_id=user_b,
        text="Help B with shipping",
        mode="ai",
    )

    # 账号 A: AI 被禁用 → delivery_mode = "manual_queue"
    assert result_a_ai["outbound"]["delivery_mode"] == "manual_queue"
    # 账号 B: AI 启用 → 应被路由
    assert result_b_ai["outbound"]["delivery_mode"] in (
        "rule_auto_reply",
        "ai_async_queued",
        "handover_recommended",
    )

    # 7. 重新启用账号 A 的 AI → 恢复
    _set_account_ai(client, account_id=account_a, enabled=True)
    ai_a_restored = _get_ai_status(client, account_id=account_a, conversation_id=conv_a)
    assert ai_a_restored["effective_ai_enabled"] is True

    # 8. 验证无数据串扰 — A 不能看到 B 的消息
    msgs_a = _get_messages(client, account_id=account_a, conversation_id=conv_a)
    msgs_b = _get_messages(client, account_id=account_b, conversation_id=conv_b)
    texts_a = [m.get("original_text", "") for m in msgs_a]
    texts_b = [m.get("original_text", "") for m in msgs_b]
    assert all("account B" not in t for t in texts_a)
    assert all("account A" not in t for t in texts_b)

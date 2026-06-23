# 端到端验证第二轮（E2E-004 ~ E2E-006）+ Bug 修复（BUG-001 ~ BUG-003）

> **执行角色**: testing_agent（验证）+ api_agent（Bug 修复）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 验证会话/工单/充值提现端到端流程 + 修复上轮发现的 Bug

---

## Part A：Bug 修复（优先执行）

### BUG-001：邀请同 IP 防刷逻辑缺陷

- **严重度**: P1
- **估计耗时**: 20 分钟
- **发现位置**: E2E-003 Step 7

#### 问题描述

`invite_service.py` 的 `_validate_invite` 方法中，同 IP 防刷检查逻辑有两个问题：
1. `InviteRecord` 模型没有存储 `invitee_ip` 和 `invitee_device_id` 字段
2. 防刷验证即使检测到重复也没有抛出异常

#### 修复方案

**Step 1: 检查 InviteRecord 模型**

```bash
# 检查 InviteRecord 是否有 invitee_ip 和 invitee_device_id 列
docker exec whatsapp_app python -c "from app.db.models import InviteRecord; print([c.name for c in InviteRecord.__table__.columns])"
```

如果没有这两个字段，需要新增迁移：

```python
# alembic/versions/20260616_0073_invite_anti_fraud_fields.py

def upgrade():
    op.add_column("invite_records", sa.Column("invitee_ip", sa.String(45), nullable=True))
    op.add_column("invite_records", sa.Column("invitee_device_id", sa.String(128), nullable=True))
    op.create_index("ix_invite_records_invitee_ip", "invite_records", ["invitee_ip"])
    op.create_index("ix_invite_records_invitee_device_id", "invite_records", ["invitee_device_id"])
```

**Step 2: 修复 invite_service.py**

在 `on_register_callback` 方法中：
1. 创建 `InviteRecord` 时存储 `invitee_ip` 和 `invitee_device_id`
2. 在 `_validate_invite` 中，检测到同 IP/设备重复时正确抛出 `AntiFraudError`

```python
# 在 on_register_callback 中创建记录时：
record = InviteRecord(
    ...
    invitee_ip=invitee_ip,
    invitee_device_id=invitee_device_id,
)

# 在 _validate_invite 中修复防刷检查：
def _validate_invite(self, inviter_id, invitee_ip, invitee_device_id):
    # 同 IP 限制
    ip_count = self._session.scalar(
        select(func.count(InviteRecord.id)).where(
            InviteRecord.inviter_user_id == inviter_id,
            InviteRecord.invitee_ip == invitee_ip,
        )
    ) or 0
    if ip_count >= config.same_ip_limit:
        raise AntiFraudError(f"Same IP limit ({config.same_ip_limit}) exceeded")

    # 同设备限制
    device_count = self._session.scalar(
        select(func.count(InviteRecord.id)).where(
            InviteRecord.inviter_user_id == inviter_id,
            InviteRecord.invitee_device_id == invitee_device_id,
        )
    ) or 0
    if device_count >= config.same_device_limit:
        raise AntiFraudError(f"Same device limit ({config.same_device_limit}) exceeded")
```

**Step 3: 重启 Docker 容器使修复生效**

```bash
docker compose restart app
# 等待 20 秒
```

**Step 4: 重新验证 E2E-003 Step 7**

```powershell
# 设置 same_ip_limit = 2
Invoke-WebRequest -Uri "http://localhost:8000/api/invites/config" -Method PUT -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"; "Content-Type"="application/json"} -Body '{"register_reward":2,"recharge_trigger_amount":30,"recharge_reward":3,"max_invitees":5,"same_ip_limit":2,"same_device_limit":1}' -UseBasicParsing

# 注册 2 个同 IP 好友（应成功）
# ... 注册第 1、2 个

# 注册第 3 个同 IP 好友（应返回 400）
try {
  Invoke-WebRequest -Uri "http://localhost:8000/api/invites/register-callback" -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"inviter_code":"xxx","invitee_user_id":"invitee-3","invitee_ip":"192.168.1.100","invitee_device_id":"device-3"}' -UseBasicParsing
} catch {
  $_.Exception.Response.StatusCode.value__  # 应为 400
}
```

**验证**: 第 3 个同 IP 注册返回 400。

---

## Part B：端到端验证（第二轮）

### E2E-004：会话完整流程

#### 目标

验证会话创建 → 消息发送 → AI 回复 → 人工接管 → 恢复 AI → 会话关闭。

#### 步骤

##### Step 1: 创建测试用户和获取账号

```bash
# 获取测试用户
curl "http://localhost:8000/api/platform/users?page=1&size=1" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
# 记录 user_id → TEST_USER_ID, public_user_id → PUBLIC_USER_ID

# 确认账号
# account_id = "acct-h5-daily-cn"
```

##### Step 2: 通过 Mock 创建入站消息（触发会话创建）

```bash
curl -X POST http://localhost:8000/dev/mock/inbound-message \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct-h5-daily-cn",
    "user_id": "PUBLIC_USER_ID",
    "text": "你好，我想查询订单状态",
    "mode": "ai"
  }'
```

**验证**: 返回 200 或 201。

##### Step 3: 查看会话列表

```bash
curl "http://localhost:8000/api/conversations?account_id=acct-h5-daily-cn&page=1&size=5" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，列表中包含刚创建的会话。记录 `conversation_id` → CONV_ID。

##### Step 4: 查看会话消息

```bash
curl "http://localhost:8000/api/conversations/acct-h5-daily-cn/CONV_ID/messages" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，包含入站消息"你好，我想查询订单状态"。如果 AI 已回复，还应包含 AI 回复消息。

##### Step 5: 发送人工回复

```bash
curl -X POST "http://localhost:8000/api/conversations/acct-h5-daily-cn/CONV_ID/messages/outbound" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"text": "您好，请提供您的订单号", "agent_id": "admin"}'
```

**验证**: 返回 200 或 201。

##### Step 6: 人工接管会话

```bash
curl -X POST "http://localhost:8000/api/runtime/conversations/CONV_ID/handover" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"account_id": "acct-h5-daily-cn", "management_mode": "human_managed", "agent_id": "admin"}'
```

**验证**: 返回 200，`management_mode` = "human_managed"。

##### Step 7: 验证会话状态变化

```bash
curl "http://localhost:8000/api/conversations?account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 会话 CONV_ID 的 `management_mode` = "human_managed"。

##### Step 8: 恢复 AI 托管

```bash
curl -X POST "http://localhost:8000/api/runtime/conversations/CONV_ID/handover" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"account_id": "acct-h5-daily-cn", "management_mode": "ai_managed", "agent_id": "admin"}'
```

**验证**: 返回 200，`management_mode` = "ai_managed"。

##### Step 9: 关闭会话

```bash
curl -X POST "http://localhost:8000/api/conversations/acct-h5-daily-cn/CONV_ID/close" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "admin"}'
```

**验证**: 返回 200，会话状态变为 "closed"。

##### Step 10: 清理（可选）

会话记录保留用于审计，无需清理。

---

### E2E-005：工单完整流程

#### 目标

验证工单创建 → 查看 → 状态变更 → 回复 → 关闭。

#### 步骤

##### Step 1: 创建工单

```bash
curl -X POST http://localhost:8000/api/tickets \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct-h5-daily-cn",
    "user_id": "TEST_USER_ID",
    "title": "E2E测试工单-订单问题",
    "description": "我的订单 MOCK-1001 迟迟未收到",
    "ticket_type": "complaint"
  }'
```

**验证**: 返回 201。记录 `ticket_id` → TICKET_ID。

##### Step 2: 查看工单列表

```bash
curl "http://localhost:8000/api/tickets?page=1&size=5" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，列表包含刚创建的工单。

##### Step 3: 查看工单详情

```bash
curl "http://localhost:8000/api/tickets/TICKET_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，title/description/status 匹配。

##### Step 4: 变更工单状态（处理中）

```bash
curl -X PATCH "http://localhost:8000/api/tickets/TICKET_ID/status" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

**验证**: 返回 200，status = "in_progress"。

##### Step 5: 回复工单

```bash
curl -X POST "http://localhost:8000/api/tickets/TICKET_ID/messages" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"content": "已查到您的订单，正在处理中", "sender_type": "agent"}'
```

**验证**: 返回 200 或 201。

##### Step 6: 关闭工单

```bash
curl -X PATCH "http://localhost:8000/api/tickets/TICKET_ID/status" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"status": "resolved"}'
```

**验证**: 返回 200，status = "resolved"。

##### Step 7: 验证最终状态

```bash
curl "http://localhost:8000/api/tickets/TICKET_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: status = "resolved"。

---

### E2E-006：充值提现完整流程

#### 目标

验证充值 → 余额增加 → 提现申请 → 审核 → 提现完成 → 余额减少。

#### 步骤

##### Step 1: 查看当前余额

```bash
curl "http://localhost:8000/api/h5/wallet?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

记录 `system_balance` → INITIAL_BALANCE。

##### Step 2: 充值

```bash
curl -X POST "http://localhost:8000/api/h5/wallet/recharges" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "TEST_USER_ID", "account_id": "acct-h5-daily-cn", "amount": 100.00}'
```

**验证**: 返回 200 或 201。

##### Step 3: 验证余额增加

```bash
curl "http://localhost:8000/api/h5/wallet?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: `system_balance` = INITIAL_BALANCE + 100.00。

##### Step 4: 查看交易记录

```bash
curl "http://localhost:8000/api/h5/wallet/transactions?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 包含 recharge 类型记录，amount = 100.00，direction = "credit"。

##### Step 5: 申请提现

```bash
curl -X POST "http://localhost:8000/api/h5/withdrawals" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "TEST_USER_ID", "account_id": "acct-h5-daily-cn", "amount": 50.00}'
```

**验证**: 返回 200 或 201。记录 `withdrawal_id` → WITHDRAWAL_ID。

##### Step 6: 查看提现列表

```bash
curl "http://localhost:8000/api/h5/withdrawals?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 包含刚创建的提现申请，status = "pending"。

##### Step 7: 审核提现（管理端）

```bash
curl -X PATCH "http://localhost:8000/api/platform/withdrawals/WITHDRAWAL_ID/status" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"status": "approved"}'
```

**验证**: 返回 200。

##### Step 8: 完成提现

```bash
curl -X PATCH "http://localhost:8000/api/platform/withdrawals/WITHDRAWAL_ID/status" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"status": "paid"}'
```

**验证**: 返回 200。

##### Step 9: 验证余额减少

```bash
curl "http://localhost:8000/api/h5/wallet?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: `system_balance` = INITIAL_BALANCE + 100.00 - 50.00 = INITIAL_BALANCE + 50.00。

##### Step 10: 验证交易记录

```bash
curl "http://localhost:8000/api/h5/wallet/transactions?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 包含 withdrawal 类型记录，amount = 50.00，direction = "debit"。

---

## 测试结果记录表

| 流程 | 步骤 | 预期结果 | 实际结果 | 通过 |
|------|------|---------|---------|------|
| BUG-001 | 修复+重验 | 同IP第3人返回400 | 第3个同IP注册返回400, reason="Same IP limit (2) exceeded" | ✅ |
| E2E-004 | Step 1-3 | 会话创建+消息 | Mock入站→会话创建(status=open, ai_managed)→AI自动回复 | ✅ |
| E2E-004 | Step 4-5 | 消息列表+回复 | 消息列表含入站+AI回复；handover后发送人工消息成功 | ✅ |
| E2E-004 | Step 6-8 | 接管+恢复AI | handover成功(human_managed)→恢复AI成功(ai_managed) | ✅ |
| E2E-004 | Step 9 | 关闭会话 | 会话成功关闭(status=closed) | ✅ |
| E2E-005 | Step 1-3 | 工单创建+详情 | 工单创建成功(cd8bf88c...), 列表+详情均显示open | ✅ |
| E2E-005 | Step 4-5 | 状态变更+回复 | status→in_progress, 回复(body_text)成功 | ✅ |
| E2E-005 | Step 6-7 | 关闭工单 | status→resolved, 验证最终状态=resolved | ✅ |
| E2E-006 | Step 1-3 | 充值+余额增加 | 余额0.0→充值100.0→余额100.0(USD) | ✅ |
| E2E-006 | Step 4-6 | 提现申请 | 交易记录显示recharge/credit/100.0；提现50.0创建成功(submitted) | ✅ |
| E2E-006 | Step 7-9 | 审核+完成+余额减少 | 管理端approved→paid, 余额100.0→50.0 | ✅ |
| E2E-006 | Step 10 | 交易记录 | 含recharge(credit=100.0)+withdraw_request(debit=50.0) | ✅ |

---

## 执行顺序

1. 先执行 BUG-001 修复（后端 Agent）
2. 重新验证 E2E-003 Step 7
3. 执行 E2E-004（会话流程）
4. 执行 E2E-005（工单流程）
5. 执行 E2E-006（充值提现）

---

## 发给测试 Agent 的文本

```
你是测试 Agent（端到端验证第二轮）。请读取 docs/task-plan-e2e-round2.md，按顺序执行：

1. BUG-001 修复 + 重新验证 E2E-003 Step 7（同 IP 防刷）
2. E2E-004：会话完整流程（10 步）
   - Mock 入站消息 → 会话创建 → 消息发送 → 人工接管 → 恢复 AI → 关闭
3. E2E-005：工单完整流程（7 步）
   - 创建工单 → 状态变更 → 回复 → 关闭
4. E2E-006：充值提现流程（10 步）
   - 充值 → 余额增加 → 提现 → 审核 → 完成 → 余额减少

注意：
- BUG-001 需要先修复后端代码（invite_service.py 存储 IP + 防刷抛异常），然后 docker compose restart app
- 使用 Invoke-WebRequest（PowerShell）
- 替换占位符为实际返回值
- 填写测试结果表

开始吧。
```

# 营销系统端到端流程验证（E2E-001 ~ E2E-003）

> **执行角色**: testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 验证营销系统 3 个核心业务流程的端到端闭环

---

## 前置条件

1. Docker 容器 `whatsapp_app` 和 `whatsapp_postgres` 正常运行
2. 数据库迁移已执行到最新版本（0072）
3. 使用测试账号 `acct-h5-daily-cn`（已存在于 accounts 表）
4. 所有 API 调用需要 Actor 头：`X-Actor-Id: admin` + `X-Actor-Role: super_admin`

### 通用请求头

```
X-Actor-Id: admin
X-Actor-Role: super_admin
Content-Type: application/json
```

### 测试账号 ID

```
account_id = "acct-h5-daily-cn"
```

---

## E2E-001：商品 → 商品包 → 任务规则 → 推送 → 完成

### 目标

验证完整的营销核心闭环：创建商品 → 组装商品包 → 创建推送规则 → 手动推送任务 → 执行商品任务 → 任务完成。

### 步骤

#### Step 1: 创建 3 个商品

```bash
# 商品 A: ¥50
curl -X POST http://localhost:8000/api/products \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"acct-h5-daily-cn","name":"E2E商品A","price":50.00,"tags":["e2e","test"]}'

# 记录返回的 id → PRODUCT_A_ID

# 商品 B: ¥30
curl -X POST http://localhost:8000/api/products \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"acct-h5-daily-cn","name":"E2E商品B","price":30.00,"tags":["e2e","test"]}'

# 记录返回的 id → PRODUCT_B_ID

# 商品 C: ¥25
curl -X POST http://localhost:8000/api/products \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"account_id":"acct-h5-daily-cn","name":"E2E商品C","price":25.00,"tags":["e2e","test"]}'

# 记录返回的 id → PRODUCT_C_ID
```

**验证**: 3 个请求均返回 201，记录各商品 ID。

#### Step 2: 验证商品列表

```bash
curl "http://localhost:8000/api/products?account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，列表中包含刚创建的 3 个商品（名称匹配 `E2E商品*`）。

#### Step 3: 创建商品包（手动指定商品）

```bash
curl -X POST http://localhost:8000/api/product-packages \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct-h5-daily-cn",
    "name": "E2E测试礼包",
    "target_amount": 99.00,
    "amount_tolerance_pct": 10,
    "product_count": 3,
    "product_ids": ["PRODUCT_A_ID", "PRODUCT_B_ID", "PRODUCT_C_ID"],
    "product_snapshot": [
      {"product_id": "PRODUCT_A_ID", "product_name": "E2E商品A", "price": 50.00, "quantity": 1},
      {"product_id": "PRODUCT_B_ID", "product_name": "E2E商品B", "price": 30.00, "quantity": 1},
      {"product_id": "PRODUCT_C_ID", "product_name": "E2E商品C", "price": 25.00, "quantity": 1}
    ],
    "total_value": 105.00,
    "completion_reward": 5.00
  }'

# 记录返回的 id → PACKAGE_ID
```

**验证**: 返回 201，total_value = 50+30+25 = 105.00（在 99±10% 即 89.1~108.9 范围内）。

#### Step 4: 测试自动配品预览

```bash
curl -X POST "http://localhost:8000/api/product-packages/assemble-preview?account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"target_amount": 99.00, "tolerance_pct": 10, "product_count": 3}'
```

**验证**: 返回 200，包含 `items` 数组和 `total_amount`，`within_range` = true。

#### Step 5: 创建任务规则（手动推送类型）

```bash
curl -X POST http://localhost:8000/api/task-rules \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct-h5-daily-cn",
    "name": "E2E测试推送规则",
    "rule_type": "package_push",
    "trigger_type": "manual",
    "trigger_config": {},
    "package_id": "PACKAGE_ID",
    "follow_up_chain": [],
    "expiry_config": {"reset_at": "00:00"},
    "is_enabled": true
  }'

# 记录返回的 id → RULE_ID
```

**验证**: 返回 201，rule_type = "package_push"，trigger_type = "manual"。

#### Step 6: 手动推送任务给测试用户

首先需要一个已存在的用户 ID。查询现有用户：

```bash
curl "http://localhost:8000/api/platform/users?page=1&size=5" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"

# 记录第一个用户的 id → TEST_USER_ID
```

然后手动推送：

```bash
curl -X POST http://localhost:8000/api/task-instances/manual-push \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct-h5-daily-cn",
    "rule_id": "RULE_ID",
    "user_ids": ["TEST_USER_ID"]
  }'
```

**验证**: 返回 200，`pushed_count` = 1，记录 `task_instance_ids[0]` → TASK_INSTANCE_ID。

#### Step 7: 查看任务实例

```bash
curl "http://localhost:8000/api/task-instances/TASK_INSTANCE_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，status = "pending" 或 "running"，task_type = "package"，package_id 匹配。

#### Step 8: 开始第一个商品任务（扣余额）

先确认用户余额：

```bash
curl "http://localhost:8000/api/h5/wallet?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

记录当前 `system_balance`。

然后开始第一个商品：

```bash
curl -X POST "http://localhost:8000/api/task-instances/TASK_INSTANCE_ID/start-product" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "PRODUCT_A_ID"}'
```

**验证**: 
- 如果余额 >= 50: 返回 200，product_progress 中 PRODUCT_A_ID 状态变为 "completed"，total_paid = 50.00
- 如果余额 < 50: 返回 402（InsufficientBalance），提示余额不足

如果余额不足，先充值再重试：

```bash
# 充值（使用 H5 充值接口或直接用 SQL 更新余额）
# 然后重试:
curl -X POST "http://localhost:8000/api/task-instances/TASK_INSTANCE_ID/retry-product" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "PRODUCT_A_ID"}'
```

#### Step 9: 完成剩余商品任务

对 PRODUCT_B_ID 和 PRODUCT_C_ID 重复 Step 8。

**验证**: 每个商品完成后 product_progress 更新，total_paid 累加。

#### Step 10: 验证任务完成

```bash
curl "http://localhost:8000/api/task-instances/TASK_INSTANCE_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 
- status = "completed"
- product_progress 中全部 3 个商品状态为 "completed"
- total_paid = 105.00（50+30+25）
- reward_amount = 5.00（完成奖励已发放到 task_balance）

#### Step 11: 验证统计变化

```bash
curl "http://localhost:8000/api/marketing/stats/packages?account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"

curl "http://localhost:8000/api/marketing/stats/tasks?account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 
- packages 统计中 E2E测试礼包 的 completion_count >= 1
- tasks 统计中 package_push 类型的 completed_count >= 1

#### Step 12: 清理测试数据

```bash
# 删除任务规则
curl -X DELETE "http://localhost:8000/api/task-rules/RULE_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"

# 删除商品包（可能被规则引用，先删规则）
curl -X DELETE "http://localhost:8000/api/product-packages/PACKAGE_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"

# 删除商品
curl -X DELETE "http://localhost:8000/api/products/PRODUCT_A_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
curl -X DELETE "http://localhost:8000/api/products/PRODUCT_B_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
curl -X DELETE "http://localhost:8000/api/products/PRODUCT_C_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 全部返回 204。

---

## E2E-002：签到完整流程

### 目标

验证签到配置 → 签到 → 连续天数累计 → 达到目标天数触发奖励 → 签到任务完成 → 再次签到被拒绝。

### 步骤

#### Step 1: 设置签到配置

```bash
# 设置连续 3 天（测试用短周期），奖励 ¥2.00
curl -X PUT http://localhost:8000/api/sign-in/config \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"consecutive_days": 3, "reward_amount": 2.00}'
```

**验证**: 返回 200，consecutive_days = 3，reward_amount = 2.00。

#### Step 2: 验证配置

```bash
curl "http://localhost:8000/api/sign-in/config" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，配置值匹配。

#### Step 3: 第 1 天签到

使用一个测试用户（复用 E2E-001 中的 TEST_USER_ID，或创建新用户）：

```bash
curl -X POST "http://localhost:8000/api/sign-in?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200：
- `consecutive_days` = 1
- `is_rewarded` = false
- `is_completed` = false

#### Step 4: 查看签到状态

```bash
curl "http://localhost:8000/api/sign-in/status?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，`today_signed_in` = true，`consecutive_days` = 1。

#### Step 5: 重复签到（同一天）

```bash
curl -X POST "http://localhost:8000/api/sign-in?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 409，detail 包含 "already signed in" 或类似消息。

#### Step 6: 模拟第 2 天签到

由于无法真正等待一天，直接操作数据库修改 `sign_date`：

```sql
-- 在 PostgreSQL 中执行：
UPDATE sign_in_records
SET sign_date = sign_date - INTERVAL '1 day'
WHERE user_id = 'TEST_USER_ID'
  AND account_id = 'acct-h5-daily-cn'
  AND sign_date = CURRENT_DATE;
```

然后再次签到：

```bash
curl -X POST "http://localhost:8000/api/sign-in?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200，`consecutive_days` = 2，`is_rewarded` = false。

#### Step 7: 模拟第 3 天签到（触发奖励）

再次修改日期并签到：

```sql
UPDATE sign_in_records
SET sign_date = sign_date - INTERVAL '1 day'
WHERE user_id = 'TEST_USER_ID'
  AND account_id = 'acct-h5-daily-cn';
```

```bash
curl -X POST "http://localhost:8000/api/sign-in?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200：
- `consecutive_days` = 3
- `is_rewarded` = true（达到 3 天目标）
- `is_completed` = true（签到任务完成）

#### Step 8: 验证奖励已发放到 task_balance

```bash
curl "http://localhost:8000/api/h5/wallet?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: `task_balance` 增加了 2.00（或检查 wallet_ledger_entries 中有 `ledger_type: sign_in_reward` 记录）。

#### Step 9: 签到任务完成后再次签到

```bash
curl -X POST "http://localhost:8000/api/sign-in?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 409，detail 包含 "sign-in task already completed" 或类似消息。

#### Step 10: 恢复签到配置

```bash
curl -X PUT http://localhost:8000/api/sign-in/config \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{"consecutive_days": 7, "reward_amount": 5.00}'
```

**验证**: 返回 200，恢复为正式配置。

#### Step 11: 清理测试数据

```sql
-- 清理签到记录
DELETE FROM sign_in_records WHERE user_id = 'TEST_USER_ID' AND account_id = 'acct-h5-daily-cn';
```

---

## E2E-003：邀请 → 注册 → 充值 → 奖励

### 目标

验证邀请链接生成 → 好友注册回调 → 注册奖励 → 好友充值 → 充值奖励 → 防刷限制。

### 步骤

#### Step 1: 设置邀请配置

```bash
curl -X PUT http://localhost:8000/api/invites/config \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "register_reward": 2.00,
    "recharge_trigger_amount": 30.00,
    "recharge_reward": 3.00,
    "max_invitees": 5,
    "same_ip_limit": 2,
    "same_device_limit": 1
  }'
```

**验证**: 返回 200，配置值匹配。

#### Step 2: 获取邀请链接

```bash
curl "http://localhost:8000/api/invites/my-link?user_id=TEST_USER_ID&account_id=acct-h5-daily-cn" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200：
- `invite_code` 不为空（如 `ABC123DEF`）
- `invite_url` 包含 invite_code
- 记录 `invite_code` → INVITE_CODE

#### Step 3: 模拟好友注册回调

创建一个模拟好友用户（或使用已有用户），然后触发注册回调：

```bash
# 假设好友用户 ID 为 INVITEE_USER_ID（需要先创建或获取）
curl -X POST http://localhost:8000/api/invites/register-callback \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "inviter_code": "INVITE_CODE",
    "invitee_user_id": "INVITEE_USER_ID",
    "invitee_ip": "192.168.1.100",
    "invitee_device_id": "device-invitee-001"
  }'
```

**验证**: 返回 200：
- `rewarded` = true
- `reward_amount` = "2.00"

#### Step 4: 查看邀请记录

```bash
curl "http://localhost:8000/api/invites/my-records?user_id=TEST_USER_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: 返回 200：
- `total` >= 1
- items 中包含 invitee_user_id = INVITEE_USER_ID，invite_type = "register"

#### Step 5: 模拟好友充值回调

```bash
curl -X POST http://localhost:8000/api/invites/recharge-callback \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "inviter_user_id": "TEST_USER_ID",
    "invitee_user_id": "INVITEE_USER_ID",
    "amount": 50.00,
    "invitee_ip": "192.168.1.100",
    "invitee_device_id": "device-invitee-001"
  }'
```

**验证**: 返回 200：
- `rewarded` = true（50 >= 30 触发阈值）
- `reward_amount` = "3.00"

#### Step 6: 验证充值奖励已发放

```bash
curl "http://localhost:8000/api/invites/my-records?user_id=TEST_USER_ID" \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin"
```

**验证**: items 中包含 invite_type = "recharge"，reward_amount = 3.00。

#### Step 7: 测试防刷 — 同 IP 限制

配置 same_ip_limit = 2，然后用同一 IP 注册第 3 个好友：

```bash
# 第 2 个好友（同 IP）
curl -X POST http://localhost:8000/api/invites/register-callback \
  -H "Content-Type: application/json" \
  -d '{
    "inviter_code": "INVITE_CODE",
    "invitee_user_id": "INVITEE_USER_ID_2",
    "invitee_ip": "192.168.1.100",
    "invitee_device_id": "device-invitee-002"
  }'

# 第 3 个好友（同 IP，应被拒绝）
curl -X POST http://localhost:8000/api/invites/register-callback \
  -H "Content-Type: application/json" \
  -d '{
    "inviter_code": "INVITE_CODE",
    "invitee_user_id": "INVITEE_USER_ID_3",
    "invitee_ip": "192.168.1.100",
    "invitee_device_id": "device-invitee-003"
  }'
```

**验证**: 
- 第 2 个好友：返回 200，rewarded = true
- 第 3 个好友：返回 400，detail 包含 "same IP limit" 或 "anti-fraud"

#### Step 8: 测试邀请上限

配置 max_invitees = 5，已邀请了 2 人。继续邀请到上限：

```bash
# 邀请第 3~5 个好友（不同 IP）
for i in 3,4,5; do
  curl -X POST http://localhost:8000/api/invites/register-callback \
    -H "Content-Type: application/json" \
    -d "{
      \"inviter_code\": \"INVITE_CODE\",
      \"invitee_user_id\": \"INVITEE_USER_ID_$i\",
      \"invitee_ip\": \"192.168.1.$((100+i))\",
      \"invitee_device_id\": \"device-invitee-00$i\"
    }"
done

# 第 6 个好友（超过上限，应被拒绝）
curl -X POST http://localhost:8000/api/invites/register-callback \
  -H "Content-Type: application/json" \
  -d '{
    "inviter_code": "INVITE_CODE",
    "invitee_user_id": "INVITEE_USER_ID_6",
    "invitee_ip": "192.168.1.200",
    "invitee_device_id": "device-invitee-006"
  }'
```

**验证**: 第 6 个返回 400，detail 包含 "invite limit" 或 "max invitees"。

#### Step 9: 恢复邀请配置

```bash
curl -X PUT http://localhost:8000/api/invites/config \
  -H "X-Actor-Id: admin" -H "X-Actor-Role: super_admin" \
  -H "Content-Type: application/json" \
  -d '{
    "register_reward": 2.00,
    "recharge_trigger_amount": 30.00,
    "recharge_reward": 3.00,
    "max_invitees": 20,
    "same_ip_limit": 3,
    "same_device_limit": 2
  }'
```

#### Step 10: 清理测试数据

```sql
DELETE FROM invite_records WHERE inviter_user_id = 'TEST_USER_ID';
DELETE FROM invite_links WHERE user_id = 'TEST_USER_ID';
```

---

## 测试结果记录表

| 流程 | 步骤 | 预期结果 | 实际结果 | 通过 |
|------|------|---------|---------|------|
| E2E-001 | Step 1-3 | 商品+包创建成功 | | |
| E2E-001 | Step 4 | 自动配品预览返回 | | |
| E2E-001 | Step 5-6 | 规则创建+手动推送 | | |
| E2E-001 | Step 7-9 | 商品任务执行 | | |
| E2E-001 | Step 10 | 任务完成+奖励发放 | | |
| E2E-001 | Step 11 | 统计变化 | | |
| E2E-001 | Step 12 | 清理成功 | | |
| E2E-002 | Step 1-2 | 签到配置 | | |
| E2E-002 | Step 3-4 | 第1天签到+状态 | | |
| E2E-002 | Step 5 | 重复签到409 | | |
| E2E-002 | Step 6-7 | 连续3天+奖励 | | |
| E2E-002 | Step 8 | 余额增加 | | |
| E2E-002 | Step 9 | 完成后拒绝 | | |
| E2E-003 | Step 1-2 | 配置+链接 | | |
| E2E-003 | Step 3-4 | 注册回调+奖励 | | |
| E2E-003 | Step 5-6 | 充值回调+奖励 | | |
| E2E-003 | Step 7 | 同IP防刷 | | |
| E2E-003 | Step 8 | 邀请上限 | | |

---

## 约束

1. 使用 `Invoke-WebRequest`（PowerShell），不用 `curl`
2. 替换步骤中的占位符（PRODUCT_A_ID, PACKAGE_ID 等）为实际返回值
3. 记录每个步骤的实际响应
4. 清理测试数据
5. 填写测试结果记录表
6. 一次性完成

---

## 发给测试 Agent 的文本

```
你是测试 Agent（端到端验证轮）。请读取 docs/task-plan-e2e-verification.md，一次性执行 E2E-001 ~ E2E-003 全部 3 个流程验证，不要中途暂停。

核心验证：

E2E-001（商品→包→规则→推送→完成）：
1. 创建 3 个商品（¥50/¥30/¥25）
2. 创建商品包（目标¥99±10%，包含 3 个商品）
3. 测试自动配品预览
4. 创建手动推送规则
5. 手动推送给测试用户
6. 依次执行 3 个商品任务（start-product）
7. 验证任务完成 + 奖励发放
8. 验证统计变化
9. 清理数据

E2E-002（签到完整流程）：
1. 设置签到配置（连续 3 天，奖励¥2）
2. 第 1 天签到 → 验证连续天数=1
3. 重复签到 → 验证 409
4. 修改 DB 日期模拟第 2/3 天签到
5. 第 3 天签到 → 验证奖励发放 + 任务完成
6. 完成后再次签到 → 验证 409

E2E-003（邀请→注册→充值→奖励）：
1. 设置邀请配置
2. 获取邀请链接
3. 注册回调 → 验证奖励
4. 充值回调 → 验证奖励
5. 测试同 IP 防刷
6. 测试邀请上限

注意：
- 使用 Invoke-WebRequest（PowerShell），不用 curl
- 替换占位符为实际返回值
- 填写测试结果记录表
- 清理所有测试数据

开始吧。
```

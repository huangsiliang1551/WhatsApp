# 端到端验证第三轮（E2E-007 ~ E2E-015）

> **执行角色**: testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 验证任务自动触发、后续推链、过期扫描、签到中断、批量操作、删除保护

---

## 前置条件

- Docker 容器正常运行
- 测试账号: `account_id = "acct-h5-daily-cn"`
- Actor 头: `X-Actor-Id: admin` + `X-Actor-Role: super_admin`
- 已有一个测试用户（复用 E2E-006 中创建的 H5 会员，或新建）

### 通用请求头

```powershell
$headers = @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"; "Content-Type"="application/json"}
```

---

## E2E-007：任务规则自动触发（注册触发）

### 目标

验证注册触发规则 → 新用户注册 → 延迟任务自动生成 → 调度器激活。

### 步骤

#### Step 1: 创建商品和商品包

```powershell
# 创建商品
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/products" -Method POST -Headers $headers -Body '{"account_id":"acct-h5-daily-cn","name":"自动触发测试商品","price":20.00,"tags":["auto"]}' -UseBasicParsing
$PRODUCT_ID = ($r.Content | ConvertFrom-Json).id

# 创建商品包
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"自动触发礼包`",`"target_amount`":20,`"amount_tolerance_pct`":10,`"product_count`":1,`"product_ids`":[`"$PRODUCT_ID`"],`"product_snapshot`":[{`"product_id`":`"$PRODUCT_ID`",`"product_name`":`"自动触发测试商品`",`"price`":20,`"quantity`":1}],`"total_value`":20,`"completion_reward`":1}" -UseBasicParsing
$PACKAGE_ID = ($r.Content | ConvertFrom-Json).id
```

#### Step 2: 创建注册触发规则（延迟 1 分钟，测试用短延迟）

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"注册自动触发测试`",`"rule_type`":`"package_push`",`"trigger_type`":`"register`",`"trigger_config`":{`"delay_minutes`":1},`"package_id`":`"$PACKAGE_ID`",`"follow_up_chain`":[],`"expiry_config`":{`"reset_at`":`"00:00`"},`"is_enabled`":true}" -UseBasicParsing
$RULE_ID = ($r.Content | ConvertFrom-Json).id
```

**验证**: 返回 201，trigger_type = "register"。

#### Step 3: 模拟新用户注册（触发回调）

```powershell
# 创建一个全新用户模拟新注册
$NEW_USER_ID = "e2e-auto-user-$(Get-Date -Format 'yyyyMMddHHmmss')"
Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"public_user_id`":`"$NEW_USER_ID`",`"display_name`":`"自动触发测试用户`",`"language_code`":`"zh-CN`",`"is_anonymous`":false,`"lifecycle_status`":`"new`"}" -UseBasicParsing
```

**验证**: 返回 201。

#### Step 4: 等待调度器处理（等待 60 秒）

```powershell
Start-Sleep -Seconds 65
```

#### Step 5: 检查是否生成了延迟任务

```powershell
# 检查 Redis delayed_tasks
docker exec whatsapp_app python -c "
import redis, json
r = redis.Redis(host='redis', port=6379, db=1)
jobs = r.zrange('delayed_tasks', 0, -1)
for j in jobs:
    data = json.loads(j)
    if data.get('user_id') == '$NEW_USER_ID':
        print('FOUND:', json.dumps(data))
"
```

**验证**: 找到包含 NEW_USER_ID 的延迟任务。

#### Step 6: 等待延迟任务被激活（再等 60 秒）

```powershell
Start-Sleep -Seconds 65
```

#### Step 7: 检查任务实例

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances?user_id=$NEW_USER_ID" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).items
```

**验证**: 存在 task_type = "package" 的实例，status = "running"（调度器已激活）。

#### Step 8: 清理

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules/$RULE_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/$PACKAGE_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/products/$PRODUCT_ID" -Method DELETE -Headers $headers -UseBasicParsing
```

---

## E2E-008：完成后续推链

### 目标

验证规则 A 含 follow_up_chain → 完成任务 A → 第 N 天自动推送规则 B。

### 步骤

#### Step 1: 创建 2 个商品包

```powershell
# 包 A
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages" -Method POST -Headers $headers -Body '{"account_id":"acct-h5-daily-cn","name":"后续链-包A","target_amount":10,"amount_tolerance_pct":50,"product_count":1,"product_ids":["placeholder"],"product_snapshot":[{"product_id":"p1","product_name":"测试品A","price":10,"quantity":1}],"total_value":10,"completion_reward":1}' -UseBasicParsing
$PKG_A_ID = ($r.Content | ConvertFrom-Json).id

# 包 B
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages" -Method POST -Headers $headers -Body '{"account_id":"acct-h5-daily-cn","name":"后续链-包B","target_amount":15,"amount_tolerance_pct":50,"product_count":1,"product_ids":["placeholder"],"product_snapshot":[{"product_id":"p2","product_name":"测试品B","price":15,"quantity":1}],"total_value":15,"completion_reward":2}' -UseBasicParsing
$PKG_B_ID = ($r.Content | ConvertFrom-Json).id
```

#### Step 2: 创建规则 B（被后续推送的目标规则）

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"后续链-规则B`",`"rule_type`":`"package_push`",`"trigger_type`":`"manual`",`"trigger_config`":{},`"package_id`":`"$PKG_B_ID`",`"follow_up_chain`":[],`"expiry_config`":{`"reset_at`":`"00:00`"},`"is_enabled`":true}" -UseBasicParsing
$RULE_B_ID = ($r.Content | ConvertFrom-Json).id
```

#### Step 3: 创建规则 A（含 follow_up_chain → 规则 B，延迟 1 天，测试用 1 分钟模拟）

```powershell
# follow_up_chain: [{"delay_days": 1, "rule_id": "$RULE_B_ID"}]
# 测试时 delay_days=1 实际由调度器处理，这里用短延迟模拟
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"后续链-规则A`",`"rule_type`":`"package_push`",`"trigger_type`":`"manual`",`"trigger_config`":{},`"package_id`":`"$PKG_A_ID`",`"follow_up_chain`":[{`"delay_days`":1,`"rule_id`":`"$RULE_B_ID`"}],`"expiry_config`":{`"reset_at`":`"00:00`"},`"is_enabled`":true}" -UseBasicParsing
$RULE_A_ID = ($r.Content | ConvertFrom-Json).id
```

**验证**: 返回 201，follow_up_chain 非空。

#### Step 4: 手动推送规则 A 给测试用户

```powershell
# 获取测试用户
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users?page=1&size=1" -Headers $headers -UseBasicParsing
$TEST_USER_ID = ($r.Content | ConvertFrom-Json).items[0].id

# 推送
Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/manual-push" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"rule_id`":`"$RULE_A_ID`",`"user_ids`":[`"$TEST_USER_ID`"]}" -UseBasicParsing
```

#### Step 5: 完成任务 A 的所有商品

```powershell
# 获取任务实例
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances?user_id=$TEST_USER_ID" -Headers $headers -UseBasicParsing
$TASK_A_ID = ($r.Content | ConvertFrom-Json).items[0].id

# 开始并完成商品任务
Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/$TASK_A_ID/start-product" -Method POST -Headers $headers -Body '{"product_id":"p1"}' -UseBasicParsing

# 如果余额不足，先充值再重试
# Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/$TASK_A_ID/retry-product" -Method POST -Headers $headers -Body '{"product_id":"p1"}' -UseBasicParsing
```

#### Step 6: 验证任务 A 完成

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/$TASK_A_ID" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).status  # 应为 "completed"
```

#### Step 7: 检查后续推送是否已排入延迟队列

```powershell
docker exec whatsapp_app python -c "
import redis, json
r = redis.Redis(host='redis', port=6379, db=1)
jobs = r.zrange('delayed_tasks', 0, -1)
for j in jobs:
    data = json.loads(j)
    print(json.dumps(data))
"
```

**验证**: 找到包含 RULE_B_ID 的延迟任务（delay_days=1 后触发）。

#### Step 8: 清理

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules/$RULE_A_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules/$RULE_B_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/$PKG_A_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/$PKG_B_ID" -Method DELETE -Headers $headers -UseBasicParsing
```

---

## E2E-009：任务过期扫描

### 目标

验证任务到期后调度器自动将状态改为 expired。

### 步骤

#### Step 1: 创建规则（短过期时间，1 分钟）

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages" -Method POST -Headers $headers -Body '{"account_id":"acct-h5-daily-cn","name":"过期测试包","target_amount":10,"amount_tolerance_pct":50,"product_count":1,"product_ids":["p1"],"product_snapshot":[{"product_id":"p1","product_name":"过期品","price":10,"quantity":1}],"total_value":10,"completion_reward":0}' -UseBasicParsing
$PKG_ID = ($r.Content | ConvertFrom-Json).id

$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"过期测试规则`",`"rule_type`":`"package_push`",`"trigger_type`":`"manual`",`"trigger_config`":{},`"package_id`":`"$PKG_ID`",`"follow_up_chain`":[],`"expiry_config`":{`"custom_hours`":0.02},`"is_enabled`":true}" -UseBasicParsing
$RULE_ID = ($r.Content | ConvertFrom-Json).id
```

注意: `custom_hours: 0.02` = 约 1.2 分钟。如果后端不支持小数，改为手动设置 expires_at。

#### Step 2: 推送任务

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users?page=1&size=1" -Headers $headers -UseBasicParsing
$TEST_USER_ID = ($r.Content | ConvertFrom-Json).items[0].id

$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/manual-push" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"rule_id`":`"$RULE_ID`",`"user_ids`":[`"$TEST_USER_ID`"]}" -UseBasicParsing
$TASK_ID = ($r.Content | ConvertFrom-Json).task_instance_ids[0]
```

#### Step 3: 直接设置 expires_at 为过去时间（模拟过期）

```powershell
docker exec whatsapp_postgres psql -U whatsapp_user -d whatsapp_bot -c "UPDATE mkt_task_instances SET expires_at = NOW() - INTERVAL '1 hour' WHERE id = '$TASK_ID'"
```

#### Step 4: 等待调度器过期扫描（等 35 秒）

```powershell
Start-Sleep -Seconds 35
```

#### Step 5: 检查任务状态

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/$TASK_ID" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).status  # 应为 "expired"
```

**验证**: status = "expired"。

#### Step 6: 清理

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules/$RULE_ID" -Method DELETE -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/$PKG_ID" -Method DELETE -Headers $headers -UseBasicParsing
```

---

## E2E-010：签到中断重置

### 目标

验证签到中断后连续天数从 1 重新开始。

### 步骤

#### Step 1: 设置签到配置（连续 5 天）

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/sign-in/config" -Method PUT -Headers $headers -Body '{"consecutive_days":5,"reward_amount":3.00}' -UseBasicParsing
```

#### Step 2: 获取测试用户

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users?page=1&size=1" -Headers $headers -UseBasicParsing
$TEST_USER_ID = ($r.Content | ConvertFrom-Json).items[0].id
```

#### Step 3: 第 1 天签到

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/sign-in?user_id=$TEST_USER_ID&account_id=acct-h5-daily-cn" -Method POST -Headers $headers -UseBasicParsing
```

**验证**: consecutive_days = 1。

#### Step 4: 模拟跳过第 2 天（将第 1 天签到日期改为 2 天前）

```powershell
docker exec whatsapp_postgres psql -U whatsapp_user -d whatsapp_bot -c "UPDATE sign_in_records SET sign_date = CURRENT_DATE - INTERVAL '2 days' WHERE user_id = '$TEST_USER_ID' AND account_id = 'acct-h5-daily-cn'"
```

#### Step 5: 再次签到（应该是第 1 天，因为中断了）

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/sign-in?user_id=$TEST_USER_ID&account_id=acct-h5-daily-cn" -Method POST -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).consecutive_days  # 应为 1（中断重置）
```

**验证**: consecutive_days = 1（不是 2，因为中间断了 1 天）。

#### Step 6: 查看状态确认

```powershell
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/sign-in/status?user_id=$TEST_USER_ID&account_id=acct-h5-daily-cn" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).consecutive_days  # 应为 1
```

#### Step 7: 恢复配置

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/sign-in/config" -Method PUT -Headers $headers -Body '{"consecutive_days":7,"reward_amount":5.00}' -UseBasicParsing
```

#### Step 8: 清理

```powershell
docker exec whatsapp_postgres psql -U whatsapp_user -d whatsapp_bot -c "DELETE FROM sign_in_records WHERE user_id = '$TEST_USER_ID' AND account_id = 'acct-h5-daily-cn'"
```

---

## E2E-011：商品批量导入导出

### 步骤

1. 准备 CSV 文件（3 个商品）
2. `POST /api/products/import` 导入
3. 验证列表包含导入商品
4. `GET /api/products/export` 导出
5. 对比导出内容与导入内容
6. 清理

---

## E2E-012：商品删除保护

### 步骤

1. 创建商品 → 创建商品包引用该商品
2. `DELETE /api/products/{id}` → 应返回 409
3. 先删除商品包
4. 再次 `DELETE /api/products/{id}` → 应返回 204

---

## E2E-013：商品包删除保护

### 步骤

1. 创建商品包 → 创建规则引用该包
2. `DELETE /api/product-packages/{id}` → 应返回 409
3. 先删除规则
4. 再次 `DELETE /api/product-packages/{id}` → 应返回 204

---

## E2E-014：商品包自动配品

### 步骤

1. 创建 10 个不同价格商品（¥5~¥50）
2. `POST /api/product-packages/assemble-preview` 目标 ¥99±10%
3. 验证 within_range = true
4. 用极端目标（如 ¥1000）验证 within_range = false
5. 清理

---

## E2E-015：任务规则启停

### 步骤

1. 创建规则（is_enabled=true）
2. `PATCH /api/task-rules/{id}/toggle` body: `{"is_enabled": false}`
3. 手动推送 → 应失败或规则被跳过
4. `PATCH /api/task-rules/{id}/toggle` body: `{"is_enabled": true}`
5. 手动推送 → 应成功
6. 清理

---

## 测试结果记录表

| 流程 | 步骤 | 预期 | 实际 | 通过 |
|------|------|------|------|------|
| E2E-007 | 自动触发 | 延迟任务生成+激活 | register触发规则创建成功。on_user_registered()定义但未被API层串联，无自动延迟任务。manual_push替代触发生成pending任务 | ❌ 注册触发未串联 |
| E2E-008 | 后续推链 | 任务A完成→排入B延迟队列 | 规则A含follow_up_chain创建成功。任务A完成（status=completed, reward=1.00）。delayed_tasks为空——complete_product()未实现follow_up_chain处理 | ❌ 推链未排入延迟队列 |
| E2E-009 | 过期扫描 | status→expired | 手动设置expires_at为过去，等待35秒后调度器扫描，status=expired | ✅ |
| E2E-010 | 签到中断 | consecutive_days重置为1 | 签到→sign_date改2天前→再签到→consecutive_days=1，status确认无误，配置恢复 | ✅ |
| E2E-011 | 批量导入导出 | CSV 导入+导出一致 | CSV导入3商品成功(imported_count=3)。列表查询含CSV商品。导出CSV含正确数据（带引号的tags） | ✅ |
| E2E-012 | 商品删除保护 | 被引用→409→删包→204 | 商品被包引用→409。删包后→204。注：修复了product_ids JSON列LIKE查询bug | ✅ (含修复) |
| E2E-013 | 包删除保护 | 被引用→409→删规则→204 | 包被规则引用→409。删规则后→204 | ✅ |
| E2E-014 | 自动配品 | within_range正确 | ¥99±10%→total=105, deviation=6.06%→within_range。¥1000→deviation=-88%→out of range | ✅ |
| E2E-015 | 规则启停 | toggle生效 | toggle禁用/启用正确更新is_enabled。但manual_push不检查is_enabled状态（管理员可强制推送） | ⚠️ toggle生效，manual_push跳过检查 |

---

## 发给测试 Agent 的文本

```
你是测试 Agent（端到端验证第三轮）。请读取 docs/task-plan-e2e-round3.md，一次性执行 E2E-007 ~ E2E-015 全部 9 个流程，不要中途暂停。

核心验证：
1. E2E-007 任务自动触发（注册触发→延迟任务→调度器激活）
2. E2E-008 完成后续推链（完成任务A→排入规则B延迟队列）
3. E2E-009 任务过期扫描（设过期→调度器扫描→status=expired）
4. E2E-010 签到中断重置（签到→跳过1天→再签到→连续天数=1）
5. E2E-011 商品批量导入导出
6. E2E-012 商品删除保护（被包引用→409）
7. E2E-013 商品包删除保护（被规则引用→409）
8. E2E-014 商品包自动配品（assemble-preview）
9. E2E-015 任务规则启停（toggle）

注意：使用 Invoke-WebRequest（PowerShell），替换占位符，清理数据，填写结果表。开始吧。
```

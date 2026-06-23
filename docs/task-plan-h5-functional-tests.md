# H5 会员端功能测试（H5-TEST-001 ~ H5-TEST-012）

> **执行角色**: testing_agent（使用 Browser Agent 执行）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 验证 H5 会员端所有单端功能的 UI 交互和数据展示

---

## 前置条件

- Vite 开发服务器运行中 (`http://localhost:5173`)
- Docker 后端运行中 (`http://localhost:8000`)
- 已有 H5 测试账号（通过 E2E-006 创建，或使用已有账号）
- H5 入口: `http://localhost:5173/h5`

### H5 站点 key

```
site_key = "mall-cn"（或 "h5-mall-cn"，需确认实际值）
```

### H5 测试账号

```
# 通过 API 创建或获取
POST /api/h5/auth/register
Body: {"phone": "13800138099", "password": "Test1234", "account_id": "acct-h5-daily-cn"}
```

---

## H5-TEST-001：注册登录流程

### 步骤

1. 访问 `http://localhost:5173/h5/login`
2. 截图登录页面
3. 输入手机号 `13800138099`，密码 `Test1234`
4. 点击"登录"
5. 验证跳转到首页
6. 截图首页

### 验证点

- [ ] 登录页显示正常（手机号输入框 + 密码输入框 + 登录按钮）
- [ ] 登录成功后跳转首页
- [ ] 首页显示用户信息

---

## H5-TEST-002：首页功能

### 步骤

1. 登录后访问首页 `/h5`
2. 截图
3. 检查以下元素

### 验证点

- [ ] 签到卡片显示（连续天数 + 签到按钮）
- [ ] 任务列表区域（进行中/已完成/已过期）
- [ ] 底部导航栏（首页/任务/我的/消息 四个 Tab）
- [ ] 用户余额显示

---

## H5-TEST-003：签到功能

### 步骤

1. 在首页找到签到按钮
2. 点击签到
3. 截图签到结果
4. 再次点击签到（验证重复签到提示）

### 验证点

- [ ] 签到按钮可点击
- [ ] 签到成功后显示"已签到"或连续天数变化
- [ ] 重复签到提示"今日已签到"或类似提示
- [ ] 签到任务完成后签到按钮消失

---

## H5-TEST-004：任务列表页

### 步骤

1. 点击底部导航"任务" Tab
2. 截图
3. 检查任务分区

### 验证点

- [ ] 任务列表显示正常
- [ ] 分区：进行中 / 已完成 / 已过期
- [ ] 每个任务卡片显示：包名 + 进度 + 状态
- [ ] 点击任务卡片跳转到详情页

---

## H5-TEST-005：任务详情页（商品包）

### 前置

需要先通过 E2E 推送一个任务给测试用户。

```powershell
# 手动推送一个任务
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users?page=1&size=1" -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"} -UseBasicParsing
$USER_ID = ($r.Content | ConvertFrom-Json).items[0].id

# 创建商品包
$pkg = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages" -Method POST -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"; "Content-Type"="application/json"} -Body '{"account_id":"acct-h5-daily-cn","name":"H5测试礼包","target_amount":20,"amount_tolerance_pct":50,"product_count":2,"product_ids":["p1","p2"],"product_snapshot":[{"product_id":"p1","product_name":"测试品1","price":10,"quantity":1},{"product_id":"p2","product_name":"测试品2","price":12,"quantity":1}],"total_value":22,"completion_reward":2}' -UseBasicParsing
$PKG_ID = ($pkg.Content | ConvertFrom-Json).id

# 创建规则
$rule = Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules" -Method POST -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"; "Content-Type"="application/json"} -Body "{`"account_id`":`"acct-h5-daily-cn`",`"name`":`"H5测试规则`",`"rule_type`":`"package_push`",`"trigger_type`":`"manual`",`"trigger_config`":{},`"package_id`":`"$PKG_ID`",`"follow_up_chain`":[],`"expiry_config`":{`"reset_at`":`"00:00`"},`"is_enabled`":true}" -UseBasicParsing
$RULE_ID = ($rule.Content | ConvertFrom-Json).id

# 推送
Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/manual-push" -Method POST -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"; "Content-Type"="application/json"} -Body "{`"account_id`":`"acct-h5-daily-cn`",`"rule_id`":`"$RULE_ID`",`"user_ids`":[`"$USER_ID`"]}" -UseBasicParsing
```

### 步骤

1. 在任务列表中找到刚推送的任务
2. 点击进入任务详情
3. 截图
4. 检查商品列表

### 验证点

- [ ] 任务详情页显示包名 + 进度
- [ ] 商品列表：每行一个商品（图片+名称+价格+状态按钮）
- [ ] 底部显示：N 件商品 + 总价
- [ ] "开始任务"按钮可见（未开始的商品）
- [ ] 已完成商品显示"已完成"（不可点击）

---

## H5-TEST-006：开始商品任务

### 步骤

1. 在任务详情页，点击第一个商品的"开始任务"
2. 观察进度弹窗（正在下单→正在支付→支付完成→核对状态）
3. 截图进度弹窗
4. 等待完成
5. 验证按钮变为"已完成"

### 验证点

- [ ] 点击"开始任务"弹出进度弹窗
- [ ] 进度步骤依次推进（4 步）
- [ ] 如果余额不足，提示"余额不足"并显示充值入口
- [ ] 完成后按钮变为"已完成"
- [ ] 下一个商品的"开始任务"变为可点击

### 余额不足测试

如果余额不足：
1. 观察余额不足提示
2. 点击"去充值"
3. 验证跳转到充值页面
4. 充值后返回任务详情
5. 点击"重试"按钮

---

## H5-TEST-007：我的页面

### 步骤

1. 点击底部导航"我的" Tab
2. 截图
3. 检查个人信息展示

### 验证点

- [ ] 个人信息显示（手机号 + 头像）
- [ ] 签到按钮在手机号右侧
- [ ] 余额显示
- [ ] 功能入口：邀请好友 / 设置 / 关于我们 等

---

## H5-TEST-008：邀请好友页面

### 步骤

1. 在"我的"页面点击"邀请好友"
2. 截图
3. 检查邀请链接和分享按钮

### 验证点

- [ ] 邀请页面显示正常
- [ ] 邀请链接显示（可复制）
- [ ] "复制链接"按钮可点击
- [ ] "WhatsApp 分享"按钮可点击
- [ ] 邀请统计显示（已邀请人数 + 已获得奖励）
- [ ] 邀请明细列表

---

## H5-TEST-009：充值页面

### 步骤

1. 找到充值入口（首页余额区域或我的页面）
2. 点击进入充值页
3. 截图
4. 选择金额并充值

### 验证点

- [ ] 充值页面显示正常
- [ ] 金额选择或输入框可用
- [ ] 充值按钮可点击
- [ ] 充值成功后余额更新
- [ ] 交易记录中出现充值记录

---

## H5-TEST-010：提现页面

### 步骤

1. 找到提现入口
2. 点击进入提现页
3. 截图
4. 输入金额并申请提现

### 验证点

- [ ] 提现页面显示正常
- [ ] 可提现余额显示
- [ ] 金额输入框可用
- [ ] 提现按钮可点击
- [ ] 提现申请成功提示
- [ ] 提现记录中出现申请记录

---

## H5-TEST-011：消息/通知页面

### 步骤

1. 点击底部导航"消息" Tab
2. 截图
3. 检查消息列表

### 验证点

- [ ] 消息页面显示正常
- [ ] 消息列表（如有消息）
- [ ] 空状态提示（如无消息）
- [ ] 消息详情可点击

---

## H5-TEST-012：页面导航完整性

### 步骤

依次访问所有 H5 页面，验证不崩溃：

```
/h5                    → 首页
/h5/tasks              → 任务列表
/h5/tasks/package/{id} → 任务详情
/h5/invite             → 邀请好友
/h5/recharge           → 充值
/h5/withdraw           → 提现
/h5/profile            → 个人中心
/h5/settings           → 设置
/h5/messages           → 消息
/h5/orders             → 订单
/h5/verification       → 认证
/h5/whatsapp-binding   → WhatsApp 绑定
```

### 验证点

- [ ] 每个页面可访问（不白屏、不崩溃）
- [ ] 每个页面有合理的 UI 内容
- [ ] 底部导航栏在所有页面可见
- [ ] 未登录状态访问受保护页面 → 跳转登录页

---

## 测试结果记录表

| 测试 | 功能 | 验证点 | 实际结果 | 通过 |
|------|------|--------|---------|------|
| H5-TEST-001 | 注册登录 | 登录页+跳转 | | |
| H5-TEST-002 | 首页 | 签到+任务+导航+余额 | | |
| H5-TEST-003 | 签到 | 签到+重复+完成消失 | | |
| H5-TEST-004 | 任务列表 | 分区+卡片+跳转 | | |
| H5-TEST-005 | 任务详情 | 商品列表+进度+按钮 | | |
| H5-TEST-006 | 开始商品任务 | 进度弹窗+余额不足 | | |
| H5-TEST-007 | 我的页面 | 个人信息+签到+入口 | | |
| H5-TEST-008 | 邀请好友 | 链接+复制+分享+统计 | | |
| H5-TEST-009 | 充值 | 页面+金额+余额更新 | | |
| H5-TEST-010 | 提现 | 页面+金额+申请 | | |
| H5-TEST-011 | 消息 | 列表+空状态 | | |
| H5-TEST-012 | 导航完整性 | 全部页面可访问 | | |

---

## 发给测试 Agent 的文本

```
你是测试 Agent（H5 功能测试轮）。请读取 docs/task-plan-h5-functional-tests.md，使用 Browser Agent 一次性执行 H5-TEST-001 ~ H5-TEST-012 全部 12 个测试，不要中途暂停。

测试入口: http://localhost:5173/h5
登录账号: 手机号 13800138099 / 密码 Test1234（如未注册先注册）

核心测试：
1. H5-TEST-001 注册登录流程
2. H5-TEST-002 首页功能（签到卡片+任务列表+导航+余额）
3. H5-TEST-003 签到功能（签到+重复签到+完成后消失）
4. H5-TEST-004 任务列表页（分区+卡片+跳转）
5. H5-TEST-005 任务详情页（商品列表+进度+开始按钮）
6. H5-TEST-006 开始商品任务（进度弹窗+余额不足处理）
7. H5-TEST-007 我的页面（个人信息+签到按钮+功能入口）
8. H5-TEST-008 邀请好友（链接+复制+WhatsApp分享+统计）
9. H5-TEST-009 充值页面
10. H5-TEST-010 提现页面
11. H5-TEST-011 消息页面
12. H5-TEST-012 页面导航完整性（全部页面可访问不崩溃）

注意：每个测试步骤截图，填写测试结果表。开始吧。
```

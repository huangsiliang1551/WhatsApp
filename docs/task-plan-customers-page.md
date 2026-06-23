# 客户管理页面重设计 + 后端增强（CUS-001 ~ CUS-006）

> **执行角色**: api_agent(后端) + frontend_agent(前端) + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 将客户页面从简单列表升级为功能全面的客户运营中心

---

## 设计理念

客户页面是运营人员最常访问的页面之一。好的客户页面应该让运营在 **10 秒内** 回答以下问题：
1. 这个客户是谁？（身份、状态、注册时间）
2. 他跟系统有过什么交互？（会话、工单、消息）
3. 他的财务情况如何？（余额、充值、提现）
4. 他是否可信？（认证状态、WhatsApp绑定、黑名单）
5. 我能对他做什么操作？（拉黑/解封/查看会话/发消息）

---

## 现有后端能力盘点

| API | 端点 | 已有 |
|-----|------|------|
| 用户列表 | `GET /api/platform/users` | ✅ 但无分页/搜索 |
| 创建用户 | `POST /api/platform/users` | ✅ |
| 更新用户 | `PATCH /api/platform/users/{id}` | ✅ |
| 删除用户 | `DELETE /api/platform/users/{id}` | ✅ |
| 客户 360 摘要 | `GET /api/customers/{id}/summary` | ✅ 会话/工单/钱包/认证/标签 |
| 生命周期状态 | `PATCH /api/customers/{id}/lifecycle-status` | ✅ active/frozen/blacklisted |

## 后端缺口（需新增）

| 能力 | 说明 |
|------|------|
| 用户列表分页 | 当前返回全量，需支持 page/size/sort |
| 用户列表搜索 | 按 public_user_id / display_name / 手机号 模糊搜索 |
| 用户列表聚合字段 | 每个用户附带 conversation_count / ticket_count / wallet_balance |
| 批量操作 | 批量拉黑/解封 |
| 客户交互时间线 | 合并消息+工单+审核+充值记录，按时间倒序 |

---

## CUS-001：后端 — 用户列表增强（P0）

- **估计耗时**: 60 分钟

### 修改 `GET /api/platform/users` 端点

增加参数：
```
GET /api/platform/users?page=1&size=20&sort=created_at:desc&search=keyword&account_id=xxx&has_whatsapp=true&lifecycle_status=active
```

响应改为分页格式：
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "size": 20
}
```

每个用户增加聚合字段（通过 LEFT JOIN + COUNT 或子查询）：
```json
{
  "id": "...",
  "public_user_id": "...",
  "display_name": "...",
  "lifecycle_status": "active",
  "conversation_count": 5,
  "open_conversation_count": 2,
  "ticket_count": 1,
  "wallet_balance": 150.00,
  "last_active_at": "2026-06-13T10:00:00Z",
  ...原有字段
}
```

### 修改文件

| 文件 | 改动 |
|------|------|
| `app/api/routes/platform.py` | list_users 增加分页/搜索/聚合参数 |
| `app/services/platform_service.py` | list_users 增加分页 SQL + 子查询聚合 |
| `app/schemas/platform.py` | PlatformUserListResponse schema |

### 验收标准

1. 分页正确（page/size/total）
2. search 按 public_user_id / display_name / identity_value 模糊匹配
3. 聚合字段正确返回
4. 向后兼容：不传 page 参数时返回全量（旧行为）
5. 测试通过

---

## CUS-002：后端 — 客户交互时间线（P0）

- **估计耗时**: 45 分钟

### 新增端点

```
GET /api/customers/{customer_id}/timeline?account_id=xxx&limit=30
```

合并以下数据源，按 created_at 倒序排列：

| 事件类型 | 数据来源 | 显示内容 |
|---------|---------|---------|
| `conversation` | conversations 表 | 会话创建/最后消息 |
| `message` | messages 表 | 最近 N 条消息摘要 |
| `ticket` | tickets 表 | 工单创建/状态变更 |
| `verification` | member_verification_requests | 认证提交/审核 |
| `whatsapp_binding` | member_whatsapp_binding_requests | 绑定申请/审核 |
| `wallet` | wallet_ledger_entries | 充值/消费/奖励 |
| `withdrawal` | withdrawal_requests | 提现申请 |

响应：
```json
{
  "events": [
    { "type": "message", "time": "...", "summary": "入站: 你好我想查询订单", "metadata": {...} },
    { "type": "ticket", "time": "...", "summary": "工单 T-001 已解决", "metadata": {...} },
    { "type": "wallet", "time": "...", "summary": "充值 +100.00", "metadata": {...} }
  ]
}
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/customer_timeline_service.py` | ~120行 |
| 路由追加到 `app/api/routes/customers.py` | +30行 |

### 验收标准

1. 返回合并时间线
2. 按时间倒序
3. 支持 limit 参数
4. 测试通过

---

## CUS-003：后端 — 批量操作 + 测试（P0）

- **估计耗时**: 30 分钟

### 新增端点

```
POST /api/customers/batch-lifecycle
Body: { "customer_ids": ["id1", "id2"], "account_id": "xxx", "lifecycle_status": "blacklisted" }
```

### 新增测试

`tests/test_customer_page.py` — 10+ 测试：
- 分页正确
- 搜索匹配
- 聚合字段
- 时间线合并
- 批量操作

---

## CUS-004：前端 — 客户列表重构（P0）

- **估计耗时**: 90 分钟

### 页面布局设计

```
┌──────────────────────────────────────────────────────────────────┐
│ 客户管理                              [🔍搜索] [导出CSV]         │
│ 总数 150 | 活跃 120 | 新用户 8 | 黑名单 3 | 有WhatsApp 95       │
├──────────────────────────────────────────────────────────────────┤
│ 筛选栏: [全部账号▾] [生命周期▾] [身份类型▾] [注册时间▾]          │
├──────────────────────────────────────────────────────────────────┤
│ □ │ 用户ID    │ 名称    │ 状态 │ 会话 │ 工单 │ 余额  │ 最后活跃 │ 操作       │
│ □ │ U12345   │ 张三    │ 🟢活跃│  5   │  1   │150.00│ 今天     │ [详情][拉黑]│
│ □ │ U12346   │ 李四    │ 🟢活跃│  2   │  0   │ 30.00│ 昨天     │ [详情][拉黑]│
│ □ │ U12347   │ 王五    │ 🔴黑名│  0   │  0   │  0   │ 3天前    │ [详情][解封]│
│   │ ...      │         │      │      │      │       │          │            │
│ ☑ 已选 2 项  [批量拉黑] [批量解封]                                │
│ 共 150 条 < 1 2 3 ... 8 > 20条/页                               │
└──────────────────────────────────────────────────────────────────┘
```

### 关键交互

1. **全局搜索框**: 支持 用户ID / 名称 / 手机号 搜索，300ms 防抖
2. **筛选器**: 账号(多选) + 生命周期(active/frozen/blacklisted/new/dormant) + 身份类型(WhatsApp/手机/邮箱) + 注册时间范围
3. **列表列**: 勾选框 + 用户ID + 名称 + 状态Tag + 会话数 + 工单数 + 余额 + 最后活跃 + 操作按钮
4. **操作按钮**: [详情](展开侧边面板) [拉黑/解封](Popconfirm) [查看会话](跳转工作台)
5. **批量操作**: 勾选后底部浮出操作栏 [批量拉黑] [批量解封]
6. **分页**: 20/50/100 条/页

### 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/CustomersPage.tsx` | 重写(81行→~400行) |
| `frontend/src/services/api.ts` | 增强 listPlatformUsers 参数 |

---

## CUS-005：前端 — 客户详情侧边面板（P0）

- **估计耗时**: 90 分钟

### 设计

点击列表行"详情"按钮，右侧滑出 480px 宽 Drawer，包含 5 个 Tab：

```
┌─ 客户详情 Drawer (480px) ───────────────────────┐
│ 张三  🟢活跃  U12345  注册: 2026-05-01          │
│ [📱WhatsApp] [☎手机] [📧邮箱]                    │
│                                                    │
│ [概览] [会话] [工单] [财务] [时间线]              │
│ ────────────────────────────────────────────────── │
│                                                    │
│ ┌─ 概览 Tab ───────────────────────────────────┐ │
│ │ 基本信息: 名称/ID/语言/注册时间/IP            │ │
│ │ 认证状态: ✅ 已认证 (身份证)                  │ │
│ │ WhatsApp: ✅ 已绑定 (138****1234)            │ │
│ │ 多IP警告: ⚠️ 2个不同IP注册                   │ │
│ │                                                │ │
│ │ 统计摘要:                                      │ │
│ │ 总会话 5 | 进行中 2 | 工单 1 | 余额 ¥150     │ │
│ │                                                │ │
│ │ 操作区:                                        │ │
│ │ [🚫 拉黑] [📱 查看会话] [✉️ 发消息]          │ │
│ └────────────────────────────────────────────────┘ │
│                                                    │
│ ┌─ 会话 Tab ───────────────────────────────────┐ │
│ │ 5 个会话 (2 进行中)                           │ │
│ │ 1. conv-001 AI托管 最后: 你好... 6/12        │ │
│ │ 2. conv-002 人工接管 最后: 退款... 6/11      │ │
│ │ [跳转到工作台 →]                               │ │
│ └────────────────────────────────────────────────┘ │
│                                                    │
│ ┌─ 工单 Tab ───────────────────────────────────┐ │
│ │ 1 个工单                                      │ │
│ │ T-001 订单未收到 🟢已解决 6/10               │ │
│ └────────────────────────────────────────────────┘ │
│                                                    │
│ ┌─ 财务 Tab ───────────────────────────────────┐ │
│ │ 余额: ¥150.00                                │ │
│ │ 累计充值: ¥500.00 | 累计提现: ¥300.00        │ │
│ │ 最近交易:                                     │ │
│ │ + 充值 ¥100 (6/10)                           │ │
│ │ - 提现 ¥50 (6/8)                             │ │
│ │ + 任务奖励 ¥20 (6/5)                         │ │
│ └────────────────────────────────────────────────┘ │
│                                                    │
│ ┌─ 时间线 Tab ─────────────────────────────────┐ │
│ │ 6/12 14:30 💬 入站消息: 你好我想查询...       │ │
│ │ 6/12 14:31 🤖 AI回复: 您好，请问...          │ │
│ │ 6/11 10:00 🎫 工单 T-001 已解决              │ │
│ │ 6/10 09:00 💰 充值 +¥100                     │ │
│ │ 6/01 08:00 📝 注册账号                       │ │
│ │ [加载更多...]                                 │ │
│ └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

### 新增文件

| 文件 | 行数 |
|------|------|
| `frontend/src/pages/CustomerDetailDrawer.tsx` | ~400行 |

---

## CUS-006：全量验证（P0）

- **估计耗时**: 15 分钟

```powershell
# 后端
.venv\Scripts\python.exe -m pytest tests/test_customer_page.py -q -x

# 前端
cd frontend && npm run build
```

### 验收标准

| # | 项 | 预期 |
|---|-----|------|
| 1 | 用户列表分页 | page/size/total 正确 |
| 2 | 搜索 | 按 ID/名称/手机号 模糊匹配 |
| 3 | 聚合字段 | conversation_count / ticket_count / wallet_balance |
| 4 | 时间线 | 合并 5+ 事件类型 |
| 5 | 批量操作 | 批量拉黑/解封可用 |
| 6 | 前端列表 | 分页+搜索+筛选+批量 |
| 7 | 详情 Drawer | 5 Tab 全部可用 |
| 8 | npm run build | 通过 |
| 9 | 测试 | 10+ 通过 |

---

## 文件清单

### 后端

| 文件 | 操作 | 行数 |
|------|------|------|
| `app/api/routes/platform.py` | 修改 | ~40 |
| `app/api/routes/customers.py` | 修改 | ~30 |
| `app/services/platform_service.py` | 修改 | ~60 |
| `app/services/customer_timeline_service.py` | 新增 | ~120 |
| `app/schemas/platform.py` | 修改 | ~20 |
| `tests/test_customer_page.py` | 新增 | ~200 |

### 前端

| 文件 | 操作 | 行数 |
|------|------|------|
| `frontend/src/pages/CustomersPage.tsx` | 重写 | ~400 |
| `frontend/src/pages/CustomerDetailDrawer.tsx` | 新增 | ~400 |
| `frontend/src/services/api.ts` | 修改 | ~20 |

### 总计: ~1290 行

---

## 全局约束

1. 后端不碰前端代码
2. 前端不碰后端代码
3. 不碰 H5
4. 用户列表向后兼容（不传 page 时返回全量）
5. API Key / 密码等敏感信息不出现在任何响应中
6. 每次改动后验证
7. 一次性执行全部任务，不中途暂停

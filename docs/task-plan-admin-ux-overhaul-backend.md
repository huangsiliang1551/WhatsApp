# 管理后台全面 UX 重构 — 后端接口任务（DBE-001 ~ DBE-012）

> **执行角色**: api_agent + db_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 为前端 UX 重构提供后端 API 支持，让操作员找数据快、操作简单

---

## 0. 后端需要新增的 API 能力

| 能力 | 前端依赖页面 | 当前状态 |
|------|-------------|---------|
| Dashboard 聚合摘要 | Dashboard | 无（前端拼凑多个 API） |
| 待办事项聚合 | Dashboard | 无 |
| 全文搜索 | 所有列表页 | 无（仅前端本地过滤） |
| 批量操作 | 模板/会话/审核/用户 | 部分有，部分无 |
| 数据导出 | 各列表页 | 仅前端 CSV（小数据） |
| 分页查询优化 | 所有 ProTable 页 | 部分 API 不支持分页 |
| 会话统计聚合 | 会话/分配/Dashboard | 分散在多个 API |

---

## 1. 执行编排（4 Phase，预计 2-3 天）

```
Day 1:
  Phase 1（Dashboard 聚合 API，P0）: DBE-001~003

Day 2:
  Phase 2（搜索 + 分页，P0）: DBE-004~006
  Phase 3（批量操作 API，P0）: DBE-007~009

Day 3:
  Phase 4（导出 + 验证，P1）: DBE-010~012
```

---

## Phase 1：Dashboard 聚合 API（P0）

### DBE-001：Dashboard 摘要 API

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 新增端点

```
GET /api/dashboard/summary
```

#### 响应结构

```json
{
  "system_health": {
    "app_healthy": true,
    "worker_healthy": true,
    "db_healthy": true,
    "redis_healthy": true,
    "queue_healthy": true,
    "last_check": "2026-06-12T14:32:00Z"
  },
  "conversation_summary": {
    "total_open": 128,
    "ai_managed": 108,
    "human_managed": 8,
    "paused": 12,
    "handover_recommended": 12
  },
  "message_stats": {
    "today_inbound": 650,
    "today_outbound": 597,
    "today_total": 1247,
    "yesterday_total": 1113,
    "change_percent": 12.0
  },
  "ai_performance": {
    "reply_rate": 94.2,
    "fallback_rate": 2.1,
    "handover_rate": 5.7,
    "avg_response_seconds": 3.2
  },
  "queue_status": {
    "pending": 5,
    "processing": 3,
    "failed": 0,
    "dead_letter": 2
  },
  "account_count": 3,
  "agent_online_count": 4
}
```

#### 实现

**新增 `app/services/dashboard_service.py`**
- `get_dashboard_summary() -> DashboardSummary`
- 内部聚合:
  - 会话统计: `SELECT count(*) FROM conversations WHERE status='open' GROUP BY management_mode`
  - 消息统计: `SELECT count(*) FROM messages WHERE created_at >= today`
  - 队列状态: Redis `LLEN` + 死信计数
  - 系统健康: `/health` + worker_health + DB ping + Redis ping
  - AI 表现: 从 metrics 指标计算

**新增 `app/api/routes/dashboard.py`**
- `GET /api/dashboard/summary`

#### 测试

`tests/test_dashboard_api.py` — 8+ 测试

#### 验收标准

1. API 返回完整摘要
2. 响应时间 < 500ms
3. 测试通过

---

### DBE-002：待办事项聚合 API

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 新增端点

```
GET /api/dashboard/todo
```

#### 响应结构

```json
{
  "items": [
    {
      "type": "handover_recommended",
      "label": "推荐转人工会话",
      "count": 12,
      "priority": "high",
      "action_path": "/collaboration/assignments?filter=recommended"
    },
    {
      "type": "pending_review",
      "label": "待审核模板",
      "count": 5,
      "priority": "medium",
      "action_path": "/templates?status=pending_review"
    },
    {
      "type": "open_tickets",
      "label": "未处理工单",
      "count": 3,
      "priority": "high",
      "action_path": "/collaboration/tickets?status=open"
    },
    {
      "type": "pending_withdrawals",
      "label": "待审核提现",
      "count": 2,
      "priority": "medium",
      "action_path": "/system/operations?tab=withdrawals&status=pending"
    },
    {
      "type": "dead_letter_jobs",
      "label": "死信队列任务",
      "count": 2,
      "priority": "high",
      "action_path": "/system/operations?tab=queue&filter=dead_letter"
    }
  ],
  "total": 24,
  "high_priority_count": 17
}
```

#### 实现

**新增到 `app/services/dashboard_service.py`**
- `get_todo_items() -> list[TodoItem]`
- 聚合: 推荐转人工数 + 待审核模板 + 未处理工单 + 待审核提现 + 死信队列

#### 测试

扩展 `tests/test_dashboard_api.py`

#### 验收标准

1. 各类待办数量正确
2. action_path 可跳转
3. 测试通过

---

### DBE-003：Dashboard 消息趋势 API

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 新增端点

```
GET /api/dashboard/message-trend?hours=24
```

#### 响应结构

```json
{
  "points": [
    { "hour": "2026-06-12T00:00", "inbound": 12, "outbound": 10, "template": 2 },
    { "hour": "2026-06-12T01:00", "inbound": 8, "outbound": 7, "template": 1 }
  ]
}
```

#### 验收标准

1. 按小时聚合
2. 支持 24h / 7d / 30d
3. 测试通过

---

## Phase 2：搜索 + 分页（P0）

### DBE-004：全局搜索 API

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 新增端点

```
GET /api/search?q=keyword&type=conversation|customer|template|ticket&limit=10
```

#### 响应结构

```json
{
  "conversations": [
    { "id": "xxx", "account_id": "a1", "customer_id": "user123", "preview": "你好，我想...", "mode": "ai_managed", "updated_at": "..." }
  ],
  "customers": [
    { "id": "xxx", "public_user_id": "U12345", "display_name": "张三", "phone": "138****1234" }
  ],
  "templates": [
    { "id": "xxx", "name": "订单确认", "status": "APPROVED", "language": "zh_CN" }
  ],
  "tickets": [
    { "id": "xxx", "subject": "订单未收到", "status": "open", "priority": "high" }
  ]
}
```

#### 实现

**新增 `app/services/search_service.py`**
- `global_search(query, types, limit) -> SearchResults`
- 使用 PostgreSQL `ILIKE` 或 `to_tsvector` 全文搜索
- 每种类型最多返回 limit 条
- 支持按 type 过滤

**新增 `app/api/routes/search.py`**

#### 测试

`tests/test_search.py` — 10+ 测试

#### 验收标准

1. 跨类型搜索可用
2. 响应时间 < 300ms
3. 结果高亮字段正确
4. 测试通过

---

### DBE-005：会话列表分页优化

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 修改端点

```
GET /api/conversations?page=1&size=20&sort=last_message_at:desc&account_id=xxx&management_mode=xxx&status=xxx&search=keyword
```

#### 改进

- 当前: 返回全部会话（前端本地分页）
- 改进: 真正的服务端分页 + 排序 + 搜索
- 响应增加 `{ items: [], total: N, page: N, size: N }`

#### 验收标准

1. 分页正确
2. 排序可用
3. 搜索可用
4. 测试通过

---

### DBE-006：模板/工单/用户列表分页优化

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 修改端点

```
GET /api/templates?page=1&size=20&sort=created_at:desc&status=xxx&search=keyword
GET /api/tickets?page=1&size=20&sort=created_at:desc&status=xxx&search=keyword
GET /api/users?page=1&size=20&sort=created_at:desc&search=keyword
```

每个端点增加：
- `page` + `size` 分页参数
- `sort` 排序参数
- `search` 全文搜索参数
- 响应统一为 `{ items: [], total: N, page: N, size: N }`

#### 验收标准

1. 三个端点都支持分页
2. 测试通过

---

## Phase 3：批量操作 API（P0）

### DBE-007：批量会话操作

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 新增端点

```
POST /api/conversations/batch-handover
POST /api/conversations/batch-restore-ai
POST /api/conversations/batch-close
POST /api/conversations/batch-assign
```

#### 请求结构

```json
{
  "conversation_ids": ["a1:c1", "a1:c2", "a2:c3"],
  "agent_id": "agent-001",
  "reason": "批量处理"
}
```

#### 响应结构

```json
{
  "success_count": 3,
  "failed_count": 0,
  "results": [
    { "conversation_id": "a1:c1", "status": "success" },
    { "conversation_id": "a1:c2", "status": "success" },
    { "conversation_id": "a2:c3", "status": "success" }
  ]
}
```

#### 实现

**新增 `app/api/routes/conversations.py`** 中的批量端点
- 每个操作内部循环调用已有 Service
- 独立事务: 单条失败不影响其他
- 审计日志: 记录批量操作

#### 测试

扩展 `tests/test_conversations.py`

#### 验收标准

1. 批量操作可用
2. 单条失败不影响其他
3. 审计日志记录
4. 测试通过

---

### DBE-008：批量模板操作

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增端点

```
POST /api/templates/batch-approve
POST /api/templates/batch-reject
POST /api/templates/batch-delete
POST /api/templates/batch-sync-meta
```

#### 验收标准

1. 批量审核/拒绝/删除/同步可用
2. 测试通过

---

### DBE-009：批量审核操作

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增端点

```
POST /api/reviews/batch-approve
POST /api/reviews/batch-reject
```

#### 请求结构

```json
{
  "review_ids": ["r1", "r2", "r3"],
  "reviewer_note": "批量审核通过"
}
```

#### 验收标准

1. 批量审核可用
2. 测试通过

---

## Phase 4：导出 + 验证（P1）

### DBE-010：通用数据导出 API

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 新增端点

```
POST /api/exports
GET /api/exports/{export_id}
GET /api/exports/{export_id}/download
```

#### POST /api/exports 请求

```json
{
  "type": "conversations",
  "filters": { "account_id": "a1", "status": "open" },
  "format": "csv",
  "columns": ["conversation_id", "customer_id", "management_mode", "last_message_at"]
}
```

#### 响应

```json
{
  "export_id": "exp-001",
  "status": "processing",
  "estimated_rows": 128
}
```

#### GET /api/exports/{export_id} 响应

```json
{
  "export_id": "exp-001",
  "status": "completed",
  "download_url": "/api/exports/exp-001/download",
  "file_size_bytes": 15234,
  "row_count": 128,
  "expires_at": "2026-06-13T14:32:00Z"
}
```

#### 实现

**新增 `app/services/export_service.py`**
- 支持类型: conversations / templates / tickets / customers / users / audit_logs
- 异步生成: 写入临时文件
- Redis 队列: 大量数据走 worker 异步
- 文件保留: 24 小时自动清理

**新增 `app/api/routes/exports.py`**

#### 测试

`tests/test_exports.py` — 8+ 测试

#### 验收标准

1. 创建导出任务
2. 轮询状态
3. 下载 CSV 文件
4. 文件 24h 过期
5. 测试通过

---

### DBE-011：OpenAPI 文档更新

- **优先级**: P1
- **估计耗时**: 15 分钟

为所有新增 API 添加 summary / description / tags。

---

### DBE-012：全量回归测试

- **优先级**: P0
- **估计耗时**: 30 分钟

```powershell
cd E:\codex\WhatsApp
.venv\Scripts\python.exe -m pytest tests/test_dashboard_api.py tests/test_search.py tests/test_exports.py tests/test_conversations.py tests/test_templates.py -q
```

#### 验收标准

| 项 | 预期 |
|----|------|
| test_dashboard_api | 8+ 通过 |
| test_search | 10+ 通过 |
| test_exports | 8+ 通过 |
| 现有测试 | 不退化 |

---

## 2. 全局约束

1. **不碰前端代码**: 不改 `frontend/` 目录
2. **不碰 H5 相关**: 不改 `h5_*` 路由和服务
3. **所有新代码有类型注解**
4. **I/O 全部异步**
5. **所有外部调用有超时 + 日志 + 异常处理**
6. **所有实体带 account_id**
7. **批量操作独立事务**: 单条失败不影响其他
8. **导出文件 24h 自动清理**
9. **进度文件**: `.codex-run/progress/DBE-XXX.json`
10. **单任务最大执行 90 分钟**
11. **每次改动后运行相关测试**
12. **一次性执行全部任务，不中途暂停确认**

---

## 3. 新增文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `app/services/dashboard_service.py` | 新增 | Dashboard 聚合 + 待办 |
| `app/services/search_service.py` | 新增 | 全局搜索 |
| `app/services/export_service.py` | 新增 | 数据导出 |
| `app/api/routes/dashboard.py` | 新增 | Dashboard API |
| `app/api/routes/search.py` | 新增 | 搜索 API |
| `app/api/routes/exports.py` | 新增 | 导出 API |
| `app/main.py` | 修改 | 注册新路由 |
| `tests/test_dashboard_api.py` | 新增 | Dashboard 测试 |
| `tests/test_search.py` | 新增 | 搜索测试 |
| `tests/test_exports.py` | 新增 | 导出测试 |
| `app/api/routes/conversations.py` | 修改 | 添加批量端点 |
| `app/api/routes/templates.py` | 修改 | 添加批量端点 |
| `app/api/routes/reviews.py` | 修改 | 添加批量端点 |

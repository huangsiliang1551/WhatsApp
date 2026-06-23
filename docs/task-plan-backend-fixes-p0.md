# 后端修复 + P0 功能 API 补全（BFX-001 ~ BFX-008）

> **执行角色**: api_agent + db_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 修复 Launch Readiness 误报 + 补全 P0 级功能 API

---

## Part A：Bug 修复（1 项）

### BFX-001：Launch Readiness 文件检查路径修复

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 问题

`app/services/launch_readiness_service.py` 中的文件检查在 Docker 容器内执行，但以下文件仅存在于宿主机，未挂载到容器：

- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/alerts.yml`
- `monitoring/alertmanager/alertmanager.yml`
- `monitoring/grafana/dashboards/whatsapp-platform-overview.json`
- `docs/deployment-checklist.md`
- `docs/recovery-runbook.md`
- `scripts/backup-postgres.ps1`
- `scripts/restore-postgres.ps1`
- `scripts/check-launch-readiness.ps1`
- `scripts/verify-ci.ps1`

导致监控页面显示 10 条假阳 Warning。

#### 修复方案（二选一，选 A）

**方案 A（推荐）：修改 docker-compose.yml 挂载监控/脚本目录**

```yaml
app:
  volumes:
    - ./app:/workspace/app
    - ./alembic:/workspace/alembic
    - ./alembic.ini:/workspace/alembic.ini
    - ./monitoring:/workspace/monitoring:ro    # 新增
    - ./scripts:/workspace/scripts:ro          # 新增
    - ./docs:/workspace/docs:ro                # 新增
```

优点：文件检查在容器内可用，且方便容器内查看配置。

**方案 B：修改 launch_readiness_service.py 增加路径查找逻辑**

```python
def _check_file_exists(relative_path: str) -> bool:
    """Check file in multiple possible locations."""
    candidates = [
        Path("/workspace") / relative_path,       # Docker container
        Path(__file__).parents[2] / relative_path,  # Relative to app/
        Path.cwd() / relative_path,                # CWD
    ]
    return any(p.exists() for p in candidates)
```

**同时修改**:
- 如果两种方案都不能解决，将文件检查改为 `status: "skipped"` 并显示原因 "Docker container - file check skipped"

#### 额外修复：OpenAI API Key Blocker

修改 `.env.example` 添加说明：

```
# AI Provider: openai | deepseek | mock
# 开发阶段如无 API Key，请设为 mock
AI_PROVIDER=mock
```

#### 验证

```powershell
# 重启 Docker
docker compose restart app

# 检查 Launch Readiness
curl http://localhost:8000/api/launch-readiness
```

#### 验收标准

1. 监控页面不再显示文件检查假阳 Warning
2. 如果选方案 A：docker-compose.yml 包含新 volume 挂载
3. 如果选方案 B：launch_readiness_service.py 多路径查找
4. 相关测试通过

---

## Part B：P0 功能 API（7 项）

### BFX-002：客户 360 聚合 API

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 新增端点

```
GET /api/customers/{customer_id}/summary?account_id=xxx
```

#### 响应结构

```json
{
  "customer": {
    "id": "xxx",
    "public_user_id": "U12345",
    "display_name": "张三",
    "language": "zh-CN",
    "created_at": "2026-06-01T10:00:00Z",
    "lifecycle_status": "active"
  },
  "member_status": {
    "verification": {
      "status": "approved",
      "request_type": "identity",
      "updated_at": "2026-06-10T14:00:00Z"
    },
    "whatsapp_binding": {
      "status": "bound",
      "phone_number": "+86138****1234",
      "updated_at": "2026-06-11T09:00:00Z"
    }
  },
  "conversations": {
    "total": 5,
    "open": 2,
    "items": [
      {
        "conversation_id": "c1",
        "account_id": "a1",
        "management_mode": "ai_managed",
        "last_message_at": "2026-06-12T14:00:00Z",
        "last_message_preview": "你好，我想查询..."
      }
    ]
  },
  "tickets": {
    "total": 2,
    "open": 1,
    "items": [
      {
        "ticket_no": "T-001",
        "title": "订单未收到",
        "status": "open",
        "created_at": "2026-06-11T10:00:00Z"
      }
    ]
  },
  "wallet": {
    "balance": 150.00,
    "total_recharged": 500.00,
    "total_withdrawn": 300.00,
    "recent_transactions": [
      { "type": "recharge", "amount": 100.00, "created_at": "2026-06-10T10:00:00Z" }
    ]
  },
  "tags": ["VIP", "活跃用户"]
}
```

#### 实现

**新增 `app/services/customer_summary_service.py`**

```python
class CustomerSummaryService:
    async def get_summary(
        self, customer_id: str, account_id: str | None = None
    ) -> CustomerSummary:
        # 并行查询各模块数据
        customer, conversations, tickets, wallet, member_status = await asyncio.gather(
            self._get_customer(customer_id),
            self._get_conversations(customer_id, account_id),
            self._get_tickets(customer_id, account_id),
            self._get_wallet(customer_id, account_id),
            self._get_member_status(customer_id, account_id),
        )
        return CustomerSummary(...)
```

**新增 `app/api/routes/customers.py`**

- `GET /api/customers/{customer_id}/summary`

**注册到 `app/main.py`**

#### 测试

`tests/test_customer_summary.py` — 8+ 测试:
- 有数据: 各模块正确聚合
- 无数据: 空模块返回空列表/零值
- 跨账号: account_id 过滤正确
- 性能: 并行查询 < 500ms

#### 验收标准

1. API 返回完整聚合数据
2. 并行查询 < 500ms
3. 8+ 测试通过
4. `app/main.py` 注册路由

---

### BFX-003：会话内部备注 API

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 新增端点

```
POST /api/conversations/{account_id}:{conversation_id}/notes
GET  /api/conversations/{account_id}:{conversation_id}/notes
```

#### POST 请求

```json
{
  "content": "客户情绪激动，优先处理",
  "agent_id": "agent-001"
}
```

#### 响应

```json
{
  "note_id": "note-001",
  "conversation_id": "c1",
  "account_id": "a1",
  "content": "客户情绪激动，优先处理",
  "agent_id": "agent-001",
  "agent_name": "张三",
  "created_at": "2026-06-12T14:32:00Z"
}
```

#### 数据模型

新增 `conversation_notes` 表（Alembic 迁移）:

```python
class ConversationNote(Base):
    __tablename__ = "conversation_notes"
    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    agent_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**新增 `app/services/conversation_note_service.py`**
**新增 `app/api/routes/conversation_notes.py`**
**新增 `alembic/versions/0067_conversation_notes.py`**

#### 测试

`tests/test_conversation_notes.py` — 6+ 测试:
- 创建备注
- 查询备注列表
- 备注不发送到客户端（验证 messaging dispatch 不触发）
- account_id 隔离

#### 验收标准

1. 创建/查询 API 可用
2. 备注不触发消息发送
3. 迁移文件存在
4. 6+ 测试通过

---

### BFX-004：快捷回复/话术库 API

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 新增端点

```
GET    /api/canned-responses?account_id=xxx
POST   /api/canned-responses
PUT    /api/canned-responses/{id}
DELETE /api/canned-responses/{id}
```

#### 数据模型

新增 `canned_responses` 表:

```python
class CannedResponse(Base):
    __tablename__ = "canned_responses"
    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=True)  # null=全局
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)
    variables = Column(JSON, nullable=False, default=list)  # ["order_id", "status"]
    is_active = Column(Boolean, default=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**新增 `app/services/canned_response_service.py`**
**新增 `app/api/routes/canned_responses.py`**
**新增 `alembic/versions/0068_canned_responses.py`**

#### 初始数据

迁移文件内预置 10 条默认话术（见前端文档 FX-006 的表格）。

#### 测试

`tests/test_canned_responses.py` — 6+ 测试

#### 验收标准

1. CRUD API 可用
2. 全局 + 账号级话术隔离
3. 迁移含初始数据
4. 6+ 测试通过

---

### BFX-005：工作时间配置 API

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 新增端点

```
GET /api/runtime/business-hours?account_id=xxx
PUT /api/runtime/business-hours?account_id=xxx
```

#### GET 响应

```json
{
  "account_id": "a1",
  "business_hours": {
    "weekdays": [1, 2, 3, 4, 5],
    "start_time": "09:00",
    "end_time": "18:00",
    "timezone": "Asia/Shanghai",
    "off_hours_behavior": "ai_managed",
    "off_hours_message": "您好，当前为非工作时间，我们的客服将在工作日 09:00-18:00 为您服务。"
  },
  "is_currently_business_hours": true
}
```

#### 数据模型

新增 `business_hours` 表:

```python
class BusinessHours(Base):
    __tablename__ = "business_hours"
    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, unique=True)
    weekdays = Column(JSON, nullable=False, default=[1,2,3,4,5])
    start_time = Column(String(5), nullable=False, default="09:00")
    end_time = Column(String(5), nullable=False, default="18:00")
    timezone = Column(String(50), nullable=False, default="Asia/Shanghai")
    off_hours_behavior = Column(String(20), nullable=False, default="ai_managed")
    off_hours_message = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
```

**新增 `app/services/business_hours_service.py`**
**新增路由到 `app/api/routes/runtime.py`**（追加，不新建文件）
**新增 `alembic/versions/0069_business_hours.py`**

#### 集成到 AI 管道

修改 `app/services/chat.py` 或 `runtime_state.py`:
- 在处理入站消息时检查 `is_currently_business_hours`
- 非工作时间 + `off_hours_behavior == "ai_managed"` → AI 正常回复
- 非工作时间 + `off_hours_behavior == "message"` → 回复 off_hours_message，不触发 AI
- 非工作时间 + `off_hours_behavior == "silent"` → 不回复

#### 测试

`tests/test_business_hours.py` — 8+ 测试:
- 工作日 10:00 → is_business_hours = true
- 周六 10:00 → is_business_hours = false
- 时区转换正确（UTC+8 09:00 = UTC 01:00）
- 非工作时间行为: ai_managed / message / silent

#### 验收标准

1. GET/PUT API 可用
2. 时间判断正确（含时区）
3. 非工作时间行为集成到消息处理
4. 迁移文件存在
5. 8+ 测试通过

---

### BFX-006：会话标签 API

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增端点

```
GET    /api/conversations/{account_id}:{conversation_id}/tags
PUT    /api/conversations/{account_id}:{conversation_id}/tags
```

#### PUT 请求

```json
{
  "tags": ["VIP", "投诉", "紧急"]
}
```

#### 响应

```json
{
  "conversation_id": "c1",
  "account_id": "a1",
  "tags": ["VIP", "投诉", "紧急"],
  "updated_at": "2026-06-12T14:32:00Z"
}
```

#### 数据模型

在 `conversations` 表增加 `tags` 列:

```python
# 新增 Alembic 迁移
tags = Column(JSON, nullable=False, default=list)
```

**修改 `app/services/conversation_service.py`**: 增加 `set_tags()` 和 `get_tags()` 方法
**修改 `app/api/routes/conversations.py`**: 增加 tag 端点

#### 查询支持

修改 `listConversations` 端点增加 `tag` 查询参数:
```
GET /api/conversations?tag=VIP
```

#### 测试

扩展 `tests/test_conversations.py` — 4+ 测试

#### 验收标准

1. GET/PUT 标签 API 可用
2. 按标签筛选可用
3. 迁移文件存在
4. 4+ 测试通过

---

### BFX-007：AI 回复质量聚合 API

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 新增端点

```
GET /api/dashboard/ai-performance?days=7
GET /api/dashboard/top-intents?days=7&limit=10
```

#### ai-performance 响应

```json
{
  "days": 7,
  "daily": [
    {
      "date": "2026-06-12",
      "total_requests": 120,
      "ai_replies": 110,
      "fallbacks": 5,
      "handovers": 5,
      "reply_rate": 91.7,
      "fallback_rate": 4.2,
      "handover_rate": 4.2
    }
  ],
  "summary": {
    "avg_reply_rate": 93.5,
    "avg_fallback_rate": 2.8,
    "avg_handover_rate": 3.7,
    "total_requests": 840
  }
}
```

#### top-intents 响应

```json
{
  "items": [
    { "intent": "订单查询", "count": 45, "percentage": 32.0 },
    { "intent": "物流追踪", "count": 38, "percentage": 27.0 },
    { "intent": "退款申请", "count": 25, "percentage": 18.0 }
  ]
}
```

#### 实现

**扩展 `app/services/dashboard_service.py`**:
- `get_ai_performance(days: int) -> AiPerformance`
- `get_top_intents(days: int, limit: int) -> list[IntentStat]`

数据来源: `message_events` 表中 `ai_generated` / `intent_name` 字段聚合。

**扩展 `app/api/routes/dashboard.py`**: 增加 2 个端点

#### 测试

扩展 `tests/test_dashboard_api.py` — 6+ 测试

#### 验收标准

1. 两个端点返回正确数据
2. 支持 7d / 30d 时间范围
3. 6+ 测试通过

---

### BFX-008：消息送达状态回执 API

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 修改端点

当前 `GET /api/conversations/{id}/messages` 返回的消息缺少 `delivery_status` 字段。

#### 修改

1. 确认 `messages` 表或 `message_events` 表已存储 delivery_status
2. 修改消息查询 API，在响应中包含:

```json
{
  "message_id": "m1",
  "direction": "outbound",
  "text": "您好",
  "delivery_status": "delivered",
  "delivered_at": "2026-06-12T14:32:05Z",
  "read_at": null
}
```

3. Webhook 状态更新处理: 确认 `webhooks.py` 中 status 类型（sent/delivered/read/failed）正确更新到 message_events

#### 实现

**修改 `app/services/conversation_service.py`**:
- `list_messages()` 增加 delivery_status 字段返回

**修改 `app/api/routes/webhooks.py`**:
- 确认 status update 处理链路完整

#### 测试

扩展 `tests/test_whatsapp_webhooks.py`:
- status update 正确写入
- 查询消息时返回 delivery_status

#### 验收标准

1. 消息查询返回 delivery_status
2. Webhook status update 正确更新
3. 测试通过

---

## 全量验证（BFX-VER）

```powershell
cd E:\codex\WhatsApp

# 新测试
.venv\Scripts\python.exe -m pytest tests/test_customer_summary.py tests/test_conversation_notes.py tests/test_canned_responses.py tests/test_business_hours.py -q -x

# 扩展测试
.venv\Scripts\python.exe -m pytest tests/test_dashboard_api.py tests/test_conversations.py tests/test_whatsapp_webhooks.py -q -x

# 迁移验证
.venv\Scripts\python.exe -m pytest tests/test_alembic_upgrade.py -q -x

# Launch Readiness 验证
curl http://localhost:8000/api/launch-readiness
```

### 最终验收清单

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | Launch Readiness 文件检查 | 无假阳 Warning |
| 2 | 客户 360 API | 返回完整聚合 + < 500ms |
| 3 | 会话备注 API | CRUD 可用 + 不触发消息 |
| 4 | 话术库 API | CRUD 可用 + 初始数据 |
| 5 | 工作时间 API | GET/PUT 可用 + 时间判断正确 |
| 6 | 会话标签 API | GET/PUT 可用 + 筛选可用 |
| 7 | AI 质量聚合 API | 趋势 + Top10 可用 |
| 8 | 消息状态回执 | delivery_status 字段存在 |
| 9 | 新 Alembic 迁移 | 0067 + 0068 + 0069 + 0070 存在 |
| 10 | 新增测试 | 38+ 全部通过 |
| 11 | 现有测试 | 不退化 |

## 全局约束

1. **不碰前端代码**: 不改 `frontend/` 目录
2. **不碰 H5 相关**: 不改 `h5_*` 路由和服务
3. **所有新代码有类型注解**
4. **I/O 全部异步**
5. **所有实体带 account_id**
6. **新增表必须有 Alembic 迁移**
7. **进度文件**: `.codex-run/progress/BFX-XXX.json`
8. **单任务最大执行 90 分钟**
9. **每次改动后运行相关测试**
10. **一次性执行全部任务，不中途暂停确认**

---

## 新增文件清单

| 文件 | 动作 |
|------|------|
| `app/services/customer_summary_service.py` | 新增 |
| `app/services/conversation_note_service.py` | 新增 |
| `app/services/canned_response_service.py` | 新增 |
| `app/services/business_hours_service.py` | 新增 |
| `app/api/routes/customers.py` | 新增 |
| `app/api/routes/canned_responses.py` | 新增 |
| `app/api/routes/conversation_notes.py` | 新增 |
| `alembic/versions/0067_conversation_notes.py` | 新增 |
| `alembic/versions/0068_canned_responses.py` | 新增 |
| `alembic/versions/0069_business_hours.py` | 新增 |
| `alembic/versions/0070_conversation_tags.py` | 新增 |
| `tests/test_customer_summary.py` | 新增 |
| `tests/test_conversation_notes.py` | 新增 |
| `tests/test_canned_responses.py` | 新增 |
| `tests/test_business_hours.py` | 新增 |
| `app/services/launch_readiness_service.py` | 修改 |
| `app/services/dashboard_service.py` | 修改 |
| `app/services/conversation_service.py` | 修改 |
| `app/api/routes/runtime.py` | 修改 |
| `app/api/routes/conversations.py` | 修改 |
| `app/api/routes/dashboard.py` | 修改 |
| `app/main.py` | 修改（注册新路由） |
| `docker-compose.yml` | 修改（新增 volume 挂载） |

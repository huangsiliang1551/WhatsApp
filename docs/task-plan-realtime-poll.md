# 会话实时推送端点修复（RT-001 ~ RT-003）

> **执行角色**: api_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 修复 ChatPage 实时更新缺失问题

---

## 问题背景

前端 `chatRealtime.ts` 设计了两层实时策略，但后端两层都未实现：

| 层 | 前端端点 | 后端状态 | 影响 |
|----|---------|---------|------|
| 第一层 SSE | `/api/conversations/stream` | 404 不存在 | 无法实时推送 |
| 第二层轮询 | `/api/conversations/poll?since=` | 404 不存在 | 降级也失败 |

**结果**: ChatPage 完全无法自动刷新新消息，操作员必须手动点"刷新"。

---

## RT-001：会话轮询端点（P0 — 必做）

- **优先级**: P0
- **估计耗时**: 30 分钟

### 新增端点

```
GET /api/conversations/poll?since={ISO8601}&account_id={optional}
```

### 响应结构

```json
{
  "events": [
    {
      "event": "new_message",
      "account_id": "acct-001",
      "conversation_id": "conv-001",
      "message_id": "msg-123",
      "direction": "inbound",
      "preview": "你好，我想查询...",
      "created_at": "2026-06-13T17:05:00Z"
    },
    {
      "event": "status_change",
      "account_id": "acct-001",
      "conversation_id": "conv-002",
      "management_mode": "human_managed",
      "created_at": "2026-06-13T17:06:00Z"
    },
    {
      "event": "handover",
      "account_id": "acct-001",
      "conversation_id": "conv-003",
      "from_mode": "ai_managed",
      "to_mode": "human_managed",
      "agent_id": "agent-001",
      "created_at": "2026-06-13T17:07:00Z"
    }
  ],
  "server_time": "2026-06-13T17:08:00Z"
}
```

### 实现方案

**新增 `app/api/routes/conversation_poll.py`**

```python
@router.get("/api/conversations/poll")
async def poll_conversation_events(
    since: str = Query(..., description="ISO8601 timestamp"),
    account_id: str | None = Query(None),
    actor: RequestActor = Depends(get_request_actor),
    session: Session = Depends(get_db_session),
) -> PollResponse:
    """Return events that occurred after `since` timestamp."""
    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))

    events = []

    # 1. 新消息 (from messages table)
    msg_query = (
        select(Message)
        .where(Message.created_at > since_dt)
        .order_by(Message.created_at.asc())
        .limit(50)
    )
    if account_id:
        msg_query = msg_query.where(Message.account_id == account_id)

    for msg in session.scalars(msg_query).all():
        events.append({
            "event": "new_message",
            "account_id": msg.account_id,
            "conversation_id": msg.conversation_id,
            "message_id": msg.id,
            "direction": msg.direction,
            "preview": (msg.text or "")[:100],
            "created_at": msg.created_at.isoformat(),
        })

    # 2. 状态变更 (from handover_logs table)
    ho_query = (
        select(HandoverLog)
        .where(HandoverLog.created_at > since_dt)
        .order_by(HandoverLog.created_at.asc())
        .limit(20)
    )
    if account_id:
        ho_query = ho_query.where(HandoverLog.account_id == account_id)

    for log in session.scalars(ho_query).all():
        events.append({
            "event": "handover",
            "account_id": log.account_id,
            "conversation_id": log.conversation_id,
            "from_mode": log.from_mode,
            "to_mode": log.to_mode,
            "agent_id": log.actor_id,
            "created_at": log.created_at.isoformat(),
        })

    # 按时间排序
    events.sort(key=lambda e: e["created_at"])

    return {
        "events": events,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
```

**注册到 `app/main.py`**:
```python
from app.api.routes.conversation_poll import router as conversation_poll_router
app.include_router(conversation_poll_router)
```

### 测试

`tests/test_conversation_poll.py` — 6+ 测试:

1. 无新事件 → 返回空 events 列表
2. since 之后有新消息 → events 包含 new_message
3. since 之后有接管事件 → events 包含 handover
4. account_id 过滤正确
5. 事件按时间排序
6. since 格式错误 → 422

### 验收标准

1. `GET /api/conversations/poll?since=xxx` 返回 200
2. 返回正确的 events 列表
3. account_id 过滤生效
4. 6+ 测试通过
5. Docker 重启后验证可用

---

## RT-002：前端轮询适配验证（P0）

- **优先级**: P0
- **估计耗时**: 10 分钟

### 验证

前端 `chatRealtime.ts` 的轮询逻辑已经完备（第 280-330 行），无需修改前端代码。

验证步骤：
1. 后端部署后，打开 ChatPage
2. 浏览器 DevTools Network 面板应显示每 5 秒一次 `GET /api/conversations/poll?since=xxx`
3. 返回 200（不再是 404）
4. 使用另一个窗口发送 mock 入站消息
5. ChatPage 应在 5 秒内自动显示新消息

### 验收标准

1. 轮询请求返回 200
2. 新消息在 5 秒内出现在 ChatPage
3. `npm run build` 通过

---

## RT-003：SSE 端点占位（P2 — 可选）

- **优先级**: P2
- **估计耗时**: 15 分钟

### 目标

添加 SSE 端点占位，返回 501 Not Implemented，让前端明确知道 SSE 不可用并立即降级轮询（而不是等 EventSource 超时）。

```python
@router.get("/api/conversations/stream")
async def conversation_stream_placeholder():
    """SSE endpoint - not yet implemented, use polling fallback."""
    raise HTTPException(
        status_code=501,
        detail="SSE streaming not yet implemented. Use polling fallback."
    )
```

### 验收标准

1. `/api/conversations/stream` 返回 501（而非 404）
2. 前端 chatRealtime.ts 收到 501 后立即降级轮询

---

## 全量验证

```powershell
# 后端
.venv\Scripts\python.exe -m pytest tests/test_conversation_poll.py -q -x

# Docker 重启验证
docker compose up -d app
# 等待 15 秒
Invoke-WebRequest -Uri "http://localhost:8000/api/conversations/poll?since=2026-06-13T00:00:00Z" -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"} -UseBasicParsing
```

## 全局约束

1. **不碰前端代码**
2. **不碰 H5 相关**
3. **新代码有类型注解 + 异步 I/O**
4. **测试覆盖**
5. **一次性执行，不中途暂停**

---

## 发给后端会话的文本

```
你是后端开发 Agent（实时推送修复轮）。请读取 docs/task-plan-realtime-poll.md，按 RT-001 → RT-003 顺序一次性执行全部 3 个任务，不要中途暂停确认。

核心任务：
1. RT-001: 新增 GET /api/conversations/poll 端点（轮询，返回 since 之后的新消息和接管事件）
2. RT-002: 验证前端轮询适配（无需改前端，只需确认后端可用）
3. RT-003: 新增 GET /api/conversations/stream 返回 501（SSE 占位，让前端立即降级）

硬约束：
1. 不碰前端代码
2. 不碰 H5 相关
3. 新增端点需要 X-Actor-Id/X-Actor-Role 认证
4. 测试 6+ 通过

进度写入 .codex-run/progress/RT-XXX.json。开始吧。
```

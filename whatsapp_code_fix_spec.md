# WhatsApp 项目代码修复与完善执行文档

> 适用对象：把这份文档交给 Codex / Cursor / Claude Code / 其他代码 Agent，让它在你的本地项目中按优先级修复。  
> 范围限制：本次只做代码正确性、安全性、运行稳定性修复；不做仓库清理、不删除本地日志、不大规模重构前端、不新增业务功能。

---

## 0. 给代码 Agent 的总指令

你需要在当前 WhatsApp 项目中完成一轮后端核心修复。请严格遵守以下规则：

1. **优先修 P0/P1，不要先做风格重构。**
2. **每个问题尽量小范围修改。**不要因为一个 bug 去格式化整个文件或改动无关模块。
3. **必须补测试。**每个 P0/P1 修复至少补一个能防止回归的测试。
4. **不要依赖请求头伪造用户身份。**生产权限必须依赖 JWT / Bearer token。
5. **不要引入新的外部服务依赖。**Redis 已存在可以使用；如果测试环境没有 Redis，要用 fake provider 或 mock。
6. **如果发现现有测试依赖旧行为，先判断旧行为是否安全。**安全边界优先，不要为了旧测试保留生产漏洞。
7. **不要修改 `.gitignore`、日志文件、截图文件、README 清理等仓库卫生问题。**这些不在本轮范围内。
8. **完成后运行测试并输出结果。**至少运行 backend 单元测试和 app import 检查。

推荐执行顺序：

```text
P0-01 严格权限边界
P0-02 会话统计 SQL 条件 bug
P0-03 sleeping scanner worker bug
P1-01 Redis dead-letter 读取 bug
P1-02 Webhook 幂等去重生产化
P1-03 配置项 AI_CONFIG_ENCRYPTION_KEY 兼容
P1-04 webhook_signature_enabled 真正生效
P2-01 dev/mock 路由生产隔离
P2-02 DB session 自动 commit 策略收敛
P2-03 main.py 静态路径配置化
P3-01 main.py / frontend 大文件拆分，暂缓
```

---

## 1. 当前发现的核心问题总览

| ID | 优先级 | 问题 | 风险 | 涉及文件 |
|---|---:|---|---|---|
| P0-01 | 最高 | `require_permission()` 使用非 strict actor，生产可能信任 `X-Actor-*` 请求头 | 权限绕过 | `app/api/deps.py`, `app/core/auth.py`, tests |
| P0-02 | 最高 | conversation stats 对字符串状态使用 `.is_("open")` | SQL 错误 / 统计错误 | `app/api/routes/conversations.py`, tests |
| P0-03 | 最高 | `sleeping_scanner()` 中 `db.execute(Query.update())` 用法错误，且 offset 可能跳批 | worker 崩溃 / 漏处理 | `app/worker.py`, tests |
| P1-01 | 高 | Redis dead-letter list 用 `GET` 读取 | Redis WRONGTYPE / 队列页面报错 | `app/providers/queue/redis_provider.py`, tests |
| P1-02 | 高 | Webhook 去重用进程内 set | 多 worker / 重启后重复处理，内存增长 | `app/api/routes/webhooks.py`, `app/services/chat.py`, `app/db/models.py`, alembic |
| P1-03 | 高 | `AI_CONFIG_ENCRY_KEY` 拼写错误 | 配置不生效 | `app/core/settings.py`, tests |
| P1-04 | 高 | `webhook_signature_enabled` 配置存在但需要确认真正控制签名验证 | 生产 webhook 签名策略不清晰 | `app/api/routes/webhooks.py`, `app/core/settings.py`, tests |
| P2-01 | 中 | dev/mock 路由和鉴权白名单路径不一致，生产仍 include dev router | 未来鉴权/生产暴露风险 | `app/api/routes/dev.py`, `app/main.py`, auth whitelist 文件 |
| P2-02 | 中 | DB session 依赖默认自动 commit | 读接口也可能误提交 | `app/api/deps.py`, routes/services |
| P2-03 | 中 | `main.py` 硬编码 `/opt/whatsapp/...` 静态路径 | 本地/生产路径不一致 | `app/main.py`, `app/core/settings.py` |
| P3-01 | 低 | `main.py` 和前端 `api.ts` / `App.tsx` 过大 | 维护成本高 | 多文件，暂缓 |

---

## 2. P0-01：修复权限体系请求头伪造身份风险

### 2.1 问题描述

当前请求 actor 构建逻辑支持这些请求头：

```text
X-Actor-Id
X-Actor-Name
X-Actor-Role
X-Actor-Account-Ids
```

`_build_request_actor()` 在没有 Bearer token 时会读取这些 header。`require_permission()` 当前依赖 `get_request_actor()`，而不是 `get_strict_request_actor()`。这会导致使用 `Depends(require_permission(...))` 的正式接口可能接受伪造的 `X-Actor-Role: super_admin`。

### 2.2 目标行为

修复后必须满足：

1. 使用 `require_permission()` 的接口，在 `AUTH_REQUIRED=true` 且非 test/dev bypass 场景下，必须提供有效 Bearer token。
2. `X-Actor-*` header 只能用于本地开发或测试，不能作为生产权限依据。
3. 如果同时存在 JWT 和 `X-Actor-*` header，身份、角色、账号范围必须以 JWT 为准。
4. `TEST_MODE=true` 或 `AUTH_REQUIRED=false` 时，可以继续使用 local dev actor，避免破坏测试和本地开发。
5. 不要删除 `RequestActor`、`ActorRole`、`parse_account_ids()` 等现有抽象。

### 2.3 涉及文件

```text
app/api/deps.py
app/core/auth.py
tests/...
```

### 2.4 推荐修改方案

#### 第一步：让 `require_permission()` 使用 strict actor

把：

```python
def require_permission(permission_code: str):
    def dependency(actor: RequestActor = Depends(get_request_actor)) -> RequestActor:
        actor.require_permission(permission_code)
        return actor

    return dependency
```

改成：

```python
def require_permission(permission_code: str):
    def dependency(actor: RequestActor = Depends(get_strict_request_actor)) -> RequestActor:
        actor.require_permission(permission_code)
        return actor

    return dependency
```

这一步是最关键的。它会让所有基于 permission 的接口默认要求 Bearer token。

#### 第二步：限制 header actor 的使用场景

在 `_build_request_actor()` 内部，保留 JWT 优先逻辑，但对 header actor 增加环境限制。

建议增加类似逻辑：

```python
def _allows_header_actor(settings: Settings) -> bool:
    env = (settings.app_env or "").strip().lower()
    return (
        settings.test_mode
        or not settings.auth_required
        or env in {"development", "local", "dev"}
    )
```

然后在没有 token、但存在 header actor 的情况下检查：

```python
if not token_present:
    has_actor_headers = bool(actor_id or role_value or display_name or account_scope)
    if has_actor_headers and not _allows_header_actor(settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request actor headers are not accepted outside development/test mode.",
        )
```

注意：如果 `require_bearer_token=True` 且 `settings.auth_required=True`，应继续返回：

```python
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Bearer token is required.",
)
```

#### 第三步：避免破坏 public/mock/dev 流程

不要把所有 `get_request_actor()` 都替换成 `get_strict_request_actor()`。只需要确保：

```text
require_permission() -> get_strict_request_actor()
```

其他少数明确用于开发、mock、测试的接口可以继续使用 `get_request_actor()`，但必须受环境限制。

### 2.5 必须补的测试

新增或修改测试文件，例如：

```text
tests/test_auth_permissions.py
```

至少覆盖以下场景：

#### 测试 1：生产/正式鉴权时，伪造 header 不能通过权限接口

伪代码：

```python
def test_permission_endpoint_rejects_header_actor_without_bearer(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TEST_MODE", "false")

    response = client.get(
        "/api/conversations/stats",
        headers={
            "X-Actor-Id": "attacker",
            "X-Actor-Role": "super_admin",
            "X-Actor-Account-Ids": "*",
        },
    )

    assert response.status_code in {401, 403}
```

#### 测试 2：没有 Bearer token 时，`require_permission()` 返回 401

```python
def test_permission_endpoint_requires_bearer_token(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("APP_ENV", "production")

    response = client.get("/api/conversations/stats")

    assert response.status_code == 401
```

#### 测试 3：test mode / auth disabled 不被破坏

```python
def test_permission_endpoint_allows_local_dev_actor_when_auth_disabled(client, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("TEST_MODE", "true")

    response = client.get("/api/conversations/stats")

    assert response.status_code != 401
```

如果项目已有 `auth_headers` fixture，优先使用已有 fixture 生成合法 JWT，而不是新造重复逻辑。

### 2.6 验收标准

- 伪造 `X-Actor-Role: super_admin` 不能访问权限接口。
- 合法 Bearer token 仍能访问。
- 测试环境不会因为 strict actor 全面失败。
- 现有路由中所有 `Depends(require_permission(...))` 自动获得更严格保护。

---

## 3. P0-02：修复 conversation stats SQL 条件 bug

### 3.1 问题描述

`get_conversation_stats()` 内部的 `_count(**filters)` 逻辑对所有字段都使用：

```python
col.is_(v)
```

但是调用时可能传入：

```python
status="open"
```

`is_()` 适合 `NULL` 或 boolean，不适合普通字符串。对 PostgreSQL 来说，`status IS 'open'` 不是期望写法，可能产生 SQL 错误或不可移植行为。

### 3.2 目标行为

1. bool 和 None 使用 `.is_(value)`。
2. 字符串、数字、枚举等普通值使用 `== value`。
3. 统计接口在 PostgreSQL 和 SQLite 测试环境都能跑。
4. 不改变 stats 返回字段含义。

### 3.3 涉及文件

```text
app/api/routes/conversations.py
tests/...
```

### 3.4 推荐修改方案

在 `get_conversation_stats()` 附近增加一个小 helper：

```python
def _apply_equal_filter(statement, column, value):
    if value is None or isinstance(value, bool):
        return statement.where(column.is_(value))
    return statement.where(column == value)
```

然后把原来的：

```python
for key, v in filters.items():
    col = getattr(Conversation, key)
    q = q.where(col.is_(v))
```

改成：

```python
for key, value in filters.items():
    col = getattr(Conversation, key)
    q = _apply_equal_filter(q, col, value)
```

如果项目 lint 对未标注类型敏感，可以加类型，但不要为了类型标注大改本文件。

### 3.5 必须补的测试

新增测试，例如：

```text
tests/test_conversation_stats.py
```

至少覆盖：

```python
def test_conversation_stats_supports_string_status_filter(client, auth_headers):
    response = client.get("/api/conversations/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
```

更好的测试：插入 2 条 conversation：

```text
open + is_sleeping=false
closed + is_sleeping=false
```

然后断言：

```python
assert data["open_conversations"] == 1
```

字段名以实际 schema 为准。

### 3.6 验收标准

- `/api/conversations/stats` 不再生成对字符串使用 `.is_()` 的 SQL。
- bool 条件例如 `is_sleeping=False` 仍正常。
- 测试覆盖字符串 status 过滤。

---

## 4. P0-03：修复 sleeping scanner worker bug

### 4.1 问题描述

`app/worker.py` 的 `sleeping_scanner()` 里存在两个问题：

#### 问题 A：错误使用 `db.execute(Query.update())`

类似代码：

```python
db.execute(
    db.query(db_models.Message)
    .filter(...)
    .update({"is_cold": True}, synchronize_session=False)
)
```

`Query.update()` 已经执行并返回 rowcount，不是 SQL statement。再传给 `db.execute()` 会导致运行时错误。

#### 问题 B：offset 可能跳过记录

循环中用：

```python
offset += batch_size
```

但每一轮会把当前记录更新为 `is_sleeping=True`，下一次查询条件变了，再使用 offset 会跳过一批仍符合旧条件的记录。

### 4.2 目标行为

1. scanner 能稳定扫描所有超时 conversation。
2. 不使用 `db.execute(Query.update())` 这种错误写法。
3. 不使用 offset 跳过已经变化的数据集。
4. 每批处理后 commit，失败时 rollback。
5. 处理结果要可观测：记录 marked count / error log。

### 4.3 涉及文件

```text
app/worker.py
tests/...
```

### 4.4 推荐修改方案

把 offset 分页改成“每次取第一批，直到没有”：

```python
while True:
    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.is_sleeping.is_(False),
            Conversation.status == "open",
            Conversation.last_customer_message_at.isnot(None),
            Conversation.last_customer_message_at < threshold,
        )
        .order_by(Conversation.account_id, Conversation.id)
        .limit(batch_size)
        .all()
    )

    if not conversations:
        break

    for conv in conversations:
        conv.is_sleeping = True

        db.query(db_models.Message).filter(
            db_models.Message.conversation_id == conv.id,
            db_models.Message.is_cold.is_(False),
            db_models.Message.created_at < threshold,
        ).update({"is_cold": True}, synchronize_session=False)

        db.add(conv)

    db.commit()
    total_marked += len(conversations)
```

或者使用 SQLAlchemy Core `update()`：

```python
from sqlalchemy import update

stmt = (
    update(db_models.Message)
    .where(
        db_models.Message.conversation_id == conv.id,
        db_models.Message.is_cold.is_(False),
        db_models.Message.created_at < threshold,
    )
    .values(is_cold=True)
)
db.execute(stmt)
```

二选一即可。不要混用 `Query.update()` 和 `db.execute()`。

### 4.5 必须补的测试

新增测试，例如：

```text
tests/test_sleeping_scanner.py
```

至少覆盖：

#### 测试 1：scanner 会标记所有符合条件的 conversation

准备 3 条 conversation：

```text
A: open, not sleeping, last_customer_message_at < threshold
B: open, not sleeping, last_customer_message_at < threshold
C: open, not sleeping, last_customer_message_at >= threshold
```

执行 scanner 一轮后：

```text
A.is_sleeping == True
B.is_sleeping == True
C.is_sleeping == False
```

这个测试能防止 offset 跳批。

#### 测试 2：旧消息被标记 is_cold

准备 conversation A 下两条消息：

```text
old message: created_at < threshold, is_cold=False
new message: created_at >= threshold, is_cold=False
```

执行后：

```text
old message.is_cold == True
new message.is_cold == False
```

### 4.6 验收标准

- scanner 不再因为 `db.execute(rowcount)` 崩溃。
- 多条符合条件的 conversation 不会漏处理。
- 消息冷标记逻辑正常。
- scanner 可重复运行，多次运行不会重复产生错误。

---

## 5. P1-01：修复 Redis dead-letter 读取 bug

### 5.1 问题描述

`move_to_dead_letter()` 把 job id push 到 list：

```python
pipe.rpush(self._dead_letter_key(queue_name), job.job_id)
```

但 `list_dead_letter_jobs()` 里对 `queue:dead:*` key 使用：

```python
payload = self._client.get(key)
```

这是错误的。dead-letter key 是 list，不是 string。Redis 会返回 WRONGTYPE。

### 5.2 目标行为

1. `list_dead_letter_jobs()` 能读取 dead-letter list 中的 job ids。
2. 根据 job id 再读取 `queue:job:{job_id}`。
3. 支持传入 `queue_name` 只读取指定 queue。
4. 忽略已经不存在的 job payload，不要整个接口崩溃。

### 5.3 涉及文件

```text
app/providers/queue/redis_provider.py
tests/...
```

### 5.4 推荐修改方案

把 `list_dead_letter_jobs()` 改成：

```python
def list_dead_letter_jobs(self, queue_name: QueueName | None = None) -> list[QueueJob]:
    jobs: list[QueueJob] = []

    if queue_name is not None:
        dead_keys = [self._dead_letter_key(queue_name)]
    else:
        dead_keys = list(self._client.scan_iter(match="queue:*:dead_letter"))

    for dead_key in dead_keys:
        job_ids = self._client.lrange(dead_key, 0, -1)
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job is not None:
                jobs.append(job)

    return jobs
```

注意当前 `_dead_letter_key()` 返回的是：

```python
f"queue:{queue_name}:dead_letter"
```

所以 scan pattern 应该匹配：

```text
queue:*:dead_letter
```

不要写成 `queue:dead:*`。

### 5.5 必须补的测试

新增或修改 Redis provider 测试：

```python
def test_redis_list_dead_letter_jobs_reads_list_entries(redis_provider):
    job = redis_provider.enqueue("ai_generation", {"x": 1}, max_retries=3)
    redis_provider.move_to_dead_letter("ai_generation", job)

    dead_jobs = redis_provider.list_dead_letter_jobs("ai_generation")

    assert [j.job_id for j in dead_jobs] == [job.job_id]
    assert dead_jobs[0].status == "dead_letter"
```

如果没有真实 Redis 测试环境，使用 fake redis / mock redis，或在现有 queue provider 测试风格下补。

### 5.6 验收标准

- `list_dead_letter_jobs()` 不再对 list key 执行 GET。
- 队列管理接口能正常展示 dead-letter jobs。
- 指定 queue 和全部 queue 两种模式都能工作。

---

## 6. P1-02：Webhook 去重从内存 set 改为生产可用幂等

### 6.1 问题描述

`webhooks.py` 里有模块级 set：

```python
_deduplicated_message_ids: set[str] = set()
```

并通过：

```python
_is_message_deduplicated()
_mark_message_processed()
```

做去重。

问题：

1. 多 worker / 多容器时，每个进程一份 set，不能全局去重。
2. 服务重启后 set 清空，重复 webhook 会再次处理。
3. set 没有 TTL，会持续增长。
4. `uvicorn_workers=4` 时尤其明显。

### 6.2 目标行为

1. Webhook 消息处理必须具备持久幂等。
2. 同一个 account/provider message id 重复到达，只能创建一条 inbound message。
3. 多 worker 并发下也不能重复创建。
4. 内存 set 不能作为生产去重依据。
5. 可以保留 `_reset_message_dedup()` 仅用于测试，但生产路径不要依赖它。

### 6.3 涉及文件

```text
app/api/routes/webhooks.py
app/services/chat.py
app/db/models.py
alembic/versions/...
tests/...
```

### 6.4 推荐修改方案

#### 第一步：检查 Message 模型是否已有 provider message id 字段

先在 `app/db/models.py` 中确认 `Message` 模型是否已有类似字段：

```text
provider_message_id
external_message_id
whatsapp_message_id
```

如果已有 `provider_message_id`，优先复用。

如果没有，新增字段：

```python
provider_message_id = Column(String(255), nullable=True, index=True)
```

字段名要和现有 service / schema 保持一致，优先不要改已有字段名。

#### 第二步：增加数据库唯一约束或唯一索引

目标是同一 account 下 provider message id 唯一：

```text
(account_id, provider_message_id)
```

推荐 PostgreSQL / SQLite 兼容的 Alembic migration：

```python
op.create_index(
    "uq_messages_account_provider_message_id",
    "messages",
    ["account_id", "provider_message_id"],
    unique=True,
    postgresql_where=sa.text("provider_message_id IS NOT NULL"),
    sqlite_where=sa.text("provider_message_id IS NOT NULL"),
)
```

如果当前表名不是 `messages`，以实际表名为准。

如果已有唯一约束，不要重复创建。

#### 第三步：在 message 创建路径中处理 IntegrityError

在 `process_inbound_message()` 或实际创建 inbound message 的 service 中：

1. 创建前先查一次是否已存在。
2. 创建时仍依赖 DB unique index 做最终保护。
3. 捕获 `IntegrityError`，rollback 后返回已存在记录或返回“已去重”。

伪代码：

```python
existing = find_message_by_provider_message_id(
    account_id=account_id,
    provider_message_id=provider_message_id,
)
if existing:
    return existing

try:
    create_message(...)
    db.commit()
except IntegrityError:
    db.rollback()
    existing = find_message_by_provider_message_id(...)
    if existing:
        return existing
    raise
```

#### 第四步：webhook 入口层移除或降级内存 set

在 `webhooks.py` 中：

- 不要用 `_deduplicated_message_ids` 判断是否跳过生产处理。
- 可以保留 helper 作为测试辅助，但生产主路径应依赖 service/DB 幂等。
- 如果仍想提前挡重复请求，使用 Redis TTL lock，但不能替代 DB unique index。

Redis TTL lock 可选：

```python
def mark_webhook_seen(redis, account_id: str, provider_message_id: str) -> bool:
    key = f"whatsapp:webhook:seen:{account_id}:{provider_message_id}"
    return bool(redis.set(key, "1", nx=True, ex=7 * 24 * 60 * 60))
```

如果 Redis 不可用，不应导致 webhook 直接失败；DB unique index 是最终防线。

### 6.5 必须补的测试

#### 测试 1：重复 webhook 只创建一条 message

```python
def test_duplicate_webhook_message_is_idempotent(client, db_session, webhook_payload):
    response1 = client.post("/webhooks/whatsapp/...", json=webhook_payload)
    response2 = client.post("/webhooks/whatsapp/...", json=webhook_payload)

    assert response1.status_code in {200, 204}
    assert response2.status_code in {200, 204}

    messages = query_messages_by_provider_message_id(...)
    assert len(messages) == 1
```

#### 测试 2：并发插入时数据库唯一约束生效

如果测试框架支持并发，做并发测试；否则直接测试 unique index：

```python
with pytest.raises(IntegrityError):
    insert_duplicate_provider_message_id()
```

然后 service 层测试捕获 IntegrityError 后能返回 existing message。

### 6.6 验收标准

- 生产路径不依赖 `_deduplicated_message_ids`。
- 同一 `account_id + provider_message_id` 不会产生多条 inbound message。
- 多 worker / 重启后仍能去重。
- migration 可执行，测试数据库可创建唯一索引。

---

## 7. P1-03：修复 AI 配置加密 key 环境变量拼写

### 7.1 问题描述

`settings.py` 当前配置：

```python
ai_config_encryption_key: str = Field(default="", alias="AI_CONFIG_ENCRY_KEY")
```

`ENCRY` 拼写不完整。正常使用者会设置：

```text
AI_CONFIG_ENCRYPTION_KEY
```

结果不会生效。

### 7.2 目标行为

1. 新环境变量 `AI_CONFIG_ENCRYPTION_KEY` 生效。
2. 兼容旧变量 `AI_CONFIG_ENCRY_KEY`，避免已有环境被破坏。
3. 优先使用新变量。

### 7.3 涉及文件

```text
app/core/settings.py
tests/...
.env.example 可选
```

### 7.4 推荐修改方案

如果项目使用 Pydantic v2，使用 `AliasChoices`：

```python
from pydantic import AliasChoices, Field
```

然后改为：

```python
ai_config_encryption_key: str = Field(
    default="",
    validation_alias=AliasChoices(
        "AI_CONFIG_ENCRYPTION_KEY",
        "AI_CONFIG_ENCRY_KEY",
    ),
)
```

注意：当前文件很多字段用的是 `alias=`。这里可以单独使用 `validation_alias=`，只要测试通过即可。

如果 Pydantic 版本不支持 `AliasChoices`，则用 model validator 或自定义 settings 初始化逻辑兼容两个变量。

### 7.5 必须补的测试

```python
def test_ai_config_encryption_key_prefers_correct_env_name(monkeypatch):
    monkeypatch.setenv("AI_CONFIG_ENCRYPTION_KEY", "new-key")
    monkeypatch.delenv("AI_CONFIG_ENCRY_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "new-key"
```

兼容旧变量：

```python
def test_ai_config_encryption_key_supports_legacy_typo(monkeypatch):
    monkeypatch.delenv("AI_CONFIG_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("AI_CONFIG_ENCRY_KEY", "legacy-key")

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "legacy-key"
```

如果两个都存在，优先新变量：

```python
def test_ai_config_encryption_key_prefers_new_over_legacy(monkeypatch):
    monkeypatch.setenv("AI_CONFIG_ENCRYPTION_KEY", "new-key")
    monkeypatch.setenv("AI_CONFIG_ENCRY_KEY", "legacy-key")

    settings = Settings(_env_file=None)

    assert settings.ai_config_encryption_key == "new-key"
```

### 7.6 验收标准

- `AI_CONFIG_ENCRYPTION_KEY` 可以生效。
- `AI_CONFIG_ENCRY_KEY` 仍兼容。
- 不破坏其他 settings 字段。

---

## 8. P1-04：让 webhook_signature_enabled 配置真正控制签名验证

### 8.1 问题描述

`Settings` 中存在：

```python
webhook_signature_enabled: bool = Field(default=True, alias="WEBHOOK_SIGNATURE_ENABLED")
```

但需要确认 `webhooks.py` 中实际签名验证逻辑是否使用这个开关。如果配置存在但生产路径没用，会导致安全策略不清晰。

### 8.2 目标行为

1. `WEBHOOK_SIGNATURE_ENABLED=true` 时必须验证签名。
2. `WEBHOOK_SIGNATURE_ENABLED=false` 只能在 development/test/mock 场景允许跳过。
3. `APP_ENV=production` 时，不允许关闭 webhook 签名验证。
4. 验证失败要返回 401/403，并记录 metric/log。

### 8.3 涉及文件

```text
app/api/routes/webhooks.py
app/core/settings.py
tests/...
```

### 8.4 推荐修改方案

在 webhook 签名验证入口处增加统一判断：

```python
def _should_verify_webhook_signature(settings: Settings) -> bool:
    if settings.app_env.strip().lower() == "production":
        return True
    return bool(settings.webhook_signature_enabled)
```

然后使用：

```python
if _should_verify_webhook_signature(settings):
    verify_signature_or_raise(...)
else:
    logger.warning(
        "webhook_signature_verification_disabled",
        app_env=settings.app_env,
        messaging_provider=settings.messaging_provider,
    )
```

更严格的方案是在 production 启动时直接报错：

```python
if settings.app_env == "production" and not settings.webhook_signature_enabled:
    raise RuntimeError("WEBHOOK_SIGNATURE_ENABLED cannot be false in production.")
```

如果担心影响现有生产启动，可先在 webhook 请求时强制验证，而不是启动时报错。

### 8.5 必须补的测试

```python
def test_webhook_signature_forced_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WEBHOOK_SIGNATURE_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is True
```

```python
def test_webhook_signature_can_be_disabled_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WEBHOOK_SIGNATURE_ENABLED", "false")

    settings = Settings(_env_file=None)

    assert _should_verify_webhook_signature(settings) is False
```

接口测试：

- production + invalid signature -> 401/403
- development + disabled signature -> 可通过到下一步逻辑

### 8.6 验收标准

- 签名开关行为明确。
- 生产环境不能关闭签名验证。
- 测试覆盖 production 强制验证。

---

## 9. P2-01：隔离 dev/mock 路由，修正路径白名单不一致

### 9.1 问题描述

`dev.py` 的 router prefix 是：

```python
prefix="/dev"
```

但某些鉴权白名单可能判断：

```python
/api/dev/mock/
```

路径不一致，容易导致未来全局鉴权时出现“以为放行了但没放行”或“放行了错误路径”。此外，`main.py` 当前直接 include dev router，生产 app 中也注册 dev 路由，只靠 route 内部判断风险较高。

### 9.2 目标行为

1. dev/mock 路由只在 development/test 环境注册。
2. production 环境不注册 dev router，访问应返回 404。
3. 如果确实需要生产保留某个诊断接口，必须单独命名并加 strict auth，不要复用 `/dev/mock/...`。
4. 鉴权白名单路径和实际 router prefix 保持一致。

### 9.3 涉及文件

```text
app/main.py
app/api/routes/dev.py
app/core/admin_auth.py 或实际白名单文件
tests/...
```

### 9.4 推荐修改方案

在 `main.py` 注册 router 时改成：

```python
if settings.app_env.strip().lower() != "production" or settings.test_mode:
    app.include_router(dev_router)
```

如果当前 `settings` 已在 `app = FastAPI(...)` 前初始化，可以直接复用。

然后统一白名单路径：

- 如果保留 `prefix="/dev"`，白名单写 `/dev/mock/`。
- 如果要走 `/api/dev`，则把 router prefix 改成 `prefix="/api/dev"`，并同步所有前端/测试调用。

推荐保留 `/dev`，但仅非生产注册。

### 9.5 必须补的测试

```python
def test_dev_router_not_registered_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TEST_MODE", "false")
    # import/recreate app according to existing test pattern
    response = client.post("/dev/mock/inbound-message", json={...})
    assert response.status_code == 404
```

```python
def test_dev_router_available_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    # 根据现有 dev endpoint 需要的 payload 构造
    response = client.post("/dev/mock/inbound-message", json={...})
    assert response.status_code != 404
```

### 9.6 验收标准

- production app 不包含 dev mock route。
- development/test 仍可使用 mock inbound。
- 白名单路径和实际路径一致。

---

## 10. P2-02：DB session 自动 commit 策略收敛

### 10.1 问题描述

当前 `get_db_session()` 在 `yield` 后自动：

```python
session.commit()
```

这会让所有使用这个 dependency 的接口，包括 GET/read-only 接口，在请求结束时都 commit。如果过程中 ORM 对象被误改，可能发生意外写入。

### 10.2 目标行为

最终目标：

1. 读接口不自动 commit。
2. 写操作在 service 层显式 commit，或使用明确的 transactional dependency。
3. rollback/close 行为清晰。

### 10.3 风险提示

这项不建议第一轮大改。因为当前项目可能很多 service 依赖 dependency 自动 commit。如果直接删除自动 commit，会导致大量写接口“看起来成功但没落库”。

### 10.4 推荐渐进方案

第一轮只新增两个 dependency，不替换全项目：

```python
def get_readonly_db_session() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
```

```python
def get_transactional_db_session() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

然后逐步把纯 GET 接口改成 `get_readonly_db_session()`。

不要一次性把 `get_db_session()` 行为改掉，除非已经全量确认所有 service 都显式 commit。

### 10.5 测试建议

选一个纯 GET 接口替换为 readonly session 后，确认：

```python
response = client.get("/api/conversations/stats", headers=auth_headers)
assert response.status_code == 200
```

选一个写接口确认仍能落库。

### 10.6 验收标准

- 本轮至少不要引入“写接口不 commit”的回归。
- 如果没有足够时间，P2-02 只写 TODO 和新增 dependency，不要大范围替换。

---

## 11. P2-03：把 main.py 静态目录从硬编码改为配置

### 11.1 问题描述

`main.py` 中存在硬编码：

```python
_static_dir = "/opt/whatsapp/static/templates"
_upload_dir = "/opt/whatsapp/uploads/templates"
```

这会让本地开发、Docker、生产环境路径不一致。

### 11.2 目标行为

1. 静态模板目录从 settings 读取。
2. 默认值兼容当前 Docker/生产布局。
3. 本地开发可通过 `.env` 配置。

### 11.3 涉及文件

```text
app/main.py
app/core/settings.py
.env.example 可选
tests/...
```

### 11.4 推荐修改方案

在 `Settings` 中新增：

```python
template_static_root: str = Field(
    default="/opt/whatsapp/static/templates",
    alias="TEMPLATE_STATIC_ROOT",
)
template_upload_root: str = Field(
    default="/opt/whatsapp/uploads/templates",
    alias="TEMPLATE_UPLOAD_ROOT",
)
```

然后 `main.py` 改成：

```python
from pathlib import Path

_static_dir = Path(settings.template_static_root).expanduser()
_upload_dir = Path(settings.template_upload_root).expanduser()
_static_dir.mkdir(parents=True, exist_ok=True)
_upload_dir.mkdir(parents=True, exist_ok=True)

app.mount("/templates", StaticFiles(directory=str(_static_dir)), name="templates")
```

注意：如果 upload dir 当前没有 mount，不要随便新增公开 mount，避免把用户上传内容暴露。

### 11.5 测试建议

```python
def test_template_static_root_from_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("TEMPLATE_STATIC_ROOT", str(tmp_path / "static"))
    settings = Settings(_env_file=None)
    assert settings.template_static_root == str(tmp_path / "static")
```

app import 检查：

```bash
python -c "from app.main import app; print(app.title)"
```

### 11.6 验收标准

- 不再硬编码 `/opt/whatsapp/static/templates`。
- 默认值保持兼容。
- app 可正常启动。

---

## 12. P3-01：main.py 和前端大文件拆分，暂缓

### 12.1 问题描述

`main.py` 一次性 import 和 include 大量 router；前端 `api.ts` / `App.tsx` 也过大。这会降低维护性，但不是当前最高风险。

### 12.2 本轮处理策略

本轮不要做大拆分。只允许：

1. 为 dev router 注册加环境判断。
2. 为静态路径引入 settings。
3. 不要重排全部 router。
4. 不要格式化整个 `main.py`。
5. 不要拆前端 `api.ts`，除非正在修复具体 bug。

### 12.3 后续建议

后续单独开重构任务：

```text
app/api/router.py
frontend/src/services/conversationsApi.ts
frontend/src/services/templatesApi.ts
frontend/src/services/metaAccountsApi.ts
frontend/src/app/AdminShell.tsx
```

但不要混入本轮 bugfix。

---

## 13. 统一测试与验收命令

代码 Agent 完成每个 P0/P1 后，至少运行相关测试。全部修复完成后，运行：

```bash
python -m pytest
python -m py_compile app/main.py
python -c "from app.main import app; print(app.title)"
```

如果项目依赖 editable install：

```bash
python -m pip install -e .[dev]
python -m pytest
```

如果修改了 Alembic migration：

```bash
alembic upgrade head
```

如果本地有 Docker：

```bash
docker compose config
```

本轮不要求前端 build，因为主要改后端；但如果改到了前端，必须运行：

```bash
cd frontend
npm run build
```

---

## 14. 完成后要求代码 Agent 输出的报告格式

让代码 Agent 完成后按这个格式汇报：

```text
已完成修复：
1. P0-01 strict permission actor
   - 修改文件：...
   - 测试：...
2. P0-02 conversation stats SQL comparator
   - 修改文件：...
   - 测试：...

未完成 / 延后：
- P2-02 DB session 自动 commit：原因 ...

测试结果：
- python -m pytest: 通过 / 失败，失败原因 ...
- python -c "from app.main import app": 通过 / 失败，失败原因 ...
- alembic upgrade head: 通过 / 未运行，原因 ...

需要人工确认：
- 是否接受 production 环境禁止关闭 WEBHOOK_SIGNATURE_ENABLED
- 是否添加 provider_message_id 唯一索引 migration
```

---

## 15. 一份可直接复制给 AI 的执行 prompt

下面这段可以直接复制给代码 Agent：

```text
你现在在我的 WhatsApp 项目本地仓库中工作。请只做代码正确性、安全性和运行稳定性修复，不做仓库清理、不删除日志、不重构前端大文件、不新增业务功能。

按以下顺序执行：

1. 修复 app/api/deps.py 的权限边界：require_permission() 必须依赖 get_strict_request_actor；生产/正式鉴权时不能接受 X-Actor-* 请求头伪造身份。保留 TEST_MODE=true 或 AUTH_REQUIRED=false 的本地开发能力。补测试证明伪造 X-Actor-Role: super_admin 无法访问权限接口。

2. 修复 app/api/routes/conversations.py 中 stats 统计条件：bool/None 用 .is_()，字符串状态例如 status="open" 用 ==。补测试覆盖 /api/conversations/stats。

3. 修复 app/worker.py 的 sleeping_scanner：不要使用 db.execute(Query.update())；不要用 offset 翻页处理会被更新的数据集；改成每次取第一批直到没有。补测试证明多条符合条件的 conversation 不会跳批，旧消息会被标记 is_cold。

4. 修复 app/providers/queue/redis_provider.py 的 list_dead_letter_jobs：dead-letter key 是 list，要用 lrange 取 job ids，再用 get_job(job_id) 取 payload；scan pattern 应匹配 queue:*:dead_letter。补测试。

5. 将 app/api/routes/webhooks.py 的 webhook 去重从进程内 set 升级为生产可用幂等：优先使用 DB 唯一索引 account_id + provider_message_id，并在 service 层捕获 IntegrityError 返回已有记录。内存 set 不得作为生产去重依据。必要时添加 Alembic migration。补重复 webhook 只创建一条 message 的测试。

6. 修复 app/core/settings.py 的 AI_CONFIG_ENCRY_KEY 拼写问题：新增 AI_CONFIG_ENCRYPTION_KEY 支持，并兼容旧的 AI_CONFIG_ENCRY_KEY，优先使用新变量。补 settings 测试。

7. 检查并修复 webhook_signature_enabled：production 环境必须强制验证 webhook 签名，即使 WEBHOOK_SIGNATURE_ENABLED=false；development/test 可以关闭。补测试。

8. P2 项只做小范围：production 环境不要注册 dev mock router；静态模板目录从 settings 读取。不要大规模拆 main.py 或前端 api.ts。

每个 P0/P1 修复都要有测试。不要格式化无关文件。完成后运行：
python -m pytest
python -m py_compile app/main.py
python -c "from app.main import app; print(app.title)"
如果加了 migration，运行 alembic upgrade head。

最后按“已完成、未完成、测试结果、需要人工确认”四部分汇报。
```

---

## 16. 人工确认点

在让 AI 开始前，你最好决定这几个策略：

1. **production 是否绝对禁止 header actor？**  
   建议：禁止。

2. **production 是否绝对强制 webhook signature？**  
   建议：强制。

3. **Webhook 去重唯一键用什么字段？**  
   建议：`account_id + provider_message_id`。如果模型里已有 `external_message_id` 或 `whatsapp_message_id`，优先复用已有字段名，避免重复字段。

4. **DB session 自动 commit 是否本轮大改？**  
   建议：本轮不要大改，只新增 readonly/transactional dependency，后续逐步迁移。

5. **dev router 路径是否保持 `/dev`？**  
   建议：保持 `/dev`，但只在非 production 注册。

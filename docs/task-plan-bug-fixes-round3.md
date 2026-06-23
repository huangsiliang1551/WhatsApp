# 营销核心缺口修复（BUG-004 ~ BUG-007）

> **执行角色**: api_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 修复 E2E Round 3 发现的 4 个功能缺口

---

## BUG-004：用户注册串联任务触发引擎

- **严重度**: P1
- **发现位置**: E2E-007（注册触发规则未生效）
- **估计耗时**: 30 分钟

### 问题描述

`platform_service.py` 中 `create_user()` 方法创建用户后，没有调用 `TaskEngine.on_user_registered()` 来触发注册类型的任务规则。导致创建了 `trigger_type="register"` 的规则后，新用户注册不会自动生成延迟任务。

### 修复方案

#### Step 1: 检查 platform_service.py 中 create_user 方法

```bash
# 查看 create_user 方法
grep -n "def create_user" app/services/platform_service.py
```

#### Step 2: 在 create_user 末尾添加触发引擎调用

在 `app/services/platform_service.py` 的 `create_user` 方法末尾（return 之前）添加：

```python
# 串联任务触发引擎
try:
    from app.services.task_engine import TaskEngine
    engine = TaskEngine(self._session)
    engine.on_user_registered(user_id=user.id, account_id=user.account_id)
except Exception as exc:
    import structlog
    structlog.get_logger().warning(
        "task_trigger_on_register_failed",
        user_id=user.id,
        account_id=user.account_id,
        error=str(exc),
    )
```

**注意**: 
- 使用 try/except 包裹，触发失败不影响用户注册
- 使用延迟 import 避免循环依赖
- 记录 warning 日志便于排查

#### Step 3: 检查 TaskEngine.on_user_registered 方法

确认 `app/services/task_engine.py` 中 `on_user_registered` 方法存在且逻辑正确：
1. 查询所有 `trigger_type="register"` 且 `is_enabled=True` 的规则
2. 为每个规则创建延迟任务（写入 Redis sorted set `delayed_tasks`）
3. 延迟时间从 `trigger_config.delay_minutes` 读取

#### Step 4: 重启 Docker

```bash
docker compose restart app
# 等待 20 秒
```

#### Step 5: 重新验证 E2E-007

```powershell
# 创建商品+包+注册触发规则（参考 E2E-007 文档）
# ...

# 创建新用户
$newUserId = "e2e-register-test-$(Get-Date -Format 'yyyyMMddHHmmss')"
Invoke-WebRequest -Uri "http://localhost:8000/api/platform/users" -Method POST -Headers $headers -Body "{`"account_id`":`"acct-h5-daily-cn`",`"public_user_id`":`"$newUserId`",`"display_name`":`"注册触发测试`",`"language_code`":`"zh-CN`",`"is_anonymous`":false,`"lifecycle_status`":`"new`"}" -UseBasicParsing

# 等待 65 秒（延迟 1 分钟 + 5 秒缓冲）
Start-Sleep -Seconds 65

# 检查延迟队列
docker exec whatsapp_app python -c "
import redis, json
r = redis.Redis(host='redis', port=6379, db=1)
jobs = r.zrange('delayed_tasks', 0, -1)
for j in jobs:
    data = json.loads(j)
    print(json.dumps(data))
"

# 再等 65 秒让调度器激活
Start-Sleep -Seconds 65

# 检查任务实例
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances?user_id=$newUserId" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).items
# 应存在 status="running" 的 package 类型实例
```

**验证**: 找到自动生成的任务实例。

---

## BUG-005：商品任务完成处理后续推链

- **严重度**: P1
- **发现位置**: E2E-008（完成任务后未触发后续推送）
- **估计耗时**: 40 分钟

### 问题描述

`task_engine.py` 中 `complete_product()` 方法在标记所有商品完成后，没有检查规则的 `follow_up_chain` 字段，也没有将后续任务排入延迟队列。

### 修复方案

#### Step 1: 检查 complete_product 方法

```bash
grep -n "def complete_product" app/services/task_engine.py
```

#### Step 2: 在 complete_product 末尾添加后续推链处理

在 `app/services/task_engine.py` 的 `complete_product` 方法中，当所有商品完成时（status 变为 "completed"），添加：

```python
# 检查后续推链
if inst.status == "completed":
    rule = self._session.get(TaskRule, inst.rule_id)
    if rule and rule.follow_up_chain:
        import json, time
        for step in rule.follow_up_chain:
            delay_days = step.get("delay_days", 1)
            next_rule_id = step.get("rule_id")
            if next_rule_id:
                # 计算触发时间
                trigger_at = time.time() + (delay_days * 86400)
                job = {
                    "task_instance_id": None,  # 待创建
                    "rule_id": next_rule_id,
                    "user_id": inst.user_id,
                    "account_id": inst.account_id,
                    "trigger_at": trigger_at,
                    "source_task_id": inst.id,
                }
                self._redis.zadd("delayed_tasks", {json.dumps(job): trigger_at})
```

**注意**:
- 延迟时间 = `delay_days * 86400` 秒
- 任务实例尚未创建，只排入规则信息，由调度器在触发时创建实例
- 记录 source_task_id 便于追踪来源

#### Step 3: 修改调度器处理后续推链

在 `app/services/task_scheduler.py` 的 `_process_delayed_tasks` 方法中，处理 `rule_id` 类型的延迟任务：

```python
async def _process_delayed_tasks(self):
    now = time.time()
    jobs = await self._redis.zrangebyscore("delayed_tasks", 0, now)
    if not jobs:
        return
    for job_raw in jobs:
        try:
            job = json.loads(job_raw)
            # 类型 1: 已有 task_instance_id（直接激活）
            if job.get("task_instance_id"):
                # ... 现有逻辑 ...
                pass
            # 类型 2: 有 rule_id（创建新实例）
            elif job.get("rule_id"):
                rule_id = job["rule_id"]
                user_id = job["user_id"]
                account_id = job["account_id"]
                session = SessionLocal()
                try:
                    engine = TaskEngine(session)
                    instances = engine.manual_push(
                        rule_id=rule_id,
                        user_ids=[user_id],
                        account_id=account_id,
                    )
                    session.commit()
                finally:
                    session.close()
            await self._redis.zrem("delayed_tasks", job_raw)
        except Exception as exc:
            logger.error("delayed_task_processing_failed", error=str(exc))
```

#### Step 4: 重启 Docker

```bash
docker compose restart app
# 等待 20 秒
```

#### Step 5: 重新验证 E2E-008

```powershell
# 创建包A+包B+规则B+规则A(含follow_up_chain→规则B)
# ...（参考 E2E-008 文档）

# 推送规则A给测试用户
# ...

# 完成任务A的所有商品
# ...

# 验证任务A完成
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/task-instances/$TASK_A_ID" -Headers $headers -UseBasicParsing
($r.Content | ConvertFrom-Json).status  # 应为 "completed"

# 检查后续推链是否排入延迟队列
docker exec whatsapp_app python -c "
import redis, json
r = redis.Redis(host='redis', port=6379, db=1)
jobs = r.zrange('delayed_tasks', 0, -1)
for j in jobs:
    data = json.loads(j)
    print(json.dumps(data))
"
# 应找到包含 RULE_B_ID 的延迟任务
```

**验证**: 找到后续推链的延迟任务。

---

## BUG-006：规则删除有关联实例时返回 500

- **严重度**: P2
- **发现位置**: E2E-015（删除有任务的规则返回 500）
- **估计耗时**: 15 分钟

### 问题描述

`task_rule_service.py` 中 `delete_rule()` 方法在规则有关联任务实例时，数据库 FK 约束导致 500 错误，应返回 409。

### 修复方案

#### Step 1: 修改 delete_rule 方法

在 `app/services/task_rule_service.py` 的 `delete_rule` 方法中添加关联检查：

```python
def delete_rule(self, rule_id: str) -> None:
    rule = self._session.get(TaskRule, rule_id)
    if not rule:
        raise LookupError(f"Task rule '{rule_id}' not found.")
    
    # 检查是否有关联任务实例
    from app.db.models import MktTaskInstance
    from sqlalchemy import select, func
    count = self._session.scalar(
        select(func.count(MktTaskInstance.id)).where(
            MktTaskInstance.rule_id == rule_id
        )
    ) or 0
    if count > 0:
        raise ValueError(
            f"Cannot delete rule '{rule.name}': {count} task instance(s) still reference it. "
            "Delete or expire all related task instances first."
        )
    
    self._session.delete(rule)
    self._session.commit()
```

#### Step 2: 验证路由层错误处理

确认 `app/api/routes/task_rules.py` 的 delete 端点已正确处理 `ValueError`：

```python
@router.delete("/{rule_id}", status_code=204)
async def delete_task_rule(rule_id, ...):
    svc = TaskRuleService(session)
    try:
        svc.delete_rule(rule_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc  # 已有
    return Response(status_code=204)
```

#### Step 3: 验证

```powershell
# 创建规则+推送任务
# ...

# 尝试删除有任务的规则
try {
    Invoke-WebRequest -Uri "http://localhost:8000/api/task-rules/$RULE_ID" -Method DELETE -Headers $headers -UseBasicParsing
} catch {
    $_.Exception.Response.StatusCode.value__  # 应为 409
    $_.ErrorDetails.Message  # 应包含 "task instance(s) still reference it"
}
```

**验证**: 返回 409 + 友好错误消息。

---

## BUG-007：assemble_preview 无 within_range 字段

- **严重度**: P2
- **发现位置**: E2E-014（返回 deviation_pct 但无 within_range）
- **估计耗时**: 10 分钟

### 问题描述

`product_package_service.py` 的 `preview_assemble` 方法返回 `deviation_pct` 但未返回 `within_range` 布尔值。前端需要 `within_range` 来判断是否在预算范围内。

### 修复方案

#### Step 1: 检查 AssemblePreviewResponse schema

```bash
grep -A 10 "class AssemblePreviewResponse" app/schemas/marketing.py
```

#### Step 2: 添加 within_range 字段

在 `app/schemas/marketing.py` 的 `AssemblePreviewResponse` 中添加：

```python
class AssemblePreviewResponse(BaseModel):
    items: list[ProductPackageItemResponse]
    total_amount: Decimal
    target_amount: Decimal
    deviation_pct: float
    within_range: bool  # 新增
    tolerance_pct: int
```

#### Step 3: 修改 preview_assemble 方法

在 `app/services/product_package_service.py` 的 `preview_assemble` 方法中计算 `within_range`：

```python
def preview_assemble(self, target_amount, tolerance_pct, product_count, account_id):
    # ... 现有凑包逻辑 ...
    
    deviation_pct = abs(float(total_amount - target_amount) / float(target_amount) * 100)
    within_range = deviation_pct <= tolerance_pct
    
    return AssemblePreviewResponse(
        items=items,
        total_amount=total_amount,
        target_amount=target_amount,
        deviation_pct=round(deviation_pct, 2),
        within_range=within_range,
        tolerance_pct=tolerance_pct,
    )
```

#### Step 4: 验证

```powershell
# 正常范围
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/assemble-preview?account_id=acct-h5-daily-cn" -Method POST -Headers $headers -Body '{"target_amount":99,"tolerance_pct":10,"product_count":3}' -UseBasicParsing
($r.Content | ConvertFrom-Json).within_range  # 应为 true

# 超出范围
$r = Invoke-WebRequest -Uri "http://localhost:8000/api/product-packages/assemble-preview?account_id=acct-h5-daily-cn" -Method POST -Headers $headers -Body '{"target_amount":1000,"tolerance_pct":10,"product_count":3}' -UseBasicParsing
($r.Content | ConvertFrom-Json).within_range  # 应为 false
```

**验证**: `within_range` 字段存在且值正确。

---

## 执行顺序

1. BUG-004（注册触发）→ 重启 → 验证 E2E-007
2. BUG-005（后续推链）→ 重启 → 验证 E2E-008
3. BUG-006（规则删除 409）→ 验证
4. BUG-007（within_range）→ 验证

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（营销缺口修复轮）。请读取 docs/task-plan-bug-fixes-round3.md，一次性修复 BUG-004 ~ BUG-007 全部 4 个 Bug，不要中途暂停。

修复内容：

BUG-004（P1，注册触发未串联）：
- 在 platform_service.py 的 create_user() 末尾添加 TaskEngine.on_user_registered() 调用
- try/except 包裹，失败不影响注册
- 重启后重新验证 E2E-007

BUG-005（P1，后续推链未处理）：
- 在 task_engine.py 的 complete_product() 中，任务完成时检查 follow_up_chain
- 将后续任务排入 Redis delayed_tasks（delay_days * 86400 秒）
- 修改 task_scheduler.py 处理 rule_id 类型的延迟任务
- 重启后重新验证 E2E-008

BUG-006（P2，规则删除 500→409）：
- 在 task_rule_service.py 的 delete_rule() 中检查关联 MktTaskInstance
- 有实例时抛出 ValueError → 路由层返回 409

BUG-007（P2，assemble_preview 无 within_range）：
- AssemblePreviewResponse schema 添加 within_range: bool 字段
- preview_assemble() 计算 within_range = deviation_pct <= tolerance_pct

约束：每个 Bug 修复后重启 Docker 并验证对应 E2E 流程。开始吧。
```

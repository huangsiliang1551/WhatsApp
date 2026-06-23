# 商城 + 任务联动系统 — 后端开发文档（MKT-BE）

> **执行角色**: api_agent + db_agent + queue_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现完整的商品管理、商品包管理、任务规则引擎、签到、邀请、余额扣减全链路

---

## 一、数据库模型设计

### 新增迁移: `0072_marketing_products_packages_tasks.py`

#### 1. products (商品)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| account_id | FK→accounts | 所属账号 |
| name | VARCHAR(200) | 商品名称 |
| image_asset_id | FK→media_assets NULL | 图片（复用 media_assets） |
| price | DECIMAL(12,2) | 单价 |
| tags | JSON | 标签列表 ["hot","new"] |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

索引: `ix_products_account_id`, `uq_products_name_account(account_id, name)`

#### 2. product_packages (商品包)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 包 ID（内部识别） |
| account_id | FK→accounts | 所属账号 |
| name | VARCHAR(200) | 包名称（展示用） |
| target_amount | DECIMAL(12,2) | 目标金额 |
| amount_tolerance_pct | INT DEFAULT 10 | 浮动百分比（默认 10%） |
| product_count | INT | 包内商品数量 |
| product_ids | JSON | 锁定的商品 ID 列表 |
| product_snapshot | JSON | 商品快照 [{id,name,price,image_url}] |
| total_value | DECIMAL(12,2) | 实际总价值 |
| completion_reward | DECIMAL(12,2) DEFAULT 0 | 完成全部商品后的额外奖励（进入任务余额） |
| created_at | DATETIME | 创建时间 |

#### 3. task_rules (任务规则)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 规则 ID |
| account_id | FK→accounts | 所属账号 |
| name | VARCHAR(200) | 规则名称 |
| rule_type | VARCHAR(32) | package_push / signin / invite |
| trigger_type | VARCHAR(32) | register / recharge / schedule / follow_up / manual |
| trigger_config | JSON | 触发配置（见下方） |
| package_id | FK→product_packages NULL | 关联商品包（package_push 类型） |
| follow_up_chain | JSON NULL | 完成后续推链 [{days:N, rule_id:xxx}] |
| expiry_config | JSON | 过期配置 {reset_at:"00:00", custom_hours:N} |
| is_enabled | BOOL DEFAULT TRUE | 启用/停用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**trigger_config 示例**:
```json
// register: 注册后 30 分钟
{"delay_minutes": 30}

// recharge: 充值满 50 元
{"threshold_amount": 50}

// schedule: 每天 10:00
{"cron_hour": 10, "cron_minute": 0, "filter_tags": ["VIP"], "exclude_claimed": true}

// follow_up: 由 follow_up_chain 字段控制

// manual: 无自动触发
{}
```

**expiry_config 示例**:
```json
// 每日 0:00 重置（默认）
{"reset_at": "00:00"}

// 自定义 48 小时过期
{"custom_hours": 48}
```

#### 4. task_instances (任务实例)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 实例 ID |
| account_id | FK→accounts | 所属账号 |
| user_id | FK→app_users | 目标用户 |
| rule_id | FK→task_rules | 来源规则 |
| package_id | FK→product_packages NULL | 商品包（package_push 类型） |
| task_type | VARCHAR(32) | package / signin / invite |
| status | VARCHAR(32) | pending / running / completed / failed / expired |
| product_progress | JSON NULL | 商品进度 [{product_id, status, paid_at}] |
| total_paid | DECIMAL(12,2) DEFAULT 0 | 已扣系统余额总额 |
| reward_amount | DECIMAL(12,2) DEFAULT 0 | 已完成奖励（进入任务余额） |
| created_at | DATETIME | 创建时间 |
| started_at | DATETIME NULL | 开始时间 |
| completed_at | DATETIME NULL | 完成时间 |
| expires_at | DATETIME NULL | 过期时间 |

索引: `ix_task_instances_user_status(user_id, status)`, `ix_task_instances_rule(rule_id)`

#### 5. sign_in_records (签到记录)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 记录 ID |
| account_id | FK→accounts | 所属账号 |
| user_id | FK→app_users | 用户 |
| sign_date | DATE | 签到日期 |
| consecutive_days | INT | 当次连续天数 |
| is_rewarded | BOOL DEFAULT FALSE | 是否已发放奖励 |
| created_at | DATETIME | 签到时间 |

唯一约束: `uq_sign_in_records_user_date(user_id, sign_date)`

#### 6. invite_records (邀请记录)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 记录 ID |
| account_id | FK→accounts | 所属账号 |
| inviter_user_id | FK→app_users | 邀请人 |
| invitee_user_id | FK→app_users | 被邀请人 |
| invite_type | VARCHAR(32) | register / recharge |
| reward_amount | DECIMAL(12,2) | 奖励金额 |
| is_rewarded | BOOL DEFAULT FALSE | 是否已发放 |
| created_at | DATETIME | 邀请时间 |

#### 7. invite_links (邀请链接)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 链接 ID |
| account_id | FK→accounts | 所属账号 |
| user_id | FK→app_users UNIQUE | 邀请人（每人一条） |
| invite_code | VARCHAR(32) UNIQUE | 邀请码 |
| created_at | DATETIME | 创建时间 |

#### 8. sign_in_config / invite_config (配置表)

```sql
-- 复用 system_settings 表，key 区分:
-- sign_in_consecutive_days = 7
-- sign_in_reward_amount = 5.00
-- invite_register_reward = 2.00
-- invite_recharge_threshold = 30
-- invite_recharge_reward = 3.00
-- invite_max_count = 20
-- anti_fraud_same_ip_limit = 3
-- anti_fraud_same_device_limit = 2
```

---

## 二、后端服务层设计

### 新增服务文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `app/services/product_service.py` | ~150 | 商品 CRUD + CSV 导入导出 + 删除保护 |
| `app/services/product_package_service.py` | ~200 | 商品包 CRUD + 自动凑包算法 + 统计 |
| `app/services/task_rule_service.py` | ~200 | 任务规则 CRUD + 触发链管理 |
| `app/services/task_engine.py` | ~300 | 任务触发引擎 + 实例生命周期 + 余额扣减 |
| `app/services/sign_in_service.py` | ~120 | 签到逻辑 + 连续天数计算 + 奖励发放 |
| `app/services/invite_service.py` | ~150 | 邀请链接 + 注册/充值触发 + 防刷 + 奖励 |
| `app/services/task_scheduler.py` | ~150 | Worker 定时任务：延迟触发 + 定时推送 + 过期扫描 |

### 核心算法

#### 凑包算法 (product_package_service.py)

```python
def assemble_package(self, target_amount, tolerance_pct, product_count) -> list[Product]:
    """
    从全部商品中随机选 product_count 个，使总价在
    [target_amount * (1 - tolerance_pct/100), target_amount * (1 + tolerance_pct/100)] 范围内。
    同一商品不重复。最多重试 100 次。凑不出则抛 ValueError。
    """
```

#### 任务触发引擎 (task_engine.py)

```python
async def on_user_registered(self, user_id, account_id):
    """扫描所有 register 触发规则，创建延迟任务"""
    for rule in self._get_enabled_rules(account_id, "register"):
        delay = rule.trigger_config["delay_minutes"]
        await self._schedule_task(rule, user_id, delay_minutes=delay)

async def on_user_recharged(self, user_id, account_id, amount):
    """扫描所有 recharge 触发规则，金额达标则创建任务"""
    for rule in self._get_enabled_rules(account_id, "recharge"):
        if amount >= rule.trigger_config["threshold_amount"]:
            await self._create_task_instance(rule, user_id)

async def on_task_completed(self, task_instance):
    """任务完成后检查 follow_up_chain，调度下一级"""
    rule = self._get_rule(task_instance.rule_id)
    if rule.follow_up_chain:
        for step in rule.follow_up_chain:
            await self._schedule_task(
                rule_id=step["rule_id"],
                user_id=task_instance.user_id,
                delay_days=step["days"],
            )

async def on_product_task_started(self, task_instance, product_id):
    """商品任务开始：扣减系统余额"""
    product = self._get_product(product_id)
    wallet = self._get_wallet(task_instance.user_id)
    if wallet.system_balance < product.price:
        raise InsufficientBalanceError(...)
    wallet.system_balance -= product.price
    # 记录 ledger: direction=debit, ledger_type=task_purchase
    self._update_product_progress(task_instance, product_id, "running")

async def on_product_task_completed(self, task_instance, product_id):
    """商品任务完成"""
    self._update_product_progress(task_instance, product_id, "completed")
    if self._all_products_completed(task_instance):
        # 发放完成奖励到任务余额
        wallet.task_balance += task_instance.package.completion_reward
        task_instance.status = "completed"
```

#### 签到服务 (sign_in_service.py)

```python
def sign_in(self, user_id, account_id) -> SignInResult:
    today = date.today()
    # 检查今天是否已签到
    existing = self._get_today_record(user_id, today)
    if existing:
        raise AlreadySignedInError()

    # 计算连续天数
    yesterday = today - timedelta(days=1)
    yesterday_record = self._get_record(user_id, yesterday)
    consecutive = (yesterday_record.consecutive_days + 1) if yesterday_record else 1

    # 检查是否已完成签到任务
    if self._is_signin_task_completed(user_id):
        raise SignInTaskAlreadyCompletedError()

    record = self._create_record(user_id, today, consecutive)

    # 检查是否达到奖励条件
    config_days = self._get_config("sign_in_consecutive_days")
    if consecutive >= config_days:
        reward = self._get_config("sign_in_reward_amount")
        self._reward_task_balance(user_id, reward, "sign_in_completion")
        self._mark_signin_task_completed(user_id)

    return SignInResult(consecutive_days=consecutive, rewarded=consecutive >= config_days)
```

#### 邀请防刷 (invite_service.py)

```python
def validate_invite(self, inviter_id, invitee_id, invitee_ip, invitee_device):
    # 1. 检查邀请上限
    count = self._count_invites(inviter_id)
    if count >= self._get_config("invite_max_count"):
        raise InviteLimitExceededError()

    # 2. 同 IP 限制
    ip_count = self._count_invites_by_ip(inviter_id, invitee_ip)
    if ip_count >= self._get_config("anti_fraud_same_ip_limit"):
        raise AntiFraudError("Same IP limit exceeded")

    # 3. 同设备限制
    device_count = self._count_invites_by_device(inviter_id, invitee_device)
    if device_count >= self._get_config("anti_fraud_same_device_limit"):
        raise AntiFraudError("Same device limit exceeded")
```

#### Worker 定时调度 (task_scheduler.py)

```python
async def run_scheduler_loop(self):
    """Worker 主循环：每 30 秒扫描一次"""
    while True:
        await self._process_delayed_tasks()    # 处理到期的延迟任务
        await self._process_scheduled_rules()  # 处理定时推送规则
        await self._expire_tasks()             # 过期未完成的任务
        await asyncio.sleep(30)

async def _process_delayed_tasks(self):
    """从 Redis sorted set 中取出到期任务"""
    now = time.time()
    jobs = await self.redis.zrangebyscore("delayed_tasks", 0, now)
    for job in jobs:
        await self._create_task_instance_from_job(job)
        await self.redis.zrem("delayed_tasks", job)

async def _process_scheduled_rules(self):
    """检查定时推送规则，按条件筛选用户创建任务"""
    rules = self._get_enabled_rules(trigger_type="schedule")
    for rule in rules:
        if self._should_fire_now(rule):
            users = self._filter_users(rule.trigger_config)
            for user in users:
                if not self._already_claimed(user, rule.package_id):
                    await self._create_task_instance(rule, user)
```

---

## 三、API 路由设计

### 新增路由文件

| 文件 | 前缀 | 端点数 |
|------|------|--------|
| `app/api/routes/products.py` | `/api/products` | 6 |
| `app/api/routes/product_packages.py` | `/api/product-packages` | 6 |
| `app/api/routes/task_rules.py` | `/api/task-rules` | 5 |
| `app/api/routes/task_instances.py` | `/api/task-instances` | 5 |
| `app/api/routes/sign_in.py` | `/api/sign-in` | 3 |
| `app/api/routes/invites.py` | `/api/invites` | 5 |
| `app/api/routes/marketing_stats.py` | `/api/marketing/stats` | 3 |

### 端点清单

#### 商品 `/api/products`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/products` | 列表（分页+搜索+标签筛选） |
| POST | `/api/products` | 创建（含图片上传） |
| PATCH | `/api/products/{id}` | 编辑 |
| DELETE | `/api/products/{id}` | 删除（被包引用时 409） |
| POST | `/api/products/import` | CSV 导入 |
| GET | `/api/products/export` | CSV 导出 |

#### 商品包 `/api/product-packages`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/product-packages` | 列表 + 统计 |
| POST | `/api/product-packages` | 创建（含自动凑包） |
| GET | `/api/product-packages/{id}` | 详情 |
| PATCH | `/api/product-packages/{id}` | 编辑（名称/奖励金额） |
| DELETE | `/api/product-packages/{id}` | 删除（被规则引用时 409） |
| POST | `/api/product-packages/assemble-preview` | 预览凑包结果（不保存） |

#### 任务规则 `/api/task-rules`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/task-rules` | 列表（按类型筛选） |
| POST | `/api/task-rules` | 创建 |
| PATCH | `/api/task-rules/{id}` | 编辑 |
| PATCH | `/api/task-rules/{id}/toggle` | 启用/停用 |
| DELETE | `/api/task-rules/{id}` | 删除 |

#### 任务实例 `/api/task-instances`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/task-instances` | 列表（按用户/状态/规则筛选） |
| POST | `/api/task-instances/manual-push` | 手动推送（选客户+选包） |
| POST | `/api/task-instances/{id}/start-product` | 开始商品任务（扣余额） |
| POST | `/api/task-instances/{id}/retry-product` | 重试失败的商品任务 |
| GET | `/api/task-instances/{id}` | 详情（含商品进度） |

#### 签到 `/api/sign-in`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sign-in` | 签到 |
| GET | `/api/sign-in/status` | 签到状态（今日是否已签/连续天数） |
| GET/PUT | `/api/sign-in/config` | 签到配置（连续天数/奖励金额） |

#### 邀请 `/api/invites`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/invites/my-link` | 获取我的邀请链接（首次自动生成） |
| GET | `/api/invites/my-records` | 我的邀请记录 |
| POST | `/api/invites/register-callback` | 注册回调（H5 注册时调用） |
| POST | `/api/invites/recharge-callback` | 充值回调 |
| GET/PUT | `/api/invites/config` | 邀请配置 |

#### 统计 `/api/marketing/stats`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/marketing/stats/packages` | 商品包统计（创建数/领取数/完成率） |
| GET | `/api/marketing/stats/tasks` | 任务统计（按类型：触发/完成/奖励/转化率） |
| GET | `/api/marketing/stats/overview` | 总览（今日签到/今日邀请/今日推送） |

### 修复电商审计日志 Bug

修改 `app/services/ecommerce_service.py`：所有 `add_audit_log()` 调用增加 try/except，防止 mock 账号 FK 违反。

---

## 四、Worker 任务

### 修改 `app/worker.py`

新增 scheduler 循环（与现有 job processor 并行）：

```python
async def run_worker():
    # 现有任务处理
    asyncio.create_task(run_job_processor())
    # 新增：营销任务调度器
    asyncio.create_task(run_marketing_scheduler())
```

### Redis 数据结构

| Key | 类型 | 说明 |
|-----|------|------|
| `delayed_tasks` | Sorted Set | score=触发时间戳, value=job_json |
| `signin:{user_id}:{date}` | String | 今日签到标记 (TTL 25h) |
| `invite_code:{code}` | Hash | 邀请码→用户映射 |

---

## 五、测试设计

| 测试文件 | 用例数 | 覆盖 |
|---------|--------|------|
| `test_product_service.py` | 10 | CRUD + 导入导出 + 删除保护 |
| `test_product_package_service.py` | 12 | 凑包算法 + 边界 + 统计 |
| `test_task_engine.py` | 15 | 触发 + 余额扣减 + 奖励 + 重试 + 过期 |
| `test_sign_in_service.py` | 10 | 签到 + 连续天数 + 中断重置 + 奖励 + 一次性 |
| `test_invite_service.py` | 10 | 链接生成 + 注册回调 + 充值回调 + 防刷 + 上限 |
| `test_task_scheduler.py` | 8 | 延迟触发 + 定时推送 + 过期扫描 + 宕机补发 |
| `test_marketing_api.py` | 12 | 全部 API 端点 |
| **总计** | **77** | |

---

## 六、依赖

- `pyproject.toml`: 新增 `python-multipart`（CSV 上传）、`Pillow`（图片处理，如已有则跳过）

## 七、全局约束

1. 所有金额使用 `Decimal`，不用 `float`
2. 余额操作使用 `SELECT ... FOR UPDATE` 防竞态
3. 签到使用 Redis + DB 双写（Redis 快速判断，DB 持久化）
4. 所有 ledger 操作记录到 `wallet_ledger_entries`
5. 不碰前端代码
6. 不碰 H5 代码
7. 一次性完成

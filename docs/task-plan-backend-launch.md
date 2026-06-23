# 后端上线级任务清单（BE2-001 ~ BE2-30）

> **执行角色**: api_agent + db_agent + ai_agent + queue_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 后端达到**可上线标准**，所有核心链路闭环

---

## 0. 项目现状摘要

### 已完成

| 模块 | 状态 | 关键产出 |
|------|------|---------|
| Docker 优化 | ✅ | CPU 0.09%, 内存 138 MiB |
| 人工接管闭环 | ✅ | AgentPresenceService(249行) + 5 API |
| 模板消息 | ✅ | CRUD + Meta 同步 + 发送日志 79 测试 |
| AI 管道 | ✅ | 意图分类 + 知识库 + 降级链 15 测试 |
| Worker 加固 | ✅ | 死信队列 + 连续失败检测 + worker_health |
| DB 优化 | ✅ | pool_size=10 + pre_ping + recycle |
| WhatsApp Provider | ✅ | 987行实现（未真实接入 Meta） |
| 监控 | ✅ | 10 条告警 + 35 Grafana 面板 |
| 迁移 | 65 个 | 最新 0065 |

### 未完成 / 待上线加固

| 缺失项 | 影响 |
|--------|------|
| 无 Admin JWT 认证 | 后台裸奔 |
| 无 API 速率限制 | 易被攻击 |
| 无 CORS 精确配置 | 前端跨域风险 |
| 无真实 Meta Webhook 签名验证加固 | 安全风险 |
| 无 Embedded Signup 完整回调处理 | Meta 接入断链 |
| 无媒体消息完整链路 | 图片/视频/文件无法收发 |
| 无并发压力测试 | 不知上限 |
| 无 API 限流/熔断 | 单点故障 |
| test_assignments_frontend_contract 预存失败 | CI 不绿 |
| 部分 service 超大（runtime_state 2551行, meta_account_registry 3596行, template_service 3028行） | 维护困难 |
| 无优雅关闭/信号处理加固 | 容器重启可能丢任务 |

---

## 1. 执行编排（7 Phase，预计 3-4 天）

```
Day 1:
  Phase 1（安全加固，P0）: BE2-001~004  ── api_agent
  Phase 2（Webhook 签名 + Embedded Signup，P0）: BE2-005~008 ── api_agent + db_agent

Day 2:
  Phase 3（媒体消息链路，P0）: BE2-009~012 ── api_agent + queue_agent
  Phase 4（AI 生产加固，P1）: BE2-013~016 ── ai_agent + queue_agent

Day 3:
  Phase 5（数据可靠性 + 优雅关闭，P1）: BE2-017~020 ── db_agent + queue_agent
  Phase 6（H5 API 收口，P1）: BE2-021~024 ── api_agent

Day 4:
  Phase 7（测试 + 上线验证，P0）: BE2-025~030 ── testing_agent
```

---

## Phase 1：安全加固（P0）

### BE2-001：Admin JWT 认证

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

管理后台所有 API 必须经过 JWT 认证，不能裸奔。

#### 实现要求

1. **新增 `app/services/admin_auth_service.py`**
   - `AdminAuthService` 类
   - `authenticate(username, password) -> AdminTokens` — 签发 access_token + refresh_token
   - `verify_token(token) -> AdminUser` — 验证 token 并返回用户信息
   - `refresh(refresh_token) -> AdminTokens` — 刷新 token
   - Token 有效期: access 2h, refresh 7d（从 settings 读取）
   - 密码存储: bcrypt hash
   - JWT 签名: HS256 + settings.admin_jwt_secret

2. **新增 `app/api/routes/admin_auth.py`**
   - `POST /api/admin/auth/login` — 登录
   - `POST /api/admin/auth/refresh` — 刷新
   - `POST /api/admin/auth/logout` — 登出（黑名单 refresh_token）
   - `GET /api/admin/auth/me` — 当前用户

3. **新增 `app/core/admin_auth.py`** — 认证中间件 / 依赖
   - `require_admin()` — FastAPI 依赖注入，从 Authorization header 提取并验证 token
   - 白名单路径: /health, /metrics, /api/admin/auth/login, /api/dev/mock/*, webhook 路径

4. **更新 `app/main.py`**
   - 注册 admin_auth 路由
   - 添加认证中间件（全局拦截，白名单放行）

5. **Settings 新增字段**
   - `admin_jwt_secret: str` — JWT 签名密钥
   - `admin_access_token_ttl_minutes: int` — access token TTL
   - `admin_refresh_token_ttl_days: int` — refresh token TTL
   - `admin_default_username: str` — 初始管理员账号
   - `admin_default_password: str` — 初始管理员密码

6. **数据模型**
   - `admin_users` 表（id, username, password_hash, role, is_active, created_at, updated_at）
   - `admin_refresh_tokens` 表（id, user_id, token_hash, expires_at, revoked_at, created_at）
   - 新增 alembic 迁移文件

7. **测试** — `tests/test_admin_auth.py`
   - 登录成功 / 密码错误 / 用户不存在
   - Token 验证成功 / 过期 / 篡改
   - 刷新成功 / 已撤销
   - 中间件白名单放行
   - 中间件拦截未认证请求

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `app/services/admin_auth_service.py` | 新增 |
| `app/api/routes/admin_auth.py` | 新增 |
| `app/core/admin_auth.py` | 新增 |
| `app/core/settings.py` | 修改（新增字段） |
| `app/main.py` | 修改（注册路由 + 中间件） |
| `alembic/versions/0066_admin_users.py` | 新增 |
| `tests/test_admin_auth.py` | 新增 |
| `.env.example` | 修改（新增 ADMIN_JWT_SECRET 等） |

#### 验收标准

1. 未认证请求返回 401
2. 登录返回 JWT token pair
3. 刷新 token 可用
4. 登出后 refresh token 失效
5. 白名单路径正常访问
6. 测试 15+ 通过

---

### BE2-002：API 速率限制

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

对关键 API 添加速率限制，防止滥用。

#### 实现要求

1. **新增 `app/core/rate_limiter.py`**
   - `RateLimiter` 类（基于 Redis sliding window）
   - `check_limit(key, max_requests, window_seconds) -> (allowed, remaining, reset_at)`
   - 预设档位:
     - `auth`: 5 req/min（登录）
     - `webhook`: 100 req/min（Meta 回调）
     - `api`: 60 req/min（后台 API）
     - `h5_auth`: 10 req/min（H5 登录）
     - `h5_api`: 30 req/min（H5 业务 API）
     - `mock`: 30 req/min（开发态 mock）

2. **FastAPI 依赖注入**
   - `rate_limit(tier: str)` — 返回依赖，自动从 request 提取 client IP 或 token
   - 超限返回 429 + Retry-After header

3. **应用范围**
   - `/api/admin/auth/login` → auth tier
   - `/api/webhooks/*` → webhook tier
   - `/api/admin/*` → api tier
   - `/api/h5/*` → h5_api tier
   - `/api/h5/auth/*` → h5_auth tier

4. **Settings 新增字段**
   - `rate_limit_enabled: bool` — 全局开关
   - 各 tier 可通过 env 覆盖

5. **测试** — `tests/test_rate_limiter.py`
   - 限流触发
   - 限流释放（窗口滑过）
   - 不同 tier 独立
   - 超限返回 429

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `app/core/rate_limiter.py` | 新增 |
| `app/core/settings.py` | 修改 |
| `app/api/routes/admin_auth.py` | 修改（加 rate_limit） |
| `app/api/routes/webhooks.py` | 修改（加 rate_limit） |
| `app/api/routes/h5_auth.py` | 修改（加 rate_limit） |
| `tests/test_rate_limiter.py` | 新增 |

#### 验收标准

1. 超限返回 429
2. Retry-After header 正确
3. 不同 tier 独立计数
4. 测试 8+ 通过

---

### BE2-003：CORS 精确配置

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 实现要求

1. `app/main.py` 中 CORSMiddleware 精确配置
2. `settings.cors_origins: str` — 逗号分隔的允许源
3. 开发态默认: `http://localhost:5173,http://localhost:3000`
4. 生产态: 从 `.env` 的 `CORS_ORIGINS` 读取
5. 允许方法: GET, POST, PUT, DELETE, OPTIONS
6. 允许 headers: Content-Type, Authorization, X-Request-ID
7. 允许 credentials: True
8. 测试: 在 `test_health.py` 中加 OPTIONS 预检请求测试

#### 验收标准

1. 允许的 origin 正常返回 CORS headers
2. 不允许的 origin 被拒绝
3. OPTIONS 预检正确

---

### BE2-004：合约测试修复 + 全局测试健康

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 目标

修复 `test_assignments_frontend_contract.py` 失败，确保全量测试绿。

#### 实现要求

1. 检查 `AssignmentsPage.tsx` 当前代码
2. `getCustomerMemberStatusSnapshot` 已封装进 `useMemberStatus` hook
3. 合约测试需要更新断言以匹配当前代码结构
4. 运行 `pytest tests/ -q` 确保全部通过
5. 如果全量测试有超时问题，标记需要 Redis/PostgreSQL 的测试为 `@pytest.mark.integration`

#### 验收标准

1. `test_assignments_frontend_contract.py` 2/2 通过
2. 全量 pytest 绿（不计 integration 标记的）

---

## Phase 2：Webhook + Embedded Signup（P0）

### BE2-005：Webhook 签名验证加固

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

生产环境必须验证 Meta Webhook 签名，防止伪造请求。

#### 实现要求

1. **`app/api/routes/webhooks.py`** 加固
   - 验证 `X-Hub-Signature-256` header
   - 使用 app_secret 对 raw body 做 HMAC-SHA256
   - 签名不匹配返回 401 + 结构化日志
   - 支持多账号（不同 WABA 不同 app_secret）

2. **Verify Token 验证**
   - `GET /api/webhooks/whatsapp/{account_id}` — Meta 验证请求
   - 对比 `hub.verify_token` 与账号配置的 verify_token
   - 匹配返回 `hub.challenge`

3. **Settings**
   - `webhook_signature_enabled: bool` — 全局开关（开发态可关闭）
   - 各账号 app_secret 从 DB 读取（webhook_subscriptions 表）

4. **测试** — 扩展 `tests/test_whatsapp_webhooks.py`
   - 签名正确 → 200
   - 签名错误 → 401
   - 签名缺失 + 开关开 → 401
   - 签名缺失 + 开关关 → 200（开发态）
   - verify token 匹配 → 返回 challenge
   - verify token 不匹配 → 403

#### 验收标准

1. 签名验证可启用/禁用
2. 所有 Webhook 测试通过
3. 安全审计通过

---

### BE2-006：Embedded Signup 完整回调

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

Meta Embedded Signup 全流程闭环：前端发起 → Meta 回调 → 自动创建账号 → 通知前端完成。

#### 实现要求

1. **`app/api/routes/meta_accounts.py`** 增强
   - `POST /api/meta/embedded-signup/start` — 创建 embedded_signup_session
   - `POST /api/meta/embedded-signup/callback` — Meta 回调处理
     - 解析 Meta 返回的 access_token, waba_id, phone_number_id
     - 自动创建 BusinessPortfolio + WABA + PhoneNumber 记录
     - 更新 embedded_signup_session 状态为 completed
     - 触发 webhook_subscription 创建
   - `GET /api/meta/embedded-signup/{session_id}/status` — 前端轮询状态

2. **`app/services/meta_account_registry.py`** 增强
   - `complete_embedded_signup(session, meta_response) -> account`
   - 处理 Meta 返回的完整对象层级
   - 幂等性: 重复回调不重复创建

3. **测试** — 扩展 `tests/test_meta_accounts.py`
   - 正常 Signup 流程
   - 重复回调幂等
   - 缺失字段处理
   - 状态轮询

#### 验收标准

1. 前端发起 → 回调 → 账号自动创建 → 状态更新
2. 测试 10+ 通过

---

### BE2-007：Webhook 事件处理加固

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

当前 webhooks.py 已有 1479 行实现。需要加固：
- 消息去重（Meta 会重发）
- 状态更新处理（sent/delivered/read/failed）
- 错误隔离（单条消息处理失败不影响其他）
- 结构化日志

#### 实现要求

1. **消息去重**
   - Redis key: `whatsapp:message_dedup:{message_id}` TTL 24h
   - 重复消息直接返回 200 + 日志标记

2. **状态更新**
   - 解析 status 类型: sent/delivered/read/failed
   - 更新 message_events 表
   - failed 状态记录 error_code 和 error_message

3. **错误隔离**
   - 每条消息独立 try/except
   - 失败不阻断 webhook 响应
   - 失败消息写入 dead_letter 或错误日志

4. **测试**
   - 去重: 相同 message_id 只处理一次
   - 状态更新: 各状态正确写入
   - 错误隔离: 单条失败不影响批次

#### 验收标准

1. 去重生效
2. 状态更新链路完整
3. 测试通过

---

### BE2-008：多账号运行时隔离加固

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

确保多账号运行时数据完全隔离，不同账号的会话、消息、模板、AI 状态不串扰。

#### 实现要求

1. 审计 `runtime_state.py`（2551 行）中的 account_id 使用
2. 确保所有查询都带 account_id 条件
3. AI 开关查询链路: 全局 → 账号 → 会话 三级完整
4. 测试: 创建两个账号，验证数据完全隔离

#### 验收标准

1. 无跨账号数据泄漏
2. AI 开关三级控制正确

---

## Phase 3：媒体消息链路（P0）

### BE2-009：媒体消息接收处理

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

用户可以发送图片/音频/视频/文档给系统，系统能正确接收、存储、并传递给 AI 或人工坐席。

#### 实现要求

1. **`app/services/media_message_processor.py`**（新增）
   - `process_inbound_media(normalized_message) -> MediaAsset`
   - 支持类型: image, audio, video, document, sticker
   - 从 Meta Graph API 下载媒体文件（需 access_token）
   - 存储到本地 storage 或 S3（通过 settings 配置）
   - 生成缩略图（图片类）
   - 记录到 media_assets 表

2. **`app/providers/messaging/whatsapp_provider.py`** 增强
   - `download_media(media_id, access_token) -> bytes`
   - 处理临时 URL 下载
   - 超时和重试

3. **集成到消息处理主流程**
   - `chat.py` / `conversation_service.py` 中识别媒体消息
   - 媒体消息入 AI 上下文时：图片 → OCR/描述，其他 → 文本摘要

4. **测试**
   - MockProvider 模拟媒体消息接收
   - 下载失败重试
   - 超大文件处理

#### 验收标准

1. 5 种媒体类型可接收
2. 文件存储正确
3. 测试通过

---

### BE2-010：媒体消息发送

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

坐席/AI 可以回复媒体消息（图片、文件、音频）。

#### 实现要求

1. **`app/services/outbound_media_service.py`**（新增）
   - `send_media_message(conversation_id, media_type, file_or_url) -> DispatchResult`
   - 支持: image, audio, video, document
   - 通过 MessagingProvider.dispatch_outbound 发送
   - 记录到 message_events

2. **`app/providers/messaging/whatsapp_provider.py`** 增强
   - `dispatch_media_outbound(request) -> result`
   - 支持发送 media 类型消息（WhatsApp API 格式）
   - 支持 caption（图片/视频文字说明）

3. **API**
   - `POST /api/conversations/{id}/send-media` — 发送媒体消息

4. **测试**

#### 验收标准

1. 图片/文件/音频可发送
2. API 可用
3. 测试通过

---

### BE2-011：媒体资产管理加固

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

`media_asset_service.py`（1413 行）已很完善。加固方向：
- 大文件分片下载
- 存储路径规范化（按 account_id/date 组织）
- 缩略图自动生成
- 清理过期媒体

#### 验收标准

1. 存储路径规范
2. 缩略图可用
3. 测试通过

---

### BE2-012：媒体消息完整测试

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 测试覆盖

1. 入站图片 → 下载 → 存储 → 入库 → AI 可见
2. 入站文档 → 下载 → 存储 → 入库
3. 出站图片 → 发送 → 状态更新
4. MockProvider 模拟完整链路
5. 大文件处理
6. 下载超时/重试
7. 媒体去重（相同 media_id 不重复下载）

#### 验收标准

1. 10+ 测试通过
2. 完整链路跑通

---

## Phase 4：AI 生产加固（P1）

### BE2-013：Prompt 管理 + 多语言支持

- **优先级**: P1
- **估计耗时**: 60 分钟

#### 目标

当前 AI prompt 硬编码在代码中。需要：
- Prompt 模板化（DB 存储 + 版本控制）
- 多语言 prompt 支持
- 按账号配置不同 prompt
- A/B 测试支持

#### 实现要求

1. **新增 `app/services/prompt_manager.py`**
   - `PromptManager` 类
   - `get_prompt(template_name, account_id, language) -> str`
   - 从 DB 加载 prompt 模板
   - 变量替换（客户名、商品名、订单号等）
   - 缓存（Redis，TTL 5min）

2. **新增 `ai_prompts` 表**
   - id, name, account_id (nullable=全局), language, version, content, is_active, created_at, updated_at
   - 唯一约束: (name, account_id, language, version)

3. **初始 Prompt 模板**
   - `customer_service_default` — 通用客服
   - `customer_service_human_handover` — 转人工话术
   - `product_inquiry` — 商品咨询
   - `order_status` — 订单查询
   - `complaint_handling` — 投诉处理

4. **API**
   - `GET /api/ai/prompts` — 列表
   - `POST /api/ai/prompts` — 创建
   - `PUT /api/ai/prompts/{id}` — 更新
   - `DELETE /api/ai/prompts/{id}` — 软删除

5. **测试**

#### 验收标准

1. Prompt 从 DB 加载
2. 变量替换正确
3. 多账号不同 prompt
4. 测试 8+ 通过

---

### BE2-014：AI 上下文窗口优化

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 目标

确保 AI 回复时上下文窗口合理，不超限，不浪费 token。

#### 实现要求

1. **上下文构建策略**
   - 最近 N 条消息（从 settings 读取，默认 10）
   - 系统 prompt + 知识库检索结果 + 历史消息
   - 总 token 估算（tiktoken 或简易估算）
   - 超限时: 截断历史消息 → 移除知识库 → 仅系统 prompt

2. **token 使用统计**
   - 每次 AI 调用记录 prompt_tokens + completion_tokens
   - 存入 message_events 或独立表
   - 暴露到 /metrics

3. **测试**

#### 验收标准

1. 上下文构建正确
2. 超限自动截断
3. token 统计可见

---

### BE2-015：AI 回复质量评估

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 目标

对 AI 生成的回复做基础质量评估，低质量回复自动降级到人工。

#### 实现要求

1. **新增 `app/services/ai_quality_evaluator.py`**
   - `evaluate_reply(reply_text, context) -> QualityScore`
   - 评估维度:
     - 长度合理性（不能太短/太长）
     - 敏感词检测
     - 重复内容检测（与上一条完全相同）
     - 语言一致性（客户中文 → 回复中文）
     - 格式检查（无 markdown/代码泄漏）
   - 返回: pass / warning / reject

2. **集成到 AI 管道**
   - AI 生成回复后 → 质量评估
   - reject → 降级到人工或重试
   - warning → 记录日志但发送

3. **Settings**
   - `ai_quality_check_enabled: bool` — 全局开关
   - `ai_quality_reject_threshold: float` — 拒绝阈值

4. **测试**

#### 验收标准

1. 低质量回复被拦截
2. 测试通过

---

### BE2-016：AI 完整测试套件

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 测试覆盖

1. 意图分类准确性（10+ 场景）
2. 知识库检索相关性
3. 降级链: OpenAI 失败 → DeepSeek → Mock
4. 上下文窗口截断
5. 质量评估各维度
6. Token 统计
7. 多账号不同 prompt
8. AI 开关三级控制
9. 人工接管后 AI 停止

#### 验收标准

1. 20+ 测试通过
2. 全链路跑通

---

## Phase 5：数据可靠性 + 优雅关闭（P1）

### BE2-017：Worker 优雅关闭

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

容器重启时 worker 必须：
- 停止接收新任务
- 等待当前任务完成（grace period）
- 未完成的任务放回队列

#### 实现要求

1. `app/worker.py` 加固
   - SIGTERM 信号处理
   - 设置 RUNNING = False 停止新任务
   - 等待当前任务完成（最多 30 秒）
   - 超时强制退出
   - 未完成的任务标记为 pending（放回队列）

2. Docker Compose
   - `stop_grace_period: 30s`

3. **测试**

#### 验收标准

1. SIGTERM 后不丢任务
2. 测试通过

---

### BE2-018：数据库连接健康监控

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

数据库连接池状态实时可见，异常时自动告警。

#### 实现要求

1. 暴露连接池状态到 /metrics
   - `db_pool_checked_out` — 活跃连接数
   - `db_pool_checked_in` — 空闲连接数
   - `db_pool_overflow` — 溢出连接数
   - `db_pool_size` — 当前池大小

2. `/health` 增加 DB 深度检查
   - 可选: `GET /health?deep=true` 执行 `SELECT 1`
   - 返回连接池状态

3. Prometheus 告警规则
   - 活跃连接 > 80% → 告警
   - 连接获取超时 → 告警

#### 验收标准

1. /metrics 有 DB 指标
2. /health deep 检查可用

---

### BE2-019：Redis 连接健康 + 降级

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. Redis 连接异常时自动降级
   - 队列: Redis 不可用 → 内存队列（临时）
   - 会话状态: Redis 不可用 → 从 DB 读取（慢但可用）
   - AI 状态缓存: Redis 不可用 → 跳过缓存

2. 连接池健康监控到 /metrics
   - `redis_pool_connections` — 连接数
   - `redis_commands_total` — 命令计数
   - `redis_errors_total` — 错误计数

3. **测试** — 模拟 Redis 不可用场景

#### 验收标准

1. Redis 挂掉后核心流程不崩溃
2. 测试通过

---

### BE2-020：数据备份 + 恢复验证

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. 验证 `scripts/backup-postgres.ps1` 和 `scripts/restore-postgres.ps1` 实际可用
2. 验证 `scripts/backup-redis.ps1` 实际可用
3. 新增 `scripts/test-backup-restore.ps1`
   - 自动备份 → 删除数据 → 恢复 → 验证数据完整
4. 更新 `docs/recovery-runbook.md`

#### 验收标准

1. 备份/恢复全链路跑通
2. 恢复手册完整

---

## Phase 6：H5 API 收口（P1）

### BE2-021：H5 会员认证加固

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 目标

当前 H5 认证 `h5_member_auth_service.py`（582 行）已实现。加固：
- Refresh token 自动续期
- Session 并发控制（同一用户不允许多设备同时登录）
- 密码强度校验
- 登录失败锁定（5 次失败 → 锁定 15 分钟）

#### 验收标准

1. 续期正确
2. 并发控制生效
3. 登录锁定生效

---

### BE2-022：H5 电商 API 收口

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

`h5_member_commerce_service.py`（1253 行）完善。收口：
- 订单查询缓存（5 分钟）
- 物流查询缓存（10 分钟）
- MockEcommerceProvider 数据完善
- 错误处理标准化

#### 验收标准

1. 缓存生效
2. 错误不泄漏到前端

---

### BE2-023：H5 提现流程完善

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

`platform_withdrawal_service.py`（330 行）+ H5 提现页面。确保：
- 提现申请 → 审核 → 打款 → 完成 全链路
- 余额不足拒绝
- 重复提交防护
- 提现记录可查

#### 验收标准

1. 全链路跑通
2. 余额校验正确

---

### BE2-024：H5 API 完整测试套件

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 测试覆盖

1. 注册 / 登录 / 刷新 / 登出
2. 首页 / 任务列表 / 任务提交 / 任务审核
3. 钱包 / 充值 / 提现
4. 认证 / WhatsApp 绑定
5. 消息 / 通知
6. 片段 / 商城
7. 密码错误 / 余额不足 / 重复提交

#### 验收标准

1. 30+ 测试通过
2. 覆盖所有 H5 API 端点

---

## Phase 7：测试 + 上线验证（P0）

### BE2-025：集成测试套件

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

创建端到端集成测试，模拟真实使用场景。

#### 测试场景

1. **消息收发 E2E**
   - Mock 入站消息 → 处理 → AI 回复 → 出站 → 状态更新
   - 人工接管 → 人工回复 → 恢复 AI

2. **Meta 接入 E2E**
   - 创建账号 → Embedded Signup → Webhook 注册 → 收发消息

3. **H5 用户 E2E**
   - 注册 → 登录 → 浏览任务 → 提交任务 → 查看钱包 → 提现

4. **多账号并发**
   - 账号 A 和账号 B 同时收消息 → 互不干扰
   - AI 开关独立控制

#### 验收标准

1. 4 个 E2E 场景全通过
2. 无数据串扰

---

### BE2-026：性能基线测试

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

建立性能基线，知道系统的上限。

#### 实现要求

1. **新增 `tests/test_performance_baseline.py`**
   - 消息处理吞吐量（100 条消息的处理时间）
   - AI 回复延迟（Mock AI，不含真实 API 调用）
   - DB 查询延迟（常用查询的 P95）
   - 并发连接数（10 并发无错误）

2. 输出性能基线报告（JSON 格式）

#### 验收标准

1. 基线数据已建立
2. 无性能退化

---

### BE2-027：OpenAPI 文档增强

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

所有 API 端点有完整的 OpenAPI 文档。

#### 实现要求

1. 所有路由添加 `summary`、`description`、`tags`
2. 所有请求/响应 schema 有 `example`
3. 认证相关 API 有 `securitySchemes`
4. FastAPI `/docs` 页面可正常浏览所有 API

#### 验收标准

1. `/docs` 页面完整
2. 所有 schema 有 example

---

### BE2-028：日志脱敏 + 审计日志加固

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. 日志脱敏
   - access_token、password、phone_number 等敏感字段自动遮蔽
   - 手机号: 138****1234
   - token: ***...abc（保留最后 3 位）

2. 审计日志
   - 管理后台所有写操作记录到 audit_logs
   - 字段: user_id, action, resource_type, resource_id, before_value, after_value, timestamp

3. **测试**

#### 验收标准

1. 日志无敏感信息泄漏
2. 审计日志完整

---

### BE2-029：Launch Readiness 脚本更新

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 目标

`scripts/check-launch-readiness.ps1` 更新，覆盖所有上线检查项。

#### 检查项

1. 数据库连接 ✅
2. Redis 连接 ✅
3. Alembic 迁移最新 ✅
4. /health 返回 200 ✅
5. /metrics 返回指标 ✅
6. Admin JWT 认证可用 ✅
7. Worker 健康 ✅
8. CORS 配置正确 ✅
9. 速率限制启用 ✅
10. Webhook 签名验证启用 ✅
11. 至少一个 Meta 账号已配置 ✅
12. AI Provider 可用 ✅
13. Prometheus targets 2/2 ✅
14. Grafana dashboard 存在 ✅
15. 备份脚本可用 ✅

#### 验收标准

1. 15 项全部可检查
2. 脚本可执行

---

### BE2-030：全量回归测试

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 执行命令

```powershell
cd E:\codex\WhatsApp

# 后端全量
.venv\Scripts\python.exe -m pytest tests/ -q -x

# 前端构建
cd frontend
npm run build
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/admin-chat.test.tsx

# Launch Readiness
cd ..
powershell -File scripts\check-launch-readiness.ps1
```

#### 验收标准

| 项 | 预期 |
|----|------|
| pytest 全量 | 全部通过 |
| npm run build | 通过 |
| 前端测试 | 通过 |
| Launch Readiness | 15/15 通过 |
| Docker Compose | 7 服务健康 |

---

## 2. 全局约束

1. **所有新代码必须有类型注解**
2. **I/O 全部异步**
3. **所有外部调用有超时 + 日志 + 异常处理**
4. **所有实体带 account_id**
5. **AI 回复遵守三级开关 + 人工接管状态**
6. **Meta 实体保留官方 ID**
7. **不碰 H5 前端代码**（frontend/src/pages/h5-member/）
8. **不碰管理后台前端代码**（frontend/src/pages/ 除 h5-member 外）
9. **每次改动后运行相关测试**
10. **失败自动回滚 + 重试最多 3 次**
11. **单任务最大执行 90 分钟**
12. **进度写入 `.codex-run/progress/BE2-XXX.json`**
13. **一次性执行全部任务，不中途暂停确认**

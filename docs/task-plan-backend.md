# 后端任务清单（Backend Agent 专用）

> **执行角色**: api_agent + db_agent + ai_agent + queue_agent + human_handover_agent + logging_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**

---

## 0. 当前后端状态总览

### 已有代码规模

| 领域 | 文件数 | 总行数 | 状态 |
|------|--------|--------|------|
| 路由 (app/api/routes/) | 28 | ~6,000 | 大部分可运行 |
| 服务 (app/services/) | 41 | ~25,000 | 核心链路已实现 |
| Provider (app/providers/) | 35 | ~3,000 | 抽象层已建 |
| 模型 (app/db/models.py) | 1 | ~2,500 | 全量表已建 |
| 迁移 (alembic/versions/) | 66 | - | 连续可用 |
| 测试 (tests/) | 60+ | - | 覆盖主要链路 |

### 已完成的核心能力

- FastAPI 主入口 + 中间件 + 统一异常处理
- 消息处理主流程: receive → normalize → route → respond
- MockMessagingProvider + WhatsAppProvider 骨架
- AIProvider: OpenAI + DeepSeek skeleton + Mock
- QueueService + Redis queue + Worker
- H5 认证 / 任务包 / 钱包 / 提现 / 消息 / 碎片 / 邮寄 / 认证 / WhatsApp 绑定
- 平台端会员认证管理 / WhatsApp 绑定管理 / 提现管理
- MetaAccountRegistry (3596 行)
- TemplateService (3028 行)
- RuntimeState (2551 行) - AI 三级开关 + 接管状态
- SupportRouter + SupportIntentService + KnowledgeBase
- HandoverService (140 行) - 基础骨架
- WhatsAppAnalyticsService (1556 行)
- MediaAssetService (1413 行)

### 距离「可正常运营」的差距

| 能力 | 当前 | 目标 | 优先级 |
|------|------|------|--------|
| WhatsApp 正式接入 | Mock 为主 | PyWa + Webhook | P0 |
| 人工接管闭环 | 基础骨架 | 完整状态机 | P0 |
| 模板消息闭环 | 大量代码 | 验证+补齐 | P0 |
| AI 管道加固 | 可用 | 可靠 | P1 |
| Worker 可靠性 | 基本可用 | 生产级 | P1 |
| 数据库生产就绪 | 迁移可用 | 性能优化 | P1 |
| 监控与告警 | 基本框架 | 全覆盖 | P2 |
| 部署与上线 | docker-compose | 生产级 | P2 |

---

## 1. 执行编排

```
Phase 1 - 人工接管闭环（P0）:
  BE-001 (HandoverService 完善)     ── human_handover_agent
  BE-002 (坐席管理 API)            ── api_agent
  BE-003 (接管相关测试)            ── testing_agent     ← 依赖 BE-001, BE-002

Phase 2 - 模板消息闭环（P0）:
  BE-004 (模板 CRUD + 同步验证)    ── api_agent
  BE-005 (模板发送 + 日志)         ── api_agent + queue_agent
  BE-006 (模板测试)                ── testing_agent     ← 依赖 BE-004, BE-005

Phase 3 - AI 管道加固（P1）:
  BE-007 (意图分类加固)            ── ai_agent
  BE-008 (知识库检索优化)          ── ai_agent
  BE-009 (降级策略完善)            ── ai_agent
  BE-010 (AI 测试)                 ── testing_agent     ← 依赖 BE-007 ~ BE-009

Phase 4 - Worker + 队列可靠性（P1）:
  BE-011 (Worker 错误处理)         ── queue_agent
  BE-012 (死信队列)                ── queue_agent
  BE-013 (队列测试)                ── testing_agent     ← 依赖 BE-011, BE-012

Phase 5 - 数据库生产就绪（P1）:
  BE-014 (迁移整理与索引优化)      ── db_agent
  BE-015 (连接池与查询优化)        ── db_agent
  BE-016 (数据库测试)              ── testing_agent     ← 依赖 BE-014, BE-015

Phase 6 - WhatsApp 正式接入准备（P0，但依赖 Meta 配置）:
  BE-017 (WhatsAppProvider 加固)   ── api_agent
  BE-018 (Webhook 签名验证)        ── api_agent
  BE-019 (Embedded Signup 流程)    ── api_agent
  BE-020 (接入测试)                ── testing_agent     ← 依赖 BE-017 ~ BE-019

Phase 7 - 监控与部署（P2）:
  BE-021 (监控指标完善)            ── monitoring_agent + logging_agent
  BE-022 (告警规则)                ── monitoring_agent
  BE-023 (CI/CD 与部署)            ── deploy_agent
```

---

## 2. 任务详情

### BE-001：HandoverService 完善 - 完整接管状态机

- **角色**: human_handover_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 60 分钟

#### 当前状态

`app/services/handover_service.py` 仅 140 行，是基础骨架。需要完善人工接管的完整状态机。

#### 需要实现的能力

1. **坐席在线状态管理**
   - 坐席上线 / 下线 / 心跳
   - Redis 存储在线状态（带 TTL）
   - 按 account_id 作用域

2. **会话分配逻辑**
   - 轮询 / 最少负载 分配策略
   - 指定坐席分配
   - 分配失败回退（无在线坐席时的处理）

3. **AI → 人工切换状态机**
   - 触发条件：置信度低于阈值、关键词触发、用户主动请求
   - 切换时通知用户
   - 切换时保存上下文
   - 切换后 AI 自动回复必须停止（遵守三级开关优先级）

4. **人工 → AI 恢复**
   - 坐席主动结束接管
   - 超时自动恢复 AI（可配置）
   - 恢复后通知用户

5. **接管审计日志**
   - 每次接管/恢复写 handover_logs 表
   - 记录触发原因、坐席 ID、时间戳

#### 涉及文件

- **修改**: `app/services/handover_service.py`
- **修改**: `app/services/runtime_state.py`（AI 开关联动）
- **修改**: `app/api/routes/conversations.py`（接管 API）
- **新增**: `app/services/agent_presence_service.py`（坐席在线状态）
- **修改**: `app/db/models.py`（handover_logs 表确认）
- **修改**: `app/api/deps.py`（新依赖注入）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_handover_management.py -v --tb=short
```

#### 验收标准

1. 坐席可上线/下线，Redis 中有在线状态
2. 会话可按策略分配给在线坐席
3. AI → 人工切换后，AI 自动回复停止
4. 人工 → AI 恢复后，AI 自动回复恢复（受三级开关控制）
5. 每次接管/恢复有审计日志
6. 现有 handover 测试全部通过
7. 新增测试覆盖以上场景

#### 重试策略

- 最大重试: 3 次
- 失败回滚: git checkout 相关文件

#### 交付物

- 完善后的 handover_service.py
- 新增 agent_presence_service.py
- 更新的路由和依赖
- 测试通过日志

---

### BE-002：坐席管理 API

- **角色**: api_agent
- **优先级**: P0
- **前置依赖**: 无（可与 BE-001 并行）
- **估计耗时**: 30 分钟

#### 需要实现的 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agents/presence/online` | 坐席上线 |
| POST | `/api/agents/presence/offline` | 坐席下线 |
| GET | `/api/agents/presence` | 查询在线坐席列表 |
| POST | `/api/conversations/{id}/assign` | 分配会话给坐席 |
| POST | `/api/conversations/{id}/handover` | 触发 AI→人工接管 |
| POST | `/api/conversations/{id}/restore-ai` | 恢复 AI 托管 |
| GET | `/api/conversations/{id}/handover-logs` | 查看接管历史 |

#### 涉及文件

- **新增**: `app/api/routes/agents.py`
- **修改**: `app/main.py`（注册路由）
- **修改**: `app/api/routes/conversations.py`（接管相关端点）

#### 验收标准

1. 所有 API 端点可调用
2. 请求参数有验证
3. 响应格式统一（含 request_id）
4. 权限检查（account_id scope）

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 新增路由文件
- 更新后的 main.py

---

### BE-003：接管相关测试

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: BE-001, BE-002
- **估计耗时**: 30 分钟

#### 测试场景

1. 坐席上线 → 出现在在线列表 → 下线后消失
2. 创建会话 → 分配给坐席 → 状态变为 human_managed
3. AI 模式下发消息 → AI 回复 → 触发接管 → AI 停止回复
4. 人工模式 → 恢复 AI → AI 重新开始回复
5. 三级开关关闭时 → 即使恢复也不触发 AI
6. 接管审计日志完整记录

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_handover_management.py tests\test_conversations.py tests\test_runtime.py -v --tb=short
```

#### 验收标准

1. 以上 6 个场景全部测试通过
2. 现有测试无回归

---

### BE-004：模板 CRUD + Meta 同步验证

- **角色**: api_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 45 分钟

#### 当前状态

`app/services/template_service.py` 已有 3028 行代码。需要验证和完善：

1. **模板 CRUD 验证**
   - 创建 / 列表 / 详情 / 更新 / 删除
   - account_id 作用域隔离
   - 模板内容验证（变量占位符、长度限制）

2. **Meta 模板同步**
   - 本地创建 → 提交 Meta 审核（mock 当前）
   - Meta 审核状态回调处理
   - 模板状态同步（PENDING / APPROVED / REJECTED）
   - TemplateRegistryProvider 集成验证

3. **模板统计**
   - TemplateStatsAggregator 验证
   - 发送量 / 成功率 / 失败率统计

#### 涉及文件

- **验证/修改**: `app/services/template_service.py`
- **验证/修改**: `app/api/routes/templates.py`
- **验证**: `app/providers/template_registry/` 全部文件
- **验证**: `app/services/template_stats_aggregator.py`

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_templates.py tests\test_template_registry_providers.py -v --tb=short
```

#### 验收标准

1. 模板 CRUD 全部可用
2. 模板同步状态机完整（创建→提交→审核通过/拒绝）
3. 模板统计准确
4. 多账号隔离正确
5. 现有测试通过

---

### BE-005：模板发送 + 日志

- **角色**: api_agent + queue_agent
- **优先级**: P0
- **前置依赖**: BE-004
- **估计耗时**: 30 分钟

#### 需要验证/完善的能力

1. **模板消息发送**
   - 通过 MessagingProvider 发送模板消息
   - 变量替换
   - 多语言模板选择
   - 发送结果记录到 template_send_logs

2. **异步发送**
   - 大批量模板发送走队列
   - Worker 处理模板发送任务
   - 失败重试 + 死信

3. **发送日志**
   - 每次发送记录：模板 ID、收件人、状态、时间戳
   - 按 account_id 可查

#### 涉及文件

- **验证/修改**: `app/services/template_service.py`（发送逻辑）
- **验证/修改**: `app/services/messaging_dispatch.py`
- **验证**: `app/db/models.py`（template_send_logs 表）

#### 验收标准

1. 模板消息可通过 Mock Provider 发送
2. 变量替换正确
3. 发送日志完整记录
4. 批量发送走队列异步处理

---

### BE-006：模板测试

- **角色**: testing_agent
- **前置依赖**: BE-004, BE-005
- **估计耗时**: 20 分钟

#### 测试场景

1. 创建模板 → 提交审核 → 审核通过 → 发送 → 日志记录
2. 模板变量不匹配 → 发送失败
3. 多账号模板隔离
4. 批量发送 → 队列处理 → 全部完成
5. 模板统计正确

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_templates.py -v --tb=short
```

---

### BE-007：意图分类加固

- **角色**: ai_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 45 分钟

#### 当前状态

- `app/services/support_intent_service.py` (182 行)
- `app/services/support_router.py` (223 行)
- `app/services/support_knowledge_service.py` (375 行)

#### 需要加固的内容

1. **意图分类准确率**
   - 规则优先：关键词匹配 → 意图直接确定
   - AI 辅助：关键词未命中 → LLM 分类
   - 意图类型：FAQ / 订单查询 / 投诉 / 人工转接 / 闲聊

2. **路由决策**
   - FAQ → 知识库检索 → 直接回复
   - 订单查询 → 电商 API → 格式化回复
   - 投诉 → 直接转人工
   - 人工转接 → 触发 handover
   - 闲聊 → AI 生成回复

3. **降级策略**
   - LLM 超时 → 返回预设回复
   - LLM 不可用 → 返回 fallback 消息 + 建议联系人工
   - 知识库无结果 → AI 生成 + 标记为低置信度

#### 涉及文件

- **修改**: `app/services/support_intent_service.py`
- **修改**: `app/services/support_router.py`
- **修改**: `app/services/support_knowledge_service.py`

#### 验收标准

1. 关键词命中时不调用 LLM
2. 各意图路由到正确处理器
3. LLM 超时时返回降级回复
4. 现有 test_support_intent_service.py、test_support_router.py 通过

---

### BE-008：知识库检索优化

- **角色**: ai_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要优化的内容

1. `app/services/knowledge_base.py` (161 行) 当前为基础骨架
2. FAQ 检索：关键词匹配 + 模糊搜索
3. 产品说明检索
4. 检索结果排序与置信度评估
5. 与意图路由的集成

#### 验收标准

1. FAQ 检索返回相关结果
2. 无结果时返回空列表（不报错）
3. 检索延迟 < 500ms
4. 与 support_router 集成正常

---

### BE-009：AI 降级策略完善

- **角色**: ai_agent
- **优先级**: P1
- **前置依赖**: BE-007
- **估计耗时**: 30 分钟

#### 需要完善的内容

1. **AI Provider 降级链**
   - OpenAI 失败 → DeepSeek
   - DeepSeek 失败 → MockProvider
   - 全部失败 → 预设回复 + 转人工建议

2. **超时控制**
   - 每次 AI 调用有超时（已有 llm_request_timeout_seconds=30）
   - 超时后自动降级

3. **上下文窗口管理**
   - 对话历史截断策略
   - Token 限制保护
   - 系统 prompt + 历史 + 用户消息的优先级

#### 涉及文件

- **修改**: `app/providers/ai/openai_provider.py`
- **修改**: `app/providers/ai/deepseek_provider.py`
- **修改**: `app/services/ai_queue_processor.py`

#### 验收标准

1. 主 AI 失败自动切换到备用
2. 全部失败返回降级回复
3. 超时不阻塞主流程
4. test_ai_provider.py 通过

---

### BE-010：AI 管道测试

- **角色**: testing_agent
- **前置依赖**: BE-007, BE-008, BE-009
- **估计耗时**: 20 分钟

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_ai_provider.py tests\test_support_intent_service.py tests\test_support_router.py -v --tb=short
```

---

### BE-011：Worker 错误处理加固

- **角色**: queue_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要加固的内容

1. **Worker 启动时连接检查**
   - Redis 连接失败时的重试和告警
   - PostgreSQL 连接失败时的处理

2. **任务处理异常隔离**
   - 单个任务失败不影响 Worker 继续运行
   - 异常任务记录到日志
   - 连续失败超过阈值 → 告警 + 暂停

3. **Worker 健康检查**
   - 暴露 Worker 状态端点
   - 最后处理时间、处理数量、错误率

#### 涉及文件

- **修改**: `app/worker.py`
- **修改**: `app/services/queue_service.py`
- **新增**: `app/services/worker_health.py`（可选）

#### 验收标准

1. Worker 不会因单个任务失败而退出
2. 异常任务有日志记录
3. Redis/PG 断连时 Worker 能自动恢复
4. test_worker.py 通过

---

### BE-012：死信队列实现

- **角色**: queue_agent
- **优先级**: P1
- **前置依赖**: BE-011
- **估计耗时**: 30 分钟

#### 需要实现的内容

1. 任务失败次数超过 max_retries → 移入死信队列
2. 死信队列可查看（API 端点）
3. 死信任务可手动重试
4. 死信队列统计

#### 涉及文件

- **修改**: `app/services/queue_service.py`
- **修改**: `app/providers/queue/redis_provider.py`
- **修改**: `app/api/routes/queue.py`

#### 验收标准

1. 超过 max_retries 的任务进入死信队列
2. 死信队列可通过 API 查看
3. 死信任务可手动重新入队
4. test_queue_runtime.py 通过

---

### BE-013：队列测试

- **角色**: testing_agent
- **前置依赖**: BE-011, BE-012

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py tests\test_queue_runtime.py -v --tb=short
```

---

### BE-014：迁移整理与索引优化

- **角色**: db_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 45 分钟

#### 需要做的内容

1. **迁移健康检查**
   - 验证 66 个迁移可完整执行（从头到尾）
   - 检查是否有重复或冲突的迁移
   - 确认 alembic upgrade head 无报错

2. **索引优化**
   - 检查 models.py 中高频查询字段是否有索引
   - 补充缺失索引：account_id、conversation_id、created_at 等
   - 复合索引优化

3. **迁移文件清理**
   - 评估是否需要 squash（合并旧迁移）
   - 确保迁移命名规范

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_alembic_upgrade.py tests\test_db_schema.py -v --tb=short
```

#### 验收标准

1. alembic upgrade head 无报错
2. 高频查询字段有索引
3. test_alembic_upgrade.py、test_db_schema.py 通过

---

### BE-015：连接池与查询优化

- **角色**: db_agent
- **优先级**: P1
- **前置依赖**: BE-014
- **估计耗时**: 30 分钟

#### 需要优化的内容

1. **连接池配置**
   - SQLAlchemy engine pool_size / max_overflow 调优
   - 连接回收策略

2. **查询优化**
   - 检查 N+1 查询问题
   - 大表查询使用分页
   - 关键查询添加 EXPLAIN 分析

#### 涉及文件

- **修改**: `app/db/session.py`
- **审查**: 各 service 中的查询逻辑

#### 验收标准

1. 连接池参数合理
2. 无 N+1 查询问题
3. 大数据量查询有分页

---

### BE-016：数据库测试

- **角色**: testing_agent
- **前置依赖**: BE-014, BE-015

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_db_schema.py tests\test_alembic_upgrade.py -v --tb=short
```

---

### BE-017：WhatsAppProvider 加固

- **角色**: api_agent
- **优先级**: P0（但依赖 Meta 配置，当前以 Mock 验证为主）
- **前置依赖**: 无
- **估计耗时**: 60 分钟

#### 当前状态

`app/providers/messaging/whatsapp_provider.py` 已有 986 行。需要验证和完善：

1. **消息发送**
   - 文本消息
   - 模板消息
   - 媒体消息（图片/文档/音频）
   - 发送结果解析

2. **Webhook 回调处理**
   - 入站消息解析
   - 状态更新处理
   - 多账号路由（通过 phone_number_id 匹配 account_id）

3. **错误处理**
   - Meta API 超时
   - 速率限制
   - Token 过期

#### 涉及文件

- **验证/修改**: `app/providers/messaging/whatsapp_provider.py`
- **验证/修改**: `app/api/routes/webhooks.py` (1479 行)
- **验证**: `app/api/routes/meta_callbacks.py`

#### 验收标准

1. Mock 模式下消息发送完整链路可走
2. Webhook 回调解析正确
3. 多账号路由准确
4. 错误处理有日志和降级

---

### BE-018：Webhook 签名验证

- **角色**: api_agent
- **优先级**: P0
- **前置依赖**: BE-017
- **估计耗时**: 30 分钟

#### 需要实现/验证的内容

1. Meta webhook verify（GET 请求 challenge 验证）
2. Webhook payload HMAC-SHA256 签名校验
3. 按 account 匹配 app_secret 进行验证
4. 签名不匹配返回 401

#### 涉及文件

- **修改**: `app/api/routes/webhooks.py`
- **修改**: `app/api/routes/meta_callbacks.py`

#### 验收标准

1. verify 端点返回正确 challenge
2. 签名校验逻辑正确
3. 无效签名被拒绝
4. test_whatsapp_webhooks.py 通过

---

### BE-019：Embedded Signup 流程

- **角色**: api_agent
- **优先级**: P0（但依赖 Meta 配置）
- **前置依赖**: BE-017
- **估计耗时**: 45 分钟

#### 需要实现/完善的内容

1. **Session 创建**
   - 前端发起 → 创建 embedded_signup_sessions 记录
   - 生成 Meta OAuth URL

2. **回调处理**
   - Meta 回调 → 提取 WABA ID、Phone Number ID、Access Token
   - 创建/更新 whatsapp_business_accounts
   - 创建/更新 whatsapp_phone_numbers
   - 设置 Webhook 订阅

3. **状态管理**
   - PENDING → COMPLETED → FAILED
   - 超时自动过期

#### 涉及文件

- **修改**: `app/services/meta_account_registry.py`
- **修改**: `app/api/routes/meta_accounts.py`
- **验证**: `app/db/models.py`（embedded_signup_sessions 表）

#### 验收标准

1. Session 创建正常
2. 回调处理逻辑完整（可 mock Meta 响应测试）
3. 状态流转正确
4. 相关实体正确创建

---

### BE-020：WhatsApp 接入测试

- **角色**: testing_agent
- **前置依赖**: BE-017, BE-018, BE-019

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_whatsapp_webhooks.py tests\test_meta_accounts.py tests\test_meta_verify_token_conflicts.py tests\test_messaging_providers.py tests\test_mock_message.py -v --tb=short
```

---

### BE-021：监控指标完善

- **角色**: monitoring_agent + logging_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要补充的指标

1. **业务指标**
   - 会话总数 / 活跃数 / 按模式分布（ai/human/paused）
   - 消息处理延迟（p50/p95/p99）
   - AI 回复成功率 / 降级率
   - 人工接管次数 / 平均接管时长

2. **系统指标**
   - Worker 队列深度 / 处理速率
   - 数据库连接池使用率
   - Redis 内存使用

3. **结构化日志**
   - 统一 request_id 贯穿
   - 关键操作审计日志

#### 涉及文件

- **修改**: `app/core/metrics.py`
- **修改**: `app/api/routes/metrics.py`
- **验证**: `app/core/logging.py`

---

### BE-022：告警规则

- **角色**: monitoring_agent
- **优先级**: P2
- **前置依赖**: BE-021
- **估计耗时**: 20 分钟

#### 需要配置的告警

1. 错误率 > 10% 持续 5 分钟
2. 队列积压 > 500
3. 会话无响应 > 10 分钟
4. Worker 连续失败 > 3 次
5. 数据库连接池使用率 > 80%

#### 涉及文件

- **修改**: `monitoring/prometheus/alerts.yml`
- **修改**: `monitoring/alertmanager/alertmanager.yml`

---

### BE-023：CI/CD 与部署

- **角色**: deploy_agent
- **优先级**: P2
- **前置依赖**: BE-021, BE-022
- **估计耗时**: 45 分钟

#### 需要完善的内容

1. **CI 流水线**
   - `.github/workflows/ci.yml` 验证
   - lint + test + build 全通过

2. **生产 docker-compose**
   - 环境变量分离（.env.production）
   - 资源限制
   - 健康检查完善

3. **备份脚本**
   - PostgreSQL 备份/恢复
   - Redis RDB 备份

4. **部署文档**
   - 部署清单
   - 恢复手册

#### 涉及文件

- **修改**: `.github/workflows/ci.yml`
- **验证**: `scripts/` 目录所有脚本
- **验证**: `docs/deployment-checklist.md`
- **验证**: `docs/recovery-runbook.md`

---

## 3. 全局约束

1. 所有函数参数和返回值必须有类型注解
2. I/O 优先异步实现
3. 所有外部 API 调用必须有超时、日志和异常处理
4. 配置统一从环境变量读取（通过 settings.py）
5. 所有实体默认带 account_id
6. AI 自动回复遵守全局、账号、会话三级控制和人工接管状态
7. Meta 相关实体保留官方 ID
8. 进度文件: `.codex-run/progress/BE-XXX.json`
9. 单任务最大执行 60 分钟
10. 失败自动回滚 + 重试最多 3 次

---

## 4. 测试总命令

每个 Phase 完成后执行：

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\ -x -q --tb=short
```

全量回归：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -v --tb=short
```

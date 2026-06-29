## 项目固定方向

- 后端：FastAPI
- WhatsApp 接入：PyWa，等待 Meta 配置后接入
- 数据层：PostgreSQL + Redis
- 前端：React + Vite + TypeScript
- AI 主方案：OpenAI
- AI 备用方案：DeepSeek
- 运行方式：Docker Compose

## 当前现实约束

目前尚未拿到 WhatsApp Business API 的关键配置：

- Phone Number ID
- Access Token
- Verify Token
- App Secret
- Business Account ID

因此当前开发必须采用“无 WhatsApp 配置先行开发”模式：

1. 先完成所有不依赖 Meta 配置的内容。
2. 消息接入层必须通过 `MessagingProvider` 抽象。
3. 先实现 `MockMessagingProvider`，再实现 `WhatsAppProvider`。
4. 业务路由、AI、前端、电商、队列都不允许直接依赖 Meta 回调结构。

## 新增核心业务要求

### Meta 官方账户模型

系统必须按 Meta 官方对象层级设计，而不是把 WhatsApp 接入简化成一组 token。

必须显式建模以下实体：
- `Business Portfolio`
- `WhatsApp Business Account (WABA)`
- `Phone Number`
- `Webhook Subscription`
- `Embedded Signup Session`

必须遵守以下官方约束：
- 发送消息走 `Phone-Number-ID`
- Webhook 订阅是 `WABA` 级别
- 一个系统内可接入多个 `WABA`
- 一个 `WABA` 下可挂多个 `Phone Number`
- 账户接入既要支持手工录入，也要支持 `Embedded Signup`

### 多账户

系统必须支持多个 WhatsApp Business API 账户并存，不能按单账号产品设计。

要求：
- 一个系统内可挂载多个 WhatsApp Business API 账户
- 每个账户拥有独立的配置、状态、会话范围和运行开关
- 所有会话、消息、模板、日志都必须带 `account_id`
- 所有 Meta 侧实体必须保留 `waba_id`、`phone_number_id`、`meta_business_portfolio_id`
- 后端、前端、队列、AI 路由都必须先按多账户模型设计

### 会话并行

接待对话是并行的，不允许按单线程串行客服逻辑设计。

要求：
- 多个会话可同时处理中
- 同一账户下多个会话可并发进行
- 不同账户下会话也可并发进行
- 队列、路由、人工接管、AI 决策都必须按“每个会话独立状态”实现

### AI 托管与人工接管

系统必须支持 AI 托管自动回复，也必须支持人工接管。

要求：
- 会话可处于 `ai_managed`、`human_managed`、`paused` 等模式
- 人工接管后，AI 自动回复必须停止
- 人工结束后，可恢复 AI 托管
- 必须支持全局、单账号、单会话三级 AI 开关控制

### AI 开关优先级

AI 自动回复的优先级规则固定如下：

1. 全局开关
2. 账号级开关
3. 会话级开关
4. 会话接管模式

只要上层关闭，下层不得强行启用。

## 推荐开发顺序

### Phase 0：项目基建

目标：让仓库从文档态变成可开发、可启动、可测试的项目。

开发内容：
- 创建 `app/`、`frontend/`、`scripts/`、`tests/`、`alembic/`
- 补齐 `Dockerfile`、`.dockerignore`、`.env.example`
- 完成 Python 依赖管理和前端依赖管理
- 让 `docker-compose.yml` 至少能启动 `postgres`、`redis`、`app`、`worker`
- 建立基础 README 和本地启动命令

完成标准：
- 后端可启动
- 前端可启动
- 测试命令可执行
- Docker 开发骨架可用

### Phase 1：配置层与抽象接口

目标：把未来会变化的外部能力全部隔离出来。

开发内容：
- 实现 `settings.py`
- 定义 `MessagingProvider`
- 定义 `AIProvider`
- 定义 `EcommerceProvider`
- 定义 `QueueProvider`
- 定义 `MetaAccountRegistry`
- 统一错误模型、日志上下文、超时策略、请求 ID

完成标准：
- 业务代码不直接依赖 OpenAI、DeepSeek、PyWa 或真实电商 SDK
- 所有外部能力都可通过工厂函数或依赖注入切换

### Phase 2：数据库模型与迁移

目标：先固定核心数据结构，再开发上层功能。

开发内容：
- 设计 `conversations`
- 设计 `messages`
- 设计 `message_events`
- 设计 `meta_business_portfolios`
- 设计 `whatsapp_business_accounts`
- 设计 `whatsapp_phone_numbers`
- 设计 `webhook_subscriptions`
- 设计 `embedded_signup_sessions`
- 设计 `accounts`
- 设计 `agents`
- 设计 `handover_logs`
- 设计 `message_templates`
- 设计 `template_send_logs`
- 设计 `audit_logs`
- 设计 Redis key 规范
- 接入 Alembic

完成标准：
- 表结构稳定
- 迁移可以执行
- Redis 使用规范固定
- 多账户和会话接管字段已包含在模型中
- WABA、号码、Webhook 和 Embedded Signup 字段已包含在模型中

### Phase 3：最小后端可运行链路

目标：在没有 WhatsApp 配置时，也能完整跑通消息处理流程。

开发内容：
- 实现 FastAPI 应用入口
- 实现 `/health`
- 实现 `/metrics`
- 实现基础中间件和统一异常处理
- 实现消息处理主流程：`receive -> normalize -> route -> respond`
- 提供开发态 mock 入站接口
- 提供后台手工添加 Meta 账户接口
- 提供 Embedded Signup 会话占位接口
- 提供全局、账号、会话三级 AI 开关接口
- 提供人工接管/恢复 AI 的控制接口

完成标准：
- 本地可以通过 mock 请求模拟用户发消息
- 系统可以返回 Echo 或 AI skeleton 回复

### Phase 4：Mock 消息接入层

目标：替代真实 WhatsApp 回调，提前联调业务和前端。

开发内容：
- 实现 `MockMessagingProvider`
- 提供 `POST /dev/mock/inbound-message`
- 支持在 mock 入站消息中指定 `account_id`
- 提供开发态出站消息结果结构
- 统一消息标准化格式，和未来 WhatsAppProvider 共用

完成标准：
- 无 Meta 配置也能测试消息接收、消息回复、消息入库、前端展示

### Phase 5：日志、监控与队列基础

目标：在系统变复杂之前把可观测性和异步能力打底。

开发内容：
- 结构化日志
- `/metrics`
- 请求计数和错误率指标
- Redis 队列
- `worker` 启动入口
- 超时、重试、死信策略

完成标准：
- Webhook 或 mock 接入层可快速返回
- 耗时任务通过 worker 异步执行

### Phase 6：AI 基础能力

目标：先把 AI 架构做对，再追求高级效果。

开发内容：
- 实现 `AIProvider`
- 接入 `OpenAIProvider`
- 预留 `DeepSeekProvider`
- 实现最小 prompt
- 实现回复生成
- 实现失败降级
- 限制上下文长度

完成标准：
- `AI_PROVIDER=openai` 可工作
- `AI_PROVIDER=deepseek` 有兼容位
- 失败时可回退

### Phase 7：知识库与意图路由

目标：让客服能力从“会回复”升级到“会处理业务”。

开发内容：
- FAQ 检索
- 产品说明检索
- 规则优先路由
- 意图分类
- 订单查询路由
- 人工转接前置判断

完成标准：
- 常见问题优先走规则或检索
- 复杂问题再走 LLM

### Phase 8：电商 API 接入

目标：接入核心业务数据。

开发内容：
- 先实现 `MockEcommerceProvider`
- 定义订单、商品、物流接口契约
- 再接真实电商系统
- 加缓存、重试、熔断

完成标准：
- 订单和物流查询链路跑通

## 商城模块冻结边界

商城模块按“最小必做完成后冻结”处理，不再继续深挖商城能力。

必须保留：

1. `EcommerceProvider` 抽象
2. `MockEcommerceProvider`
3. 最小接口契约：
   - 订单详情
   - 物流详情
4. `account_id` 多账号作用域
5. AI 和人工工作台可调用订单/物流查询
6. 商城查询失败不能影响主消息链路
7. 真实 Provider 的替换接口位

以下内容默认后置，未经用户明确指令不得继续开发：

- 售后 / 退款扩展
- 商品 / 库存
- 商城 webhook 事件
- 会员深度绑定
- 主动营销联动
- 多商城平台适配
- 复杂缓存、同步、熔断

### Phase 9：前端后台

目标：给客服、运营和调试提供可视化界面。

开发内容：
- 初始化 React + Vite + TypeScript
- 实现聊天面板
- 实现模板管理页
- 实现系统设置页
- 实现基础数据看板
- 先接 mock API，再接真实 API

完成标准：
- 能查看会话
- 能发送 mock 消息
- 能看到 AI 处理结果和系统健康状态

### Phase 10：人工接管与模板管理

目标：进入客服真实业务闭环。

开发内容：
- 客服在线状态
- 会话分配
- 人工接管
- 会话关闭与回退 AI
- 模板创建、同步、发送、日志

完成标准：
- AI 无法处理时可稳定转人工
- 模板消息管理具备完整闭环

### Phase 11：监控、上线与恢复

目标：为上线做准备。

开发内容：
- Prometheus
- Grafana
- 告警规则
- 备份脚本
- CI/CD
- 部署文档
- 恢复手册

完成标准：
- 可部署
- 可监控
- 可审计
- 可回滚

### Phase 12：WhatsApp 正式接入

目标：在拿到 Meta 配置后，把 mock 接入切换为真实 WhatsApp 接入。

开发内容：
- 接入 PyWa
- 对接 `Embedded Signup` 完整流程
- 管理 `WABA -> phone numbers` 同步
- 对接 `WABA` 级 Webhook 订阅
- Webhook Verify
- 签名校验
- 模板发送
- 媒体消息支持
- 回调标准化

完成标准：
- 只替换接入层，不重写业务主流程

## 当前优先事项

在尚未拿到 WhatsApp 配置前，优先做以下内容：

1. FastAPI 项目骨架
2. `settings.py`
3. `MessagingProvider` 与 `MockMessagingProvider`
4. 多账户运行时模型与 AI 开关控制
5. `AIProvider` 与 `OpenAIProvider` skeleton
6. Redis worker skeleton
7. React + Vite + TypeScript skeleton
8. `/health` 与 `/metrics`
9. `.env.example`

## 当前主线优先级

从现在开始，主线优先级固定切换为以下顺序，并覆盖商城继续扩展的倾向：

1. WhatsApp / Meta 正式接入准备
2. 多账号后台完善
3. 人工接管闭环
4. 模板消息闭环
5. 监控、部署、上线准备

## 子 Agent 协作规则

从现在开始，主 Agent 不能单独包办所有开发。只要任务不是纯小修小补，就必须让相关子 agents 参与。

### 何时必须启用子 Agents

以下场景必须启用至少 2 个相关子 agents 共同参与：

1. 同时涉及后端、数据库、前端、AI、队列、监控中的两个或以上领域
2. 涉及多账户、WABA、Phone Number、Webhook、Embedded Signup 任一核心模型变更
3. 涉及 AI 自动回复、人工接管、翻译、多语言、运行时开关等核心流程变更
4. 涉及 Docker、迁移、测试、部署链路变更
5. 涉及需要并行推进的中等及以上功能开发

以下场景可由主 Agent 直接处理，不强制启用子 agents：

1. 单文件小修复
2. 纯文案修改
3. 不影响主流程的微小样式调整

### 主 Agent 职责

主 Agent 必须负责：

1. 拆解任务并指定子 agent 分工边界
2. 明确每个子 agent 的文件所有权与输出要求
3. 在并行工作结束后统一集成、复核、测试和对外汇报
4. 避免不同子 agent 写入同一批文件，减少冲突
5. 当子 agent 结论冲突时，由主 Agent 负责裁决

### 子 Agent 输出要求

每个子 agent 的结果必须至少包含：

1. 它负责的范围
2. 它修改或建议修改的文件
3. 风险点或未完成项
4. 建议补充的测试

### 文件所有权规则

为避免冲突，默认按以下边界协作：

- `api_agent`: `app/api/`、消息接入编排、Provider 路由
- `db_agent`: `app/db/`、`alembic/`、持久化模型与查询约束
- `ai_agent`: `app/providers/ai/`、AI/翻译/路由策略、Prompt 与降级策略
- `frontend_agent`: `frontend/src/` 页面、状态管理、前端接口封装
- `queue_agent`: `worker`、队列任务、重试与死信策略
- `human_handover_agent`: 接管状态机、客服分配、人工恢复 AI 规则
- `testing_agent`: `tests/`、回归覆盖、mock 隔离、集成验证
- `deploy_agent`: `Dockerfile`、`docker-compose.yml`、`.env.example`、启动脚本
- `monitoring_agent`: `/metrics`、告警规则、监控面板定义
- `logging_agent`: 结构化日志、审计日志、日志保留与脱敏策略

主 Agent 默认不把同一文件同时交给两个子 agents 修改。

### 当前项目的默认协作组合

在本项目中，默认按以下组合启用子 agents：

1. 后端 API 或消息链路开发：`api_agent` + `db_agent` + `testing_agent`
2. AI、翻译、多语言能力开发：`ai_agent` + `api_agent` + `testing_agent`
3. 中文后台与聊天工作台开发：`frontend_agent` + `api_agent` + `testing_agent`
4. 人工接管与运行时控制开发：`human_handover_agent` + `api_agent` + `db_agent` + `testing_agent`
5. 队列、异步任务、稳定性开发：`queue_agent` + `monitoring_agent` + `logging_agent` + `testing_agent`
6. 容器、启动、部署链路开发：`deploy_agent` + `monitoring_agent` + `testing_agent`

## 代码约束

1. 所有函数参数和返回值必须有类型注解。
2. I/O 优先异步实现。
3. 所有外部 API 调用必须有超时、日志和异常处理。
4. 配置统一从环境变量读取。
5. AI 和消息接入必须经过 Provider 抽象层。
6. 任何真实集成都必须先有 mock 版本。
7. 前端默认先接 mock API，不等待真实 WhatsApp 配置。
8. 所有实体默认带 `account_id`。
9. AI 自动回复必须遵守全局、账号、会话三级控制和人工接管状态。
10. Meta 相关实体必须保留官方 ID，不允许只保存本地别名。


<!-- CODEX_PARALLEL_AUTORUN_V2_START -->

# Codex 并行持续执行补充协议 V2

## 文档读取边界

- 默认只读取 `docs/README.md`、`docs/specs/active/README.md`、`docs/specs/active/IMPLEMENTATION_INDEX.md`、`docs/dev-run/**`。
- 不要默认读取 `docs/archive/**`。
- 不要默认读取 `docs/specs/active/full/**` 全量；只在当前 Worker 需要时读取对应一份。
- 不要扫描 `.git/**`、`.venv/**`、`.python/**`、`frontend/dist/**`、`frontend/.vite/**`。

## 断点恢复

- 每个阶段必须写入 `docs/dev-run/parallel/status/Wx.md`。
- 每次测试必须写入 `docs/dev-run/TEST_LOG.md`。
- 额度即将用完或会话即将结束时，先写 checkpoint。
- 新会话必须先运行 `python tools/codex/resume_preflight.py`，再继续未完成 Worker。
- 不要因为会话恢复重新做已完成阶段。

## 外部依赖缺失

- 缺少真实 Meta、B 服务器、SSH、域名、CDN、支付通道、生产密钥时，不暂停开发。
- 将缺失项写入 `docs/dev-run/parallel/env/EXTERNAL_BLOCKERS.md`。
- 用 dry-run、mock provider、fake gateway、配置占位、接口抽象、测试替身继续推进。
- 只有产品规则冲突、破坏性 migration、资金错账风险、无法自修的核心测试失败才停下来问用户。

## 并行开发

- 先完成 W0 共享基础。
- W1-W6 并行时严格遵守 `docs/dev-run/parallel/FILE_OWNERSHIP.md`。
- W9 负责共享文件合并和最终接线。
- 主控线程必须维护 `docs/dev-run/parallel/MASTER_PROGRESS.md` 并输出百分比。

<!-- CODEX_PARALLEL_AUTORUN_V2_END -->

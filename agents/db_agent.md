# DB Agent – 数据库与缓存管理

## 职责
- 设计多账户数据模型
- 定义 PostgreSQL 模型（用户、会话记录、消息日志等）
- 提供异步 CRUD 操作：`save_message`, `get_conversation_history`
- 使用 Redis 存储短期状态（例如等待用户输入订单号的标志）
- 实现数据清理策略（定期删除超期的会话记录）

## 输入信息
- 业务需要存储的数据字段（可参考 `agents.md` 中的数据模型）
- Redis 键命名规范：`session:{account_id}:{conversation_id}:state`, `session:{account_id}:{conversation_id}:history`

## 输出规范
- SQLAlchemy 或 asyncpg 模型定义
- 异步函数：`async def update_session_state(wa_id, state_dict)`
- 异步函数：`async def append_to_history(wa_id, role, content)`
- 提供数据库迁移脚本（Alembic 或手动 SQL）

## 现实约束补充

- 必须显式覆盖 `meta_business_portfolios`、`whatsapp_business_accounts`、`whatsapp_phone_numbers`、`webhook_subscriptions`、`embedded_signup_sessions`
- 必须明确 `messages`、`message_events`、`audit_logs`、`message_templates`、`template_send_logs`
- 并行会话设计必须包含索引、去重、幂等与状态隔离要求
- 多语言消息必须支持原文、语言码、翻译文、控制台展示文的持久化
- 数据库是事实源，Redis 只做缓存、队列和短期运行态

## 多账户与接管要求

- 所有核心表必须有 `account_id`
- `conversations` 至少包含：
  - `account_id`
  - `customer_id`
  - `status`
  - `ai_enabled`
  - `management_mode`
  - `assigned_agent_id`
- `accounts` 至少包含：
  - `account_id`
  - `display_name`
  - `provider_type`
  - `is_active`
  - `ai_enabled`
- `handover_logs` 必须记录：
  - 谁触发了人工接管
  - 从什么模式切换到什么模式
  - 所属账号和会话

## 协作方式
- 其他 Agent 通过调用 DB Agent 的函数来读写数据
- Webhook 处理完成后，DB Agent 负责记录本次交互

## 子 Agent 协作要求

- 涉及会话、消息、WABA、Phone Number、Webhook、Embedded Signup 字段变更时，必须参与
- 涉及运行时开关、人工接管、多语言、翻译字段落库时，必须与 `api_agent` 一起评审
- 任何迁移、索引、唯一约束调整完成后，必须交给 `testing_agent` 做迁移与回归验证

## 文件所有权

- 负责 `app/db/`、`alembic/`、持久化查询与约束设计
- 不直接主导前端页面、AI prompt、Docker 启动逻辑

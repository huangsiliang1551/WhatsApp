# API Agent - 消息接入与业务网关

## 职责
- 定义统一的 `MessagingProvider` 接口。
- 在没有 Meta 配置时，先实现 `MockMessagingProvider`。
- 在拿到 Meta 配置后，再实现 `WhatsAppProvider`。
- 标准化所有入站和出站消息，避免业务代码依赖具体渠道格式。
- 提供和电商接口、AI 路由、模板发送之间的编排层。
- 从设计第一天开始支持多账户。

## 当前开发策略

当前阶段禁止把业务逻辑直接耦合到 PyWa 或 Meta Webhook 结构上。

必须按以下顺序开发：
1. `MessagingProvider` 抽象
2. `MockMessagingProvider`
3. 消息标准化模型
4. 开发态 mock 入站接口
5. 真实 `WhatsAppProvider`

## 多账户要求

- 所有入站消息必须带 `account_id`
- 所有出站消息必须带 `account_id`
- Provider 初始化必须支持多个账号实例
- 不允许把系统做成“只有一个默认 WhatsApp 账号”的结构

## Meta 官方对象要求

- 必须区分 `Business Portfolio`、`WABA`、`Phone Number`
- 必须显式建模 `Webhook Subscription`
- 发送消息必须明确由哪个 `phone_number_id` 发出
- Webhook 处理必须先按 `waba_id` 分流
- 一个内部账户可映射一个 `WABA` 和多个 `Phone Number`
- 必须支持手工添加账户和 `Embedded Signup` 两种接入路径

## 现实约束补充

- 必须支持同账号多会话并行处理，不能按账号串行化
- 入站、出站、`message_events`、审计事件必须进入持久化层，不能只做内存路由
- 标准化消息必须携带语言元数据，至少包括源语言、检测来源、控制台展示文本
- 所有发送契约必须显式带 `account_id` 与 `phone_number_id`

## 输入信息
- 开发态 mock 消息体
- 统一消息模型
- 电商 API 契约
- Meta 配置，拿到后再启用

## 输出规范
- `normalize_inbound(payload) -> NormalizedMessage`
- `send_text_message(account_id, phone_number_id, recipient_id, text) -> OutboundResult`
- `send_template_message(...) -> OutboundResult`
- `verify_webhook(...) -> bool`
- `list_accounts() -> list[AccountRuntimeState]`
- `list_wabas() -> list[MetaWabaAccount]`
- `list_phone_numbers(waba_id) -> list[MetaPhoneNumber]`

## 约束
- 未拿到 Meta 配置前，不实现真实 webhook 联调作为主链路。
- 所有消息处理必须复用统一模型，不直接传递原始 Meta payload。
- Mock 和真实 Provider 必须共用相同业务入口。
- Mock Provider 必须支持多账户消息模拟。

## 子 Agent 协作要求

- 涉及接口字段、消息入库、查询结构变更时，必须同步拉上 `db_agent`
- 涉及 AI 自动回复、翻译、多语言路由时，必须同步拉上 `ai_agent`
- 涉及前端消费接口结构变更时，必须同步拉上 `frontend_agent`
- 任意新增或修改 API 后，必须同步拉上 `testing_agent`

## 文件所有权

- 负责 `app/api/`、消息接入编排层、Provider 装配层
- 不直接主导修改 `frontend/`、`alembic/`、`tests/`，这些由对应子 agents 负责

# 会话交接文档（主线续做）

最后更新时间：`2026-06-12`

适用目标：
- 新开会话后，直接继续当前仓库主线开发
- 不从头规划
- 允许新会话自行扫描目录，但先读本文件能少走很多弯路

项目目录：
- `E:\codex\WhatsApp`

必须继续遵守：
- 仓库内 `Agents.md`
- 用户在线程里追加的 AGENTS 约束
- 当前主线原则：继续现有 WhatsApp / 多账号 / 人工接管 / H5 并行主线，不重排、不推倒重来

---

## 1. 先读这个：固定方向与硬约束

### 1.1 技术栈与总方向

- 后端：FastAPI
- WhatsApp 接入：PyWa，当前仍以 mock-first 开发
- 数据层：PostgreSQL + Redis
- 前端：React + Vite + TypeScript
- AI 主方案：OpenAI
- AI 备用：DeepSeek
- 运行方式：Docker Compose

### 1.2 当前现实约束

还没有拿到 Meta 正式接入关键配置，所以现在仍然是：
- 先做不依赖 Meta 配置的内容
- 消息接入必须走 `MessagingProvider`
- 先 `MockMessagingProvider`，后 `WhatsAppProvider`
- 业务层、AI、前端、电商、队列都不能直接依赖 Meta webhook 原始结构

### 1.3 必须保持的架构要求

- 多账号是硬约束，不能按单账号产品思路继续开发
- 所有新业务实体默认带 `account_id`
- 会话并行、AI 托管、人工接管、三级 AI 开关优先级不能破坏
- H5 正式身份必须由服务端会话推导，不能再信任前端传正式作用域
- 所有真实集成都必须先有 mock 版本

### 1.4 子 Agent 协作规则

这条很重要，新会话不要忽略：
- 只要不是纯小修小补，就必须启用子 agents
- 涉及两个以上领域、数据库变更、H5/平台/测试联动、Docker/迁移/测试链路时，至少 2 个相关子 agent
- 主 Agent 负责拆分边界、集成、复核、测试、对外汇报

---

## 2. 当前主线状态总览

### 2.1 不要重新规划

这条是用户反复强调的：
- 继续当前仓库主线开发
- 不要从头规划
- H5 会员端后端是“并行主线支线”，不改写 WhatsApp / 多账号 / 人工接管主线排序

### 2.2 H5 并行主线总体状态

按用户给出的 `H5 会员端后端并行主线计划`，代码里已经落地到较完整状态，至少以下能力已经有实际实现与测试：

- Slice 1：H5 认证与会员身份闭环
- Slice 2：认证态首页摘要与现有任务/工单切换
- Slice 3：任务包 + 钱包底座 + H5 订单列表
- Slice 4：提现与排行榜闭环
- Slice 5：消息中心闭环
- Slice 6：碎片与邮寄闭环
- H5 会员认证域
- H5 WhatsApp 绑定占位与平台审核闭环
- 平台侧会员认证管理 API
- 平台侧会员 WhatsApp 绑定管理 API

结论：
- H5 后端不是空壳，已经从认证到钱包、提现、消息、碎片、邮寄、认证、WhatsApp 绑定都打通了
- 当前更像“持续集成与平台工作台联动完善阶段”，不是“从 0 到 1 搭骨架阶段”

---

## 3. 当前已经完成的后端能力

## 3.1 FastAPI 主入口与路由聚合

主入口：
- [app/main.py](E:/codex/WhatsApp/app/main.py)

这里已经挂载了以下 H5 / 平台相关路由：
- `h5_auth_router`
- `h5_member_commerce_router`
- `h5_member_fragments_router`
- `h5_member_messages_router`
- `h5_member_verification_router`
- `h5_member_whatsapp_binding_router`
- `h5_router`
- `platform_member_whatsapp_bindings_router`
- `platform_member_verifications_router`
- `platform_withdrawals_router`

说明：
- 不是散落未接线的代码，路由已接入应用入口
- 请求上下文、中间件、统一异常、request_id 也都已经在主入口里接好

## 3.2 H5 认证与会员身份

关键路由：
- [app/api/routes/h5_auth.py](E:/codex/WhatsApp/app/api/routes/h5_auth.py)

已有接口：
- `POST /api/h5/auth/register`
- `POST /api/h5/auth/login`
- `POST /api/h5/auth/logout`
- `POST /api/h5/auth/refresh`
- `GET /api/h5/auth/me`
- `GET /api/h5/member/home`

关键依赖：
- [app/api/deps.py](E:/codex/WhatsApp/app/api/deps.py)
  - `get_current_h5_member_context`
  - `get_h5_member_auth_service`

关键服务：
- [app/services/h5_member_auth_service.py](E:/codex/WhatsApp/app/services/h5_member_auth_service.py)

已确认行为：
- 正式 H5 身份从 cookie/session 解析
- `member_no` 是 8 位随机数字
- `(account_id, member_no)` 唯一
- 不再依赖前端传 `public_user_id/site_key/account_id` 作为正式身份来源

## 3.3 认证态 H5 首页 / 任务 / 工单

关键路由：
- [app/api/routes/h5.py](E:/codex/WhatsApp/app/api/routes/h5.py)

这里已经实现或兼容了：
- `GET /api/h5/bootstrap`
- `GET /api/h5/tasks`
- `GET /api/h5/tasks/{task_instance_id}`
- `POST /api/h5/task-proofs`
- `POST /api/h5/tasks/{task_instance_id}/submit`
- `GET /api/h5/tickets`
- `POST /api/h5/tickets`

当前状态判断：
- 这些接口已经改成“优先走认证态”
- 旧 query 模式仍有兼容痕迹，但正式身份解析已通过 `_resolve_h5_context_with_auth(...)`
- 任务/工单链路仍保留既有业务规则

## 3.4 任务包 / 钱包 / 订单 / 提现榜

关键路由：
- [app/api/routes/h5_member_commerce.py](E:/codex/WhatsApp/app/api/routes/h5_member_commerce.py)

已有接口：
- `GET /api/h5/task-packages`
- `GET /api/h5/task-packages/{package_id}`
- `POST /api/h5/task-packages/{package_id}/claim`
- `POST /api/h5/task-packages/{package_id}/items/{item_id}/purchase`
- `GET /api/h5/orders`
- `GET /api/h5/wallet`
- `GET /api/h5/wallet/transactions`
- `POST /api/h5/wallet/recharges`
- `POST /api/h5/wallet/transfers`
- `POST /api/h5/withdrawals`
- `GET /api/h5/withdrawals`
- `GET /api/h5/withdraw-leaderboard`

关键服务：
- [app/services/h5_member_commerce_service.py](E:/codex/WhatsApp/app/services/h5_member_commerce_service.py)

已确认能力：
- 任务包领取
- 包内商品购买
- 系统余额扣款
- 任务余额结算
- 订单列表
- 余额划转
- 提现申请
- 排行榜累计提现金额统计

## 3.5 消息中心

关键路由：
- [app/api/routes/h5_member_messages.py](E:/codex/WhatsApp/app/api/routes/h5_member_messages.py)

已有接口：
- `GET /api/h5/messages`
- `POST /api/h5/messages/read-all`
- `GET /api/h5/messages/{message_id}`
- `POST /api/h5/messages/{message_id}/read`

关键服务：
- [app/services/h5_member_notification_service.py](E:/codex/WhatsApp/app/services/h5_member_notification_service.py)

已确认规则：
- 消息中心与工单分离
- 首页未读数走这个域
- 不把内部客服消息混入 `tickets`

## 3.6 碎片 / 邮寄

关键路由：
- [app/api/routes/h5_member_fragments.py](E:/codex/WhatsApp/app/api/routes/h5_member_fragments.py)

已有接口：
- `GET /api/h5/fragments`
- `POST /api/h5/fragments/check-in`
- `POST /api/h5/fragments/exchanges`
- `GET /api/h5/rewards/shipping`

关键服务：
- [app/services/h5_member_fragment_service.py](E:/codex/WhatsApp/app/services/h5_member_fragment_service.py)

已确认能力：
- 签到掉落
- 任务完成掉落
- 碎片背包
- 掉落日志
- 兑换并生成邮寄申请
- 邮寄状态列表

## 3.7 H5 会员认证

关键路由：
- [app/api/routes/h5_member_verification.py](E:/codex/WhatsApp/app/api/routes/h5_member_verification.py)

关键服务：
- [app/services/h5_member_verification_service.py](E:/codex/WhatsApp/app/services/h5_member_verification_service.py)

已确认能力：
- 提交认证申请
- 查看当前认证摘要
- 查看历史申请
- 查看申请详情
- 平台审核后，H5 状态同步变化
- H5 消息中心可看到审核通知

## 3.8 H5 WhatsApp 绑定占位

关键路由：
- [app/api/routes/h5_member_whatsapp_binding.py](E:/codex/WhatsApp/app/api/routes/h5_member_whatsapp_binding.py)

关键服务：
- [app/services/h5_member_whatsapp_binding_service.py](E:/codex/WhatsApp/app/services/h5_member_whatsapp_binding_service.py)

已确认能力：
- 查询绑定状态
- 发起绑定流程占位 `start`
- 平台审批后回写状态
- 绑定成功可同步 `AppUser.has_whatsapp`

## 3.9 平台端会员认证管理

关键路由：
- [app/api/routes/platform_member_verifications.py](E:/codex/WhatsApp/app/api/routes/platform_member_verifications.py)

关键服务：
- [app/services/platform_member_verification_service.py](E:/codex/WhatsApp/app/services/platform_member_verification_service.py)

已确认能力：
- 平台按 `account_id` 列表查看认证申请
- 平台查看认证详情
- 平台变更认证状态
- 写审计日志
- 兼容旧 approve/reject action 风格路由

## 3.10 平台端会员 WhatsApp 绑定管理

关键路由：
- [app/api/routes/platform_member_whatsapp_bindings.py](E:/codex/WhatsApp/app/api/routes/platform_member_whatsapp_bindings.py)

关键服务：
- [app/services/platform_member_whatsapp_binding_service.py](E:/codex/WhatsApp/app/services/platform_member_whatsapp_binding_service.py)

已确认能力：
- 平台按账号查看绑定申请
- 平台查看单条绑定详情
- 平台修改绑定状态
- 写审计日志
- 绑定成功后同步 `UserIdentity` / `AppUser.has_whatsapp`

---

## 4. 当前数据库 / 迁移状态

## 4.1 模型总入口

核心模型文件：
- [app/db/models.py](E:/codex/WhatsApp/app/db/models.py)

这个文件非常大，包含：
- 多账号 / Meta / 会话 / 消息 / 模板
- H5 site / app user / invite / task / ticket
- H5 member auth / wallet / withdrawal / notification / fragment / mailing / verification / whatsapp binding

## 4.2 已落地的 H5 关键表

在 [app/db/models.py](E:/codex/WhatsApp/app/db/models.py) 中已经有以下实体：

- `member_profiles`
- `member_auth_sessions`
- `member_verification_requests`
- `member_verification_documents`
- `member_whatsapp_binding_requests`
- `member_notifications`
- `task_package_templates`
- `task_package_template_items`
- `task_package_instances`
- `task_package_instance_items`
- `promotion_task_templates`
- `promotion_task_instances`
- `user_referrals`
- `wallet_accounts`
- `wallet_ledger_entries`
- `wallet_transfer_requests`
- `wallet_recharge_orders`
- `withdrawal_requests`
- `withdrawal_audit_logs`
- `fragment_definitions`
- `fragment_inventory`
- `fragment_ledger_entries`
- `fragment_drop_logs`
- `fragment_exchange_requests`
- `mailing_requests`
- `mailing_shipments`

## 4.3 最近相关迁移

`alembic/versions` 里和 H5 主线强相关的迁移：

- `20260611_0057_h5_member_auth.py`
- `20260611_0058_h5_member_slice3_commerce.py`
- `20260611_0059_h5_member_withdrawals.py`
- `20260611_0060_h5_member_notifications.py`
- `20260611_0061_h5_member_fragments_and_mailing.py`
- `20260611_0062_h5_member_promotion_tasks.py`
- `20260612_0063_h5_wallet_ledger_idempotent_reward_scope.py`
- `20260612_0064_h5_member_verification_review_metadata.py`
- `20260612_0065_h5_member_whatsapp_binding_requests.py`

结论：
- 数据库层不是半成品，H5 并行主线对应迁移已经连续落库
- 新会话如果要改 schema，先读这些迁移，避免重复造轮子

## 4.4 数据库契约测试入口

重点测试：
- [tests/test_db_schema.py](E:/codex/WhatsApp/tests/test_db_schema.py)
- [tests/test_alembic_upgrade.py](E:/codex/WhatsApp/tests/test_alembic_upgrade.py)

这些测试已经明确锁定：
- 相关表存在
- 关键列存在
- 唯一约束、索引、外键存在
- H5 新表的 account scope、member scope、fragment scope、wallet scope 已被契约化

---

## 5. 当前已经完成的前端能力

以下内容综合代码检查和前一轮工作总结。

## 5.1 平台后台壳层与入口

主入口：
- [frontend/src/main.tsx](E:/codex/WhatsApp/frontend/src/main.tsx)
- [frontend/src/App.tsx](E:/codex/WhatsApp/frontend/src/App.tsx)

路由与页面切换：
- [frontend/src/routes/consoleRoutes.ts](E:/codex/WhatsApp/frontend/src/routes/consoleRoutes.ts)
- [frontend/src/routes/adminUrlState.ts](E:/codex/WhatsApp/frontend/src/routes/adminUrlState.ts)

状态中心：
- [frontend/src/stores/appStore.ts](E:/codex/WhatsApp/frontend/src/stores/appStore.ts)

当前后台不是纯 mock 展示，已经挂载：
- `customers`
- `users`
- `tasks`
- `operations`
- `assignments`
- `reviews`
- `tickets`
- `members`
- `member_access`
- `meta`
- `templates`
- `conversations`
- 以及 H5 入口

## 5.2 H5 会员端页面

主页面文件：
- [frontend/src/pages/H5App.tsx](E:/codex/WhatsApp/frontend/src/pages/H5App.tsx)

当前已经承载：
- 登录
- 注册
- 首页
- 任务包列表
- 任务包详情
- 消息中心
- 我的
- 钱包 / 充值 / 提现
- 订单列表
- 工单列表 / 详情 / 新建
- 碎片背包
- 排行榜
- 推广
- 会员认证
- WhatsApp 绑定

说明：
- H5App 已经很大
- 它是当前最值得拆分的前端文件之一

## 5.3 H5 前端服务层

关键服务文件：
- [frontend/src/services/h5Member.ts](E:/codex/WhatsApp/frontend/src/services/h5Member.ts)
- [frontend/src/services/h5.ts](E:/codex/WhatsApp/frontend/src/services/h5.ts)

当前状态：
- `h5Member.ts` 已经是“正式 H5 后端优先 + 受控 fallback”的服务层
- `h5.ts` 还保留任务/工单相关服务与平台认证/绑定接口类型

重点：
- `h5Member.ts` 已经直接对接：
  - `/api/h5/member/home`
  - `/api/h5/withdrawals`
  - `/api/h5/messages`
  - `/api/h5/member/verification`
  - `/api/h5/fragments`
  - `/api/h5/whatsapp-binding`
- 且已经处理 `credentials: include`、401 refresh retry、legacy fallback

## 5.4 平台 member-status / customer drill-through 主线

这是最近一直在推进的重点。

共享服务入口：
- [frontend/src/services/operations.ts](E:/codex/WhatsApp/frontend/src/services/operations.ts)

关键函数：
- `listPlatformUserMemberStatusIndex`
- `getCustomerMemberStatusSnapshot`
- `selectCustomerProfileForConversation`
- `resolveCustomerProfileSummaryByConversation`

已经接入这条主线的页面：
- [frontend/src/pages/UsersPage.tsx](E:/codex/WhatsApp/frontend/src/pages/UsersPage.tsx)
- [frontend/src/pages/CustomersPage.tsx](E:/codex/WhatsApp/frontend/src/pages/CustomersPage.tsx)
- [frontend/src/pages/ChatPage.tsx](E:/codex/WhatsApp/frontend/src/pages/ChatPage.tsx)
- [frontend/src/pages/AssignmentsPage.tsx](E:/codex/WhatsApp/frontend/src/pages/AssignmentsPage.tsx)
- [frontend/src/pages/OperationsCenterPage.tsx](E:/codex/WhatsApp/frontend/src/pages/OperationsCenterPage.tsx)
- [frontend/src/pages/TasksPage.tsx](E:/codex/WhatsApp/frontend/src/pages/TasksPage.tsx)
- [frontend/src/pages/TicketsPage.tsx](E:/codex/WhatsApp/frontend/src/pages/TicketsPage.tsx)
- [frontend/src/pages/ReviewsPage.tsx](E:/codex/WhatsApp/frontend/src/pages/ReviewsPage.tsx)

已实现能力：
- 从用户、任务、工单、会话、运营页跳到 `CustomersPage`
- `CustomersPage` 通过 `customersPagePrefill` 接收预填并恢复目标客户
- 在多个后台页展示会员认证状态、WhatsApp 绑定状态
- 会话页/分配页已经实现 `conversation -> customer profile -> member status` 联动

## 5.5 后台跳转状态机制

关键状态定义：
- [frontend/src/stores/appStore.ts](E:/codex/WhatsApp/frontend/src/stores/appStore.ts)

关键点：
- `customersPagePrefill`
- `openCustomersPage(...)`
- `clearCustomersPagePrefill()`

`CustomersPage` 中已消费该状态：
- [frontend/src/pages/CustomersPage.tsx](E:/codex/WhatsApp/frontend/src/pages/CustomersPage.tsx)

具体逻辑：
- 通过 `nonce` 防止重复消费
- 可恢复 `account_id`
- 可恢复 `query`
- 可恢复 `selected_profile_id`

这套机制已经被测试锁定，不要随便改 key 名和行为

---

## 6. 关键测试地图

## 6.1 H5 后端核心测试

认证与作用域：
- [tests/test_h5_member_auth.py](E:/codex/WhatsApp/tests/test_h5_member_auth.py)

任务包 / 钱包 / 推广：
- [tests/test_h5_task_packages_wallet.py](E:/codex/WhatsApp/tests/test_h5_task_packages_wallet.py)
- [tests/test_h5_task_packages_wallet_postgres.py](E:/codex/WhatsApp/tests/test_h5_task_packages_wallet_postgres.py)

提现：
- [tests/test_h5_withdrawals.py](E:/codex/WhatsApp/tests/test_h5_withdrawals.py)

消息：
- [tests/test_h5_member_messages.py](E:/codex/WhatsApp/tests/test_h5_member_messages.py)

碎片与邮寄：
- [tests/test_h5_fragments.py](E:/codex/WhatsApp/tests/test_h5_fragments.py)

会员认证：
- [tests/test_h5_member_verification.py](E:/codex/WhatsApp/tests/test_h5_member_verification.py)

WhatsApp 绑定：
- [tests/test_h5_member_whatsapp_binding.py](E:/codex/WhatsApp/tests/test_h5_member_whatsapp_binding.py)

平台会员认证管理：
- [tests/test_platform_member_verifications.py](E:/codex/WhatsApp/tests/test_platform_member_verifications.py)

平台会员 WhatsApp 绑定管理：
- [tests/test_platform_member_whatsapp_bindings.py](E:/codex/WhatsApp/tests/test_platform_member_whatsapp_bindings.py)

平台提现管理：
- [tests/test_platform_withdrawals.py](E:/codex/WhatsApp/tests/test_platform_withdrawals.py)

## 6.2 前端测试

H5 前端服务层：
- [frontend/src/services/h5Member.test.ts](E:/codex/WhatsApp/frontend/src/services/h5Member.test.ts)
- [frontend/src/services/h5.test.ts](E:/codex/WhatsApp/frontend/src/services/h5.test.ts)

平台 member-status 聚合服务：
- [frontend/src/services/operations.test.ts](E:/codex/WhatsApp/frontend/src/services/operations.test.ts)

最近新增的高价值页面行为测试：
- [frontend/src/pages/memberCustomerNavigation.test.tsx](E:/codex/WhatsApp/frontend/src/pages/memberCustomerNavigation.test.tsx)

源码契约测试：
- [tests/test_h5_frontend_ticket_contract.py](E:/codex/WhatsApp/tests/test_h5_frontend_ticket_contract.py)
- [tests/test_assignments_frontend_contract.py](E:/codex/WhatsApp/tests/test_assignments_frontend_contract.py)
- [tests/test_h5_member_prototype_contract.py](E:/codex/WhatsApp/tests/test_h5_member_prototype_contract.py)
- [tests/test_h5_member_camelcase_contract.py](E:/codex/WhatsApp/tests/test_h5_member_camelcase_contract.py)

## 6.3 最近明确通过过的命令

上一轮已确认通过：
- `npm test -- src/pages/memberCustomerNavigation.test.tsx`
- `.\.venv\Scripts\python.exe -m pytest tests\test_h5_frontend_ticket_contract.py -q`
- `npm run build`

构建仍有历史非阻塞 warning：
- 大 chunk warning
- `vendor-antd` 相关 circular chunk warning

---

## 7. 已知坑点与接力时不要踩的地方

## 7.1 不要把 H5 正式身份改回 query 契约

现在正式方向已经很明确：
- H5 正式身份必须由服务端会话推出
- 不要重新扩散 `site_key + public_user_id` 作为正式访问契约

兼容逻辑可以暂留，但不要再把它当主方向维护

## 7.2 `member-status` 聚合不要重新分散到页面

平台后台这条线已经确定：
- 页面不要自己散着调 `listPlatformMemberVerifications` / `listPlatformMemberWhatsAppBindings`
- 统一走 [frontend/src/services/operations.ts](E:/codex/WhatsApp/frontend/src/services/operations.ts) 的聚合层

否则容易破坏：
- 匹配优先级
- account scope
- UI 一致性
- 已有测试契约

## 7.3 `conversation -> customer profile` 不是强外键

这一条很重要：
- 不要把 `customer_id` 直接当稳定 member/profile id
- 当前逻辑是解析匹配
- 优先级已被 `operations.test.ts` 锁定

## 7.4 `CustomersPage` 跳转链路已被锁死

不要随便改：
- `openCustomersPage(...)`
- `customersPagePrefill`
- `nonce`
- `account_id`
- `selected_profile_id`
- `query`

这些字段已经被：
- 页面行为测试
- 源码契约测试
- URL 状态联动
共同依赖

## 7.5 `TasksPage` 之前出现过“注释代码骗过静态测试”的问题

已知历史坑：
- `TasksPage` 曾经 customer jump 只存在于被注释的旧列定义里
- 静态契约测试能过，但真实 UI 没功能

后续看任务页时：
- 先看真实生效的 column
- 不要只靠 grep

## 7.6 `H5App.tsx` 已经过大

继续往里堆功能会越来越难接手：
- 路由解析、状态、视图、表单、购买动画、碎片、认证都混在一个文件
- 新会话如果继续做 H5 前端，优先考虑“局部拆分而不是继续加巨石”

## 7.7 当前目录里 `git status` 不可直接用

本轮在 `E:\codex\WhatsApp` 执行 `git status --short` 返回：
- `fatal: not a git repository (or any of the parent directories): .git`

含义可能有两种：
- 当前目录不是实际 git 根
- 或当前会话环境没有正确暴露仓库元数据

所以新会话如果要依赖 git 信息：
- 先自己确认 `.git` 是否可用
- 不要把“git status 失败”误判成代码丢失

---

## 8. 新会话建议优先继续什么

下面是最值得继续的方向，按优先级给。

## 8.1 第一优先：补强平台 customer drill-through 集成验证

原因：
- 这条主线最近一直在推进
- 已经有服务聚合、页面跳转、行为测试基础
- 继续做能最快减少回归

建议动作：
- 加一个更高层级的集成测试
- 最好从 `App.tsx` 或更接近真实路由的层面验证：
  - source page 触发 jump
  - `CustomersPage` 成为 active page
  - prefill 被消费
  - detail/member status 被加载

注意：
- 不要过度锁定 Antd DOM 结构
- 不要过度锁 URL query 顺序
- 重点锁业务行为

## 8.2 第二优先：抽共享 customer/member-status hook 或 panel

原因：
- `Chat / Assignments / Customers / Users / Tickets` 都有重复的 member status 载入逻辑
- 当前重复的 `loading/error/requestIdRef/latestVerification/latestBinding` 很容易漂移

建议边界：
- 保持入口不变
- 聚合仍经 `operations.ts`
- 跳转仍经 `appStore.ts`
- 先抽只读展示组件或 hook，不要一次性大重构

## 8.3 第三优先：拆 `H5App.tsx`

建议拆分顺序：
- `auth`
- `home`
- `wallet/withdraw`
- `verification`
- `whatsapp`
- `fragments`
- `tickets`

目标：
- 保持功能不变
- 把视图切成子组件或子路由模块
- 减少后续维护成本

## 8.4 如果继续做后端，优先查这些空白

虽然 H5 主线大部分已落地，但仍可能有以下残余工作可继续：
- 平台侧把 H5 新域更多地纳入后台管理页联动
- 推广任务在前端/后台上的可视化完成度
- 平台提现工作台与 H5 钱包链路的联动细化
- 订单列表/钱包/消息的更多平台态观察入口
- 继续补 PostgreSQL 路径下的回归测试

原则：
- 不要重复造 H5 已有表和接口
- 先找“平台联动 / 可维护性 / 验证缺口”

---

## 9. 新会话建议启动步骤

建议新会话先按下面顺序做，不要上来大面积乱扫：

1. 先读本文件。
2. 再读：
   - [Agents.md](E:/codex/WhatsApp/Agents.md)
   - [app/main.py](E:/codex/WhatsApp/app/main.py)
   - [app/api/deps.py](E:/codex/WhatsApp/app/api/deps.py)
   - [frontend/src/App.tsx](E:/codex/WhatsApp/frontend/src/App.tsx)
   - [frontend/src/stores/appStore.ts](E:/codex/WhatsApp/frontend/src/stores/appStore.ts)
3. 如果要接 H5 后端，优先读：
   - [app/api/routes/h5_auth.py](E:/codex/WhatsApp/app/api/routes/h5_auth.py)
   - [app/api/routes/h5_member_commerce.py](E:/codex/WhatsApp/app/api/routes/h5_member_commerce.py)
   - [app/api/routes/h5_member_messages.py](E:/codex/WhatsApp/app/api/routes/h5_member_messages.py)
   - [app/api/routes/h5_member_fragments.py](E:/codex/WhatsApp/app/api/routes/h5_member_fragments.py)
   - [app/services/h5_member_auth_service.py](E:/codex/WhatsApp/app/services/h5_member_auth_service.py)
   - [app/services/h5_member_commerce_service.py](E:/codex/WhatsApp/app/services/h5_member_commerce_service.py)
4. 如果要接平台 member-status 前端，优先读：
   - [frontend/src/services/operations.ts](E:/codex/WhatsApp/frontend/src/services/operations.ts)
   - [frontend/src/pages/CustomersPage.tsx](E:/codex/WhatsApp/frontend/src/pages/CustomersPage.tsx)
   - [frontend/src/pages/ChatPage.tsx](E:/codex/WhatsApp/frontend/src/pages/ChatPage.tsx)
   - [frontend/src/pages/AssignmentsPage.tsx](E:/codex/WhatsApp/frontend/src/pages/AssignmentsPage.tsx)
   - [frontend/src/pages/OperationsCenterPage.tsx](E:/codex/WhatsApp/frontend/src/pages/OperationsCenterPage.tsx)
   - [frontend/src/pages/TasksPage.tsx](E:/codex/WhatsApp/frontend/src/pages/TasksPage.tsx)
   - [frontend/src/pages/memberCustomerNavigation.test.tsx](E:/codex/WhatsApp/frontend/src/pages/memberCustomerNavigation.test.tsx)
5. 开工前先确认你这次是：
   - 修测试
   - 补页面联动
   - 抽共享 hook/组件
   - 还是补后端联动
6. 不是小修小补的话，按 AGENTS 规则启用至少 2 个子 agents。

---

## 10. 可以直接复制给新会话的简版启动提示

如果需要把最核心上下文直接发给新会话，可以用下面这段：

```text
继续当前仓库主线开发，不要重新规划。先读 docs/session-handoff-mainline-2026-06-12.md，再遵守 Agents.md 和线程里的 AGENTS 约束。

当前仓库里 H5 并行主线已经不是骨架阶段，以下能力已落地并有测试：H5 认证、认证态首页/任务/工单、任务包、钱包、订单列表、提现与排行榜、消息中心、碎片与邮寄、会员认证、WhatsApp 绑定、平台侧会员认证管理、平台侧会员 WhatsApp 绑定管理。

前端最近主线是平台后台 customer/member-status drill-through：Users/Customers/Chat/Assignments/OperationsCenter/Tasks/Tickets/Reviews 已部分接入 shared member-status 聚合，统一走 frontend/src/services/operations.ts，不要在页面里散着重新拉 verification/binding 列表。CustomersPage 的 prefill 跳转链路已经被测试锁定，继续沿用 openCustomersPage + customersPagePrefill + nonce。

优先建议继续做：
1. customer drill-through 更高层级集成测试
2. 抽共享 customer/member-status hook 或 panel
3. 拆分 H5App.tsx

关键文件：
- app/main.py
- app/api/deps.py
- app/api/routes/h5_auth.py
- app/api/routes/h5_member_commerce.py
- app/api/routes/h5_member_messages.py
- app/api/routes/h5_member_fragments.py
- app/services/h5_member_auth_service.py
- app/services/h5_member_commerce_service.py
- app/db/models.py
- frontend/src/App.tsx
- frontend/src/stores/appStore.ts
- frontend/src/services/operations.ts
- frontend/src/pages/CustomersPage.tsx
- frontend/src/pages/ChatPage.tsx
- frontend/src/pages/AssignmentsPage.tsx
- frontend/src/pages/OperationsCenterPage.tsx
- frontend/src/pages/TasksPage.tsx
- frontend/src/pages/H5App.tsx
- frontend/src/pages/memberCustomerNavigation.test.tsx
```

---

## 11. 本轮补充说明

- 本文档是基于当前仓库文件、已有测试、最近连续主线推进记录整理的
- 不是“理想计划”，而是“当前真实已落地状态 + 接力建议”
- 新会话如果发现个别局部实现与本文档有细小偏差，以实际代码为准，但不要据此重启规划


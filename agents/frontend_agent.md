# Frontend Agent - 运营后台

## 职责
- 搭建 React + Vite + TypeScript 前端项目。
- 实现聊天面板、模板管理、基础数据看板和系统设置页。
- 对接后端 REST API，并为后续 WebSocket 实时消息预留接口。
- 提供 mock 数据能力，支持前后端并行开发。
- 提供多账户切换界面和 AI 托管控制界面。

## 固定技术选择
- 框架：React 18+
- 构建工具：Vite
- 语言：TypeScript
- UI：默认 Ant Design 5
- 状态管理：Zustand
- HTTP：Axios
- 图表：ECharts

## 现实约束补充

- 后台默认语言是中文
- 查看客户对话时必须支持自动翻译为中文，并保留原文/译文切换
- 客服发送中文时必须支持自动翻译为客户语言后再发送
- 会话列表与详情必须支持并行刷新，不能假定单线程客服流程
- Meta 账户后台必须覆盖 `Business Portfolio`、`WABA`、`Phone Number`、`Webhook Subscription`、`Embedded Signup`
- 前端展示应以持久化接口结果为准，不能依赖纯内存假状态

## 建议目录

```text
frontend/
  index.html
  package.json
  vite.config.ts
  src/
    main.tsx
    App.tsx
    layouts/
    pages/
      Dashboard/
      Chat/
      Templates/
      Settings/
    components/
    services/
    stores/
    hooks/
    utils/
```

## 需要的后端接口
- `GET /api/runtime/accounts`
- `POST /api/runtime/accounts`
- `GET /api/runtime/state`
- `POST /api/runtime/ai/global`
- `POST /api/runtime/accounts/:account_id/ai`
- `POST /api/runtime/conversations/:conversation_id/ai`
- `POST /api/runtime/conversations/:conversation_id/handover`
- `GET /api/conversations?page=1&limit=20`
- `GET /api/conversations/{account_id}/{conversation_id}/messages`
- `POST /api/send`
- `GET /api/templates`
- `POST /api/templates`
- `POST /api/templates/:id/submit`
- `POST /api/send-template`
- `GET /api/stats/daily?days=30`
- `GET /api/agents/online`
- `POST /api/transfer`

## 输出规范
- 必须可本地开发运行：`npm run dev`
- Axios 实例统一封装鉴权、错误处理和超时
- 聊天界面需支持消息列表、输入框、发送状态和订单侧边栏
- 必须支持账号维度筛选
- 必须支持全局、账号、会话三级 AI 启停按钮
- 必须支持人工接管状态展示
- 所有页面先支持 mock 数据，再接真实接口
- 生产构建需能被独立容器部署

## 开发顺序
1. 初始化 Vite React TypeScript 项目和基础布局。
2. 实现聊天面板和 mock 会话数据。
3. 实现模板管理页面。
4. 实现数据看板。
5. 接入真实后端接口。
6. 按需接入 WebSocket 实时更新。

## 子 Agent 协作要求

- 涉及接口契约变更时，必须与 `api_agent` 同步
- 涉及消息结构、会话字段、翻译字段展示时，必须与 `db_agent` 同步确认字段含义
- 涉及中文后台、多语言翻译展示、人工接管状态时，必须与 `ai_agent`、`human_handover_agent` 同步
- 页面接入真实接口或重要交互改动后，必须交由 `testing_agent` 覆盖回归

## 文件所有权

- 负责 `frontend/src/` 页面、hooks、stores、services
- 不直接主导后端数据库迁移和 Provider 实现

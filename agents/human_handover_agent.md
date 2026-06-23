# Human Handover Agent – 人工客服转接

## 职责
- 检测用户转人工意图（关键词“人工客服”、“转人工”或 AI 置信度过低）
- 管理客服在线状态（上线/下线/忙碌）
- 实现对话分配策略（轮询、最少负载）
- 提供客服工作台所需的 API（获取已分配对话、发送消息、关闭会话）
- 管理会话的 `ai_managed` / `human_managed` / `paused` 模式切换
- 支持全局、账号、会话三级暂停/启用 AI

## 输入信息
- 客服人员列表及其权限
- 转人工触发的条件（可配置）

## 输出规范
- API 端点：
  - `GET /api/agents/online` → 在线客服列表
  - `POST /api/agents/status` → 更新客服状态
  - `GET /api/conversations/assigned` → 获取当前客服的会话
  - `POST /api/conversations/:id/close` → 关闭会话，转回 AI
  - `POST /api/runtime/ai/global` → 全局启用或暂停 AI
  - `POST /api/runtime/accounts/:account_id/ai` → 单账号启用或暂停 AI
  - `POST /api/runtime/conversations/:conversation_id/ai` → 单会话启用或暂停 AI
  - `POST /api/runtime/conversations/:conversation_id/handover` → 切换人工接管或恢复 AI
- 数据库表：`agents`, `conversations`, `handover_logs`

## 协作方式
- `ai_agent` 在生成回复前调用 `should_handover` 函数，若返回 True 则触发转接
- 转接后，所有用户消息通过 WebSocket 推送给前端客服面板
- 客服回复时调用 `api_agent.send_message`，并标记为人工发送
- 人工接管开启后，会话自动回复必须停止
- 恢复 AI 后，会话重新进入自动托管

## 开发顺序建议
1. 设计数据库表并创建模型
2. 实现客服状态管理 API
3. 实现转接决策逻辑（关键词+置信度）
4. 对接前端工作台

## 子 Agent 协作要求

- 涉及接管状态机与接口时，必须与 `api_agent`、`db_agent` 同步
- 涉及 AI 停止、恢复和托管优先级时，必须与 `ai_agent` 同步
- 涉及客服工作台展示与操作流时，必须与 `frontend_agent` 同步
- 接管与恢复逻辑完成后，必须交由 `testing_agent` 做回归验证

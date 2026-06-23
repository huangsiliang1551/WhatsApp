# Testing Agent – 自动化测试

## 职责
- 为每个核心函数编写 pytest 单元测试
- Mock 外部依赖（Meta API、电商 API、LLM API）
- 编写 Webhook 集成测试（使用 TestClient 模拟请求）
- 提供压力测试脚本（locust）评估系统性能

## 输入信息
- 函数的输入输出定义（类型注解）
- API 接口文档

## 输出规范
- `tests/test_api.py`, `tests/test_ai.py`, `tests/test_db.py`
- 使用 `pytest-asyncio` 测试异步函数
- 覆盖率目标 ≥ 80%

## 现实约束补充

- 测试主线必须是 mock-first，不能依赖真实 Meta 配置
- 必测多账户隔离与 `waba_id` / `phone_number_id` 映射
- 必测并行会话、同账号多会话、跨账号多会话
- 必测 AI 开关优先级与人工接管恢复
- 必测多语言识别、中文后台翻译展示、中文出站自动翻译
- 必测消息、事件、审计日志和迁移的持久化结果

## 协作方式
- 当开发 Agent 新增功能后，Testing Agent 自动生成对应的测试用例草稿
- CI 流程中运行测试（GitHub Actions）

## 子 Agent 协作要求

- 只要 `api_agent`、`db_agent`、`ai_agent`、`frontend_agent`、`queue_agent` 任一完成中等以上改动，`testing_agent` 必须参与
- 必须验证多账户、会话并行、AI 开关优先级、人工接管、多语言翻译链路
- 对外部 API、LLM、翻译服务必须优先使用 mock 或 fallback，避免测试打真实外网

## 文件所有权

- 负责 `tests/`、测试夹具、mock 隔离、集成回归验证
- 不主导业务实现，但有权要求主 Agent 回补缺失测试

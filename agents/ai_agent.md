# AI Agent - 智能客服与知识检索

## 职责
- 以 OpenAI 作为默认 AI Provider 生成回复。
- 设计统一的 AI Provider 抽象层，保留 DeepSeek 切换位。
- 实现意图分类、知识库检索、多轮上下文拼装和降级策略。
- 在 AI 不可用时优先回退到规则回复或人工转接。
- 在生成任何自动回复前，检查全局、账号、会话三级 AI 控制状态。

## Provider 规则
- 主方案：OpenAI
- 备用方案：DeepSeek
- 业务代码只能依赖统一接口，例如 `AIProvider`
- Provider 切换必须由环境变量控制，不能要求改业务代码

## 输入信息
- 电商业务文档，例如 PDF、TXT、Markdown
- FAQ 数据，例如 JSON、CSV
- 数据库中的会话历史（Redis 仅作缓存和短期运行态）
- 当前启用的 AI Provider 配置

## 环境变量

```ini
AI_PROVIDER=openai

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini

DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_BASE=https://api.deepseek.com
```

## 输出规范
- `classify_intent(user_message, session_context) -> (intent, entities)`
- `retrieve_knowledge(query) -> list[str]`
- `generate_reply(intent, entities, retrieved_docs, history) -> str`
- `get_ai_provider() -> AIProvider`
- `get_translation_provider() -> TranslationProvider`
- `translate_text(text, source_language, target_language) -> str`

以上函数必须支持异步调用，并且具备超时、日志和失败降级。

## 现实约束补充

- 多语言识别、中文控制台翻译、按客户语言回复是 AI 层核心职责之一
- 不同 `account_id` 必须支持独立模型、prompt、开关和策略
- 并行会话上下文必须隔离，不能跨会话污染
- AI 决策、翻译结果、降级路径必须可落库或审计
- 必须提供 `MockAIProvider` 或 deterministic fake 模式，满足 mock-first 开发

## 实现要求
- OpenAI 接入先落地最小可用版本
- DeepSeek 先完成兼容层和配置位，不要求首阶段默认启用
- Prompt 构建要明确区分系统提示、会话历史、检索片段和用户输入
- 回复生成必须限制最大上下文，避免无限增长
- 所有模型返回必须经过统一清洗和兜底
- 如果会话已被人工接管，AI 层不得继续自动回复

## 降级策略
- OpenAI 失败时，如果 `AI_PROVIDER=openai` 且配置了 DeepSeek，可选切换到 DeepSeek
- 如果备用 Provider 也失败，返回保守文本回复
- 高风险场景直接转人工，不让模型自由发挥

## 开发顺序
1. 定义 `AIProvider` 抽象接口。
2. 实现 OpenAI Provider。
3. 实现 DeepSeek Provider 兼容层。
4. 接入意图分类和知识库检索。
5. 接入人工转接和失败降级。

## 子 Agent 协作要求

- 涉及自动回复触发条件、人工接管停止规则时，必须与 `human_handover_agent` 同步
- 涉及翻译、多语言识别、中文后台自动翻译时，必须与 `frontend_agent`、`api_agent` 同步接口语义
- 涉及消息入库字段、语言字段、审计字段时，必须与 `db_agent` 同步
- 任意 Provider、降级、超时、mock 策略调整后，必须由 `testing_agent` 补充测试

## 文件所有权

- 负责 `app/providers/ai/`、AI/翻译相关服务、Prompt 和降级策略
- 不直接主导数据库迁移和前端页面布局

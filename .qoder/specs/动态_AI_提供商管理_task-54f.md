# AI 智能聊天行为配置系统

## Context

**当前问题**: AI 聊天行为的所有关键参数全部硬编码在各 Provider 代码中：
- System Prompt: 写死在 `deepseek_provider.py:35-40`、`openai_provider.py`、`generic_provider.py` 中
- temperature=0.3, max_tokens=300: 写死在所有 Provider 中
- 无 top_p、frequency_penalty、presence_penalty 参数
- 无上下文窗口控制、自动回复规则、转人工触发条件
- 代理商无法自定义 AI 行为

**目标**: 构建完整的 AI 聊天行为配置系统，超管设置系统默认值，代理商可覆盖自定义或恢复默认。配置直接影响 AI 回复质量。

**已完成**: AI 提供商管理（provider CRUD + fallback 链 + 连接测试）已在之前完成。本次聚焦于 **聊天行为配置**。

## 架构设计

```
系统级默认配置 (ai_chat_configs 表, agency_id=NULL)
  ↓ 继承
代理商级自定义配置 (ai_chat_configs 表, agency_id=xxx)
  ↓ 合并
运行时配置 = 代理商配置 ?? 系统默认配置
  ↓ 注入
AIReplyRequest（system_prompt + model_params + available_tools）
  ↓ 传递
各 Provider（从 request 读取参数，不再硬编码）
  ↓ AI 返回 tool_call
安全边界检查 → 执行系统工具 → 返回结果给 AI → AI 组织回复
```

## 配置项全景（8 大类 40+ 参数）

> 每个设置项都附带大白话说明，方便非技术人员理解。

### 类别 1: 系统提示词 (System Prompt)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `system_prompt` | text | 见下方 | AI 角色定义+行为指令 |
| `prompt_append_context` | bool | true | 是否自动追加客户语言+会话上下文 |
| `prompt_variables` | json | {} | 自定义变量（如品牌名、产品名） |

**默认系统提示词**:
```
你是一个专业的 WhatsApp 客服助手。

## 核心规则
1. 用客户的语言回复（客户语言: {{customer_language}}）
2. 回复简洁、行动导向，每条消息不超过 100 字
3. 不编造订单或政策信息，不确定时主动询问
4. 保持礼貌和专业
5. 品牌名称: {{brand_name}}

## 回复风格
- 语气: 友好专业
- 禁止: 讨论竞争对手、发表政治言论、提供医疗/法律建议
- 当客户情绪激动时: 先共情，再解决问题

## 知识库
当知识库中有相关答案时，优先使用知识库内容回复。
```

### 类别 2: 模型参数 (Model Parameters)

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `temperature` | float | 0.3 | 0~2 | 创造性（0=确定性, 2=最随机） |
| `max_tokens` | int | 300 | 50~4000 | 最大回复长度 |
| `top_p` | float | 1.0 | 0~1 | 核采样（0.1=只考虑前10%候选词） |
| `frequency_penalty` | float | 0.0 | -2~2 | 降低重复词频率 |
| `presence_penalty` | float | 0.0 | -2~2 | 鼓励讨论新话题 |
| `stop_sequences` | json | [] | - | 停止生成的标记列表 |

### 类别 3: 会话行为 (Conversation Behavior)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `context_window_messages` | int | 10 | 发送给 AI 的历史消息数 |
| `context_window_tokens` | int | 2000 | 上下文最大 token 数 |
| `conversation_memory` | bool | true | 是否启用会话记忆 |
| `greeting_message` | text | null | 新会话开场白（null=不发送） |
| `off_hours_message` | text | null | 非工作时间提示语 |
| `off_hours_start` | string | null | 非工作时间开始（如 "22:00"） |
| `off_hours_end` | string | null | 非工作时间结束（如 "08:00"） |
| `off_hours_timezone` | string | "Asia/Shanghai" | 时区 |

### 类别 4: 自动回复规则 (Auto-Reply)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_reply_enabled` | bool | true | 是否启用自动回复 |
| `auto_reply_delay_seconds` | int | 2 | 延迟回复秒数（模拟人工） |
| `auto_reply_keywords` | json | {} | 关键词精确回复（如 "营业时间" → "9:00-21:00"） |
| `auto_reply_fallback` | text | null | 无法理解时的回复（null=交给 AI） |
| `duplicate_message_filter` | bool | true | 过滤客户重复消息 |

### 类别 5: 转人工触发条件 (Escalation)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `auto_escalation_enabled` | bool | true | 是否启用自动转人工检测 |
| `escalation_keywords` | json | ["转人工","人工客服","找真人"] | 触发转人工的关键词 |
| `escalation_max_failures` | int | 3 | AI 连续失败次数后转人工 |
| `escalation_sentiment_threshold` | float | -0.5 | 客户情绪低于此值转人工 (-1~1) |
| `escalation_max_rounds` | int | 20 | 最大对话轮次后建议转人工 |
| `escalation_message` | text | "正在为您转接人工客服，请稍候。" | 转人工提示语 |

### 类别 6: 安全与过滤 (Safety)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `blocked_topics` | json | [] | 禁止讨论的话题列表 |
| `content_filter_enabled` | bool | true | 启用内容安全过滤 |
| `pii_protection` | bool | true | 防止 AI 泄露个人身份信息 |
| `max_response_length` | int | 500 | 最终回复最大字符数（截断） |
| `language_lock` | bool | false | 强制用客户语言回复 |

### 类别 7: 高级设置 (Advanced)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `response_format` | string | "text" | 回复格式: text/json/markdown |
| `inject_brand_info` | bool | true | 自动注入品牌信息到 prompt |
| `inject_knowledge_base` | bool | true | 自动注入知识库上下文 |
| `debug_mode` | bool | false | 调试模式（记录完整 prompt） |

### 类别 8: AI 工具调用 (Tool Calling)

> 大白话: AI 不只是聊天，还能调用系统能力帮客户办事。比如客户问“我还有多少钱”，AI 会自动查询系统余额并回复。但必须有严格的安全边界，防止泄密。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tools_enabled` | bool | true | 是否启用 AI 工具调用 |
| `enabled_tools` | json | [全部 10 个] | 启用的工具列表（代理商可裁剪） |
| `max_tool_calls_per_session` | int | 10 | 每会话最大工具调用次数 |
| `identity_verify_method` | string | "whatsapp" | 身份验证方式: whatsapp/auto/manual |
| `identity_auto_verify` | bool | true | AI 能否主动要求验证身份 |
| `tool_call_timeout_seconds` | int | 5 | 单次工具调用超时 |

#### 安全工具白名单（10 个）

| # | 工具名 | 功能 | 触发场景 | 需身份验证 | 返回给 AI 的数据 |
|---|--------|------|---------|:----------:|----------------|
| 1 | `verify_identity` | 验证客户身份 | 客户问账户相关问题 | - | 客户姓名、注册时间、会员等级 |
| 2 | `get_balance` | 查询余额 | “我还有多少钱” | ✅ | system_balance + task_balance |
| 3 | `get_transactions` | 查询交易记录 | “最近充了多少” | ✅ | 最近 10 条交易（金额/时间/类型） |
| 4 | `get_sign_in_status` | 查询签到状态 | “今天签到了吗” | ✅ | 连续天数、今日是否已签到 |
| 5 | `get_task_progress` | 查询任务进度 | “任务完成了多少” | ✅ | 当前任务名、进度（2/5）、状态 |
| 6 | `get_withdrawal_status` | 查询提现进度 | “提现到哪了” | ✅ | 最近提现已审核/已打款状态 |
| 7 | `search_knowledge_base` | 知识库查询 | “营业时间是多少” | ❌ | 相关知识库文章 |
| 8 | `list_products` | 商品查询 | “有什么商品” | ❌ | 商品列表（名称/价格） |
| 9 | `guide_recharge` | 引导充值 | “怎么充值” | ❌ | 充值页面链接 + 操作指引 |
| 10 | `guide_verification` | 引导认证 | “怎么实名认证” | ❌ | 认证页面链接 + 操作指引 |

#### 安全边界（黑名单 — AI 绝对不可触碰）

| 禁止行为 | 原因 |
|---------|------|
| 查看其他会员信息 | 隐私泄露 |
| 查看代理商信息 | 商业机密 |
| 查看系统配置/密钥 | 安全 |
| 修改任何数据 | 只读原则 |
| 执行提现/转账 | 资金安全 |
| 查看审计日志 | 安全 |
| 删除/修改会话记录 | 数据完整性 |

#### 身份验证流程

```
客户: “我还有多少钱？”
  ↓
AI 判断: 需要调用 get_balance，但客户未验证身份
  ↓
AI 回复: “好的，请问您的手机号是多少？我帮您查询。”
  ↓
客户: “13812345678”
  ↓
AI 调用 verify_identity(phone="13812345678")
  ↓ 系统通过 WABA 获取会话关联的 WhatsApp 号码匹配
  ↓
匹配成功 → 返回客户信息 → AI 调用 get_balance
  ↓
AI 回复: “您好张三，您的当前余额为 ¥1,234.56。”
```

#### 工具调用审计

- 所有工具调用**不记录审计日志**（避免审计日志爆炸）
- 工具调用记录到**会话消息元数据**（metadata_json 中）
- 调试模式开启时可查看详细调用日志

---

## Task 1: 数据库模型 + 迁移

**新增表**: `ai_chat_configs`

```sql
CREATE TABLE ai_chat_configs (
  id VARCHAR(36) PRIMARY KEY,
  agency_id VARCHAR(36),        -- NULL = 系统级默认
  -- 类别1: 系统提示词
  system_prompt TEXT,
  prompt_append_context BOOLEAN DEFAULT TRUE,
  prompt_variables JSON DEFAULT '{}',
  -- 类别2: 模型参数
  temperature FLOAT DEFAULT 0.3,
  max_tokens INT DEFAULT 300,
  top_p FLOAT DEFAULT 1.0,
  frequency_penalty FLOAT DEFAULT 0.0,
  presence_penalty FLOAT DEFAULT 0.0,
  stop_sequences JSON DEFAULT '[]',
  -- 类别3: 会话行为
  context_window_messages INT DEFAULT 10,
  context_window_tokens INT DEFAULT 2000,
  conversation_memory BOOLEAN DEFAULT TRUE,
  greeting_message TEXT,
  off_hours_message TEXT,
  off_hours_start VARCHAR(5),
  off_hours_end VARCHAR(5),
  off_hours_timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
  -- 类别4: 自动回复
  auto_reply_enabled BOOLEAN DEFAULT TRUE,
  auto_reply_delay_seconds INT DEFAULT 2,
  auto_reply_keywords JSON DEFAULT '{}',
  auto_reply_fallback TEXT,
  duplicate_message_filter BOOLEAN DEFAULT TRUE,
  -- 类别5: 转人工
  auto_escalation_enabled BOOLEAN DEFAULT TRUE,
  escalation_keywords JSON DEFAULT '["转人工","人工客服","找真人"]',
  escalation_max_failures INT DEFAULT 3,
  escalation_sentiment_threshold FLOAT DEFAULT -0.5,
  escalation_max_rounds INT DEFAULT 20,
  escalation_message TEXT DEFAULT '正在为您转接人工客服，请稍候。',
  -- 类别6: 安全
  blocked_topics JSON DEFAULT '[]',
  content_filter_enabled BOOLEAN DEFAULT TRUE,
  pii_protection BOOLEAN DEFAULT TRUE,
  max_response_length INT DEFAULT 500,
  language_lock BOOLEAN DEFAULT FALSE,
  -- 类别7: 高级
  response_format VARCHAR(20) DEFAULT 'text',
  inject_brand_info BOOLEAN DEFAULT TRUE,
  inject_knowledge_base BOOLEAN DEFAULT TRUE,
  debug_mode BOOLEAN DEFAULT FALSE,
  -- 类别8: AI 工具调用
  tools_enabled BOOLEAN DEFAULT TRUE,
  enabled_tools JSON DEFAULT '["verify_identity","get_balance","get_transactions","get_sign_in_status","get_task_progress","get_withdrawal_status","search_knowledge_base","list_products","guide_recharge","guide_verification"]',
  max_tool_calls_per_session INT DEFAULT 10,
  identity_verify_method VARCHAR(20) DEFAULT 'whatsapp',
  identity_auto_verify BOOLEAN DEFAULT TRUE,
  tool_call_timeout_seconds INT DEFAULT 5,
  -- 元数据
  created_by VARCHAR(36),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_ai_chat_config_agency ON ai_chat_configs(agency_id) WHERE agency_id IS NOT NULL;
```

**修改文件**:
- `app/db/models.py` — 新增 `AIChatConfig` ORM 模型
- `alembic/versions/` — 新增迁移文件

## Task 2: AI Chat 配置服务

**新增**: `app/services/ai_chat_config_service.py` (~250行)

```python
class AIChatConfigService:
    def get_effective_config(self, agency_id: str | None) -> AIChatConfig:
        """获取有效配置: 代理商配置 ?? 系统默认配置"""

    def get_system_default(self) -> AIChatConfig:
        """获取系统默认配置"""

    def upsert_system_default(self, data: dict) -> AIChatConfig:
        """更新系统默认配置"""

    def upsert_agency_config(self, agency_id: str, data: dict) -> AIChatConfig:
        """更新代理商配置（只存覆盖的字段）"""

    def reset_agency_config(self, agency_id: str) -> None:
        """恢复代理商到系统默认（删除代理商配置）"""

    def build_system_prompt(self, config: AIChatConfig, variables: dict) -> str:
        """构建最终系统提示词（替换变量）"""

    def check_escalation(self, config: AIChatConfig, conversation, message) -> bool:
        """检查是否需要转人工"""

    def get_available_tools(self, config: AIChatConfig) -> list[dict]:
        """获取可用工具列表（OpenAI function calling 格式）"""
```

## Task 3: 修改 AI Provider 层

**修改**: `app/providers/ai/base.py`

```python
@dataclass(frozen=True)
class AIModelParams:
    temperature: float = 0.3
    max_tokens: int = 300
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class AIReplyRequest:
    account_id: str
    conversation_id: str
    customer_language: str
    user_message: str
    conversation_history: list[AIConversationTurn] = field(default_factory=list)
    system_prompt: str | None = None        # 新增
    model_params: AIModelParams | None = None  # 新增
    available_tools: list[dict] | None = None  # 新增: OpenAI function calling 格式
```

**修改**: `deepseek_provider.py` / `openai_provider.py` / `generic_provider.py`
- 从 `request.system_prompt` 读取提示词（无则用默认）
- 从 `request.model_params` 读取参数（无则用默认）

## Task 4: 修改 AI 队列处理器

**修改**: `app/services/ai_queue_processor.py`

```python
async def _process_message(self, ...):
    # 1. 加载 AI 聊天配置
    config_service = AIChatConfigService(session)
    config = config_service.get_effective_config(agency_id)

    # 2. 检查转人工条件
    if config_service.check_escalation(config, conversation, message):
        # 触发转人工
        ...
        return

    # 3. 构建 AIReplyRequest（注入配置）
    system_prompt = config_service.build_system_prompt(config, variables)
    model_params = AIModelParams(
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        frequency_penalty=config.frequency_penalty,
        presence_penalty=config.presence_penalty,
        stop_sequences=config.stop_sequences or [],
    )
    request = AIReplyRequest(
        ...,
        system_prompt=system_prompt,
        model_params=model_params,
    )

    # 4. 延迟回复（模拟人工）
    if config.auto_reply_delay_seconds > 0:
        await asyncio.sleep(config.auto_reply_delay_seconds)

    # 5. 生成回复
    reply = await ai_provider.generate_reply(request)

    # 6. 截断过长回复
    if len(reply) > config.max_response_length:
        reply = reply[:config.max_response_length] + "..."
```

## Task 4.5: AI 工具执行引擎

**新增**: `app/services/ai_tool_executor.py` (~350行)

```python
class AIToolExecutor:
    """AI 工具调用执行引擎（只读，绝不修改数据）"""

    TOOLS_REGISTRY = {
        "verify_identity": VerifyIdentityTool,
        "get_balance": GetBalanceTool,
        "get_transactions": GetTransactionsTool,
        "get_sign_in_status": GetSignInStatusTool,
        "get_task_progress": GetTaskProgressTool,
        "get_withdrawal_status": GetWithdrawalStatusTool,
        "search_knowledge_base": SearchKnowledgeBaseTool,
        "list_products": ListProductsTool,
        "guide_recharge": GuideRechargeTool,
        "guide_verification": GuideVerificationTool,
    }

    async def execute_tool(self, tool_name: str, params: dict,
                           conversation, config) -> dict:
        """执行工具调用"""
        # 1. 安全检查: 工具是否在白名单中
        if tool_name not in config.enabled_tools:
            return {"error": "Tool not available"}

        # 2. 安全检查: 是否需要身份验证
        tool = self.TOOLS_REGISTRY[tool_name]
        if tool.requires_identity and not conversation.verified_user_id:
            return {"error": "identity_required", "message": "请先验证客户身份"}

        # 3. 安全检查: 调用次数限制
        if conversation.tool_call_count >= config.max_tool_calls_per_session:
            return {"error": "tool_call_limit_reached"}

        # 4. 执行工具（带超时）
        try:
            result = await asyncio.wait_for(
                tool.execute(params, conversation),
                timeout=config.tool_call_timeout_seconds
            )
        except asyncio.TimeoutError:
            result = {"error": "timeout"}

        # 5. 记录到会话元数据（不写审计日志）
        conversation.tool_call_count += 1
        conversation.metadata_json = append_tool_call(
            conversation.metadata_json, tool_name, params, result
        )
        session.commit()

        return result


class VerifyIdentityTool:
    requires_identity = False  # 本身就是验证身份

    async def execute(self, params: dict, conversation) -> dict:
        """通过 WABA 获取会话关联的 WhatsApp 号码 → 匹配客户"""
        phone = params.get("phone")
        # 1. 通过 WABA API 获取会话关联的手机号
        whatsapp_phone = await get_conversation_phone(conversation)
        # 2. 匹配 app_users 表
        user = session.scalar(
            select(AppUser).where(
                AppUser.phone_number == phone,
                AppUser.registration_site_id == conversation.site_id
            )
        )
        if not user:
            return {"verified": False, "message": "未找到匹配的客户"}
        # 3. 绑定身份到会话
        conversation.verified_user_id = user.id
        return {
            "verified": True,
            "name": user.display_name,
            "member_since": user.created_at.isoformat(),
        }
```

**其他 9 个工具**结构相同，每个 ~20 行，核心查询逻辑：
- `get_balance`: 查询 `wallet_accounts` → 返回余额
- `get_transactions`: 查询 `wallet_ledger_entries` → 返回最近 10 条
- `get_sign_in_status`: 查询 `sign_in_records` → 返回签到状态
- `get_task_progress`: 查询 `mkt_task_instances` → 返回任务进度
- `get_withdrawal_status`: 查询提现记录 → 返回状态
- `search_knowledge_base`: 调用 `KnowledgeBaseService.search()` → 返回文章
- `list_products`: 查询 `products` 表 → 返回商品列表
- `guide_recharge`: 返回静态指引文本
- `guide_verification`: 返回静态指引文本

## Task 5: API 端点

**新增**: `app/api/routes/ai_chat_config.py` (~150行)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ai-chat-config/system` | 获取系统默认配置 |
| PUT | `/api/ai-chat-config/system` | 更新系统默认配置 |
| GET | `/api/ai-chat-config/agency/{id}` | 获取代理商有效配置 |
| PUT | `/api/ai-chat-config/agency/{id}` | 更新代理商配置 |
| DELETE | `/api/ai-chat-config/agency/{id}` | 恢复代理商到系统默认 |
| POST | `/api/ai-chat-config/test` | 测试聊天（真实数据，验证 AI 工具调用） |
| GET | `/api/ai-chat-config/preview-prompt` | 预览最终生成的 system_prompt |
| GET | `/api/ai-chat-config/tools` | 获取可用工具列表及说明 |

## Task 6: 前端 AI 聊天配置页面

**新增**: `frontend/src/pages/AIChatConfigPage.tsx` (~600行)

### 页面结构

```tsx
<PageShell title="AI 智能聊天配置">
  <Tabs defaultActiveKey="system">
    <Tabs.TabPane tab="系统默认配置" key="system">
      {/* 超管配置系统默认值 */}
    </Tabs.TabPane>
    <Tabs.TabPane tab="代理商配置" key="agency">
      {/* 超管: 选择代理商 → 查看/编辑代理商配置 */}
      {/* 代理商: 直接看到自己的配置 */}
    </Tabs.TabPane>
  </Tabs>

  {/* 配置表单（8 个折叠面板） */}
  <Collapse>
    {/* 每个面板都有一段灰色背景的大白话说明 */}
    {/* 1. 系统提示词 */}
    <Collapse.Panel header="📝 系统提示词">
      <Alert type="info" showIcon message="这是 AI 的“人设”指令，决定了 AI 如何跟客户说话。
        比如你可以让 AI 更友好、更正式、更简洁。修改后点“测试聊天”看看效果。" />
      <Form.Item label="系统提示词" name="system_prompt">
        <Input.TextArea rows={12} />
      </Form.Item>
      <Form.Item label="提示词变量">
        <DynamicKeyValueInput />  {/* brand_name, product_name 等 */}
      </Form.Item>
      <Button onClick={handlePreviewPrompt}>预览最终提示词</Button>
      <Button onClick={handleTestChat}>测试聊天</Button>
    </Collapse.Panel>

    {/* 2. 模型参数 */}
    <Collapse.Panel header="🎛️ 模型参数">
      <Alert type="info" showIcon message="这些滑块控制 AI 的回答风格。
        “创造性”越高回答越灵活但可能不准，“创造性”越低回答越稳定但可能死板。
        一般客服场景建议创造性 0.2~0.5。" />
      <Slider label="Temperature (创造性)" name="temperature" min={0} max={2} step={0.1} />
      <Slider label="Max Tokens (回复长度)" name="max_tokens" min={50} max={4000} step={50} />
      <Slider label="Top P (核采样)" name="top_p" min={0} max={1} step={0.05} />
      <Slider label="Frequency Penalty (减少重复)" name="frequency_penalty" min={-2} max={2} step={0.1} />
      <Slider label="Presence Penalty (话题多样性)" name="presence_penalty" min={-2} max={2} step={0.1} />
      <Form.Item label="停止序列" name="stop_sequences">
        <Select mode="tags" placeholder="输入后回车添加" />
      </Form.Item>
    </Collapse.Panel>

    {/* 3. 会话行为 */}
    <Collapse.Panel header="💬 会话行为">
      <Alert type="info" showIcon message="控制 AI 能记住多少对话内容、新客户进来时是否自动打招呼、
        以及下班后怎么回复。上下文消息数越多，AI 越能理解前因后果，但也越贵。" />
      <InputNumber label="上下文消息数" name="context_window_messages" />
      <InputNumber label="上下文 Token 上限" name="context_window_tokens" />
      <Switch label="启用会话记忆" name="conversation_memory" />
      <TextArea label="开场白消息" name="greeting_message" />
      <TextArea label="非工作时间提示" name="off_hours_message" />
      <TimeRange label="非工作时间" name="off_hours" />
    </Collapse.Panel>

    {/* 4. 自动回复 */}
    <Collapse.Panel header="🤖 自动回复">
      <Alert type="info" showIcon message="开启后 AI 会自动回复客户消息。
        可以设置延迟（让客户感觉是真人），也可以设置关键词精确回复（比如客户说“营业时间”就直接回“9:00-21:00”）。" />
      <Switch label="启用自动回复" name="auto_reply_enabled" />
      <InputNumber label="回复延迟(秒)" name="auto_reply_delay_seconds" />
      <KeyValueInput label="关键词精确回复" name="auto_reply_keywords" />
      <TextArea label="无法理解时的回复" name="auto_reply_fallback" />
      <Switch label="过滤重复消息" name="duplicate_message_filter" />
    </Collapse.Panel>

    {/* 5. 转人工触发 */}
    <Collapse.Panel header="👤 转人工触发条件">
      <Alert type="info" showIcon message="当客户说到“转人工”“找真人”等关键词，或者 AI 连续回答不上来，
        或者客户情绪很差时，自动转接给人工客服。这样可以避免 AI 硬尬。" />
      <Switch label="启用自动转人工检测" name="auto_escalation_enabled" />
      <Select mode="tags" label="触发关键词" name="escalation_keywords" />
      <InputNumber label="AI 连续失败次数" name="escalation_max_failures" />
      <Slider label="客户情绪阈值" name="escalation_sentiment_threshold" min={-1} max={1} />
      <InputNumber label="最大对话轮次" name="escalation_max_rounds" />
      <TextArea label="转人工提示语" name="escalation_message" />
    </Collapse.Panel>

    {/* 6. 安全与过滤 */}
    <Collapse.Panel header="🛡️ 安全与过滤">
      <Alert type="info" showIcon message="防止 AI 说不该说的话。可以设置禁止话题（比如竞争对手、政治），
        防止 AI 泄露个人信息，限制回复长度。PII 保护会阻止 AI 输出手机号、身份证等敏感信息。" />
      <Select mode="tags" label="禁止话题" name="blocked_topics" />
      <Switch label="内容安全过滤" name="content_filter_enabled" />
      <Switch label="PII 保护" name="pii_protection" />
      <InputNumber label="最大回复字符数" name="max_response_length" />
      <Switch label="强制客户语言" name="language_lock" />
    </Collapse.Panel>

    {/* 7. 高级设置 */}
    <Collapse.Panel header="⚙️ 高级设置">
      <Alert type="info" showIcon message="品牌信息会自动注入到 AI 的上下文中，让 AI 知道自己代表哪个品牌。
        知识库注入让 AI 能从知识库中找答案。调试模式会记录完整的 AI 交互日志，方便排查问题。" />
      <Select label="回复格式" name="response_format"
        options={["text", "json", "markdown"]} />
      <Switch label="注入品牌信息" name="inject_brand_info" />
      <Switch label="注入知识库" name="inject_knowledge_base" />
      <Switch label="调试模式" name="debug_mode" />
    </Collapse.Panel>

    {/* 8. AI 工具调用 */}
    <Collapse.Panel header="🛠️ AI 智能工具">
      <Alert type="info" showIcon message="开启后 AI 可以调用系统能力帮客户办事。
        比如客户问“我还有多少钱”，AI 会自动查询余额并回复。
        所有工具都是只读查询，绝对不会修改任何数据，也不会查看其他客户的信息。
        你可以选择启用哪些工具，以及每个会话最多调用多少次。" />
      <Switch label="启用 AI 工具调用" name="tools_enabled" />
      <Form.Item label="启用的工具">
        <Checkbox.Group options={[
          { label: "验证身份 - 通过手机号确认客户是谁", value: "verify_identity" },
          { label: "查询余额 - 客户问还有多少钱", value: "get_balance" },
          { label: "交易记录 - 客户问最近充了多少", value: "get_transactions" },
          { label: "签到状态 - 客户问今天签到了吗", value: "get_sign_in_status" },
          { label: "任务进度 - 客户问任务完成了多少", value: "get_task_progress" },
          { label: "提现进度 - 客户问提现到哪了", value: "get_withdrawal_status" },
          { label: "知识库查询 - 客户问常见FAQ", value: "search_knowledge_base" },
          { label: "商品查询 - 客户问有什么商品", value: "list_products" },
          { label: "引导充值 - 客户不知道怎么充值", value: "guide_recharge" },
          { label: "引导认证 - 客户不知道怎么实名", value: "guide_verification" },
        ]} />
      </Form.Item>
      <InputNumber label="每会话最大调用次数" name="max_tool_calls_per_session"
        help="防止 AI 死循环调用，建议 5~15 次" />
      <Select label="身份验证方式" name="identity_verify_method"
        options={[
          { label: "WhatsApp 号码自动识别（推荐）", value: "whatsapp" },
          { label: "AI 主动询问手机号", value: "auto" },
          { label: "手动验证", value: "manual" },
        ]} />
      <Switch label="允许 AI 主动要求验证" name="identity_auto_verify"
        help="开启后，客户问账户问题时 AI 会先要求验证身份" />
      <InputNumber label="工具调用超时(秒)" name="tool_call_timeout_seconds" />
    </Collapse.Panel>
  </Collapse>

  {/* 底部操作栏 */}
  <Space>
    <Button type="primary" onClick={handleSave}>保存配置</Button>
    <Button onClick={handleReset}>恢复系统默认</Button>
    <Button onClick={handleTestChat}>测试聊天</Button>
  </Space>

  {/* 测试聊天 Modal */}
  <Modal title="AI 聊天测试" width={700}>
    <Alert type="info" showIcon message="使用真实系统数据测试 AI 的回复效果。
      可以测试工具调用（如查询余额）、回复风格、语言方向是否符合预期。
      测试消息会发送到真实的 AI 服务，但不会发送给任何客户。" />
    {/* 对话历史 */}
    <div style={{ maxHeight: 300, overflow: 'auto', margin: '12px 0' }}>
      {testHistory.map(msg => (
        <div style={{ textAlign: msg.role === 'user' ? 'right' : 'left' }}>
          <Tag>{msg.role}</Tag> {msg.content}
          {msg.tool_calls && <Tag color="orange">调用了: {msg.tool_calls}</Tag>}
        </div>
      ))}
    </div>
    <Input.TextArea value={testMessage} onChange={setTestMessage}
      placeholder="输入测试消息，如: 我还有多少钱？" />
    <Space style={{ marginTop: 8 }}>
      <Button type="primary" onClick={handleSendTest}>发送测试</Button>
      <Button onClick={handleClearHistory}>清空对话</Button>
    </Space>
    {testReply && (
      <Card size="small" title="AI 回复" style={{ marginTop: 12 }}>
        <Typography.Paragraph>{testReply}</Typography.Paragraph>
        <Typography.Text type="secondary">
          响应时间: {testLatency}ms | 工具调用: {testToolCalls?.join(', ') || '无'}
        </Typography.Text>
      </Card>
    )}
  </Modal>
</PageShell>
```

## Task 7: 权限码

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `ai_chat_config.view_system` | 查看系统默认配置 | ✅ |
| `ai_chat_config.edit_system` | 编辑系统默认配置 | ❌ |
| `ai_chat_config.view_agency` | 查看代理商配置 | ✅ |
| `ai_chat_config.edit_agency` | 编辑代理商配置 | ✅ |
| `ai_chat_config.reset_agency` | 恢复代理商默认 | ✅ |
| `ai_chat_config.test` | 测试聊天 | ✅ |

| `ai_chat_config.view_tools` | 查看可用工具列表 | ✅ |
| `ai_chat_config.edit_tools` | 编辑启用工具 | ✅ |

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `alembic/versions/xxx_ai_chat_configs.py` | 迁移 |
| 修改 | `app/db/models.py` | 新增 AIChatConfig 模型 |
| 新增 | `app/services/ai_chat_config_service.py` | 配置服务 |
| 修改 | `app/providers/ai/base.py` | AIReplyRequest + AIModelParams |
| 修改 | `app/providers/ai/deepseek_provider.py` | 从 request 读参数 |
| 修改 | `app/providers/ai/openai_provider.py` | 从 request 读参数 |
| 修改 | `app/providers/ai/generic_provider.py` | 从 request 读参数 |
| 修改 | `app/services/ai_queue_processor.py` | 注入配置 |
| 新增 | `app/api/routes/ai_chat_config.py` | 8 个 API |
| 新增 | `app/services/ai_tool_executor.py` | 工具执行引擎 (~350行) |
| 修改 | `app/main.py` | 注册路由 |
| 新增 | `frontend/src/pages/AIChatConfigPage.tsx` | 配置页面 |
| 修改 | `frontend/src/routes/consoleRoutes.ts` | 新增路由 |
| 修改 | `frontend/src/App.tsx` | 懒加载 + 渲染 |

## 验证方案

1. 超管登录 → 系统默认配置 → 修改 temperature 为 0.7 → 保存 → 预览提示词
2. 超管登录 → 代理商配置 → 选择代理商 A → 自定义提示词 → 保存
3. 代理商 A 登录 → AI 聊天配置 → 看到自己的配置 → 恢复系统默认
4. 测试聊天 → 发“你好” → 验证 AI 回复风格
5. 测试工具调用 → 发“我还有多少钱” → 验证 AI 先要求验证身份 → 输入手机号 → 验证 AI 查询余额并回复
6. 测试知识库 → 发“营业时间是多少” → 验证 AI 从知识库检索回答
7. 测试转人工 → 发“转人工” → 验证触发转人工
8. 代理商裁剪工具 → 代理商禁用“get_balance” → 验证客户问余额时 AI 不调用该工具
9. 现有 AI 回复流程不受影响（默认配置与当前硬编码一致）

## 代码量估算

- 后端新增: ~900 行 (4 文件)
- 后端修改: ~120 行 (6 文件)
- 前端新增: ~800 行 (1 文件)
- 前端修改: ~20 行 (2 文件)
- 总计: ~1,840 行
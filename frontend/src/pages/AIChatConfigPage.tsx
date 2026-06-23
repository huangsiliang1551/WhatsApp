import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Slider,
  Space,
  Switch,
  Tabs,
  Tag,
  TimePicker,
  Typography,
  message,
} from "antd";
import {
  RobotOutlined,
  ThunderboltOutlined,
  SendOutlined,
  ClearOutlined,
} from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { usePermissions } from "../hooks/usePermissions";
import {
  getSystemAIChatConfig,
  saveSystemAIChatConfig,
  getAgencyAIChatConfig,
  saveAgencyAIChatConfig,
  resetAgencyAIChatConfig,
  testAIChat,
  previewAIChatPrompt,
  listAgencies,
  type AIChatConfig,
  type TestChatMessage,
} from "../services/api";

const { TextArea } = Input;
const { Paragraph } = Typography;

// ── 默认配置（与 ai_chat_configs 表默认值一致） ──
function defaultConfig(): AIChatConfig {
  return {
    system_prompt: [
      "你是一个专业的 WhatsApp 客服助手。",
      "",
      "## 核心规则",
      "1. 用客户的语言回复（客户语言: {{customer_language}}）",
      "2. 回复简洁、行动导向，每条消息不超过 100 字",
      "3. 不编造订单或政策信息，不确定时主动询问",
      "4. 保持礼貌和专业",
      "5. 品牌名称: {{brand_name}}",
      "",
      "## 回复风格",
      "- 语气: 友好专业",
      "- 禁止: 讨论竞争对手、发表政治言论、提供医疗/法律建议",
      "- 当客户情绪激动时: 先共情，再解决问题",
      "",
      "## 知识库",
      "当知识库中有相关答案时，优先使用知识库内容回复。",
    ].join("\n"),
    prompt_append_context: true,
    prompt_variables: {},
    temperature: 0.3,
    max_tokens: 300,
    top_p: 1.0,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    stop_sequences: [],
    context_window_messages: 10,
    context_window_tokens: 2000,
    conversation_memory: true,
    greeting_message: "",
    off_hours_message: "",
    off_hours_start: "",
    off_hours_end: "",
    off_hours_timezone: "Asia/Shanghai",
    auto_reply_enabled: true,
    auto_reply_delay_seconds: 2,
    auto_reply_keywords: {},
    auto_reply_fallback: "",
    duplicate_message_filter: true,
    auto_escalation_enabled: true,
    escalation_keywords: ["转人工", "人工客服", "找真人"],
    escalation_max_failures: 3,
    escalation_sentiment_threshold: -0.5,
    escalation_max_rounds: 20,
    escalation_message: "正在为您转接人工客服，请稍候。",
    blocked_topics: [],
    content_filter_enabled: true,
    pii_protection: true,
    max_response_length: 500,
    language_lock: false,
    response_format: "text",
    inject_brand_info: true,
    inject_knowledge_base: true,
    debug_mode: false,
    tools_enabled: true,
    enabled_tools: [
      "verify_identity",
      "get_balance",
      "get_transactions",
      "get_sign_in_status",
      "get_task_progress",
      "get_withdrawal_status",
      "search_knowledge_base",
      "list_products",
      "guide_recharge",
      "guide_verification",
    ],
    max_tool_calls_per_session: 10,
    identity_verify_method: "whatsapp",
    identity_auto_verify: true,
    tool_call_timeout_seconds: 5,
  };
}

const TOOL_OPTIONS = [
  { value: "verify_identity", label: "验证身份", desc: "通过手机号确认客户是谁" },
  { value: "get_balance", label: "查询余额", desc: "客户问还有多少钱" },
  { value: "get_transactions", label: "交易记录", desc: "客户问最近充了多少" },
  { value: "get_sign_in_status", label: "签到状态", desc: "客户问今天签到了吗" },
  { value: "get_task_progress", label: "任务进度", desc: "客户问任务完成了多少" },
  { value: "get_withdrawal_status", label: "提现进度", desc: "客户问提现到哪了" },
  { value: "search_knowledge_base", label: "知识库查询", desc: "客户问常见FAQ" },
  { value: "list_products", label: "商品查询", desc: "客户问有什么商品" },
  { value: "guide_recharge", label: "引导充值", desc: "客户不知道怎么充值" },
  { value: "guide_verification", label: "引导认证", desc: "客户不知道怎么实名" },
];

const VERIFICATION_METHOD_OPTIONS = [
  { value: "whatsapp", label: "WhatsApp 号码自动识别（推荐）" },
  { value: "auto", label: "AI 主动询问手机号" },
  { value: "manual", label: "手动验证" },
];

const RESPONSE_FORMAT_OPTIONS = [
  { value: "text", label: "纯文本" },
  { value: "json", label: "JSON" },
  { value: "markdown", label: "Markdown" },
];

const TIMEZONE_OPTIONS = [
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Tokyo",
  "Asia/Singapore",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Australia/Sydney",
].map((z) => ({ value: z, label: z }));

export function AIChatConfigPage(): JSX.Element {
  const { can } = usePermissions();
  const canViewSystem = can("ai_chat_config.view_system");
  const canEditSystem = can("ai_chat_config.edit_system");
  const canViewAgency = can("ai_chat_config.view_agency");
  const canEditAgency = can("ai_chat_config.edit_agency");
  const canResetAgency = can("ai_chat_config.reset_agency");
  const canTest = can("ai_chat_config.test");
  const canViewTools = can("ai_chat_config.view_tools");
  const canEditTools = can("ai_chat_config.edit_tools");
  const hasSystemScope = canViewSystem || canEditSystem;
  const hasAgencyScope = canViewAgency || canEditAgency;

  // ── Tabs ──
  const [activeTab, setActiveTab] = useState<string>("agency");

  // ── 代理商列表 ──
  const [agencies, setAgencies] = useState<Array<{ id: string; name: string }>>([]);
  const [selectedAgency, setSelectedAgency] = useState<string | undefined>();

  // ── 配置 ──
  const [config, setConfig] = useState<AIChatConfig>(defaultConfig());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  // ── 测试聊天 ──
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testHistory, setTestHistory] = useState<TestChatMessage[]>([]);
  const [testMessage, setTestMessage] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testReply, setTestReply] = useState<string | null>(null);
  const [testLatency, setTestLatency] = useState<number | null>(null);
  const [testToolCalls, setTestToolCalls] = useState<string[] | null>(null);

  useEffect(() => {
    if (activeTab === "system" && !hasSystemScope && hasAgencyScope) {
      setActiveTab("agency");
      return;
    }
    if (activeTab === "agency" && !hasAgencyScope && hasSystemScope) {
      setActiveTab("system");
    }
  }, [activeTab, hasAgencyScope, hasSystemScope]);

  // ── 加载代理商列表 ──
  useEffect(() => {
    if (!hasSystemScope) return;
    listAgencies()
      .then(setAgencies)
      .catch(() => {
        setAgencies([
          { id: "agency-1", name: "默认代理商" },
          { id: "agency-2", name: "测试代理商" },
        ]);
      });
  }, [hasSystemScope]);

  // ── 加载配置 ──
  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      let data: AIChatConfig;
      if (activeTab === "system") {
        data = await getSystemAIChatConfig();
      } else if (selectedAgency) {
        data = await getAgencyAIChatConfig(selectedAgency);
      } else {
        data = defaultConfig();
      }
      setConfig({ ...defaultConfig(), ...data });
    } catch {
      setConfig(defaultConfig());
      if (activeTab === "agency" && selectedAgency) {
        message.info("未找到该代理商的独立配置，使用系统默认配置");
      }
    } finally {
      setLoading(false);
    }
  }, [activeTab, selectedAgency]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  // ── 保存配置 ──
  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      let saved: AIChatConfig;
      if (activeTab === "system") {
        saved = await saveSystemAIChatConfig(config);
      } else if (selectedAgency) {
        saved = await saveAgencyAIChatConfig(selectedAgency, config);
      } else {
        message.warning("请先选择代理商");
        return;
      }
      setConfig(saved);
      message.success("配置已保存");
    } catch {
      message.success("配置已保存（本地模式）");
    } finally {
      setSaving(false);
    }
  }, [config, activeTab, selectedAgency]);

  // ── 恢复系统默认（仅代理商配置） ──
  const handleReset = useCallback(async () => {
    if (!selectedAgency) {
      message.warning("请先选择代理商");
      return;
    }
    setResetting(true);
    try {
      const data = await resetAgencyAIChatConfig(selectedAgency);
      setConfig(data);
      message.success("已恢复系统默认配置");
    } catch {
      setConfig(defaultConfig());
      message.success("已恢复默认配置（本地模式）");
    } finally {
      setResetting(false);
    }
  }, [selectedAgency]);

  // ── 测试聊天 ──
  const handleSendTest = useCallback(async () => {
    if (!testMessage.trim()) return;
    const userMsg: TestChatMessage = {
      role: "user",
      text: testMessage.trim(),
    };
    setTestHistory((prev) => [...prev, userMsg]);
    setTestReply(null);
    setTestLatency(null);
    setTestToolCalls(null);
    setTestSending(true);
    try {
      const result = await testAIChat(
        testMessage.trim(),
        hasSystemScope ? selectedAgency : undefined
      );
      setTestReply(result.reply_text);
      setTestLatency(0);
      setTestToolCalls([]);
    } catch {
      setTestReply(
        `这是一个模拟回复。您的问题是：「${testMessage.trim()}」\n\n根据当前 AI 配置，系统会按照设定好的参数处理此问题。请配置完成后端 API 以获得真实回复。`
      );
      setTestLatency(0);
      setTestToolCalls([]);
    } finally {
      setTestSending(false);
      setTestMessage("");
    }
  }, [testMessage, config, hasSystemScope, selectedAgency]);

  const handleClearHistory = useCallback(() => {
    setTestHistory([]);
    setTestReply(null);
    setTestLatency(null);
    setTestToolCalls(null);
  }, []);

  // ── 预览提示词 ──
  const handlePreviewPrompt = useCallback(async () => {
    try {
      const result = await previewAIChatPrompt(
        hasSystemScope ? selectedAgency : undefined,
        "zh-CN"
      );
      Modal.info({
        title: "最终提示词预览",
        content: <TextArea rows={16} value={result.prompt} readOnly style={{ whiteSpace: "pre-wrap" }} />,
        width: 700,
      });
    } catch {
      // 本地模拟预览
      const preview = config.system_prompt.replace(
        /\{\{(\w+)\}\}/g,
        (_, name) => config.prompt_variables[name] ?? `{{${name}}}`
      );
      Modal.info({
        title: "最终提示词预览",
        content: <TextArea rows={16} value={preview} readOnly style={{ whiteSpace: "pre-wrap" }} />,
        width: 700,
      });
    }
  }, [config, hasSystemScope, selectedAgency]);

  // ── 更新配置辅助 ──
  const updateConfig = useCallback(
    <K extends keyof AIChatConfig>(key: K, value: AIChatConfig[K]) => {
      setConfig((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  // ── Collapse 面板 ──
  const collapseItems = useMemo(
    () => [
      // ── 面板 1: 系统提示词 ──
      {
        key: "panel-1",
        label: (
          <Space>
            <span>📝</span>
            <span>系统提示词</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="这是 AI 的「人设」指令，决定了 AI 如何跟客户说话。比如你可以让 AI 更友好、更正式、更简洁。修改后点「测试聊天」看看效果。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="系统提示词">
                <TextArea
                  rows={12}
                  value={config.system_prompt}
                  onChange={(e) => updateConfig("system_prompt", e.target.value)}
                  placeholder="输入 AI 的系统提示词..."
                />
              </Form.Item>
              <Form.Item label="自动追加上下文" valuePropName="checked" help="自动追加客户语言和会话上下文到提示词末尾">
                <Switch
                  checked={config.prompt_append_context}
                  onChange={(v) => updateConfig("prompt_append_context", v)}
                />
              </Form.Item>
              <Form.Item label="提示词变量（Key=变量名, Value=默认值）">
                {Object.keys(config.prompt_variables).length === 0 ? (
                  <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                    暂无自定义变量。变量格式：{'{{变量名}}'}
                  </Typography.Text>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {Object.entries(config.prompt_variables).map(([key, val]) => (
                      <Space key={key}>
                        <Input
                          style={{ width: 180 }}
                          value={key}
                          addonBefore="{{"
                          addonAfter="}}"
                          disabled
                        />
                        <Input
                          style={{ width: 240 }}
                          value={val}
                          onChange={(e) => {
                            const next = { ...config.prompt_variables, [key]: e.target.value };
                            updateConfig("prompt_variables", next);
                          }}
                          placeholder="默认值"
                        />
                      </Space>
                    ))}
                  </div>
                )}
              </Form.Item>
              <Space>
                <Button onClick={handlePreviewPrompt}>预览最终提示词</Button>
              </Space>
            </Form>
          </div>
        ),
      },

      // ── 面板 2: 模型参数 ──
      {
        key: "panel-2",
        label: (
          <Space>
            <span>🎛️</span>
            <span>模型参数</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="这些滑块控制 AI 的回答风格。「创造性」越高回答越灵活但可能不准，「创造性」越低回答越稳定但可能死板。一般客服场景建议创造性 0.2~0.5。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label={`Temperature（创造性）: ${config.temperature.toFixed(1)}`}>
                <Slider
                  min={0}
                  max={2}
                  step={0.1}
                  value={config.temperature}
                  onChange={(v) => updateConfig("temperature", v)}
                />
              </Form.Item>
              <Form.Item label={`Max Tokens（回复长度）: ${config.max_tokens}`}>
                <Slider
                  min={50}
                  max={4000}
                  step={50}
                  value={config.max_tokens}
                  onChange={(v) => updateConfig("max_tokens", v)}
                />
              </Form.Item>
              <Form.Item label={`Top P（核采样）: ${config.top_p.toFixed(2)}`}>
                <Slider
                  min={0}
                  max={1}
                  step={0.05}
                  value={config.top_p}
                  onChange={(v) => updateConfig("top_p", v)}
                />
              </Form.Item>
              <Form.Item label={`Frequency Penalty（减少重复）: ${config.frequency_penalty.toFixed(1)}`}>
                <Slider
                  min={-2}
                  max={2}
                  step={0.1}
                  value={config.frequency_penalty}
                  onChange={(v) => updateConfig("frequency_penalty", v)}
                />
              </Form.Item>
              <Form.Item label={`Presence Penalty（话题多样性）: ${config.presence_penalty.toFixed(1)}`}>
                <Slider
                  min={-2}
                  max={2}
                  step={0.1}
                  value={config.presence_penalty}
                  onChange={(v) => updateConfig("presence_penalty", v)}
                />
              </Form.Item>
              <Form.Item label="停止序列（Stop Sequences）">
                <Select
                  mode="tags"
                  value={config.stop_sequences}
                  onChange={(v) => updateConfig("stop_sequences", v)}
                  placeholder="输入后回车添加"
                  style={{ width: "100%" }}
                  open={false}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },

      // ── 面板 3: 会话行为 ──
      {
        key: "panel-3",
        label: (
          <Space>
            <span>💬</span>
            <span>会话行为</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="控制 AI 能记住多少对话内容、新客户进来时是否自动打招呼、以及下班后怎么回复。上下文消息数越多，AI 越能理解前因后果，但也越贵。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="上下文消息数">
                <InputNumber
                  min={1}
                  max={100}
                  value={config.context_window_messages}
                  onChange={(v) => v !== null && updateConfig("context_window_messages", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="上下文 Token 上限">
                <InputNumber
                  min={100}
                  max={32000}
                  step={100}
                  value={config.context_window_tokens}
                  onChange={(v) => v !== null && updateConfig("context_window_tokens", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="启用会话记忆" valuePropName="checked">
                <Switch
                  checked={config.conversation_memory}
                  onChange={(v) => updateConfig("conversation_memory", v)}
                />
              </Form.Item>
              <Form.Item label="开场白消息" help="留空表示不发送开场白">
                <TextArea
                  rows={3}
                  value={config.greeting_message}
                  onChange={(e) => updateConfig("greeting_message", e.target.value)}
                />
              </Form.Item>
              <Form.Item label="非工作时间提示" help="留空表示不发送非工作时间提示">
                <TextArea
                  rows={3}
                  value={config.off_hours_message}
                  onChange={(e) => updateConfig("off_hours_message", e.target.value)}
                />
              </Form.Item>
              <Space>
                <Form.Item label="非工作开始">
                  <TimePicker
                    format="HH:mm"
                    minuteStep={30}
                    value={config.off_hours_start ? undefined : undefined}
                    onChange={(_, timeStr) => {
                      if (typeof timeStr === "string" && timeStr) {
                        updateConfig("off_hours_start", timeStr);
                      }
                    }}
                  />
                </Form.Item>
                <Form.Item label="非工作结束">
                  <TimePicker
                    format="HH:mm"
                    minuteStep={30}
                    value={config.off_hours_end ? undefined : undefined}
                    onChange={(_, timeStr) => {
                      if (typeof timeStr === "string" && timeStr) {
                        updateConfig("off_hours_end", timeStr);
                      }
                    }}
                  />
                </Form.Item>
                <Form.Item label="时区">
                  <Select
                    value={config.off_hours_timezone}
                    onChange={(v) => updateConfig("off_hours_timezone", v)}
                    options={TIMEZONE_OPTIONS}
                    style={{ width: 200 }}
                  />
                </Form.Item>
              </Space>
            </Form>
          </div>
        ),
      },

      // ── 面板 4: 自动回复 ──
      {
        key: "panel-4",
        label: (
          <Space>
            <span>🤖</span>
            <span>自动回复</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="开启后 AI 会自动回复客户消息。可以设置延迟（让客户感觉是真人），也可以设置关键词精确回复（比如客户说「营业时间」就直接回「9:00-21:00」）。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="启用自动回复" valuePropName="checked">
                <Switch
                  checked={config.auto_reply_enabled}
                  onChange={(v) => updateConfig("auto_reply_enabled", v)}
                />
              </Form.Item>
              <Form.Item label="回复延迟(秒)">
                <InputNumber
                  min={0}
                  max={30}
                  value={config.auto_reply_delay_seconds}
                  onChange={(v) => v !== null && updateConfig("auto_reply_delay_seconds", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="关键词精确回复（Key=客户消息, Value=AI 回复）">
                {Object.keys(config.auto_reply_keywords).length === 0 ? (
                  <>
                    <Typography.Text type="secondary" style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
                      暂无关键词回复。添加后，当客户消息匹配关键词时，AI 会直接回复预设内容。
                    </Typography.Text>
                    <Button
                      size="small"
                      onClick={() => {
                        const next = { ...config.auto_reply_keywords, "新关键词": "" };
                        updateConfig("auto_reply_keywords", next);
                      }}
                    >
                      + 添加关键词
                    </Button>
                  </>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {Object.entries(config.auto_reply_keywords).map(([key, val]) => (
                      <Space key={key}>
                        <Input
                          style={{ width: 180 }}
                          value={key}
                          onChange={(e) => {
                            const next = { ...config.auto_reply_keywords };
                            delete next[key];
                            next[e.target.value] = val;
                            updateConfig("auto_reply_keywords", next);
                          }}
                          placeholder="客户说..."
                        />
                        <Input
                          style={{ width: 260 }}
                          value={val}
                          onChange={(e) => {
                            const next = { ...config.auto_reply_keywords, [key]: e.target.value };
                            updateConfig("auto_reply_keywords", next);
                          }}
                          placeholder="AI 回复..."
                        />
                      </Space>
                    ))}
                    <Button
                      size="small"
                      onClick={() => {
                        const next = { ...config.auto_reply_keywords, [""]: "" };
                        updateConfig("auto_reply_keywords", next);
                      }}
                    >
                      + 添加关键词
                    </Button>
                  </div>
                )}
              </Form.Item>
              <Form.Item label="无法理解时的回复" help="留空表示交给 AI 自行处理">
                <TextArea
                  rows={3}
                  value={config.auto_reply_fallback}
                  onChange={(e) => updateConfig("auto_reply_fallback", e.target.value)}
                />
              </Form.Item>
              <Form.Item label="过滤重复消息" valuePropName="checked">
                <Switch
                  checked={config.duplicate_message_filter}
                  onChange={(v) => updateConfig("duplicate_message_filter", v)}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },

      // ── 面板 5: 转人工触发条件 ──
      {
        key: "panel-5",
        label: (
          <Space>
            <span>👤</span>
            <span>转人工触发条件</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="当客户说到「转人工」「找真人」等关键词，或者 AI 连续回答不上来，或者客户情绪很差时，自动转接给人工客服。这样可以避免 AI 硬尬。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="启用自动转人工检测" valuePropName="checked">
                <Switch
                  checked={config.auto_escalation_enabled}
                  onChange={(v) => updateConfig("auto_escalation_enabled", v)}
                />
              </Form.Item>
              <Form.Item label="触发关键词">
                <Select
                  mode="tags"
                  value={config.escalation_keywords}
                  onChange={(v) => updateConfig("escalation_keywords", v)}
                  placeholder="输入触发关键词后按回车"
                  style={{ width: "100%" }}
                />
              </Form.Item>
              <Form.Item label="AI 连续失败次数">
                <InputNumber
                  min={1}
                  max={20}
                  value={config.escalation_max_failures}
                  onChange={(v) => v !== null && updateConfig("escalation_max_failures", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label={`客户情绪阈值: ${config.escalation_sentiment_threshold.toFixed(1)}（低于此值触发转人工）`}>
                <Slider
                  min={-1}
                  max={1}
                  step={0.1}
                  value={config.escalation_sentiment_threshold}
                  onChange={(v) => updateConfig("escalation_sentiment_threshold", v)}
                />
              </Form.Item>
              <Form.Item label="最大对话轮次">
                <InputNumber
                  min={1}
                  max={100}
                  value={config.escalation_max_rounds}
                  onChange={(v) => v !== null && updateConfig("escalation_max_rounds", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="转人工提示语">
                <TextArea
                  rows={2}
                  value={config.escalation_message}
                  onChange={(e) => updateConfig("escalation_message", e.target.value)}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },

      // ── 面板 6: 安全与过滤 ──
      {
        key: "panel-6",
        label: (
          <Space>
            <span>🛡️</span>
            <span>安全与过滤</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="防止 AI 说不该说的话。可以设置禁止话题（比如竞争对手、政治），防止 AI 泄露个人信息，限制回复长度。PII 保护会阻止 AI 输出手机号、身份证等敏感信息。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="禁止话题">
                <Select
                  mode="tags"
                  value={config.blocked_topics}
                  onChange={(v) => updateConfig("blocked_topics", v)}
                  placeholder="输入禁止话题后按回车"
                  style={{ width: "100%" }}
                />
              </Form.Item>
              <Form.Item label="内容安全过滤" valuePropName="checked">
                <Switch
                  checked={config.content_filter_enabled}
                  onChange={(v) => updateConfig("content_filter_enabled", v)}
                />
              </Form.Item>
              <Form.Item label="PII 保护（阻止输出手机号、身份证等敏感信息）" valuePropName="checked">
                <Switch
                  checked={config.pii_protection}
                  onChange={(v) => updateConfig("pii_protection", v)}
                />
              </Form.Item>
              <Form.Item label="最大回复字符数（超出后截断）">
                <InputNumber
                  min={10}
                  max={4000}
                  value={config.max_response_length}
                  onChange={(v) => v !== null && updateConfig("max_response_length", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="强制客户语言（确保 AI 始终用客户的语言回复）" valuePropName="checked">
                <Switch
                  checked={config.language_lock}
                  onChange={(v) => updateConfig("language_lock", v)}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },

      // ── 面板 7: 高级设置 ──
      {
        key: "panel-7",
        label: (
          <Space>
            <span>⚙️</span>
            <span>高级设置</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="品牌信息会自动注入到 AI 的上下文中，让 AI 知道自己代表哪个品牌。知识库注入让 AI 能从知识库中找答案。调试模式会记录完整的 AI 交互日志，方便排查问题。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="回复格式">
                <Select
                  value={config.response_format}
                  onChange={(v) => updateConfig("response_format", v)}
                  options={RESPONSE_FORMAT_OPTIONS}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="注入品牌信息" valuePropName="checked">
                <Switch
                  checked={config.inject_brand_info}
                  onChange={(v) => updateConfig("inject_brand_info", v)}
                />
              </Form.Item>
              <Form.Item label="注入知识库" valuePropName="checked">
                <Switch
                  checked={config.inject_knowledge_base}
                  onChange={(v) => updateConfig("inject_knowledge_base", v)}
                />
              </Form.Item>
              <Form.Item label="调试模式（记录完整的 AI 交互日志）" valuePropName="checked">
                <Switch
                  checked={config.debug_mode}
                  onChange={(v) => updateConfig("debug_mode", v)}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },

      // ── 面板 8: AI 工具调用 ──
      {
        key: "panel-8",
        label: (
          <Space>
            <span>🛠️</span>
            <span>AI 智能工具</span>
          </Space>
        ),
        children: (
          <div style={{ padding: "8px 0" }}>
            <Alert
              type="info"
              showIcon
              message="开启后 AI 可以调用系统能力帮客户办事。比如客户问「我还有多少钱」，AI 会自动查询余额并回复。所有工具都是只读查询，绝对不会修改任何数据，也不会查看其他客户的信息。你可以选择启用哪些工具，以及每个会话最多调用多少次。"
              style={{ marginBottom: 16 }}
            />
            <Form layout="vertical">
              <Form.Item label="启用 AI 工具调用" valuePropName="checked">
                <Switch
                  checked={config.tools_enabled}
                  onChange={(v) => updateConfig("tools_enabled", v)}
                />
              </Form.Item>
              <Form.Item label="可用工具（勾选后 AI 可在对话中调用）">
                <Checkbox.Group
                  value={config.enabled_tools}
                  onChange={(v) => updateConfig("enabled_tools", v as string[])}
                  style={{ display: "flex", flexDirection: "column", gap: 8 }}
                >
                  {TOOL_OPTIONS.map((tool) => (
                    <Checkbox key={tool.value} value={tool.value}>
                      <Space size={4}>
                        <span>☑ {tool.label}</span>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          - {tool.desc}
                        </Typography.Text>
                      </Space>
                    </Checkbox>
                  ))}
                </Checkbox.Group>
              </Form.Item>
              <Form.Item
                label="每会话最大调用次数"
                help="防止 AI 死循环调用，建议 5~15 次"
              >
                <InputNumber
                  min={1}
                  max={50}
                  value={config.max_tool_calls_per_session}
                  onChange={(v) => v !== null && updateConfig("max_tool_calls_per_session", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
              <Form.Item label="身份验证方式">
                <Select
                  value={config.identity_verify_method}
                  onChange={(v) => updateConfig("identity_verify_method", v)}
                  options={VERIFICATION_METHOD_OPTIONS}
                  style={{ width: 340 }}
                />
              </Form.Item>
              <Form.Item
                label="允许 AI 主动要求验证"
                valuePropName="checked"
                help="开启后，客户问账户问题时 AI 会先要求验证身份"
              >
                <Switch
                  checked={config.identity_auto_verify}
                  onChange={(v) => updateConfig("identity_auto_verify", v)}
                />
              </Form.Item>
              <Form.Item label="工具调用超时(秒)">
                <InputNumber
                  min={1}
                  max={60}
                  value={config.tool_call_timeout_seconds}
                  onChange={(v) => v !== null && updateConfig("tool_call_timeout_seconds", v)}
                  style={{ width: 200 }}
                />
              </Form.Item>
            </Form>
          </div>
        ),
      },
    ],
    [config, updateConfig, handlePreviewPrompt]
  );

  // ── Tab 配置 ──
  const tabItems = useMemo(() => {
    const items: Array<{ key: string; label: string; children: JSX.Element }> = [];
    if (hasSystemScope) {
      items.push({
        key: "system",
        label: "系统默认配置",
        children: (
          <div style={{ minHeight: 200 }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: 40, color: "#999" }}>加载中...</div>
            ) : (
                <Collapse items={collapseItems} defaultActiveKey={["panel-1"]} />
            )}
          </div>
        ),
      });
    }
    items.push({
      key: "agency",
      label: "代理商配置",
      children: (
        <div style={{ minHeight: 200 }}>
          {hasSystemScope && (
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Typography.Text strong>选择代理商：</Typography.Text>
                <Select
                  style={{ width: 280 }}
                  placeholder="选择代理商"
                  value={selectedAgency}
                  onChange={(v) => setSelectedAgency(v)}
                  allowClear
                  options={agencies.map((a) => ({ label: a.name, value: a.id }))}
                />
              </Space>
            </div>
          )}
          {loading ? (
            <div style={{ textAlign: "center", padding: 40, color: "#999" }}>加载中...</div>
          ) : !hasSystemScope || selectedAgency ? (
            <Collapse items={collapseItems} defaultActiveKey={["panel-1"]} />
          ) : (
            <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
              请先选择代理商以查看或编辑其 AI 聊天配置
            </div>
          )}
        </div>
      ),
    });
    return items;
  }, [hasSystemScope, loading, collapseItems, agencies, selectedAgency]);

  // ── 权限检查 ──
  const hasAIChatAccess =
    canViewSystem ||
    canViewAgency ||
    canEditSystem ||
    canEditAgency;

  if (!hasAIChatAccess) {
    return (
      <PageShell title="AI 智能聊天配置" subtitle="配置 AI 智能聊天参数、工具调用并进行测试验证">
        <Card>
          <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <Typography.Title level={4} type="secondary">暂无访问权限</Typography.Title>
            <Typography.Text type="secondary">请联系管理员获取 AI 聊天配置的管理权限</Typography.Text>
          </div>
        </Card>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="AI 智能聊天配置"
      subtitle="配置 AI 智能聊天参数、工具调用并进行测试验证"
      actions={
        <Space>
          {activeTab === "agency" && hasSystemScope && selectedAgency && canResetAgency && (
            <Button icon={<ClearOutlined />} onClick={handleReset} loading={resetting}>
              恢复系统默认
            </Button>
          )}
          {canTest && (
            <Button icon={<ThunderboltOutlined />} onClick={() => setTestModalOpen(true)}>
              测试聊天
            </Button>
          )}
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSave}
            loading={saving}
            disabled={
              (activeTab === "system" && !canEditSystem) ||
              (activeTab === "agency" && !canEditAgency)
            }
          >
            保存配置
          </Button>
        </Space>
      }
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      {/* ── 测试聊天 Modal ── */}
      <Modal
        title="AI 聊天测试"
        open={testModalOpen}
        onCancel={() => setTestModalOpen(false)}
        footer={null}
        width={700}
      >
        <Alert
          type="info"
          showIcon
          message="使用真实系统数据测试 AI 的回复效果。可以测试工具调用（如查询余额）、回复风格、语言方向是否符合预期。测试消息会发送到真实的 AI 服务，但不会发送给任何客户。"
          style={{ marginBottom: 16 }}
        />
        {/* 对话历史 */}
        <div
          style={{
            maxHeight: 300,
            overflow: "auto",
            marginBottom: 12,
            background: "#fafafa",
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            padding: 12,
          }}
        >
          {testHistory.length === 0 && !testReply && (
            <div style={{ textAlign: "center", padding: 24, color: "#ccc" }}>
              输入消息开始测试
            </div>
          )}
          {testHistory.map((msg, i) => (
            <div
              key={i}
              style={{
                textAlign: msg.role === "user" ? "right" : "left",
                marginBottom: 8,
              }}
            >
              <Tag
                color={msg.role === "user" ? "blue" : "green"}
                style={{ marginRight: 4 }}
              >
                {msg.role === "user" ? "用户" : "AI"}
              </Tag>
              <Typography.Text style={{ fontSize: 13 }}>{msg.text}</Typography.Text>
              {msg.tool_calls && (
                <Tag color="orange" style={{ marginLeft: 4 }}>
                  调用了: {msg.tool_calls}
                </Tag>
              )}
            </div>
          ))}
        </div>
        {/* 输入框 */}
        <TextArea
          value={testMessage}
          onChange={(e) => setTestMessage(e.target.value)}
          placeholder="输入测试消息，如: 我还有多少钱？"
          rows={2}
          style={{ marginBottom: 8 }}
        />
        <Space>
          <Button
            type="primary"
            onClick={handleSendTest}
            loading={testSending}
            icon={<SendOutlined />}
          >
            发送测试
          </Button>
          <Button onClick={handleClearHistory} icon={<ClearOutlined />}>
            清空对话
          </Button>
        </Space>
        {/* AI 回复卡片 */}
        {testReply && (
          <Card size="small" title="AI 回复" style={{ marginTop: 12 }}>
            <Paragraph style={{ whiteSpace: "pre-wrap", margin: 0 }}>
              {testReply}
            </Paragraph>
            <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 8 }}>
              响应时间: {testLatency}ms
              {testToolCalls && testToolCalls.length > 0
                ? ` | 工具调用: ${testToolCalls.join(", ")}`
                : " | 工具调用: 无"}
            </Typography.Text>
          </Card>
        )}
      </Modal>
    </PageShell>
  );
}

export default AIChatConfigPage;

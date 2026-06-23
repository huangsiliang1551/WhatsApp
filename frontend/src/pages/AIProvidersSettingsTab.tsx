import { useCallback, useState, type JSX } from "react";
import {
  Button, Card, Col, Form, Input, InputNumber, Modal, Popconfirm,
  Row, Select, Space, Switch, Tag, Typography, message,
} from "antd";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";

import { EmptyGuide } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { usePageData } from "../hooks/usePageData";
import {
  listAIProviderConfigs,
  createAIProviderConfig,
  updateAIProviderConfig,
  deleteAIProviderConfig,
  testAIProviderConnection,
} from "../services/aiProviderApi";
import type {
  AIProviderConfig,
  CreateAIProviderRequest,
  UpdateAIProviderRequest,
  TestConnectionResponse,
} from "../types/aiProviders";

// ── Presets ──

interface PresetValue {
  api_base_url: string;
  model: string;
  use_responses_api: boolean;
}

const PROVIDER_PRESETS: Record<string, PresetValue> = {
  openai:   { api_base_url: "",                                    model: "gpt-5.4-mini",                  use_responses_api: true },
  deepseek: { api_base_url: "https://api.deepseek.com/v1",        model: "deepseek-chat",                 use_responses_api: false },
  groq:     { api_base_url: "https://api.groq.com/openai/v1",     model: "llama-3.3-70b-versatile",       use_responses_api: false },
  ollama:   { api_base_url: "http://localhost:11434/v1",          model: "llama3.3",                      use_responses_api: false },
  together: { api_base_url: "https://api.together.xyz/v1",        model: "meta-llama/Llama-3.3-70B-Instruct-Turbo", use_responses_api: false },
  custom:   { api_base_url: "",                                    model: "",                               use_responses_api: false },
};

const PROVIDER_TYPE_OPTIONS = Object.keys(PROVIDER_PRESETS).map((t) => ({
  label: t === "openai" ? "OpenAI" : t === "deepseek" ? "DeepSeek" : t === "groq" ? "Groq" : t === "ollama" ? "Ollama" : t === "together" ? "Together" : "自定义",
  value: t,
}));

// ── Helpers ──

function statusIcon(p: AIProviderConfig): string {
  return p.is_enabled ? "🟢" : "⚫";
}

function formatLatency(ms: number | null): string {
  if (ms === null) return "";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

// ── AIProvidersSettingsTab ──

export function AIProvidersSettingsTab(): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<AIProviderConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [testingCardId, setTestingCardId] = useState<string | null>(null);
  const [disableLoadingId, setDisableLoadingId] = useState<string | null>(null);
  const [cardTestResults, setCardTestResults] = useState<Record<string, TestConnectionResponse | null>>({});
  const [form] = Form.useForm();
  const providerType = Form.useWatch("provider_type", form);

  const fetcher = useCallback(async () => {
    const [providers] = await Promise.all([
      listAIProviderConfigs(true),
    ]);
    return { providers };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher, immediate: true });
  const providers = data?.providers ?? [];

  // ── Open modal (create / edit) ──
  const openCreate = () => {
    setEditTarget(null);
    setTestResult(null);
    form.resetFields();
    form.setFieldsValue({
      provider_type: "openai",
      priority: 0,
      timeout_seconds: 30,
      is_enabled: true,
      ...PROVIDER_PRESETS["openai"],
    });
    setModalOpen(true);
  };

  const openEdit = (p: AIProviderConfig) => {
    setEditTarget(p);
    setTestResult(null);
    form.resetFields();
    form.setFieldsValue({
      name: p.name,
      provider_type: p.provider_type,
      api_base_url: p.api_base_url ?? "",
      model: p.model,
      priority: p.priority,
      timeout_seconds: p.timeout_seconds,
      is_enabled: p.is_enabled,
      use_responses_api: p.use_responses_api,
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditTarget(null);
    setTestResult(null);
  };

  // ── Type change → auto-fill presets ──
  const handleTypeChange = (type: string) => {
    const preset = PROVIDER_PRESETS[type];
    if (!preset) return;
    form.setFieldsValue({
      api_base_url: preset.api_base_url,
      model: preset.model,
      use_responses_api: preset.use_responses_api,
    });
  };

  // ── Save ──
  const handleSave = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      if (editTarget) {
        const payload: UpdateAIProviderRequest = {
          name: values.name,
          api_base_url: values.api_base_url || null,
          api_key: values.api_key || undefined,
          model: values.model,
          priority: values.priority,
          is_enabled: values.is_enabled,
          timeout_seconds: values.timeout_seconds,
          use_responses_api: values.use_responses_api,
        };
        await updateAIProviderConfig(editTarget.id, payload);
        showSuccess("提供商已更新");
      } else {
        const payload: CreateAIProviderRequest = {
          name: values.name,
          provider_type: values.provider_type,
          api_base_url: values.api_base_url || null,
          api_key: values.api_key || null,
          model: values.model,
          priority: values.priority ?? 0,
          is_enabled: values.is_enabled ?? true,
          timeout_seconds: values.timeout_seconds ?? 30,
          use_responses_api: values.use_responses_api ?? false,
        };
        await createAIProviderConfig(payload);
        showSuccess("提供商已创建");
      }
      closeModal();
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  // ── Toggle enable ──
  const handleToggle = async (p: AIProviderConfig) => {
    setDisableLoadingId(p.id);
    try {
      await updateAIProviderConfig(p.id, { is_enabled: !p.is_enabled });
      showSuccess(p.is_enabled ? "已禁用" : "已启用");
      void reload();
    } catch { showError("操作失败"); }
    finally { setDisableLoadingId(null); }
  };

  // ── Delete ──
  const handleDelete = async (p: AIProviderConfig) => {
    try {
      await deleteAIProviderConfig(p.id);
      showSuccess("已删除");
      void reload();
    } catch { showError("删除失败"); }
  };

  // ── Test connection (modal) ──
  const handleTestModal = async () => {
    if (!editTarget) {
      message.info("请先保存提供商后再测试连接");
      return;
    }
    try {
      const values = await form.validateFields();
      setTesting(true);
      setTestResult(null);
      const result = await testAIProviderConnection({
        config_id: editTarget.id,
        provider_type: values.provider_type,
        api_base_url: values.api_base_url || null,
        api_key: values.api_key || null,
        model: values.model,
        timeout_seconds: values.timeout_seconds,
      });
      setTestResult(result);
    } catch (e) {
      setTestResult({ status: "error", latency_ms: null, model_echoed: null, error_type: e instanceof Error && e.message === "缺少 config_id，请先保存提供商后再测试连接" ? "missing_config" : "validation", message: e instanceof Error ? e.message : "表单验证失败" });
    } finally {
      setTesting(false);
    }
  };

  // ── Test connection (card) ──
  const handleTestCard = async (p: AIProviderConfig) => {
    setTestingCardId(p.id);
    try {
      const result = await testAIProviderConnection({ config_id: p.id });
      setCardTestResults(prev => ({ ...prev, [p.id]: result }));
    } catch (e) {
      setCardTestResults(prev => ({ ...prev, [p.id]: { status: "error", latency_ms: null, model_echoed: null, error_type: "request", message: e instanceof Error ? e.message : "请求失败" } }));
    } finally {
      setTestingCardId(null);
    }
  };

  // ── Set as default ──
  const handleSetDefault = async (p: AIProviderConfig) => {
    try {
      // Clear is_default on all other providers first
      const clearPromises = providers
        .filter(pr => pr.id !== p.id && pr.metadata_json?.is_default)
        .map(pr => updateAIProviderConfig(pr.id, { metadata_json: {} }));
      await Promise.all(clearPromises);
      // Set new default
      await updateAIProviderConfig(p.id, { metadata_json: { is_default: true } });
      showSuccess("已设为默认");
      void reload();
    } catch { showError("操作失败"); }
  };


  // ── Sort providers by priority ──
  const sortedProviders = [...providers].sort((a, b) => a.priority - b.priority);

  // ── Render ──
  const actions = (
    <Space>
      <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreate}>
        添加 AI 提供商
      </Button>
      <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>
        刷新
      </Button>
    </Space>
  );

  if (!data && loading) {
    return <div style={{ textAlign: "center", padding: 48, color: "#999" }}>加载中...</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>{actions}</div>

      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}

      {/* ── Fallback Chain ── */}
      {sortedProviders.length === 0 ? (
        <EmptyGuide icon="🤖" title="暂无 AI 提供商" description="添加 AI 提供商以启用自动回复功能" actions={[{ label: "添加 AI 提供商", onClick: openCreate }]} />
      ) : (
        <>
          <Typography.Title level={5} style={{ margin: "0 0 8px", fontSize: 14 }}>Fallback 链 <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>（按优先级排序）</Typography.Text></Typography.Title>
          <div style={{ marginBottom: 24 }}>
            {sortedProviders.map((p, i) => (
              <Card
                key={p.id}
                size="small"
                style={{ marginBottom: 8, borderLeft: `3px solid ${p.is_enabled ? "#52c41a" : "#d9d9d9"}` }}
              >
                <Row align="middle" gutter={12}>
                  <Col flex="auto">
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <Typography.Text strong style={{ fontSize: 13 }}>{i + 1}.</Typography.Text>
                      <span style={{ fontSize: 13 }}>{statusIcon(p)}</span>
                      <Typography.Text strong style={{ fontSize: 13 }}>{p.name}</Typography.Text>
                      <Tag>{p.provider_type}</Tag>
                      <Tag color="purple">{p.model}</Tag>
                      {p.metadata_json?.is_default === true && <Tag color="blue">默认</Tag>}
                      <Typography.Text type="secondary" style={{ fontSize: 11 }}>priority={p.priority}</Typography.Text>
                    </div>
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                      {p.api_base_url ? `base: ${p.api_base_url}` : "base: (默认)"}
                    </Typography.Text>
                  </Col>
                  <Col>
                    <Space size="small">
                      <Button size="small" onClick={() => openEdit(p)}>编辑</Button>
                      <Button size="small" onClick={() => void handleTestCard(p)} loading={testingCardId === p.id}>测试连接</Button>
                      {p.metadata_json?.is_default === true ? (
                        <Tag color="blue">默认</Tag>
                      ) : (
                        <Button size="small" onClick={() => void handleSetDefault(p)}>设为默认</Button>
                      )}
                      <Popconfirm
                        title={p.is_enabled ? "确认禁用此提供商？" : "确认启用此提供商？"}
                        onConfirm={async () => { await handleToggle(p); }}
                        okText="确认"
                        cancelText="取消"
                      >
                        <Button size="small" loading={disableLoadingId === p.id}>{p.is_enabled ? "禁用" : "启用"}</Button>
                      </Popconfirm>
                      <DangerButton
                        label="删除"
                        confirmTitle="确认删除此 AI 提供商？"
                        confirmDescription={`此操作将删除 ${p.name}`}
                        onConfirm={() => handleDelete(p)}
                        type="default"
                      />
                    </Space>
                  </Col>
                </Row>
                {p.has_api_key && (
                  <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
                    🔑 API Key 已配置
                  </Typography.Text>
                )}
                {cardTestResults[p.id] && (
                  <div style={{ marginTop: 4, fontSize: 11, lineHeight: "20px" }}>
                    {cardTestResults[p.id]!.status === "ok" ? (
                      <span style={{ color: "#52c41a" }}>✅ 连接成功 ({formatLatency(cardTestResults[p.id]!.latency_ms)}){cardTestResults[p.id]!.model_echoed ? ` · 模型: ${cardTestResults[p.id]!.model_echoed}` : ""}</span>
                    ) : (
                      <span style={{ color: "#ff4d4f" }}>
                        ❌ 连接失败{cardTestResults[p.id]!.error_type ? `: ${cardTestResults[p.id]!.error_type}` : ""}{cardTestResults[p.id]!.message ? ` · ${cardTestResults[p.id]!.message}` : ""}
                      </span>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </>
      )}

      {/* ── Add / Edit Modal ── */}
      <Modal
        title={editTarget ? "编辑 AI 提供商" : "添加 AI 提供商"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={handleSave}
        confirmLoading={saving}
        okText={editTarget ? "保存" : "创建"}
        cancelText="取消"
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="类型" name="provider_type" rules={[{ required: true, message: "请选择提供商类型" }]}>
            <Select
              options={PROVIDER_TYPE_OPTIONS}
              onChange={handleTypeChange}
              placeholder="选择类型"
              disabled={!!editTarget}
            />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="例如：生产 DeepSeek" />
          </Form.Item>
          <Form.Item label="API Base URL" name="api_base_url">
            <Input placeholder="留空使用默认 URL" />
          </Form.Item>
          <Form.Item label="API Key" name="api_key">
            <Input.Password
              placeholder={editTarget ? "留空保留原密钥" : "输入 API Key"}
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item label="模型" name="model" rules={[{ required: true, message: "请输入模型名" }]}>
            <Input placeholder="例如：gpt-5.4-mini" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item label="超时(秒)" name="timeout_seconds">
                <InputNumber min={1} max={300} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="优先级" name="priority">
                <InputNumber min={0} max={999} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="启用" name="is_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          {providerType === "openai" && (
            <Form.Item label="使用 Responses API" name="use_responses_api" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}

          {/* Test Connection */}
          <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12, marginBottom: 12 }}>
            <Space align="start">
              <Button onClick={() => void handleTestModal()} loading={testing} icon={<span>🔌</span>}>
                测试连接
              </Button>
              {testResult && (
                <div style={{ fontSize: 12, lineHeight: "22px" }}>
                  {testResult.status === "ok" ? (
                    <span style={{ color: "#52c41a" }}>✅ 成功 ({formatLatency(testResult.latency_ms)}){testResult.model_echoed ? ` · 模型: ${testResult.model_echoed}` : ""}</span>
                  ) : (
                    <span style={{ color: "#ff4d4f" }}>
                      ❌ 失败{testResult.error_type ? `: ${testResult.error_type}` : ""}{testResult.message ? ` · ${testResult.message}` : ""}
                    </span>
                  )}
                </div>
              )}
            </Space>
          </div>
        </Form>
      </Modal>
    </div>
  );
}

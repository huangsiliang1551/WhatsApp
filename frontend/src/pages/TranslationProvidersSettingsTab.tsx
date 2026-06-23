import { useCallback, useState, type JSX } from "react";
import {
  Button, Card, Col, Form, Input, InputNumber, Modal, Popconfirm,
  Row, Select, Space, Spin, Switch, Table, Tag, Typography, message,
} from "antd";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";

import { EmptyGuide } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { usePageData } from "../hooks/usePageData";
import { withSorter } from "../utils/withSorter";
import {
  listTranslationProviderConfigs,
  createTranslationProviderConfig,
  updateTranslationProviderConfig,
  deleteTranslationProviderConfig,
  testTranslationProviderConnection,
  pingTMTRegions,
} from "../services/translationProviderApi";
import type {
  TranslationProviderConfig,
  CreateTranslationProviderRequest,
  UpdateTranslationProviderRequest,
  TestConnectionResponse,
  RegionPingResult,
} from "../types/translationProviders";

// ── Presets ──

const PROVIDER_TYPE_OPTIONS = [
  { label: "腾讯云 TMT", value: "tencent_cloud" },
];

const REGION_OPTIONS = [
  { label: "广州 (ap-guangzhou)", value: "ap-guangzhou" },
  { label: "北京 (ap-beijing)", value: "ap-beijing" },
  { label: "上海 (ap-shanghai)", value: "ap-shanghai" },
  { label: "南京 (ap-nanjing)", value: "ap-nanjing" },
  { label: "成都 (ap-chengdu)", value: "ap-chengdu" },
  { label: "香港 (ap-hongkong)", value: "ap-hongkong" },
  { label: "新加坡 (ap-singapore)", value: "ap-singapore" },
  { label: "东京 (ap-tokyo)", value: "ap-tokyo" },
  { label: "硅谷 (na-siliconvalley)", value: "na-siliconvalley" },
];

// ── Helpers ──

function statusIcon(p: TranslationProviderConfig): string {
  return p.is_enabled ? "🟢" : "⚫";
}

function formatLatency(ms: number | null): string {
  if (ms === null) return "";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function providerTypeLabel(t: string): string {
  const opt = PROVIDER_TYPE_OPTIONS.find(o => o.value === t);
  return opt?.label ?? t;
}

// ── TranslationProvidersSettingsTab ──

export function TranslationProvidersSettingsTab(): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<TranslationProviderConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);
  const [testing, setTesting] = useState(false);
  const [testingCardId, setTestingCardId] = useState<string | null>(null);
  const [disableLoadingId, setDisableLoadingId] = useState<string | null>(null);
  const [cardTestResults, setCardTestResults] = useState<Record<string, TestConnectionResponse | null>>({});
  const [form] = Form.useForm();

  // ── Region Ping state ──
  const [pingModalOpen, setPingModalOpen] = useState(false);
  const [pingResults, setPingResults] = useState<RegionPingResult[]>([]);
  const [pingLoading, setPingLoading] = useState(false);

  const fetcher = useCallback(async () => {
    const [providers] = await Promise.all([
      listTranslationProviderConfigs(true),
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
      provider_type: "tencent_cloud",
      region: "ap-guangzhou",
      priority: 0,
      timeout_seconds: 15,
      is_enabled: true,
    });
    setModalOpen(true);
  };

  const openEdit = (p: TranslationProviderConfig) => {
    setEditTarget(p);
    setTestResult(null);
    form.resetFields();
    form.setFieldsValue({
      name: p.name,
      provider_type: p.provider_type,
      region: p.region || "ap-guangzhou",
      priority: p.priority,
      timeout_seconds: p.timeout_seconds,
      is_enabled: p.is_enabled,
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditTarget(null);
    setTestResult(null);
  };

  // ── Save ──
  const handleSave = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      if (editTarget) {
        const payload: UpdateTranslationProviderRequest = {
          name: values.name,
          region: values.region || null,
          secret_id: values.secret_id || undefined,
          secret_key: values.secret_key || undefined,
          priority: values.priority,
          is_enabled: values.is_enabled,
          timeout_seconds: values.timeout_seconds,
        };
        await updateTranslationProviderConfig(editTarget.id, payload);
        showSuccess("翻译提供商已更新");
      } else {
        const payload: CreateTranslationProviderRequest = {
          name: values.name,
          provider_type: values.provider_type,
          secret_id: values.secret_id || "",
          secret_key: values.secret_key || "",
          region: values.region || "ap-guangzhou",
          priority: values.priority ?? 0,
          is_enabled: values.is_enabled ?? true,
          timeout_seconds: values.timeout_seconds ?? 15,
        };
        await createTranslationProviderConfig(payload);
        showSuccess("翻译提供商已创建");
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
  const handleToggle = async (p: TranslationProviderConfig) => {
    setDisableLoadingId(p.id);
    try {
      await updateTranslationProviderConfig(p.id, { is_enabled: !p.is_enabled });
      showSuccess(p.is_enabled ? "已禁用" : "已启用");
      void reload();
    } catch { showError("操作失败"); }
    finally { setDisableLoadingId(null); }
  };

  // ── Delete ──
  const handleDelete = async (p: TranslationProviderConfig) => {
    try {
      await deleteTranslationProviderConfig(p.id);
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
      setTesting(true);
      setTestResult(null);
      const result = await testTranslationProviderConnection({
        config_id: editTarget.id,
        timeout_seconds: form.getFieldValue("timeout_seconds") || 15,
      });
      setTestResult(result);
    } catch (e) {
      setTestResult({ status: "error", latency_ms: null, source_text: null, translated_text: null, error_type: "request", message: e instanceof Error ? e.message : "请求失败", error_friendly_message: null, error_code: null });
    } finally {
      setTesting(false);
    }
  };

  // ── Test connection (card) ──
  const handleTestCard = async (p: TranslationProviderConfig) => {
    setTestingCardId(p.id);
    try {
      const result = await testTranslationProviderConnection({ config_id: p.id });
      setCardTestResults(prev => ({ ...prev, [p.id]: result }));
    } catch (e) {
      setCardTestResults(prev => ({ ...prev, [p.id]: { status: "error", latency_ms: null, source_text: null, translated_text: null, error_type: "request", message: e instanceof Error ? e.message : "请求失败", error_friendly_message: null, error_code: null } }));
    } finally {
      setTestingCardId(null);
    }
  };

  // ── Region Ping ──
  const handlePingRegions = async () => {
    if (!editTarget) {
      setPingModalOpen(true);
      setPingLoading(true);
      setPingResults([]);
      try {
        // Use form values for temp credentials
        const values = form.getFieldsValue();
        const result = await pingTMTRegions({
          secret_id: values.secret_id || undefined,
          secret_key: values.secret_key || undefined,
          timeout_seconds: values.timeout_seconds || 10,
        });
        setPingResults(result.results);
      } catch (e) {
        message.error(e instanceof Error ? e.message : "测速失败");
      } finally {
        setPingLoading(false);
      }
      return;
    }
    setPingModalOpen(true);
    setPingLoading(true);
    setPingResults([]);
    try {
      const result = await pingTMTRegions({
        config_id: editTarget.id,
        timeout_seconds: form.getFieldValue("timeout_seconds") || 10,
      });
      setPingResults(result.results);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "测速失败");
    } finally {
      setPingLoading(false);
    }
  };

  // ── Select fastest region from ping results ──
  const handleSelectFastestRegion = () => {
    const fastest = pingResults.find(r => r.status === "ok");
    if (fastest) {
      form.setFieldsValue({ region: fastest.region });
      message.success(`已自动选择最快地域: ${fastest.label} (${fastest.latency_ms}ms)`);
      setPingModalOpen(false);
    } else {
      message.warning("没有可用的地域，请检查网络连接或密钥配置");
    }
  };

  // ── Select a specific region from ping results ──
  const handleSelectRegion = (region: string) => {
    form.setFieldsValue({ region });
    setPingModalOpen(false);
  };

  // ── Set as default ──
  const handleSetDefault = async (p: TranslationProviderConfig) => {
    try {
      // Clear is_default on all other providers first
      const clearPromises = providers
        .filter(pr => pr.id !== p.id && pr.metadata_json?.is_default)
        .map(pr => updateTranslationProviderConfig(pr.id, { metadata_json: {} }));
      await Promise.all(clearPromises);
      // Set new default
      await updateTranslationProviderConfig(p.id, { metadata_json: { is_default: true } });
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
        添加翻译提供商
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

      {/* ── Provider List ── */}
      {sortedProviders.length === 0 ? (
        <EmptyGuide icon="🌐" title="暂无翻译提供商" description="添加翻译提供商以启用机器翻译功能" actions={[{ label: "添加翻译提供商", onClick: openCreate }]} />
      ) : (
        <>
          <Typography.Title level={5} style={{ margin: "0 0 8px", fontSize: 14 }}>
            Fallback 链 <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>（按优先级排序，失败自动降级到 AI 翻译）</Typography.Text>
          </Typography.Title>
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
                      <Tag>{providerTypeLabel(p.provider_type)}</Tag>
                      {p.region && <Tag color="geekblue">{p.region}</Tag>}
                      {p.metadata_json?.is_default === true && <Tag color="blue">默认</Tag>}
                      <Typography.Text type="secondary" style={{ fontSize: 11 }}>priority={p.priority}</Typography.Text>
                    </div>
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
                        title={p.is_enabled ? "确认禁用此翻译提供商？" : "确认启用此翻译提供商？"}
                        onConfirm={async () => { await handleToggle(p); }}
                        okText="确认"
                        cancelText="取消"
                      >
                        <Button size="small" loading={disableLoadingId === p.id}>{p.is_enabled ? "禁用" : "启用"}</Button>
                      </Popconfirm>
                      <DangerButton
                        label="删除"
                        confirmTitle="确认删除此翻译提供商？"
                        confirmDescription={`此操作将删除 ${p.name}`}
                        onConfirm={() => handleDelete(p)}
                        type="default"
                      />
                    </Space>
                  </Col>
                </Row>
                {p.has_secret && (
                  <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
                    🔑 SecretId / SecretKey 已配置
                  </Typography.Text>
                )}
                {cardTestResults[p.id] && (
                  <div style={{ marginTop: 4, fontSize: 11, lineHeight: "20px" }}>
                    {cardTestResults[p.id]!.status === "ok" ? (
                      <span style={{ color: "#52c41a" }}>
                        ✅ 连接成功 ({formatLatency(cardTestResults[p.id]!.latency_ms)})
                        {cardTestResults[p.id]!.translated_text
                          ? ` · "Hello" → "${cardTestResults[p.id]!.translated_text}"`
                          : ""}
                      </span>
                    ) : (
                      <div>
                        <span style={{ color: "#ff4d4f" }}>
                          ❌ 连接失败{cardTestResults[p.id]!.error_type ? `: ${cardTestResults[p.id]!.error_type}` : ""}{cardTestResults[p.id]!.message ? ` · ${cardTestResults[p.id]!.message}` : ""}
                        </span>
                        {cardTestResults[p.id]!.error_friendly_message && (
                          <div style={{ color: "#ff7a45", marginTop: 2 }}>
                            💡 {cardTestResults[p.id]!.error_friendly_message}
                          </div>
                        )}
                      </div>
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
        title={editTarget ? "编辑翻译提供商" : "添加翻译提供商"}
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
              placeholder="选择类型"
              disabled={!!editTarget}
            />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="例如：生产腾讯云翻译" />
          </Form.Item>
          <Form.Item label="SecretId" name="secret_id" rules={!editTarget ? [{ required: true, message: "请输入 SecretId" }] : []}>
            <Input.Password
              placeholder={editTarget ? "留空保留原 SecretId" : "输入 Tencent Cloud SecretId"}
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item label="SecretKey" name="secret_key" rules={!editTarget ? [{ required: true, message: "请输入 SecretKey" }] : []}>
            <Input.Password
              placeholder={editTarget ? "留空保留原 SecretKey" : "输入 Tencent Cloud SecretKey"}
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item label="地域 (Region)" name="region">
            <Row gutter={8} align="middle">
              <Col flex="auto">
                <Select options={REGION_OPTIONS} placeholder="选择地域" />
              </Col>
              <Col>
                <Button
                  size="small"
                  icon={<span>⚡</span>}
                  onClick={() => void handlePingRegions()}
                  loading={pingLoading}
                >
                  测速
                </Button>
              </Col>
            </Row>
          </Form.Item>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item label="超时(秒)" name="timeout_seconds">
                <InputNumber min={5} max={120} style={{ width: "100%" }} />
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

          {/* Test Connection */}
          <div style={{ borderTop: "1px solid #f0f0f0", paddingTop: 12, marginBottom: 12 }}>
            <Space align="start">
              <Button onClick={() => void handleTestModal()} loading={testing} icon={<span>🔌</span>}>
                测试连接
              </Button>
              {testResult && (
                <div style={{ fontSize: 12, lineHeight: "22px" }}>
                  {testResult.status === "ok" ? (
                    <span style={{ color: "#52c41a" }}>
                      ✅ 成功 ({formatLatency(testResult.latency_ms)})
                      {testResult.source_text && testResult.translated_text
                        ? ` · "${testResult.source_text}" → "${testResult.translated_text}"`
                        : ""}
                    </span>
                  ) : (
                    <div style={{ fontSize: 12, lineHeight: "22px" }}>
                      <span style={{ color: "#ff4d4f" }}>
                        ❌ 失败{testResult.error_type ? `: ${testResult.error_type}` : ""}{testResult.message ? ` · ${testResult.message}` : ""}
                      </span>
                      {testResult.error_friendly_message && (
                        <div style={{ color: "#ff7a45", marginTop: 2 }}>
                          💡 {testResult.error_friendly_message}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </Space>
          </div>
        </Form>
      </Modal>

      {/* ── Region Ping Results Modal ── */}
      <Modal
        title="地域测速结果"
        open={pingModalOpen}
        onCancel={() => setPingModalOpen(false)}
        footer={
          <Space>
            <Button onClick={() => setPingModalOpen(false)}>关闭</Button>
            <Button type="primary" onClick={handleSelectFastestRegion} disabled={!pingResults.some(r => r.status === "ok")}>
              选择最快地域
            </Button>
          </Space>
        }
        width={600}
      >
        {pingLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin size="large" />
            <div style={{ marginTop: 12, color: "#999" }}>正在测试各地域延迟，请稍候...</div>
          </div>
        ) : pingResults.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
            暂无数据，请先输入 SecretId 和 SecretKey 后重试
          </div>
        ) : (
          <div>
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12, fontSize: 12 }}>
              按延迟从快到慢排序，绿色为可用地域，红色为不可用
            </Typography.Text>
            <Table
              dataSource={pingResults}
              rowKey="region"
              size="small"
              pagination={false}
              onRow={(record) => ({
                onClick: () => record.status === "ok" && handleSelectRegion(record.region),
                style: {
                  cursor: record.status === "ok" ? "pointer" : "default",
                  background: record.status === "ok" ? "#f6ffed" : undefined,
                },
              })}
              columns={withSorter([
                {
                  title: "状态",
                  dataIndex: "status",
                  key: "status",
                  width: 60,
                  render: (s: string) => s === "ok" ? <Tag color="success">正常</Tag> : s === "timeout" ? <Tag color="warning">超时</Tag> : <Tag color="error">错误</Tag>,
                },
                {
                  title: "地域",
                  dataIndex: "label",
                  key: "label",
                },
                {
                  title: "延迟",
                  dataIndex: "latency_ms",
                  key: "latency_ms",
                  width: 100,
                  render: (ms: number | null, record: RegionPingResult) => {
                    if (record.status !== "ok") return <span style={{ color: "#ff4d4f" }}>{record.error || "-"}</span>;
                    const color = ms !== null && ms < 200 ? "#52c41a" : ms !== null && ms < 500 ? "#faad14" : "#ff4d4f";
                    return <span style={{ color, fontWeight: 600 }}>{formatLatency(ms)}</span>;
                  },
                },
                {
                  title: "操作",
                  key: "action",
                  width: 80,
                  render: (_: unknown, record: RegionPingResult) => (
                    record.status === "ok" ? (
                      <Button size="small" type="link" onClick={() => handleSelectRegion(record.region)}>
                        选择
                      </Button>
                    ) : null
                  ),
                },
              ])}
            />
          </div>
        )}
      </Modal>
    </div>
  );
}

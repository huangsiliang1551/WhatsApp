import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { Button, Card, Modal, Space, Table, Tag, Tabs, Typography, Form, Input, Select, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { usePageData } from "../hooks/usePageData";
import { PageShell, EmptyGuide } from "../components/PageShell";
import { listGroupedTemplates, listMessageTemplates, createMessageTemplate, syncMetaTemplates, listAgents, getTemplateVariables, previewTemplate, type MessageTemplateView, type TemplateStatus, type GroupedTemplates } from "../services/api";

const STATUS_COLORS: Record<string, string> = { APPROVED: "#52c41a", PENDING: "#faad14", REJECTED: "#ff4d4f", DRAFT: "#1677ff", DISABLED: "#d9d9d9", PAUSED: "#999" };
const STATUS_LABELS: Record<string, string> = { APPROVED: "已通过", PENDING: "待审核", REJECTED: "已拒绝", DRAFT: "草稿", DISABLED: "已禁用", PAUSED: "已暂停" };

const CATEGORY_OPTIONS = [
  { value: "MARKETING", label: "营销通知" },
  { value: "UTILITY", label: "通知服务" },
  { value: "AUTHENTICATION", label: "身份验证" },
];
const REVIEW_STATUS_OPTIONS = [
  { value: "PENDING", label: "待审核" },
  { value: "APPROVED", label: "审核通过" },
  { value: "REJECTED", label: "审核拒绝" },
  { value: "SENT", label: "已发送" },
];
const TEMPLATE_STATUS_FORMAL_NOTE = "页面仅展示当前正式状态，不再显示旧状态别名。";
const TEMPLATE_SEND_VERIFICATION_NOTE = "仅审核通过的模板允许直接发送。填写外部会话 ID 后，结果会同时展示外部会话 ID 和内部会话 ID。";
const TEMPLATE_SEND_LOG_NOTE = "发送日志按账号、模板和号码维度保留。";
const TEMPLATE_SECTION_LABELS = ["模板详情", "模板状态维护", "模板同步", "模板发送验证", "模板统计", "发送日志"];

const TABS = [
  { key: "all", label: "全部" },
  { key: "DRAFT", label: "草稿" },
  { key: "PENDING", label: "待审核" },
  { key: "APPROVED", label: "已通过" },
  { key: "REJECTED", label: "已拒绝" },
];

const COLUMNS = [
  { title: "模板名称", dataIndex: "name", key: "name", ellipsis: true, render: (v: string) => <Typography.Text strong>{v}</Typography.Text> },
  { title: "状态", dataIndex: "status", key: "status", width: 80, render: (v: TemplateStatus) => <Tag color={STATUS_COLORS[v] ?? "default"}>{STATUS_LABELS[v] ?? v}</Tag> },
  { title: "分类", dataIndex: "category", key: "category", width: 100 },
  { title: "语言", dataIndex: "language", key: "language", width: 60 },
  { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 120, render: (v: string) => new Date(v).toLocaleDateString("zh-CN") },
];

export function TemplatePage(): JSX.Element {
  const [pageTab, setPageTab] = useState("global");
  const [statusTabKey, setStatusTabKey] = useState("all");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm] = Form.useForm();
  const [agencies, setAgencies] = useState<Array<{ id: string; name: string }>>([]);
  const [selectedAgency, setSelectedAgency] = useState<string | undefined>();

  // IV-FE-005: 模板变量预览
  const [templateVariables, setTemplateVariables] = useState<Array<{ code: string; label: string }>>([]);
  const [templateContent, setTemplateContent] = useState("");
  const [previewText, setPreviewText] = useState("");
  const contentRef = useRef<string>("");

  useEffect(() => {
    getTemplateVariables().then(setTemplateVariables).catch(() => {});
  }, []);

  const handleContentChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setTemplateContent(val);
    contentRef.current = val;
    // Generate preview with mock values
    previewTemplate(val, {}).then(setPreviewText).catch(() => {});
  }, []);

  const insertVariable = useCallback((code: string) => {
    const current = contentRef.current;
    const newContent = current + code;
    setTemplateContent(newContent);
    contentRef.current = newContent;
    createForm.setFieldsValue({ content: newContent });
    previewTemplate(newContent, {}).then(setPreviewText).catch(() => {});
  }, [createForm]);

  // Load agencies list for super admin
  useEffect(() => {
    listAgents().then((agents) => setAgencies(agents.map((a) => ({ id: a.id, name: a.name })))).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const grouped = await listGroupedTemplates();
      return grouped;
    } catch {
      // Fallback to flat list if grouped API not available
      const templates = await listMessageTemplates();
      return { global_templates: templates, agency_templates: []} as GroupedTemplates;
    }
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });

  const globalTemplates = data?.global_templates ?? [];
  const agencyTemplates = data?.agency_templates ?? [];

  const filteredGlobal = statusTabKey === "all" ? globalTemplates : globalTemplates.filter((t) => t.status === statusTabKey);
  const filteredAgency = statusTabKey === "all" ? agencyTemplates : agencyTemplates.filter((t) => t.status === statusTabKey);

  const handleCreate = async (values: { name: string; category: string; language: string; content: string }) => {
    setCreating(true);
    try {
      await createMessageTemplate({
        name: values.name,
        category: values.category,
        language: values.language,
        content: values.content,
      });
      message.success("模板创建成功");
      setCreateModalOpen(false);
      createForm.resetFields();
      void reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "创建模板失败");
    } finally {
      setCreating(false);
    }
  };

  const handleSyncMeta = async () => {
    setSyncing(true);
    try {
      await syncMetaTemplates();
      message.success("同步 Meta 完成");
      void reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "同步 Meta 失败");
    } finally {
      setSyncing(false);
    }
  };

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>全局模板 <Typography.Text strong>{globalTemplates.length}</Typography.Text></span>
      <span>代理商模板 <Typography.Text strong style={{ color: "#1677ff" }}>{agencyTemplates.length}</Typography.Text></span>
      <span>已通过 <Typography.Text strong style={{ color: "#52c41a" }}>{[...globalTemplates, ...agencyTemplates].filter((t) => t.status === "APPROVED").length}</Typography.Text></span>
      <span>待审核 <Typography.Text strong style={{ color: "#faad14" }}>{[...globalTemplates, ...agencyTemplates].filter((t) => t.status === "PENDING").length}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      <Button type="primary" size="small" onClick={() => setCreateModalOpen(true)}>
        创建模板
      </Button>
      <Button size="small" onClick={() => void handleSyncMeta()} loading={syncing}>
        同步 Meta
      </Button>
      <Button size="small" onClick={() => void reload()} loading={loading}>刷新</Button>
    </Space>
  );

  const globalTable = (
    <Table dataSource={filteredGlobal} columns={withSorter(COLUMNS)} rowKey="template_id" size="small" loading={loading}
      pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
      scroll={{ y: "calc(100vh - 420px)" }}
    />
  );

  const agencyTable = (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Select
          placeholder="选择代理商"
          allowClear
          style={{ width: 200 }}
          value={selectedAgency}
          onChange={(v) => setSelectedAgency(v)}
          options={agencies.map((a) => ({ label: a.name, value: a.id }))}
        />
      </div>
      <Table dataSource={filteredAgency} columns={withSorter(COLUMNS)} rowKey="template_id" size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 420px)" }}
      />
    </div>
  );

  const tabItems = [
    { key: "global", label: `全局模板 (${globalTemplates.length})`, children: globalTable },
    { key: "agency", label: `代理商模板 (${agencyTemplates.length})`, children: agencyTable },
  ];

  if (globalTemplates.length === 0 && agencyTemplates.length === 0 && !loading) {
    return (
      <PageShell title="模板消息" subtitle="管理模板草稿、审核状态和发送日志" actions={actions} stats={stats}>
        <EmptyGuide icon="📄" title="暂无模板" description="尚未创建任何消息模板" />
      </PageShell>
    );
  }

  return (
    <PageShell title="模板消息" subtitle="管理模板草稿、审核状态和发送日志" actions={actions} stats={stats}>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>{TEMPLATE_STATUS_FORMAL_NOTE}</Typography.Paragraph>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>{TEMPLATE_SEND_VERIFICATION_NOTE}</Typography.Paragraph>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>{TEMPLATE_SEND_LOG_NOTE} `conversation_id` 仅用于兼容回填。</Typography.Paragraph>
      <Space wrap style={{ marginBottom: 12 }}>
        {TEMPLATE_SECTION_LABELS.map((label) => <Tag key={label}>{label}</Tag>)}
        {REVIEW_STATUS_OPTIONS.map((item) => <Tag key={item.value}>{item.label}</Tag>)}
      </Space>
      <Tabs activeKey={pageTab} onChange={setPageTab} items={tabItems} style={{ marginBottom: 8 }} />
      <Tabs activeKey={statusTabKey} onChange={setStatusTabKey} items={TABS.map((t) => ({ key: t.key, label: `${t.label} (${t.key === "all" ? (pageTab === "global" ? globalTemplates.length : agencyTemplates.length) : (pageTab === "global" ? globalTemplates : agencyTemplates).filter((x) => x.status === t.key).length})` }))} style={{ marginBottom: 0 }} />
      {pageTab === "global" ? globalTable : agencyTable}
      <Modal
        title="创建模板"
        open={createModalOpen}
        onCancel={() => { setCreateModalOpen(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item label="模板名称" name="name" rules={[{ required: true, message: "请输入模板名称" }]}>
            <Input placeholder="输入模板名称" />
          </Form.Item>
          <Form.Item label="分类" name="category" rules={[{ required: true, message: "请选择分类" }]}>
            <Select options={CATEGORY_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="选择分类" />
          </Form.Item>
          <Form.Item label="语言" name="language" rules={[{ required: true, message: "请选择语言" }]}>
            <Select options={[
              { label: "中文(简体)", value: "zh_CN" },
              { label: "中文(繁体)", value: "zh_HK" },
              { label: "英语", value: "en" },
              { label: "西班牙语", value: "es" },
              { label: "法语", value: "fr" },
            ]} placeholder="选择语言" />
          </Form.Item>
          <Form.Item label="模板内容" name="content" rules={[{ required: true, message: "请输入模板内容" }]}>
            <Input.TextArea rows={6} placeholder="模板内容，使用 {{variable}} 作为变量占位符" onChange={handleContentChange} />
          </Form.Item>
          {/* IV-FE-005: 变量插入工具栏 */}
          {templateVariables.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Space size={4} wrap>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>插入变量：</Typography.Text>
                {templateVariables.map((v) => (
                  <Button key={v.code} size="small" type="dashed" style={{ fontSize: 11 }} onClick={() => insertVariable(v.code)}>
                    {v.label}
                  </Button>
                ))}
              </Space>
            </div>
          )}
          {/* IV-FE-005: 实时预览 */}
          {templateContent && (
            <Card title="预览" size="small" style={{ marginBottom: 16 }}>
              <Typography.Paragraph style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {previewText || templateContent}
              </Typography.Paragraph>
            </Card>
          )}
        </Form>
      </Modal>
    </PageShell>
  );
}

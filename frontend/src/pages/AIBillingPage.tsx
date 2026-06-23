import { useState, type JSX } from "react";
import { Alert, Button, Form, InputNumber, Modal, Select, Space, Table, Tag, Tabs, Typography, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { EditOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { showSuccess, showError } from "../components/Feedback";

const MOCK_PROVIDERS = [
  { id: "openai", name: "OpenAI", cost_per_msg: 0.02 },
  { id: "deepseek", name: "DeepSeek", cost_per_msg: 0.005 },
  { id: "translate", name: "翻译服务", cost_per_msg: 0.003 },
];
const MOCK_AGENCIES = [
  { id: "a1", name: "上海锦囊", free_ai: 1000, used_ai: 450, free_translate: 500, used_translate: 200 },
  { id: "a2", name: "深圳启航", free_ai: 1000, used_ai: 1200, free_translate: 500, used_translate: 80 },
];
const MOCK_SITES = [
  { id: "s1", name: "站点A", agent: "上海锦囊", ai_msgs: 560, translate_count: 120, ai_cost: 11.2, translate_cost: 0.36, total: 11.56 },
  { id: "s2", name: "站点B", agent: "深圳启航", ai_msgs: 1300, translate_count: 80, ai_cost: 6.5, translate_cost: 0.24, total: 6.74 },
];
const MOCK_BILLS = [
  { id: "b1", agent: "上海锦囊", month: "2026-06", ai_cost: 11.2, translate_cost: 0.36, total: 11.56, status: "pending" },
  { id: "b2", agent: "深圳启航", month: "2026-06", ai_cost: 6.5, translate_cost: 0.24, total: 6.74, status: "settled" },
];

export function AIBillingPage({ embedded }: { embedded?: boolean } = {}): JSX.Element {
  const [rateModalOpen, setRateModalOpen] = useState(false);
  const [rateTarget, setRateTarget] = useState<{ id: string; name: string; cost_per_msg: number } | null>(null);
  const [rateForm] = Form.useForm();
  const [editQuotaOpen, setEditQuotaOpen] = useState(false);
  const [quotaTarget, setQuotaTarget] = useState<typeof MOCK_AGENCIES[0] | null>(null);
  const [quotaForm] = Form.useForm();

  const rateColumns = [
    { title: "Provider", dataIndex: "name", key: "name" },
    { title: "每条消息费用(¥)", dataIndex: "cost_per_msg", key: "cost_per_msg", render: (v: number) => `¥${v.toFixed(4)}` },
    { title: "操作", key: "actions", width: 100, render: (_: unknown, r: typeof MOCK_PROVIDERS[0]) => (
      <Button size="small" icon={<EditOutlined />} onClick={() => { setRateTarget(r); rateForm.setFieldsValue({ cost: r.cost_per_msg }); setRateModalOpen(true); }}>编辑</Button>
    )},
  ];

  const quotaColumns = [
    { title: "代理商", dataIndex: "name", key: "name" },
    { title: "免费AI消息数", dataIndex: "free_ai", key: "free_ai" },
    { title: "已使用", dataIndex: "used_ai", key: "used_ai", render: (v: number, r: typeof MOCK_AGENCIES[0]) => (
      <Tag color={v > r.free_ai ? "red" : "green"}>{v}</Tag>
    )},
    { title: "免费翻译次数", dataIndex: "free_translate", key: "free_translate" },
    { title: "已使用", dataIndex: "used_translate", key: "used_translate", render: (v: number, r: typeof MOCK_AGENCIES[0]) => (
      <Tag color={v > r.free_translate ? "red" : "green"}>{v}</Tag>
    )},
    { title: "操作", key: "actions", width: 100, render: (_: unknown, r: typeof MOCK_AGENCIES[0]) => (
      <Button size="small" icon={<EditOutlined />} onClick={() => { setQuotaTarget(r); quotaForm.setFieldsValue({ free_ai: r.free_ai, free_translate: r.free_translate }); setEditQuotaOpen(true); }}>编辑</Button>
    )},
  ];

  const statsColumns = [
    { title: "代理商", dataIndex: "agent", key: "agent" },
    { title: "站点", dataIndex: "name", key: "name" },
    { title: "AI消息数", dataIndex: "ai_msgs", key: "ai_msgs" },
    { title: "翻译次数", dataIndex: "translate_count", key: "translate_count" },
    { title: "AI费用", dataIndex: "ai_cost", key: "ai_cost", render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "翻译费用", dataIndex: "translate_cost", key: "translate_cost", render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "总费用", dataIndex: "total", key: "total", render: (v: number) => <Typography.Text strong>¥{v.toFixed(2)}</Typography.Text> },
  ];

  const billColumns = [
    { title: "代理商", dataIndex: "agent", key: "agent" },
    { title: "月份", dataIndex: "month", key: "month" },
    { title: "AI费用", dataIndex: "ai_cost", key: "ai_cost", render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "翻译费用", dataIndex: "translate_cost", key: "translate_cost", render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "总费用", dataIndex: "total", key: "total", render: (v: number) => <Typography.Text strong>¥{v.toFixed(2)}</Typography.Text> },
    { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={s === "settled" ? "green" : "orange"}>{s === "settled" ? "已结算" : "待结算"}</Tag> },
    { title: "操作", key: "actions", width: 100, render: () => <Button size="small">查看明细</Button> },
  ];

  const content = (
    <Tabs items={[
      { key: "rates", label: "费率设置", children: (
        <>
          <Alert message="设置每个 AI 提供商的单条消息费用。AI 回复客户时，系统会根据这里的费率计算成本，最终算到代理商头上。" type="info" showIcon style={{ marginBottom: 16 }} />
          <Table rowKey="id" dataSource={MOCK_PROVIDERS} columns={withSorter(rateColumns)} pagination={false} />
          <Modal title="编辑费率" open={rateModalOpen} onCancel={() => setRateModalOpen(false)} onOk={() => { rateForm.submit(); }} okText="保存">
            <Form form={rateForm} layout="vertical" onFinish={(v) => { showSuccess("费率已更新"); setRateModalOpen(false); }}>
              <Form.Item label={`${rateTarget?.name} - 每条消息费用(¥)`} name="cost" rules={[{ required: true }]}><InputNumber min={0} step={0.001} style={{ width: 200 }} /></Form.Item>
            </Form>
          </Modal>
        </>
      )},
      { key: "quota", label: "免费额度", children: (
        <>
          <Alert message="给每个代理商设置每月的免费额度。在免费额度内不收费，超过后按费率计费，但不会限制使用。" type="info" showIcon style={{ marginBottom: 16 }} />
          <Table rowKey="id" dataSource={MOCK_AGENCIES} columns={withSorter(quotaColumns)} pagination={false} />
          <Modal title="编辑免费额度" open={editQuotaOpen} onCancel={() => setEditQuotaOpen(false)} onOk={() => { quotaForm.submit(); }} okText="保存">
            <Form form={quotaForm} layout="vertical" onFinish={(v) => { showSuccess("免费额度已更新"); setEditQuotaOpen(false); }}>
              <Form.Item label="免费AI消息数" name="free_ai" rules={[{ required: true }]}><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
              <Form.Item label="免费翻译次数" name="free_translate" rules={[{ required: true }]}><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
            </Form>
          </Modal>
        </>
      )},
      { key: "stats", label: "用量统计", children: (
        <>
          <Alert message="查看各代理商、各站点的 AI 和翻译用量。可以按月、按代理商、按站点筛选。" type="info" showIcon style={{ marginBottom: 16 }} />
          <Space style={{ marginBottom: 16 }}>
            <Select placeholder="月份" style={{ width: 120 }} options={[{ label: "2026-06", value: "2026-06" }]} />
            <Select placeholder="代理商" style={{ width: 160 }} allowClear options={MOCK_AGENCIES.map(a => ({ label: a.name, value: a.id }))} />
            <Select placeholder="站点" style={{ width: 160 }} allowClear options={MOCK_SITES.map(s => ({ label: s.name, value: s.id }))} />
          </Space>
          <Space style={{ marginBottom: 16 }}>
            <Card small><Statistic title="本月AI消息总数" value={1860} /></Card>
            <Card small><Statistic title="翻译总次数" value={200} /></Card>
            <Card small><Statistic title="总费用" value={18.3} precision={2} prefix="¥" /></Card>
            <Card small><Statistic title="超额代理商数" value={1} valueStyle={{ color: "#cf1322" }} /></Card>
          </Space>
          <Table rowKey="id" dataSource={MOCK_SITES} columns={withSorter(statsColumns)} pagination={false} />
        </>
      )},
      { key: "bills", label: "月度账单", children: (
        <>
          <Alert message="每月 1 号系统自动生成上月账单。这里可以查看所有代理商的账单明细。" type="info" showIcon style={{ marginBottom: 16 }} />
          <Table rowKey="id" dataSource={MOCK_BILLS} columns={withSorter(billColumns)} pagination={false} />
        </>
      )},
    ]} />
  );

  if (embedded) return <>{content}</>;
  return (
    <PageShell title="AI & 翻译费用管理" subtitle="管理 AI 提供商费率和代理商免费额度">
      {content}
    </PageShell>
  );
}

function Card({ small, children, ...props }: any) {
  return (
    <div style={{ background: "#fafafa", borderRadius: 8, padding: "12px 20px", minWidth: 160, textAlign: "center" }} {...props}>
      {children}
    </div>
  );
}
function Statistic({ title, value, precision, prefix, valueStyle }: any) {
  const fmt = precision != null ? Number(value).toFixed(precision) : value;
  return <div><div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>{title}</div><div style={{ fontSize: 24, fontWeight: 600, ...(valueStyle || {}) }}>{prefix}{fmt}</div></div>;
}

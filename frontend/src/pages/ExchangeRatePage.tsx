import { useState, type JSX } from "react";
import { Alert, Button, Form, InputNumber, Modal, Space, Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { EditOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { showSuccess, showError } from "../components/Feedback";

const MOCK_RATES = [
  { id: "1", from: "CNY", to: "USDT", rate: 7.25, updated_at: "2026-06-11T10:00:00Z" },
  { id: "2", from: "CNY", to: "BTC", rate: 498000, updated_at: "2026-06-11T10:00:00Z" },
  { id: "3", from: "USDT", to: "CNY", rate: 0.138, updated_at: "2026-06-11T10:00:00Z" },
];

export function ExchangeRatePage({ embedded }: { embedded?: boolean } = {}): JSX.Element {
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<typeof MOCK_RATES[0] | null>(null);
  const [form] = Form.useForm();

  const columns = [
    { title: "源币种", dataIndex: "from", key: "from", render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: "目标币种", dataIndex: "to", key: "to", render: (v: string) => <Tag color="green">{v}</Tag> },
    { title: "汇率", dataIndex: "rate", key: "rate", render: (v: number) => v.toLocaleString() },
    { title: "更新时间", dataIndex: "updated_at", key: "updated_at", render: (d: string) => new Date(d).toLocaleString("zh-CN") },
    { title: "操作", key: "actions", width: 100, render: (_: unknown, r: typeof MOCK_RATES[0]) => (
      <Button size="small" icon={<EditOutlined />} onClick={() => { setEditTarget(r); form.setFieldsValue({ rate: r.rate }); setEditOpen(true); }}>编辑</Button>
    )},
  ];

  if (embedded) return <><Alert message="设置不同币种之间的转换汇率。每个站点有自己的币种，会员充值其他币种时会自动按这里的汇率转换。" type="info" showIcon style={{ marginBottom: 16 }} />
      <Table rowKey="id" dataSource={MOCK_RATES} columns={withSorter(columns)} pagination={false} />
      <Modal title="编辑汇率" open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => form.submit()} okText="保存">
        <Form form={form} layout="vertical" onFinish={(v) => { showSuccess("汇率已更新"); setEditOpen(false); }}>
          <Form.Item label={`${editTarget?.from} → ${editTarget?.to} 汇率`} name="rate" rules={[{ required: true }]}>
            <InputNumber min={0} step={0.0001} style={{ width: 200 }} />
          </Form.Item>
        </Form>
      </Modal></>;
  return (
    <PageShell title="汇率管理" subtitle="管理不同币种之间的转换汇率">
      <Alert message="设置不同币种之间的转换汇率。每个站点有自己的币种，会员充值其他币种时会自动按这里的汇率转换。" type="info" showIcon style={{ marginBottom: 16 }} />
      <Table rowKey="id" dataSource={MOCK_RATES} columns={withSorter(columns)} pagination={false} />
      <Modal title="编辑汇率" open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => form.submit()} okText="保存">
        <Form form={form} layout="vertical" onFinish={(v) => { showSuccess("汇率已更新"); setEditOpen(false); }}>
          <Form.Item label={`${editTarget?.from} → ${editTarget?.to} 汇率`} name="rate" rules={[{ required: true }]}>
            <InputNumber min={0} step={0.0001} style={{ width: 200 }} />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}

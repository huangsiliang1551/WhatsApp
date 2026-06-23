import { useState, type JSX } from "react";
import { Alert, Button, Drawer, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag, Typography, DatePicker, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { EditOutlined, ReloadOutlined, HeartOutlined, AuditOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { showSuccess, showError } from "../components/Feedback";

const MOCK_CHANNELS = [
  { id: "c1", name: "USDT-TRC20", type: "usdt", status: "active", sandbox: false, today_tx: 156, success_rate: 98.5 },
  { id: "c2", name: "银行转账", type: "local_bank", status: "active", sandbox: true, today_tx: 42, success_rate: 100 },
  { id: "c3", name: "支付宝", type: "custom", status: "maintenance", sandbox: false, today_tx: 0, success_rate: 0 },
];

export function PaymentChannelPage({ embedded }: { embedded?: boolean } = {}): JSX.Element {
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<any>(null);
  const [form] = Form.useForm();
  const [healthOpen, setHealthOpen] = useState(false);
  const [healthTarget, setHealthTarget] = useState<any>(null);
  const [reconOpen, setReconOpen] = useState(false);
  const [reconTarget, setReconTarget] = useState<any>(null);
  const [reconResult, setReconResult] = useState<{ date: string; matched: number; diff: number; unmatched: Array<{ id: string; desc: string; amount: number; status: string }> } | null>(null);

  const statusMap: Record<string, { label: string; color: string }> = { active: { label: "启用", color: "green" }, inactive: { label: "停用", color: "default" }, maintenance: { label: "维护中", color: "orange" } };
  const typeMap: Record<string, string> = { usdt: "USDT", local_bank: "银行转账", custom: "自定义" };

  const columns = [
    { title: "渠道名称", dataIndex: "name", key: "name" },
    { title: "类型", dataIndex: "type", key: "type", render: (v: string) => typeMap[v] || v },
    { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label || s}</Tag> },
    { title: "沙箱", key: "sandbox", render: (_: unknown, r: any) => r.sandbox ? <Tag color="orange">沙箱</Tag> : <Tag>正式</Tag> },
    { title: "今日交易", dataIndex: "today_tx", key: "today_tx" },
    { title: "成功率", dataIndex: "success_rate", key: "success_rate", render: (v: number) => `${v}%` },
    { title: "操作", key: "actions", width: 220, render: (_: unknown, r: any) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => { setEditTarget(r); form.setFieldsValue(r); setEditOpen(true); }}>编辑</Button>
        <Button size="small" icon={<HeartOutlined />} onClick={() => { setHealthTarget(r); setHealthOpen(true); }}>健康</Button>
        <Button size="small" icon={<AuditOutlined />} onClick={() => { setReconTarget(r); setReconResult(null); setReconOpen(true); }}>对账</Button>
      </Space>
    )},
  ];

  const healthColumns = [
    { title: "指标", dataIndex: "metric", key: "metric" },
    { title: "值", dataIndex: "value", key: "value" },
  ];
  const healthData = healthTarget ? [
    { metric: "成功率", value: `${healthTarget.success_rate}%` },
    { metric: "平均响应时间", value: "1.2s" },
    { metric: "今日交易量", value: healthTarget.today_tx },
  ] : [];

  const pageContent = (<>
      <Alert message="配置支付渠道（如 USDT、银行转账等）。密钥会加密存储。代理商不能修改渠道配置，但可以决定自己的 H5 页面上显示哪些渠道。" type="info" showIcon style={{ marginBottom: 16 }} />
      <Button type="primary" style={{ marginBottom: 12 }} onClick={() => { setEditTarget(null); form.resetFields(); setEditOpen(true); }}>新增渠道</Button>
      <Table rowKey="id" dataSource={MOCK_CHANNELS} columns={withSorter(columns)} pagination={false} />

      <Modal title={editTarget ? "编辑渠道" : "新增渠道"} open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => form.submit()} confirmLoading={false} width={600} okText="保存">
        <Form form={form} layout="vertical" onFinish={(v) => { showSuccess("渠道已保存"); setEditOpen(false); }}>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="类型" name="type" rules={[{ required: true }]}><Select options={[{ label: "USDT", value: "usdt" }, { label: "银行转账", value: "local_bank" }, { label: "自定义", value: "custom" }]} /></Form.Item>
          <Form.Item label="AppID" name="app_id"><Input /></Form.Item>
          <Form.Item label="密钥" name="secret"><Input.Password /></Form.Item>
          <Form.Item label="回调地址" name="callback_url"><Input /></Form.Item>
          <Form.Item label="回调签名密钥" name="sign_key"><Input.Password /></Form.Item>
          <Form.Item label="费率(%)" name="fee_rate"><InputNumber min={0} max={100} step={0.01} style={{ width: 200 }} /></Form.Item>
          <Form.Item label="最低金额" name="min_amount"><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
          <Form.Item label="最高金额" name="max_amount"><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
          <Form.Item label="沙箱模式" name="sandbox" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>

      <Drawer title={`${healthTarget?.name || ""} 渠道健康`} open={healthOpen} onClose={() => setHealthOpen(false)} width={400}>
        <Table dataSource={healthData} columns={withSorter(healthColumns)} pagination={false} />
      </Drawer>

      <Modal title={`${reconTarget?.name || ""} 对账`} open={reconOpen} onCancel={() => setReconOpen(false)} footer={null}>
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <DatePicker />
          <Button icon={<ReloadOutlined />} onClick={() => setReconResult({ date: "2026-06-11", matched: 145, diff: 3, unmatched: [{ id: "u1", desc: "金额差异 - 订单 T20260611001", amount: 0.5, status: "unprocessed" }]})}>触发对账</Button>
          {reconResult && (
            <>
              <Space>
                <Tag color="success">匹配: {reconResult.matched} 笔</Tag>
                <Tag color="error">差异: {reconResult.diff} 笔</Tag>
              </Space>
              <Table rowKey="id" dataSource={reconResult.unmatched} columns={withSorter([
                { title: "说明", dataIndex: "desc", key: "desc" },
                { title: "金额", dataIndex: "amount", key: "amount" },
                { title: "操作", key: "actions", render: (_: unknown, r: any) => r.status === "unprocessed" ? <Button size="small" onClick={() => { showSuccess("已标记处理"); }}>标记已处理</Button> : <Tag color="green">已处理</Tag> },
              ])} pagination={false} />
            </>
          )}
        </Space>
      </Modal>
    </>);

  if (embedded) return pageContent;
  return (
    <PageShell title="支付渠道管理" subtitle="配置支付渠道和密钥">
      {pageContent}
    </PageShell>
  );
}

import { type JSX } from "react";
import { Alert, Form, InputNumber, Switch, Table, Tabs, Tag, Button } from "antd";
import { withSorter } from "../../utils/withSorter";
import { PageShell } from "../../components/PageShell";
import { showSuccess } from "../../components/Feedback";

const MOCK_CHANNELS = [
  { id: "c1", name: "USDT-TRC20", deposit: true, withdraw: true, merchant_id: "" },
  { id: "c2", name: "银行转账", deposit: true, withdraw: false, merchant_id: "MCH001" },
];

export function AgentFinanceSettingsPage(): JSX.Element {
  return (
    <PageShell title="财务设置" subtitle="管理支付渠道和提现规则">
      <Tabs items={[
        { key: "channels", label: "支付渠道", children: (
          <>
            <Alert message="选择您的 H5 页面上显示哪些支付渠道。平台已配置好渠道，您只需要决定启用哪些。修改后 H5 充值页面会实时同步。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Table rowKey="id" dataSource={MOCK_CHANNELS} columns={[
              { title: "渠道名称", dataIndex: "name", key: "name" },
              { title: "充值", dataIndex: "deposit", key: "deposit", render: (v: boolean) => <Switch checked={v} onChange={() => showSuccess("已更新")} /> },
              { title: "提现", dataIndex: "withdraw", key: "withdraw", render: (v: boolean) => <Switch checked={v} onChange={() => showSuccess("已更新")} /> },
              { title: "自定义商户号", dataIndex: "merchant_id", key: "merchant_id", render: (v: string) => v || <Tag>未设置</Tag> },
            ]} pagination={false} />
          </>
        )},
        { key: "withdraw", label: "提现设置", children: (
          <>
            <Alert message="设置提现规则。您可以设置小额自动审批（比如 100 元以下自动通过），大额需要人工审核。也可以设置全部人工审核。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Form layout="vertical" style={{ maxWidth: 480 }} onFinish={() => showSuccess("提现设置已保存")}>
              <Form.Item label="小额自动审批金额(¥)" name="auto_approve_limit" initialValue={100}><InputNumber min={0} style={{ width: 200 }} addonAfter="留空=全部人工" /></Form.Item>
              <Form.Item label="单笔最低提现(¥)" name="min_withdraw" initialValue={10}><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
              <Form.Item label="每日最高提现(¥)" name="daily_max" initialValue={5000}><InputNumber min={0} style={{ width: 200 }} /></Form.Item>
              <Form.Item label="收取手续费" valuePropName="checked"><Switch /> <Form.Item name="fee_percent" initialValue={1} style={{ display: "inline-block", marginLeft: 8 }}><InputNumber min={0} max={100} style={{ width: 80 }} /> %</Form.Item></Form.Item>
              <Form.Item label="启用冻结机制" valuePropName="checked" name="enable_freeze"><Switch /></Form.Item>
              <Form.Item label="冻结触发次数" name="freeze_threshold" initialValue={3}><InputNumber min={1} style={{ width: 200 }} addonAfter="24小时内提现超过N次触发冻结" /></Form.Item>
              <Button type="primary" htmlType="submit">保存设置</Button>
            </Form>
          </>
        )},
      ]} />
    </PageShell>
  );
}

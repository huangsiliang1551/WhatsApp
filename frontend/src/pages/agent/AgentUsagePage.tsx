import { type JSX } from "react";
import { Alert, Space, Table, Tag, Typography } from "antd";
import { withSorter } from "../../utils/withSorter";
import { PageShell } from "../../components/PageShell";

const MOCK_USAGE = [
  { site: "站点A", ai_msgs: 450, translate_count: 200, cost: 6.3 },
  { site: "站点B", ai_msgs: 120, translate_count: 50, cost: 1.8 },
];
const MOCK_BILLS = [
  { month: "2026-05", ai_cost: 5.2, translate_cost: 0.6, total: 5.8, status: "settled" },
  { month: "2026-06", ai_cost: 8.1, translate_cost: 0.75, total: 8.85, status: "pending" },
];

export function AgentUsagePage(): JSX.Element {
  return (
    <PageShell title="用量查看" subtitle="AI 和翻译服务使用情况">
      <Alert message="以下是您本月 AI 和翻译服务的使用情况。在免费额度内不收费。" type="info" showIcon style={{ marginBottom: 16 }} />
      <Space style={{ marginBottom: 16 }}>
        <StatCard title="本月AI消息数" value="570" />
        <StatCard title="翻译次数" value="250" />
        <StatCard title="费用(¥)" value="8.85" />
        <StatCard title="免费额度剩余" value="430 AI / 250 翻译" color="#52c41a" />
      </Space>
      <Typography.Title level={5} style={{ marginTop: 24 }}>按站点明细</Typography.Title>
      <Table rowKey="site" dataSource={MOCK_USAGE} columns={[
        { title: "站点", dataIndex: "site", key: "site" },
        { title: "AI消息数", dataIndex: "ai_msgs", key: "ai_msgs" },
        { title: "翻译次数", dataIndex: "translate_count", key: "translate_count" },
        { title: "费用(¥)", dataIndex: "cost", key: "cost", render: (v: number) => `¥${v.toFixed(2)}` },
      ]} pagination={false} />
      <Typography.Title level={5} style={{ marginTop: 24 }}>月度账单历史</Typography.Title>
      <Table rowKey="month" dataSource={MOCK_BILLS} columns={[
        { title: "月份", dataIndex: "month", key: "month" },
        { title: "AI费用", dataIndex: "ai_cost", key: "ai_cost", render: (v: number) => `¥${v.toFixed(2)}` },
        { title: "翻译费用", dataIndex: "translate_cost", key: "translate_cost", render: (v: number) => `¥${v.toFixed(2)}` },
        { title: "总费用", dataIndex: "total", key: "total", render: (v: number) => <Typography.Text strong>¥{v.toFixed(2)}</Typography.Text> },
        { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={s === "settled" ? "green" : "orange"}>{s === "settled" ? "已结算" : "待结算"}</Tag> },
      ]} pagination={false} />
    </PageShell>
  );
}

function StatCard({ title, value, color }: { title: string; value: string; color?: string }) {
  return <div style={{ background: "#fafafa", borderRadius: 8, padding: "12px 20px", minWidth: 160, textAlign: "center" }}><div style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 4 }}>{title}</div><div style={{ fontSize: 22, fontWeight: 600, color: color || "#000" }}>{value}</div></div>;
}

import { useMemo, useState } from "react";
import { Select, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { MetaWebhookSubscriptionView } from "../../services/api";
import { whColor, whLabel, whSubColor, whSubLabel, shortTs } from "./utils";

interface WebhookListTabProps {
  subscriptions: MetaWebhookSubscriptionView[];
  focusedAccountId: string;
}

export function WebhookListTab({ subscriptions, focusedAccountId }: WebhookListTabProps) {
  const [filterStatus, setFilterStatus] = useState<string>("");

  const filtered = useMemo(() => {
    let result = subscriptions;
    if (focusedAccountId) {
      result = result.filter((s) => s.account_id === focusedAccountId);
    }
    if (filterStatus) {
      result = result.filter((s) => s.status === filterStatus);
    }
    return result;
  }, [subscriptions, focusedAccountId, filterStatus]);

  const columns: ColumnsType<MetaWebhookSubscriptionView> = [
    { title: "账户", dataIndex: "account_display_name", width: 100, ellipsis: true },
    { title: "WABA", dataIndex: "waba_id", width: 110, ellipsis: true, render: (v: string) => <span style={{ fontSize: 11, fontFamily: "monospace", color: "#888" }}>{v}</span> },
    {
      title: "回调地址", dataIndex: "callback_url", width: 200, ellipsis: true,
      render: (v: string) => <Typography.Text copyable style={{ fontSize: 11 }}>{v}</Typography.Text>,
    },
    {
      title: "订阅状态", dataIndex: "status", width: 90,
      render: (v: string) => <Tag color={whSubColor(v)} style={{ fontSize: 10, margin: 0 }}>{whSubLabel(v)}</Tag>,
    },
    {
      title: "运行状态", key: "runtime", width: 80,
      render: (_: unknown, r: MetaWebhookSubscriptionView) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: whColor(r.webhook_runtime_status), flexShrink: 0 }} />
          <span style={{ color: "#666" }}>{whLabel(r.webhook_runtime_status)}</span>
        </span>
      ),
    },
    { title: "订阅时间", dataIndex: "subscribed_at", width: 90, render: (v: string | null) => <span style={{ fontSize: 11, color: "#aaa" }}>{shortTs(v)}</span> },
    { title: "最后事件", dataIndex: "webhook_last_event_received_at", width: 90, render: (v: string | null) => <span style={{ fontSize: 11, color: "#aaa" }}>{shortTs(v)}</span> },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "0 0 8px", flexShrink: 0, display: "flex", gap: 8, alignItems: "center" }}>
        <Select size="small" allowClear placeholder="订阅状态" value={filterStatus || undefined} onChange={setFilterStatus} style={{ width: 120 }}
          options={["pending","mock_subscribed","remote_subscribed","remote_pending","subscribed"].map((v) => ({ label: v, value: v }))} />
        <span style={{ fontSize: 11, color: "#999" }}>共 {filtered.length} 条</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Table<MetaWebhookSubscriptionView>
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={filtered}
          pagination={false}
          scroll={{ y: "100%" }}
        />
      </div>
    </div>
  );
}

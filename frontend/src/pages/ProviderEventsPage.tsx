import { useCallback, type JSX } from "react";
import { Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { usePageData } from "../hooks/usePageData";
import { PageShell, EmptyGuide } from "../components/PageShell";
import { listProviderStatusBuffer } from "../services/api";

export function ProviderEventsPage(): JSX.Element {
  const fetchData = useCallback(async () => {
    const result = await listProviderStatusBuffer({ replay_state: "pending", limit: 50 });
    return result;
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const items = data?.items ?? [];

  const stats = data ? (
    <span style={{ fontSize: 13 }}>
      积压 <Typography.Text strong style={{ color: "#faad14" }}>{data.pending_count}</Typography.Text>
      {" | "}已回放 <Typography.Text strong>{data.replayed_count}</Typography.Text>
      {" | "}总数 <Typography.Text strong>{data.returned_count}</Typography.Text>
    </span>
  ) : null;

  if (!data && !loading) {
    return (
      <PageShell title="Provider 事件" subtitle="消息 provider 状态回放和事件记录" stats={stats}>
        <EmptyGuide icon="📡" title="暂无 Provider 事件" description="尚无 provider 事件记录" />
      </PageShell>
    );
  }

  const columns = [
    { title: "Provider", dataIndex: "provider_name", key: "provider_name", width: 100 },
    { title: "状态", dataIndex: "external_status", key: "external_status", width: 100 },
    { title: "回放状态", dataIndex: "replay_state", key: "replay_state", width: 80, render: (v: string) => <Tag color={v === "pending" ? "warning" : "success"}>{v}</Tag> },
    { title: "WABA ID", dataIndex: "waba_id", key: "waba_id", width: 120, ellipsis: true },
    { title: "号码 ID", dataIndex: "phone_number_id", key: "phone_number_id", width: 120, ellipsis: true },
    { title: "消息 ID", dataIndex: "provider_message_id", key: "provider_message_id", width: 160, ellipsis: true },
    { title: "错误码", dataIndex: "error_code", key: "error_code", width: 80 },
    { title: "首次发现", dataIndex: "first_seen_at", key: "first_seen_at", width: 140, render: (v: string) => new Date(v).toLocaleString("zh-CN") },
    { title: "最后发现", dataIndex: "last_seen_at", key: "last_seen_at", width: 140, render: (v: string) => new Date(v).toLocaleString("zh-CN") },
  ];

  return (
    <PageShell
      title="Provider 事件"
      subtitle="消息 provider 状态回放和事件记录"
      stats={stats}
      actions={<a onClick={() => void reload()} style={{ fontSize: 12, color: "#1677ff", cursor: "pointer" }}>{loading ? "刷新中..." : "刷新"}</a>}
    >
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}
      <Table dataSource={items} columns={withSorter(columns)} rowKey={(r) => r.id} size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 320px)" }}
      />
    </PageShell>
  );
}

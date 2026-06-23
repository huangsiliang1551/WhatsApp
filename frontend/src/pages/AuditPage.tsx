import { useCallback, type JSX } from "react";
import { Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { usePageData } from "../hooks/usePageData";
import { PageShell, EmptyGuide } from "../components/PageShell";
import { getSystemLogSnapshot } from "../services/adminCenter";

const SEV_COLORS: Record<string, string> = { critical: "#ff4d4f", warning: "#faad14", info: "#1677ff" };

export function AuditPage(): JSX.Element {
  const fetchData = useCallback(async () => {
    const snapshot = await getSystemLogSnapshot();
    return snapshot;
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const entries = data?.entries ?? [];

  const stats = data ? (
    <span style={{ fontSize: 13 }}>
      审计条目 <Typography.Text strong>{data.audit_count}</Typography.Text>
      {" | "}Provider 积压 <Typography.Text strong style={{ color: "#faad14" }}>{data.provider_pending_count}</Typography.Text>
      {" | "}失败任务 <Typography.Text strong style={{ color: "#ff4d4f" }}>{data.failed_job_count}</Typography.Text>
    </span>
  ) : null;

  if (!data && !loading) {
    return (
      <PageShell title="审计日志" subtitle="系统操作审计、Provider 回放和队列异常记录" stats={stats}>
        <EmptyGuide icon="📋" title="暂无审计日志" description="尚无审计记录" />
      </PageShell>
    );
  }

  const columns = [
    { title: "严重程度", dataIndex: "severity", key: "severity", width: 80, render: (v: string) => <Tag color={SEV_COLORS[v] ?? "default"}>{v}</Tag> },
    { title: "来源", dataIndex: "source_kind", key: "source_kind", width: 70 },
    { title: "标题", dataIndex: "title", key: "title", width: 200, ellipsis: true },
    { title: "摘要", dataIndex: "summary", key: "summary", width: 250, ellipsis: true },
    { title: "详情", dataIndex: "detail", key: "detail", width: 250, ellipsis: true },
    { title: "发生时间", dataIndex: "occurred_at", key: "occurred_at", width: 140, render: (v: string) => new Date(v).toLocaleString("zh-CN") },
  ];

  return (
    <PageShell
      title="审计日志"
      subtitle="系统操作审计、Provider 回放和队列异常记录"
      stats={stats}
      actions={<a onClick={() => void reload()} style={{ fontSize: 12, color: "#1677ff", cursor: "pointer" }}>{loading ? "刷新中..." : "刷新"}</a>}
    >
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}
      <Table dataSource={entries} columns={withSorter(columns)} rowKey={(r) => r.id} size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 320px)" }}
      />
    </PageShell>
  );
}

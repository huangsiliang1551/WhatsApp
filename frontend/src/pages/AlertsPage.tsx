import { useCallback, type JSX } from "react";
import { Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { usePageData } from "../hooks/usePageData";
import { PageShell, EmptyGuide } from "../components/PageShell";
import { getAlertCenterSnapshot } from "../services/operations";

const SEV_COLORS: Record<string, string> = { critical: "#ff4d4f", warning: "#faad14", info: "#1677ff" };

export function AlertsPage(): JSX.Element {
  const fetchData = useCallback(async () => {
    const snapshot = await getAlertCenterSnapshot();
    return snapshot;
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const items = data?.items ?? [];

  const healthLabel: Record<string, { color: string; label: string }> = {
    healthy: { color: "#52c41a", label: "健康" },
    warning: { color: "#faad14", label: "需关注" },
    critical: { color: "#ff4d4f", label: "严重" },
  };
  const health = data?.service_health ? healthLabel[data.service_health] : null;

  const stats = data ? (
    <span style={{ fontSize: 13 }}>
      队列积压 <Typography.Text strong>{data.queue_backlog}</Typography.Text>
      {" | "}失败任务 <Typography.Text strong style={{ color: "#ff4d4f" }}>{data.failed_jobs}</Typography.Text>
      {" | "}Provider 积压 <Typography.Text strong style={{ color: "#faad14" }}>{data.provider_pending}</Typography.Text>
      {" | "}告警总数 <Typography.Text strong>{items.length}</Typography.Text>
    </span>
  ) : null;

  if (!data && !loading) {
    return (
      <PageShell title="告警中心" subtitle="系统告警、队列积压和运行异常" stats={stats}>
        <EmptyGuide icon="🔔" title="暂无告警" description="系统运行正常，无需关注" />
      </PageShell>
    );
  }

  const columns = [
    { title: "严重程度", dataIndex: "severity", key: "severity", width: 80, render: (v: string) => <Tag color={SEV_COLORS[v] ?? "default"}>{v}</Tag> },
    { title: "标题", dataIndex: "title", key: "title", width: 200, ellipsis: true },
    { title: "摘要", dataIndex: "summary", key: "summary", width: 300, ellipsis: true },
    { title: "分类", dataIndex: "category", key: "category", width: 80 },
    { title: "来源", dataIndex: "source", key: "source", width: 60 },
    { title: "发生时间", dataIndex: "occurred_at", key: "occurred_at", width: 140, render: (v: string) => new Date(v).toLocaleString("zh-CN") },
  ];

  return (
    <PageShell
      title="告警中心"
      subtitle="系统告警、队列积压和运行异常"
      stats={stats}
      actions={<a onClick={() => void reload()} style={{ fontSize: 12, color: "#1677ff", cursor: "pointer" }}>{loading ? "刷新中..." : "刷新"}</a>}
    >
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}
      {health && <Tag color={health.color} style={{ marginBottom: 12 }}>服务健康: {health.label}</Tag>}
      <Table dataSource={items} columns={withSorter(columns)} rowKey={(r) => r.id} size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 320px)" }}
      />
    </PageShell>
  );
}

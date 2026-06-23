import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Statistic, Table, Tag, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getRiskCenterSnapshot } from "../services/operations";
import { withSorter } from "../utils/withSorter";

const PROFILE_STATUS_COLORS: Record<string, string> = {
  allow: "success",
  blocklist: "error",
  watchlist: "warning",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function RiskCenterPage(): JSX.Element {
  const fetchData = useCallback(async () => getRiskCenterSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const profiles = data?.profiles ?? [];
  const cases = data?.cases ?? [];

  if (!data && !loading) {
    return (
      <PageShell subtitle="风险画像、风险案例与风控概览" title="风险中心">
        <EmptyGuide description="当前无法读取风险中心数据。" icon="⚠️" title="暂无风险数据" />
      </PageShell>
    );
  }

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      }
      subtitle="风险画像、风险案例与风控概览"
      title="风险中心"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={8}><Card size="small"><Statistic title="风险画像" value={profiles.length} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="观察名单" value={profiles.filter((item) => item.status === "watchlist").length} valueStyle={{ color: "#faad14" }} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="风险案例" value={cases.length} /></Card></Col>
      </Row>

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        风险画像
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "名称", dataIndex: "display_name", key: "display_name", width: 140 },
          { title: "类型", dataIndex: "target_type", key: "target_type", width: 100 },
          { title: "目标值", dataIndex: "target_value", ellipsis: true, key: "target_value", width: 180 },
          {
            title: "状态",
            dataIndex: "status",
            key: "status",
            render: (value: string) => <Tag color={PROFILE_STATUS_COLORS[value] ?? "default"}>{value}</Tag>,
            width: 100,
          },
          { title: "原因", dataIndex: "reason", ellipsis: true, key: "reason" },
          { title: "7日命中", dataIndex: "hit_count_7d", key: "hit_count_7d", width: 90 },
          { title: "最近命中", dataIndex: "last_hit_at", key: "last_hit_at", render: (value: string | null) => formatDateTime(value), width: 180 },
        ])}
        dataSource={profiles}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        rowKey="id"
        scroll={{ y: 260 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        风险案例
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "ID", dataIndex: "id", ellipsis: true, key: "id", width: 160 },
          { title: "分类", dataIndex: "category", key: "category", render: (value: string) => <Tag>{value}</Tag>, width: 120 },
          { title: "目标值", dataIndex: "target_value", ellipsis: true, key: "target_value", width: 180 },
          { title: "摘要", dataIndex: "summary", ellipsis: true, key: "summary" },
          {
            title: "状态",
            dataIndex: "status",
            key: "status",
            render: (value: string) => (
              <Tag color={value === "open" ? "error" : value === "reviewing" ? "warning" : "success"}>
                {value}
              </Tag>
            ),
            width: 100,
          },
          {
            title: "严重程度",
            dataIndex: "severity",
            key: "severity",
            render: (value: string) => (
              <Tag color={value === "high" ? "error" : value === "medium" ? "warning" : "default"}>
                {value}
              </Tag>
            ),
            width: 110,
          },
          { title: "创建时间", dataIndex: "created_at", key: "created_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={cases}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        rowKey="id"
        scroll={{ y: 260 }}
        size="small"
      />
    </PageShell>
  );
}

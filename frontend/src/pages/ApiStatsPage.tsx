import { ApiOutlined, ClockCircleOutlined, TeamOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Card, Col, Row, Space, Statistic, Table, Typography, type TableColumnsType } from "antd";
import { useCallback, type JSX } from "react";

import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getApiStatsByAgency,
  getApiStatsByEndpoint,
  getApiStatsSummary,
  type ApiStatsByAgency,
  type ApiStatsByEndpoint,
  type ApiStatsSummary,
} from "../services/api";

export function ApiStatsPage(): JSX.Element {
  const fetcher = useCallback(async () => {
    const [summary, byAgency, byEndpoint] = await Promise.all([
      getApiStatsSummary(),
      getApiStatsByAgency(),
      getApiStatsByEndpoint(),
    ]);
    return { summary, byAgency, byEndpoint };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher });
  const summary: ApiStatsSummary | null = data?.summary ?? null;
  const byAgency: ApiStatsByAgency[] = data?.byAgency ?? [];
  const byEndpoint: ApiStatsByEndpoint[] = data?.byEndpoint ?? [];

  const agencyColumns: TableColumnsType<ApiStatsByAgency> = [
    {
      title: "代理商",
      dataIndex: "agency_name",
      key: "agency_name",
      render: (value: string | null) => value || "全局",
    },
    {
      title: "调用次数",
      dataIndex: "count",
      key: "count",
      sorter: (left, right) => left.count - right.count,
    },
    {
      title: "平均响应 (ms)",
      dataIndex: "avg_ms",
      key: "avg_ms",
      render: (value: number) => `${value.toFixed(1)} ms`,
      sorter: (left, right) => left.avg_ms - right.avg_ms,
    },
    {
      title: "峰值",
      dataIndex: "peak_count",
      key: "peak_count",
      sorter: (left, right) => left.peak_count - right.peak_count,
    },
  ];

  const endpointColumns: TableColumnsType<ApiStatsByEndpoint> = [
    {
      title: "端点",
      dataIndex: "endpoint",
      key: "endpoint",
      ellipsis: true,
    },
    {
      title: "调用次数",
      dataIndex: "count",
      key: "count",
      sorter: (left, right) => left.count - right.count,
    },
    {
      title: "平均响应 (ms)",
      dataIndex: "avg_ms",
      key: "avg_ms",
      render: (value: number) => `${value.toFixed(1)} ms`,
      sorter: (left, right) => left.avg_ms - right.avg_ms,
    },
  ];

  return (
    <PageShell
      actions={
        <Space>
          <Button loading={loading} onClick={() => void reload()} size="small">
            刷新
          </Button>
        </Space>
      }
      subtitle="查看 API 调用量与响应表现"
      title="API 调用统计"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col lg={6} md={12} xs={24}>
          <Card size="small">
            <Statistic prefix={<ApiOutlined />} title="今日总调用" value={summary?.today_count ?? 0} />
          </Card>
        </Col>
        <Col lg={6} md={12} xs={24}>
          <Card size="small">
            <Statistic prefix={<ClockCircleOutlined />} suffix="ms" title="平均响应时间" value={summary?.avg_ms ?? 0} />
          </Card>
        </Col>
        <Col lg={6} md={12} xs={24}>
          <Card size="small">
            <Statistic prefix={<TeamOutlined />} title="活跃代理商" value={summary?.active_agencies ?? 0} />
          </Card>
        </Col>
        <Col lg={6} md={12} xs={24}>
          <Card size="small">
            <Statistic
              prefix={<WarningOutlined />}
              title="被限流次数"
              value={summary?.rate_limited ?? 0}
              valueStyle={{ color: (summary?.rate_limited ?? 0) > 0 ? "#ff4d4f" : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }} title="按代理商统计">
        <Table
          columns={agencyColumns}
          dataSource={byAgency}
          loading={loading}
          pagination={false}
          rowKey={(record) => record.agency_name || "global"}
          scroll={{ y: 300 }}
          size="small"
        />
      </Card>

      <Card size="small" title="按端点统计">
        <Table
          columns={endpointColumns}
          dataSource={byEndpoint}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          rowKey="endpoint"
          scroll={{ y: 300 }}
          size="small"
        />
      </Card>
    </PageShell>
  );
}

export default ApiStatsPage;

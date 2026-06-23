import { Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd";
import { useCallback, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getImportExportCenterSnapshot } from "../services/operations";
import type { KnowledgeCategorySummary, KnowledgeEntrySummary } from "../types/operations";
import { withSorter } from "../utils/withSorter";

export function ImportExportPage(): JSX.Element {
  const fetchData = useCallback(async () => getImportExportCenterSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  if (!data && !loading) {
    return (
      <PageShell subtitle="知识库导入导出与分类概览" title="导入导出">
        <EmptyGuide description="当前无法读取知识库导入导出数据。" icon="📚" title="暂无数据" />
      </PageShell>
    );
  }

  const categoryColumns = withSorter<KnowledgeCategorySummary>([
    { title: "分类", dataIndex: "category", key: "category", width: 180 },
    { title: "总数", dataIndex: "total_count", key: "total_count", width: 100 },
    { title: "活跃", dataIndex: "active_count", key: "active_count", width: 100 },
    { title: "内置", dataIndex: "builtin_count", key: "builtin_count", width: 100 },
    { title: "数据库", dataIndex: "database_count", key: "database_count", width: 100 },
  ]);

  const entryColumns = withSorter<KnowledgeEntrySummary>([
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      width: 240,
      ellipsis: true,
      render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      width: 140,
    },
    {
      title: "路由",
      dataIndex: "route_name",
      key: "route_name",
      width: 140,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "语言",
      dataIndex: "source_language",
      key: "source_language",
      width: 100,
    },
    {
      title: "来源",
      dataIndex: "source_type",
      key: "source_type",
      width: 110,
      render: (value: string) => <Tag color={value === "builtin" ? "blue" : "gold"}>{value}</Tag>,
    },
    {
      title: "关键词",
      dataIndex: "keywords",
      key: "keywords",
      ellipsis: true,
      render: (value: string[]) => (value.length ? value.join(", ") : "-"),
    },
    {
      title: "活跃",
      dataIndex: "is_active",
      key: "is_active",
      width: 90,
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "yes" : "no"}</Tag>,
    },
  ]);

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      }
      stats={
        <Space size={16} wrap>
          <Typography.Text>
            总条目 <Typography.Text strong>{data?.total_entries ?? 0}</Typography.Text>
          </Typography.Text>
          <Typography.Text>
            活跃 <Typography.Text strong style={{ color: "#52c41a" }}>{data?.active_entries ?? 0}</Typography.Text>
          </Typography.Text>
          <Typography.Text>
            内置 <Typography.Text strong>{data?.builtin_entries ?? 0}</Typography.Text>
          </Typography.Text>
          <Typography.Text>
            数据库 <Typography.Text strong style={{ color: "#1677ff" }}>{data?.database_entries ?? 0}</Typography.Text>
          </Typography.Text>
        </Space>
      }
      subtitle="知识库导入导出与分类概览"
      title="导入导出"
    >
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? (
          <Typography.Text style={{ display: "block" }} type="danger">
            {error}
          </Typography.Text>
        ) : null}

        <Row gutter={[12, 12]}>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="总条目" value={data?.total_entries ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="活跃条目" value={data?.active_entries ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="内置条目" value={data?.builtin_entries ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="数据库条目" value={data?.database_entries ?? 0} />
            </Card>
          </Col>
        </Row>

        <Card bodyStyle={{ padding: 0 }} size="small" title="分类概览">
          <Table
            columns={categoryColumns}
            dataSource={data?.categories ?? []}
            loading={loading}
            pagination={false}
            rowKey="category"
            scroll={{ x: 620 }}
            size="small"
          />
        </Card>

        <Card bodyStyle={{ padding: 0 }} size="small" title="知识库条目">
          <Table
            columns={entryColumns}
            dataSource={data?.entries ?? []}
            loading={loading}
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
            rowKey="article_id"
            scroll={{ x: 1080, y: "calc(100vh - 420px)" }}
            size="small"
          />
        </Card>
      </Space>
    </PageShell>
  );
}

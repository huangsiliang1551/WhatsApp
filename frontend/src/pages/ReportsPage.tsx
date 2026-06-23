import { Button, Card, Col, Row, Select, Space, Statistic, Table, Tabs, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getFinanceReport, getWhatsAppStatsSummary } from "../services/api";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import { getReportCenterSnapshot } from "../services/operations";
import type { ReportCenterDailyRow } from "../types/operations";
import { withSorter } from "../utils/withSorter";

function WhatsAppStatsTab(): JSX.Element {
  const [sites, setSites] = useState<H5Site[]>([]);
  const [siteFilter, setSiteFilter] = useState<string | undefined>();

  useEffect(() => {
    listSites().then(setSites).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    return getWhatsAppStatsSummary(siteFilter ? { account_id: siteFilter } : undefined);
  }, [siteFilter]);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData, deps: [siteFilter] });

  if (!data && !loading) {
    return (
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
        <EmptyGuide description="WhatsApp 统计数据暂不可用。" icon="📊" title="暂无统计数据" />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space style={{ justifyContent: "flex-end", width: "100%" }} wrap>
        <Select
          allowClear
          onChange={(value) => setSiteFilter(value)}
          options={sites.map((site) => ({ label: site.brand_name || site.site_key, value: site.site_key }))}
          placeholder="H5 站点"
          style={{ width: 160 }}
          value={siteFilter}
        />
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      </Space>

      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="入站消息" value={data?.inbound_message_count ?? 0} valueStyle={{ color: "#1677ff" }} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="出站消息" value={data?.outbound_message_count ?? 0} valueStyle={{ color: "#52c41a" }} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="已送达" value={data?.delivered_count ?? 0} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="已读" value={data?.read_count ?? 0} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="失败" value={data?.failed_count ?? 0} valueStyle={{ color: (data?.failed_count ?? 0) > 0 ? "#ff4d4f" : undefined }} /></Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="会话数" value={data?.conversation_count ?? 0} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="独立客户" value={data?.unique_customer_count ?? 0} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="计费消息" value={data?.billable_count ?? 0} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic title="预计费用" value={data ? `$${data.estimated_cost.toFixed(2)}` : "$0.00"} /></Card>
        </Col>
      </Row>
    </Space>
  );
}

function OperationsReportTab(): JSX.Element {
  const fetchData = useCallback(async () => getReportCenterSnapshot(), []);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });

  if (!data && !loading) {
    return (
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
        <EmptyGuide description="运营报表数据暂不可用。" icon="📈" title="暂无运营报表" />
      </Space>
    );
  }

  const columns = withSorter<ReportCenterDailyRow>([
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 120,
      sorter: (left: ReportCenterDailyRow, right: ReportCenterDailyRow) => (left.date ?? "").localeCompare(right.date ?? ""),
      defaultSortOrder: "descend",
    },
    {
      title: "来源",
      dataIndex: "source_kind",
      key: "source_kind",
      width: 100,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "标识",
      dataIndex: "label",
      key: "label",
      width: 180,
      ellipsis: true,
    },
    { title: "入站", dataIndex: "inbound_count", key: "inbound_count", width: 90 },
    { title: "出站", dataIndex: "outbound_count", key: "outbound_count", width: 90 },
    { title: "送达", dataIndex: "delivered_count", key: "delivered_count", width: 90 },
    { title: "已读", dataIndex: "read_count", key: "read_count", width: 90 },
    {
      title: "失败",
      dataIndex: "failed_count",
      key: "failed_count",
      width: 90,
      render: (value: number) => (value > 0 ? <Typography.Text type="danger">{value}</Typography.Text> : value),
    },
    {
      title: "成本",
      dataIndex: "estimated_cost",
      key: "estimated_cost",
      width: 100,
      render: (value: number) => `$${value.toFixed(2)}`,
    },
  ]);

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space style={{ justifyContent: "flex-end", width: "100%" }}>
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      </Space>

      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}

      <Row gutter={[12, 12]}>
        {(data?.kpis ?? []).map((kpi) => (
          <Col key={kpi.key} lg={4} md={8} sm={12} xs={24}>
            <Card size="small">
              <Statistic title={kpi.label} value={kpi.value} />
            </Card>
          </Col>
        ))}
      </Row>

      <Card bodyStyle={{ padding: 0 }} size="small" title="日报明细">
        <Table
          columns={columns}
          dataSource={data?.daily_rows ?? []}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          rowKey={(record) => `${record.date}-${record.label}`}
          scroll={{ x: 980, y: "calc(100vh - 400px)" }}
          size="small"
        />
      </Card>
    </Space>
  );
}

const FINANCE_PERIODS = [
  { value: "daily", label: "每日" },
  { value: "weekly", label: "每周" },
  { value: "monthly", label: "每月" },
];

function FinanceReportTab(): JSX.Element {
  const [period, setPeriod] = useState<string>("monthly");

  const fetchData = useCallback(async () => getFinanceReport(period), [period]);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchData, deps: [period] });

  if (!data && !loading) {
    return (
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
        <EmptyGuide description="财务报表数据暂不可用。" icon="💰" title="暂无财务报表" />
      </Space>
    );
  }

  const detailColumns = withSorter<NonNullable<typeof data>["details"][number]>([
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 120,
      sorter: (left: NonNullable<typeof data>["details"][number], right: NonNullable<typeof data>["details"][number]) =>
        (left.date ?? "").localeCompare(right.date ?? ""),
      defaultSortOrder: "descend",
    },
    {
      title: "类型",
      dataIndex: "type",
      key: "type",
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "金额",
      dataIndex: "amount",
      key: "amount",
      width: 120,
      render: (value: number) => <Typography.Text strong>¥{value.toFixed(2)}</Typography.Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => {
        const colorMap: Record<string, string> = {
          paid: "success",
          pending: "warning",
          canceled: "default",
          failed: "error",
        };
        return <Tag color={colorMap[value] ?? "default"}>{value}</Tag>;
      },
    },
  ]);

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space style={{ justifyContent: "flex-end", width: "100%" }} wrap>
        <Select onChange={(value) => setPeriod(value)} options={FINANCE_PERIODS} style={{ width: 120 }} value={period} />
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      </Space>

      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="总收入" value={data?.total_revenue ?? 0} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="总账单" value={data?.total_billing ?? 0} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="已付账单" value={data?.paid_billing ?? 0} valueStyle={{ color: "#52c41a" }} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="待付账单" value={data?.pending_billing ?? 0} valueStyle={{ color: "#faad14" }} /></Card>
        </Col>
        <Col lg={4} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="充值金额" value={data?.recharge_amount ?? 0} valueStyle={{ color: "#1677ff" }} /></Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="提现金额" value={data?.withdraw_amount ?? 0} /></Card>
        </Col>
        <Col lg={6} md={8} sm={12} xs={24}>
          <Card size="small"><Statistic precision={2} prefix="¥" title="佣金" value={data?.commission ?? 0} valueStyle={{ color: "#722ed1" }} /></Card>
        </Col>
      </Row>

      <Card bodyStyle={{ padding: 0 }} size="small" title="财务明细">
        <Table
          columns={detailColumns}
          dataSource={data?.details ?? []}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          rowKey={(record, index) => `${record.date}-${record.type}-${index}`}
          scroll={{ x: 860, y: "calc(100vh - 450px)" }}
          size="small"
        />
      </Card>
    </Space>
  );
}

export function ReportsPage(): JSX.Element {
  const tabItems = useMemo(
    () => [
      { key: "whatsapp", label: "WhatsApp 统计", children: <WhatsAppStatsTab /> },
      { key: "operations", label: "运营报表", children: <OperationsReportTab /> },
      { key: "finance", label: "财务报表", children: <FinanceReportTab /> },
    ],
    []
  );

  return (
    <PageShell subtitle="消息统计、运营指标与财务明细" title="报表中心">
      <div style={{ overflowY: "auto", height: "100%" }}>
        <Tabs items={tabItems} />
      </div>
    </PageShell>
  );
}

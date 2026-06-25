import { Alert, Button, Card, Col, Descriptions, Row, Select, Space, Statistic, Table, Tabs, Tag, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import { getWhatsAppStatsSummary } from "../services/api";
import { getFinanceSummary } from "../services/financeApi";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import { getReportCenterSnapshot } from "../services/operations";
import { fetchOwnershipReport, type OwnershipReport } from "../services/ownershipReports";
import { useAppStore } from "../stores/appStore";
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
        <EmptyGuide description="WhatsApp 统计数据暂不可用。" icon="📳" title="暂无统计数据" />
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
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="入站消息" value={data?.inbound_message_count ?? 0} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="出站消息" value={data?.outbound_message_count ?? 0} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic title="已送达" value={data?.delivered_count ?? 0} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic title="已读" value={data?.read_count ?? 0} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic title="失败" value={data?.failed_count ?? 0} valueStyle={{ color: (data?.failed_count ?? 0) > 0 ? "#ff4d4f" : undefined }} /></Card></Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="会话数" value={data?.conversation_count ?? 0} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="独立客户" value={data?.unique_customer_count ?? 0} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="计费消息" value={data?.billable_count ?? 0} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="预估费用" value={data ? `$${data.estimated_cost.toFixed(2)}` : "$0.00"} /></Card></Col>
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
        <EmptyGuide description="运营报表数据暂不可用。" icon="📫" title="暂无运营报表" />
      </Space>
    );
  }

  const columns = withSorter<ReportCenterDailyRow>([
    { title: "日期", dataIndex: "date", key: "date", width: 120, sorter: (left: ReportCenterDailyRow, right: ReportCenterDailyRow) => (left.date ?? "").localeCompare(right.date ?? ""), defaultSortOrder: "descend" },
    { title: "来源", dataIndex: "source_kind", key: "source_kind", width: 100, render: (value: string) => <Tag>{value}</Tag> },
    { title: "标识", dataIndex: "label", key: "label", width: 180, ellipsis: true },
    { title: "入站", dataIndex: "inbound_count", key: "inbound_count", width: 90 },
    { title: "出站", dataIndex: "outbound_count", key: "outbound_count", width: 90 },
    { title: "送达", dataIndex: "delivered_count", key: "delivered_count", width: 90 },
    { title: "已读", dataIndex: "read_count", key: "read_count", width: 90 },
    { title: "失败", dataIndex: "failed_count", key: "failed_count", width: 90, render: (value: number) => (value > 0 ? <Typography.Text type="danger">{value}</Typography.Text> : value) },
    { title: "成本", dataIndex: "estimated_cost", key: "estimated_cost", width: 100, render: (value: number) => `$${value.toFixed(2)}` },
  ]);

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space style={{ justifyContent: "flex-end", width: "100%" }}>
        <Button loading={loading} onClick={() => void reload()} size="small">刷新</Button>
      </Space>
      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
      <Row gutter={[12, 12]}>
        {(data?.kpis ?? []).map((kpi) => (
          <Col key={kpi.key} lg={4} md={8} sm={12} xs={24}>
            <Card size="small"><Statistic title={kpi.label} value={kpi.value} /></Card>
          </Col>
        ))}
      </Row>
      <Card size="small" title="日报明细">
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

function FinanceReportTab(): JSX.Element {
  const setActivePage = useAppStore((state) => state.setActivePage);
  const { canSeePage } = usePermissions();
  const canOpenFinancePage = canSeePage("finance");
  const fetchData = useCallback(async () => getFinanceSummary(), []);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });

  if (!data && !loading) {
    return (
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
        <EmptyGuide description="财务摘要暂不可用。" icon="💼" title="暂无财务摘要" />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space style={{ justifyContent: "flex-end", width: "100%" }} wrap>
        <Button loading={loading} onClick={() => void reload()} size="small">刷新</Button>
        {canOpenFinancePage ? (
          <Button onClick={() => setActivePage("finance")} type="primary">进入财务工作台</Button>
        ) : null}
      </Space>

      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}

      <Alert
        description="这里只保留核心摘要，明细查询、导出和风控排查请进入统一财务工作台。"
        message="财务报表已收口到统一财务工作台"
        showIcon
        type="info"
      />

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic precision={2} prefix="$" title="充值金额" value={data?.recharge_amount ?? 0} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic precision={2} prefix="$" title="赠金金额" value={data?.bonus_amount ?? 0} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic precision={2} prefix="$" title="提现金额" value={data?.withdrawal_amount ?? 0} valueStyle={{ color: "#cf1322" }} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic precision={2} prefix="$" title="提现手续费" value={data?.withdrawal_fee ?? 0} /></Card></Col>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic precision={2} prefix="$" title="净充值" value={data?.net_recharge ?? 0} valueStyle={{ color: "#1677ff" }} /></Card></Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="充值次数" value={data?.recharge_count ?? 0} /></Card></Col>
        <Col lg={6} md={8} sm={12} xs={24}><Card size="small"><Statistic title="提现笔数" value={data?.withdrawal_count ?? 0} valueStyle={{ color: "#722ed1" }} /></Card></Col>
      </Row>
    </Space>
  );
}

function OwnershipReportTab(): JSX.Element {
  const [accountId, setAccountId] = useState<string | undefined>(undefined);
  const fetchData = useCallback(() => fetchOwnershipReport(accountId ? { account_id: accountId } : undefined), [accountId]);
  const { data, loading, error } = usePageData<OwnershipReport>({ fetcher: fetchData, deps: [accountId] });

  if (loading && !data) {
    return <EmptyGuide description="正在加载归属报表" icon="📮" title="加载中" />;
  }
  if (error) {
    return <Typography.Text type="danger">归属报表加载失败：{error}</Typography.Text>;
  }
  if (!data) {
    return <EmptyGuide description="暂无归属报表数据" icon="📮" title="暂无数据" />;
  }

  return (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Space>
        <Select allowClear placeholder="按 account_id 筛选" style={{ minWidth: 240 }} onChange={(value) => setAccountId(value)} />
        <Typography.Text type="secondary">当前页展示的是归属与 EntryLink 运营快照。</Typography.Text>
      </Space>

      <Row gutter={16}>
        <Col span={6}><Card size="small" title="未归属会员"><Statistic value={data.current.owner.unattributed} suffix="人" /></Card></Col>
        <Col span={6}><Card size="small" title="无 AI 会员"><Statistic value={data.current.ai.no_ai_assignment} suffix="人" /></Card></Col>
        <Col span={6}><Card size="small" title="AI 自动消息"><Statistic value={data.ai_reception.ai_message_count} suffix="条" /></Card></Col>
        <Col span={6}><Card size="small" title="AI failover 事件"><Statistic value={data.ai_reception.failover_event_count} suffix="次" /></Card></Col>
      </Row>

      <Card size="small" title="当前归属分布">
        <Row gutter={16}>
          <Col span={12}>
            <Typography.Title level={5}>客服归属</Typography.Title>
            <Table size="small" dataSource={data.current.owner.by_owner} rowKey={(row) => String(row.owner_staff_user_id ?? "null")} columns={[{ title: "客服", dataIndex: "owner_staff_user_id" }, { title: "会员数", dataIndex: "member_count" }]} pagination={false} />
          </Col>
          <Col span={12}>
            <Typography.Title level={5}>AI 归属</Typography.Title>
            <Table size="small" dataSource={data.current.ai.by_ai_agent} rowKey={(row) => String(row.ai_agent_id ?? "null")} columns={[{ title: "AI Agent", dataIndex: "ai_agent_id" }, { title: "会员数", dataIndex: "member_count" }]} pagination={false} />
          </Col>
        </Row>
      </Card>

      <Card size="small" title="EntryLink 转化">
        <Table
          size="small"
          dataSource={data.entry_links}
          rowKey="entry_link_id"
          columns={[
            { title: "Code", dataIndex: "code", width: 110 },
            { title: "类型", dataIndex: "link_type", width: 140 },
            { title: "状态", dataIndex: "status", width: 100, render: (value: string) => <Tag>{value}</Tag> },
            { title: "使用", dataIndex: "usage_count", width: 80 },
            { title: "注册", dataIndex: "members_registered", width: 80 },
            { title: "AI 绑定", dataIndex: "ai_assigned", width: 80 },
            { title: "会话", dataIndex: "conversations", width: 80 },
            { title: "AI 消息", dataIndex: "ai_messages", width: 80 },
          ]}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Card size="small" title="异常">
        <Descriptions
          size="small"
          column={2}
          items={[
            { key: "no_owner", label: "无客服归属会员", children: data.anomalies.no_owner_member_count },
            { key: "no_ai", label: "无 AI 会员", children: data.anomalies.no_ai_member_count },
            { key: "bad_link", label: "EntryLink 指向已停用 AI", children: data.anomalies.entry_link_pointing_disabled_ai },
            { key: "no_fallback", label: "AI 无 fallback staff", children: data.anomalies.ai_without_fallback_staff },
          ]}
        />
        {data.anomalies.no_owner_member_count > 0 ||
        data.anomalies.no_ai_member_count > 0 ||
        data.anomalies.entry_link_pointing_disabled_ai > 0 ||
        data.anomalies.ai_without_fallback_staff > 0 ? (
          <Alert style={{ marginTop: 12 }} type="warning" showIcon message="存在异常项，请到 EntryLinks / AIAgents / Members 继续排查。" />
        ) : null}
      </Card>
    </Space>
  );
}

export function ReportsPage(): JSX.Element {
  const { can } = usePermissions();
  const canViewFinanceReports = can("reports.finance");
  const tabItems = useMemo(
    () => [
      { key: "whatsapp", label: "WhatsApp 统计", children: <WhatsAppStatsTab /> },
      { key: "operations", label: "运营报表", children: <OperationsReportTab /> },
      { key: "ownership", label: "归属报表", children: <OwnershipReportTab /> },
      ...(canViewFinanceReports ? [{ key: "finance", label: "财务报表", children: <FinanceReportTab /> }] : []),
    ],
    [canViewFinanceReports],
  );

  return (
    <PageShell subtitle="消息统计、运营指标与财务明细" title="报表中心">
      <div style={{ overflowY: "auto", height: "100%" }}>
        <Tabs items={tabItems} />
      </div>
    </PageShell>
  );
}

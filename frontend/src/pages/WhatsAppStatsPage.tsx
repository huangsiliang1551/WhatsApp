import { useCallback, useEffect, useState, type JSX } from "react";
import { Button, Card, Col, Row, Select, Space, Statistic, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getWhatsAppStatsSummary } from "../services/api";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";

export function WhatsAppStatsPage(): JSX.Element {
  const [sites, setSites] = useState<H5Site[]>([]);
  const [siteFilter, setSiteFilter] = useState<string | undefined>();

  useEffect(() => {
    listSites().then(setSites).catch(() => {
      setSites([]);
    });
  }, []);

  const fetchData = useCallback(async () => getWhatsAppStatsSummary(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  if (!data) {
    if (loading) {
      return (
        <PageShell subtitle="WhatsApp 消息发送与接收统计" title="WhatsApp 统计">
          <Typography.Text>加载中...</Typography.Text>
        </PageShell>
      );
    }

    return (
      <PageShell subtitle="WhatsApp 消息发送与接收统计" title="WhatsApp 统计">
        <EmptyGuide description="当前没有可展示的 WhatsApp 统计数据。" icon="📫" title="暂无统计数据" />
      </PageShell>
    );
  }

  return (
    <PageShell
      actions={
        <Space>
          <Select
            allowClear
            onChange={(value) => setSiteFilter(value)}
            options={sites.map((site) => ({
              label: site.brand_name || site.site_key,
              value: site.site_key,
            }))}
            placeholder="H5 站点"
            style={{ width: 160 }}
            value={siteFilter}
          />
          <Button loading={loading} onClick={() => void reload()} size="small">
            刷新
          </Button>
        </Space>
      }
      subtitle="WhatsApp 消息发送与接收统计"
      title="WhatsApp 统计"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[12, 12]}>
        <Col span={6}><Card size="small"><Statistic title="入站消息" value={data.inbound_message_count} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="出站消息" value={data.outbound_message_count} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已送达" value={data.delivered_count} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="已读" value={data.read_count} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="失败" value={data.failed_count} valueStyle={{ color: data.failed_count > 0 ? "#ff4d4f" : undefined }} /></Card></Col>
      </Row>

      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        <Col span={6}><Card size="small"><Statistic title="会话数" value={data.conversation_count} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="独立客户" value={data.unique_customer_count} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="计费消息" value={data.billable_count} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic prefix="$" title="预估费用" value={data.estimated_cost} precision={2} /></Card></Col>
      </Row>
    </PageShell>
  );
}

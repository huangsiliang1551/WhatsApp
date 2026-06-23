import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Badge, Button, Card, Col, Row, Space, Statistic, Tag, Typography, message } from "antd";

import { useDashboardData } from "../hooks/useDashboardData";
import { useHealth } from "../hooks/useHealth";
import { useAppStore } from "../stores/appStore";
import { getHealthCheckSummary, runHealthCheck, type HealthCheckSummary } from "../services/api";

type DailyTrend = {
  day: string;
  replyRate: number;
  fallbackRate: number;
  handoverRate: number;
};

type IntentStat = {
  name: string;
  count: number;
  pct: number;
};

const MOCK_TRENDS: DailyTrend[] = [
  { day: "周一", fallbackRate: 8, handoverRate: 5, replyRate: 92 },
  { day: "周二", fallbackRate: 12, handoverRate: 7, replyRate: 88 },
  { day: "周三", fallbackRate: 5, handoverRate: 3, replyRate: 95 },
  { day: "周四", fallbackRate: 15, handoverRate: 9, replyRate: 85 },
  { day: "周五", fallbackRate: 10, handoverRate: 6, replyRate: 90 },
  { day: "周六", fallbackRate: 22, handoverRate: 11, replyRate: 78 },
  { day: "周日", fallbackRate: 18, handoverRate: 8, replyRate: 82 },
];

const MOCK_INTENTS: IntentStat[] = [
  { count: 45, name: "订单查询", pct: 32 },
  { count: 38, name: "物流跟踪", pct: 27 },
  { count: 25, name: "退款咨询", pct: 18 },
  { count: 15, name: "商品咨询", pct: 11 },
  { count: 8, name: "投诉建议", pct: 6 },
  { count: 5, name: "账户问题", pct: 4 },
  { count: 4, name: "活动优惠", pct: 3 },
  { count: 3, name: "发票需求", pct: 2 },
];

function HealthStatusBadge({ label, status }: { label: string; status?: string | null }): JSX.Element {
  const color = status === "healthy" ? "success" : status === "warning" ? "warning" : status ? "error" : "default";
  const text = status === "healthy" ? "正常" : status === "warning" ? "警告" : status ? "异常" : "-";

  return (
    <Col lg={4} md={8} sm={12} xs={24}>
      <Card size="small">
        <Space direction="vertical" size={4} style={{ width: "100%" }}>
          <Space size={8}>
            <Badge status={color as "success" | "warning" | "error" | "default"} />
            <Typography.Text strong>{label}</Typography.Text>
          </Space>
          <Typography.Text type="secondary">{text}</Typography.Text>
        </Space>
      </Card>
    </Col>
  );
}

function TrendChart({ trends }: { trends: DailyTrend[] }): JSX.Element {
  const maxRate = 100;

  return (
    <div>
      <Space size={16} style={{ fontSize: 12, marginBottom: 12 }} wrap>
        <span><span style={{ background: "#52c41a", borderRadius: 2, display: "inline-block", height: 12, marginRight: 4, width: 12 }} /> 回复率</span>
        <span><span style={{ background: "#faad14", borderRadius: 2, display: "inline-block", height: 12, marginRight: 4, width: 12 }} /> 降级率</span>
        <span><span style={{ background: "#1677ff", borderRadius: 2, display: "inline-block", height: 12, marginRight: 4, width: 12 }} /> 转人工率</span>
      </Space>
      <div style={{ alignItems: "flex-end", display: "flex", gap: 12, height: 160, padding: "0 8px" }}>
        {trends.map((trend) => {
          const replyHeight = (trend.replyRate / maxRate) * 140;
          const fallbackHeight = (trend.fallbackRate / maxRate) * 140;
          const handoverHeight = (trend.handoverRate / maxRate) * 140;

          return (
            <div key={trend.day} style={{ alignItems: "center", display: "flex", flex: 1, flexDirection: "column", gap: 4 }}>
              <div style={{ alignItems: "flex-end", display: "flex", gap: 3, height: 140 }}>
                <div style={{ background: "#52c41a", borderRadius: "2px 2px 0 0", height: Math.max(replyHeight, 2), width: 14 }} />
                <div style={{ background: "#faad14", borderRadius: "2px 2px 0 0", height: Math.max(fallbackHeight, 2), width: 14 }} />
                <div style={{ background: "#1677ff", borderRadius: "2px 2px 0 0", height: Math.max(handoverHeight, 2), width: 14 }} />
              </div>
              <Typography.Text style={{ fontSize: 10 }} type="secondary">
                {trend.day}
              </Typography.Text>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IntentRanking({ intents }: { intents: IntentStat[] }): JSX.Element {
  const maxCount = intents[0]?.count ?? 1;

  return (
    <Space direction="vertical" size={8} style={{ width: "100%" }}>
      {intents.map((item, index) => (
        <div key={item.name} style={{ alignItems: "center", display: "flex", gap: 8 }}>
          <Typography.Text strong style={{ minWidth: 18 }}>
            {index + 1}
          </Typography.Text>
          <Typography.Text ellipsis style={{ flex: "0 0 96px" }}>
            {item.name}
          </Typography.Text>
          <div style={{ background: "#f0f0f0", borderRadius: 7, flex: 1, height: 14, overflow: "hidden" }}>
            <div
              style={{
                background: index === 0 ? "#52c41a" : index === 1 ? "#1677ff" : index === 2 ? "#faad14" : "#d9d9d9",
                borderRadius: 7,
                height: "100%",
                width: `${(item.count / maxCount) * 100}%`,
              }}
            />
          </div>
          <Typography.Text style={{ minWidth: 44, textAlign: "right" }}>{item.count}</Typography.Text>
          <Typography.Text style={{ minWidth: 44, textAlign: "right" }} type="secondary">
            {item.pct}%
          </Typography.Text>
        </div>
      ))}
    </Space>
  );
}

export function DashboardPage(): JSX.Element {
  const health = useHealth();
  const { data, error, loading, reload, stats, accounts } = useDashboardData();
  const setActivePage = useAppStore((state) => state.setActivePage);
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);

  const aiProvider = data?.launchReadiness?.summary.ai_provider ?? "未配置";
  const aiGlobalOn = data?.runtimeState?.global_ai_enabled ?? false;
  const metaReady = data?.launchReadiness?.summary.meta_ready_account_count ?? 0;
  const totalMessages = (data?.whatsAppSummary?.inbound_message_count ?? 0) + (data?.whatsAppSummary?.outbound_message_count ?? 0);
  const aiSuccess = data?.metrics?.ai.success_total ?? 0;
  const aiFallback = data?.metrics?.ai.fallback_total ?? 0;
  const aiSuccessPct = aiSuccess + aiFallback > 0 ? Math.round((aiSuccess / (aiSuccess + aiFallback)) * 100) : 0;

  const [healthSummary, setHealthSummary] = useState<HealthCheckSummary | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const fetchHealthSummary = useCallback(async () => {
    try {
      setHealthSummary(await getHealthCheckSummary());
    } catch {
      setHealthSummary(null);
    }
  }, []);

  useEffect(() => {
    void fetchHealthSummary();
  }, [fetchHealthSummary]);

  const handleRunCheck = useCallback(async () => {
    setHealthLoading(true);
    try {
      const results = await runHealthCheck();
      const summary: HealthCheckSummary = {
        api: "healthy",
        db: "healthy",
        last_check_at: new Date().toISOString(),
        redis: "healthy",
        sites: "healthy",
        ssl: "healthy",
      };

      results.forEach((item) => {
        if (item.check_type === "db") summary.db = item.status;
        if (item.check_type === "redis") summary.redis = item.status;
        if (item.check_type === "api") summary.api = item.status;
        if (item.check_type === "sites") summary.sites = item.status;
        if (item.check_type === "ssl") summary.ssl = item.status;
      });

      setHealthSummary(summary);
      message.success("健康检查完成");
    } catch (runError) {
      message.error(runError instanceof Error ? runError.message : "健康检查失败");
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const blockerCount = data?.launchReadiness?.summary.blocker_count ?? 0;
  const warningCount = data?.launchReadiness?.summary.warning_count ?? 0;

  const readinessTag = useMemo(() => {
    const status = data?.launchReadiness?.summary.overall_status;
    if (status === "ready") return <Tag color="success">上线就绪</Tag>;
    if (status === "blocked") return <Tag color="error">存在阻塞</Tag>;
    return <Tag color="warning">需要关注</Tag>;
  }, [data?.launchReadiness?.summary.overall_status]);

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: 16 }}>
      <Space align="center" style={{ marginBottom: 16, width: "100%" }} wrap>
        {readinessTag}
        <Typography.Text type="secondary">Health: {health}</Typography.Text>
        <Typography.Text type="secondary">AI Provider: {aiProvider}</Typography.Text>
        <Tag color={aiGlobalOn ? "processing" : "default"}>{aiGlobalOn ? "AI 全局开启" : "AI 全局关闭"}</Tag>
        {blockerCount ? <Tag color="error">阻塞 {blockerCount}</Tag> : null}
        {warningCount ? <Tag color="warning">告警 {warningCount}</Tag> : null}
        <div style={{ flex: 1 }} />
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      </Space>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col lg={4} md={8} sm={12} xs={24}><Card size="small"><Statistic title="总会话" value={stats.totalConversations} /></Card></Col>
        <Col lg={5} md={8} sm={12} xs={24}><Card size="small"><Statistic title="待处理" value={stats.recommended} valueStyle={{ color: stats.recommended > 0 ? "#ff4d4f" : undefined }} /></Card></Col>
        <Col lg={5} md={8} sm={12} xs={24}><Card size="small"><Statistic title="人工接管" value={stats.humanManaged} valueStyle={{ color: "#faad14" }} /></Card></Col>
        <Col lg={5} md={8} sm={12} xs={24}><Card size="small"><Statistic title="AI 托管" value={stats.aiManaged} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col lg={5} md={8} sm={12} xs={24}><Card size="small"><Statistic title="今日消息" value={totalMessages} suffix={<Typography.Text style={{ fontSize: 11 }}>{aiSuccessPct}% AI 成功</Typography.Text>} /></Card></Col>
      </Row>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col lg={14} xs={24}>
          <Card size="small" title="我的待办">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block ghost onClick={() => openWorkspacePage({})} type="primary">
                打开工作台
              </Button>
              <Button block onClick={() => openWorkspacePage({ managementMode: "human_managed" })}>
                查看人工接管会话
              </Button>
              <Button block onClick={() => openWorkspacePage({ managementMode: "paused" })}>
                查看已暂停会话
              </Button>
            </Space>
          </Card>
        </Col>
        <Col lg={10} xs={24}>
          <Card size="small" title="快捷操作">
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block onClick={() => setActivePage("conversations")} type="primary">
                进入会话工作台
              </Button>
              <Button block onClick={() => setActivePage("assignments")}>查看分配队列</Button>
              <Button block onClick={() => setActivePage("tickets")}>处理工单</Button>
              <Button block onClick={() => setActivePage("reviews")}>进入审核队列</Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col lg={12} xs={24}>
          <Card size="small" title="AI 表现">
            <Row gutter={[12, 12]}>
              <Col span={8}><Statistic title="成功率" value={`${aiSuccessPct}%`} /></Col>
              <Col span={8}><Statistic title="AI 成功" value={aiSuccess} /></Col>
              <Col span={8}><Statistic title="AI 降级" value={aiFallback} valueStyle={{ color: aiFallback > 0 ? "#faad14" : undefined }} /></Col>
            </Row>
          </Card>
        </Col>
        <Col lg={12} xs={24}>
          <Card size="small" title="账号概览">
            <Row gutter={[12, 12]}>
              <Col span={8}><Statistic title="运行中账号" value={accounts.length} /></Col>
              <Col span={8}><Statistic title="Meta 就绪" value={metaReady} valueStyle={{ color: "#52c41a" }} /></Col>
              <Col span={8}><Statistic title="AI 状态" value={aiGlobalOn ? "开启" : "关闭"} valueStyle={{ color: aiGlobalOn ? "#1677ff" : "#999" }} /></Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Card
        extra={
          <Space>
            {healthSummary?.last_check_at ? (
              <Typography.Text style={{ fontSize: 11 }} type="secondary">
                上次检查: {new Date(healthSummary.last_check_at).toLocaleString("zh-CN")}
              </Typography.Text>
            ) : null}
            <Button loading={healthLoading} onClick={() => void handleRunCheck()} size="small">
              立即检查
            </Button>
          </Space>
        }
        size="small"
        style={{ marginBottom: 16 }}
        title="系统健康"
      >
        <Row gutter={[12, 12]}>
          <HealthStatusBadge label="数据库" status={healthSummary?.db} />
          <HealthStatusBadge label="Redis" status={healthSummary?.redis} />
          <HealthStatusBadge label="API" status={healthSummary?.api} />
          <HealthStatusBadge label="H5 站点" status={healthSummary?.sites} />
          <HealthStatusBadge label="SSL" status={healthSummary?.ssl} />
        </Row>
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col lg={14} xs={24}>
          <Card size="small" title="AI 表现趋势（7天）">
            <TrendChart trends={MOCK_TRENDS} />
          </Card>
        </Col>
        <Col lg={10} xs={24}>
          <Card size="small" title="热门意图 Top 8">
            <IntentRanking intents={MOCK_INTENTS} />
          </Card>
        </Col>
      </Row>

      {error ? (
        <Typography.Text style={{ display: "block", marginTop: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}
    </div>
  );
}

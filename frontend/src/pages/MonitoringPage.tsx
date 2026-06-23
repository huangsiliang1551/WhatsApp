import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Card, Col, Modal, Row, Select, Space, Statistic, Table, Tag, Tabs, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { type LaunchReadinessCheck, getLaunchReadiness, getMetricsSummary, listQueueStats } from "../services/api";
import {
  getClientErrorDetail,
  listClientErrors,
  listUptimeChecks,
  type ClientErrorEntry,
  type UptimeCheckEntry,
} from "../services/errorTracker";
import { withSorter } from "../utils/withSorter";

const STATUS_META: Record<string, { color: string; label: string }> = {
  ready: { color: "success", label: "正常" },
  needs_attention: { color: "warning", label: "需关注" },
  blocked: { color: "error", label: "阻塞" },
};

const CLIENT_ERROR_TYPE_OPTIONS = [
  { label: "JavaScript", value: "javascript" },
  { label: "Promise", value: "promise" },
  { label: "资源加载", value: "resource" },
] as const;

const UPTIME_STATUS_OPTIONS = [
  { label: "在线", value: "up" },
  { label: "离线", value: "down" },
  { label: "超时", value: "timeout" },
] as const;

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function MetricTag({ label, color }: { label: string; color: "success" | "warning" | "error" | "default" }): JSX.Element {
  return (
    <Tag color={color} style={{ fontSize: 11 }}>
      {label}
    </Tag>
  );
}

function UptimeStatusTag({ status }: { status: UptimeCheckEntry["status"] }): JSX.Element {
  if (status === "up") return <Tag color="success">在线</Tag>;
  if (status === "down") return <Tag color="error">离线</Tag>;
  return <Tag color="warning">超时</Tag>;
}

function ReadinessCheckList({
  title,
  color,
  items,
}: {
  title: string;
  color: "warning" | "error";
  items: LaunchReadinessCheck[];
}): JSX.Element | null {
  if (!items.length) return null;

  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        {title}
      </Typography.Title>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        {items.map((item) => (
          <Card key={item.key} size="small">
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              <Space size={8} wrap>
                <Tag color={color}>{item.category}</Tag>
                <Typography.Text strong>{item.title}</Typography.Text>
              </Space>
              <Typography.Text>{item.message}</Typography.Text>
              {item.action_hint ? (
                <Typography.Text type="secondary">建议: {item.action_hint}</Typography.Text>
              ) : null}
            </Space>
          </Card>
        ))}
      </Space>
    </div>
  );
}

export function MonitoringPage(): JSX.Element {
  const fetchOverview = useCallback(async () => {
    const [metrics, queue, readiness] = await Promise.all([
      getMetricsSummary().catch(() => null),
      listQueueStats().catch(() => null),
      getLaunchReadiness().catch(() => null),
    ]);
    return { metrics, queue, readiness };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchOverview });
  const metrics = data?.metrics ?? null;
  const queue = data?.queue ?? null;
  const readiness = data?.readiness ?? null;

  const [clientErrors, setClientErrors] = useState<ClientErrorEntry[]>([]);
  const [clientErrorTotal, setClientErrorTotal] = useState(0);
  const [clientErrorPage, setClientErrorPage] = useState(1);
  const [clientErrorType, setClientErrorType] = useState<string | undefined>();
  const [clientErrorLoading, setClientErrorLoading] = useState(false);
  const [clientErrorDetail, setClientErrorDetail] = useState<ClientErrorEntry | null>(null);
  const [clientErrorDetailOpen, setClientErrorDetailOpen] = useState(false);

  const [uptimeChecks, setUptimeChecks] = useState<UptimeCheckEntry[]>([]);
  const [uptimeTotal, setUptimeTotal] = useState(0);
  const [uptimePage, setUptimePage] = useState(1);
  const [uptimeStatus, setUptimeStatus] = useState<string | undefined>();
  const [uptimeLoading, setUptimeLoading] = useState(false);

  const fetchClientErrors = useCallback(async () => {
    setClientErrorLoading(true);
    try {
      const response = await listClientErrors({
        page: clientErrorPage,
        size: 20,
        error_type: clientErrorType,
      });
      setClientErrors(response.items);
      setClientErrorTotal(response.total);
    } finally {
      setClientErrorLoading(false);
    }
  }, [clientErrorPage, clientErrorType]);

  const fetchUptimeChecks = useCallback(async () => {
    setUptimeLoading(true);
    try {
      const response = await listUptimeChecks({
        page: uptimePage,
        size: 20,
        status: uptimeStatus,
      });
      setUptimeChecks(response.items);
      setUptimeTotal(response.total);
    } finally {
      setUptimeLoading(false);
    }
  }, [uptimePage, uptimeStatus]);

  useEffect(() => {
    void fetchClientErrors();
  }, [fetchClientErrors]);

  useEffect(() => {
    void fetchUptimeChecks();
  }, [fetchUptimeChecks]);

  const handleViewErrorDetail = useCallback(async (id: string) => {
    const detail = await getClientErrorDetail(id);
    setClientErrorDetail(detail);
    setClientErrorDetailOpen(true);
  }, []);

  const statusMeta = STATUS_META[readiness?.summary.overall_status ?? "needs_attention"] ?? STATUS_META.needs_attention;
  const blockerChecks = readiness?.checks.filter((item) => item.status === "blocker") ?? [];
  const warningChecks = readiness?.checks.filter((item) => item.status === "warning") ?? [];

  const clientErrorColumns = useMemo(
    () =>
      withSorter([
        {
          title: "时间",
          dataIndex: "created_at",
          key: "created_at",
          width: 180,
          render: (value: string) => formatDateTime(value),
        },
        {
          title: "站点",
          dataIndex: "site_key",
          key: "site_key",
          width: 120,
          render: (value: string | null) => value || "-",
        },
        {
          title: "类型",
          dataIndex: "error_type",
          key: "error_type",
          width: 120,
          render: (value: string) => <Tag>{value}</Tag>,
        },
        {
          title: "消息",
          dataIndex: "message",
          key: "message",
          ellipsis: true,
        },
        {
          title: "操作",
          key: "actions",
          width: 120,
          render: (_: unknown, row: ClientErrorEntry) => (
            <Button onClick={() => void handleViewErrorDetail(row.id)} size="small" type="link">
              查看详情
            </Button>
          ),
        },
      ]),
    [handleViewErrorDetail],
  );

  const uptimeColumns = useMemo(
    () =>
      withSorter([
        {
          title: "站点",
          dataIndex: "site_name",
          key: "site_name",
          width: 180,
          render: (value: string | undefined, row: UptimeCheckEntry) => value || row.site_id,
        },
        {
          title: "状态",
          dataIndex: "status",
          key: "status",
          width: 120,
          render: (value: UptimeCheckEntry["status"]) => <UptimeStatusTag status={value} />,
        },
        {
          title: "响应时间",
          dataIndex: "response_time_ms",
          key: "response_time_ms",
          width: 120,
          render: (value: number | null) => (value == null ? "-" : `${value} ms`),
        },
        {
          title: "状态码",
          dataIndex: "status_code",
          key: "status_code",
          width: 100,
          render: (value: number | null) => value ?? "-",
        },
        {
          title: "错误信息",
          dataIndex: "error_message",
          key: "error_message",
          ellipsis: true,
          render: (value: string | null) =>
            value ? <Typography.Text type="danger">{value}</Typography.Text> : "-",
        },
        {
          title: "检测时间",
          dataIndex: "created_at",
          key: "created_at",
          width: 180,
          render: (value: string) => formatDateTime(value),
        },
      ]),
    [],
  );

  const overview = (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {error ? (
        <Typography.Text style={{ display: "block" }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Space size={12} wrap>
        <MetricTag color={statusMeta.color as "success" | "warning" | "error"} label={`上线状态: ${statusMeta.label}`} />
        <MetricTag color={metrics ? "success" : "warning"} label="Metrics" />
        <MetricTag color={queue?.queues.length ? "success" : "warning"} label="Queue" />
        <MetricTag color={readiness ? "success" : "warning"} label="Readiness" />
        {blockerChecks.length ? <Tag color="error">阻塞项 {blockerChecks.length}</Tag> : null}
        {warningChecks.length ? <Tag color="warning">告警项 {warningChecks.length}</Tag> : null}
      </Space>

      <Row gutter={[12, 12]}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="AI 请求" value={(metrics?.ai.success_total ?? 0) + (metrics?.ai.fallback_total ?? 0)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="AI 成功" value={metrics?.ai.success_total ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="AI 降级" value={metrics?.ai.fallback_total ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="入站消息" value={metrics?.inbound.accepted_total ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="队列待处理" value={metrics?.queue.queued_current ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="队列处理中" value={metrics?.queue.processing_current ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="模板送达" value={metrics?.templates.delivered_total ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="失败任务" value={metrics?.processing_failures.ai_auto_reply_total ?? 0} />
          </Card>
        </Col>
      </Row>

      {queue?.queues.length ? (
        <Card size="small" title="队列概览">
          <Space size={[8, 8]} wrap>
            {queue.queues.map((item) => (
              <Tag color={item.queued > 0 ? "warning" : "success"} key={item.queue}>
                {item.queue}: {item.queued}
              </Tag>
            ))}
          </Space>
        </Card>
      ) : null}

      <ReadinessCheckList color="error" items={blockerChecks} title="阻塞项" />
      <ReadinessCheckList color="warning" items={warningChecks} title="告警项" />
    </Space>
  );

  const clientErrorPanel = (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Space size={12} wrap>
        <Select
          allowClear
          onChange={(value) => {
            setClientErrorType(value);
            setClientErrorPage(1);
          }}
          options={CLIENT_ERROR_TYPE_OPTIONS.map((item) => ({ ...item }))}
          placeholder="选择错误类型"
          style={{ width: 180 }}
          value={clientErrorType}
        />
        <Button loading={clientErrorLoading} onClick={() => void fetchClientErrors()} size="small">
          刷新
        </Button>
      </Space>
      <Table
        columns={clientErrorColumns}
        dataSource={clientErrors}
        loading={clientErrorLoading}
        pagination={{
          current: clientErrorPage,
          onChange: (page) => setClientErrorPage(page),
          pageSize: 20,
          showSizeChanger: false,
          total: clientErrorTotal,
        }}
        rowKey="id"
        size="small"
      />
    </Space>
  );

  const uptimePanel = (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Space size={12} wrap>
        <Select
          allowClear
          onChange={(value) => {
            setUptimeStatus(value);
            setUptimePage(1);
          }}
          options={UPTIME_STATUS_OPTIONS.map((item) => ({ ...item }))}
          placeholder="选择状态"
          style={{ width: 180 }}
          value={uptimeStatus}
        />
        <Button loading={uptimeLoading} onClick={() => void fetchUptimeChecks()} size="small">
          刷新
        </Button>
      </Space>
      <Table
        columns={uptimeColumns}
        dataSource={uptimeChecks}
        loading={uptimeLoading}
        pagination={{
          current: uptimePage,
          onChange: (page) => setUptimePage(page),
          pageSize: 20,
          showSizeChanger: false,
          total: uptimeTotal,
        }}
        rowKey="id"
        size="small"
      />
    </Space>
  );

  const tabs = [
    { key: "overview", label: "概览", children: overview },
    { key: "client-errors", label: "前端错误", children: clientErrorPanel },
    { key: "uptime", label: "Uptime", children: uptimePanel },
  ];

  if (!metrics && !queue && !readiness && !loading) {
    return (
      <PageShell subtitle="系统健康状态、前端错误和运行可用性" title="监控健康">
        <EmptyGuide description="暂时没有可展示的监控数据。" icon="📊" title="暂无监控数据" />
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
      subtitle="系统健康状态、前端错误和运行可用性"
      title="监控健康"
    >
      <Tabs items={tabs} />
      <Modal
        footer={
          <Button onClick={() => setClientErrorDetailOpen(false)} type="default">
            关闭
          </Button>
        }
        onCancel={() => setClientErrorDetailOpen(false)}
        open={clientErrorDetailOpen}
        title="错误详情"
        width={720}
      >
        {clientErrorDetail ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <div>
              <Typography.Text strong>时间</Typography.Text>
              <div>{formatDateTime(clientErrorDetail.created_at)}</div>
            </div>
            <div>
              <Typography.Text strong>类型</Typography.Text>
              <div>{clientErrorDetail.error_type}</div>
            </div>
            <div>
              <Typography.Text strong>消息</Typography.Text>
              <div>{clientErrorDetail.message}</div>
            </div>
            <div>
              <Typography.Text strong>URL</Typography.Text>
              <div>{clientErrorDetail.url || "-"}</div>
            </div>
            <div>
              <Typography.Text strong>User Agent</Typography.Text>
              <div style={{ wordBreak: "break-all" }}>{clientErrorDetail.user_agent || "-"}</div>
            </div>
            {clientErrorDetail.stack_trace ? (
              <div>
                <Typography.Text strong>Stack Trace</Typography.Text>
                <pre
                  style={{
                    background: "#111827",
                    borderRadius: 8,
                    color: "#e5e7eb",
                    marginTop: 8,
                    maxHeight: 320,
                    overflow: "auto",
                    padding: 12,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {clientErrorDetail.stack_trace}
                </pre>
              </div>
            ) : null}
          </Space>
        ) : null}
      </Modal>
    </PageShell>
  );
}

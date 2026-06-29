import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Statistic,
  Table,
  Typography,
} from "antd";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePermissions } from "../hooks/usePermissions";
import { GatewayStatusTag } from "../components/h5-gateway/GatewayStatusTag";
import {
  getGatewayHealthSummary,
  listGatewayJobs,
  listGatewayNodes,
} from "../services/gatewayAdmin";
import type {
  GatewayHealthSummary,
  GatewayJobRecord,
  GatewayNodeRecord,
} from "../types/gateway";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function normalizeGatewayError(error: unknown): string {
  const message = error instanceof Error ? error.message : "加载 H5 Gateway 失败";
  if (message.includes("404")) {
    return "H5 Gateway 后端接口尚未接线，当前页面只提供 typed client 的 loading、error、empty state。";
  }
  return message;
}

export function H5GatewayNodesPage(): JSX.Element {
  const { can, loading: permissionLoading } = usePermissions();
  const canView = can("sites.view") || can("sites.edit");

  const [summary, setSummary] = useState<GatewayHealthSummary | null>(null);
  const [nodes, setNodes] = useState<GatewayNodeRecord[]>([]);
  const [jobs, setJobs] = useState<GatewayJobRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  const loadPage = useCallback(async (): Promise<void> => {
    if (!canView) {
      return;
    }
    setLoading(true);
    setPageError(null);
    const [summaryResult, nodesResult, jobsResult] = await Promise.allSettled([
      getGatewayHealthSummary(),
      listGatewayNodes(),
      listGatewayJobs(),
    ]);

    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      setSummary(null);
      setPageError(normalizeGatewayError(summaryResult.reason));
    }

    if (nodesResult.status === "fulfilled") {
      setNodes(nodesResult.value);
    } else {
      setNodes([]);
      setPageError((current) => current ?? normalizeGatewayError(nodesResult.reason));
    }

    if (jobsResult.status === "fulfilled") {
      setJobs(jobsResult.value);
    } else {
      setJobs([]);
      setPageError((current) => current ?? normalizeGatewayError(jobsResult.reason));
    }

    setLoading(false);
  }, [canView]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  const pageStats = useMemo(() => {
    if (!summary) {
      return null;
    }
    return (
      <Row gutter={[12, 12]}>
        <Col span={4}><Card size="small"><Statistic title="节点总数" value={summary.totalNodes} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="在线节点" value={summary.onlineNodes} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="降级节点" value={summary.degradedNodes} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="离线节点" value={summary.offlineNodes} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="运行中任务" value={summary.runningJobs} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="失败任务" value={summary.failedJobs} /></Card></Col>
      </Row>
    );
  }, [summary]);

  if (!permissionLoading && !canView) {
    return (
      <PageShell title="H5 Gateway 工作台" subtitle="节点、作业和部署健康占位工作台">
        <EmptyGuide
          icon="馃敀"
          title="缺少 sites.view / sites.edit 权限"
          description="当前账号无法查看 H5 Gateway 节点和作业状态。"
        />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="H5 Gateway 工作台"
      subtitle="Gateway 后端未完成前，前端只展示真实接口的 loading、error、empty state。"
      actions={(
        <Button loading={loading} onClick={() => void loadPage()}>
          刷新
        </Button>
      )}
      stats={pageStats ?? undefined}
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {pageError ? <Alert type="warning" showIcon message={pageError} /> : null}
        <Alert
          type="info"
          showIcon
          message="当前状态"
          description="W4 后端路由尚未落地时，这个页面不会伪造节点成功数据；如果接口未实现，会直接暴露真实错误并保持空态。"
        />

        <Card size="small" title="Gateway 节点">
          <Table
            rowKey="id"
            loading={loading}
            dataSource={nodes}
            locale={{ emptyText: <Empty description="暂无可读取的 Gateway 节点" /> }}
            pagination={{ pageSize: 8, showSizeChanger: true }}
            columns={[
              { title: "节点名", dataIndex: "name" },
              { title: "主机", dataIndex: "host" },
              { title: "环境", dataIndex: "environment", render: (value: string | null) => value || "-" },
              { title: "区域", dataIndex: "region", render: (value: string | null) => value || "-" },
              {
                title: "状态",
                dataIndex: "status",
                render: (value: GatewayNodeRecord["status"]) => <GatewayStatusTag status={value} />,
              },
              { title: "站点数", dataIndex: "activeSiteCount", width: 90 },
              { title: "最近心跳", dataIndex: "lastHeartbeatAt", render: (value: string | null) => formatDateTime(value) },
              { title: "最近部署", dataIndex: "lastDeployAt", render: (value: string | null) => formatDateTime(value) },
            ]}
          />
        </Card>

        <Card size="small" title="Gateway 作业">
          <Table
            rowKey="id"
            loading={loading}
            dataSource={jobs}
            locale={{ emptyText: <Empty description="暂无可读取的 Gateway 作业" /> }}
            pagination={{ pageSize: 8, showSizeChanger: true }}
            columns={[
              { title: "作业 ID", dataIndex: "id", width: 180 },
              { title: "类型", dataIndex: "jobType", width: 140 },
              { title: "站点", dataIndex: "siteKey", render: (value: string | null) => value || "-" },
              {
                title: "状态",
                dataIndex: "status",
                width: 100,
                render: (value: GatewayJobRecord["status"]) => <GatewayStatusTag status={value} />,
              },
              { title: "开始时间", dataIndex: "startedAt", render: (value: string | null) => formatDateTime(value) },
              { title: "结束时间", dataIndex: "finishedAt", render: (value: string | null) => formatDateTime(value) },
              {
                title: "错误",
                dataIndex: "errorMessage",
                render: (value: string | null) => (
                  <Typography.Text type={value ? "danger" : undefined}>{value || "-"}</Typography.Text>
                ),
              },
            ]}
          />
        </Card>
      </Space>
    </PageShell>
  );
}

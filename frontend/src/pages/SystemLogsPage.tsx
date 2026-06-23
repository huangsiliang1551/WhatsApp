import { Alert, Button, Card, Col, Descriptions, Row, Select, Space, Statistic, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useRef, useState, type JSX } from "react";

import { PageShell } from "../components/PageShell";
import { getSystemLogSnapshot } from "../services/adminCenter";
import { useAppStore } from "../stores/appStore";
import type { SystemLogEntry, SystemLogSeverity, SystemLogSnapshot } from "../types/systemLogs";

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString("zh-CN");
}

function getSeverityTag(severity: SystemLogSeverity): JSX.Element {
  if (severity === "critical") return <Tag color="error">critical</Tag>;
  if (severity === "warning") return <Tag color="warning">warning</Tag>;
  return <Tag color="processing">info</Tag>;
}

function getSourceTag(kind: SystemLogEntry["source_kind"]): JSX.Element {
  if (kind === "audit") return <Tag color="blue">audit</Tag>;
  if (kind === "provider") return <Tag color="gold">provider</Tag>;
  return <Tag color="red">queue</Tag>;
}

export function SystemLogsPage(): JSX.Element {
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const systemLogsPagePrefill = useAppStore((state) => state.systemLogsPagePrefill);
  const clearSystemLogsPagePrefill = useAppStore((state) => state.clearSystemLogsPagePrefill);
  const setSystemLogsPagePrefill = useAppStore((state) => state.setSystemLogsPagePrefill);
  const openAuditPage = useAppStore((state) => state.openAuditPage);
  const openProviderEventsPage = useAppStore((state) => state.openProviderEventsPage);
  const openEvidencePage = useAppStore((state) => state.openEvidencePage);
  const openOperationsPage = useAppStore((state) => state.openOperationsPage);
  const lastAppliedPrefillNonce = useRef<number | null>(null);

  const [accountFilter, setAccountFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<"ALL" | SystemLogSeverity>("ALL");
  const [sourceFilter, setSourceFilter] = useState<"ALL" | SystemLogEntry["source_kind"]>("ALL");
  const [snapshot, setSnapshot] = useState<SystemLogSnapshot | null>(null);
  const [selectedLogId, setSelectedLogId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredEntries = useMemo(() => {
    const entries = snapshot?.entries ?? [];
    return entries.filter((item) => {
      const matchSeverity = severityFilter === "ALL" || item.severity === severityFilter;
      const matchSource = sourceFilter === "ALL" || item.source_kind === sourceFilter;
      return matchSeverity && matchSource;
    });
  }, [severityFilter, snapshot, sourceFilter]);

  const selectedEntry = useMemo(
    () => filteredEntries.find((item) => item.id === selectedLogId) ?? null,
    [filteredEntries, selectedLogId]
  );

  async function loadPage(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const nextSnapshot = await getSystemLogSnapshot(accountFilter !== "ALL" ? accountFilter : undefined);
      setSnapshot(nextSnapshot);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "系统日志加载失败");
    } finally {
      setLoading(false);
    }
  }

  function openEntry(entry: SystemLogEntry): void {
    if (entry.source_kind === "audit") {
      openAuditPage({
        account_id: entry.account_id ?? undefined,
        target_type: entry.target_type ?? undefined,
        target_id: entry.target_id ?? undefined,
        limit: 50,
      });
      return;
    }

    if (entry.source_kind === "provider") {
      openProviderEventsPage({
        account_id: entry.account_id ?? undefined,
        provider_name: entry.provider_name ?? undefined,
        provider_message_id: entry.provider_message_id ?? undefined,
        replay_state: "pending",
      });
      return;
    }

    openOperationsPage({
      account_id: entry.account_id ?? undefined,
    });
  }

  useEffect(() => {
    void loadPage();
  }, [accountFilter]);

  useEffect(() => {
    if (!systemLogsPagePrefill) return;
    if (lastAppliedPrefillNonce.current === systemLogsPagePrefill.nonce) return;

    lastAppliedPrefillNonce.current = systemLogsPagePrefill.nonce;
    setAccountFilter(systemLogsPagePrefill.account_id ?? "ALL");
    setSeverityFilter(systemLogsPagePrefill.severity ?? "ALL");
    setSourceFilter(systemLogsPagePrefill.source_kind ?? "ALL");
    setSelectedLogId(systemLogsPagePrefill.selected_log_id ?? "");
    clearSystemLogsPagePrefill();
  }, [clearSystemLogsPagePrefill, systemLogsPagePrefill]);

  useEffect(() => {
    setSystemLogsPagePrefill({
      account_id: accountFilter !== "ALL" ? accountFilter : undefined,
      severity: severityFilter !== "ALL" ? severityFilter : undefined,
      source_kind: sourceFilter !== "ALL" ? sourceFilter : undefined,
      selected_log_id: selectedLogId || undefined,
    });
  }, [accountFilter, selectedLogId, setSystemLogsPagePrefill, severityFilter, sourceFilter]);

  useEffect(() => {
    if (!filteredEntries.length) {
      setSelectedLogId("");
      return;
    }
    if (selectedLogId && filteredEntries.some((item) => item.id === selectedLogId)) {
      return;
    }
    setSelectedLogId(filteredEntries[0].id);
  }, [filteredEntries, selectedLogId]);

  const columns = [
    {
      title: "时间",
      key: "occurred_at",
      width: 180,
      render: (_: unknown, record: SystemLogEntry) => formatTimestamp(record.occurred_at),
    },
    {
      title: "来源",
      key: "source_kind",
      width: 110,
      render: (_: unknown, record: SystemLogEntry) => getSourceTag(record.source_kind),
    },
    {
      title: "账号",
      key: "account_id",
      width: 140,
      render: (_: unknown, record: SystemLogEntry) => record.account_id ?? "global",
    },
    {
      title: "等级",
      key: "severity",
      width: 110,
      render: (_: unknown, record: SystemLogEntry) => getSeverityTag(record.severity),
    },
    {
      title: "内容",
      key: "content",
      render: (_: unknown, record: SystemLogEntry) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{record.title}</Typography.Text>
          <Typography.Text type="secondary">{record.summary}</Typography.Text>
        </Space>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 90,
      render: (_: unknown, record: SystemLogEntry) => (
        <Button onClick={() => openEntry(record)} size="small" type="link">
          查看
        </Button>
      ),
    },
  ];

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void loadPage()} size="small" type="primary">
          刷新
        </Button>
      }
      subtitle="审计、Provider 与队列失败日志的统一检视"
      title="系统日志"
    >
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? <Alert message={error} showIcon type="error" /> : null}
        {snapshot?.warnings.map((item) => (
          <Alert key={item} message={item} showIcon type="warning" />
        ))}

        <Card>
          <Space align="center" size={[12, 12]} wrap>
            <Select
              options={[
                { label: "全部账号", value: "ALL" },
                ...actorAccountIds.map((item) => ({ label: item, value: item })),
              ]}
              onChange={setAccountFilter}
              style={{ width: 220 }}
              value={accountFilter}
            />
            <Select
              options={[
                { label: "全部等级", value: "ALL" },
                { label: "critical", value: "critical" },
                { label: "warning", value: "warning" },
                { label: "info", value: "info" },
              ]}
              onChange={(value) => setSeverityFilter(value)}
              style={{ width: 160 }}
              value={severityFilter}
            />
            <Select
              options={[
                { label: "全部来源", value: "ALL" },
                { label: "audit", value: "audit" },
                { label: "provider", value: "provider" },
                { label: "queue", value: "queue" },
              ]}
              onChange={(value) => setSourceFilter(value)}
              style={{ width: 160 }}
              value={sourceFilter}
            />
            <Button
              onClick={() =>
                openEvidencePage({
                  account_id: accountFilter !== "ALL" ? accountFilter : undefined,
                  source_kind:
                    sourceFilter !== "ALL"
                      ? sourceFilter
                      : selectedEntry?.source_kind === "audit"
                        ? "audit"
                        : selectedEntry?.source_kind === "provider"
                          ? "provider"
                          : "queue",
                })
              }
            >
              证据中心
            </Button>
            <Button
              onClick={() =>
                openAuditPage({
                  account_id: accountFilter !== "ALL" ? accountFilter : undefined,
                  limit: 50,
                })
              }
            >
              审计日志
            </Button>
            <Button
              onClick={() =>
                openProviderEventsPage({
                  account_id: accountFilter !== "ALL" ? accountFilter : undefined,
                })
              }
            >
              Webhook 事件
            </Button>
            <Button
              onClick={() =>
                openOperationsPage({
                  account_id: accountFilter !== "ALL" ? accountFilter : undefined,
                })
              }
            >
              运营看板
            </Button>
          </Space>
        </Card>

        <Row gutter={[16, 16]}>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="审计数量" value={snapshot?.audit_count ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="待处理 Provider" value={snapshot?.provider_pending_count ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="失败任务" value={snapshot?.failed_job_count ?? 0} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="严重告警" value={snapshot?.critical_count ?? 0} />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col lg={14} xs={24}>
            <Card bodyStyle={{ padding: 0 }} size="small" title="日志列表">
              <Table<SystemLogEntry>
                columns={columns}
                dataSource={filteredEntries}
                loading={loading}
                onRow={(record) => ({
                  onClick: () => setSelectedLogId(record.id),
                })}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                rowClassName={(record) => (record.id === selectedLogId ? "ant-table-row-selected" : "")}
                rowKey="id"
                scroll={{ x: 860 }}
                size="small"
              />
            </Card>
          </Col>
          <Col lg={10} xs={24}>
            <Card size="small" title="当前选中">
              {selectedEntry ? (
                <Descriptions bordered column={1} size="small">
                  <Descriptions.Item label="来源">
                    <Space size={[8, 8]} wrap>
                      {getSourceTag(selectedEntry.source_kind)}
                      {getSeverityTag(selectedEntry.severity)}
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label="账号">{selectedEntry.account_id ?? "global"}</Descriptions.Item>
                  <Descriptions.Item label="时间">{formatTimestamp(selectedEntry.occurred_at)}</Descriptions.Item>
                  <Descriptions.Item label="标题">{selectedEntry.title}</Descriptions.Item>
                  <Descriptions.Item label="摘要">{selectedEntry.summary}</Descriptions.Item>
                  <Descriptions.Item label="详情">{selectedEntry.detail}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Typography.Text type="secondary">请选择一条日志查看详情。</Typography.Text>
              )}
            </Card>
          </Col>
        </Row>
      </Space>
    </PageShell>
  );
}

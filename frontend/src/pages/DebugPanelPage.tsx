import {
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  LinkOutlined,
  LoadingOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getLaunchReadiness,
  getMetricsSummary,
  healthCheckMetaAccount,
  listMetaAccounts,
  listMetaPhoneNumbers,
  listMetaWebhookSubscriptions,
  listQueueStats,
  type MetaPhoneNumberScopeView,
  type MetaWabaAccount,
  type MetaWebhookSubscriptionView,
} from "../services/api";

interface CheckItem {
  key: string;
  label: string;
  status: "pass" | "fail" | "warn" | "pending";
  detail: string;
}

interface DebugData {
  health: Record<string, unknown> | null;
  readiness: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  accounts: MetaWabaAccount[] | null;
  phones: MetaPhoneNumberScopeView[] | null;
  webhooks: MetaWebhookSubscriptionView[] | null;
  queue: Record<string, unknown> | null;
  accountHealthChecks: Record<string, { status: string; detail: string }>;
}

function statusBadge(status: CheckItem["status"], label?: string): JSX.Element {
  const map: Record<CheckItem["status"], { color: string; icon: JSX.Element }> = {
    pass: { color: "#52c41a", icon: <CheckCircleOutlined /> },
    fail: { color: "#ff4d4f", icon: <CloseCircleOutlined /> },
    warn: { color: "#faad14", icon: <CheckCircleOutlined /> },
    pending: { color: "#d9d9d9", icon: <LoadingOutlined spin /> },
  };

  const item = map[status];
  return (
    <Tag color={item.color} icon={item.icon} style={{ fontSize: 11, margin: 0 }}>
      {label ?? status}
    </Tag>
  );
}

function JsonSummary({ data }: { data: unknown }): JSX.Element {
  return (
    <pre
      style={{
        background: "#fafafa",
        border: "1px solid #f0f0f0",
        borderRadius: 8,
        fontSize: 11,
        margin: 0,
        maxHeight: 260,
        overflow: "auto",
        padding: 12,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export function DebugPanelPage(): JSX.Element {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAll = useCallback(async (): Promise<DebugData> => {
    const [healthResult, readinessResult, metricsResult, accountsResult, phonesResult, webhooksResult, queueResult] =
      await Promise.allSettled([
        fetch("/health").then((response) => response.json()),
        getLaunchReadiness(),
        getMetricsSummary(),
        listMetaAccounts(),
        listMetaPhoneNumbers(),
        listMetaWebhookSubscriptions(),
        listQueueStats(),
      ]);

    const pick = <T,>(result: PromiseSettledResult<T>): T | null =>
      result.status === "fulfilled" ? result.value : null;

    const health = pick(healthResult);
    const readiness = pick(readinessResult);
    const metrics = pick(metricsResult);
    const accounts = pick(accountsResult);
    const phones = pick(phonesResult);
    const webhooks = pick(webhooksResult);
    const queue = pick(queueResult);

    const accountHealthChecks: DebugData["accountHealthChecks"] = {};
    if (accounts?.length) {
      const checks = await Promise.allSettled(
        accounts.map((account) =>
          healthCheckMetaAccount(account.account_id, account.waba_id).catch((error) => ({
            status: "error",
            detail: error instanceof Error ? error.message : String(error),
          }))
        )
      );

      accounts.forEach((account, index) => {
        const result = checks[index];
        accountHealthChecks[`${account.account_id}:${account.waba_id}`] =
          result.status === "fulfilled"
            ? {
                status: (result.value as { status?: string }).status ?? "unknown",
                detail: JSON.stringify(result.value),
              }
            : {
                status: "error",
                detail: String(result.reason),
              };
      });
    }

    return {
      health,
      readiness,
      metrics,
      accounts,
      phones,
      webhooks,
      queue,
      accountHealthChecks,
    };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchAll });

  useEffect(() => {
    if (!autoRefresh) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    timerRef.current = setInterval(() => void reload(), 10_000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoRefresh, reload]);

  const dbStatus = ((data?.health as { db_circuit_status?: { status?: string } } | null)?.db_circuit_status?.status ??
    "unknown") as string;
  const queueList = ((data?.queue as { queues?: Array<{ queued?: number }> } | null)?.queues ?? []) as Array<{ queued?: number }>;
  const queueTotal = queueList.reduce((sum, item) => sum + (item.queued ?? 0), 0);
  const accountCount = data?.accounts?.length ?? 0;
  const phoneCount = data?.phones?.length ?? 0;
  const webhookCount = data?.webhooks?.length ?? 0;

  const checks: CheckItem[] = [
    {
      key: "health",
      label: "App 服务",
      status: data?.health ? "pass" : "fail",
      detail: data?.health ? `健康接口可访问，数据库状态 ${dbStatus}` : "无法获取 /health",
    },
    {
      key: "db",
      label: "数据库",
      status: dbStatus === "HEALTHY" ? "pass" : dbStatus === "RECOVERING" ? "warn" : "fail",
      detail: `db_circuit_status = ${dbStatus}`,
    },
    {
      key: "meta_accounts",
      label: "Meta 账户",
      status: accountCount > 0 ? "pass" : "warn",
      detail: `已配置 ${accountCount} 个账户`,
    },
    {
      key: "phones",
      label: "WhatsApp 号码",
      status: phoneCount > 0 ? "pass" : "warn",
      detail: `已发现 ${phoneCount} 个号码`,
    },
    {
      key: "webhooks",
      label: "Webhook 订阅",
      status: webhookCount > 0 ? "pass" : "pending",
      detail: `已发现 ${webhookCount} 条订阅记录`,
    },
    {
      key: "queue",
      label: "任务队列",
      status: queueTotal > 50 ? "warn" : "pass",
      detail: `当前队列积压 ${queueTotal} 条`,
    },
  ];

  const failCount = checks.filter((item) => item.status === "fail").length;
  const warnCount = checks.filter((item) => item.status === "warn").length;
  const passCount = checks.filter((item) => item.status === "pass").length;
  const overallStatus: "success" | "warning" | "error" = failCount > 0 ? "error" : warnCount > 0 ? "warning" : "success";

  return (
    <PageShell
      actions={
        <Space>
          <Button onClick={() => setAutoRefresh((value) => !value)} size="small" type={autoRefresh ? "primary" : "default"}>
            自动刷新: {autoRefresh ? "ON" : "OFF"}
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void reload()} size="small">
            立即刷新
          </Button>
        </Space>
      }
      subtitle="全链路联通状态、Meta 接入状态与系统运行概览"
      title="链路调试面板"
    >
      {error ? <Alert closable message={error} style={{ marginBottom: 16 }} type="error" /> : null}

      <Card style={{ marginBottom: 16, textAlign: "center" }}>
        {loading && !data ? (
          <Spin tip="正在检测全链路状态">
            <div style={{ height: 80 }} />
          </Spin>
        ) : (
          <Result
            extra={
              <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "center" }}>
                <Statistic title="通过" value={passCount} valueStyle={{ color: "#52c41a", fontSize: 28 }} />
                <Statistic title="警告" value={warnCount} valueStyle={{ color: "#faad14", fontSize: 28 }} />
                <Statistic title="失败" value={failCount} valueStyle={{ color: "#ff4d4f", fontSize: 28 }} />
              </div>
            }
            status={overallStatus}
            subTitle={`${passCount}/${checks.length} 项检查通过`}
            title={overallStatus === "success" ? "全部通畅" : overallStatus === "warning" ? "部分需关注" : "存在阻塞项"}
          />
        )}
      </Card>

      <Card size="small" style={{ marginBottom: 16 }} title="检测项">
        <Timeline
          items={checks.map((item) => ({
            dot: statusBadge(item.status),
            children: (
              <div>
                <Typography.Text strong style={{ fontSize: 13 }}>
                  {item.label}
                </Typography.Text>
                <br />
                <Typography.Text style={{ fontSize: 11 }} type="secondary">
                  {item.detail}
                </Typography.Text>
              </div>
            ),
          }))}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col lg={12} xs={24}>
          <Card
            extra={<Badge count={accountCount} style={{ backgroundColor: accountCount > 0 ? "#52c41a" : "#faad14" }} />}
            size="small"
            title={
              <span>
                <LinkOutlined /> Meta 账户
              </span>
            }
          >
            {!data?.accounts?.length ? (
              <Typography.Text style={{ fontSize: 12 }} type="secondary">
                暂无 Meta 账户，请先在 Meta 账户页面完成配置。
              </Typography.Text>
            ) : (
              <Space direction="vertical" size={8} style={{ display: "flex" }}>
                {data.accounts.map((account) => {
                  const healthKey = `${account.account_id}:${account.waba_id}`;
                  const healthInfo = data.accountHealthChecks[healthKey];
                  return (
                    <Card key={healthKey} size="small">
                      <Descriptions
                        colon={false}
                        column={1}
                        contentStyle={{ fontSize: 11 }}
                        labelStyle={{ color: "#888", fontSize: 10 }}
                        size="small"
                      >
                        <Descriptions.Item label="账户">
                          {account.display_name}
                          <Tag color={account.is_active ? "success" : "default"} style={{ marginLeft: 8 }}>
                            {account.is_active ? "启用" : "停用"}
                          </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="WABA ID">{account.waba_id}</Descriptions.Item>
                        <Descriptions.Item label="号码数">{account.phone_numbers?.length ?? 0}</Descriptions.Item>
                        <Descriptions.Item label="Webhook 运行态">{account.webhook_runtime_status}</Descriptions.Item>
                        <Descriptions.Item label="健康检查">
                          <Tag color={healthInfo?.status === "healthy" ? "success" : "error"}>
                            {healthInfo?.status ?? "unknown"}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                    </Card>
                  );
                })}
              </Space>
            )}
          </Card>
        </Col>

        <Col lg={12} xs={24}>
          <Card
            extra={<Badge count={phoneCount} style={{ backgroundColor: "#1677ff" }} />}
            size="small"
            title={
              <span>
                <ApiOutlined /> 号码与 Webhook
              </span>
            }
          >
            <Space direction="vertical" size={12} style={{ display: "flex" }}>
              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  号码列表
                </Typography.Text>
                {!data?.phones?.length ? (
                  <Typography.Text style={{ fontSize: 12 }} type="secondary">
                    暂无号码
                  </Typography.Text>
                ) : (
                  <Space direction="vertical" size={6} style={{ display: "flex" }}>
                    {data.phones.map((phone) => (
                      <div
                        key={phone.phone_number_id}
                        style={{ alignItems: "center", borderBottom: "1px solid #f5f5f5", display: "flex", justifyContent: "space-between", padding: "6px 0" }}
                      >
                        <div>
                          <Typography.Text style={{ fontSize: 12 }}>{phone.display_phone_number}</Typography.Text>
                          <Typography.Text style={{ fontSize: 10, marginLeft: 6 }} type="secondary">
                            {phone.account_display_name}
                          </Typography.Text>
                        </div>
                        <Space size={4}>
                          <Tag color={phone.is_registered ? "success" : "default"}>{phone.is_registered ? "已注册" : "未注册"}</Tag>
                          <Tag color={phone.webhook_subscribed ? "success" : "default"}>{phone.webhook_subscribed ? "Webhook 已订阅" : "Webhook 未订阅"}</Tag>
                        </Space>
                      </div>
                    ))}
                  </Space>
                )}
              </div>

              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  Webhook 订阅
                </Typography.Text>
                {!data?.webhooks?.length ? (
                  <Typography.Text style={{ fontSize: 12 }} type="secondary">
                    暂无订阅记录
                  </Typography.Text>
                ) : (
                  <Space direction="vertical" size={6} style={{ display: "flex" }}>
                    {data.webhooks.map((item) => (
                      <div key={item.id} style={{ borderBottom: "1px solid #f5f5f5", padding: "6px 0" }}>
                        <Typography.Text style={{ fontSize: 12 }}>{item.callback_url || item.waba_id || item.id}</Typography.Text>
                        <div>
                          <Tag color={item.status === "subscribed" ? "success" : "default"}>{item.status}</Tag>
                        </div>
                      </div>
                    ))}
                  </Space>
                )}
              </div>
            </Space>
          </Card>
        </Col>

        <Col lg={12} xs={24}>
          <Card
            size="small"
            title={
              <span>
                <DatabaseOutlined /> Readiness / Metrics
              </span>
            }
          >
            <Space direction="vertical" size={12} style={{ display: "flex" }}>
              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  Readiness
                </Typography.Text>
                {data?.readiness ? <JsonSummary data={data.readiness} /> : <Typography.Text type="secondary">暂无 readiness 数据</Typography.Text>}
              </div>
              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  Metrics
                </Typography.Text>
                {data?.metrics ? <JsonSummary data={data.metrics} /> : <Typography.Text type="secondary">暂无 metrics 数据</Typography.Text>}
              </div>
            </Space>
          </Card>
        </Col>

        <Col lg={12} xs={24}>
          <Card
            size="small"
            title={
              <span>
                <CloudServerOutlined /> Queue / Health
              </span>
            }
          >
            <Space direction="vertical" size={12} style={{ display: "flex" }}>
              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  /health
                </Typography.Text>
                {data?.health ? <JsonSummary data={data.health} /> : <Typography.Text type="secondary">暂无 /health 数据</Typography.Text>}
              </div>
              <div>
                <Typography.Text strong style={{ display: "block", marginBottom: 6 }}>
                  Queue
                </Typography.Text>
                {data?.queue ? <JsonSummary data={data.queue} /> : <Typography.Text type="secondary">暂无队列数据</Typography.Text>}
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </PageShell>
  );
}

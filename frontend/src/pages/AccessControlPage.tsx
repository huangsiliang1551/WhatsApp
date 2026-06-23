import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Statistic, Table, Tag, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getAccessControlSnapshot } from "../services/accessControl";
import { withSorter } from "../utils/withSorter";

const POLICY_STATUS_COLORS: Record<string, string> = {
  enforced: "success",
  none: "default",
  partial: "warning",
  review: "processing",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function AccessControlPage(): JSX.Element {
  const fetchData = useCallback(async () => getAccessControlSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const policies = data?.policies ?? [];
  const sessions = data?.sessions ?? [];
  const events = data?.events ?? [];
  const globalSettings = data?.global_settings ?? null;

  if (!data && !loading) {
    return (
      <PageShell subtitle="访问策略、管理员会话和安全事件概览" title="访问控制">
        <EmptyGuide description="当前无法读取访问控制数据。" icon="🛡️" title="暂无访问控制数据" />
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
      subtitle="访问策略、管理员会话和安全事件概览"
      title="访问控制"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="访问策略" value={policies.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="后台会话" value={sessions.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="强制策略" value={policies.filter((item) => item.effective_status === "enforced").length} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="待复核事件" value={events.filter((item) => item.level !== "info").length} valueStyle={{ color: "#faad14" }} /></Card></Col>
      </Row>

      {globalSettings ? (
        <Card size="small" style={{ marginBottom: 16 }} title="全局设置">
          <Row gutter={[12, 12]}>
            <Col span={6}><Statistic title="登录模式" value={globalSettings.login_mode} /></Col>
            <Col span={6}><Statistic title="会话超时(分钟)" value={globalSettings.session_timeout_minutes} /></Col>
            <Col span={6}><Statistic title="MFA" value={globalSettings.mfa_required ? "开启" : "关闭"} /></Col>
            <Col span={6}><Statistic title="IP 白名单" value={globalSettings.ip_allowlist_enabled ? "开启" : "关闭"} /></Col>
          </Row>
        </Card>
      ) : null}

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        访问策略
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "策略 ID", dataIndex: "policy_id", ellipsis: true, key: "policy_id", width: 180 },
          { title: "账号", dataIndex: "account_id", key: "account_id", render: (value: string | null) => value || "全局", width: 100 },
          { title: "范围", dataIndex: "scope", key: "scope", render: (value: string) => <Tag>{value}</Tag>, width: 90 },
          { title: "登录模式", dataIndex: "login_mode", key: "login_mode", width: 100 },
          { title: "MFA", dataIndex: "mfa_required", key: "mfa_required", render: (value: boolean) => (value ? "是" : "否"), width: 70 },
          { title: "会话超时", dataIndex: "session_timeout_minutes", key: "session_timeout_minutes", width: 90 },
          {
            title: "状态",
            dataIndex: "effective_status",
            key: "effective_status",
            render: (value: string) => <Tag color={POLICY_STATUS_COLORS[value] ?? "default"}>{value}</Tag>,
            width: 100,
          },
          { title: "原因", dataIndex: "effective_reason", ellipsis: true, key: "effective_reason" },
          { title: "更新时间", dataIndex: "updated_at", key: "updated_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={policies}
        loading={loading}
        pagination={false}
        rowKey="policy_id"
        scroll={{ y: 180 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        后台会话
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "成员", dataIndex: "display_name", key: "display_name", width: 120 },
          { title: "账号", dataIndex: "account_id", key: "account_id", render: (value: string | null) => value || "全局", width: 100 },
          { title: "角色", dataIndex: "role_name", key: "role_name", width: 100 },
          {
            title: "状态",
            dataIndex: "status",
            key: "status",
            render: (value: string) => <Tag color={value === "active" ? "success" : value === "idle" ? "warning" : "default"}>{value}</Tag>,
            width: 100,
          },
          { title: "登录模式", dataIndex: "login_mode", key: "login_mode", width: 100 },
          { title: "MFA", dataIndex: "mfa_verified", key: "mfa_verified", render: (value: boolean) => (value ? "是" : "否"), width: 70 },
          { title: "设备", dataIndex: "device_label", ellipsis: true, key: "device_label", width: 140 },
          { title: "IP", dataIndex: "ip_address", key: "ip_address", width: 130 },
          { title: "最近活跃", dataIndex: "last_seen_at", key: "last_seen_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={sessions}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        rowKey={(row) => row.session_id}
        scroll={{ y: 220 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        安全事件
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "时间", dataIndex: "occurred_at", key: "occurred_at", render: (value: string) => formatDateTime(value), width: 180 },
          { title: "账号", dataIndex: "account_id", key: "account_id", render: (value: string | null) => value || "全局", width: 100 },
          { title: "等级", dataIndex: "level", key: "level", render: (value: string) => <Tag color={value === "critical" ? "error" : value === "warning" ? "warning" : "processing"}>{value}</Tag>, width: 100 },
          { title: "标题", dataIndex: "title", key: "title", width: 180 },
          { title: "摘要", dataIndex: "summary", ellipsis: true, key: "summary" },
        ])}
        dataSource={events}
        loading={loading}
        pagination={{ pageSize: 8, showSizeChanger: false }}
        rowKey={(row) => row.event_id}
        scroll={{ y: 180 }}
        size="small"
      />
    </PageShell>
  );
}

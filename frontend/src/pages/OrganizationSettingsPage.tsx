import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Statistic, Table, Tag, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getOrganizationCenterSnapshot } from "../services/organizationCenter";
import { withSorter } from "../utils/withSorter";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function OrganizationSettingsPage(): JSX.Element {
  const fetchData = useCallback(async () => getOrganizationCenterSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const scopes = data?.account_scopes ?? [];
  const units = data?.units ?? [];
  const inviteDomains = data?.invite_domains ?? [];
  const approvalChains = data?.approval_chains ?? [];
  const warnings = data?.warnings ?? [];

  if (!data && !loading) {
    return (
      <PageShell subtitle="组织架构、账号范围与审批链配置" title="组织设置">
        <EmptyGuide description="组织结构数据暂时不可用。" icon="🏢" title="暂无组织数据" />
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
      subtitle="组织架构、账号范围与审批链配置"
      title="组织设置"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      {warnings.length ? (
        <Card size="small" style={{ marginBottom: 16 }} title="数据告警">
          {warnings.map((item) => (
            <Typography.Text key={item} style={{ display: "block", marginBottom: 4 }} type="warning">
              {item}
            </Typography.Text>
          ))}
        </Card>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="账号范围" value={scopes.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="组织单元" value={units.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="邀请域名" value={inviteDomains.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="审批链" value={approvalChains.length} /></Card></Col>
      </Row>

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        账号范围
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "名称", dataIndex: "display_name", key: "display_name", width: 140 },
          {
            title: "状态",
            dataIndex: "is_active",
            key: "is_active",
            render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "启用" : "停用"}</Tag>,
            width: 90,
          },
          { title: "站点数", dataIndex: "site_count", key: "site_count", width: 90 },
          { title: "成员数", dataIndex: "member_count", key: "member_count", width: 90 },
          { title: "WABA", dataIndex: "waba_count", key: "waba_count", width: 80 },
          { title: "已登记号码", dataIndex: "registered_phone_number_count", key: "registered_phone_number_count", width: 120 },
          {
            title: "Webhook 验证",
            dataIndex: "webhook_verification_status",
            key: "webhook_verification_status",
            render: (value: string | null) => <Tag>{value ?? "-"}</Tag>,
            width: 120,
          },
          {
            title: "Webhook 运行",
            dataIndex: "webhook_runtime_status",
            key: "webhook_runtime_status",
            render: (value: string | null) => <Tag>{value ?? "-"}</Tag>,
            width: 120,
          },
          {
            title: "最近回调",
            dataIndex: "last_webhook_event_at",
            key: "last_webhook_event_at",
            render: (value: string | null) => formatDateTime(value),
            width: 180,
          },
        ])}
        dataSource={scopes}
        loading={loading}
        pagination={false}
        rowKey={(row) => row.account_id ?? "global"}
        scroll={{ y: 180 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        组织单元
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "名称", dataIndex: "name", key: "name", width: 160 },
          { title: "负责人", dataIndex: "manager_name", key: "manager_name", width: 120 },
          { title: "成员数", dataIndex: "member_count", key: "member_count", width: 90 },
          {
            title: "账号范围",
            dataIndex: "account_scope",
            key: "account_scope",
            ellipsis: true,
            render: (value: string[]) => value.join(", "),
          },
          {
            title: "状态",
            dataIndex: "status",
            key: "status",
            render: (value: string) => <Tag color={value === "active" ? "success" : "default"}>{value}</Tag>,
            width: 100,
          },
        ])}
        dataSource={units}
        loading={loading}
        pagination={false}
        rowKey={(row) => row.unit_id}
        scroll={{ y: 180 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        邀请域名
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "域名", dataIndex: "domain", key: "domain", width: 200 },
          { title: "默认角色", dataIndex: "auto_join_role", key: "auto_join_role", width: 120 },
          {
            title: "审批模式",
            dataIndex: "approval_mode",
            key: "approval_mode",
            render: (value: string) => <Tag>{value}</Tag>,
            width: 120,
          },
          {
            title: "SSO",
            dataIndex: "sso_enforced",
            key: "sso_enforced",
            render: (value: boolean) => <Tag color={value ? "processing" : "default"}>{value ? "强制" : "关闭"}</Tag>,
            width: 90,
          },
          {
            title: "验证状态",
            dataIndex: "verified",
            key: "verified",
            render: (value: boolean) => <Tag color={value ? "success" : "warning"}>{value ? "已验证" : "待验证"}</Tag>,
            width: 100,
          },
          { title: "说明", dataIndex: "effective_reason", key: "effective_reason", ellipsis: true },
        ])}
        dataSource={inviteDomains}
        loading={loading}
        pagination={false}
        rowKey={(row) => row.domain_id}
        scroll={{ y: 180 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        审批链
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "名称", dataIndex: "name", key: "name", width: 180 },
          { title: "触发类型", dataIndex: "trigger_type", key: "trigger_type", width: 140, render: (value: string) => <Tag>{value}</Tag> },
          {
            title: "审批人",
            dataIndex: "approvers",
            key: "approvers",
            render: (value: string[]) => value.join(", "),
          },
          { title: "SLA(分钟)", dataIndex: "sla_minutes", key: "sla_minutes", width: 110 },
          {
            title: "启用",
            dataIndex: "enabled",
            key: "enabled",
            render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "是" : "否"}</Tag>,
            width: 90,
          },
        ])}
        dataSource={approvalChains}
        loading={loading}
        pagination={false}
        rowKey={(row) => row.chain_id}
        scroll={{ y: 180 }}
        size="small"
      />
    </PageShell>
  );
}

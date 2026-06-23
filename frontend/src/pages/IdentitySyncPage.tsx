import { Alert, Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography, message } from "antd";
import { useCallback, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getIdentitySyncSnapshot, toggleIdentityDomain, triggerIdentitySync } from "../services/identitySync";
import type {
  IdentityDomainBinding,
  IdentityProviderView,
  IdentityRoleMapping,
  IdentitySyncJob,
} from "../types/identitySync";
import { withSorter } from "../utils/withSorter";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function renderResultTag(value: "active" | "review" | "enforced" | "partial"): JSX.Element {
  const color =
    value === "active" || value === "enforced"
      ? "success"
      : value === "partial"
        ? "warning"
        : "processing";
  return <Tag color={color}>{value}</Tag>;
}

export function IdentitySyncPage(): JSX.Element {
  const fetchData = useCallback(async () => getIdentitySyncSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const handleSyncProvider = useCallback(
    async (providerId: string) => {
      try {
        await triggerIdentitySync(providerId);
        message.success("身份同步任务已触发");
        await reload();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "触发同步失败");
      }
    },
    [reload]
  );

  const handleToggleDomain = useCallback(
    async (domainId: string) => {
      try {
        await toggleIdentityDomain(domainId);
        message.success("域名同步策略已更新");
        await reload();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "更新域名策略失败");
      }
    },
    [reload]
  );

  if (!data) {
    if (loading) {
      return (
        <PageShell subtitle="身份源、域名绑定、角色映射与同步任务" title="身份同步">
          <Typography.Text>加载中...</Typography.Text>
        </PageShell>
      );
    }

    return (
      <PageShell subtitle="身份源、域名绑定、角色映射与同步任务" title="身份同步">
        <EmptyGuide description="当前无法读取身份同步快照。" icon="🪪" title="暂无身份同步数据" />
      </PageShell>
    );
  }

  const providerColumns = withSorter<IdentityProviderView>([
    {
      title: "提供方",
      dataIndex: "provider_name",
      key: "provider_name",
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "账号",
      dataIndex: "account_id",
      key: "account_id",
      width: 140,
      render: (value: string | null) => value ?? "global",
    },
    {
      title: "状态",
      dataIndex: "account_binding_status",
      key: "account_binding_status",
      width: 120,
      render: (value: string) => (
        <Tag color={value === "linked" ? "success" : value === "limited" ? "warning" : "default"}>{value}</Tag>
      ),
    },
    {
      title: "登录模式",
      dataIndex: "login_mode",
      key: "login_mode",
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "成员数",
      dataIndex: "mapped_member_count",
      key: "mapped_member_count",
      width: 100,
    },
    {
      title: "目录数",
      dataIndex: "directory_member_count",
      key: "directory_member_count",
      width: 100,
    },
    {
      title: "最近同步",
      dataIndex: "last_sync_at",
      key: "last_sync_at",
      width: 180,
      render: (value: string | null) => formatDateTime(value),
    },
    {
      title: "结果",
      dataIndex: "effective_result",
      key: "effective_result",
      width: 120,
      render: (value: IdentityProviderView["effective_result"]) => renderResultTag(value),
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_: unknown, record: IdentityProviderView) => (
        <Button onClick={() => void handleSyncProvider(record.provider_id)} size="small" type="link">
          立即同步
        </Button>
      ),
    },
  ]);

  const domainColumns = withSorter<IdentityDomainBinding>([
    {
      title: "域名",
      dataIndex: "domain",
      key: "domain",
      width: 220,
    },
    {
      title: "账号",
      dataIndex: "account_id",
      key: "account_id",
      width: 140,
      render: (value: string | null) => value ?? "global",
    },
    {
      title: "已验证",
      dataIndex: "verified",
      key: "verified",
      width: 100,
      render: (value: boolean) => <Tag color={value ? "success" : "warning"}>{value ? "yes" : "no"}</Tag>,
    },
    {
      title: "Auto provision",
      dataIndex: "auto_provision_enabled",
      key: "auto_provision_enabled",
      width: 140,
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "on" : "off"}</Tag>,
    },
    {
      title: "JIT",
      dataIndex: "jit_enabled",
      key: "jit_enabled",
      width: 100,
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "on" : "off"}</Tag>,
    },
    {
      title: "结果",
      dataIndex: "effective_result",
      key: "effective_result",
      width: 120,
      render: (value: IdentityDomainBinding["effective_result"]) => renderResultTag(value),
    },
    {
      title: "操作",
      key: "action",
      width: 130,
      render: (_: unknown, record: IdentityDomainBinding) => (
        <Button onClick={() => void handleToggleDomain(record.domain_id)} size="small" type="link">
          切换策略
        </Button>
      ),
    },
  ]);

  const mappingColumns = withSorter<IdentityRoleMapping>([
    {
      title: "外部组",
      dataIndex: "external_group",
      key: "external_group",
      width: 180,
    },
    {
      title: "角色",
      dataIndex: "role_name",
      key: "role_name",
      width: 160,
    },
    {
      title: "账号范围",
      dataIndex: "account_scope",
      key: "account_scope",
      width: 220,
      render: (value: string[]) => value.join(", "),
    },
    {
      title: "页面范围",
      dataIndex: "page_scope",
      key: "page_scope",
      width: 260,
      render: (value: string[]) => (value.length ? value.join(", ") : "all"),
    },
    {
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 100,
    },
    {
      title: "已映射成员",
      dataIndex: "mapped_member_count",
      key: "mapped_member_count",
      width: 120,
    },
    {
      title: "结果",
      dataIndex: "effective_result",
      key: "effective_result",
      width: 120,
      render: (value: IdentityRoleMapping["effective_result"]) => renderResultTag(value),
    },
  ]);

  const jobColumns = withSorter<IdentitySyncJob>([
    {
      title: "任务 ID",
      dataIndex: "job_id",
      key: "job_id",
      width: 220,
      ellipsis: true,
    },
    {
      title: "账号",
      dataIndex: "account_id",
      key: "account_id",
      width: 140,
      render: (value: string | null) => value ?? "global",
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => (
        <Tag color={value === "completed" ? "success" : value === "failed" ? "error" : "processing"}>{value}</Tag>
      ),
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      key: "started_at",
      width: 180,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: "结束时间",
      dataIndex: "finished_at",
      key: "finished_at",
      width: 180,
      render: (value: string | null) => formatDateTime(value),
    },
    {
      title: "Imported",
      dataIndex: "imported_count",
      key: "imported_count",
      width: 100,
    },
    {
      title: "Updated",
      dataIndex: "updated_count",
      key: "updated_count",
      width: 100,
    },
    {
      title: "Errors",
      dataIndex: "error_count",
      key: "error_count",
      width: 100,
    },
    {
      title: "摘要",
      dataIndex: "summary",
      key: "summary",
      ellipsis: true,
    },
  ]);

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      }
      subtitle="身份源、域名绑定、角色映射与同步任务"
      title="身份同步"
    >
      <Space direction="vertical" size={16} style={{ display: "flex" }}>
        {error ? (
          <Typography.Text style={{ display: "block" }} type="danger">
            {error}
          </Typography.Text>
        ) : null}

        {data.warnings.length > 0 ? (
          <Alert
            showIcon
            type="warning"
            message="同步告警"
            description={
              <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                {data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            }
          />
        ) : null}

        <Row gutter={[12, 12]}>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="身份源" value={data.providers.length} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="域名绑定" value={data.domains.length} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="角色映射" value={data.mappings.length} />
            </Card>
          </Col>
          <Col lg={6} md={12} xs={24}>
            <Card size="small">
              <Statistic title="同步任务" value={data.jobs.length} />
            </Card>
          </Col>
        </Row>

        <Card bodyStyle={{ padding: 0 }} size="small" title="身份源">
          <Table
            columns={providerColumns}
            dataSource={data.providers}
            loading={loading}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            rowKey="provider_id"
            scroll={{ x: 1160 }}
            size="small"
          />
        </Card>

        <Card bodyStyle={{ padding: 0 }} size="small" title="域名绑定">
          <Table
            columns={domainColumns}
            dataSource={data.domains}
            loading={loading}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            rowKey="domain_id"
            scroll={{ x: 980 }}
            size="small"
          />
        </Card>

        <Card bodyStyle={{ padding: 0 }} size="small" title="角色映射">
          <Table
            columns={mappingColumns}
            dataSource={data.mappings}
            loading={loading}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            rowKey="mapping_id"
            scroll={{ x: 1180 }}
            size="small"
          />
        </Card>

        <Card bodyStyle={{ padding: 0 }} size="small" title="最近同步任务">
          <Table
            columns={jobColumns}
            dataSource={data.jobs}
            loading={loading}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            rowKey="job_id"
            scroll={{ x: 1260 }}
            size="small"
          />
        </Card>
      </Space>
    </PageShell>
  );
}

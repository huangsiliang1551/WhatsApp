import { PlusOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import { useCallback, useEffect, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { listIPBlacklist, addToBlacklist, removeFromBlacklist, type IPBlacklistEntry } from "../services/errorTracker";
import { getSecuritySettingsSnapshot } from "../services/securityCenter";
import type { SecuritySessionPolicy, SecuritySsoProvider } from "../types/securitySettings";
import { withSorter } from "../utils/withSorter";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function formatBool(value: boolean | null | undefined, trueLabel = "Yes", falseLabel = "No"): string {
  return value ? trueLabel : falseLabel;
}

function renderPolicyResultTag(value: SecuritySessionPolicy["effective_result"]): JSX.Element {
  const color =
    value === "enforced" ? "success" : value === "partial" ? "warning" : value === "review" ? "processing" : "default";
  return <Tag color={color}>{value ?? "n/a"}</Tag>;
}

function renderProviderResultTag(value: SecuritySsoProvider["effective_result"]): JSX.Element {
  const color = value === "enforced" ? "success" : value === "partial" ? "warning" : "processing";
  return <Tag color={color}>{value}</Tag>;
}

function renderRuntimeStatusTag(value: SecuritySsoProvider["webhook_runtime_status"]): JSX.Element {
  const color =
    value === "healthy"
      ? "success"
      : value === "signature_failed" || value === "payload_invalid"
        ? "error"
        : value === "verification_pending" || value === "pending"
          ? "warning"
          : "default";
  return <Tag color={color}>{value ?? "none"}</Tag>;
}

export function SecuritySettingsPage(): JSX.Element {
  const fetchData = useCallback(async () => getSecuritySettingsSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const [blacklist, setBlacklist] = useState<IPBlacklistEntry[]>([]);
  const [blacklistLoading, setBlacklistLoading] = useState(false);
  const [blacklistModalOpen, setBlacklistModalOpen] = useState(false);
  const [blacklistSaving, setBlacklistSaving] = useState(false);
  const [blacklistForm] = Form.useForm<{ ip_address: string; reason?: string }>();

  const loadBlacklist = useCallback(async () => {
    setBlacklistLoading(true);
    try {
      const items = await listIPBlacklist();
      setBlacklist(items);
    } catch {
      setBlacklist([]);
    } finally {
      setBlacklistLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBlacklist();
  }, [loadBlacklist]);

  const handleAddIP = useCallback(
    async (values: { ip_address: string; reason?: string }) => {
      setBlacklistSaving(true);
      try {
        await addToBlacklist(values);
        message.success("IP 已加入黑名单");
        setBlacklistModalOpen(false);
        blacklistForm.resetFields();
        await loadBlacklist();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "添加 IP 失败");
      } finally {
        setBlacklistSaving(false);
      }
    },
    [blacklistForm, loadBlacklist]
  );

  const handleRemoveIP = useCallback(
    async (id: string) => {
      try {
        await removeFromBlacklist(id);
        message.success("IP 已移出黑名单");
        await loadBlacklist();
      } catch (err) {
        message.error(err instanceof Error ? err.message : "移除 IP 失败");
      }
    },
    [loadBlacklist]
  );

  const sessionPolicyColumns = withSorter<SecuritySessionPolicy>([
    {
      title: "Account",
      dataIndex: "account_id",
      key: "account_id",
      width: 140,
      render: (value: string | null) => value ?? "global",
    },
    {
      title: "Login mode",
      dataIndex: "login_mode",
      key: "login_mode",
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "MFA",
      dataIndex: "mfa_required",
      key: "mfa_required",
      width: 100,
      render: (value: boolean) => formatBool(value, "Required", "Optional"),
    },
    {
      title: "Timeout",
      dataIndex: "session_timeout_minutes",
      key: "session_timeout_minutes",
      width: 120,
      render: (value: number) => `${value} min`,
    },
    {
      title: "Parallel sessions",
      dataIndex: "max_parallel_sessions",
      key: "max_parallel_sessions",
      width: 130,
    },
    {
      title: "Webhook signature",
      dataIndex: "webhook_signature_enforced",
      key: "webhook_signature_enforced",
      width: 140,
      render: (value: boolean | undefined) => formatBool(value, "Enforced", "Off"),
    },
    {
      title: "Effective result",
      dataIndex: "effective_result",
      key: "effective_result",
      width: 140,
      render: (value: SecuritySessionPolicy["effective_result"]) => renderPolicyResultTag(value),
    },
    {
      title: "Reason",
      dataIndex: "effective_reason",
      key: "effective_reason",
      ellipsis: true,
    },
  ]);

  const providerColumns = withSorter<SecuritySsoProvider>([
    {
      title: "Provider",
      dataIndex: "provider_name",
      key: "provider_name",
      width: 120,
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: "Account",
      dataIndex: "account_id",
      key: "account_id",
      width: 140,
      render: (value: string | null) => value ?? "global",
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      width: 100,
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "On" : "Off"}</Tag>,
    },
    {
      title: "Mapped roles",
      dataIndex: "mapped_role_count",
      key: "mapped_role_count",
      width: 120,
    },
    {
      title: "Binding",
      dataIndex: "account_binding_status",
      key: "account_binding_status",
      width: 120,
      render: (value: string | undefined) => <Tag>{value ?? "n/a"}</Tag>,
    },
    {
      title: "Runtime",
      dataIndex: "webhook_runtime_status",
      key: "webhook_runtime_status",
      width: 120,
      render: (value: SecuritySsoProvider["webhook_runtime_status"]) => renderRuntimeStatusTag(value),
    },
    {
      title: "Delivery",
      dataIndex: "webhook_delivery_state",
      key: "webhook_delivery_state",
      width: 120,
      render: (value: string | undefined) => <Tag>{value ?? "n/a"}</Tag>,
    },
    {
      title: "Effective result",
      dataIndex: "effective_result",
      key: "effective_result",
      width: 140,
      render: (value: SecuritySsoProvider["effective_result"]) => renderProviderResultTag(value),
    },
    {
      title: "Last verified",
      dataIndex: "webhook_last_verified_at",
      key: "webhook_last_verified_at",
      width: 180,
      render: (value: string | null | undefined) => formatDateTime(value),
    },
  ]);

  const blacklistColumns = withSorter<IPBlacklistEntry>([
    {
      title: "IP address",
      dataIndex: "ip_address",
      key: "ip_address",
      width: 180,
    },
    {
      title: "Reason",
      dataIndex: "reason",
      key: "reason",
      ellipsis: true,
      render: (value: string | null) => value ?? "-",
    },
    {
      title: "Blocked until",
      dataIndex: "blocked_until",
      key: "blocked_until",
      width: 180,
      render: (value: string | null) => formatDateTime(value),
    },
    {
      title: "Created at",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: "Action",
      key: "action",
      width: 100,
      render: (_: unknown, record: IPBlacklistEntry) => (
        <Button danger onClick={() => void handleRemoveIP(record.id)} size="small" type="link">
          Remove
        </Button>
      ),
    },
  ]);

  if (!data) {
    if (loading) {
      return (
        <PageShell subtitle="Password policy, session controls, SSO providers, and IP restrictions" title="Security Settings">
          <Typography.Text>Loading...</Typography.Text>
        </PageShell>
      );
    }

    return (
      <PageShell subtitle="Password policy, session controls, SSO providers, and IP restrictions" title="Security Settings">
        <EmptyGuide description="The security settings snapshot is currently unavailable." icon="🔐" title="No security data" />
      </PageShell>
    );
  }

  const settingsTab = (
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
          message="Security warnings"
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
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Members" value={data.summary.member_count} />
          </Card>
        </Col>
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Active sessions" value={data.summary.active_session_count} />
          </Card>
        </Col>
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Linked providers" value={data.summary.linked_provider_count} />
          </Card>
        </Col>
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Review policies" value={data.summary.review_policy_count} />
          </Card>
        </Col>
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Webhook protected" value={data.summary.webhook_protected_policy_count} />
          </Card>
        </Col>
        <Col lg={8} md={12} sm={12} xs={24}>
          <Card size="small">
            <Statistic title="Signature failures" value={data.summary.webhook_signature_failure_count} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col lg={12} xs={24}>
          <Card
            size="small"
            title="Password policy"
            extra={<Tag>{data.password_policy.source}</Tag>}
          >
            <Space size={[8, 8]} wrap>
              <Tag>Min length {data.password_policy.min_length}</Tag>
              <Tag color={data.password_policy.require_uppercase ? "success" : "default"}>
                Uppercase {formatBool(data.password_policy.require_uppercase, "on", "off")}
              </Tag>
              <Tag color={data.password_policy.require_number ? "success" : "default"}>
                Number {formatBool(data.password_policy.require_number, "on", "off")}
              </Tag>
              <Tag color={data.password_policy.require_symbol ? "success" : "default"}>
                Symbol {formatBool(data.password_policy.require_symbol, "on", "off")}
              </Tag>
              <Tag>Password expiry {data.password_policy.password_expiry_days} days</Tag>
            </Space>
          </Card>
        </Col>
        <Col lg={12} xs={24}>
          <Card
            size="small"
            title="Runtime config"
            extra={<Typography.Text type="secondary">{formatDateTime(data.generated_at)}</Typography.Text>}
          >
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              <Typography.Text>Environment: {data.config?.app_env ?? "-"}</Typography.Text>
              <Typography.Text>Language: {data.config?.console_language ?? "-"}</Typography.Text>
              <Typography.Text>Test mode: {formatBool(data.config?.test_mode, "Enabled", "Disabled")}</Typography.Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card bodyStyle={{ padding: 0 }} size="small" title="Session policies">
        <Table
          columns={sessionPolicyColumns}
          dataSource={data.session_policies}
          loading={loading}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          rowKey={(record) => record.account_id ?? "global"}
          scroll={{ x: 980 }}
          size="small"
        />
      </Card>

      <Card bodyStyle={{ padding: 0 }} size="small" title="SSO providers">
        <Table
          columns={providerColumns}
          dataSource={data.sso_providers}
          loading={loading}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          rowKey="provider_id"
          scroll={{ x: 1100 }}
          size="small"
        />
      </Card>
    </Space>
  );

  const blacklistTab = (
    <Space direction="vertical" size={16} style={{ display: "flex" }}>
      <Row align="middle" gutter={[12, 12]} justify="space-between">
        <Col flex="auto">
          <Typography.Text type="secondary">
            Add risky client IPs here to block access to the admin console and related endpoints.
          </Typography.Text>
        </Col>
        <Col>
          <Button
            icon={<PlusOutlined />}
            onClick={() => {
              blacklistForm.resetFields();
              setBlacklistModalOpen(true);
            }}
            type="primary"
          >
            Add IP
          </Button>
        </Col>
      </Row>

      <Card bodyStyle={{ padding: 0 }} size="small" title="IP blacklist">
        <Table
          columns={blacklistColumns}
          dataSource={blacklist}
          loading={blacklistLoading}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          rowKey="id"
          scroll={{ x: 760 }}
          size="small"
        />
      </Card>

      <Modal
        cancelText="Cancel"
        confirmLoading={blacklistSaving}
        okText="Add"
        onCancel={() => {
          setBlacklistModalOpen(false);
          blacklistForm.resetFields();
        }}
        onOk={() => void blacklistForm.submit()}
        open={blacklistModalOpen}
        title="Add blacklist IP"
      >
        <Form form={blacklistForm} layout="vertical" onFinish={handleAddIP}>
          <Form.Item
            label="IP address"
            name="ip_address"
            rules={[{ required: true, message: "Please enter an IP address." }]}
          >
            <Input placeholder="e.g. 192.168.1.100" />
          </Form.Item>
          <Form.Item label="Reason" name="reason">
            <Input.TextArea placeholder="Optional note for audit context" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          Refresh
        </Button>
      }
      subtitle="Password policy, session controls, SSO providers, and IP restrictions"
      title="Security Settings"
    >
      <Tabs
        items={[
          { key: "settings", label: "Settings", children: settingsTab },
          { key: "ip-blacklist", label: "IP Blacklist", children: blacklistTab },
        ]}
      />
    </PageShell>
  );
}

import { useCallback, useState, type JSX } from "react";
import { Button, Card, Divider, Form, Input, InputNumber, Modal, Select, Space, Switch, Table, Tag, Typography, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, UnlockOutlined } from "@ant-design/icons";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import { PageShell } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import {
  listRateLimitRules, createRateLimitRule, updateRateLimitRule, deleteRateLimitRule,
  listBannedIps, unbanIp,
  type RateLimitRule, type BannedIp,
} from "../services/api";

export function RateLimitsPage(): JSX.Element {
  const { can } = usePermissions();

  // ── Rules ──
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RateLimitRule | null>(null);
  const [ruleForm] = Form.useForm();
  const [ruleSaving, setRuleSaving] = useState(false);

  const ruleFetcher = useCallback(async () => {
    const [rules, bannedIps] = await Promise.all([
      listRateLimitRules(),
      listBannedIps(),
    ]);
    return { rules, bannedIps };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: ruleFetcher });
  const rules: RateLimitRule[] = data?.rules ?? [];
  const bannedIps: BannedIp[] = data?.bannedIps ?? [];

  const handleOpenRuleModal = (rule?: RateLimitRule) => {
    setEditingRule(rule ?? null);
    if (rule) {
      ruleForm.setFieldsValue({
        agency_name: rule.agency_name,
        endpoint_pattern: rule.endpoint_pattern,
        max_requests: rule.max_requests,
        window_seconds: rule.window_seconds,
        ban_minutes: rule.ban_minutes,
        is_enabled: rule.is_enabled,
      });
    } else {
      ruleForm.resetFields();
      ruleForm.setFieldsValue({ is_enabled: true, window_seconds: 60, ban_minutes: 30 });
    }
    setRuleModalOpen(true);
  };

  const handleRuleSave = async (values: {
    agency_name?: string; endpoint_pattern: string;
    max_requests: number; window_seconds: number; ban_minutes: number; is_enabled: boolean;
  }) => {
    setRuleSaving(true);
    try {
      if (editingRule) {
        await updateRateLimitRule(editingRule.id, values);
        showSuccess("规则已更新");
      } else {
        await createRateLimitRule(values);
        showSuccess("规则已创建");
      }
      setRuleModalOpen(false);
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setRuleSaving(false);
    }
  };

  const handleRuleDelete = async (rule: RateLimitRule) => {
    try {
      await deleteRateLimitRule(rule.id);
      showSuccess("规则已删除");
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleRuleToggle = async (rule: RateLimitRule, enabled: boolean) => {
    try {
      await updateRateLimitRule(rule.id, { is_enabled: enabled });
      showSuccess(enabled ? "规则已启用" : "规则已禁用");
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    }
  };

  const handleUnban = async (ip: string) => {
    try {
      await unbanIp(ip);
      showSuccess(`IP ${ip} 已解封`);
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "解封失败");
    }
  };

  const actions = (
    <Space>
      {can("rate_limits.manage") && (
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => handleOpenRuleModal()}>
          新增规则
        </Button>
      )}
      <Button size="small" onClick={() => void reload()} loading={loading}>刷新</Button>
    </Space>
  );

  const ruleColumns = [
    { title: "代理商", dataIndex: "agency_name", key: "agency_name", width: 120, render: (v: string | null) => v || <Tag>全局</Tag> },
    { title: "端点模式", dataIndex: "endpoint_pattern", key: "endpoint_pattern", ellipsis: true },
    {
      title: "限制", key: "limit", width: 160,
      render: (_: unknown, r: RateLimitRule) => `${r.max_requests} 次 / ${r.window_seconds}秒`,
    },
    { title: "封禁时长", key: "ban", width: 120, render: (_: unknown, r: RateLimitRule) => `${r.ban_minutes} 分钟` },
    {
      title: "状态", dataIndex: "is_enabled", key: "is_enabled", width: 80,
      render: (v: boolean, r: RateLimitRule) => (
        <Switch size="small" checked={v} onChange={(checked) => handleRuleToggle(r, checked)} />
      ),
    },
    {
      title: "操作", key: "actions", width: 140,
      render: (_: unknown, r: RateLimitRule) => (
        <Space size="small">
          <Button size="small" onClick={() => handleOpenRuleModal(r)}>编辑</Button>
          <DangerButton label="删除" confirmTitle="确认删除此规则?" onConfirm={() => handleRuleDelete(r)} type="link" danger />
        </Space>
      ),
    },
  ];

  const banColumns = [
    { title: "IP 地址", dataIndex: "ip", key: "ip", width: 160 },
    { title: "封禁时间", dataIndex: "banned_at", key: "banned_at", width: 160, render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-" },
    { title: "剩余时间 (分钟)", dataIndex: "remaining_minutes", key: "remaining_minutes", width: 140 },
    {
      title: "操作", key: "actions", width: 100,
      render: (_: unknown, r: BannedIp) => (
        <Button size="small" icon={<UnlockOutlined />} onClick={() => handleUnban(r.ip)}>解封</Button>
      ),
    },
  ];

  return (
    <PageShell title="API 频率限制" subtitle="配置 API 调用频率限制和 IP 封禁规则" actions={actions}>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}

      <Card size="small" title="频率限制规则" style={{ marginBottom: 16 }}>
        <Table
          dataSource={rules}
          columns={withSorter(ruleColumns)}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={false}
          scroll={{ y: 300 }}
        />
      </Card>

      <Card size="small" title="被封禁 IP">
        <Table
          dataSource={bannedIps}
          columns={withSorter(banColumns)}
          rowKey="ip"
          size="small"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ y: 300 }}
        />
      </Card>

      {/* Rule Modal */}
      <Modal
        title={editingRule ? "编辑规则" : "新增规则"}
        open={ruleModalOpen}
        onCancel={() => { setRuleModalOpen(false); setEditingRule(null); }}
        onOk={() => ruleForm.submit()}
        confirmLoading={ruleSaving}
        okText="保存"
        cancelText="取消"
      >
        <Form form={ruleForm} layout="vertical" onFinish={handleRuleSave}>
          <Form.Item label="代理商" name="agency_name">
            <Input placeholder="留空表示全局规则" />
          </Form.Item>
          <Form.Item label="端点模式" name="endpoint_pattern" rules={[{ required: true, message: "请输入端点模式" }]}>
            <Input placeholder="例如: /api/* 或 /api/chat/send" />
          </Form.Item>
          <Space style={{ width: "100%" }} size={12}>
            <Form.Item label="最大请求数" name="max_requests" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item label="时间窗口 (秒)" name="window_seconds" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item label="封禁时长 (分钟)" name="ban_minutes" rules={[{ required: true }]}>
              <InputNumber min={0} style={{ width: 140 }} />
            </Form.Item>
          </Space>
          <Form.Item label="启用" name="is_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}

export default RateLimitsPage;

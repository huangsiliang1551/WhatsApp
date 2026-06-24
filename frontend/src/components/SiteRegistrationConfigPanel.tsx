// SiteRegistrationConfigPanel：站点注册与归属配置区。
//
// 展示/编辑：
// - registration_entry_required
// - allow_invite_code_alias
// - default_staff_entry_link_id
// - default_ai_agent_id
// - default_ai_entry_link_id
// - member_invite_inherits_human_owner
// - member_invite_inherits_ai
// - allow_unattributed_waba_inbound
// - existing_member_link_override_policy
// - ai_failover_policy
// - ai_failover_threshold_minutes
//
// 操作：一键确保默认客服链接 / AI 链接、复制注册链接 / WhatsApp 对话链接。

import { useEffect, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { CopyOutlined, LinkOutlined, ReloadOutlined } from "@ant-design/icons";

interface SiteRegistrationConfig {
  registration_entry_required?: boolean;
  allow_invite_code_alias?: boolean;
  allow_unattributed_waba_inbound?: boolean;
  default_staff_entry_link_id?: string | null;
  default_ai_agent_id?: string | null;
  default_ai_entry_link_id?: string | null;
  member_invite_inherits_human_owner?: boolean;
  member_invite_inherits_ai?: boolean;
  existing_member_link_override_policy?: string;
  ai_failover_policy?: string;
  ai_failover_threshold_minutes?: number;
}

interface SiteRegistrationConfigPanelProps {
  accountId: string;
  siteId: string;
  siteKey: string;
  canManage: boolean;
  initialConfig: SiteRegistrationConfig | null;
  onEnsureDefaultStaffLink?: () => Promise<{ code?: string; link_id?: string } | null>;
  onEnsureDefaultAILink?: () => Promise<{ code?: string; link_id?: string } | null>;
  onSave?: (values: SiteRegistrationConfig) => Promise<void> | void;
}

const OVERRIDE_POLICIES = [
  { value: "do_not_override", label: "不覆盖" },
  { value: "allow_manual_override", label: "允许手工覆盖" },
  { value: "allow_new_link_override", label: "允许新链接覆盖" },
];

const FAILOVER_POLICIES = [
  { value: "temporary_only", label: "仅临时" },
  { value: "temporary_then_auto_reassign", label: "临时后自动迁移" },
  { value: "immediate_reassign", label: "立即迁移" },
  { value: "handover_only", label: "仅转人工" },
];

function copyToClipboard(text: string, label: string) {
  if (!text) {
    message.warning(`${label} 为空，无法复制`);
    return;
  }
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    navigator.clipboard
      .writeText(text)
      .then(() => message.success(`${label} 已复制`))
      .catch(() => message.info(`请手动复制：${text}`));
  } else {
    message.info(`请手动复制：${text}`);
  }
}

export function SiteRegistrationConfigPanel({
  accountId,
  siteId,
  siteKey,
  canManage,
  initialConfig,
  onEnsureDefaultStaffLink,
  onEnsureDefaultAILink,
  onSave,
}: SiteRegistrationConfigPanelProps): JSX.Element {
  const [form] = Form.useForm<SiteRegistrationConfig>();
  const [saving, setSaving] = useState(false);
  const [ensuring, setEnsuring] = useState<"staff" | "ai" | null>(null);
  const [config, setConfig] = useState<SiteRegistrationConfig | null>(initialConfig);

  useEffect(() => {
    setConfig(initialConfig);
    if (initialConfig) {
      form.setFieldsValue(initialConfig);
    }
  }, [initialConfig, form]);

  const staffLinkUrl = config?.default_staff_entry_link_id
    ? `${window.location.origin}/h5/register?code=${config.default_staff_entry_link_id}`
    : "";
  const aiLinkUrl = config?.default_ai_entry_link_id
    ? `${window.location.origin}/h5/register?code=${config.default_ai_entry_link_id}`
    : "";
  const waLink = `${window.location.origin}/h5/${siteKey}/whatsapp/ai`;

  const handleSubmit = async (values: SiteRegistrationConfig) => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(values);
      setConfig(values);
      message.success("已保存站点注册与归属配置");
    } catch (err) {
      message.error(`保存失败：${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleEnsureStaff = async () => {
    if (!onEnsureDefaultStaffLink) return;
    setEnsuring("staff");
    try {
      const result = await onEnsureDefaultStaffLink();
      if (result?.link_id) {
        form.setFieldValue("default_staff_entry_link_id", result.link_id);
        setConfig((prev) => ({ ...(prev ?? {}), default_staff_entry_link_id: result.link_id }));
        message.success("默认客服链接已确保");
      }
    } catch (err) {
      message.error(`操作失败：${(err as Error).message}`);
    } finally {
      setEnsuring(null);
    }
  };

  const handleEnsureAI = async () => {
    if (!onEnsureDefaultAILink) return;
    setEnsuring("ai");
    try {
      const result = await onEnsureDefaultAILink();
      if (result?.link_id) {
        form.setFieldValue("default_ai_entry_link_id", result.link_id);
        setConfig((prev) => ({ ...(prev ?? {}), default_ai_entry_link_id: result.link_id }));
        message.success("默认 AI 链接已确保");
      }
    } catch (err) {
      message.error(`操作失败：${(err as Error).message}`);
    } finally {
      setEnsuring(null);
    }
  };

  return (
    <Card
      size="small"
      title="注册与归属配置"
      style={{ marginBottom: 16 }}
      extra={
        <Space>
          {canManage && onEnsureDefaultStaffLink ? (
            <Button
              size="small"
              icon={<LinkOutlined />}
              loading={ensuring === "staff"}
              onClick={() => void handleEnsureStaff()}
            >
              确保默认客服链接
            </Button>
          ) : null}
          {canManage && onEnsureDefaultAILink ? (
            <Button
              size="small"
              icon={<LinkOutlined />}
              loading={ensuring === "ai"}
              onClick={() => void handleEnsureAI()}
            >
              确保默认 AI 链接
            </Button>
          ) : null}
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="站点注册与归属规则：影响 H5 会员注册、AI 接待绑定、划转 / failover 行为。"
      />
      <Form<SiteRegistrationConfig>
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        disabled={!canManage}
        initialValues={initialConfig ?? {}}
      >
        <Space size="large" wrap>
          <Form.Item name="registration_entry_required" label="必须入口码" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="allow_invite_code_alias" label="允许 invite_code 别名" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="allow_unattributed_waba_inbound" label="允许未归属 WABA 入站" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="member_invite_inherits_human_owner" label="会员邀请继承客服" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="member_invite_inherits_ai" label="会员邀请继承 AI" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Space>
        <Space size="large" wrap>
          <Form.Item name="default_staff_entry_link_id" label="默认客服 EntryLink">
            <Input placeholder="entry-link-id" style={{ minWidth: 280 }} />
          </Form.Item>
          <Form.Item name="default_ai_agent_id" label="默认 AI Agent">
            <Input placeholder="ai-agent-id" style={{ minWidth: 240 }} />
          </Form.Item>
          <Form.Item name="default_ai_entry_link_id" label="默认 AI EntryLink">
            <Input placeholder="entry-link-id" style={{ minWidth: 280 }} />
          </Form.Item>
        </Space>
        <Space size="large" wrap>
          <Form.Item name="existing_member_link_override_policy" label="既有会员链接覆盖策略">
            <Select options={OVERRIDE_POLICIES} style={{ minWidth: 200 }} />
          </Form.Item>
          <Form.Item name="ai_failover_policy" label="AI failover 策略">
            <Select options={FAILOVER_POLICIES} style={{ minWidth: 220 }} />
          </Form.Item>
          <Form.Item name="ai_failover_threshold_minutes" label="AI failover 阈值（分钟）">
            <InputNumber min={1} max={1440} style={{ minWidth: 160 }} />
          </Form.Item>
        </Space>
        {canManage && onSave ? (
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={saving}
            onClick={() => form.submit()}
          >
            保存配置
          </Button>
        ) : null}
      </Form>
      <Space wrap style={{ marginTop: 16 }}>
        <Button
          icon={<CopyOutlined />}
          onClick={() => copyToClipboard(staffLinkUrl, "默认客服注册链接")}
          disabled={!staffLinkUrl}
        >
          复制站点总客服注册链接
        </Button>
        <Button
          icon={<CopyOutlined />}
          onClick={() => copyToClipboard(aiLinkUrl, "默认 AI 注册链接")}
          disabled={!aiLinkUrl}
        >
          复制站点总 AI 注册链接
        </Button>
        <Button icon={<CopyOutlined />} onClick={() => copyToClipboard(waLink, "WhatsApp AI 对话链接")}>
          复制站点 WhatsApp AI 对话链接
        </Button>
        <span style={{ fontSize: 12, color: "#999" }}>account: {accountId} · site: {siteKey}</span>
      </Space>
    </Card>
  );
}

export default SiteRegistrationConfigPanel;

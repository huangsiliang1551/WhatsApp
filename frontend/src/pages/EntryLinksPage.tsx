// EntryLinksPage：入口链接运营管理。
//
// 列表 / 筛选 / 创建 / 复制 / 撤销 / 轮换 / stats 全部接 mock + 真实 API。
// 不重复 InviteCode 管理（旧 InviteCode 仍由 InvitePage 承载，spec 8.2）。

import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";

import {
  createEntryLink as apiCreateEntryLink,
  getEntryLinkStats as apiFetchEntryLinkStats,
  listEntryLinks as apiListEntryLinks,
  revokeEntryLink as apiRevokeEntryLink,
  rotateEntryLink as apiRotateEntryLink,
} from "../services/entryLinks";
import type { EntryLink, EntryLinkStats } from "../types/entryLinks";

const LINK_TYPE_OPTIONS = [
  { value: "staff_register", label: "客服注册" },
  { value: "ai_register", label: "AI H5 注册" },
  { value: "ai_chat", label: "AI WhatsApp 对话" },
  { value: "staff_ai_register", label: "客服+AI 组合" },
  { value: "member_invite", label: "会员邀请入口" },
  { value: "site_default_staff", label: "站点总客服" },
  { value: "site_default_ai", label: "站点总 AI" },
  { value: "qr", label: "二维码" },
  { value: "ad", label: "广告链接" },
];

const STATUS_OPTIONS = [
  { value: "active", label: "活跃" },
  { value: "disabled", label: "已停用" },
  { value: "revoked", label: "已撤销" },
  { value: "expired", label: "已过期" },
  { value: "target_unavailable", label: "目标不可用" },
  { value: "usage_limit_reached", label: "已达上限" },
];

const TARGET_TYPE_OPTIONS = [
  { value: "staff", label: "客服" },
  { value: "ai_agent", label: "AI Agent" },
  { value: "staff_ai", label: "客服+AI 组合" },
  { value: "site", label: "站点" },
];

interface CreateFormValues {
  link_type: string;
  target_type: string;
  channel?: string;
  target_staff_user_id?: string;
  target_ai_agent_id?: string;
  site_id?: string;
  usage_limit?: number;
}

function copyToClipboard(text: string, label: string) {
  if (!text) {
    message.warning(`${label} 为空，无法复制`);
    return;
  }
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    navigator.clipboard
      .writeText(text)
      .then(() => message.success(`${label} 已复制到剪贴板`))
      .catch(() => message.info(`请手动复制：${text}`));
  } else {
    message.info(`请手动复制：${text}`);
  }
}

export function EntryLinksPage(): JSX.Element {
  const [filters, setFilters] = useState<{
    site_id?: string;
    link_type?: string;
    target_type?: string;
    target_staff_user_id?: string;
    target_ai_agent_id?: string;
    status?: string;
  }>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<CreateFormValues>();
  const [links, setLinks] = useState<EntryLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statsLinkId, setStatsLinkId] = useState<string | null>(null);
  const [statsData, setStatsData] = useState<EntryLinkStats | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiListEntryLinks(filters);
      setLinks(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!statsLinkId) {
      setStatsData(null);
      return;
    }
    let cancelled = false;
    void apiFetchEntryLinkStats(statsLinkId)
      .then((data) => {
        if (!cancelled) setStatsData(data);
      })
      .catch((err: Error) => message.error(`获取统计失败：${err.message}`));
    return () => {
      cancelled = true;
    };
  }, [statsLinkId]);

  useEffect(() => {
    if (statsData) {
      Modal.info({
        title: `链接 ${statsData.code} 统计`,
        content: (
          <div>
            <p>状态：{statsData.status}</p>
            <p>使用次数：{statsData.usage_count}</p>
            <p>使用上限：{statsData.usage_limit ?? "无限制"}</p>
            <p>最近使用：{statsData.last_used_at ?? "尚未使用"}</p>
          </div>
        ),
        onOk: () => setStatsLinkId(null),
        afterClose: () => setStatsLinkId(null),
      });
    }
  }, [statsData]);

  const handleCreate = useCallback(
    async (values: CreateFormValues) => {
      try {
        await apiCreateEntryLink({
          link_type: values.link_type,
          target_type: values.target_type,
          channel: values.channel,
          target_staff_user_id: values.target_staff_user_id,
          target_ai_agent_id: values.target_ai_agent_id,
          site_id: values.site_id,
          usage_limit: values.usage_limit,
        });
        message.success("入口链接已创建");
        setCreateOpen(false);
        createForm.resetFields();
        await refresh();
      } catch (err) {
        message.error(`创建失败：${(err as Error).message}`);
      }
    },
    [createForm, refresh]
  );

  const handleRevoke = useCallback(
    async (id: string) => {
      try {
        await apiRevokeEntryLink(id);
        message.success("已撤销");
        await refresh();
      } catch (err) {
        message.error(`撤销失败：${(err as Error).message}`);
      }
    },
    [refresh]
  );

  const handleRotate = useCallback(
    async (id: string) => {
      try {
        await apiRotateEntryLink(id);
        message.success("已轮换 code");
        await refresh();
      } catch (err) {
        message.error(`轮换失败：${(err as Error).message}`);
      }
    },
    [refresh]
  );

  const columns: ColumnsType<EntryLink> = useMemo(
    () => [
      { title: "Code", dataIndex: "code", key: "code", width: 120 },
      {
        title: "类型",
        dataIndex: "link_type",
        key: "link_type",
        width: 140,
        render: (v: string) => (
          <Tag color="blue">
            {LINK_TYPE_OPTIONS.find((o) => o.value === v)?.label ?? v}
          </Tag>
        ),
      },
      {
        title: "目标",
        dataIndex: "target_type",
        key: "target_type",
        width: 110,
        render: (v: string) => (
          <Tag color="purple">
            {TARGET_TYPE_OPTIONS.find((o) => o.value === v)?.label ?? v}
          </Tag>
        ),
      },
      { title: "目标客服", dataIndex: "target_staff_user_id", key: "staff", width: 130 },
      { title: "目标 AI", dataIndex: "target_ai_agent_id", key: "ai", width: 130 },
      { title: "站点", dataIndex: "site_id", key: "site", width: 130 },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (v: string) => (
          <Tag
            color={
              v === "active"
                ? "green"
                : v === "revoked"
                  ? "red"
                  : v === "expired"
                    ? "orange"
                    : "default"
            }
          >
            {STATUS_OPTIONS.find((o) => o.value === v)?.label ?? v}
          </Tag>
        ),
      },
      { title: "使用次数", dataIndex: "usage_count", key: "usage_count", width: 90 },
      { title: "最近使用", dataIndex: "last_used_at", key: "last_used_at", width: 160 },
      {
        title: "操作",
        key: "actions",
        fixed: "right" as const,
        width: 360,
        render: (_, record) => (
          <Space size="small" wrap>
            <Button
              size="small"
              onClick={() => copyToClipboard(record.h5_register_url ?? "", "H5 注册链接")}
            >
              复制 H5
            </Button>
            <Button
              size="small"
              onClick={() => copyToClipboard(record.whatsapp_chat_url ?? "", "WhatsApp 链接")}
            >
              复制 WhatsApp
            </Button>
            <Button size="small" onClick={() => setStatsLinkId(record.id)}>
              stats
            </Button>
            <Button size="small" onClick={() => handleRotate(record.id)}>
              rotate
            </Button>
            <Popconfirm
              title="确定撤销？"
              okText="撤销"
              cancelText="取消"
              onConfirm={() => handleRevoke(record.id)}
            >
              <Button size="small" danger>
                revoke
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleRevoke, handleRotate]
  );

  return (
    <section style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>入口链接运营管理</h2>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="EntryLink 是新的一等主体。客服注册链接 / AI H5 注册链接 / AI WhatsApp 对话链接 / 站点总链接 / 二维码 / 广告链接均在此管理。旧 InviteCode 仍由邀请页承载。"
      />
      {error ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message={`加载失败：${error}`}
          action={
            <Button size="small" onClick={() => void refresh()}>
              重试
            </Button>
          }
        />
      ) : null}
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="类型"
          style={{ width: 160 }}
          value={filters.link_type}
          onChange={(v) => setFilters((s) => ({ ...s, link_type: v }))}
          options={LINK_TYPE_OPTIONS}
        />
        <Select
          allowClear
          placeholder="目标"
          style={{ width: 160 }}
          value={filters.target_type}
          onChange={(v) => setFilters((s) => ({ ...s, target_type: v }))}
          options={TARGET_TYPE_OPTIONS}
        />
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 140 }}
          value={filters.status}
          onChange={(v) => setFilters((s) => ({ ...s, status: v }))}
          options={STATUS_OPTIONS}
        />
        <Input
          allowClear
          placeholder="目标客服 ID"
          style={{ width: 160 }}
          value={filters.target_staff_user_id}
          onChange={(e) =>
            setFilters((s) => ({ ...s, target_staff_user_id: e.target.value || undefined }))
          }
        />
        <Input
          allowClear
          placeholder="目标 AI ID"
          style={{ width: 160 }}
          value={filters.target_ai_agent_id}
          onChange={(e) =>
            setFilters((s) => ({ ...s, target_ai_agent_id: e.target.value || undefined }))
          }
        />
        <Input
          allowClear
          placeholder="站点 ID"
          style={{ width: 160 }}
          value={filters.site_id}
          onChange={(e) => setFilters((s) => ({ ...s, site_id: e.target.value || undefined }))}
        />
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          新建链接
        </Button>
      </Space>
      <Table<EntryLink>
        rowKey="id"
        loading={loading}
        dataSource={links}
        columns={columns}
        scroll={{ x: 1200 }}
        pagination={{ pageSize: 20, showSizeChanger: true }}
      />
      <Modal
        open={createOpen}
        title="新建入口链接"
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        destroyOnClose
      >
        <Form<CreateFormValues>
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ channel: "h5", target_type: "staff", link_type: "staff_register" }}
        >
          <Form.Item name="link_type" label="链接类型" rules={[{ required: true }]}>
            <Select options={LINK_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="target_type" label="目标类型" rules={[{ required: true }]}>
            <Select options={TARGET_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="channel" label="渠道">
            <Select
              options={[
                { value: "h5", label: "H5" },
                { value: "whatsapp", label: "WhatsApp" },
                { value: "qr", label: "QR" },
                { value: "ad", label: "广告" },
                { value: "manual", label: "手工" },
              ]}
            />
          </Form.Item>
          <Form.Item name="target_staff_user_id" label="目标客服 ID">
            <Input placeholder="staff-uuid" />
          </Form.Item>
          <Form.Item name="target_ai_agent_id" label="目标 AI ID">
            <Input placeholder="ai-agent-uuid" />
          </Form.Item>
          <Form.Item name="site_id" label="站点 ID">
            <Input placeholder="site-uuid（可选）" />
          </Form.Item>
          <Form.Item name="usage_limit" label="使用上限">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
}

export default EntryLinksPage;

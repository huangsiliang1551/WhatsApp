import { Button, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { DangerButton, showError, showSuccess } from "../components/Feedback";
import { usePageData } from "../hooks/usePageData";
import {
  api,
  deletePlatformUser,
  listPlatformUsers,
  updatePlatformUser,
  type PlatformUser,
} from "../services/api";
import {
  getPlatformUserMemberStatusSnapshot,
  listPlatformUserMemberStatusIndex,
  type PlatformUserMemberStatusSnapshot,
  type PlatformUserMemberStatusSummary,
} from "../services/operations";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import { useAppStore } from "../stores/appStore";

const LC_COLORS: Record<string, string> = {
  active: "#52c41a",
  inactive: "#d9d9d9",
  new: "#1677ff",
  churned: "#999",
  dormant: "#faad14",
};

const LC_LABELS: Record<string, string> = {
  active: "活跃",
  inactive: "不活跃",
  new: "新用户",
  churned: "流失",
  dormant: "休眠",
};

const LANGUAGE_OPTIONS = [
  { label: "中文", value: "zh-CN" },
  { label: "English", value: "en" },
  { label: "Español", value: "es" },
  { label: "Français", value: "fr" },
];

function renderMemberStatus(value: string | null): JSX.Element {
  if (!value) return <Tag>-</Tag>;
  const color =
    value === "approved" || value === "bound"
      ? "green"
      : value === "rejected" || value === "failed"
        ? "red"
        : "blue";
  return <Tag color={color}>{value}</Tag>;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-CN");
}

export function UsersPage(): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<PlatformUser | null>(null);
  const [selectedUserMemberStatus, setSelectedUserMemberStatus] = useState<PlatformUserMemberStatusSnapshot | null>(null);
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [sites, setSites] = useState<H5Site[]>([]);
  const [createForm] = Form.useForm<{ display_name: string; language_code: string; role: string }>();
  const [editForm] = Form.useForm<{ display_name?: string; language_code?: string }>();

  useEffect(() => {
    listSites().then(setSites).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    const users = await listPlatformUsers();
    const userMemberStatusIndex = await listPlatformUserMemberStatusIndex(
      users.map((item) => ({
        id: item.id,
        account_id: item.account_id,
        public_user_id: item.public_user_id,
      }))
    );
    return { users, userMemberStatusIndex };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });
  const users = data?.users ?? [];
  const userMemberStatusIndex: Record<string, PlatformUserMemberStatusSummary> = data?.userMemberStatusIndex ?? {};

  useEffect(() => {
    if (!selectedUser) {
      setSelectedUserMemberStatus(null);
      return;
    }

    getPlatformUserMemberStatusSnapshot({
      id: selectedUser.id,
      account_id: selectedUser.account_id,
      public_user_id: selectedUser.public_user_id,
    })
      .then(setSelectedUserMemberStatus)
      .catch(() => setSelectedUserMemberStatus(null));
  }, [selectedUser]);

  const handleDeleteUser = useCallback(
    async (userId: string) => {
      try {
        await deletePlatformUser(userId);
        showSuccess("用户已删除");
        if (selectedUser?.id === userId) {
          setSelectedUser(null);
        }
        await reload();
      } catch {
        showError("删除失败");
      }
    },
    [reload, selectedUser]
  );

  const handleCreateUser = useCallback(
    async (values: { display_name: string; language_code: string; role: string }) => {
      setCreating(true);
      try {
        await api.post("/api/platform/users", {
          public_user_id: `user_${Date.now()}`,
          display_name: values.display_name,
          language_code: values.language_code,
          is_anonymous: false,
          lifecycle_status: "new",
          restrict_task_claim: false,
          identities: [],
          tag_keys: [],
        });
        message.success("用户创建成功");
        setCreateModalOpen(false);
        createForm.resetFields();
        await reload();
      } catch (loadError) {
        message.error(loadError instanceof Error ? loadError.message : "创建用户失败");
      } finally {
        setCreating(false);
      }
    },
    [createForm, reload]
  );

  const handleStartEdit = useCallback(
    (user: PlatformUser) => {
      setSelectedUser(user);
      editForm.setFieldsValue({
        display_name: user.display_name ?? "",
        language_code: user.language_code ?? "",
      });
      setEditModalOpen(true);
    },
    [editForm]
  );

  const handleUpdateUser = useCallback(
    async (values: { display_name?: string; language_code?: string }) => {
      if (!selectedUser) return;

      setUpdating(true);
      try {
        await updatePlatformUser(selectedUser.id, values);
        message.success("用户更新成功");
        setEditModalOpen(false);
        await reload();
      } catch (loadError) {
        message.error(loadError instanceof Error ? loadError.message : "更新用户失败");
      } finally {
        setUpdating(false);
      }
    },
    [reload, selectedUser]
  );

  const handleOpenCustomerPage = useCallback(
    (user: PlatformUser) => {
      openCustomersPage({
        account_id: user.account_id ?? undefined,
        selected_profile_id: user.id,
        query: user.public_user_id,
      });
    },
    [openCustomersPage]
  );

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }} wrap>
      <span>
        总数 <Typography.Text strong>{users.length}</Typography.Text>
      </span>
      <span>
        活跃 <Typography.Text strong style={{ color: "#52c41a" }}>{users.filter((item) => item.lifecycle_status === "active").length}</Typography.Text>
      </span>
      <span>
        匿名 <Typography.Text strong>{users.filter((item) => item.is_anonymous).length}</Typography.Text>
      </span>
      <span>
        新用户 <Typography.Text strong style={{ color: "#1677ff" }}>{users.filter((item) => item.is_new_user).length}</Typography.Text>
      </span>
    </Space>
  );

  const actions = (
    <Space>
      <Button onClick={() => setCreateModalOpen(true)} size="small" type="primary">
        创建用户
      </Button>
      <Button loading={loading} onClick={() => void reload()} size="small">
        刷新
      </Button>
    </Space>
  );

  const columns = [
    {
      title: "用户 ID",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 150,
      ellipsis: true,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.public_user_id ?? "").localeCompare(right.public_user_id ?? ""),
    },
    {
      title: "显示名称",
      dataIndex: "display_name",
      key: "display_name",
      width: 150,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.display_name ?? "").localeCompare(right.display_name ?? ""),
      render: (value: string | null, record: PlatformUser) => (
        <Button onClick={() => setSelectedUser(record)} size="small" type="link">
          {value || record.public_user_id}
        </Button>
      ),
    },
    {
      title: "状态",
      dataIndex: "lifecycle_status",
      key: "lifecycle_status",
      width: 100,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.lifecycle_status ?? "").localeCompare(right.lifecycle_status ?? ""),
      render: (value: string) => <Tag color={LC_COLORS[value] ?? "default"}>{LC_LABELS[value] ?? value}</Tag>,
    },
    {
      title: "会员认证",
      key: "verification_status",
      width: 120,
      render: (_: unknown, record: PlatformUser) =>
        renderMemberStatus(userMemberStatusIndex[record.id]?.latestVerificationStatus ?? null),
    },
    {
      title: "WhatsApp 绑定",
      key: "binding_status",
      width: 140,
      render: (_: unknown, record: PlatformUser) =>
        renderMemberStatus(userMemberStatusIndex[record.id]?.latestBindingStatus ?? null),
    },
    {
      title: "账号",
      dataIndex: "account_id",
      key: "account_id",
      width: 120,
      ellipsis: true,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.account_id ?? "").localeCompare(right.account_id ?? ""),
      render: (value: string | null) => value || "-",
    },
    {
      title: "注册站点",
      dataIndex: "registration_site_id",
      key: "registration_site_id",
      width: 150,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.registration_site_id ?? "").localeCompare(right.registration_site_id ?? ""),
      render: (siteId: string | null) => {
        if (!siteId) return "-";
        const site = sites.find((item) => item.id === siteId);
        return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
      },
    },
    {
      title: "语言",
      dataIndex: "language_code",
      key: "language_code",
      width: 100,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        (left.language_code ?? "").localeCompare(right.language_code ?? ""),
    },
    {
      title: "WhatsApp",
      dataIndex: "has_whatsapp",
      key: "has_whatsapp",
      width: 90,
      sorter: (left: PlatformUser, right: PlatformUser) => Number(left.has_whatsapp) - Number(right.has_whatsapp),
      render: (value: boolean) => (value ? "是" : "否"),
    },
    {
      title: "邮箱",
      dataIndex: "has_email",
      key: "has_email",
      width: 90,
      sorter: (left: PlatformUser, right: PlatformUser) => Number(left.has_email) - Number(right.has_email),
      render: (value: boolean) => (value ? "是" : "否"),
    },
    {
      title: "手机",
      dataIndex: "has_phone",
      key: "has_phone",
      width: 90,
      sorter: (left: PlatformUser, right: PlatformUser) => Number(left.has_phone) - Number(right.has_phone),
      render: (value: boolean) => (value ? "是" : "否"),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 140,
      sorter: (left: PlatformUser, right: PlatformUser) =>
        new Date(left.created_at ?? 0).getTime() - new Date(right.created_at ?? 0).getTime(),
      render: (value: string) => formatDate(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 190,
      render: (_: unknown, record: PlatformUser) => (
        <Space size={4}>
          <Button onClick={() => handleStartEdit(record)} size="small" type="link">
            编辑
          </Button>
          <Button onClick={() => handleOpenCustomerPage(record)} size="small" type="link">
            客户页
          </Button>
          <DangerButton
            confirmDescription={`将删除用户 ${record.public_user_id}`}
            confirmTitle="确认删除该用户？"
            danger
            label="删除"
            onConfirm={() => handleDeleteUser(record.id)}
            type="text"
          />
        </Space>
      ),
    },
  ];

  if (!users.length && !loading) {
    return (
      <PageShell actions={actions} stats={stats} subtitle="查看和管理平台用户" title="用户管理">
        <EmptyGuide description="当前还没有可管理的用户记录。" icon="👤" title="暂无用户" />
      </PageShell>
    );
  }

  return (
    <PageShell actions={actions} stats={stats} subtitle="查看和管理平台用户" title="用户管理">
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Table
        columns={columns}
        dataSource={users}
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        rowKey="id"
        scroll={{ y: "calc(100vh - 320px)", x: 1400 }}
        size="small"
      />

      {selectedUser ? (
        <div style={{ border: "1px solid #f0f0f0", borderRadius: 8, marginTop: 16, padding: 16 }}>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            用户详情
          </Typography.Title>
          <Space direction="vertical" size={6}>
            <Typography.Text>用户：{selectedUser.public_user_id}</Typography.Text>
            <Typography.Text>账号：{selectedUser.account_id || "-"}</Typography.Text>
            <Typography.Text>
              会员认证状态：{selectedUserMemberStatus?.verificationRequests[0]?.status ?? "暂无"}
            </Typography.Text>
            <Typography.Text>
              WhatsApp 绑定状态：{selectedUserMemberStatus?.bindingRequests[0]?.status ?? "暂无"}
            </Typography.Text>
            <Space>
              <Button onClick={() => handleOpenCustomerPage(selectedUser)} size="small">
                打开客户页
              </Button>
              <Button onClick={() => handleStartEdit(selectedUser)} size="small">
                编辑用户
              </Button>
            </Space>
          </Space>
        </div>
      ) : null}

      <Modal
        cancelText="取消"
        confirmLoading={creating}
        okText="创建"
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        onOk={() => void createForm.submit()}
        open={createModalOpen}
        title="创建用户"
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreateUser}>
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: "请输入显示名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="语言" name="language_code" rules={[{ required: true, message: "请选择语言" }]}>
            <Select options={LANGUAGE_OPTIONS} />
          </Form.Item>
          <Form.Item label="角色" name="role" rules={[{ required: true, message: "请选择角色" }]}>
            <Select
              options={[
                { label: "管理员", value: "admin" },
                { label: "运营", value: "operator" },
                { label: "客服", value: "agent" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        cancelText="取消"
        confirmLoading={updating}
        okText="保存"
        onCancel={() => setEditModalOpen(false)}
        onOk={() => void editForm.submit()}
        open={editModalOpen}
        title={`编辑用户 - ${selectedUser?.public_user_id ?? ""}`}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdateUser}>
          <Form.Item label="显示名称" name="display_name">
            <Input />
          </Form.Item>
          <Form.Item label="语言" name="language_code">
            <Select allowClear options={LANGUAGE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}

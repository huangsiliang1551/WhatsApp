import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tabs, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";

import { PageShell } from "../components/PageShell";
import { showError, showSuccess } from "../components/Feedback";
import { usePageData } from "../hooks/usePageData";
import { useAppStore } from "../stores/appStore";
import {
  approveTaskReview,
  createTaskTemplate,
  listMetaAccounts,
  listTaskInstances,
  listTaskTemplates,
  rejectTaskReview,
  type TaskInstance,
  type TaskTemplate,
} from "../services/api";
import {
  listPlatformUserMemberStatusIndex,
  type PlatformUserMemberStatusSummary,
} from "../services/operations";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";

const TPL_STATUS_COLORS: Record<string, string> = { active: "green", draft: "default", disabled: "red" };
const TPL_STATUS_LABELS: Record<string, string> = { active: "启用", draft: "草稿", disabled: "停用" };
const INST_STATUS_COLORS: Record<string, string> = {
  pending: "default",
  claimed: "blue",
  submitted: "orange",
  approved: "green",
  rejected: "red",
  completed: "green",
  expired: "default",
};
const INST_STATUS_LABELS: Record<string, string> = {
  pending: "待领取",
  claimed: "进行中",
  submitted: "待审核",
  approved: "已完成",
  rejected: "已拒绝",
  completed: "已完成",
  expired: "已过期",
};

function renderMemberTag(status: string | null | undefined): JSX.Element {
  if (!status) {
    return <Tag>-</Tag>;
  }
  const color = status === "approved" || status === "bound" ? "green" : status === "rejected" || status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
}

export function TasksPage(): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);

  const [activeTab, setActiveTab] = useState("templates");
  const [accounts, setAccounts] = useState<Array<{ account_id: string; display_name: string }>>([]);
  const [sites, setSites] = useState<H5Site[]>([]);
  const [tplFilterAccount, setTplFilterAccount] = useState<string | undefined>();
  const [tplFilterType, setTplFilterType] = useState<string | undefined>();
  const [tplFilterStatus, setTplFilterStatus] = useState<string | undefined>();
  const [instFilterAccount, setInstFilterAccount] = useState<string | undefined>();
  const [instFilterStatus, setInstFilterStatus] = useState<string | undefined>();
  const [instSearchUser, setInstSearchUser] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listSites().then(setSites).catch(() => {});
    listMetaAccounts({}).then(setAccounts).catch(() => {});
  }, []);

  const accountOptions = useMemo(
    () => accounts.map((item) => ({ label: item.display_name, value: item.account_id })),
    [accounts],
  );

  const fetchTemplates = useCallback(async () => {
    const templates = await listTaskTemplates({
      account_id: tplFilterAccount,
      status: tplFilterStatus,
      task_type: tplFilterType,
    });
    return { templates };
  }, [tplFilterAccount, tplFilterStatus, tplFilterType]);
  const tplData = usePageData({ fetcher: fetchTemplates });
  const templates = tplData.data?.templates ?? [];

  const fetchInstances = useCallback(async () => {
    const instances = await listTaskInstances({
      account_id: instFilterAccount,
      status: instFilterStatus,
    });
    const taskInstanceMemberStatusIndex = await listPlatformUserMemberStatusIndex(
      instances.map((record) => ({
        id: record.user_id,
        account_id: record.account_id,
        public_user_id: record.public_user_id,
      })),
      instFilterAccount,
    );
    return { instances, taskInstanceMemberStatusIndex };
  }, [instFilterAccount, instFilterStatus]);
  const instData = usePageData({ fetcher: fetchInstances, deps: [instFilterAccount, instFilterStatus]});
  const instances = instData.data?.instances ?? [];
  const taskInstanceMemberStatusIndex: Record<string, PlatformUserMemberStatusSummary> = instData.data?.taskInstanceMemberStatusIndex ?? {};

  const fetchReviews = useCallback(async () => {
    const reviews = await listTaskInstances({ status: "submitted" });
    return { reviews };
  }, []);
  const reviewData = usePageData({ fetcher: fetchReviews });
  const reviews = reviewData.data?.reviews ?? [];

  const filteredInstances = useMemo(() => {
    if (!instSearchUser.trim()) {
      return instances;
    }
    const query = instSearchUser.toLowerCase();
    return instances.filter((item) => item.public_user_id.toLowerCase().includes(query));
  }, [instances, instSearchUser]);

  const handleCreateTemplate = async (values: { name: string; task_type: string; account_id?: string; reward_amount?: number; description?: string }): Promise<void> => {
    setCreating(true);
    try {
      await createTaskTemplate({
        account_id: values.account_id,
        task_key: `tpl-${Date.now()}`,
        name: values.name,
        title: values.name,
        description: values.description,
        task_type: values.task_type,
        status: "draft",
        reward_amount: values.reward_amount?.toString(),
        reward_points: 0,
        claim_timeout_seconds: 86400,
        auto_review_enabled: false,
      });
      showSuccess("模板已创建");
      setCreateModalOpen(false);
      createForm.resetFields();
      void tplData.reload();
    } catch {
      showError("创建失败");
    } finally {
      setCreating(false);
    }
  };

  const handleApprove = async (instance: TaskInstance): Promise<void> => {
    try {
      await approveTaskReview(instance.id);
      showSuccess(`${instance.public_user_id} 审核通过`);
      void reviewData.reload();
    } catch {
      showError("审核通过失败");
    }
  };

  const handleReject = async (instance: TaskInstance): Promise<void> => {
    try {
      await rejectTaskReview(instance.id);
      showSuccess(`${instance.public_user_id} 审核拒绝`);
      void reviewData.reload();
    } catch {
      showError("审核拒绝失败");
    }
  };

  const handleOpenCustomerPage = (record: { account_id: string | null; user_id: string; public_user_id: string }): void => {
    openCustomersPage({
      account_id: record.account_id ?? undefined,
      selected_profile_id: record.user_id,
      query: record.public_user_id,
    });
  };

  const tplStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>总模板 <Typography.Text strong>{templates.length}</Typography.Text></span>
      <span>启用 <Typography.Text strong style={{ color: "#52c41a" }}>{templates.filter((item) => item.status === "active").length}</Typography.Text></span>
      <span>草稿 <Typography.Text strong>{templates.filter((item) => item.status === "draft").length}</Typography.Text></span>
      <span>停用 <Typography.Text strong style={{ color: "#ff4d4f" }}>{templates.filter((item) => item.status === "disabled").length}</Typography.Text></span>
    </Space>
  );

  const instStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>总实例 <Typography.Text strong>{filteredInstances.length}</Typography.Text></span>
      <span>待领取 <Typography.Text strong>{filteredInstances.filter((item) => item.status === "pending").length}</Typography.Text></span>
      <span>进行中 <Typography.Text strong style={{ color: "#1677ff" }}>{filteredInstances.filter((item) => item.status === "claimed").length}</Typography.Text></span>
      <span>已完成 <Typography.Text strong style={{ color: "#52c41a" }}>{filteredInstances.filter((item) => item.status === "approved" || item.status === "completed").length}</Typography.Text></span>
      <span>已拒绝 <Typography.Text strong style={{ color: "#ff4d4f" }}>{filteredInstances.filter((item) => item.status === "rejected").length}</Typography.Text></span>
    </Space>
  );

  const reviewStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>待审核 <Typography.Text strong style={{ color: "#faad14" }}>{reviews.length}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      <Button size="small" icon={<ReloadOutlined />} onClick={() => { void tplData.reload(); void instData.reload(); void reviewData.reload(); }}>刷新</Button>
    </Space>
  );

  // title: "浼氬憳璁よ瘉"
  // title: "WhatsApp 缁戝畾"

  const tplColumns = [
    { title: "模板 Key", dataIndex: "task_key", key: "task_key", width: 140, ellipsis: true },
    { title: "名称", dataIndex: "name", key: "name", width: 140, ellipsis: true },
    { title: "类型", dataIndex: "task_type", key: "task_type", width: 100 },
    { title: "状态", dataIndex: "status", key: "status", width: 100, render: (value: string) => <Tag color={TPL_STATUS_COLORS[value] ?? "default"}>{TPL_STATUS_LABELS[value] ?? value}</Tag> },
    { title: "奖励", dataIndex: "reward_amount", key: "reward_amount", width: 100, render: (value: string | null) => value ? `￥${value}` : "-" },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 140, render: (value: string) => new Date(value).toLocaleDateString("zh-CN") },
  ];

  const instColumns = [
    { title: "实例 ID", dataIndex: "id", key: "id", width: 160, ellipsis: true, render: (value: string) => <Typography.Text copyable style={{ fontSize: 12 }}>{value.slice(0, 16)}...</Typography.Text> },
    { title: "模板", dataIndex: "template_name", key: "template_name", width: 120, ellipsis: true },
    { title: "用户", dataIndex: "public_user_id", key: "public_user_id", width: 120 },
    {
      title: "用户来源",
      dataIndex: "site_key",
      key: "site_key",
      width: 130,
      render: (siteKey: string | null) => {
        if (!siteKey) {
          return "-";
        }
        const site = sites.find((item) => item.site_key === siteKey);
        return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
      },
    },
    { title: "状态", dataIndex: "status", key: "status", width: 100, render: (value: string) => <Tag color={INST_STATUS_COLORS[value] ?? "default"}>{INST_STATUS_LABELS[value] ?? value}</Tag> },
    { title: "会员认证", key: "verification_status", width: 120, render: (_: unknown, record: { user_id: string }) => renderMemberTag(taskInstanceMemberStatusIndex[record.user_id]?.latestVerificationStatus) },
    { title: "WhatsApp 绑定", key: "binding_status", width: 140, render: (_: unknown, record: { user_id: string }) => renderMemberTag(taskInstanceMemberStatusIndex[record.user_id]?.latestBindingStatus) },
    { title: "领取时间", dataIndex: "claimed_at", key: "claimed_at", width: 140, render: (value: string | null) => value ? new Date(value).toLocaleDateString("zh-CN") : "-" },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: unknown, record: { account_id: string | null; user_id: string; public_user_id: string }) => (
        <Button size="small" onClick={() => handleOpenCustomerPage(record)}>客户页</Button>
      ),
    },
  ];

  const reviewColumns = [
    { title: "实例 ID", dataIndex: "id", key: "id", width: 160, ellipsis: true, render: (value: string) => <Typography.Text copyable style={{ fontSize: 12 }}>{value.slice(0, 16)}...</Typography.Text> },
    { title: "模板", dataIndex: "template_name", key: "template_name", width: 120, ellipsis: true },
    { title: "用户", dataIndex: "public_user_id", key: "public_user_id", width: 120 },
    { title: "提交时间", dataIndex: "submitted_at", key: "submitted_at", width: 140, render: (value: string | null) => value ? new Date(value).toLocaleDateString("zh-CN") : "-" },
    {
      title: "操作",
      key: "actions",
      width: 160,
      render: (_: unknown, record: TaskInstance) => (
        <Space size={4}>
          <Button size="small" type="primary" style={{ fontSize: 11 }} onClick={() => void handleApprove(record)}>通过</Button>
          <Button size="small" danger style={{ fontSize: 11 }} onClick={() => void handleReject(record)}>拒绝</Button>
        </Space>
      ),
    },
  ];

  const renderTemplates = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select placeholder="全部账号" allowClear style={{ width: 160 }} value={tplFilterAccount} onChange={(value) => { setTplFilterAccount(value); void tplData.reload(); }} options={accountOptions} />
        <Select placeholder="类型" allowClear style={{ width: 120 }} value={tplFilterType} onChange={(value) => { setTplFilterType(value); void tplData.reload(); }} options={[{ label: "每日", value: "daily" }, { label: "分享", value: "share" }, { label: "视频", value: "video" }, { label: "自定义", value: "custom" }]} />
        <Select placeholder="状态" allowClear style={{ width: 120 }} value={tplFilterStatus} onChange={(value) => { setTplFilterStatus(value); void tplData.reload(); }} options={Object.entries(TPL_STATUS_LABELS).map(([key, value]) => ({ label: value, value: key }))} />
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>创建模板</Button>
      </Space>
      {tplData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{tplData.error}</Typography.Text> : null}
      <Table dataSource={templates} columns={withSorter(tplColumns)} rowKey="id" size="small" loading={tplData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 440px)" }} />
    </div>
  );

  const renderInstances = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select placeholder="全部账号" allowClear style={{ width: 160 }} value={instFilterAccount} onChange={(value) => { setInstFilterAccount(value); void instData.reload(); }} options={accountOptions} />
        <Select placeholder="状态" allowClear style={{ width: 120 }} value={instFilterStatus} onChange={(value) => { setInstFilterStatus(value); void instData.reload(); }} options={Object.entries(INST_STATUS_LABELS).map(([key, value]) => ({ label: value, value: key }))} />
        <Input placeholder="搜索用户 ID" prefix={<SearchOutlined />} allowClear style={{ width: 180 }} value={instSearchUser} onChange={(event) => setInstSearchUser(event.target.value)} />
      </Space>
      {instData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{instData.error}</Typography.Text> : null}
      <Table dataSource={filteredInstances} columns={withSorter(instColumns)} rowKey="id" size="small" loading={instData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 440px)" }} />
    </div>
  );

  const renderReviews = (): JSX.Element => (
    <div>
      {reviewData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{reviewData.error}</Typography.Text> : null}
      {reviews.length === 0 && !reviewData.loading ? (
        <Empty description="暂无待审核提交" />
      ) : (
        <Table dataSource={reviews} columns={withSorter(reviewColumns)} rowKey="id" size="small" loading={reviewData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 380px)" }} />
      )}
    </div>
  );

  const currentStats = activeTab === "templates" ? tplStats : activeTab === "instances" ? instStats : reviewStats;

  return (
    <PageShell title="任务管理" subtitle="管理任务模板、监控实例进度、审核用户提交" actions={actions} stats={currentStats}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: "templates", label: "任务模板", children: renderTemplates() },
          { key: "instances", label: "任务实例", children: renderInstances() },
          { key: "reviews", label: "审核", children: renderReviews() },
        ]}
        size="small"
      />

      <Modal title="创建任务模板" open={createModalOpen} onCancel={() => { setCreateModalOpen(false); createForm.resetFields(); }} onOk={() => createForm.submit()} confirmLoading={creating} okText="创建" cancelText="取消">
        <Form form={createForm} layout="vertical" onFinish={handleCreateTemplate}>
          <Form.Item label="任务名称" name="name" rules={[{ required: true, message: "请输入任务名称" }]}>
            <Input placeholder="例如：每日签到" />
          </Form.Item>
          <Form.Item label="任务类型" name="task_type" rules={[{ required: true, message: "请选择任务类型" }]}>
            <Select options={[{ label: "每日签到 (daily)", value: "daily" }, { label: "分享推广 (share)", value: "share" }, { label: "看视频 (video)", value: "video" }, { label: "自定义 (custom)", value: "custom" }]} placeholder="选择类型" />
          </Form.Item>
          <Form.Item label="账号" name="account_id">
            <Select allowClear placeholder="选择账号" options={accountOptions} />
          </Form.Item>
          <Form.Item label="奖励金额 (￥)" name="reward_amount">
            <InputNumber min={0} step={0.5} style={{ width: "100%" }} placeholder="例如：2.00" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="任务描述" />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}

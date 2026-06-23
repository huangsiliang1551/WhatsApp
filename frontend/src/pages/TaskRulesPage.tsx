import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Modal, Row, Select, Space, Statistic, Table, Tabs, Tag, TimePicker, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, ReloadOutlined, MinusCircleOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { useAppStore } from "../stores/appStore";
import {
  listTaskRules, createTaskRule, updateTaskRule, toggleTaskRule, deleteTaskRule,
  getSignInConfig, updateSignInConfig,
  getInviteConfig, updateInviteConfig,
  getMarketingStats, listPackages,
} from "../services/marketingApi";
import type { TaskRule, TaskRuleFollowUp, SignInConfig, InviteConfig, MarketingStats, ProductPackage } from "../services/marketingApi";

const TRIGGER_OPTIONS = [
  { label: "注册触发", value: "register" },
  { label: "充值触发", value: "recharge" },
  { label: "定时推送", value: "schedule" },
  { label: "完成后续推", value: "follow_up" },
  { label: "手动推送", value: "manual" },
];

const EXPIRY_OPTIONS = [
  { label: "每日 0:00 重置", value: "daily_reset" },
  { label: "永不重置", value: "none" },
  { label: "7天后过期", value: "7d_expire" },
  { label: "30天后过期", value: "30d_expire" },
];

// ── Push Rules Tab ──

function PushRulesTab({ packages }: { packages: ProductPackage[] }): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<TaskRule | null>(null);
  const [triggerType, setTriggerType] = useState<string>("register");
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchRules = useCallback(async () => {
    const rules = await listTaskRules();
    return { rules };
  }, []);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchRules });
  const rules = data?.rules ?? [];

  const pkgOptions = useMemo(() => packages.map((p) => ({ label: p.name, value: p.id })), [packages]);

  const handleSave = async (values: {
    name: string;
    trigger_type: string;
    trigger_config: Record<string, unknown>;
    package_id: string;
    expiry_config: string;
    follow_up_chain: { delay_days: number; package_id: string }[];
  }) => {
    setSaving(true);
    try {
      const followUpChain: TaskRuleFollowUp[] = (values.follow_up_chain || []).map((f) => ({
        delay_days: f.delay_days,
        package_id: f.package_id,
        package_name: packages.find((p) => p.id === f.package_id)?.name ?? "",
      }));

      const payload = {
        name: values.name,
        trigger_type: values.trigger_type,
        trigger_config: values.trigger_config || {},
        package_id: values.package_id,
        package_name: packages.find((p) => p.id === values.package_id)?.name ?? "",
        expiry_config: values.expiry_config,
        follow_up_chain: followUpChain,
      };

      if (editingRule) {
        await updateTaskRule(editingRule.id, payload);
        showSuccess("规则已更新");
      } else {
        await createTaskRule(payload);
        showSuccess("规则已创建");
      }
      setModalOpen(false);
      form.resetFields();
      setTriggerType("register");
      void reload();
    } catch { showError("保存失败"); }
    finally { setSaving(false); }
  };

  const handleEdit = (rule: TaskRule) => {
    setEditingRule(rule);
    setTriggerType(rule.trigger_type);
    form.setFieldsValue({
      name: rule.name,
      trigger_type: rule.trigger_type,
      trigger_config: rule.trigger_config,
      package_id: rule.package_id,
      expiry_config: rule.expiry_config,
      follow_up_chain: rule.follow_up_chain.map((f) => ({ delay_days: f.delay_days, package_id: f.package_id })),
    });
    setModalOpen(true);
  };

  const handleToggle = async (rule: TaskRule) => {
    try {
      await toggleTaskRule(rule.id);
      showSuccess(`${rule.name} 已${rule.status === "active" ? "暂停" : "启用"}`);
      void reload();
    } catch { showError("操作失败"); }
  };

  const handleDelete = async (rule: TaskRule) => {
    try { await deleteTaskRule(rule.id); showSuccess("规则已删除"); void reload(); }
    catch { showError("删除失败"); }
  };

  const columns = [
    { title: "规则名", dataIndex: "name", key: "name", width: 130, ellipsis: true },
    { title: "触发方式", key: "trigger", width: 130, render: (_: unknown, r: TaskRule) => {
      const label = TRIGGER_OPTIONS.find((o) => o.value === r.trigger_type)?.label ?? r.trigger_type;
      const cfg = r.trigger_config;
      let detail = "";
      if (r.trigger_type === "register" && cfg.delay_minutes) detail = `注册后${cfg.delay_minutes}分钟`;
      else if (r.trigger_type === "recharge" && cfg.threshold_amount) detail = `充值满¥${cfg.threshold_amount}`;
      else if (r.trigger_type === "schedule" && cfg.cron_hour) detail = `每天${cfg.cron_hour}`;
      else if (r.trigger_type === "follow_up" && cfg.delay_days) detail = `完成后第${cfg.delay_days}天`;
      else if (r.trigger_type === "manual") detail = "手动推送";
      return <span>{label}{detail ? <Typography.Text type="secondary" style={{ fontSize: 11 }}> ({detail})</Typography.Text> : ""}</span>;
    }},
    { title: "商品包", dataIndex: "package_name", key: "package_name", width: 100, ellipsis: true },
    { title: "后续链", key: "follow_up", width: 60, render: (_: unknown, r: TaskRule) => {
      const count = (r.follow_up_chain ?? []).length;
      return count > 0 ? <Tag color="blue" style={{ fontSize: 10 }}>{count}级</Tag> : <Typography.Text type="secondary">无</Typography.Text>;
    }},
    { title: "状态", dataIndex: "status", key: "status", width: 60, render: (v: string) => (
      <Tag color={v === "active" ? "green" : "default"} style={{ fontSize: 10 }}>{v === "active" ? "启用" : "暂停"}</Tag>
    )},
    {
      title: "操作", key: "actions", width: 160,
      render: (_: unknown, r: TaskRule) => (
        <Space size={4}>
          <Button size="small" type="link" style={{ fontSize: 11, padding: 0 }} onClick={() => handleEdit(r)}>编辑</Button>
          <Button size="small" type="link" style={{ fontSize: 11, padding: 0, color: r.status === "active" ? "#faad14" : "#52c41a" }} onClick={() => void handleToggle(r)}>
            {r.status === "active" ? "暂停" : "启用"}
          </Button>
          <DangerButton label="删除" confirmTitle={`确认删除「${r.name}」？`}
            onConfirm={() => handleDelete(r)} type="link" danger />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => { setEditingRule(null); form.resetFields(); setTriggerType("register"); setModalOpen(true); }}>创建规则</Button>
        <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>刷新</Button>
      </Space>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{error}</Typography.Text>}
      <Table dataSource={rules} columns={withSorter(columns)} rowKey="id" size="small" loading={loading}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 420px)" }} />

      <Modal title={editingRule ? "编辑推送规则" : "创建推送规则"} open={modalOpen} width={640}
        onCancel={() => { setModalOpen(false); form.resetFields(); setTriggerType("register"); }}
        onOk={() => form.submit()} confirmLoading={saving} okText="保存" cancelText="取消"
        destroyOnHidden>
        <Form form={form} layout="vertical" onFinish={handleSave}
          initialValues={{ trigger_type: "register", expiry_config: "daily_reset", trigger_config: {} }}>
          <Form.Item label="规则名称" name="name" rules={[{ required: true, message: "请输入规则名称" }]}>
            <Input placeholder="例如: 新人大礼包" />
          </Form.Item>
          <Form.Item label="触发类型" name="trigger_type" rules={[{ required: true, message: "请选择触发类型" }]}>
            <Select options={TRIGGER_OPTIONS} placeholder="选择触发类型"
              onChange={(v: string) => { setTriggerType(v); form.setFieldValue("trigger_config", {}); }} />
          </Form.Item>

          {/* ── 动态触发配置字段 ── */}
          {triggerType === "register" && (
            <Form.Item label="延迟推送" name={["trigger_config", "delay_minutes"]} rules={[{ required: true, message: "请输入延迟分钟数" }]}>
              <Space>
                注册后 <InputNumber min={0} max={1440} style={{ width: 100 }} /> 分钟推送
              </Space>
            </Form.Item>
          )}
          {triggerType === "recharge" && (
            <Form.Item label="充值门槛" name={["trigger_config", "threshold_amount"]} rules={[{ required: true, message: "请输入充值门槛" }]}>
              <Space>
                充值满 <InputNumber min={1} style={{ width: 120 }} prefix="¥" /> 元
              </Space>
            </Form.Item>
          )}
          {triggerType === "schedule" && (
            <>
              <Form.Item label="推送时间" name={["trigger_config", "cron_hour"]} rules={[{ required: true, message: "请选择推送时间" }]}>
                <TimePicker format="HH:mm" />
              </Form.Item>
              <Form.Item label="用户筛选" name={["trigger_config", "filter_tags"]}>
                <Select mode="tags" placeholder="标签筛选（留空=全部未领取用户）" />
              </Form.Item>
            </>
          )}
          {triggerType === "follow_up" && (
            <Form.Item label="完成后续推" name={["trigger_config", "delay_days"]} rules={[{ required: true, message: "请输入延迟天数" }]}>
              <Space>
                任务完成后第 <InputNumber min={1} max={365} style={{ width: 100 }} /> 天推送
              </Space>
            </Form.Item>
          )}
          {triggerType === "manual" && (
            <Alert message="手动触发：创建后可在客户列表中手动推送" type="info" showIcon style={{ marginBottom: 16 }} />
          )}

          <Form.Item label="选择商品包" name="package_id" rules={[{ required: true, message: "请选择商品包" }]}>
            <Select options={pkgOptions} placeholder="选择商品包" />
          </Form.Item>
          <Form.Item label="过期配置" name="expiry_config">
            <Select options={EXPIRY_OPTIONS} />
          </Form.Item>

          {/* ── 后续推送链 ── */}
          <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>完成后续推链</Typography.Text>
          <Form.List name="follow_up_chain">
            {(fields, { add, remove }) => (
              <div>
                {fields.map(({ key, name, ...rest }) => (
                  <Row key={key} gutter={8} style={{ marginBottom: 8 }} align="middle">
                    <Col>
                      完成后第
                    </Col>
                    <Col>
                      <Form.Item {...rest} name={[name, "delay_days"]} noStyle>
                        <InputNumber min={1} max={365} style={{ width: 80 }} />
                      </Form.Item>
                    </Col>
                    <Col>天推送</Col>
                    <Col span={10}>
                      <Form.Item {...rest} name={[name, "package_id"]} noStyle>
                        <Select options={pkgOptions} placeholder="选择商品包" style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col>
                      <Button type="link" danger icon={<MinusCircleOutlined />} onClick={() => remove(name)} />
                    </Col>
                  </Row>
                ))}
                <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => add({ delay_days: 1, package_id: undefined })}>添加后续推送</Button>
              </div>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
}

// ── Sign-in Config Tab ──

function SignInConfigTab(): JSX.Element {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    const signinConfig = await getSignInConfig();
    return { signinConfig };
  }, []);
  const { data, loading, reload } = usePageData({ fetcher: fetchConfig });
  const config = data?.signinConfig;

  useEffect(() => {
    if (config) form.setFieldsValue(config);
  }, [config, form]);

  const handleSave = async (values: SignInConfig) => {
    setSaving(true);
    try {
      await updateSignInConfig(values);
      showSuccess("签到配置已保存");
    } catch { showError("保存失败"); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ maxWidth: 500 }}>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        配置连续签到规则，达到指定天数后发放奖励，签到按钮消失
      </Typography.Text>
      <Form form={form} layout="vertical" onFinish={handleSave} initialValues={config}>
        <Form.Item label="连续签到天数" name="consecutive_days" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={1} max={365} style={{ width: 200 }} placeholder="7" />
        </Form.Item>
        <Form.Item label="完成奖励 (¥)" name="reward_amount" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={0} step={0.5} style={{ width: 200 }} placeholder="5.00" prefix="¥" />
        </Form.Item>
        <Button type="primary" onClick={() => form.submit()} loading={saving}>保存配置</Button>
      </Form>
    </div>
  );
}

// ── Invite Config Tab ──

function InviteConfigTab(): JSX.Element {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    const inviteConfig = await getInviteConfig();
    return { inviteConfig };
  }, []);
  const { data, reload } = usePageData({ fetcher: fetchConfig });
  const config = data?.inviteConfig;

  useEffect(() => {
    if (config) form.setFieldsValue(config);
  }, [config, form]);

  const handleSave = async (values: InviteConfig) => {
    setSaving(true);
    try {
      await updateInviteConfig(values);
      showSuccess("邀请配置已保存");
    } catch { showError("保存失败"); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ maxWidth: 500 }}>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        配置邀请奖励、充值触发和风控限制
      </Typography.Text>
      <Form form={form} layout="vertical" onFinish={handleSave} initialValues={config}>
        <Form.Item label="邀请注册奖励 (¥)" name="register_reward" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={0} step={0.5} style={{ width: 200 }} placeholder="2.00" prefix="¥" />
        </Form.Item>
        <Form.Item label="邀请充值触发 (¥)" name="recharge_trigger_amount" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={0} step={5} style={{ width: 200 }} placeholder="30" prefix="¥" />
        </Form.Item>
        <Form.Item label="邀请充值奖励 (¥)" name="recharge_reward" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={0} step={0.5} style={{ width: 200 }} placeholder="3.00" prefix="¥" />
        </Form.Item>
        <Form.Item label="每人最多邀请" name="max_invitees" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={1} max={1000} style={{ width: 200 }} placeholder="20" />
        </Form.Item>
        <Form.Item label="同IP限制 (人/IP)" name="same_ip_limit" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={1} max={100} style={{ width: 200 }} placeholder="3" />
        </Form.Item>
        <Form.Item label="同设备限制 (人/设备)" name="same_device_limit" rules={[{ required: true, message: "请输入" }]}>
          <InputNumber min={1} max={100} style={{ width: 200 }} placeholder="2" />
        </Form.Item>
        <Button type="primary" onClick={() => form.submit()} loading={saving}>保存配置</Button>
      </Form>
    </div>
  );
}

// ── Stats Tab ──

function StatsTab(): JSX.Element {
  const fetchStats = useCallback(async () => {
    const stats = await getMarketingStats();
    return { stats };
  }, []);
  const { data, loading, reload } = usePageData({ fetcher: fetchStats });
  const stats = data?.stats;

  if (!stats) return <div style={{ textAlign: "center", padding: 48, color: "#999" }}>加载中...</div>;

  const trendColumns = [
    { title: "日期", dataIndex: "date", key: "date", width: 100 },
    { title: "推送", dataIndex: "push", key: "push", width: 80 },
    { title: "签到", dataIndex: "signin", key: "signin", width: 80 },
    { title: "邀请", dataIndex: "invite", key: "invite", width: 80 },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="推送统计" value={stats.push_triggered} suffix={`触发`} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              领取 {stats.push_claimed} | 完成 {stats.push_completed} | 奖励 ¥{stats.push_reward_total}
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="签到统计" value={stats.signin_count} suffix={`签到`} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              完成 {stats.signin_completed} | 奖励 ¥{stats.signin_reward_total}
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="邀请统计" value={stats.invite_share_count} suffix={`分享`} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              注册转化 {stats.invite_registration} | 充值转化 {stats.invite_recharge} | 奖励 ¥{stats.invite_reward_total}
            </div>
          </Card>
        </Col>
      </Row>
      <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>日趋势 (最近 30 天)</Typography.Text>
      <Table dataSource={stats.daily_trend} columns={withSorter(trendColumns)} rowKey="date" size="small" loading={loading}
        pagination={false} scroll={{ y: 300 }} />
    </div>
  );
}

// ── Main Component ──

export function TaskRulesPage(): JSX.Element {
  const [activeTab, setActiveTab] = useState("push");
  const [packages, setPackages] = useState<ProductPackage[]>([]);
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const accountId = actorAccountIds.length > 0 ? actorAccountIds[0] : undefined;

  const loadPackages = useCallback(async () => {
    const pkgList = await listPackages(accountId);
    setPackages(pkgList);
  }, [accountId]);
  useEffect(() => { void loadPackages(); }, [loadPackages]);

  const actions = (
    <Button size="small" icon={<ReloadOutlined />} onClick={() => {
      void loadPackages();
      window.location.reload();
    }}>刷新</Button>
  );

  return (
    <PageShell title="任务规则管理" subtitle="管理推送规则、签到配置、邀请配置和统计" actions={actions}>
      <Tabs activeKey={activeTab} onChange={setActiveTab} size="small"
        items={[
          { key: "push", label: "推送规则", children: <PushRulesTab packages={packages} /> },
          { key: "signin", label: "签到配置", children: <SignInConfigTab /> },
          { key: "invite", label: "邀请配置", children: <InviteConfigTab /> },
          { key: "stats", label: "统计", children: <StatsTab /> },
        ]}
      />
    </PageShell>
  );
}

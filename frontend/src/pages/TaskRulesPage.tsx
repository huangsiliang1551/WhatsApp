import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  TimePicker,
  Typography,
  type TableColumnsType,
} from "antd";
import { MinusCircleOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState, type JSX } from "react";

import { DangerButton, showError, showSuccess } from "../components/Feedback";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getTaskSystemConfig,
  listTaskIssuePlans,
  patchTaskSystemConfig,
  type TaskIssuePlan,
  type TaskSystemConfig,
} from "../services/api";
import {
  createTaskRule,
  deleteTaskRule,
  getMarketingStats,
  getSignInConfig,
  listPackages,
  listTaskRules,
  toggleTaskRule,
  updateSignInConfig,
  updateTaskRule,
  type MarketingStats,
  type ProductPackage,
  type SignInConfig,
  type TaskRule,
  type TaskRuleFollowUp,
} from "../services/marketingApi";
import { useAppStore } from "../stores/appStore";
import { withSorter } from "../utils/withSorter";

const TRIGGER_OPTIONS = [
  { label: "注册触发", value: "register" },
  { label: "充值触发", value: "recharge" },
  { label: "定时触发", value: "schedule" },
  { label: "完成后跟进", value: "follow_up" },
  { label: "手动触发", value: "manual" },
];

const EXPIRY_OPTIONS = [
  { label: "每日 0:00 重置", value: "daily_reset" },
  { label: "永不过期", value: "none" },
  { label: "7 天后过期", value: "7d_expire" },
  { label: "30 天后过期", value: "30d_expire" },
];

const BOOLEAN_OPTIONS = [
  { label: "启用", value: true },
  { label: "关闭", value: false },
];

type TaskRuleFormValues = {
  name: string;
  trigger_type: string;
  trigger_config: Record<string, {} | undefined>;
  package_id: string;
  expiry_config: string;
  follow_up_chain: Array<{ delay_days: number; package_id: string }>;
};

type TaskSystemConfigFormValues = {
  status: string;
  newbie_task_enabled: boolean;
  newbie_plan_id?: string;
  newbie_auto_popup: boolean;
  official_plan_id?: string;
  show_task_balance_transfer_prompt: boolean;
  min_task_balance_transfer_prompt_amount: number;
  max_active_batches_per_user: number;
  max_active_packages_per_user: number;
  whatsapp_binding_reward_enabled: boolean;
  whatsapp_binding_reward_amount: number;
  certified_member_enabled: boolean;
  certified_recharge_threshold: number;
  auto_certify_on_recharge: boolean;
};

function BasicSettingsTab({ accountId }: { accountId?: string }): JSX.Element {
  const [form] = Form.useForm<TaskSystemConfigFormValues>();
  const [saving, setSaving] = useState(false);
  const [configSnapshot, setConfigSnapshot] = useState<TaskSystemConfig | null>(null);

  const fetchSettings = useCallback(async () => {
    if (!accountId) {
      return {
        taskSystemConfig: null as TaskSystemConfig | null,
        issuePlans: [] as TaskIssuePlan[],
      };
    }
    const [taskSystemConfig, issuePlans] = await Promise.all([
      getTaskSystemConfig({ account_id: accountId }),
      listTaskIssuePlans({ account_id: accountId }),
    ]);
    return { taskSystemConfig, issuePlans };
  }, [accountId]);

  const { data, loading, error, reload } = usePageData({
    fetcher: fetchSettings,
    deps: [accountId],
  });

  const issuePlans = data?.issuePlans ?? [];

  useEffect(() => {
    if (!data?.taskSystemConfig) {
      return;
    }
    setConfigSnapshot(data.taskSystemConfig);
    form.setFieldsValue({
      status: data.taskSystemConfig.status,
      newbie_task_enabled: data.taskSystemConfig.newbieTaskEnabled,
      newbie_plan_id: data.taskSystemConfig.newbiePlanId ?? undefined,
      newbie_auto_popup: data.taskSystemConfig.newbieAutoPopup,
      official_plan_id: data.taskSystemConfig.officialPlanId ?? undefined,
      show_task_balance_transfer_prompt: data.taskSystemConfig.showTaskBalanceTransferPrompt,
      min_task_balance_transfer_prompt_amount: Number(data.taskSystemConfig.minTaskBalanceTransferPromptAmount),
      max_active_batches_per_user: data.taskSystemConfig.maxActiveBatchesPerUser,
      max_active_packages_per_user: data.taskSystemConfig.maxActivePackagesPerUser,
      whatsapp_binding_reward_enabled: data.taskSystemConfig.whatsappBindingRewardEnabled,
      whatsapp_binding_reward_amount: Number(data.taskSystemConfig.whatsappBindingRewardAmount),
      certified_member_enabled: data.taskSystemConfig.certifiedMemberEnabled,
      certified_recharge_threshold: Number(data.taskSystemConfig.certifiedRechargeThreshold),
      auto_certify_on_recharge: data.taskSystemConfig.autoCertifyOnRecharge,
    });
  }, [data?.taskSystemConfig, form]);

  const handleSave = async (values: TaskSystemConfigFormValues) => {
    if (!accountId || !configSnapshot) {
      showError("缺少可保存的任务系统配置范围");
      return;
    }
    setSaving(true);
    try {
      const nextConfig = await patchTaskSystemConfig({
        account_id: accountId,
        site_id: configSnapshot.siteId ?? undefined,
        status: values.status,
        whatsapp_binding_reward_enabled: values.whatsapp_binding_reward_enabled,
        whatsapp_binding_reward_amount: String(values.whatsapp_binding_reward_amount),
        whatsapp_binding_reward_wallet_type: configSnapshot.whatsappBindingRewardWalletType,
        whatsapp_binding_reward_currency: configSnapshot.whatsappBindingRewardCurrency,
        certified_member_enabled: values.certified_member_enabled,
        certified_recharge_threshold: String(values.certified_recharge_threshold),
        certified_recharge_scope: configSnapshot.certifiedRechargeScope,
        auto_certify_on_recharge: values.auto_certify_on_recharge,
        newbie_task_enabled: values.newbie_task_enabled,
        newbie_plan_id: values.newbie_plan_id || undefined,
        newbie_auto_popup: configSnapshot.newbieAutoPopup,
        official_plan_id: values.official_plan_id || undefined,
        show_task_balance_transfer_prompt: configSnapshot.showTaskBalanceTransferPrompt,
        min_task_balance_transfer_prompt_amount: String(configSnapshot.minTaskBalanceTransferPromptAmount),
        max_active_batches_per_user: values.max_active_batches_per_user,
        max_active_packages_per_user: values.max_active_packages_per_user,
        metadata_json: configSnapshot.metadataJson,
      });
      setConfigSnapshot(nextConfig);
      showSuccess("任务系统基础设置已保存");
      void reload();
    } catch {
      showError("保存任务系统基础设置失败");
    } finally {
      setSaving(false);
    }
  };

  const planOptions = issuePlans.map((plan) => ({
    label: `${plan.name} (${plan.plan_type})`,
    value: plan.id,
  }));

  if (!accountId) {
    return <Alert type="info" showIcon message="当前账号范围缺失，暂时无法加载任务系统基础设置。" />;
  }

  return (
    <div style={{ maxWidth: 880 }}>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        收口 v3 任务系统基础配置：新手任务、正式任务、余额转入引导、认证门槛与活跃批次限制。
      </Typography.Text>

      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>
          {error}
        </Typography.Text>
      ) : null}

      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card size="small" title="新手任务">
              <Form.Item label="任务状态" name="newbie_task_enabled" valuePropName="checked">
                <Checkbox>启用新手任务链路</Checkbox>
              </Form.Item>
              <Form.Item label="默认新手计划" name="newbie_plan_id">
                <Select allowClear options={planOptions} placeholder="选择新手计划" loading={loading} />
              </Form.Item>
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Card size="small" title="正式任务">
              <Form.Item label="默认正式计划" name="official_plan_id">
                <Select allowClear options={planOptions} placeholder="选择正式计划" loading={loading} />
              </Form.Item>
              <Form.Item label="活跃批次上限" name="max_active_batches_per_user" rules={[{ required: true, message: "请输入活跃批次上限" }]}>
                <InputNumber min={1} max={20} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label="活跃任务包上限" name="max_active_packages_per_user" rules={[{ required: true, message: "请输入活跃任务包上限" }]}>
                <InputNumber min={1} max={50} style={{ width: "100%" }} />
              </Form.Item>
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Card size="small" title="认证与奖励">
              <Form.Item label="绑定奖励启用" name="whatsapp_binding_reward_enabled">
                <Select options={BOOLEAN_OPTIONS} placeholder="选择是否启用" />
              </Form.Item>
              <Form.Item label="绑定奖励金额" name="whatsapp_binding_reward_amount" rules={[{ required: true, message: "请输入绑定奖励金额" }]}>
                <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label="认证开关" name="certified_member_enabled">
                <Select options={BOOLEAN_OPTIONS} placeholder="选择是否启用认证" />
              </Form.Item>
              <Form.Item label="认证充值门槛" name="certified_recharge_threshold" rules={[{ required: true, message: "请输入认证充值门槛" }]}>
                <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item label="充值后自动认证" name="auto_certify_on_recharge">
                <Select options={BOOLEAN_OPTIONS} placeholder="选择是否自动认证" />
              </Form.Item>
            </Card>
          </Col>
        </Row>

        <Space style={{ marginTop: 16 }}>
          <Button type="primary" onClick={() => form.submit()} loading={saving}>
            保存基础设置
          </Button>
          <Button onClick={() => void reload()} loading={loading}>
            重新加载
          </Button>
        </Space>
      </Form>
    </div>
  );
}

function PushRulesTab({ packages }: { packages: ProductPackage[] }): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<TaskRule | null>(null);
  const [triggerType, setTriggerType] = useState<string>("register");
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<TaskRuleFormValues>();

  const fetchRules = useCallback(async () => {
    const rules = await listTaskRules();
    return { rules };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchRules });
  const rules = data?.rules ?? [];

  const packageOptions = useMemo(
    () => packages.map((item) => ({ label: item.name, value: item.id })),
    [packages]
  );

  const closeModal = () => {
    setModalOpen(false);
    setEditingRule(null);
    setTriggerType("register");
    form.resetFields();
  };

  const handleSave = async (values: TaskRuleFormValues) => {
    setSaving(true);
    try {
      const followUpChain: TaskRuleFollowUp[] = (values.follow_up_chain ?? []).map((item) => ({
        delay_days: item.delay_days,
        package_id: item.package_id,
        package_name: packages.find((pkg) => pkg.id === item.package_id)?.name ?? "",
      }));

      const payload = {
        name: values.name,
        trigger_type: values.trigger_type,
        trigger_config: values.trigger_config ?? {},
        package_id: values.package_id,
        package_name: packages.find((pkg) => pkg.id === values.package_id)?.name ?? "",
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

      closeModal();
      void reload();
    } catch {
      showError("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (rule: TaskRule) => {
    setEditingRule(rule);
    setTriggerType(rule.trigger_type);
    form.setFieldsValue({
      name: rule.name,
      trigger_type: rule.trigger_type,
      trigger_config: (rule.trigger_config ?? {}) as TaskRuleFormValues["trigger_config"],
      package_id: rule.package_id,
      expiry_config: rule.expiry_config,
      follow_up_chain: (rule.follow_up_chain ?? []).map((item) => ({
        delay_days: item.delay_days,
        package_id: item.package_id,
      })),
    });
    setModalOpen(true);
  };

  const handleToggle = async (rule: TaskRule) => {
    try {
      await toggleTaskRule(rule.id);
      showSuccess(`${rule.name} 已${rule.status === "active" ? "暂停" : "启用"}`);
      void reload();
    } catch {
      showError("操作失败");
    }
  };

  const handleDelete = async (rule: TaskRule) => {
    try {
      await deleteTaskRule(rule.id);
      showSuccess("规则已删除");
      void reload();
    } catch {
      showError("删除失败");
    }
  };

  const columns: TableColumnsType<TaskRule> = [
    {
      title: "规则名称",
      dataIndex: "name",
      key: "name",
      width: 160,
      ellipsis: true,
    },
    {
      title: "触发方式",
      key: "trigger",
      width: 180,
      render: (_, rule) => {
        const label = TRIGGER_OPTIONS.find((item) => item.value === rule.trigger_type)?.label ?? rule.trigger_type;
        const config = rule.trigger_config ?? {};
        let detail = "";
        if (rule.trigger_type === "register" && typeof config.delay_minutes === "number") {
          detail = `注册后 ${config.delay_minutes} 分钟`;
        } else if (rule.trigger_type === "recharge" && typeof config.threshold_amount === "number") {
          detail = `充值满 ￥${config.threshold_amount}`;
        } else if (rule.trigger_type === "schedule" && typeof config.cron_hour === "string") {
          detail = `每天 ${config.cron_hour}`;
        } else if (rule.trigger_type === "follow_up" && typeof config.delay_days === "number") {
          detail = `完成后第 ${config.delay_days} 天`;
        } else if (rule.trigger_type === "manual") {
          detail = "手动发放";
        }

        return (
          <span>
            {label}
            {detail ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {" "}
                ({detail})
              </Typography.Text>
            ) : null}
          </span>
        );
      },
    },
    {
      title: "商品包",
      dataIndex: "package_name",
      key: "package_name",
      width: 140,
      ellipsis: true,
    },
    {
      title: "跟进链",
      key: "follow_up",
      width: 90,
      render: (_, rule) => {
        const count = rule.follow_up_chain?.length ?? 0;
        return count > 0 ? <Tag color="blue">{count} 条</Tag> : <Typography.Text type="secondary">无</Typography.Text>;
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (value: string) => <Tag color={value === "active" ? "green" : "default"}>{value === "active" ? "启用" : "暂停"}</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_, rule) => (
        <Space size={4}>
          <Button size="small" type="link" onClick={() => handleEdit(rule)}>
            编辑
          </Button>
          <Button
            size="small"
            type="link"
            onClick={() => void handleToggle(rule)}
            style={{ color: rule.status === "active" ? "#d48806" : "#389e0d" }}
          >
            {rule.status === "active" ? "暂停" : "启用"}
          </Button>
          <DangerButton
            label="删除"
            confirmTitle={`确认删除「${rule.name}」？`}
            onConfirm={() => handleDelete(rule)}
            type="link"
            danger
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button
          size="small"
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingRule(null);
            form.resetFields();
            setTriggerType("register");
            setModalOpen(true);
          }}
        >
          创建规则
        </Button>
        <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>
          刷新
        </Button>
      </Space>

      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>
          {error}
        </Typography.Text>
      ) : null}

      <Table
        dataSource={rules}
        columns={withSorter(columns)}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 20 }}
        scroll={{ y: "calc(100vh - 420px)" }}
      />

      <Modal
        title={editingRule ? "编辑推送规则" : "创建推送规则"}
        open={modalOpen}
        width={680}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            trigger_type: "register",
            expiry_config: "daily_reset",
            trigger_config: {},
            follow_up_chain: [],
          }}
        >
          <Form.Item label="规则名称" name="name" rules={[{ required: true, message: "请输入规则名称" }]}>
            <Input placeholder="例如：新人礼包" />
          </Form.Item>
          <Form.Item label="触发类型" name="trigger_type" rules={[{ required: true, message: "请选择触发类型" }]}>
            <Select
              options={TRIGGER_OPTIONS}
              onChange={(value: string) => {
                setTriggerType(value);
                form.setFieldValue("trigger_config", {});
              }}
            />
          </Form.Item>

          {triggerType === "register" ? (
            <Form.Item
              label="延迟发放"
              name={["trigger_config", "delay_minutes"]}
              rules={[{ required: true, message: "请输入延迟分钟数" }]}
            >
              <Space>
                注册后
                <InputNumber min={0} max={1440} style={{ width: 120 }} />
                分钟发放
              </Space>
            </Form.Item>
          ) : null}

          {triggerType === "recharge" ? (
            <Form.Item
              label="充值门槛"
              name={["trigger_config", "threshold_amount"]}
              rules={[{ required: true, message: "请输入充值门槛" }]}
            >
              <Space>
                充值满
                <InputNumber min={1} style={{ width: 140 }} prefix="￥" />
              </Space>
            </Form.Item>
          ) : null}

          {triggerType === "schedule" ? (
            <>
              <Form.Item
                label="触发时间"
                name={["trigger_config", "cron_hour"]}
                rules={[{ required: true, message: "请选择触发时间" }]}
              >
                <TimePicker format="HH:mm" />
              </Form.Item>
              <Form.Item label="标签筛选" name={["trigger_config", "filter_tags"]}>
                <Select mode="tags" placeholder="留空表示全部未领取用户" />
              </Form.Item>
            </>
          ) : null}

          {triggerType === "follow_up" ? (
            <Form.Item
              label="跟进触发"
              name={["trigger_config", "delay_days"]}
              rules={[{ required: true, message: "请输入延迟天数" }]}
            >
              <Space>
                任务完成后第
                <InputNumber min={1} max={365} style={{ width: 120 }} />
                天发放
              </Space>
            </Form.Item>
          ) : null}

          {triggerType === "manual" ? (
            <Alert message="手动触发规则创建后，可在客户或任务侧手动发放。" type="info" showIcon style={{ marginBottom: 16 }} />
          ) : null}

          <Form.Item label="商品包" name="package_id" rules={[{ required: true, message: "请选择商品包" }]}>
            <Select options={packageOptions} placeholder="请选择商品包" />
          </Form.Item>
          <Form.Item label="过期策略" name="expiry_config">
            <Select options={EXPIRY_OPTIONS} />
          </Form.Item>

          <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
            后续跟进链
          </Typography.Text>
          <Form.List name="follow_up_chain">
            {(fields, { add, remove }) => (
              <div>
                {fields.map(({ key, name, ...rest }) => (
                  <Row key={key} gutter={8} style={{ marginBottom: 8 }} align="middle">
                    <Col>完成后第</Col>
                    <Col>
                      <Form.Item {...rest} name={[name, "delay_days"]} noStyle>
                        <InputNumber min={1} max={365} style={{ width: 80 }} />
                      </Form.Item>
                    </Col>
                    <Col>天发放</Col>
                    <Col span={10}>
                      <Form.Item {...rest} name={[name, "package_id"]} noStyle>
                        <Select options={packageOptions} placeholder="选择商品包" style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col>
                      <Button type="link" danger icon={<MinusCircleOutlined />} onClick={() => remove(name)} />
                    </Col>
                  </Row>
                ))}
                <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => add({ delay_days: 1 })}>
                  添加跟进项
                </Button>
              </div>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
}

function SignInConfigTab(): JSX.Element {
  const [form] = Form.useForm<SignInConfig>();
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    const signinConfig = await getSignInConfig();
    return { signinConfig };
  }, []);

  const { data } = usePageData({ fetcher: fetchConfig });
  const config = data?.signinConfig;

  useEffect(() => {
    if (config) {
      form.setFieldsValue(config);
    }
  }, [config, form]);

  const handleSave = async (values: SignInConfig) => {
    setSaving(true);
    try {
      await updateSignInConfig(values);
      showSuccess("签到配置已保存");
    } catch {
      showError("保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 520 }}>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        配置连续签到达标天数和完成奖励金额。
      </Typography.Text>
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item label="连续签到天数" name="consecutive_days" rules={[{ required: true, message: "请输入连续签到天数" }]}>
          <InputNumber min={1} max={365} style={{ width: 220 }} />
        </Form.Item>
        <Form.Item label="奖励金额 (￥)" name="reward_amount" rules={[{ required: true, message: "请输入奖励金额" }]}>
          <InputNumber min={0} step={0.5} style={{ width: 220 }} prefix="￥" />
        </Form.Item>
        <Button type="primary" onClick={() => form.submit()} loading={saving}>
          保存配置
        </Button>
      </Form>
    </div>
  );
}

function StatsTab(): JSX.Element {
  const fetchStats = useCallback(async () => {
    const stats = await getMarketingStats();
    return { stats };
  }, []);

  const { data, loading } = usePageData({ fetcher: fetchStats });
  const stats: MarketingStats | undefined = data?.stats;

  if (!stats) {
    return (
      <div style={{ textAlign: "center", padding: 48, color: "#999" }}>
        {loading ? "加载中..." : "暂无数据"}
      </div>
    );
  }

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <Card size="small">
            <Statistic title="推送触发" value={stats.push_triggered} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              领取 {stats.push_claimed} | 完成 {stats.push_completed} | 奖励 ￥{stats.push_reward_total}
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Statistic title="签到统计" value={stats.signin_count} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              完成 {stats.signin_completed} | 奖励 ￥{stats.signin_reward_total}
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Statistic title="邀请统计" value={stats.invite_share_count} />
            <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              注册转化 {stats.invite_registration} | 充值转化 {stats.invite_recharge} | 奖励 ￥{stats.invite_reward_total}
            </div>
          </Card>
        </Col>
      </Row>
      <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
        最近 30 天趋势
      </Typography.Text>
      <Table
        dataSource={stats.daily_trend}
        columns={withSorter([
          { title: "日期", dataIndex: "date", key: "date", width: 120 },
          { title: "推送", dataIndex: "push", key: "push", width: 90 },
          { title: "签到", dataIndex: "signin", key: "signin", width: 90 },
          { title: "邀请", dataIndex: "invite", key: "invite", width: 90 },
        ])}
        rowKey="date"
        size="small"
        loading={loading}
        pagination={false}
        scroll={{ y: 300 }}
      />
    </div>
  );
}

export function TaskRulesPage(): JSX.Element {
  const [activeTab, setActiveTab] = useState("basic_settings");
  const [packages, setPackages] = useState<ProductPackage[]>([]);
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const accountId = actorAccountIds.length > 0 ? actorAccountIds[0] : undefined;

  const loadPackages = useCallback(async () => {
    const packageList = await listPackages(accountId);
    setPackages(packageList);
  }, [accountId]);

  useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  const actions = (
    <Button
      size="small"
      icon={<ReloadOutlined />}
      onClick={() => {
        void loadPackages();
        window.location.reload();
      }}
    >
      刷新
    </Button>
  );

  return (
    <PageShell title="任务规则管理" subtitle="管理 v3 任务系统基础设置、推送规则、签到配置和任务统计" actions={actions}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          { key: "basic_settings", label: "基础设置", children: <BasicSettingsTab accountId={accountId} /> },
          { key: "push", label: "推送规则", children: <PushRulesTab packages={packages} /> },
          { key: "signin", label: "签到配置", children: <SignInConfigTab /> },
          { key: "stats", label: "统计", children: <StatsTab /> },
        ]}
      />
    </PageShell>
  );
}

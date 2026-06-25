import {
  Alert,
  Button,
  Card,
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

type TaskRuleFormValues = {
  name: string;
  trigger_type: string;
  trigger_config: Record<string, {} | undefined>;
  package_id: string;
  expiry_config: string;
  follow_up_chain: Array<{ delay_days: number; package_id: string }>;
};

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
  const [activeTab, setActiveTab] = useState("push");
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
    <PageShell title="任务规则管理" subtitle="管理推送规则、签到配置和任务统计" actions={actions}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          { key: "push", label: "推送规则", children: <PushRulesTab packages={packages} /> },
          { key: "signin", label: "签到配置", children: <SignInConfigTab /> },
          { key: "stats", label: "统计", children: <StatsTab /> },
        ]}
      />
    </PageShell>
  );
}

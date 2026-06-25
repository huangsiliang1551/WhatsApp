import { ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Form, InputNumber, Row, Statistic, Tabs, Typography } from "antd";
import { useCallback, useEffect, useState, type JSX } from "react";

import { showError, showSuccess } from "../components/Feedback";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getInviteConfig,
  getMarketingStats,
  updateInviteConfig,
  type InviteConfig,
  type MarketingStats,
} from "../services/marketingApi";

function InviteConfigTab(): JSX.Element {
  const [form] = Form.useForm<InviteConfig>();
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    const inviteConfig = await getInviteConfig();
    return { inviteConfig };
  }, []);

  const { data, reload } = usePageData({ fetcher: fetchConfig });
  const config = data?.inviteConfig;

  useEffect(() => {
    if (config) {
      form.setFieldsValue(config);
    }
  }, [config, form]);

  const handleSave = async (values: InviteConfig) => {
    setSaving(true);
    try {
      await updateInviteConfig(values);
      showSuccess("邀请配置已保存");
      void reload();
    } catch {
      showError("保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 560 }}>
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        独立维护邀请注册奖励、充值门槛和基础风控限制。
      </Typography.Text>
      <Form form={form} layout="vertical" onFinish={handleSave}>
        <Form.Item
          label="邀请注册奖励 (￥)"
          name="register_reward"
          rules={[{ required: true, message: "请输入邀请注册奖励" }]}
        >
          <InputNumber min={0} step={0.5} style={{ width: 220 }} placeholder="2.00" prefix="￥" />
        </Form.Item>
        <Form.Item
          label="邀请充值触发金额 (￥)"
          name="recharge_trigger_amount"
          rules={[{ required: true, message: "请输入充值触发金额" }]}
        >
          <InputNumber min={0} step={5} style={{ width: 220 }} placeholder="30" prefix="￥" />
        </Form.Item>
        <Form.Item
          label="邀请充值奖励 (￥)"
          name="recharge_reward"
          rules={[{ required: true, message: "请输入邀请充值奖励" }]}
        >
          <InputNumber min={0} step={0.5} style={{ width: 220 }} placeholder="3.00" prefix="￥" />
        </Form.Item>
        <Form.Item
          label="每人最多邀请"
          name="max_invitees"
          rules={[{ required: true, message: "请输入邀请上限" }]}
        >
          <InputNumber min={1} max={1000} style={{ width: 220 }} placeholder="20" />
        </Form.Item>
        <Form.Item
          label="同 IP 限制"
          name="same_ip_limit"
          rules={[{ required: true, message: "请输入同 IP 限制" }]}
        >
          <InputNumber min={0} max={100} style={{ width: 220 }} placeholder="3" />
        </Form.Item>
        <Form.Item
          label="同设备限制"
          name="same_device_limit"
          rules={[{ required: true, message: "请输入同设备限制" }]}
        >
          <InputNumber min={0} max={100} style={{ width: 220 }} placeholder="2" />
        </Form.Item>
        <Button type="primary" onClick={() => form.submit()} loading={saving}>
          保存配置
        </Button>
      </Form>
    </div>
  );
}

function InviteStatsTab(): JSX.Element {
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
            <Statistic title="分享次数" value={stats.invite_share_count} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Statistic title="注册转化" value={stats.invite_registration} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small">
            <Statistic title="充值转化" value={stats.invite_recharge} />
          </Card>
        </Col>
      </Row>
      <Card size="small">
        <Statistic title="累计邀请奖励" value={stats.invite_reward_total} precision={2} prefix="￥" />
      </Card>
    </div>
  );
}

export function InviteManagementPage(): JSX.Element {
  const actions = (
    <Button size="small" icon={<ReloadOutlined />} onClick={() => window.location.reload()}>
      刷新
    </Button>
  );

  return (
    <PageShell
      title="邀请管理"
      subtitle="将邀请配置从任务规则中拆出，单独维护奖励规则和关键运营指标"
      actions={actions}
    >
      <Tabs
        defaultActiveKey="config"
        size="small"
        items={[
          { key: "config", label: "邀请配置", children: <InviteConfigTab /> },
          { key: "stats", label: "邀请统计", children: <InviteStatsTab /> },
        ]}
      />
    </PageShell>
  );
}

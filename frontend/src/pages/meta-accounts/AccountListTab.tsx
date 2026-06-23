import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Dropdown, Form, Input, message, Popover, Select, Table, Tag, Typography } from "antd";
import type { InputRef } from "antd";
import type { ColumnsType } from "antd/es/table";
import { LinkOutlined, MoreOutlined, SettingOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { MetaWabaAccount } from "../../services/api";
import {
  getGlobalWebhookConfig,
  healthCheckMetaAccount,
  subscribeMetaWebhook,
  updateGlobalWebhookConfig,
} from "../../services/api";
import { shortTs, whColor, whLabel } from "./utils";

interface AccountListTabProps {
  accounts: MetaWabaAccount[];
  selectedWabaKey: string | null;
  onSelect: (key: string | null) => void;
  filterMode: string;
  onFilterModeChange: (v: string) => void;
  searchText: string;
  onSearchChange: (v: string) => void;
  onManualAdd: () => void;
  onSignup: () => void;
  onRefresh: () => void;
  loading: boolean;
}

function compositeStatus(r: MetaWabaAccount): "green" | "yellow" | "red" | "gray" {
  if (!r.has_access_token) return "gray";
  if (!r.account_is_active || !r.is_active) return "red";
  if (r.blocking_reasons.length > 0) return "red";
  if (
    r.webhook_runtime_status === "healthy" &&
    r.phone_number_count > 0 &&
    r.registered_phone_number_count === r.phone_number_count
  ) {
    return "green";
  }
  if (
    r.webhook_runtime_status !== "healthy" ||
    r.registered_phone_number_count < r.phone_number_count
  ) {
    return "yellow";
  }
  return "green";
}

function statusDot(status: ReturnType<typeof compositeStatus>) {
  const colorMap: Record<ReturnType<typeof compositeStatus>, string> = {
    green: "#52c41a",
    yellow: "#faad14",
    red: "#ff4d4f",
    gray: "#d9d9d9",
  };
  return (
    <span
      style={{
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: colorMap[status],
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  );
}

function phoneColor(registered: number, total: number): string {
  if (total === 0) return "#d9d9d9";
  if (registered === total) return "#52c41a";
  if (registered === 0) return "#ff4d4f";
  return "#faad14";
}

function webhookBrief(r: MetaWabaAccount): { label: string; reason: string } {
  const label = whLabel(r.webhook_runtime_status);
  let reason = "";
  if (r.webhook_signature_failure_count > 0) {
    reason = `签名失败 ${r.webhook_signature_failure_count}`;
  } else if (r.webhook_runtime_error) {
    reason = r.webhook_runtime_error.slice(0, 20);
  }
  return { label, reason };
}

export function AccountListTab({
  accounts,
  selectedWabaKey,
  onSelect,
  filterMode,
  onFilterModeChange,
  searchText,
  onSearchChange,
  onManualAdd,
  onSignup,
  onRefresh,
  loading,
}: AccountListTabProps) {
  const [configOpen, setConfigOpen] = useState(false);
  const [whSaving, setWhSaving] = useState(false);
  const [whForm] = Form.useForm();
  const whLoadedRef = useRef(false);
  const inputRef = useRef<InputRef>(null);

  useEffect(() => {
    if (!configOpen || whLoadedRef.current) return;
    whLoadedRef.current = true;
    getGlobalWebhookConfig().then((cfg) => whForm.setFieldsValue(cfg)).catch(() => undefined);
  }, [configOpen, whForm]);

  const handleSaveWh = useCallback(async () => {
    try {
      const values = await whForm.validateFields();
      setWhSaving(true);
      await updateGlobalWebhookConfig(values);
      message.success("已保存");
      setConfigOpen(false);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setWhSaving(false);
    }
  }, [whForm]);

  const whContent = (
    <div style={{ width: 340, padding: "4px 0" }}>
      <Form form={whForm} size="small" layout="vertical">
        <Form.Item
          name="callback_url"
          label="回调地址"
          rules={[{ required: true, message: "必填" }]}
          style={{ marginBottom: 8 }}
        >
          <Input placeholder="https://your-domain.com/webhooks/whatsapp" />
        </Form.Item>
        <Form.Item name="verify_token" label="Verify Token" style={{ marginBottom: 8 }}>
          <Input placeholder="Webhook 验证令牌" />
        </Form.Item>
        <Typography.Text type="secondary" style={{ fontSize: 10, display: "block", marginBottom: 8 }}>
          新建账户会自动使用这里配置的全局 Webhook 参数。
        </Typography.Text>
        <Button type="primary" size="small" block loading={whSaving} onClick={handleSaveWh}>
          保存
        </Button>
      </Form>
    </div>
  );

  const filtered = useMemo(() => {
    let result = accounts;
    if (filterMode) {
      result = result.filter((a) => a.onboarding_mode === filterMode);
    }
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase();
      result = result.filter((a) =>
        a.display_name.toLowerCase().includes(q) ||
        a.waba_id.toLowerCase().includes(q) ||
        a.account_id.toLowerCase().includes(q) ||
        (a.notes ?? "").toLowerCase().includes(q)
      );
    }
    return result;
  }, [accounts, filterMode, searchText]);

  const columns: ColumnsType<MetaWabaAccount> = [
    {
      title: "",
      key: "status",
      width: 40,
      render: (_: unknown, record: MetaWabaAccount) => (
        <div style={{ display: "flex", justifyContent: "center" }}>
          {statusDot(compositeStatus(record))}
        </div>
      ),
    },
    {
      title: "账户信息",
      key: "info",
      ellipsis: true,
      render: (_: unknown, record: MetaWabaAccount) => (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
            <Typography.Text strong style={{ fontSize: 12 }} ellipsis>
              {record.display_name}
            </Typography.Text>
            <Tag style={{ fontSize: 9, margin: 0, lineHeight: "16px" }}>
              {record.onboarding_mode === "embedded_signup" ? "Signup" : "手动"}
            </Tag>
            <Tag color={record.is_active ? "success" : "default"} style={{ fontSize: 9, margin: 0, lineHeight: "16px" }}>
              {record.is_active ? "启用" : "禁用"}
            </Tag>
            {record.notes ? (
              <Typography.Text type="secondary" style={{ fontSize: 9, maxWidth: 80 }} ellipsis>
                {record.notes}
              </Typography.Text>
            ) : null}
          </div>
          <Typography.Text style={{ fontSize: 10, fontFamily: "monospace", color: "#aaa" }}>
            {record.waba_id}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: "号码",
      key: "phones",
      width: 60,
      align: "center",
      render: (_: unknown, record: MetaWabaAccount) => (
        <span
          style={{
            fontSize: 12,
            color: phoneColor(record.registered_phone_number_count, record.phone_number_count),
            fontWeight: 500,
          }}
        >
          {record.registered_phone_number_count}/{record.phone_number_count}
        </span>
      ),
    },
    {
      title: "Webhook",
      key: "wh",
      width: 90,
      render: (_: unknown, record: MetaWabaAccount) => {
        const { label, reason } = webhookBrief(record);
        return (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: whColor(record.webhook_runtime_status),
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 11, color: "#666" }}>{label}</span>
            </div>
            {reason ? <div style={{ fontSize: 9, color: "#ff4d4f", lineHeight: 1.2 }}>{reason}</div> : null}
          </div>
        );
      },
    },
    {
      title: "最后活跃",
      key: "lastAct",
      width: 80,
      render: (_: unknown, record: MetaWabaAccount) => (
        <span style={{ fontSize: 11, color: record.webhook_last_event_received_at ? "#aaa" : "#ddd" }}>
          {shortTs(record.webhook_last_event_received_at) || "--"}
        </span>
      ),
    },
    {
      title: "",
      key: "actions",
      width: 40,
      render: (_: unknown, record: MetaWabaAccount) => (
        <Dropdown
          trigger={["click"]}
          menu={{
            items: [
              {
                key: "health",
                icon: <ThunderboltOutlined />,
                label: "检测连通性",
                onClick: () => {
                  healthCheckMetaAccount(record.account_id, record.waba_id)
                    .then((res) => {
                      if (res.status === "healthy") {
                        message.success("链路正常");
                      } else {
                        message.warning(`状态: ${res.status}`);
                      }
                    })
                    .catch((err: unknown) => {
                      message.error(err instanceof Error ? err.message : "检测失败");
                    });
                },
              },
              {
                key: "sub",
                icon: <LinkOutlined />,
                label: "订阅 Webhook",
                disabled: record.webhook_subscribed,
                onClick: () => {
                  getGlobalWebhookConfig().then((cfg) => {
                    if (!cfg.callback_url) {
                      message.warning("请先设置全局回调地址");
                      return;
                    }
                    subscribeMetaWebhook(record.account_id, record.waba_id, {
                      callback_url: cfg.callback_url,
                      verify_token: cfg.verify_token || undefined,
                    })
                      .then(() => {
                        message.success("已订阅");
                        onRefresh();
                      })
                      .catch((err: unknown) => {
                        message.error(err instanceof Error ? err.message : "订阅失败");
                      });
                  });
                },
              },
            ],
          }}
        >
          <Button
            type="text"
            size="small"
            icon={<MoreOutlined />}
            style={{ opacity: 0.4 }}
            onClick={(event) => event.stopPropagation()}
          />
        </Dropdown>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "0 0 8px", flexShrink: 0, display: "flex", gap: 8, alignItems: "center" }}>
        <Select
          size="small"
          allowClear
          placeholder="接入方式"
          value={filterMode || undefined}
          onChange={(value) => onFilterModeChange((value as string | undefined) ?? "")}
          style={{ width: 100 }}
          options={[
            { label: "手动", value: "manual" },
            { label: "Signup", value: "embedded_signup" },
          ]}
        />
        <Input
          ref={inputRef}
          size="small"
          placeholder="搜索名称 / WABA / 备注"
          value={searchText}
          onChange={(event) => onSearchChange(event.target.value)}
          allowClear
          style={{ flex: 1 }}
        />
        <Button size="small" onClick={onSignup}>接入新账户</Button>
        <Button size="small" type="primary" onClick={onManualAdd}>添加</Button>
        <Button size="small" onClick={onRefresh} loading={loading}>刷新</Button>
        <Popover
          content={whContent}
          title="全局 Webhook 配置"
          trigger="click"
          open={configOpen}
          onOpenChange={setConfigOpen}
          placement="bottomRight"
        >
          <Button size="small" icon={<SettingOutlined />}>配置</Button>
        </Popover>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Table<MetaWabaAccount>
          size="small"
          rowKey={(record) => `${record.account_id}:${record.waba_id}`}
          columns={columns}
          dataSource={filtered}
          pagination={{
            pageSize: 50,
            pageSizeOptions: ["20", "50", "100"],
            showSizeChanger: true,
            showTotal: (total: number) => `共 ${total} 个账号`,
            size: "small",
          }}
          scroll={{ y: "100%" }}
          onRow={(record) => ({
            onClick: () => onSelect(`${record.account_id}:${record.waba_id}`),
            style: {
              cursor: "pointer",
              background: selectedWabaKey === `${record.account_id}:${record.waba_id}` ? "#e6f4ff" : undefined,
            },
          })}
        />
      </div>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Button, Card, Collapse, Descriptions, message, Popconfirm, Switch, Tag, Typography, Space, Badge, Result,
} from "antd";
import {
  ThunderboltOutlined, SyncOutlined, LinkOutlined, DeleteOutlined,
  EditOutlined, CopyOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from "@ant-design/icons";
import type { MetaWabaAccount } from "../../services/api";
import {
  updateMetaAccountStatus, updateMetaWabaStatus, updateMetaPhoneNumberStatus,
  syncMetaPhoneNumbers, subscribeMetaWebhook, deleteMetaAccount,
  healthCheckMetaAccount, getGlobalWebhookConfig,
} from "../../services/api";
import { whColor, whLabel, qualityColor, shortTs } from "./utils";

interface AccountDetailPanelProps {
  account: MetaWabaAccount;
  onRefresh: () => void;
  onEdit?: (account: MetaWabaAccount) => void;
  onDeleted?: () => void;
}

function copyId(text: string): void {
  navigator.clipboard.writeText(text).then(() => message.success("已复制")).catch(() => {});
}

export function AccountDetailPanel({ account, onRefresh, onEdit, onDeleted }: AccountDetailPanelProps) {
  const [syncing, setSyncing] = useState(false);
  const [subscribing, setSubscribing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [healthResult, setHealthResult] = useState<any>(null);
  const [globalWhUrl, setGlobalWhUrl] = useState("");
  const loadedGlobalRef = useRef(false);

  useEffect(() => {
    if (!loadedGlobalRef.current) {
      loadedGlobalRef.current = true;
      getGlobalWebhookConfig().then((cfg) => setGlobalWhUrl(cfg.callback_url)).catch(() => {});
    }
  }, []);

  const handleAccountToggle = useCallback(async (checked: boolean) => {
    try {
      await updateMetaAccountStatus(account.account_id, { is_active: checked });
      message.success(checked ? "账户已启用" : "账户已禁用");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [account.account_id, onRefresh]);

  const handleWabaToggle = useCallback(async (checked: boolean) => {
    try {
      await updateMetaWabaStatus(account.account_id, account.waba_id, { is_active: checked });
      message.success(checked ? "WABA 已启用" : "WABA 已禁用");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [account.account_id, account.waba_id, onRefresh]);

  const handlePhoneToggle = useCallback(async (phoneNumberId: string, checked: boolean) => {
    try {
      await updateMetaPhoneNumberStatus(account.account_id, account.waba_id, phoneNumberId, { is_active: checked });
      message.success(checked ? "号码已启用" : "号码已禁用");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [account.account_id, account.waba_id, onRefresh]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    try {
      const result = await syncMetaPhoneNumbers(account.account_id, account.waba_id);
      message.success(`同步完成: ${result.synced_count} 个号码`);
      onRefresh();
    } catch { message.error("同步失败"); }
    finally { setSyncing(false); }
  }, [account.account_id, account.waba_id, onRefresh]);

  const handleSubscribe = useCallback(async () => {
    setSubscribing(true);
    try {
      const cfg = await getGlobalWebhookConfig();
      if (!cfg.callback_url) { message.warning("请先在全局 Webhook 配置中设置回调地址"); return; }
      await subscribeMetaWebhook(account.account_id, account.waba_id, {
        callback_url: cfg.callback_url,
        verify_token: cfg.verify_token || undefined,
      });
      message.success("Webhook 订阅成功");
      onRefresh();
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "订阅失败");
    } finally { setSubscribing(false); }
  }, [account.account_id, account.waba_id, onRefresh]);

  const handleHealthCheck = useCallback(async () => {
    setChecking(true);
    try {
      const result = await healthCheckMetaAccount(account.account_id, account.waba_id);
      setHealthResult(result);
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "检测失败");
    } finally { setChecking(false); }
  }, [account.account_id, account.waba_id]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      await deleteMetaAccount(account.account_id, account.waba_id);
      message.success("账户已删除");
      onDeleted?.();
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "删除失败");
    } finally { setDeleting(false); }
  }, [account.account_id, account.waba_id, onDeleted]);

  /* ---- computed ---- */
  const allOk = account.has_access_token && account.webhook_runtime_status === "healthy" && account.phone_number_count > 0;
  const someWarn = !account.has_access_token || account.webhook_runtime_status !== "healthy" || account.registered_phone_number_count < account.phone_number_count;

  return (
    <div style={{ padding: "0 0 0 12px", height: "100%", overflow: "auto" }}>
      {/* ---- HEADER ---- */}
      <Card size="small" styles={{ body: { padding: 10 } }} style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <Typography.Text strong style={{ fontSize: 14 }} ellipsis>{account.display_name}</Typography.Text>
              <Tag color={account.is_active ? "success" : "default"} style={{ fontSize: 9 }}>
                {account.is_active ? "WABA启用" : "WABA禁用"}
              </Tag>
            </div>
            <Typography.Text type="secondary" style={{ fontSize: 10 }}>
              {account.onboarding_mode === "embedded_signup" ? "Embedded Signup" : "手动接入"} · {account.token_source}
              {account.notes && ` · ${account.notes}`}
            </Typography.Text>
          </div>
          <Space size={2} style={{ flexShrink: 0 }}>
            {onEdit && <Button size="small" type="link" icon={<EditOutlined />} style={{ fontSize: 10, padding: "0 4px" }} onClick={() => onEdit(account)} />}
            <Button size="small" type="link" icon={<ThunderboltOutlined />} loading={checking} style={{ fontSize: 10, padding: "0 4px" }} onClick={handleHealthCheck}>检测</Button>
            <Popconfirm title="确认删除此账户？" onConfirm={handleDelete}>
              <Button size="small" type="link" danger icon={<DeleteOutlined />} loading={deleting} style={{ fontSize: 10, padding: "0 4px" }} />
            </Popconfirm>
          </Space>
        </div>
      </Card>

      {/* ---- QUICK ACTIONS ---- */}
      <Card size="small" styles={{ body: { padding: "6px 10px" } }} style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Typography.Text style={{ fontSize: 10 }}>账户</Typography.Text>
              <Popconfirm title={account.account_is_active ? "确认禁用？" : "确认启用？"} onConfirm={() => handleAccountToggle(!account.account_is_active)}>
                <Switch size="small" checked={account.account_is_active} />
              </Popconfirm>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <Typography.Text style={{ fontSize: 10 }}>WABA</Typography.Text>
              <Popconfirm title={account.is_active ? "确认禁用？" : "确认启用？"} onConfirm={() => handleWabaToggle(!account.is_active)}>
                <Switch size="small" checked={account.is_active} />
              </Popconfirm>
            </div>
          </div>
          <Button size="small" icon={<SyncOutlined />} loading={syncing} onClick={handleSync} style={{ fontSize: 10 }}>
            同步号码
          </Button>
        </div>
      </Card>

      {/* ---- CONNECTION STATUS ---- */}
      <Card size="small" styles={{ body: { padding: 10 } }} style={{ marginBottom: 8 }}>
        <Typography.Text strong style={{ fontSize: 11 }}>连接状态</Typography.Text>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
          <Tag color={account.has_access_token ? "success" : "error"} style={{ fontSize: 9 }}>Token {account.has_access_token ? "✓" : "✗"}</Tag>
          <Tag color={account.has_verify_token || globalWhUrl ? "success" : "default"} style={{ fontSize: 9 }}>Verify {account.has_verify_token || globalWhUrl ? "✓" : "—"}</Tag>
          <Tag color={account.ready_for_outbound_messages ? "success" : "default"} style={{ fontSize: 9 }}>出站就绪 {account.ready_for_outbound_messages ? "✓" : "✗"}</Tag>
        </div>
        {healthResult && (
          <div style={{ marginTop: 4 }}>
            <Tag color={(healthResult as any).status === "healthy" ? "success" : "error"} style={{ fontSize: 9 }}>
              链路检测: {(healthResult as any).status}
            </Tag>
          </div>
        )}
      </Card>

      {/* ---- PHONE NUMBERS ---- */}
      <Card size="small" styles={{ body: { padding: 10 } }} style={{ marginBottom: 8 }}
        title={<Typography.Text strong style={{ fontSize: 11 }}>号码 ({account.phone_number_count})</Typography.Text>}
        extra={<Tag style={{ fontSize: 9 }}>{account.registered_phone_number_count}/{account.phone_number_count} 已注册</Tag>}>
        {account.phone_numbers.map((pn) => (
          <div key={pn.phone_number_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 0", borderBottom: "1px solid #f5f5f5" }}>
            <div>
              <Typography.Text style={{ fontSize: 11 }}>{pn.display_phone_number}</Typography.Text>
              <div style={{ display: "flex", gap: 3, marginTop: 1 }}>
                <Tag color={qualityColor(pn.quality_rating)} style={{ fontSize: 8, margin: 0, lineHeight: "14px" }}>{pn.quality_rating}</Tag>
                <Tag color={pn.is_registered ? "success" : "default"} style={{ fontSize: 8, margin: 0, lineHeight: "14px" }}>{pn.is_registered ? "已注册" : "未注册"}</Tag>
              </div>
            </div>
            <Switch size="small" checked={pn.is_active} onChange={(chk) => handlePhoneToggle(pn.phone_number_id, chk)} />
          </div>
        ))}
      </Card>

      {/* ---- WEBHOOK ---- */}
      <Card size="small" styles={{ body: { padding: 10 } }} style={{ marginBottom: 8 }}
        title={<Typography.Text strong style={{ fontSize: 11 }}>Webhook</Typography.Text>}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: whColor(account.webhook_runtime_status) }} />
          <Typography.Text style={{ fontSize: 11 }}>{whLabel(account.webhook_runtime_status)}</Typography.Text>
        </div>
        <Descriptions size="small" column={1} colon={false} labelStyle={{ fontSize: 9, color: "#aaa" }} contentStyle={{ fontSize: 10 }}>
          <Descriptions.Item label="最后事件">{shortTs(account.webhook_last_event_received_at) || "—"}</Descriptions.Item>
          {account.webhook_signature_failure_count > 0 && (
            <Descriptions.Item label="签名失败"><Typography.Text type="danger">{account.webhook_signature_failure_count} 次</Typography.Text></Descriptions.Item>
          )}
          {account.webhook_runtime_error && (
            <Descriptions.Item label="错误"><Typography.Text type="danger" style={{ fontSize: 9 }}>{account.webhook_runtime_error}</Typography.Text></Descriptions.Item>
          )}
        </Descriptions>
        {!account.webhook_subscribed && (
          <Button type="primary" size="small" block loading={subscribing} onClick={handleSubscribe} icon={<LinkOutlined />} style={{ fontSize: 10, marginTop: 6 }}>
            {globalWhUrl ? `订阅 Webhook (${globalWhUrl})` : "订阅 Webhook"}
          </Button>
        )}
      </Card>

      {/* ---- IDs ---- */}
      <Card size="small" styles={{ body: { padding: 10 } }}>
        <Typography.Text strong style={{ fontSize: 11 }}>ID 信息</Typography.Text>
        <Descriptions size="small" column={1} colon={false} labelStyle={{ fontSize: 9, color: "#aaa" }} contentStyle={{ fontSize: 10 }}>
          <Descriptions.Item label="Account ID">
            <Typography.Text copyable style={{ fontSize: 10, fontFamily: "monospace" }}>{account.account_id}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="WABA ID">
            <Typography.Text copyable style={{ fontSize: 10, fontFamily: "monospace" }}>{account.waba_id}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Portfolio">
            <Typography.Text style={{ fontSize: 9, fontFamily: "monospace", color: "#888" }}>{account.meta_business_portfolio_id}</Typography.Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* ---- Blocking Reasons ---- */}
      {account.blocking_reasons.length > 0 && (
        <Card size="small" styles={{ body: { padding: 10 } }} style={{ marginTop: 8 }}>
          <Typography.Text strong style={{ fontSize: 11, color: "#ff4d4f" }}>阻塞原因</Typography.Text>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
            {account.blocking_reasons.map((r, i) => <Tag key={i} color="error" style={{ fontSize: 9, margin: 0 }}>{r}</Tag>)}
          </div>
        </Card>
      )}
    </div>
  );
}

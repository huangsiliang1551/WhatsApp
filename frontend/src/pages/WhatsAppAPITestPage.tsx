import { LinkOutlined, SearchOutlined, SendOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Form,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useCallback, useMemo, useState, type JSX } from "react";

import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getGlobalWebhookConfig,
  healthCheckMetaAccount,
  listMetaAccounts,
  queryBusinessProfile,
  queryPhoneDetail,
  sendTestMessage,
  subscribeMetaWebhook,
  type MetaWabaAccount,
} from "../services/api";

interface PageData {
  accounts: MetaWabaAccount[];
}

function JsonBlock({ data }: { data: unknown }): JSX.Element {
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return (
    <pre
      style={{
        background: "#1e1e1e",
        borderRadius: 6,
        color: "#d4d4d4",
        fontFamily: "Consolas, Monaco, monospace",
        fontSize: 11,
        margin: 0,
        maxHeight: 320,
        overflow: "auto",
        padding: 12,
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}
    >
      {text}
    </pre>
  );
}

function ResultPanel({
  error,
  result,
  title,
}: {
  error?: string;
  result?: unknown;
  title: string;
}): JSX.Element | null {
  if (!error && !result) return null;

  return (
    <div style={{ marginTop: 8 }}>
      {error ? <Alert message={error} showIcon type="error" /> : null}
      {result ? (
        <div style={{ marginTop: error ? 8 : 0 }}>
          <Typography.Text strong style={{ display: "block", fontSize: 11, marginBottom: 4 }}>
            {title}
          </Typography.Text>
          <JsonBlock data={result} />
        </div>
      ) : null}
    </div>
  );
}

export function WhatsAppAPITestPage(): JSX.Element {
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const fetchData = useCallback(async (): Promise<PageData> => {
    const accounts = await listMetaAccounts().catch(() => [] as MetaWabaAccount[]);
    return { accounts };
  }, []);

  const { data, loading, reload } = usePageData({ fetcher: fetchData });
  const accounts = data?.accounts ?? [];

  const selectedAccount = useMemo(
    () => accounts.find((account) => `${account.account_id}:${account.waba_id}` === selectedKey) ?? null,
    [accounts, selectedKey]
  );

  const aid = selectedAccount?.account_id ?? "";
  const wid = selectedAccount?.waba_id ?? "";
  const phones = selectedAccount?.phone_numbers ?? [];

  const setOpState = useCallback((key: string, result?: unknown, error?: string) => {
    setBusy((prev) => ({ ...prev, [key]: false }));
    setResults((prev) => ({ ...prev, [key]: result }));
    setErrors((prev) => ({ ...prev, [key]: error ?? "" }));
  }, []);

  const runOp = useCallback(
    async (key: string, fn: () => Promise<unknown>) => {
      setBusy((prev) => ({ ...prev, [key]: true }));
      setErrors((prev) => ({ ...prev, [key]: "" }));
      try {
        const result = await fn();
        setOpState(key, result);
      } catch (err) {
        setOpState(key, null, err instanceof Error ? err.message : String(err));
      }
    },
    [setOpState]
  );

  const handleHealthCheck = useCallback(() => runOp("health", () => healthCheckMetaAccount(aid, wid)), [aid, runOp, wid]);

  const handleSendMsg = useCallback(
    (values: { phone_id: string; to: string; text: string }) =>
      runOp("send_msg", () => sendTestMessage(aid, wid, values)),
    [aid, runOp, wid]
  );

  const handlePhoneDetail = useCallback(
    (phoneId: string) => runOp(`phone_${phoneId}`, () => queryPhoneDetail(aid, wid, phoneId)),
    [aid, runOp, wid]
  );

  const handleBizProfile = useCallback(
    (phoneId: string) => runOp(`biz_${phoneId}`, () => queryBusinessProfile(aid, wid, phoneId)),
    [aid, runOp, wid]
  );

  const handleWebhookConfig = useCallback(
    async (values: { callback_url?: string; verify_token?: string }) => {
      const config = await getGlobalWebhookConfig();
      const callbackUrl = values.callback_url || config.callback_url;
      if (!callbackUrl) {
        message.warning("请先设置回调地址");
        return;
      }

      await runOp("wh_sub", () =>
        subscribeMetaWebhook(aid, wid, {
          callback_url: callbackUrl,
          verify_token: values.verify_token || config.verify_token || undefined,
        })
      );
    },
    [aid, runOp, wid]
  );

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新账户列表
        </Button>
      }
      subtitle="Token 验证、发测试消息、号码详情与 Webhook 订阅"
      title="WhatsApp API 调试"
    >
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <Typography.Text strong style={{ fontSize: 12 }}>
            选择账户
          </Typography.Text>
          <Select
            onChange={(value) => {
              setSelectedKey(value ?? "");
              setResults({});
              setErrors({});
            }}
            options={accounts.map((account) => ({
              value: `${account.account_id}:${account.waba_id}`,
              label: `${account.display_name} (${account.waba_id.slice(0, 14)}...)`,
            }))}
            placeholder="选择一个 Meta 账户 / WABA"
            size="small"
            style={{ minWidth: 300 }}
            value={selectedKey || undefined}
          />
          {selectedAccount ? (
            <>
              <Tag color={selectedAccount.is_active ? "success" : "default"}>
                {selectedAccount.is_active ? "启用" : "停用"}
              </Tag>
              <Tag>{selectedAccount.token_source}</Tag>
              <Tag color={selectedAccount.has_access_token ? "success" : "error"}>
                Token: {selectedAccount.has_access_token ? "已配置" : "未配置"}
              </Tag>
            </>
          ) : null}
        </Space>
      </Card>

      {!selectedAccount ? (
        <Alert
          message="请先选择一个已配置 Meta Access Token 的账户，然后再进行 API 调试。"
          style={{ marginBottom: 12 }}
          type="info"
        />
      ) : (
        <Row gutter={[12, 12]}>
          <Col lg={12} xs={24}>
            <Card
              extra={
                <Button
                  disabled={!selectedAccount.has_access_token}
                  loading={busy.health}
                  onClick={() => void handleHealthCheck()}
                  size="small"
                  type="primary"
                >
                  验证 Token
                </Button>
              }
              size="small"
              title={
                <span>
                  <LinkOutlined /> 运行配置与 Token
                </span>
              }
            >
              <Descriptions
                colon={false}
                column={1}
                contentStyle={{ fontSize: 12 }}
                labelStyle={{ color: "#888", fontSize: 11 }}
                size="small"
              >
                <Descriptions.Item label="WABA ID">
                  <Typography.Text copyable style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {wid}
                  </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="Business Portfolio">
                  <Typography.Text style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {selectedAccount.meta_business_portfolio_id || "-"}
                  </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="Access Token">
                  <Typography.Text style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {selectedAccount.has_access_token ? "***已配置***" : "未配置"}
                  </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="号码数量">{phones.length}</Descriptions.Item>
              </Descriptions>

              <ResultPanel error={errors.health} result={results.health} title="Token 验证返回" />
            </Card>

            <Card
              size="small"
              style={{ marginTop: 12 }}
              title={
                <span>
                  <SendOutlined /> 发送文本消息
                </span>
              }
            >
              <Typography.Text style={{ display: "block", fontSize: 11, marginBottom: 8 }} type="secondary">
                发送消息时必须填写 Phone Number ID，而不是 WABA ID。
              </Typography.Text>
              <Form
                layout="inline"
                onFinish={handleSendMsg}
                size="small"
                style={{ display: "flex", flexWrap: "wrap", gap: 6 }}
              >
                <Form.Item name="phone_id" rules={[{ required: true, message: "必填" }]} style={{ flex: "1 1 160px", marginBottom: 8 }}>
                  <Input placeholder="发送方 Phone ID" />
                </Form.Item>
                <Form.Item name="to" rules={[{ required: true, message: "必填" }]} style={{ flex: "1 1 140px", marginBottom: 8 }}>
                  <Input placeholder="目标号码" />
                </Form.Item>
                <Form.Item name="text" rules={[{ required: true, message: "必填" }]} style={{ flex: "2 1 220px", marginBottom: 8 }}>
                  <Input placeholder="消息内容" />
                </Form.Item>
                <Form.Item style={{ marginBottom: 8 }}>
                  <Button
                    disabled={!selectedAccount.has_access_token}
                    htmlType="submit"
                    icon={<SendOutlined />}
                    loading={busy.send_msg}
                    type="primary"
                  >
                    发送
                  </Button>
                </Form.Item>
              </Form>

              <ResultPanel error={errors.send_msg} result={results.send_msg} title="发送消息返回" />
            </Card>
          </Col>

          <Col lg={12} xs={24}>
            <Card
              size="small"
              title={
                <span>
                  <SearchOutlined /> 号码与账号查询
                </span>
              }
            >
              {phones.length === 0 ? (
                <Typography.Text style={{ fontSize: 12 }} type="secondary">
                  当前 WABA 下没有号码，请先在 Meta 账户中完成号码配置。
                </Typography.Text>
              ) : (
                phones.map((phone) => (
                  <div
                    key={phone.phone_number_id}
                    style={{ borderBottom: "1px solid #f0f0f0", padding: "8px 0" }}
                  >
                    <div style={{ alignItems: "center", display: "flex", justifyContent: "space-between" }}>
                      <div>
                        <Typography.Text strong style={{ fontSize: 12 }}>
                          {phone.display_phone_number}
                        </Typography.Text>
                        <Typography.Text style={{ fontSize: 10, marginLeft: 6 }} type="secondary">
                          {phone.phone_number_id}
                        </Typography.Text>
                      </div>
                      <Space size={4}>
                        <Button
                          loading={busy[`phone_${phone.phone_number_id}`]}
                          onClick={() => void handlePhoneDetail(phone.phone_number_id)}
                          size="small"
                        >
                          号码详情
                        </Button>
                        <Button
                          loading={busy[`biz_${phone.phone_number_id}`]}
                          onClick={() => void handleBizProfile(phone.phone_number_id)}
                          size="small"
                        >
                          业务资料
                        </Button>
                      </Space>
                    </div>

                    <ResultPanel
                      error={errors[`phone_${phone.phone_number_id}`]}
                      result={results[`phone_${phone.phone_number_id}`]}
                      title="号码详情返回"
                    />
                    <ResultPanel
                      error={errors[`biz_${phone.phone_number_id}`]}
                      result={results[`biz_${phone.phone_number_id}`]}
                      title="业务资料返回"
                    />
                  </div>
                ))
              )}
            </Card>

            <Card size="small" style={{ marginTop: 12 }} title="Webhook 配置">
              <Descriptions
                colon={false}
                column={1}
                contentStyle={{ fontSize: 12 }}
                labelStyle={{ color: "#888", fontSize: 11 }}
                size="small"
              >
                <Descriptions.Item label="Verify 路径">
                  <Typography.Text copyable style={{ fontFamily: "monospace", fontSize: 10 }}>
                    {selectedAccount.webhook_verify_path}
                  </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="接收路径">
                  <Typography.Text copyable style={{ fontFamily: "monospace", fontSize: 10 }}>
                    {selectedAccount.webhook_receive_path}
                  </Typography.Text>
                </Descriptions.Item>
                <Descriptions.Item label="验证状态">
                  <Tag color={selectedAccount.webhook_verification_status === "verified" ? "success" : "default"}>
                    {selectedAccount.webhook_verification_status}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="运行状态">
                  <Tag color={selectedAccount.webhook_runtime_status === "healthy" ? "success" : "warning"}>
                    {selectedAccount.webhook_runtime_status}
                  </Tag>
                </Descriptions.Item>
                {selectedAccount.webhook_last_event_received_at ? (
                  <Descriptions.Item label="最后事件">
                    {new Date(selectedAccount.webhook_last_event_received_at).toLocaleString("zh-CN")}
                  </Descriptions.Item>
                ) : null}
              </Descriptions>

              <Form layout="inline" onFinish={handleWebhookConfig} size="small" style={{ marginTop: 8 }}>
                <Form.Item name="callback_url" style={{ flex: 1, marginBottom: 8 }}>
                  <Input placeholder="回调 URL，留空则使用全局配置" style={{ width: 250 }} />
                </Form.Item>
                <Form.Item name="verify_token" style={{ marginBottom: 8 }}>
                  <Input placeholder="Verify Token，可选" style={{ width: 150 }} />
                </Form.Item>
                <Form.Item style={{ marginBottom: 8 }}>
                  <Button htmlType="submit" loading={busy.wh_sub} type="primary">
                    订阅 Webhook
                  </Button>
                </Form.Item>
              </Form>

              <ResultPanel error={errors.wh_sub} result={results.wh_sub} title="Webhook 订阅返回" />
            </Card>
          </Col>
        </Row>
      )}

      <Divider style={{ margin: "12px 0" }} />
      <Typography.Text style={{ fontSize: 11 }} type="secondary">
        提示：先在 Meta 账户管理页完成 Access Token 配置，再回到这里做健康检查、发消息和 Webhook 联调。
      </Typography.Text>
    </PageShell>
  );
}

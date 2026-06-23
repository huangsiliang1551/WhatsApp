import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Form, Input, Modal, Select, Switch, Tag, Typography, message } from "antd";
import { MinusCircleOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons";
import type { DiscoverResponse, MetaWabaAccount } from "../../services/api";
import { createManualMetaAccount, discoverMetaAccount, updateMetaAccount } from "../../services/api";
import type { ManualFormValues } from "./types";

const { TextArea } = Input;

function genAccountId(): string {
  return `acc-${Math.random().toString(16).slice(2, 10)}`;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  editingAccount?: MetaWabaAccount | null;
  onSaved?: () => void;
}

export function CreateManualModal({
  open,
  onClose,
  onCreated,
  editingAccount,
  onSaved,
}: Props) {
  const [form] = Form.useForm<ManualFormValues>();
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoverResult, setDiscoverResult] = useState<DiscoverResponse | null>(null);
  const defaultIdRef = useRef(genAccountId());
  const isEdit = Boolean(editingAccount);

  useEffect(() => {
    if (!open) {
      setDiscoverResult(null);
      defaultIdRef.current = genAccountId();
      return;
    }

    if (editingAccount) {
      form.setFieldsValue({
        display_name: editingAccount.display_name,
        meta_business_portfolio_id: editingAccount.meta_business_portfolio_id,
        waba_id: editingAccount.waba_id,
        access_token: "",
        app_secret: "",
        token_source: editingAccount.token_source as "system_user" | "user_access_token",
        notes: editingAccount.notes ?? undefined,
        phone_numbers: editingAccount.phone_numbers.map((phone) => ({
          phone_number_id: phone.phone_number_id,
          display_phone_number: phone.display_phone_number,
          verified_name: phone.verified_name ?? undefined,
          quality_rating: phone.quality_rating,
          is_registered: phone.is_registered,
        })),
      });
      return;
    }

    form.resetFields();
    form.setFieldsValue({
      display_name: defaultIdRef.current,
      token_source: "system_user",
      phone_numbers: [{ quality_rating: "UNKNOWN", is_registered: false }],
    });
  }, [editingAccount, form, open]);

  const handleDiscover = useCallback(async () => {
    const wabaId = form.getFieldValue("waba_id");
    const accessToken = form.getFieldValue("access_token");

    if (!wabaId) {
      message.warning("请先填写 WABA ID");
      return;
    }
    if (!accessToken && !isEdit) {
      message.warning("请先填写 Access Token");
      return;
    }

    setDiscovering(true);
    setDiscoverResult(null);

    try {
      const result = await discoverMetaAccount({
        waba_id: wabaId,
        access_token: accessToken || "",
        account_id: isEdit ? editingAccount?.account_id : undefined,
      });
      setDiscoverResult(result);

      if (!result.ok) {
        message.error(result.errors[0] || "加载失败");
        return;
      }

      const portfolioId = (result.fields["business_portfolio_id"]?.value as string) || "";
      if (portfolioId) {
        form.setFieldValue("meta_business_portfolio_id", portfolioId);
      }

      const phones = (result.fields["phone_numbers"]?.value as Array<Record<string, unknown>>) || [];
      if (phones.length > 0) {
        form.setFieldValue(
          "phone_numbers",
          phones.map((phone) => ({
            phone_number_id: String(phone.phone_number_id ?? ""),
            display_phone_number: String(phone.display_phone_number ?? ""),
            verified_name: phone.verified_name ? String(phone.verified_name) : undefined,
            quality_rating: String(phone.quality_rating ?? "UNKNOWN"),
            is_registered: Boolean(phone.is_registered),
          }))
        );
      }

      message.success("加载完成");
    } catch (err: unknown) {
      message.error(err instanceof Error ? err.message : "请求失败");
    } finally {
      setDiscovering(false);
    }
  }, [editingAccount?.account_id, form, isEdit]);

  const handleOk = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const phoneNumbers = (values.phone_numbers ?? []).map((phone) => ({
        phone_number_id: phone.phone_number_id,
        display_phone_number: phone.display_phone_number,
        verified_name: phone.verified_name || null,
        quality_rating: phone.quality_rating,
        is_registered: phone.is_registered,
        is_active: true,
      }));

      if (isEdit && editingAccount) {
        await updateMetaAccount(editingAccount.account_id, editingAccount.waba_id, {
          display_name: values.display_name,
          meta_business_portfolio_id: values.meta_business_portfolio_id,
          access_token: values.access_token || undefined,
          token_source: values.token_source,
          app_secret: values.app_secret || undefined,
          notes: values.notes || undefined,
          phone_numbers: phoneNumbers,
        });
        message.success("已更新");
        onSaved?.();
      } else {
        await createManualMetaAccount({
          display_name: values.display_name,
          meta_business_portfolio_id: values.meta_business_portfolio_id,
          waba_id: values.waba_id,
          access_token: values.access_token,
          token_source: values.token_source,
          app_secret: values.app_secret || undefined,
          notes: values.notes || undefined,
          phone_numbers: phoneNumbers,
        });
        message.success("已添加");
        form.resetFields();
        setDiscoverResult(null);
        onCreated();
      }
    } catch (err: unknown) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }, [editingAccount, form, isEdit, onCreated, onSaved]);

  const discovery = discoverResult;
  const discoveryOk = discovery?.ok === true;

  return (
    <Modal
      title={isEdit ? "编辑账户" : "添加 Meta 账户"}
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={loading}
      okText={isEdit ? "保存" : "添加"}
      cancelText="取消"
      width={700}
      destroyOnClose
    >
      <Form<ManualFormValues>
        form={form}
        layout="vertical"
        size="small"
        initialValues={{
          token_source: "system_user",
          phone_numbers: [{ quality_rating: "UNKNOWN" as const, is_registered: false }],
        }}
        style={{ marginTop: 8 }}
      >
        <div style={{ display: "flex", gap: 10 }}>
          <Form.Item
            name="display_name"
            label="显示名称"
            rules={[{ required: true, message: "必填" }]}
            style={{ flex: 1, marginBottom: 10 }}
          >
            <Input placeholder={isEdit ? undefined : `默认 ${defaultIdRef.current}，可修改`} />
          </Form.Item>
          <Form.Item
            name="waba_id"
            label="WABA ID"
            rules={[{ required: true, message: "必填" }]}
            style={{ flex: 1, marginBottom: 10 }}
          >
            <Input placeholder="WhatsApp Business Account ID" disabled={isEdit} />
          </Form.Item>
          <Form.Item
            name="meta_business_portfolio_id"
            label="Portfolio ID"
            style={{ flex: "1 1 200px", marginBottom: 10 }}
          >
            <Input placeholder="自动发现或手动填写" />
          </Form.Item>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <Form.Item
            name="token_source"
            label="Token 来源"
            rules={[{ required: true, message: "必填" }]}
            style={{ width: 140, marginBottom: 10 }}
          >
            <Select
              options={[
                { label: "System User", value: "system_user" },
                { label: "User Token", value: "user_access_token" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="access_token"
            label="Access Token"
            rules={isEdit ? [] : [{ required: true, message: "必填" }]}
            style={{ flex: 1, marginBottom: 10 }}
          >
            <Input.Password placeholder={isEdit ? "留空则不修改" : "Meta Access Token"} />
          </Form.Item>
          <Form.Item
            name="app_secret"
            label="App Secret"
            style={{ flex: "1 1 200px", marginBottom: 10 }}
          >
            <Input.Password placeholder={isEdit ? "留空则不修改" : "开发者后台 App Secret"} />
          </Form.Item>
        </div>

        <Form.Item name="notes" label="备注" style={{ marginBottom: 10 }}>
          <TextArea rows={3} placeholder="例如归属 FB 账号、使用场景、维护说明" style={{ fontSize: 12 }} />
        </Form.Item>

        <div style={{ marginBottom: 10 }}>
          <Button
            type="dashed"
            icon={<SearchOutlined />}
            loading={discovering}
            onClick={handleDiscover}
            block
          >
            从 Meta 自动加载号码和 WABA 信息
          </Button>
        </div>

        {discovering ? (
          <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 10 }}>
            正在从 Meta 拉取信息...
          </Typography.Text>
        ) : null}

        {discoveryOk ? (() => {
          const wabaName = discovery?.fields["waba_name"]?.value || discovery?.fields["waba_id"]?.value || "--";
          const portfolioId = discovery?.fields["business_portfolio_id"]?.value;
          const appId = discovery?.fields["app_id"]?.value;
          const phones = discovery?.fields["phone_numbers"]?.value;
          const phoneCount = Array.isArray(phones) ? phones.length : 0;
          const summary: string[] = [`WABA: ${String(wabaName)}`];

          if (portfolioId) {
            summary.push(`Portfolio: ${String(portfolioId)}`);
          }
          if (appId && discovery?.fields["app_id"]?.status === "ok") {
            summary.push(`App: ${String(appId).slice(0, 14)}`);
          }
          summary.push(`号码: ${phoneCount} 个`);

          return (
            <div
              style={{
                marginBottom: 10,
                padding: "6px 10px",
                background: "#f6ffed",
                borderRadius: 4,
                border: "1px solid #b7eb8f",
                fontSize: 11,
                display: "flex",
                flexWrap: "wrap",
                gap: "2px 12px",
              }}
            >
              <span style={{ color: "#52c41a", fontWeight: 600 }}>已加载</span>
              {summary.map((item, index) => (
                <span key={index}>{item}</span>
              ))}
            </div>
          );
        })() : null}

        {discovery && !discoveryOk ? (
          <Typography.Text type="danger" style={{ fontSize: 11, display: "block", marginBottom: 10 }}>
            加载失败: {discovery.errors[0]}
          </Typography.Text>
        ) : null}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <Typography.Text style={{ fontSize: 12, fontWeight: 600 }}>号码配置</Typography.Text>
          {discoveryOk ? <Tag color="green" style={{ fontSize: 9, margin: 0 }}>已自动加载</Tag> : null}
        </div>

        <Form.List
          name="phone_numbers"
          rules={[
            {
              validator: async (_rule: unknown, value?: unknown[]) => {
                if (!value || value.length === 0) {
                  throw new Error("请至少添加一个号码");
                }
              },
            },
          ]}
        >
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...rest }) => (
                <div
                  key={key}
                  style={{ background: "#fafafa", padding: "3px 8px", borderRadius: 4, marginBottom: 4 }}
                >
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <Form.Item
                      {...rest}
                      name={[name, "phone_number_id"]}
                      rules={[{ required: true, message: "必填" }]}
                      style={{ flex: "1 1 180px", marginBottom: 0 }}
                    >
                      <Input placeholder="Phone Number ID" style={{ fontSize: 11 }} bordered={false} />
                    </Form.Item>
                    <Form.Item
                      {...rest}
                      name={[name, "display_phone_number"]}
                      rules={[{ required: true, message: "必填" }]}
                      style={{ flex: "1 1 160px", marginBottom: 0 }}
                    >
                      <Input placeholder="显示号码" style={{ fontSize: 11 }} bordered={false} />
                    </Form.Item>
                    <Form.Item
                      {...rest}
                      name={[name, "verified_name"]}
                      style={{ flex: "1 1 140px", marginBottom: 0 }}
                    >
                      <Input placeholder="认证名称" style={{ fontSize: 11 }} bordered={false} />
                    </Form.Item>
                    <Form.Item
                      {...rest}
                      name={[name, "quality_rating"]}
                      style={{ width: 90, marginBottom: 0 }}
                    >
                      <Select
                        size="small"
                        style={{ fontSize: 10 }}
                        bordered={false}
                        options={["GREEN", "YELLOW", "RED", "UNKNOWN"].map((value) => ({
                          label: value,
                          value,
                        }))}
                      />
                    </Form.Item>
                    <Form.Item
                      {...rest}
                      name={[name, "is_registered"]}
                      valuePropName="checked"
                      style={{ marginBottom: 0 }}
                    >
                      <Switch size="small" />
                    </Form.Item>
                    {fields.length > 1 ? (
                      <MinusCircleOutlined
                        style={{ color: "#ff4d4f", cursor: "pointer", fontSize: 14, flexShrink: 0 }}
                        onClick={() => remove(name)}
                      />
                    ) : null}
                  </div>
                </div>
              ))}

              <Button
                type="dashed"
                size="small"
                onClick={() => add({ quality_rating: "UNKNOWN", is_registered: false })}
                icon={<PlusOutlined />}
                block
              >
                添加号码
              </Button>
            </>
          )}
        </Form.List>

        {discovery?.warnings && discovery.warnings.length > 0 ? (
          <div style={{ marginTop: 6 }}>
            {discovery.warnings.map((warning, index) => (
              <Typography.Text
                key={index}
                type="warning"
                style={{ fontSize: 10, display: "block" }}
              >
                {warning}
              </Typography.Text>
            ))}
          </div>
        ) : null}
      </Form>
    </Modal>
  );
}

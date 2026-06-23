import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Card, Checkbox, Form, Input, Typography, message } from "antd";
import { useState, type JSX } from "react";

import { adminAuth, type LoginPayload } from "../services/adminAuth";
import { useAppStore, type ActorRole } from "../stores/appStore";

const { Title, Text } = Typography;

const THEME_BG = "#f5f7fa";
const THEME_PRIMARY = "#1f2937";

function navigateTo(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function LoginPage(): JSX.Element {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setConsoleAgentId = useAppStore((state) => state.setConsoleAgentId);
  const setConsoleAgentName = useAppStore((state) => state.setConsoleAgentName);
  const setActorRole = useAppStore((state) => state.setActorRole);
  const setActorAccountIds = useAppStore((state) => state.setActorAccountIds);

  async function handleSubmit(values: LoginPayload): Promise<void> {
    setLoading(true);
    setError(null);

    try {
      const tokens = await adminAuth.login(values);
      const user = await adminAuth.getMe();

      setConsoleAgentId(user.id);
      setConsoleAgentName(user.display_name);

      const roleMap: Record<string, ActorRole> = {
        admin: "super_admin",
        operator: "operator",
        agent: "agent",
        agent_member: "agent_member",
      };

      const role: ActorRole = (tokens.user_type as ActorRole) || roleMap[user.role] || "support_agent";
      setActorRole(role);
      setActorAccountIds(tokens.account_ids || []);

      const params = new URLSearchParams(window.location.search);
      const redirect = params.get("redirect") || "/";

      message.success("登录成功");
      navigateTo(redirect);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败，请重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: THEME_BG,
        padding: 24,
      }}
    >
      <Card
        bodyStyle={{ padding: "40px 32px" }}
        style={{
          width: 420,
          maxWidth: "100%",
          borderRadius: 14,
          boxShadow: "0 4px 24px rgba(15,23,42,0.08)",
          border: "1px solid #e2e8f0",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Title level={3} style={{ color: THEME_PRIMARY, margin: 0 }}>
            WhatsApp 管理后台
          </Title>
          <Text style={{ marginTop: 8, display: "block" }} type="secondary">
            请输入您的账号信息
          </Text>
        </div>

        <Form<LoginPayload>
          autoComplete="off"
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark={false}
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input autoFocus placeholder="用户名" prefix={<UserOutlined style={{ color: "#94a3b8" }} />} />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password placeholder="密码" prefix={<LockOutlined style={{ color: "#94a3b8" }} />} />
          </Form.Item>

          <Form.Item name="remember" valuePropName="checked">
            <Checkbox>记住登录</Checkbox>
          </Form.Item>

          {error ? (
            <div
              style={{
                marginBottom: 16,
                padding: "8px 12px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 8,
                color: "#dc2626",
                fontSize: 14,
              }}
            >
              {error}
            </div>
          ) : null}

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              block
              htmlType="submit"
              loading={loading}
              style={{
                height: 44,
                background: THEME_PRIMARY,
                borderColor: THEME_PRIMARY,
              }}
              type="primary"
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

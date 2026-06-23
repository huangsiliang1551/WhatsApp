import { Button, Card, Descriptions, Form, Input, Tag, Typography } from "antd";
import { useCallback, useEffect, useState, type JSX } from "react";

import { showError, showSuccess } from "../components/Feedback";
import { PageShell } from "../components/PageShell";
import { usePermissions } from "../hooks/usePermissions";
import { adminAuth } from "../services/adminAuth";

const { Text } = Typography;

const ROLE_LABELS: Record<string, string> = {
  admin: "超级管理员",
  operator: "运营",
  agent: "代理商",
  super_admin: "超级管理员",
  support: "客服",
  finance: "财务",
  manager: "经理",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "blue",
  operator: "cyan",
  agent: "green",
  super_admin: "blue",
  support: "green",
  finance: "orange",
  manager: "purple",
};

type ProfileUser = {
  id: string;
  username: string;
  display_name: string;
  role: string;
  email?: string;
  avatar_url?: string;
};

export function ProfilePage(): JSX.Element {
  const { can } = usePermissions();
  const [user, setUser] = useState<ProfileUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [pwForm] = Form.useForm<{ old_password: string; new_password: string }>();
  const [changingPw, setChangingPw] = useState(false);

  useEffect(() => {
    setLoading(true);
    adminAuth
      .getMe()
      .then((currentUser) => {
        setUser(currentUser);
      })
      .catch(() => {
        setUser({
          id: "unknown",
          username: "unknown",
          display_name: "用户",
          role: "agent",
        });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleChangePassword = useCallback(
    async (values: { old_password: string; new_password: string }) => {
      setChangingPw(true);
      try {
        await adminAuth.changePassword(values);
        showSuccess("密码修改成功");
        pwForm.resetFields();
      } catch (err) {
        showError(err instanceof Error ? err.message : "密码修改失败");
      } finally {
        setChangingPw(false);
      }
    },
    [pwForm]
  );

  const userRole = user?.role ?? "agent";
  const roleLabel = ROLE_LABELS[userRole] ?? userRole;
  const roleColor = ROLE_COLORS[userRole] ?? "default";
  const isManager =
    can("users.view") ||
    can("agents.view") ||
    can("sites.view") ||
    can("settings.view") ||
    can("finance.view_channels");

  if (loading) {
    return (
      <PageShell title="个人中心">
        <Typography.Text type="secondary">加载中...</Typography.Text>
      </PageShell>
    );
  }

  return (
    <PageShell subtitle="查看当前账号信息并修改登录密码" title="个人中心">
      <Card size="small" style={{ marginBottom: 16 }} title="基本信息">
        <Descriptions column={2} size="small">
          <Descriptions.Item label="用户名">{user?.username ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="显示名称">{user?.display_name ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="角色">
            <Tag color={roleColor}>{roleLabel}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email || "-"}</Descriptions.Item>
          <Descriptions.Item label="用户类型">
            <Tag color={isManager ? "blue" : "green"}>{isManager ? "管理" : "普通"}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="用户 ID">
            <Text copyable>{user?.id ?? "-"}</Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card size="small" style={{ marginBottom: 16, maxWidth: 420 }} title="修改密码">
        <Form form={pwForm} layout="vertical" onFinish={handleChangePassword}>
          <Form.Item
            label="当前密码"
            name="old_password"
            rules={[{ required: true, message: "请输入当前密码" }]}
          >
            <Input.Password placeholder="当前密码" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: "请输入新密码" },
              { min: 8, message: "密码至少 8 位" },
            ]}
          >
            <Input.Password placeholder="新密码（至少 8 位）" />
          </Form.Item>
          <Form.Item>
            <Button htmlType="submit" loading={changingPw} type="primary">
              修改密码
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </PageShell>
  );
}

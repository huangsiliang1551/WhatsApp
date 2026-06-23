import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Alert, Button, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";

import { DangerButton, showError, showSuccess } from "../Feedback";
import {
  addAgentMember,
  checkAgentUsername,
  listAgentMembers,
  removeAgentMember,
  updateAgentMemberRole,
  type AgentMember,
} from "../../services/api";

type RoleOption = {
  label: string;
  value: string;
};

type AgencyMembersPanelProps = {
  agencyId: string;
  roleOptions: RoleOption[];
  initialMemberId?: string | null;
  onSelectedMemberChange?: (memberId: string | null) => void;
  onRoleCenter?: (roleName: string) => void;
  roleAssignmentDisabled?: boolean;
};

const ROLE_COLORS: Record<string, string> = {
  finance: "blue",
  manager: "orange",
  support: "green",
  agent: "purple",
};

const STATUS_COLORS: Record<string, string> = {
  active: "success",
  online: "success",
  busy: "warning",
  away: "default",
  offline: "default",
  inactive: "default",
};

const STATUS_LABELS: Record<string, string> = {
  active: "启用",
  online: "在线",
  busy: "忙碌",
  away: "离开",
  offline: "离线",
  inactive: "停用",
};

function renderMemberName(member: AgentMember): JSX.Element {
  const displayName = member.display_name?.trim() || member.username?.trim() || "未命名成员";
  const username = member.username?.trim();

  return (
    <Space direction="vertical" size={2}>
      <Typography.Text strong>{displayName}</Typography.Text>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {username ? `登录名 ${username}` : `成员 ID ${member.id}`}
      </Typography.Text>
    </Space>
  );
}

export function AgencyMembersPanel({
  agencyId,
  roleOptions,
  initialMemberId = null,
  onSelectedMemberChange,
  onRoleCenter,
  roleAssignmentDisabled = false,
}: AgencyMembersPanelProps): JSX.Element {
  const [members, setMembers] = useState<AgentMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<AgentMember | null>(null);
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(initialMemberId);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const memberManagementDisabled = roleAssignmentDisabled || roleOptions.length === 0;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setMembers(await listAgentMembers(agencyId));
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "加载代理成员失败");
      setMembers([]);
    } finally {
      setLoading(false);
    }
  }, [agencyId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setSelectedMemberId(initialMemberId);
  }, [initialMemberId]);

  useEffect(() => {
    if (members.length === 0) {
      if (selectedMemberId !== null) {
        setSelectedMemberId(null);
        onSelectedMemberChange?.(null);
      }
      return;
    }

    if (selectedMemberId && members.some((member) => member.id === selectedMemberId)) {
      return;
    }

    if (initialMemberId && members.some((member) => member.id === initialMemberId)) {
      setSelectedMemberId(initialMemberId);
      onSelectedMemberChange?.(initialMemberId);
      return;
    }

    setSelectedMemberId(null);
    onSelectedMemberChange?.(null);
  }, [initialMemberId, members, onSelectedMemberChange, selectedMemberId]);

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setEditingMember(null);
    form.resetFields();
  }, [form]);

  const handleSave = useCallback(
    async (values: { username?: string; password?: string; role: string }) => {
      if (memberManagementDisabled) return;
      setSaving(true);
      try {
        if (editingMember) {
          await updateAgentMemberRole(agencyId, editingMember.id, values.role, values.password || undefined);
          showSuccess("成员已更新");
        } else {
          await addAgentMember(agencyId, values.username || "", values.password || "", values.role);
          showSuccess("成员已添加");
        }
        closeModal();
        await load();
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "成员保存失败");
      } finally {
        setSaving(false);
      }
    },
    [agencyId, closeModal, editingMember, load, memberManagementDisabled],
  );

  const handleRemove = useCallback(
    (member: AgentMember) => {
      const displayName = member.display_name || member.username || member.id;
      Modal.confirm({
        title: "确认移除成员",
        content: `确认移除成员 ${displayName} 吗？`,
        okText: "确认",
        cancelText: "取消",
        onOk: async () => {
          try {
            await removeAgentMember(agencyId, member.id);
            showSuccess("成员已移除");
            await load();
          } catch (cause) {
            showError(cause instanceof Error ? cause.message : "移除成员失败");
          }
        },
      });
    },
    [agencyId, load],
  );

  const columns = useMemo(
    () => [
      {
        title: "成员",
        key: "member",
        render: (_: unknown, member: AgentMember) => renderMemberName(member),
      },
      {
        title: "角色",
        dataIndex: "role",
        key: "role",
        render: (role: string) => <Tag color={ROLE_COLORS[role] ?? "default"}>{role}</Tag>,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (status?: string) => {
          const normalized = status || "inactive";
          return <Tag color={STATUS_COLORS[normalized] ?? "default"}>{STATUS_LABELS[normalized] ?? normalized}</Tag>;
        },
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        render: (value: string) => (value ? new Date(value).toLocaleDateString("zh-CN") : "-"),
      },
      {
        title: "操作",
        key: "actions",
        width: 280,
        render: (_: unknown, member: AgentMember) => (
          <Space wrap>
            <Button
              size="small"
              disabled={memberManagementDisabled}
              onClick={() => {
                if (memberManagementDisabled) return;
                setEditingMember(member);
                form.setFieldsValue({ role: member.role });
                setModalOpen(true);
              }}
            >
              编辑
            </Button>
            <Button size="small" disabled={!onRoleCenter} onClick={() => onRoleCenter?.(member.role)}>
              查看角色
            </Button>
            <DangerButton
              label="移除"
              disabled={memberManagementDisabled}
              type="link"
              danger
              confirmTitle="确认移除该成员？"
              onConfirm={async () => handleRemove(member)}
            />
          </Space>
        ),
      },
    ],
    [form, handleRemove, memberManagementDisabled, onRoleCenter],
  );

  return (
    <>
      {roleAssignmentDisabled ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="请先配置权限池和角色"
          description="当前只允许浏览成员列表；请先完成权限池与角色配置，再继续分配成员角色。"
        />
      ) : roleOptions.length === 0 ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="当前代理还没有可分配角色"
          description="请先到角色页配置角色，再为成员分配角色。"
        />
      ) : null}

      <Table
        rowKey="id"
        dataSource={members}
        columns={columns}
        loading={loading}
        pagination={false}
        rowClassName={(member) => (member.id === selectedMemberId ? "permission-role-selected" : "")}
        onRow={(member) => ({
          onClick: () => {
            setSelectedMemberId(member.id);
            onSelectedMemberChange?.(member.id);
          },
        })}
        title={() => (
          <Space>
            <Typography.Text strong>成员</Typography.Text>
            <Button
              type="primary"
              size="small"
              icon={<PlusOutlined />}
              disabled={memberManagementDisabled}
              onClick={() => {
                if (memberManagementDisabled) return;
                setEditingMember(null);
                form.resetFields();
                form.setFieldsValue({ role: roleOptions[0]?.value });
                setModalOpen(true);
              }}
            >
              新增成员
            </Button>
          </Space>
        )}
      />

      <Modal
        title={editingMember ? "编辑成员" : "新增成员"}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={saving}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleSave(values)}>
          {!editingMember ? (
            <>
              <Form.Item
                label="登录名"
                name="username"
                rules={[
                  { required: true },
                  {
                    pattern: /^[a-zA-Z][a-zA-Z0-9_]{2,49}$/,
                    message: "字母开头，长度 3-50，只能包含字母、数字和下划线。",
                  },
                  {
                    validator: async (_, value) => {
                      if (!value || value.length < 3) return;
                      const exists = await checkAgentUsername(value);
                      if (exists) throw new Error("该登录名已被占用");
                    },
                    validateTrigger: "onBlur",
                  },
                ]}
              >
                <Input placeholder="用于后台登录" />
              </Form.Item>
              <Form.Item label="密码" name="password" rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}>
                <Input.Password placeholder="至少 8 位" />
              </Form.Item>
            </>
          ) : null}

          <Form.Item label="角色" name="role" rules={[{ required: true, message: "请选择角色" }]}>
            <Select options={roleOptions} disabled={memberManagementDisabled} />
          </Form.Item>

          {editingMember ? (
            <Form.Item label="新密码（可选）" name="password">
              <Input.Password placeholder="留空则不修改密码" />
            </Form.Item>
          ) : null}
        </Form>
      </Modal>
    </>
  );
}

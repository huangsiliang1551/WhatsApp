import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, type TableColumnsType } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { showError, showSuccess } from "../components/Feedback";
import { usePageData } from "../hooks/usePageData";
import {
  listAgentPresence,
  listAgentWorkloads,
  listMetaAccounts,
  listRuntimeAgents,
  registerRuntimeAgent,
  setAgentOffline,
  setAgentOnline,
  setRuntimeAgentStatus,
  type AgentPresenceRecord,
  type AgentWorkload,
  type OperatorStatus,
  type RuntimeAgent,
} from "../services/api";

const STATUS_ICONS: Record<string, string> = {
  online: "在线",
  busy: "忙碌",
  away: "离开",
  offline: "离线",
};

const STATUS_COLORS: Record<string, string> = {
  online: "green",
  busy: "orange",
  away: "red",
  offline: "default",
};

type MergedAgent = RuntimeAgent & {
  presenceStatus?: string;
  assigned_open: number;
  assigned_total: number;
  last_heartbeat?: number;
};

function formatHeartbeat(value: number | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function MembersPage(): JSX.Element {
  const [filterAccount, setFilterAccount] = useState<string | undefined>();
  const [accounts, setAccounts] = useState<Array<{ account_id: string; display_name: string }>>([]);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [registerForm] = Form.useForm<{ agent_id: string; display_name: string; email?: string; account_id?: string }>();
  const intervalRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  useEffect(() => {
    listMetaAccounts({})
      .then((items) => setAccounts(items))
      .catch(() => {
        setAccounts([]);
      });
  }, []);

  const fetchAll = useCallback(async () => {
    const [agents, workloads, presence] = await Promise.all([
      listRuntimeAgents(undefined, filterAccount),
      listAgentWorkloads(undefined, filterAccount),
      listAgentPresence(filterAccount),
    ]);
    return { agents, workloads, presence };
  }, [filterAccount]);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchAll });

  useEffect(() => {
    intervalRef.current = setInterval(() => void reload(), 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reload]);

  const mergedAgents: MergedAgent[] = useMemo(() => {
    const agents = data?.agents ?? [];
    const workloads = data?.workloads ?? [];
    const presence = data?.presence ?? [];

    return agents.map((agent) => {
      const workload = workloads.find((item) => item.agent_id === agent.agent_id);
      const presenceItem = presence.find((item) => item.agent_id === agent.agent_id);
      return {
        ...agent,
        presenceStatus: presenceItem?.status,
        last_heartbeat: presenceItem?.last_heartbeat,
        assigned_open: workload?.assigned_open_conversations ?? 0,
        assigned_total: workload?.assigned_total_conversations ?? 0,
      };
    });
  }, [data]);

  const getEffectiveStatus = useCallback((agent: MergedAgent): string => agent.presenceStatus ?? agent.status, []);

  const onlineCount = mergedAgents.filter((agent) => getEffectiveStatus(agent) === "online").length;
  const busyCount = mergedAgents.filter((agent) => getEffectiveStatus(agent) === "busy").length;
  const awayCount = mergedAgents.filter((agent) => getEffectiveStatus(agent) === "away").length;
  const offlineCount = mergedAgents.filter((agent) => getEffectiveStatus(agent) === "offline").length;

  const handleStatusChange = useCallback(
    async (agent: MergedAgent, newStatus: OperatorStatus) => {
      try {
        await setRuntimeAgentStatus(agent.agent_id, { status: newStatus }, agent.account_id ?? undefined);
        showSuccess(`${agent.display_name} 状态已更新`);
        await reload();
      } catch {
        showError("状态更新失败");
      }
    },
    [reload]
  );

  const handleGoOnline = useCallback(
    async (agent: MergedAgent) => {
      try {
        await setAgentOnline(agent.agent_id, agent.account_id ?? undefined);
        showSuccess(`${agent.display_name} 已上线`);
        await reload();
      } catch {
        showError("上线失败");
      }
    },
    [reload]
  );

  const handleGoOffline = useCallback(
    async (agent: MergedAgent) => {
      try {
        await setAgentOffline(agent.agent_id, agent.account_id ?? undefined);
        showSuccess(`${agent.display_name} 已下线`);
        await reload();
      } catch {
        showError("下线失败");
      }
    },
    [reload]
  );

  const handleRegister = useCallback(
    async (values: { agent_id: string; display_name: string; email?: string; account_id?: string }) => {
      setRegistering(true);
      try {
        await registerRuntimeAgent({
          agent_id: values.agent_id,
          display_name: values.display_name,
          email: values.email ?? null,
          account_id: values.account_id ?? null,
          status: "offline",
          is_active: true,
        });
        showSuccess("坐席已注册");
        setRegisterModalOpen(false);
        registerForm.resetFields();
        await reload();
      } catch {
        showError("注册失败");
      } finally {
        setRegistering(false);
      }
    },
    [registerForm, reload]
  );

  const renderActions = useCallback(
    (agent: MergedAgent): JSX.Element => {
      const effectiveStatus = getEffectiveStatus(agent);

      if (effectiveStatus === "offline") {
        return (
          <Space size={4}>
            <Button onClick={() => void handleGoOnline(agent)} size="small" type="link">
              上线
            </Button>
          </Space>
        );
      }

      return (
        <Space size={4}>
          {effectiveStatus === "online" ? (
            <Popconfirm cancelText="取消" okText="确认" onConfirm={() => void handleStatusChange(agent, "busy")} title={`将 ${agent.display_name} 设为忙碌？`}>
              <Button size="small" type="link">
                忙碌
              </Button>
            </Popconfirm>
          ) : (
            <Popconfirm cancelText="取消" okText="确认" onConfirm={() => void handleStatusChange(agent, "online")} title={`将 ${agent.display_name} 设为在线？`}>
              <Button size="small" type="link">
                在线
              </Button>
            </Popconfirm>
          )}
          <Popconfirm cancelText="取消" okText="确认" onConfirm={() => void handleGoOffline(agent)} title={`将 ${agent.display_name} 下线？`}>
            <Button danger size="small" type="link">
              下线
            </Button>
          </Popconfirm>
        </Space>
      );
    },
    [getEffectiveStatus, handleGoOffline, handleGoOnline, handleStatusChange]
  );

  const columns: TableColumnsType<MergedAgent> = [
    {
      title: "坐席",
      dataIndex: "display_name",
      key: "display_name",
      width: 140,
      ellipsis: true,
      sorter: (left, right) => (left.display_name ?? "").localeCompare(right.display_name ?? ""),
    },
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
      width: 180,
      ellipsis: true,
      render: (value: string | null) => value || "-",
      sorter: (left, right) => (left.email ?? "").localeCompare(right.email ?? ""),
    },
    {
      title: "账号",
      dataIndex: "account_id",
      key: "account_id",
      width: 120,
      ellipsis: true,
      render: (value: string | null) => value || "-",
      sorter: (left, right) => (left.account_id ?? "").localeCompare(right.account_id ?? ""),
    },
    {
      title: "状态",
      key: "status",
      width: 120,
      sorter: (left, right) => getEffectiveStatus(left).localeCompare(getEffectiveStatus(right)),
      render: (_: unknown, record: MergedAgent) => {
        const status = getEffectiveStatus(record);
        return <Tag color={STATUS_COLORS[status] ?? "default"}>{STATUS_ICONS[status] ?? status}</Tag>;
      },
    },
    {
      title: "当前会话",
      dataIndex: "assigned_open",
      key: "assigned_open",
      width: 100,
      sorter: (left, right) => left.assigned_open - right.assigned_open,
    },
    {
      title: "总处理",
      dataIndex: "assigned_total",
      key: "assigned_total",
      width: 100,
      sorter: (left, right) => left.assigned_total - right.assigned_total,
    },
    {
      title: "最后心跳",
      dataIndex: "last_heartbeat",
      key: "last_heartbeat",
      width: 170,
      render: (value: number | undefined) => formatHeartbeat(value),
      sorter: (left, right) => (left.last_heartbeat ?? 0) - (right.last_heartbeat ?? 0),
    },
    {
      title: "操作",
      key: "actions",
      width: 170,
      fixed: "right",
      render: (_: unknown, record: MergedAgent) => renderActions(record),
    },
  ];

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }} wrap>
      <span>
        在线 <Typography.Text strong style={{ color: "#52c41a" }}>{onlineCount}</Typography.Text>
      </span>
      <span>
        忙碌 <Typography.Text strong style={{ color: "#faad14" }}>{busyCount}</Typography.Text>
      </span>
      <span>
        离开 <Typography.Text strong style={{ color: "#ff4d4f" }}>{awayCount}</Typography.Text>
      </span>
      <span>
        离线 <Typography.Text strong>{offlineCount}</Typography.Text>
      </span>
      <span>
        总计 <Typography.Text strong>{mergedAgents.length}</Typography.Text>
      </span>
    </Space>
  );

  const actions = (
    <Space>
      <Select
        allowClear
        onChange={(value) => setFilterAccount(value)}
        options={accounts.map((account) => ({ label: account.display_name, value: account.account_id }))}
        placeholder="全部账号"
        style={{ width: 180 }}
        value={filterAccount}
      />
      <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void reload()} size="small">
        刷新
      </Button>
      <Button icon={<PlusOutlined />} onClick={() => setRegisterModalOpen(true)} size="small" type="primary">
        注册坐席
      </Button>
    </Space>
  );

  if (mergedAgents.length === 0 && !loading) {
    return (
      <PageShell actions={actions} stats={stats} subtitle="管理坐席、查看在线状态和工作负载" title="客服团队">
        <EmptyGuide description="当前还没有已注册坐席，点击“注册坐席”开始添加。" icon="👥" title="暂无坐席" />
      </PageShell>
    );
  }

  return (
    <PageShell actions={actions} stats={stats} subtitle="管理坐席、查看在线状态和工作负载" title="客服团队">
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 8 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Table
        columns={columns}
        dataSource={mergedAgents}
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
        rowKey="agent_id"
        scroll={{ x: 1100, y: "calc(100vh - 380px)" }}
        size="small"
      />

      <Modal
        cancelText="取消"
        confirmLoading={registering}
        okText="注册"
        onCancel={() => {
          setRegisterModalOpen(false);
          registerForm.resetFields();
        }}
        onOk={() => void registerForm.submit()}
        open={registerModalOpen}
        title="注册坐席"
      >
        <Form form={registerForm} layout="vertical" onFinish={handleRegister}>
          <Form.Item label="坐席 ID" name="agent_id" rules={[{ required: true, message: "请输入坐席 ID" }]}>
            <Input placeholder="例如：agent-new" />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: "请输入显示名称" }]}>
            <Input placeholder="例如：新坐席" />
          </Form.Item>
          <Form.Item label="邮箱" name="email">
            <Input placeholder="new@company.com" />
          </Form.Item>
          <Form.Item label="账号" name="account_id">
            <Select
              allowClear
              options={accounts.map((account) => ({ label: account.display_name, value: account.account_id }))}
              placeholder="选择账号"
            />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}

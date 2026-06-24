// AIAgentsPanel：AI Agent 主体管理（spec 10.2）。
//
// 展示：列表、health_status、owning staff、fallback staff/AI、默认 EntryLink、
// 当前绑定会员数（estimate）、自动回复开关、proactive_send_enabled。
// 提供：disable / archive / health-check 操作。

import { useCallback, useEffect, useState, type JSX } from "react";
import {
  Button,
  Card,
  Empty,
  Popconfirm,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";

import {
  listAIAgents,
  disableAIAgent,
  archiveAIAgent,
  healthCheckAIAgent,
} from "../services/aiAgents";
import type { AIAgent } from "../types/aiAgents";

interface AIAgentsPanelProps {
  accountId?: string;
  siteId?: string;
  canDisable: boolean;
  canManage: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  active: "green",
  disabled: "orange",
  suspended: "orange",
  archived: "default",
  deleted: "red",
};

const HEALTH_COLORS: Record<string, string> = {
  healthy: "green",
  degraded: "orange",
  unavailable: "red",
  disabled: "default",
  suspended: "default",
};

export function AIAgentsPanel({
  accountId,
  siteId,
  canDisable,
  canManage,
}: AIAgentsPanelProps): JSX.Element {
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAIAgents({ site_id: siteId });
      setAgents(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [siteId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const columns: ColumnsType<AIAgent> = [
    { title: "名称", dataIndex: "display_name", key: "display_name", width: 160 },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (v: string) => <Tag color={STATUS_COLORS[v] ?? "default"}>{v}</Tag>,
    },
    {
      title: "健康",
      dataIndex: "health_status",
      key: "health_status",
      width: 100,
      render: (v: string) => <Tag color={HEALTH_COLORS[v] ?? "default"}>{v}</Tag>,
    },
    { title: "Provider", dataIndex: "provider_name", key: "provider_name", width: 100 },
    { title: "Model", dataIndex: "model_name", key: "model_name", width: 140 },
    { title: "Owning staff", dataIndex: "owning_staff_user_id", key: "owning_staff_user_id", width: 130 },
    { title: "Fallback staff", dataIndex: "fallback_staff_user_id", key: "fallback_staff_user_id", width: 130 },
    { title: "Fallback AI", dataIndex: "fallback_ai_agent_id", key: "fallback_ai_agent_id", width: 130 },
    {
      title: "自动回复",
      dataIndex: "auto_reply_enabled",
      key: "auto_reply_enabled",
      width: 100,
      render: (v: boolean) => (v ? <Tag color="green">开启</Tag> : <Tag>关闭</Tag>),
    },
    {
      title: "主动发送",
      dataIndex: "proactive_send_enabled",
      key: "proactive_send_enabled",
      width: 100,
      render: (v: boolean) => (v ? <Tag color="blue">开启</Tag> : <Tag>关闭</Tag>),
    },
    {
      title: "操作",
      key: "actions",
      width: 320,
      render: (_, record) => (
        <Space size={4} wrap>
          {canManage ? (
            <Button
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={async () => {
                try {
                  await healthCheckAIAgent(record.id);
                  message.success("健康检查已触发");
                  await refresh();
                } catch (err) {
                  message.error(`失败：${(err as Error).message}`);
                }
              }}
            >
              health-check
            </Button>
          ) : null}
          {canDisable && record.status === "active" ? (
            <Popconfirm
              title="确认停用？"
              okText="停用"
              cancelText="取消"
              onConfirm={async () => {
                try {
                  await disableAIAgent(record.id);
                  message.success("已停用");
                  await refresh();
                } catch (err) {
                  message.error(`失败：${(err as Error).message}`);
                }
              }}
            >
              <Button size="small" danger>
                disable
              </Button>
            </Popconfirm>
          ) : null}
          {canDisable && record.status !== "archived" ? (
            <Popconfirm
              title="确认归档？归档后不能再启用"
              okText="归档"
              cancelText="取消"
              onConfirm={async () => {
                try {
                  await archiveAIAgent(record.id);
                  message.success("已归档");
                  await refresh();
                } catch (err) {
                  message.error(`失败：${(err as Error).message}`);
                }
              }}
            >
              <Button size="small">archive</Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <Card
      size="small"
      title="AI 主体（AI Agent）"
      extra={
        <Space>
          <span style={{ fontSize: 12, color: "#999" }}>account: {accountId ?? "—"}</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => void refresh()}>
            刷新
          </Button>
        </Space>
      }
    >
      {error ? (
        <Empty description={`加载失败：${error}`} />
      ) : (
        <Table<AIAgent>
          rowKey="id"
          loading={loading}
          dataSource={agents}
          columns={columns}
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: true }}
          scroll={{ x: 1200 }}
        />
      )}
    </Card>
  );
}

export default AIAgentsPanel;

import { Button, Card, Col, Row, Space, Tag, Typography, message } from "antd";
import { useCallback, type JSX } from "react";

import { PageShell, EmptyGuide } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { api, listConversations, listRuntimeAgents, type ConversationSummary } from "../services/api";
import { useAppStore } from "../stores/appStore";

const MODE_LABELS: Record<string, string> = {
  recommended: "待处理",
  human_managed: "人工接管",
  ai_managed: "AI 托管",
  paused: "暂停",
  closed: "已关闭",
};

const MODE_COLORS: Record<string, string> = {
  recommended: "#ff4d4f",
  human_managed: "#faad14",
  ai_managed: "#52c41a",
  paused: "#d9d9d9",
  closed: "#bfbfbf",
};

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "-";

  const date = new Date(value);
  const diff = Date.now() - date.getTime();

  if (diff < 60_000) return "刚刚";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

type QueueSectionProps = {
  conversations: ConversationSummary[];
  onClaim: (conversation: ConversationSummary) => Promise<void>;
  onOpen: (conversation: ConversationSummary) => void;
  title: string;
  tone: "priority" | "normal";
};

function QueueSection({ conversations, onClaim, onOpen, title, tone }: QueueSectionProps): JSX.Element | null {
  if (!conversations.length) return null;

  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Title level={5} style={{ margin: "0 0 8px" }}>
        {title}
      </Typography.Title>
      <Row gutter={[12, 12]}>
        {conversations.map((conversation) => {
          const key = `${conversation.account_id}:${conversation.conversation_id}`;
          const borderColor =
            tone === "priority"
              ? "#ff4d4f"
              : MODE_COLORS[conversation.management_mode] ?? "#d9d9d9";

          return (
            <Col key={key} lg={8} sm={12} xs={24}>
              <Card size="small" style={{ borderLeft: `3px solid ${borderColor}` }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ minWidth: 0 }}>
                    <Typography.Text strong>{conversation.customer_id.slice(0, 18)}</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      <Tag color={MODE_COLORS[conversation.management_mode] ?? "default"} style={{ fontSize: 10 }}>
                        {MODE_LABELS[conversation.management_mode] ?? conversation.management_mode}
                      </Tag>
                      {conversation.customer_language ? (
                        <Typography.Text style={{ color: "#999", fontSize: 11, marginLeft: 4 }}>
                          {conversation.customer_language}
                        </Typography.Text>
                      ) : null}
                    </div>
                    <Typography.Paragraph ellipsis={{ rows: 2 }} style={{ color: "#666", fontSize: 12, margin: "6px 0 0" }}>
                      {conversation.last_message_preview || "暂无消息"}
                    </Typography.Paragraph>
                    <Typography.Text style={{ color: "#999", fontSize: 11 }}>
                      {formatRelativeTime(conversation.last_message_at)}
                    </Typography.Text>
                    {conversation.latest_handover_reason ? (
                      <Typography.Paragraph style={{ color: "#8c8c8c", fontSize: 11, margin: "6px 0 0" }}>
                        {conversation.latest_handover_reason}
                      </Typography.Paragraph>
                    ) : null}
                  </div>
                </div>

                <Space size={6} style={{ marginTop: 10 }} wrap>
                  <Button onClick={() => onOpen(conversation)} size="small" type="primary">
                    处理
                  </Button>
                  {conversation.management_mode !== "human_managed" ? (
                    <Button onClick={() => void onClaim(conversation)} size="small">
                      认领
                    </Button>
                  ) : null}
                </Space>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}

export function AssignmentsPage(): JSX.Element {
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);

  const fetchData = useCallback(async () => {
    const [conversations, agents] = await Promise.all([listConversations(), listRuntimeAgents()]);
    return { conversations, agents };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });
  const conversations = data?.conversations ?? [];
  const agents = data?.agents ?? [];

  const handleClaim = useCallback(
    async (conversation: ConversationSummary) => {
      try {
        await api.post(
          `/api/conversations/${conversation.account_id}/${conversation.conversation_id}/handover`,
          { management_mode: "human_managed" }
        );
        message.success("认领成功");
        await reload();
      } catch {
        message.error("认领失败");
      }
    },
    [reload]
  );

  const handleBatchClaim = useCallback(async () => {
    const pending = conversations.filter((item) => item.latest_handover_recommended);
    for (const conversation of pending) {
      try {
        await api.post(
          `/api/conversations/${conversation.account_id}/${conversation.conversation_id}/handover`,
          { management_mode: "human_managed" }
        );
      } catch {
        // Ignore individual failures and continue claiming the rest.
      }
    }

    message.success(`已批量认领 ${pending.length} 个会话`);
    await reload();
  }, [conversations, reload]);

  const openConversation = useCallback(
    (conversation: ConversationSummary) => {
      openWorkspacePage({
        accountId: conversation.account_id,
        conversationKey: `${conversation.account_id}:${conversation.conversation_id}`,
      });
    },
    [openWorkspacePage]
  );

  const pendingCount = conversations.filter((item) => item.latest_handover_recommended).length;
  const humanCount = conversations.filter((item) => item.management_mode === "human_managed").length;
  const aiCount = conversations.filter((item) => item.management_mode === "ai_managed").length;
  const pausedCount = conversations.filter((item) => item.management_mode === "paused").length;
  const onlineAgentCount = agents.filter((item) => item.status === "online").length;

  const topPriority = conversations.filter(
    (item) => item.latest_handover_recommended && item.management_mode !== "human_managed"
  );
  const otherOpen = conversations.filter(
    (item) => !item.latest_handover_recommended || item.management_mode === "human_managed"
  );

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }} wrap>
      <span>
        待处理 <Typography.Text strong style={{ color: "#ff4d4f" }}>{pendingCount}</Typography.Text>
      </span>
      <span>
        人工接管 <Typography.Text strong style={{ color: "#faad14" }}>{humanCount}</Typography.Text>
      </span>
      <span>
        AI 托管 <Typography.Text strong style={{ color: "#52c41a" }}>{aiCount}</Typography.Text>
      </span>
      <span>
        暂停 <Typography.Text strong>{pausedCount}</Typography.Text>
      </span>
      <span>
        在线坐席 <Typography.Text strong>{onlineAgentCount}</Typography.Text>
      </span>
    </Space>
  );

  const actions = (
    <Space wrap>
      {pendingCount > 0 ? (
        <Button onClick={() => void handleBatchClaim()} type="primary">
          批量认领 ({pendingCount})
        </Button>
      ) : null}
      <Button loading={loading} onClick={() => void reload()}>
        刷新
      </Button>
    </Space>
  );

  if (!conversations.length && !loading) {
    return (
      <PageShell actions={actions} stats={stats} subtitle="待处理会话与人工接管队列" title="我的队列">
        <EmptyGuide description="当前没有需要人工处理的会话。" icon="📭" title="暂无待处理会话" />
      </PageShell>
    );
  }

  return (
    <PageShell actions={actions} stats={stats} subtitle="待处理会话与人工接管队列" title="我的队列">
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <div style={{ overflowY: "auto", height: "100%" }}>
        <QueueSection
          conversations={topPriority}
          onClaim={handleClaim}
          onOpen={openConversation}
          title="优先处理"
          tone="priority"
        />
        <QueueSection
          conversations={otherOpen}
          onClaim={handleClaim}
          onOpen={openConversation}
          title="其他会话"
          tone="normal"
        />

        {loading ? (
          <div style={{ color: "#999", padding: 24, textAlign: "center" }}>
            加载中...
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}

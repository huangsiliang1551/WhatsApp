import { Button, Card, Col, Input, Row, Space, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useMemo, useState, type JSX } from "react";

import { MemberIdLink } from "../components/member/MemberIdLink";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { useMemberStatus } from "../hooks/useMemberStatus";
import { usePageData } from "../hooks/usePageData";
import {
  api,
  listConversations,
  listRuntimeAgents,
  type ConversationSummary,
} from "../services/api";
import { resolveCustomerProfileSummaryByConversation } from "../services/operations";
import { useAppStore } from "../stores/appStore";

type HandoverRecommendationFilter = "all" | "recommended" | "normal";

const MODE_LABELS: Record<string, string> = {
  recommended: "建议转人工",
  human_managed: "人工接管",
  ai_managed: "AI 托管",
  paused: "暂停",
  closed: "已关闭",
};

const MODE_COLORS: Record<string, string> = {
  recommended: "volcano",
  human_managed: "gold",
  ai_managed: "green",
  paused: "default",
  closed: "default",
};

const HANDOVER_FILTER_OPTIONS: Array<{
  value: HandoverRecommendationFilter;
  label: string;
}> = [
  { value: "all", label: "全部接管建议" },
  { value: "recommended", label: "仅推荐转人工" },
  { value: "normal", label: "仅普通会话" },
];

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "-";

  const date = new Date(value);
  const diff = Date.now() - date.getTime();

  if (diff < 60_000) return "刚刚";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function getConversationPublicUserId(conversation: ConversationSummary): string {
  return (
    (
      conversation as ConversationSummary & {
        customer_public_user_id?: string | null;
      }
    ).customer_public_user_id ?? conversation.customer_id
  );
}

function getConversationModeLabel(conversation: ConversationSummary): string {
  if (conversation.latest_handover_recommended && conversation.management_mode !== "human_managed") {
    return MODE_LABELS.recommended;
  }
  return MODE_LABELS[conversation.management_mode] ?? conversation.management_mode;
}

function matchesSearch(conversation: ConversationSummary, search: string): boolean {
  const normalized = search.trim().toLowerCase();
  if (!normalized) return true;
  return [
    conversation.customer_id,
    getConversationPublicUserId(conversation),
    conversation.assigned_agent_name ?? "",
    conversation.last_message_preview ?? "",
    conversation.customer_language ?? "",
  ].some((value) => value.toLowerCase().includes(normalized));
}

export function AssignmentsPage(): JSX.Element {
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);
  const {
    memberStatus,
    memberStatusLoading,
    memberStatusError,
    latestVerification,
    latestBinding,
    loadMemberStatus,
    resetMemberStatus,
  } = useMemberStatus();

  const [handoverMode, setHandoverMode] = useState<HandoverRecommendationFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedConversationKey, setSelectedConversationKey] = useState<string>("");

  const fetchData = useCallback(async () => {
    const [conversations, agents] = await Promise.all([listConversations(), listRuntimeAgents()]);
    return { conversations, agents };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });
  const conversations = data?.conversations ?? [];
  const agents = data?.agents ?? [];

  const filteredConversations = useMemo(() => {
    return conversations.filter((conversation) => {
      const queueContext = {
        latest_handover_recommended: conversation.latest_handover_recommended,
      };
      if (!matchesSearch(conversation, search)) {
        return false;
      }
      if (handoverMode === "recommended") {
        return queueContext.latest_handover_recommended;
      }
      if (handoverMode === "normal") {
        return !queueContext.latest_handover_recommended;
      }
      return true;
    });
  }, [conversations, handoverMode, search]);

  useEffect(() => {
    if (!filteredConversations.length) {
      setSelectedConversationKey("");
      return;
    }
    if (!filteredConversations.some((item) => `${item.account_id}:${item.conversation_id}` === selectedConversationKey)) {
      setSelectedConversationKey(
        `${filteredConversations[0].account_id}:${filteredConversations[0].conversation_id}`
      );
    }
  }, [filteredConversations, selectedConversationKey]);

  const selectedConversation = useMemo(
    () =>
      filteredConversations.find(
        (item) => `${item.account_id}:${item.conversation_id}` === selectedConversationKey
      ) ?? null,
    [filteredConversations, selectedConversationKey]
  );

  useEffect(() => {
    if (!selectedConversation?.account_id || !selectedConversation.customer_id) {
      resetMemberStatus();
      return;
    }
    if (typeof useAppStore.getState !== "function") {
      resetMemberStatus();
      return;
    }
    let active = true;
    void resolveCustomerProfileSummaryByConversation({
      account_id: selectedConversation.account_id,
      customer_id: selectedConversation.customer_id,
    }).then((profile) => {
      if (!active) return;
      if (!profile) {
        resetMemberStatus();
        return;
      }
      void loadMemberStatus({
        id: profile.id,
        account_id: profile.account_id,
        public_user_id: profile.public_user_id,
      });
    });
    return () => {
      active = false;
    };
  }, [
    loadMemberStatus,
    resetMemberStatus,
    selectedConversation?.account_id,
    selectedConversation?.customer_id,
  ]);

  const handleClaim = useCallback(
    async (conversation: ConversationSummary) => {
      try {
        await api.post(
          `/api/conversations/${conversation.account_id}/${conversation.conversation_id}/handover`,
          { management_mode: "human_managed" }
        );
        message.success("已切换为人工接管");
        await reload();
      } catch (claimError) {
        message.error(claimError instanceof Error ? claimError.message : "接管失败");
      }
    },
    [reload]
  );

  const handleOpenWorkspace = useCallback(
    (conversation: ConversationSummary) => {
      openWorkspacePage({
        accountId: conversation.account_id,
        conversationKey: `${conversation.account_id}:${conversation.conversation_id}`,
        handoverMode: handoverMode,
        search: search,
      });
    },
    [handoverMode, openWorkspacePage, search]
  );

  const pendingCount = conversations.filter((item) => item.latest_handover_recommended).length;
  const humanCount = conversations.filter((item) => item.management_mode === "human_managed").length;
  const aiCount = conversations.filter((item) => item.management_mode === "ai_managed").length;
  const onlineAgentCount = agents.filter((item) => item.status === "online").length;

  const stats = (
    <Space size="middle" wrap>
      <Typography.Text>建议转人工 {pendingCount}</Typography.Text>
      <Typography.Text>人工接管 {humanCount}</Typography.Text>
      <Typography.Text>AI 托管 {aiCount}</Typography.Text>
      <Typography.Text>在线坐席 {onlineAgentCount}</Typography.Text>
    </Space>
  );

  const actions = (
    <Space wrap>
      {HANDOVER_FILTER_OPTIONS.map((option) => (
        <Button
          key={option.value}
          onClick={() => setHandoverMode(option.value)}
          type={handoverMode === option.value ? "primary" : "default"}
        >
          {option.label}
        </Button>
      ))}
      <Input.Search
        allowClear
        onChange={(event) => setSearch(event.target.value)}
        placeholder="搜索会话 / 会员 / 语言"
        style={{ width: 240 }}
        value={search}
      />
      <Button loading={loading} onClick={() => void reload()}>
        刷新
      </Button>
    </Space>
  );

  if (!filteredConversations.length && !loading) {
    return (
      <PageShell
        actions={actions}
        stats={stats}
        subtitle="按接管建议聚焦需要人工处理的会话"
        title="我的接管队列"
      >
        <EmptyGuide
          description="当前筛选条件下没有待处理会话。"
          icon="📭"
          title="暂无会话"
        />
      </PageShell>
    );
  }

  return (
    <PageShell
      actions={actions}
      stats={stats}
      subtitle="按接管建议聚焦需要人工处理的会话"
      title="我的接管队列"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[16, 16]} style={{ height: "100%" }}>
        <Col lg={15} xs={24}>
          <div style={{ display: "grid", gap: 12 }}>
            {filteredConversations.map((conversation) => {
              const key = `${conversation.account_id}:${conversation.conversation_id}`;
              const selected = key === selectedConversationKey;
              return (
                <Card
                  key={key}
                  onClick={() => setSelectedConversationKey(key)}
                  size="small"
                  style={{
                    borderColor: selected ? "#1677ff" : undefined,
                    cursor: "pointer",
                  }}
                >
                  <Space align="start" direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space align="start" style={{ justifyContent: "space-between", width: "100%" }}>
                      <div style={{ minWidth: 0 }}>
                        <Typography.Text strong>
                          <MemberIdLink
                            accountId={conversation.account_id}
                            label={getConversationPublicUserId(conversation)}
                            publicUserId={getConversationPublicUserId(conversation)}
                            userId={conversation.customer_id}
                          />
                        </Typography.Text>
                        <div style={{ marginTop: 4 }}>
                          <Tag color={MODE_COLORS[conversation.management_mode] ?? "default"}>
                            {getConversationModeLabel(conversation)}
                          </Tag>
                          {conversation.customer_language ? (
                            <Typography.Text type="secondary">
                              {conversation.customer_language}
                            </Typography.Text>
                          ) : null}
                        </div>
                      </div>
                      <Typography.Text type="secondary">
                        {formatRelativeTime(conversation.last_message_at)}
                      </Typography.Text>
                    </Space>

                    <Typography.Paragraph style={{ margin: 0 }}>
                      {conversation.last_message_preview || "暂无消息"}
                    </Typography.Paragraph>

                    {conversation.latest_handover_reason ? (
                      <Typography.Text type="secondary">
                        {conversation.latest_handover_reason}
                      </Typography.Text>
                    ) : null}

                    <Space wrap>
                      <Button onClick={() => void handleOpenWorkspace(conversation)} type="primary">
                        进入工作台
                      </Button>
                      {conversation.management_mode !== "human_managed" ? (
                        <Button onClick={() => void handleClaim(conversation)}>
                          接管
                        </Button>
                      ) : null}
                    </Space>
                  </Space>
                </Card>
              );
            })}
          </div>
        </Col>

        <Col lg={9} xs={24}>
          <Card size="small" title="会话上下文">
            {selectedConversation ? (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <div>
                  <Typography.Text type="secondary">会话成员</Typography.Text>
                  <div>
                    <Typography.Text>{getConversationPublicUserId(selectedConversation)}</Typography.Text>
                  </div>
                </div>

                <div>
                  <Typography.Text type="secondary">会话标签</Typography.Text>
                  <div>
                    <Tag color={MODE_COLORS[selectedConversation.management_mode] ?? "default"}>
                      {getConversationModeLabel(selectedConversation)}
                    </Tag>
                    <Tag>{selectedConversation.customer_language || "未识别语言"}</Tag>
                  </div>
                </div>

                <div>
                  <Typography.Text type="secondary">会员认证状态</Typography.Text>
                  <div>
                    {memberStatusLoading
                      ? "加载中..."
                      : latestVerification?.status ?? memberStatusError ?? "暂无认证记录"}
                  </div>
                </div>

                <div>
                  <Typography.Text type="secondary">WhatsApp 绑定状态</Typography.Text>
                  <div>
                    {memberStatusLoading
                      ? "加载中..."
                      : latestBinding?.status ?? memberStatusError ?? "暂无绑定记录"}
                  </div>
                </div>

                <div>
                  <Typography.Text type="secondary">工作台快捷入口</Typography.Text>
                  <div style={{ marginTop: 8 }}>
                    <Button onClick={() => void handleOpenWorkspace(selectedConversation)} type="link">
                      打开当前会话
                    </Button>
                  </div>
                </div>

                {memberStatus ? (
                  <Typography.Text type="secondary">
                    认证记录 {memberStatus.verificationRequests.length} 条，绑定记录{" "}
                    {memberStatus.bindingRequests.length} 条
                  </Typography.Text>
                ) : null}
              </Space>
            ) : (
              <EmptyGuide description="从左侧选择一个会话后，这里会展示会员与接管上下文。" title="未选择会话" />
            )}
          </Card>
        </Col>
      </Row>
    </PageShell>
  );
}

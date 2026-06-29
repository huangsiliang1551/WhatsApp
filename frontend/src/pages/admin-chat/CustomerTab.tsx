import { type JSX, useEffect, useMemo, useState } from "react";
import { Alert, Button, Collapse, Descriptions, Tag, Typography, Spin } from "antd";
import type { ConversationSummary, ConversationMessage } from "../../services/api";
import { listMessages } from "../../services/api";
import { MemberIdLink } from "../../components/member/MemberIdLink";
import { useMemberStatus } from "../../hooks/useMemberStatus";
import type { CustomerProfileSummary } from "../../types/operations";

export interface CustomerTabProps {
  conversation: ConversationSummary | null;
  customerProfile: CustomerProfileSummary | null;
  onOpenCustomerPage: () => void;
}

function fmt(v: string | null | undefined): string {
  return v ? new Date(v).toLocaleString("zh-CN") : "-";
}

function getVerificationColor(s: string): string {
  if (s === "approved") return "success";
  if (s === "rejected") return "error";
  if (s === "submitted" || s === "under_review") return "processing";
  return "default";
}

function getBindingColor(s: string): string {
  if (s === "bound" || s === "approved") return "success";
  if (s === "failed" || s === "rejected") return "error";
  if (s === "submitted" || s === "pending" || s === "verifying") return "processing";
  return "default";
}

export function CustomerTab({
  conversation,
  customerProfile,
  onOpenCustomerPage,
}: CustomerTabProps): JSX.Element {
  const {
    memberStatus,
    memberStatusLoading,
    memberStatusError,
    latestVerification,
    latestBinding,
  } = useMemberStatus();

  const [recentMessages, setRecentMessages] = useState<ConversationMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);

  useEffect(() => {
    if (!conversation) return;
    setMsgLoading(true);
    listMessages(conversation.account_id, conversation.conversation_id, false)
      .then((msgs) => setRecentMessages(msgs.slice(-10)))
      .catch(() => { /* ignore */ })
      .finally(() => setMsgLoading(false));
  }, [conversation?.account_id, conversation?.conversation_id]);

  if (!conversation) {
    return <Typography.Text type="secondary">未选择会话</Typography.Text>;
  }

  const collapseItems = [
    {
      key: "profile",
      label: <span>👤 客户信息</span>,
      children: customerProfile ? (
        <div>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="名称">{customerProfile.display_name ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="用户 ID">
              <MemberIdLink
                accountId={conversation.account_id}
                userId={customerProfile.id}
                publicUserId={customerProfile.public_user_id}
                label={customerProfile.public_user_id}
              />
            </Descriptions.Item>
            <Descriptions.Item label="语言">{customerProfile.language_code}</Descriptions.Item>
            <Descriptions.Item label="注册时间">{fmt(customerProfile.last_active_at)}</Descriptions.Item>
            <Descriptions.Item label="注册IP">{customerProfile.registration_ip ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={customerProfile.lifecycle_status === "active" ? "success" : "default"}>
                {customerProfile.lifecycle_status}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
          <Button size="small" style={{ marginTop: 6 }} onClick={onOpenCustomerPage}>
            查看用户资料
          </Button>
        </div>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>未加载客户资料</Typography.Text>
      ),
    },
    {
      key: "conversations",
      label: <span>💬 会话记录（最近 10 条）</span>,
      children: msgLoading ? (
        <Spin size="small" />
      ) : recentMessages.length > 0 ? (
        <div style={{ maxHeight: 200, overflowY: "auto" }}>
          {recentMessages.map((msg, i) => (
            <div key={msg.message_id || i} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid #f0f0f0" }}>
              <Tag color={msg.direction === "inbound" ? "processing" : "success"} style={{ fontSize: 9, margin: 0 }}>
                {msg.direction === "inbound" ? "入站" : "出站"}
              </Tag>
              <Typography.Text style={{ fontSize: 11, marginLeft: 4 }}>
                {new Date(msg.created_at).toLocaleString("zh-CN")}
              </Typography.Text>
              <div style={{ fontSize: 11, color: "#666", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {msg.console_text || msg.original_text || "-"}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>暂无会话记录</Typography.Text>
      ),
    },
    {
      key: "tickets",
      label: <span>🎫 工单记录</span>,
      children: (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          后端 API 就绪后显示工单数据
        </Typography.Text>
      ),
    },
    {
      key: "finance",
      label: <span>💰 财务概要</span>,
      children: memberStatusLoading ? (
        <Spin size="small" />
      ) : (
        <Descriptions column={1} size="small">
          <Descriptions.Item label="会员验证">
            {latestVerification ? (
              <Tag color={getVerificationColor(latestVerification.status)}>{latestVerification.status}</Tag>
            ) : "暂无"}
          </Descriptions.Item>
          <Descriptions.Item label="WhatsApp 绑定">
            {latestBinding ? (
              <Tag color={getBindingColor(latestBinding.status)}>{latestBinding.status}</Tag>
            ) : "暂无"}
          </Descriptions.Item>
        </Descriptions>
      ),
    },
  ];

  return (
    <div style={{ padding: "0 4px" }}>
      {memberStatusError && <Alert message={memberStatusError} type="warning" showIcon style={{ marginBottom: 8 }} />}
      <Collapse items={collapseItems} defaultActiveKey={["profile"]} size="small" />
    </div>
  );
}

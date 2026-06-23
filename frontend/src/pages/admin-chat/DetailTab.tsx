import { type JSX } from "react";



import { Descriptions, Tag, Typography } from "antd";



import type { ConversationAiStatus, ConversationSummary } from "../../services/api";



export interface DetailTabProps {

  conversation: ConversationSummary | null;

  aiStatus: ConversationAiStatus | null;

}



function fmt(v: string | null | undefined): string {

  return v ? new Date(v).toLocaleString("zh-CN") : "-";

}



function fmtMode(m: string | null | undefined): string {

  if (m === "ai_managed") return "AI 托管";

  if (m === "human_managed") return "人工接管";

  if (m === "paused") return "暂停";

  return m ?? "未知";

}



function formatAiReason(status: ConversationAiStatus | null): string {

  if (!status) return "-";

  if (status.effective_ai_enabled) return "当前生效中: AI 自动回复";

  if (status.primary_blocking_reason) return `已暂停${status.primary_blocking_reason.message}`;

  if (status.blocking_reasons.length > 0) return `已暂停${status.blocking_reasons[0].message}`;

  return "无法验证: 原因未知";

}



export function DetailTab({ conversation, aiStatus }: DetailTabProps): JSX.Element {

  if (!conversation) {

    return <Typography.Text type="secondary">未选择会话</Typography.Text>;

  }



  return (

    <div style={{ padding: "0 4px" }}>

      <Descriptions column={1} size="small" bordered>

        <Descriptions.Item label="账户">{conversation.account_id}</Descriptions.Item>

        <Descriptions.Item label="管理模式">{fmtMode(conversation.management_mode)}</Descriptions.Item>

        <Descriptions.Item label="状态">

          <Tag color={conversation.status === "open" ? "success" : "default"}>

            {conversation.status === "open" ? "进行中" : "进行中"}

          </Tag>

        </Descriptions.Item>

        <Descriptions.Item label="手机号 ID">{conversation.phone_number_id ?? "-"}</Descriptions.Item>

        <Descriptions.Item label="客户">{conversation.customer_id}</Descriptions.Item>

        <Descriptions.Item label="最后消息">{fmt(conversation.last_message_at)}</Descriptions.Item>

        <Descriptions.Item label="接管状态">

          <Tag color={conversation.latest_handover_recommended ? "volcano" : "default"}>

            {conversation.latest_handover_recommended ? "建议转人工" : "普通消息"}

          </Tag>

        </Descriptions.Item>

        <Descriptions.Item label="转接原因">{conversation.latest_handover_reason ?? "-"}</Descriptions.Item>

        <Descriptions.Item label="坐席">

          {conversation.assigned_agent_name

            ? `${conversation.assigned_agent_name} (${conversation.assigned_agent_id})`

            : "未分配"}

        </Descriptions.Item>

      </Descriptions>



      <div style={{ marginTop: 12 }}>

        <Descriptions column={1} size="small" bordered title="AI 状态">

          <Descriptions.Item label="全局 AI">{aiStatus?.global_ai_enabled ? "开启" : "关闭"}</Descriptions.Item>

          <Descriptions.Item label="账号 AI">{aiStatus?.account_ai_enabled ? "开启" : "关闭"}</Descriptions.Item>

          <Descriptions.Item label="会话 AI">{aiStatus?.conversation_ai_enabled ? "开启" : "关闭"}</Descriptions.Item>

          <Descriptions.Item label="生效状态">

            <Tag color={aiStatus?.effective_ai_enabled ? "success" : "error"}>

              {aiStatus?.effective_ai_enabled ? "开启" : "关闭"}

            </Tag>

          </Descriptions.Item>

          <Descriptions.Item label="原因">{formatAiReason(aiStatus)}</Descriptions.Item>

        </Descriptions>

      </div>

    </div>

  );

}


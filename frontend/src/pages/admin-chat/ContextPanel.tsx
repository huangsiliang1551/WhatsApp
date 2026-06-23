import { type JSX } from "react";

import { Empty, Tabs } from "antd";

import type { ConversationAiStatus, ConversationSummary, ConversationTimelineItem, RuntimeAgent, TemplateSendLogView } from "../../services/api";
import type { CustomerProfileSummary } from "../../types/operations";
import { OperationsTab } from "./OperationsTab";
import { DetailTab } from "./DetailTab";
import { CustomerTab } from "./CustomerTab";
import { HistoryTab } from "./HistoryTab";

export interface ContextPanelProps {
  conversation: ConversationSummary | null;
  aiStatus: ConversationAiStatus | null;
  timeline: ConversationTimelineItem[];
  templateLogs: TemplateSendLogView[];
  customerProfile: CustomerProfileSummary | null;
  agents: RuntimeAgent[];
  agentOptions: { label: string; value: string }[];
  pendingAction: string | null;
  globalAiEnabled: boolean;
  onHandover: () => void;
  onRestoreAI: () => void;
  onPause: () => void;
  onClose: () => void;
  onToggleAiSwitch: () => void;
  onAssignAgent: (agentId: string) => void;
  onReasonChange: (reason: string) => void;
  onOpenCustomerPage: () => void;
}

export function ContextPanel({
  conversation,
  aiStatus,
  timeline,
  templateLogs,
  customerProfile,
  agents,
  agentOptions,
  pendingAction,
  globalAiEnabled,
  onHandover,
  onRestoreAI,
  onPause,
  onClose,
  onToggleAiSwitch,
  onAssignAgent,
  onReasonChange,
  onOpenCustomerPage,
}: ContextPanelProps): JSX.Element {
  const showSkeleton = !conversation;

  const tabContent = (key: string) => {
    if (showSkeleton) {
      return (
        <div style={{ padding: 24, color: "#bbb", fontSize: 12, textAlign: "center" }}>
          ⚡ 选择会话后可查看{key === "operations" ? "操作" : key === "detail" ? "详情" : key === "customer" ? "客户" : "历史"}信息
        </div>
      );
    }
    switch (key) {
      case "operations":
        return (
          <OperationsTab
            conversation={conversation}
            aiStatus={aiStatus}
            agents={agents}
            agentOptions={agentOptions}
            pendingAction={pendingAction}
            globalAiEnabled={globalAiEnabled}
            onHandover={onHandover}
            onRestoreAI={onRestoreAI}
            onPause={onPause}
            onClose={onClose}
            onToggleAiSwitch={onToggleAiSwitch}
            onAssignAgent={onAssignAgent}
            onReasonChange={onReasonChange}
          />
        );
      case "detail":
        return <DetailTab conversation={conversation} aiStatus={aiStatus} />;
      case "customer":
        return (
          <CustomerTab
            conversation={conversation}
            customerProfile={customerProfile}
            onOpenCustomerPage={onOpenCustomerPage}
          />
        );
      case "history":
        return <HistoryTab timeline={timeline} templateLogs={templateLogs} />;
      default:
        return null;
    }
  };

  return (
    <Tabs
      defaultActiveKey="operations"
      size="small"
      style={{ height: "100%" }}
      items={[
        { key: "operations", label: "🎯 操作", children: tabContent("operations") },
        { key: "detail", label: "📋 详情", children: tabContent("detail") },
        { key: "customer", label: "👤 客户", children: tabContent("customer") },
        { key: "history", label: "📜 历史", children: tabContent("history") },
      ]}
    />
  );
}

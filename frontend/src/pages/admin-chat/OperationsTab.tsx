import { type JSX, useEffect, useState } from "react";
import { Alert, Button, Input, Popconfirm, Select, Space, Tag, Typography, AutoComplete } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ConversationAiStatus, ConversationSummary, RuntimeAgent } from "../../services/api";

const TAGS_STORAGE_PREFIX = "fx_tags_";

function loadTags(accountId: string, conversationId: string): string[] {
  try {
    const key = `${TAGS_STORAGE_PREFIX}${accountId}_${conversationId}`;
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw) as string[];
  } catch { /* ignore */ }
  return [];
}

function saveTags(accountId: string, conversationId: string, tags: string[]): void {
  const key = `${TAGS_STORAGE_PREFIX}${accountId}_${conversationId}`;
  localStorage.setItem(key, JSON.stringify(tags));
}

function getAllTags(): string[] {
  const all = new Set<string>();
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(TAGS_STORAGE_PREFIX)) {
        const raw = localStorage.getItem(k);
        if (raw) {
          const arr = JSON.parse(raw) as string[];
          arr.forEach((t) => all.add(t));
        }
      }
    }
  } catch { /* ignore */ }
  return Array.from(all).sort();
}

export interface OperationsTabProps {
  conversation: ConversationSummary | null;
  aiStatus: ConversationAiStatus | null;
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
}

function formatMode(m: string | null | undefined): string {
  if (m === "ai_managed") return "AI 托管";
  if (m === "human_managed") return "人工接管";
  if (m === "paused") return "已暂停";
  return m ?? "未知";
}

export function OperationsTab({
  conversation,
  aiStatus,
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
}: OperationsTabProps): JSX.Element {
  if (!conversation) {
    return <Typography.Text type="secondary">未选择会话</Typography.Text>;
  }

  const mode = conversation.management_mode;
  const isHuman = mode === "human_managed";
  const isPaused = mode === "paused";
  const recommended = conversation.latest_handover_recommended;

  // FX-012: 会话标签
  const [tags, setTags] = useState<string[]>(() =>
    loadTags(conversation.account_id, conversation.conversation_id)
  );
  const [addTagInput, setAddTagInput] = useState("");
  const allExistingTags = getAllTags();

  useEffect(() => {
    setTags(loadTags(conversation.account_id, conversation.conversation_id));
    setAddTagInput("");
  }, [conversation.account_id, conversation.conversation_id]);

  const handleRemoveTag = (tag: string) => {
    const next = tags.filter((t) => t !== tag);
    setTags(next);
    saveTags(conversation.account_id, conversation.conversation_id, next);
  };

  const handleAddTag = (value: string) => {
    const trimmed = value.trim();
    if (trimmed && !tags.includes(trimmed)) {
      const next = [...tags, trimmed];
      setTags(next);
      saveTags(conversation.account_id, conversation.conversation_id, next);
    }
    setAddTagInput("");
  };

  return (
    <div style={{ padding: "0 4px" }}>
      <div style={{ fontSize: 20, fontWeight: 600, textAlign: "center", padding: "12px 0", color: isHuman ? "#faad14" : isPaused ? "#999" : "#1677ff" }}>
        {formatMode(mode)}
      </div>

      {recommended && !isHuman && (
        <Alert
          showIcon
          type="warning"
          message="建议转人工"
          description={conversation.latest_handover_reason ?? "暂无"}
          style={{ marginBottom: 12, fontSize: 12 }}
        />
      )}

      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Select
          size="small"
          options={agentOptions}
          placeholder="选择操作坐席"
          value={conversation.assigned_agent_id || undefined}
          onChange={(v) => onAssignAgent(v)}
          style={{ width: "100%" }}
        />

        <Input.TextArea
          rows={2}
          size="small"
          placeholder="输入原因(可选)"
          onChange={(e) => onReasonChange(e.target.value)}
        />

        <Popconfirm title="确认人工接管" description="接管后 AI 停止自动回复" onConfirm={onHandover} okText="确认接管" cancelText="取消">
          <Button block size="small" type="primary" disabled={isHuman || isPaused} loading={pendingAction === "mode:human_managed"}>
            人工接管
          </Button>
        </Popconfirm>

        <Popconfirm title="确认恢复 AI" description="恢复后 AI 自动回复消息" onConfirm={onRestoreAI} okText="确认恢复" cancelText="取消">
          <Button block size="small" disabled={!isHuman} loading={pendingAction === "mode:ai_managed"}>
            恢复 AI
          </Button>
        </Popconfirm>

        <Popconfirm title="确认暂停会话" description="暂停后 AI 不再自动回复" onConfirm={onPause} okText="确认暂停" cancelText="取消">
          <Button block size="small" danger disabled={isPaused} loading={pendingAction === "mode:paused"}>
            暂停会话
          </Button>
        </Popconfirm>

        <Popconfirm title="确认关闭会话" description="关闭后无法继续发送消息" onConfirm={onClose} okText="确认关闭" cancelText="取消">
          <Button block size="small" loading={pendingAction === "close"}>
            关闭会话
          </Button>
        </Popconfirm>
      </Space>

      <div style={{ marginTop: 12, padding: "8px 0", borderTop: "1px solid #f0f0f0" }}>
        <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>AI 控制</Typography.Text>
        <div style={{ marginTop: 4, fontSize: 12 }}>
          <Tag color={globalAiEnabled ? "processing" : "default"} style={{ marginBottom: 4 }}>
            全局 AI: {globalAiEnabled ? "已开" : "已关"}
          </Tag>
          <Tag color={conversation.ai_enabled ? "success" : "default"} style={{ marginBottom: 4 }}>
            会话 AI: {conversation.ai_enabled ? "已开" : "已关"}
          </Tag>
        </div>
        {!globalAiEnabled && (
          <Typography.Text type="warning" style={{ fontSize: 11 }}>全局 AI 已关闭</Typography.Text>
        )}
        <Popconfirm title="确认切换会话 AI" description={conversation.ai_enabled ? "关闭后 AI 暂停回复" : "开启后 AI 自动回复"} onConfirm={onToggleAiSwitch} okText="确认" cancelText="取消">
          <Button block size="small" loading={pendingAction === "toggle-ai"} style={{ marginTop: 6 }}>
            {conversation.ai_enabled ? "关闭会话 AI" : "开启会话 AI"}
          </Button>
        </Popconfirm>
      </div>

      {/* FX-012: 会话标签 */}
      <div style={{ marginTop: 12, padding: "8px 0", borderTop: "1px solid #f0f0f0" }}>
        <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>会话标签</Typography.Text>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
          {tags.map((t) => (
            <Tag key={t} closable onClose={() => handleRemoveTag(t)} style={{ fontSize: 11, margin: 0 }}>
              {t}
            </Tag>
          ))}
          <AutoComplete
            value={addTagInput}
            onChange={setAddTagInput}
            onSelect={handleAddTag}
            options={allExistingTags
              .filter((t) => !tags.includes(t) && t.includes(addTagInput))
              .map((t) => ({ value: t }))}
            style={{ width: 100 }}
            size="small"
          >
            <Input
              size="small"
              placeholder="+ 添加标签"
              prefix={<PlusOutlined style={{ fontSize: 10 }} />}
              onPressEnter={(e) => handleAddTag((e.target as HTMLInputElement).value)}
              style={{ fontSize: 11, height: 22 }}
            />
          </AutoComplete>
        </div>
      </div>
    </div>
  );
}

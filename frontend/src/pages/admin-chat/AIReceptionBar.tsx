// AIReceptionBar：会话顶部 AI 接待归属条。
//
// 展示：当前客服归属、客户绑定 AI、本次实际接待 AI、临时 failover、
// source entry link、handover 状态、AI 开关。
// 操作：切换 AI、转人工、恢复 AI、查看归属历史、复制入口链接。
// 不重建聊天页，仅扩展顶部条。

import { useState, type JSX } from "react";
import { Alert, Button, Modal, Select, Space, Tag, message } from "antd";
import {
  ApiOutlined,
  CopyOutlined,
  HistoryOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  SwapOutlined,
  UserSwitchOutlined,
} from "@ant-design/icons";

import type { ConversationSummary } from "../../services/api";
import { switchConversationAI } from "../../services/entryLinks";

interface AIReceptionBarProps {
  selConv: ConversationSummary;
  canSwitchAI: boolean;
  canHandover: boolean;
  canRestoreAI: boolean;
  canViewAudit: boolean;
  onSwitchAI: (aiAgentId: string) => void | Promise<void>;
  onHandover: () => void | Promise<void>;
  onRestoreAI: () => void | Promise<void>;
}

interface AssignmentPayload {
  current_ai_agent_id?: string | null;
  current_ai_assignment_id?: string | null;
  current_entry_link_id?: string | null;
  current_owner_staff_user_id_snapshot?: string | null;
  current_owner_agency_id_snapshot?: string | null;
  current_owner_agency_member_id_snapshot?: string | null;
  current_owner_assignment_id_snapshot?: string | null;
  ai_failover_active?: boolean;
  ai_failover_from_agent_id?: string | null;
  ai_failover_reason?: string | null;
  attribution_status?: string | null;
  binding_ai_agent_id?: string | null;
}

function readAssignment(selConv: ConversationSummary): AssignmentPayload {
  const direct = selConv as unknown as AssignmentPayload;
  if (direct && (direct.current_ai_agent_id !== undefined || direct.ai_failover_active !== undefined)) {
    return direct;
  }
  const nested = (selConv as unknown as { attribution?: AssignmentPayload | null }).attribution;
  return nested ?? {};
}

function copyToClipboard(text: string, label: string) {
  if (!text) {
    message.warning(`${label} 为空，无法复制`);
    return;
  }
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    navigator.clipboard
      .writeText(text)
      .then(() => message.success(`${label} 已复制`))
      .catch(() => message.info(`请手动复制：${text}`));
  } else {
    message.info(`请手动复制：${text}`);
  }
}

export function AIReceptionBar({
  selConv,
  canSwitchAI,
  canHandover,
  canRestoreAI,
  canViewAudit,
  onSwitchAI,
  onHandover,
  onRestoreAI,
}: AIReceptionBarProps): JSX.Element | null {
  const a = readAssignment(selConv);
  const [switchOpen, setSwitchOpen] = useState(false);
  const [switchTarget, setSwitchTarget] = useState<string | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  if (!selConv) return null;

  const isHuman = selConv.management_mode === "human_managed";
  const isPaused = selConv.management_mode === "paused";
  const failoverActive = Boolean(a.ai_failover_active);

  const h5Link = a.current_entry_link_id
    ? `${window.location.origin}/h5/register?code=${a.current_entry_link_id}`
    : "";

  const confirmSwitch = async () => {
    if (!switchTarget) {
      message.warning("请先选择目标 AI Agent");
      return;
    }
    setSwitching(true);
    try {
      await switchConversationAI(
        selConv.account_id,
        selConv.conversation_id,
        switchTarget,
        "switched_from_chat_header",
      );
      await onSwitchAI(switchTarget);
      message.success("会话 AI 已切换");
      setSwitchOpen(false);
      setSwitchTarget(null);
    } catch (err) {
      message.error(`切换失败：${(err as Error).message}`);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div
      style={{
        padding: "8px 12px",
        background: failoverActive ? "#fff7e6" : "#fafafa",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        alignItems: "center",
      }}
    >
      <Space size={6} wrap>
        <UserSwitchOutlined />
        <span>客服：</span>
        <Tag color="blue">
          {a.current_owner_staff_user_id_snapshot ?? "未归属"}
        </Tag>
        <ApiOutlined />
        <span>客户绑定 AI：</span>
        <Tag color="purple">
          {a.current_ai_agent_id ?? a.binding_ai_agent_id ?? "未绑定"}
        </Tag>
        <span>本次实际 AI：</span>
        <Tag color={failoverActive ? "orange" : "green"}>
          {a.current_ai_agent_id ?? "—"}
        </Tag>
        {failoverActive ? (
          <Tag color="orange">
            临时 failover：{a.ai_failover_from_agent_id ?? "?"} → {a.current_ai_agent_id}
            {a.ai_failover_reason ? `（${a.ai_failover_reason}）` : ""}
          </Tag>
        ) : null}
        <span>状态：</span>
        {isHuman ? (
          <Tag color="blue">人工接管</Tag>
        ) : isPaused ? (
          <Tag color="orange">已暂停</Tag>
        ) : (
          <Tag color="green">AI 托管</Tag>
        )}
        {a.attribution_status ? (
          <Tag>{`归属：${a.attribution_status}`}</Tag>
        ) : null}
      </Space>
      <Space style={{ marginLeft: "auto" }} size={4} wrap>
        {canSwitchAI ? (
          <Button
            size="small"
            icon={<SwapOutlined />}
            onClick={() => setSwitchOpen(true)}
            disabled={isHuman}
          >
            切换 AI
          </Button>
        ) : null}
        {isHuman ? (
          canRestoreAI ? (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => void onRestoreAI()}
            >
              恢复 AI
            </Button>
          ) : null
        ) : canHandover ? (
          <Button
            size="small"
            icon={<PauseCircleOutlined />}
            danger
            onClick={() => void onHandover()}
          >
            转人工
          </Button>
        ) : null}
        <Button
          size="small"
          icon={<CopyOutlined />}
          disabled={!h5Link}
          onClick={() => copyToClipboard(h5Link, "入口链接")}
        >
          复制入口
        </Button>
        {canViewAudit ? (
          <Button
            size="small"
            icon={<HistoryOutlined />}
            onClick={() => setAuditOpen(true)}
          >
            归属历史
          </Button>
        ) : null}
      </Space>
      {failoverActive ? (
        <Alert
          type="warning"
          showIcon
          message="本次会话触发临时 failover。会员 current_ai_agent_id 未改变。"
          style={{ flex: 1, minWidth: 240 }}
        />
      ) : null}
      <Modal
        open={switchOpen}
        title="切换会话 AI"
        onCancel={() => setSwitchOpen(false)}
        onOk={() => void confirmSwitch()}
        confirmLoading={switching}
        destroyOnClose
      >
        <p>请选择要切换到的 AI Agent：</p>
        <Select
          style={{ width: "100%" }}
          placeholder="AI Agent ID"
          value={switchTarget ?? undefined}
          onChange={(v) => setSwitchTarget(v)}
          options={[
            { value: a.current_ai_agent_id ?? undefined, label: `当前 (${a.current_ai_agent_id ?? "无"})` },
          ]}
          showSearch
        />
        <p style={{ color: "#999", marginTop: 8 }}>
          提示：可输入 AI Agent UUID 直接切换。切换仅影响本次会话，不改写客户 current_ai_agent_id。
        </p>
      </Modal>
      <Modal
        open={auditOpen}
        title="归属审计占位"
        onCancel={() => setAuditOpen(false)}
        onOk={() => setAuditOpen(false)}
        cancelText="关闭"
        okText="好"
      >
        <p>归属历史查询请调用：</p>
        <code>GET /api/ownership-audit/member/&lt;member_profile_id&gt;</code>
        <p style={{ marginTop: 8 }}>
          或 <code>GET /api/ownership-audit/events?action=member_ai_transferred</code> 查看最近 AI 划转事件。
        </p>
      </Modal>
    </div>
  );
}

export default AIReceptionBar;

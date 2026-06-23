import { useCallback, useState } from "react";

import { message } from "antd";
import axios from "axios";

import type {
  ConversationSummary,
  MediaAssetView,
  MessageTemplateView,
} from "../../../services/api";
import {
  assignConversation,
  batchAssignConversationsByAgent,
  batchCloseConversations,
  batchHandoverConversations,
  batchRestoreAIConversations,
  closeConversation,
  reopenConversation,
  sendConversationMediaMessage,
  sendMockInboundMessage,
  sendOutboundMessage,
  sendTemplateMessage,
  setConversationAiEnabled,
  setConversationManagementMode,
} from "../../../services/api";
import { useAppStore } from "../../../stores/appStore";

export interface ChatActions {
  pendingAction: string | null;
  sendMessage: (conv: ConversationSummary, text: string) => Promise<void>;
  mockInbound: (conv: ConversationSummary, text: string, lang?: string) => Promise<void>;
  handover: (conv: ConversationSummary, reason?: string) => Promise<void>;
  restoreAI: (conv: ConversationSummary, reason?: string) => Promise<void>;
  pause: (conv: ConversationSummary, reason?: string) => Promise<void>;
  close: (conv: ConversationSummary, reason?: string) => Promise<void>;
  reopen: (conv: ConversationSummary, reason?: string) => Promise<void>;
  toggleAiSwitch: (conv: ConversationSummary) => Promise<void>;
  assignAgent: (
    conv: ConversationSummary,
    agentId: string,
    reason?: string
  ) => Promise<void>;
  sendTemplate: (
    template: MessageTemplateView,
    conv: ConversationSummary,
    vars: Record<string, string>
  ) => Promise<void>;
  sendMedia: (
    media: MediaAssetView,
    conv: ConversationSummary,
    caption?: string,
    fileName?: string
  ) => Promise<void>;
  batchHandover: (convKeys: string[]) => Promise<void>;
  batchRestoreAI: (convKeys: string[]) => Promise<void>;
  batchClose: (convKeys: string[]) => Promise<void>;
  batchAssign: (convKeys: string[], agentId: string) => Promise<void>;
}

export function useChatActions(onSuccess: () => Promise<void>): ChatActions {
  const [pendingAction, setPending] = useState<string | null>(null);
  const caId = useAppStore((s) => s.consoleAgentId);

  const exec = useCallback(
    async (actionLabel: string, fn: () => Promise<unknown>) => {
      setPending(actionLabel);
      try {
        await fn();
        await onSuccess();
      } catch (e) {
        const detail = axios.isAxiosError(e) && e.response?.data?.detail
          ? (typeof e.response.data.detail === "string" ? e.response.data.detail : JSON.stringify(e.response.data.detail))
          : null;
        message.error(detail || (e instanceof Error ? e.message : `${actionLabel} 失败`));
      } finally {
        setPending(null);
      }
    },
    [onSuccess]
  );

  const sendMessage = useCallback(
    (conv: ConversationSummary, text: string) =>
      exec("send", () =>
        sendOutboundMessage(conv.account_id, conv.conversation_id, {
          text,
          agent_id: caId,
        })
      ),
    [exec, caId]
  );

  const mockInbound = useCallback(
    (conv: ConversationSummary, text: string, lang?: string) =>
      exec("mock", () =>
        sendMockInboundMessage({
          account_id: conv.account_id,
          conversation_id: conv.conversation_id,
          user_id: conv.customer_id,
          text,
          mode: "ai",
          language_hint: lang,
          phone_number_id: conv.phone_number_id ?? undefined,
        })
      ),
    [exec]
  );

  const setMode = useCallback(
    (conv: ConversationSummary, mode: "ai_managed" | "human_managed" | "paused", reason?: string) =>
      exec(`mode:${mode}`, () =>
        setConversationManagementMode(conv.account_id, conv.conversation_id, {
          management_mode: mode,
          agent_id: caId,
          reason: reason?.trim() || undefined,
        })
      ),
    [exec, caId]
  );

  const handover = useCallback(
    (conv: ConversationSummary, reason?: string) => setMode(conv, "human_managed", reason),
    [setMode]
  );

  const restoreAI = useCallback(
    (conv: ConversationSummary, reason?: string) => setMode(conv, "ai_managed", reason),
    [setMode]
  );

  const pause = useCallback(
    (conv: ConversationSummary, reason?: string) => setMode(conv, "paused", reason),
    [setMode]
  );

  const closeFn = useCallback(
    (conv: ConversationSummary, reason?: string) =>
      exec("close", () =>
        closeConversation(conv.account_id, conv.conversation_id, {
          agent_id: caId,
          reason: reason?.trim() || undefined,
        })
      ),
    [exec, caId]
  );

  const reopen = useCallback(
    (conv: ConversationSummary, reason?: string) =>
      exec("reopen", () =>
        reopenConversation(conv.account_id, conv.conversation_id, {
          agent_id: caId,
          reason: reason?.trim() || undefined,
        })
      ),
    [exec, caId]
  );

  const toggleAiSwitch = useCallback(
    (conv: ConversationSummary) =>
      exec("toggle-ai", () =>
        setConversationAiEnabled(conv.account_id, conv.conversation_id, {
          enabled: !conv.ai_enabled,
        })
      ),
    [exec]
  );

  const assignAgent = useCallback(
    (conv: ConversationSummary, agentId: string, reason?: string) =>
      exec("assign", () =>
        assignConversation(conv.account_id, conv.conversation_id, {
          agent_id: agentId,
          assigned_by_agent_id: caId,
          reason: reason?.trim() || undefined,
        })
      ),
    [exec, caId]
  );

  const sendTemplate = useCallback(
    (template: MessageTemplateView, conv: ConversationSummary, vars: Record<string, string>) =>
      exec("send-template", () =>
        sendTemplateMessage(template.template_id, {
          account_id: conv.account_id,
          conversation_id: conv.conversation_id,
          phone_number_id: conv.phone_number_id ?? undefined,
          agent_id: caId,
          variables: vars,
        })
      ),
    [exec, caId]
  );

  const sendMedia = useCallback(
    (
      media: MediaAssetView,
      conv: ConversationSummary,
      caption?: string,
      fileName?: string
    ) =>
      exec("send-media", () =>
        sendConversationMediaMessage(conv.account_id, conv.conversation_id, {
          asset_id: media.asset_id,
          caption: caption?.trim() || undefined,
          file_name: fileName?.trim() || undefined,
          agent_id: caId,
        })
      ),
    [exec, caId]
  );

  const batchHandover = useCallback(
    async (convKeys: string[]) => {
      setPending("batch-handover");
      try {
        const result = await batchHandoverConversations(convKeys);
        if (result.failed_count > 0) {
          const failures = result.results.filter(r => r.status === "failed");
          message.warning(`接管完成: ${result.success_count} 成功, ${result.failed_count} 失败 - ${failures.map(f => f.error).join("; ")}`);
        } else {
          message.success(`批量接管完成 (${result.success_count} 个会话)`);
        }
        await onSuccess();
      } catch (e) {
        const detail = axios.isAxiosError(e) && e.response?.data?.detail
          ? (typeof e.response.data.detail === "string" ? e.response.data.detail : JSON.stringify(e.response.data.detail))
          : null;
        message.error(detail || (e instanceof Error ? e.message : "批量接管失败"));
      } finally {
        setPending(null);
      }
    },
    [onSuccess]
  );

  const batchRestoreAI = useCallback(
    async (convKeys: string[]) => {
      setPending("batch-restore-ai");
      try {
        const result = await batchRestoreAIConversations(convKeys);
        if (result.failed_count > 0) {
          const failures = result.results.filter(r => r.status === "failed");
          message.warning(`恢复AI完成: ${result.success_count} 成功, ${result.failed_count} 失败 - ${failures.map(f => f.error).join("; ")}`);
        } else {
          message.success(`已恢复AI (${result.success_count} 个会话)`);
        }
        await onSuccess();
      } catch (e) {
        const detail = axios.isAxiosError(e) && e.response?.data?.detail
          ? (typeof e.response.data.detail === "string" ? e.response.data.detail : JSON.stringify(e.response.data.detail))
          : null;
        message.error(detail || (e instanceof Error ? e.message : "批量恢复AI失败"));
      } finally {
        setPending(null);
      }
    },
    [onSuccess]
  );

  const batchClose = useCallback(
    async (convKeys: string[]) => {
      setPending("batch-close");
      try {
        const result = await batchCloseConversations(convKeys);
        if (result.failed_count > 0) {
          const failures = result.results.filter(r => r.status === "failed");
          message.warning(`关闭完成: ${result.success_count} 成功, ${result.failed_count} 失败 - ${failures.map(f => f.error).join("; ")}`);
        } else {
          message.success(`已批量关闭 (${result.success_count} 个会话)`);
        }
        await onSuccess();
      } catch (e) {
        const detail = axios.isAxiosError(e) && e.response?.data?.detail
          ? (typeof e.response.data.detail === "string" ? e.response.data.detail : JSON.stringify(e.response.data.detail))
          : null;
        message.error(detail || (e instanceof Error ? e.message : "批量关闭失败"));
      } finally {
        setPending(null);
      }
    },
    [onSuccess]
  );

  const batchAssign = useCallback(
    async (convKeys: string[], agentId: string) => {
      setPending("batch-assign");
      try {
        const result = await batchAssignConversationsByAgent(convKeys, agentId);
        if (result.failed_count > 0) {
          const failures = result.results.filter(r => r.status === "failed");
          message.warning(`分配完成: ${result.success_count} 成功, ${result.failed_count} 失败 - ${failures.map(f => f.error).join("; ")}`);
        } else {
          message.success(`已批量分配 (${result.success_count} 个会话)`);
        }
        await onSuccess();
      } catch (e) {
        const detail = axios.isAxiosError(e) && e.response?.data?.detail
          ? (typeof e.response.data.detail === "string" ? e.response.data.detail : JSON.stringify(e.response.data.detail))
          : null;
        message.error(detail || (e instanceof Error ? e.message : "批量分配失败"));
      } finally {
        setPending(null);
      }
    },
    [onSuccess]
  );

  return {
    pendingAction,
    sendMessage,
    mockInbound,
    handover,
    restoreAI,
    pause,
    close: closeFn,
    reopen,
    toggleAiSwitch,
    assignAgent,
    sendTemplate,
    sendMedia,
    batchHandover,
    batchRestoreAI,
    batchClose,
    batchAssign,
  };
}

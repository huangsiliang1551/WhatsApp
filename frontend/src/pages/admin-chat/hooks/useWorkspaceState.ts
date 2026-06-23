import { useCallback, useEffect, useState } from "react";

import {
  listAgentWorkloads,
  listConversations,
  listMediaAssets,
  listMessageTemplates,
  listRuntimeAgents,
  listRuntimeState,
  type AgentWorkload,
  type ConversationSummary,
  type MediaAssetView,
  type MessageTemplateView,
  type RuntimeAgent,
  type RuntimeState,
} from "../../../services/api";

export interface ConvFilter {
  accountIds: string[];
  managementMode: "all" | "ai_managed" | "human_managed" | "paused";
  handoverMode: "all" | "recommended" | "normal";
  search: string;
  /** F6: 沉睡会话过滤：null=显示活跃, true=仅沉睡, false=仅活跃 */
  isSleeping: "all" | "active" | "sleeping";
}

export const INITIAL_FILTERS: ConvFilter = {
  accountIds: [],
  managementMode: "all",
  handoverMode: "all",
  search: "",
  isSleeping: "active",
};

export interface WorkspaceState {
  filter: ConvFilter;
  setFilter: (f: Partial<ConvFilter>) => void;
  conversations: ConversationSummary[];
  runtimeState: RuntimeState | null;
  agents: RuntimeAgent[];
  workloads: AgentWorkload[];
  templates: MessageTemplateView[];
  mediaAssets: MediaAssetView[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useWorkspaceState(initialFilter?: Partial<ConvFilter>): WorkspaceState {
  const [filter, setFilterRaw] = useState<ConvFilter>({ ...INITIAL_FILTERS, ...initialFilter });
  const [conversations, setConvs] = useState<ConversationSummary[]>([]);
  const [runtimeState, setRt] = useState<RuntimeState | null>(null);
  const [agents, setAgents] = useState<RuntimeAgent[]>([]);
  const [workloads, setWorkloads] = useState<AgentWorkload[]>([]);
  const [templates, setTmpl] = useState<MessageTemplateView[]>([]);
  const [mediaAssets, setMedia] = useState<MediaAssetView[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setErr] = useState<string | null>(null);

  const setFilter = useCallback((f: Partial<ConvFilter>) => {
    setFilterRaw((prev) => ({ ...prev, ...f }));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    const mode = filter.managementMode !== "all" ? filter.managementMode : undefined;
    const recommended =
      filter.handoverMode === "recommended"
        ? true
        : filter.handoverMode === "normal"
          ? false
          : undefined;
    try {
      const [c, r, a, w, t, m] = await Promise.all([
        listConversations({
          management_mode: mode,
          latest_handover_recommended: recommended,
          is_sleeping: filter.isSleeping === "sleeping" ? true : filter.isSleeping === "active" ? false : undefined,
        }),
        listRuntimeState(),
        listRuntimeAgents(),
        listAgentWorkloads(),
        listMessageTemplates(),
        listMediaAssets({ is_active: true }),
      ]);
      setConvs(c);
      setRt(r);
      setAgents(a);
      setWorkloads(w);
      setTmpl(t);
      setMedia(m);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [filter.accountIds, filter.managementMode, filter.handoverMode, filter.isSleeping]);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    filter,
    setFilter,
    conversations,
    runtimeState,
    agents,
    workloads,
    templates,
    mediaAssets,
    loading,
    error,
    reload: load,
  };
}

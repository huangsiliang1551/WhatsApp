import { useCallback, useEffect, useRef } from "react";
import { usePageData } from "./usePageData";
import {
  getLaunchReadiness,
  getMetricsSummary,
  getWhatsAppStatsDetail,
  listAgentWorkloads,
  listMetaAccounts,
  listRuntimeState,
  type AgentWorkload,
  type LaunchReadinessResponse,
  type MetricsSummaryResponse,
  type RuntimeState,
  type WhatsAppStatsSummary,
} from "../services/api";

export interface DashboardData {
  runtimeState: RuntimeState | null;
  metrics: MetricsSummaryResponse | null;
  whatsAppSummary: WhatsAppStatsSummary | null;
  launchReadiness: LaunchReadinessResponse | null;
  agents: AgentWorkload[];
  metaAccountsCount: number;
}

export function useDashboardData(autoRefreshMs = 15000) {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetcher = useCallback(async (): Promise<DashboardData> => {
    const [rt, m, wa, lr, ag, ma] = await Promise.all([
      listRuntimeState().catch(() => null),
      getMetricsSummary().catch(() => null),
      getWhatsAppStatsDetail().catch(() => null),
      getLaunchReadiness().catch(() => null),
      listAgentWorkloads().catch(() => null),
      listMetaAccounts().catch(() => []),
    ]);
    return {
      runtimeState: rt,
      metrics: m,
      whatsAppSummary: wa?.summary ?? null,
      launchReadiness: lr,
      agents: ag ?? [],
      metaAccountsCount: Array.isArray(ma) ? ma.length : 0,
    };
  }, []);

  const { data, loading, error, reload } = usePageData({
    fetcher,
    immediate: true,
  });

  // 自动刷新
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => { void reload(); }, autoRefreshMs);
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [reload, autoRefreshMs]);

  const conversations = data?.runtimeState?.conversations ?? [];
  const totalConv = conversations.length || 1;
  const aiManaged = conversations.filter((c) => c.management_mode === "ai_managed").length;
  const humanManaged = conversations.filter((c) => c.management_mode === "human_managed").length;
  const paused = conversations.filter((c) => c.management_mode === "paused").length;
  const recommended = conversations.filter((c) => (c as any).latest_handover_recommended).length;

  return {
    data,
    loading,
    error,
    reload,
    stats: {
      totalConversations: conversations.length,
      aiManaged,
      humanManaged,
      paused,
      recommended,
      aiPct: Math.round((aiManaged / totalConv) * 100),
      humanPct: Math.round((humanManaged / totalConv) * 100),
      pausedPct: Math.round((paused / totalConv) * 100),
    },
    accounts: data?.runtimeState?.accounts ?? [],
  };
}

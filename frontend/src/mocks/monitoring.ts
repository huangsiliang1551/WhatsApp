import type {
  AuditLogEntry,
  MetricsSummaryResponse,
  ProviderStatusBufferEntry,
  QueueStatsResponse,
  RuntimeConfigSummary,
  RuntimeState,
} from "../services/api";

export type MonitoringTrendPoint = {
  label: string;
  value: number;
};

export type MonitoringEventItem = {
  id: string;
  title: string;
  summary: string;
  timestamp: string;
  source: "api" | "frontend_mock";
  category: "audit" | "provider" | "mock";
  account_id?: string | null;
  action?: string;
  target_type?: string;
  target_id?: string | null;
  provider_name?: string;
  provider_message_id?: string;
  external_status?: string;
  waba_id?: string | null;
  phone_number_id?: string | null;
};

export type MonitoringInfraCard = {
  id: string;
  label: string;
  status: "healthy" | "warning" | "degraded" | "placeholder";
  summary: string;
  source: "api" | "frontend_mock";
};

function clampSeriesValue(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.round(value));
}

function buildSeries(base: number, deltas: number[]): MonitoringTrendPoint[] {
  return deltas.map((delta, index) => ({
    label: `${index + 1}h`,
    value: clampSeriesValue(base + delta),
  }));
}

export function buildRequestTrend(metrics: MetricsSummaryResponse | null): MonitoringTrendPoint[] {
  if (!metrics) {
    return buildSeries(18, [-4, 0, 3, 7, 5, 8, 4]);
  }

  const base = Math.max(
    6,
    Math.round(
      (metrics.inbound.accepted_total + metrics.outbound.accepted_total + metrics.queue.completed_total) / 42
    )
  );
  return buildSeries(base, [-3, 1, 4, 7, 5, 8, 2]);
}

export function buildErrorTrend(metrics: MetricsSummaryResponse | null): MonitoringTrendPoint[] {
  if (!metrics) {
    return buildSeries(2, [0, 1, 1, 2, 1, 3, 1]);
  }

  const base = Math.max(
    1,
    Math.round(
      (metrics.queue.failed_total +
        metrics.processing_failures.manual_operator_total +
        metrics.processing_failures.ai_auto_reply_total +
        metrics.webhook.signature_failure_total) /
        48
    )
  );
  return buildSeries(base, [0, 1, 0, 2, 1, 2, 1]);
}

export function buildMonitoringEvents(
  auditLogs: AuditLogEntry[],
  providerItems: ProviderStatusBufferEntry[]
): MonitoringEventItem[] {
  const apiEvents: MonitoringEventItem[] = [
    ...auditLogs.slice(0, 4).map((entry) => ({
      id: `audit:${entry.id}`,
      title: entry.action,
      summary: `${entry.account_id ?? "global"} / ${entry.target_type} / ${entry.target_id ?? "n/a"}`,
      timestamp: entry.created_at,
      source: "api" as const,
      category: "audit" as const,
      account_id: entry.account_id,
      action: entry.action,
      target_type: entry.target_type,
      target_id: entry.target_id,
      waba_id: entry.waba_id,
      phone_number_id: entry.phone_number_id,
    })),
    ...providerItems.slice(0, 3).map((entry) => ({
      id: `provider:${entry.id}`,
      title: `${entry.provider_name} ${entry.external_status}`,
      summary: `${entry.account_id} / ${entry.waba_id ?? "no-waba"} / ${entry.phone_number_id ?? "no-phone"}`,
      timestamp: entry.last_seen_at,
      source: "api" as const,
      category: "provider" as const,
      account_id: entry.account_id,
      provider_name: entry.provider_name,
      provider_message_id: entry.provider_message_id,
      external_status: entry.external_status,
      waba_id: entry.waba_id,
      phone_number_id: entry.phone_number_id,
    })),
  ];

  if (apiEvents.length > 0) {
    return apiEvents;
  }

  return [
    {
      id: "mock:worker-retry",
      title: "Worker retry",
      summary: "Mock event",
      timestamp: new Date().toISOString(),
      source: "frontend_mock",
      category: "mock",
    },
    {
      id: "mock:provider-gap",
      title: "Provider replay",
      summary: "Mock event",
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      source: "frontend_mock",
      category: "mock",
    },
  ];
}

export function buildInfraCards(
  healthStatus: string,
  runtimeState: RuntimeState | null,
  queueStats: QueueStatsResponse | null,
  config: RuntimeConfigSummary | null
): MonitoringInfraCard[] {
  const runtimeConnected = runtimeState !== null;
  const queueConnected = queueStats !== null;
  const providerMode = config?.messaging_provider ?? "mock";
  const modeSummary = config?.test_mode ? "test" : config?.app_env ?? "unknown";

  return [
    {
      id: "app",
      label: "App",
      status: healthStatus === "ok" ? "healthy" : healthStatus === "loading" ? "placeholder" : "degraded",
      summary: healthStatus === "ok" ? "health ok" : "health unavailable",
      source: "api",
    },
    {
      id: "postgres",
      label: "PostgreSQL",
      status: runtimeConnected ? "healthy" : "placeholder",
      summary: runtimeConnected ? "runtime reachable" : "unavailable",
      source: runtimeConnected ? "api" : "frontend_mock",
    },
    {
      id: "redis",
      label: "Redis",
      status: queueConnected ? "healthy" : "placeholder",
      summary: queueConnected ? "queue reachable" : "unavailable",
      source: queueConnected ? "api" : "frontend_mock",
    },
    {
      id: "worker",
      label: "Worker",
      status: queueConnected ? "healthy" : "warning",
      summary: queueConnected ? `${queueStats?.queues.length ?? 0} scopes` : "unavailable",
      source: queueConnected ? "api" : "frontend_mock",
    },
    {
      id: "mode",
      label: "Mode",
      status: providerMode === "whatsapp" ? "healthy" : "warning",
      summary: `${providerMode} / ${modeSummary}`,
      source: "api",
    },
  ];
}

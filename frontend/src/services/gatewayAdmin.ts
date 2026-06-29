import { adminAuth } from "./adminAuth";
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";
import type {
  GatewayHealthSummary,
  GatewayJobRecord,
  GatewayNodeRecord,
} from "../types/gateway";

type ErrorBody = {
  detail?: string | { message?: string };
  message?: string;
};

const API_BASE = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.DEV,
);

function buildHeaders(): HeadersInit {
  const token = adminAuth.getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function normalizeErrorMessage(errorBody: ErrorBody, status: number): string {
  if (typeof errorBody.detail === "string" && errorBody.detail.trim()) {
    return errorBody.detail;
  }
  if (
    errorBody.detail &&
    typeof errorBody.detail === "object" &&
    typeof errorBody.detail.message === "string" &&
    errorBody.detail.message.trim()
  ) {
    return errorBody.detail.message;
  }
  if (typeof errorBody.message === "string" && errorBody.message.trim()) {
    return errorBody.message;
  }
  return `HTTP ${status}`;
}

async function requestJson<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: buildHeaders(),
      signal: controller.signal,
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({} as ErrorBody));
      throw new Error(normalizeErrorMessage(errorBody, response.status));
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

function toStringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function toNumberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function mapNodeRecord(item: Record<string, unknown>): GatewayNodeRecord {
  return {
    id: String(item.id ?? ""),
    accountId: toStringValue(item.account_id) ?? toStringValue(item.accountId),
    name: toStringValue(item.name) ?? "Unnamed node",
    host: toStringValue(item.host) ?? toStringValue(item.hostname) ?? "-",
    region: toStringValue(item.region),
    environment: toStringValue(item.environment),
    status: (toStringValue(item.status) ?? "unknown") as GatewayNodeRecord["status"],
    lastHeartbeatAt: toStringValue(item.last_heartbeat_at) ?? toStringValue(item.lastHeartbeatAt),
    lastDeployAt: toStringValue(item.last_deploy_at) ?? toStringValue(item.lastDeployAt),
    activeSiteCount: toNumberValue(item.active_site_count ?? item.activeSiteCount),
    updatedAt: toStringValue(item.updated_at) ?? toStringValue(item.updatedAt),
  };
}

function mapJobRecord(item: Record<string, unknown>): GatewayJobRecord {
  return {
    id: String(item.id ?? ""),
    accountId: toStringValue(item.account_id) ?? toStringValue(item.accountId),
    nodeId: toStringValue(item.node_id) ?? toStringValue(item.nodeId),
    siteId: toStringValue(item.site_id) ?? toStringValue(item.siteId),
    siteKey: toStringValue(item.site_key) ?? toStringValue(item.siteKey),
    jobType: toStringValue(item.job_type) ?? toStringValue(item.jobType) ?? "unknown",
    status: (toStringValue(item.status) ?? "unknown") as GatewayJobRecord["status"],
    startedAt: toStringValue(item.started_at) ?? toStringValue(item.startedAt),
    finishedAt: toStringValue(item.finished_at) ?? toStringValue(item.finishedAt),
    errorMessage: toStringValue(item.error_message) ?? toStringValue(item.errorMessage),
  };
}

export async function listGatewayNodes(): Promise<GatewayNodeRecord[]> {
  const response = await requestJson<Record<string, unknown>[] | { items?: Record<string, unknown>[] }>(
    "/api/h5-gateway/nodes",
  );
  const items = Array.isArray(response) ? response : response.items ?? [];
  return items.map(mapNodeRecord);
}

export async function listGatewayJobs(): Promise<GatewayJobRecord[]> {
  const response = await requestJson<Record<string, unknown>[] | { items?: Record<string, unknown>[] }>(
    "/api/h5-gateway/jobs",
  );
  const items = Array.isArray(response) ? response : response.items ?? [];
  return items.map(mapJobRecord);
}

export async function getGatewayHealthSummary(): Promise<GatewayHealthSummary> {
  const summary = await requestJson<Record<string, unknown>>("/api/h5-gateway/health/summary");
  return {
    totalNodes: toNumberValue(summary.total_nodes ?? summary.totalNodes),
    onlineNodes: toNumberValue(summary.online_nodes ?? summary.onlineNodes),
    degradedNodes: toNumberValue(summary.degraded_nodes ?? summary.degradedNodes),
    offlineNodes: toNumberValue(summary.offline_nodes ?? summary.offlineNodes),
    runningJobs: toNumberValue(summary.running_jobs ?? summary.runningJobs),
    failedJobs: toNumberValue(summary.failed_jobs ?? summary.failedJobs),
  };
}

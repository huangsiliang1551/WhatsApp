import { api } from "./api";

// ── Types ──

export interface ClientErrorReport {
  error_type: "javascript" | "resource" | "promise";
  message: string;
  stack_trace?: string;
  url?: string;
}

export interface ClientErrorEntry {
  id: string;
  site_key: string | null;
  error_type: string;
  message: string;
  stack_trace: string | null;
  url: string | null;
  user_agent: string | null;
  created_at: string;
}

// ── API ──

export async function reportClientError(data: ClientErrorReport): Promise<void> {
  await api.post("/api/client-errors", data);
}

export async function listClientErrors(params?: {
  page?: number;
  size?: number;
  error_type?: string;
}): Promise<{ items: ClientErrorEntry[]; total: number }> {
  const res = await api.get<{ items: ClientErrorEntry[]; total: number }>("/api/admin/client-errors", {
    params,
  });
  return res.data;
}

export async function getClientErrorDetail(id: string): Promise<ClientErrorEntry> {
  const res = await api.get<ClientErrorEntry>(`/api/admin/client-errors/${encodeURIComponent(id)}`);
  return res.data;
}

// ── Secret Management ──

export interface SecretEntry {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at?: string;
}

export async function listSecrets(): Promise<SecretEntry[]> {
  const res = await api.get<SecretEntry[]>("/api/admin/secrets");
  return res.data;
}

export async function createSecret(data: {
  name: string;
  value: string;
  description?: string;
}): Promise<SecretEntry> {
  const res = await api.post<SecretEntry>("/api/admin/secrets", data);
  return res.data;
}

export async function updateSecret(id: string, data: {
  value?: string;
  description?: string;
}): Promise<SecretEntry> {
  const res = await api.put<SecretEntry>(`/api/admin/secrets/${encodeURIComponent(id)}`, data);
  return res.data;
}

export async function deleteSecret(id: string): Promise<void> {
  await api.delete(`/api/admin/secrets/${encodeURIComponent(id)}`);
}

export async function getSecretValue(id: string): Promise<{ value: string }> {
  const res = await api.get<{ value: string }>(`/api/admin/secrets/${encodeURIComponent(id)}/value`);
  return res.data;
}

// ── IP Blacklist ──

export interface IPBlacklistEntry {
  id: string;
  ip_address: string;
  reason: string | null;
  blocked_until: string | null;
  created_by: string | null;
  created_at: string;
}

export async function listIPBlacklist(): Promise<IPBlacklistEntry[]> {
  const res = await api.get<IPBlacklistEntry[]>("/api/admin/ip-blacklist");
  return res.data;
}

export async function addToBlacklist(data: {
  ip_address: string;
  reason?: string;
  blocked_until?: string;
}): Promise<IPBlacklistEntry> {
  const res = await api.post<IPBlacklistEntry>("/api/admin/ip-blacklist", data);
  return res.data;
}

export async function removeFromBlacklist(id: string): Promise<void> {
  await api.delete(`/api/admin/ip-blacklist/${encodeURIComponent(id)}`);
}

// ── Uptime Monitoring ──

export interface UptimeCheckEntry {
  id: string;
  site_id: string;
  site_name?: string;
  status: "up" | "down" | "timeout";
  response_time_ms: number | null;
  status_code: number | null;
  error_message: string | null;
  created_at: string;
}

export async function listUptimeChecks(params?: {
  page?: number;
  size?: number;
  status?: string;
}): Promise<{ items: UptimeCheckEntry[]; total: number }> {
  const res = await api.get<{ items: UptimeCheckEntry[]; total: number }>("/api/admin/uptime-checks", {
    params,
  });
  return res.data;
}

// ── Global Error Tracker ──

let _initialized = false;

export function initErrorTracker(): void {
  if (_initialized) return;
  _initialized = true;

  window.addEventListener("error", (event) => {
    reportClientError({
      error_type: "javascript",
      message: event.message ?? "Unknown script error",
      stack_trace: (event.error as Error)?.stack,
      url: window.location.href,
    }).catch(() => {
      /* silent */
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    reportClientError({
      error_type: "promise",
      message: reason?.message ?? "Unhandled promise rejection",
      stack_trace: reason?.stack,
      url: window.location.href,
    }).catch(() => {
      /* silent */
    });
  });
}

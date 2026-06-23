import { getAccessControlSnapshot } from "./accessControl";
import {
  listAuditLogs,
  listMetaWebhookSubscriptions,
  listProviderStatusBuffer,
  listQueueStats,
  listRuntimeState,
  type AuditLogEntry,
  type MetaWebhookSubscriptionView,
  type ProviderStatusBufferEntry,
  type QueueJob,
  type RuntimeAccountState,
} from "./api";
import {
  mockEvidenceBundles,
  mockEvidenceExports,
  type EvidenceBundleRecord,
} from "../mocks/evidenceCenter";
import type {
  EvidenceBundlePayload,
  EvidenceBundleView,
  EvidenceCenterSnapshot,
  EvidenceCoverageItem,
  EvidenceExportJob,
  EvidenceIncidentItem,
  EvidenceSourceKind,
} from "../types/evidenceCenter";
import type { AccessPolicyItem } from "../types/accessControl";

const bundleStore = mockEvidenceBundles.map(cloneBundleRecord);
const exportStore = mockEvidenceExports.map(cloneExport);

function cloneBundleRecord(record: EvidenceBundleRecord): EvidenceBundleRecord {
  return {
    ...record,
    included_sources: [...record.included_sources],
  };
}

function cloneExport(job: EvidenceExportJob): EvidenceExportJob {
  return { ...job };
}

function filterByAccount<T extends { account_id: string | null }>(items: T[], accountId?: string): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

function getPayloadAccountId(job: QueueJob): string | null {
  const value = job.payload.account_id;
  return typeof value === "string" && value.trim() ? value : null;
}

function getAccountLabel(accountId: string | null, runtimeAccounts: RuntimeAccountState[]): string {
  if (!accountId) {
    return "全局";
  }
  const matched = runtimeAccounts.find((item) => item.account_id === accountId);
  return matched ? `${matched.display_name} (${accountId})` : accountId;
}

function countBundleEvents(
  includedSources: EvidenceSourceKind[],
  accountId: string | null,
  coverage: EvidenceCoverageItem
): number {
  return includedSources.reduce((sum, source) => {
    if (source === "audit") return sum + coverage.audit_count;
    if (source === "provider") return sum + coverage.provider_pending_count;
    if (source === "queue") return sum + coverage.failed_job_count;
    return sum + coverage.webhook_issue_count;
  }, 0);
}

function countBundleAnomalies(
  includedSources: EvidenceSourceKind[],
  coverage: EvidenceCoverageItem
): number {
  return includedSources.reduce((sum, source) => {
    if (source === "provider") return sum + coverage.provider_pending_count;
    if (source === "queue") return sum + coverage.failed_job_count;
    if (source === "webhook") return sum + coverage.webhook_issue_count;
    return sum;
  }, 0);
}

function findPolicy(accountId: string | null, policies: AccessPolicyItem[]): AccessPolicyItem | null {
  return (
    policies.find((item) => item.account_id && item.account_id === accountId) ??
    policies.find((item) => item.account_id === null) ??
    null
  );
}

function buildCoverage(
  runtimeAccounts: RuntimeAccountState[],
  auditLogs: AuditLogEntry[],
  providerItems: ProviderStatusBufferEntry[],
  subscriptions: MetaWebhookSubscriptionView[],
  failedJobs: QueueJob[],
  policies: AccessPolicyItem[],
  requestedAccountId?: string
): EvidenceCoverageItem[] {
  const accountIds = new Set<string | null>();
  runtimeAccounts.forEach((item) => accountIds.add(item.account_id));
  auditLogs.forEach((item) => accountIds.add(item.account_id));
  providerItems.forEach((item) => accountIds.add(item.account_id));
  subscriptions.forEach((item) => accountIds.add(item.account_id));
  failedJobs.forEach((item) => accountIds.add(getPayloadAccountId(item)));
  if (!accountIds.size) {
    accountIds.add(requestedAccountId ?? null);
  }

  return Array.from(accountIds)
    .filter((accountId) => (requestedAccountId ? accountId === requestedAccountId : true))
    .map((accountId) => {
      const auditCount = auditLogs.filter((item) => item.account_id === accountId).length;
      const providerPendingCount = providerItems.filter((item) => item.account_id === accountId).length;
      const webhookIssueCount = subscriptions.filter(
        (item) =>
          item.account_id === accountId &&
          item.webhook_runtime_status !== "healthy" &&
          item.webhook_runtime_status !== "pending"
      ).length;
      const failedJobCount = failedJobs.filter((item) => getPayloadAccountId(item) === accountId).length;
      const policy = findPolicy(accountId, policies);
      const exportEnabled = policy?.audit_export_enabled ?? true;
      const coverageResult: EvidenceCoverageItem["coverage_result"] =
        !exportEnabled || failedJobCount > 0
          ? "review"
          : providerPendingCount > 0 || webhookIssueCount > 0
            ? "warning"
            : "healthy";
      const coverageReason = !exportEnabled
        ? policy?.effective_reason ?? "Audit export disabled by policy"
        : failedJobCount > 0
          ? "Recent failed queue jobs require review"
          : providerPendingCount > 0
            ? "Pending provider events remain"
            : webhookIssueCount > 0
              ? "Webhook runtime anomalies remain"
              : "Evidence coverage is healthy";

      return {
        account_id: accountId,
        account_label: getAccountLabel(accountId, runtimeAccounts),
        audit_count: auditCount,
        provider_pending_count: providerPendingCount,
        webhook_issue_count: webhookIssueCount,
        failed_job_count: failedJobCount,
        export_enabled: exportEnabled,
        coverage_result: coverageResult,
        coverage_reason: coverageReason,
        source: "hybrid" as const,
      };
    })
    .sort((left, right) => left.account_label.localeCompare(right.account_label, "en"));
}

function mapBundle(record: EvidenceBundleRecord, coverage: EvidenceCoverageItem[]): EvidenceBundleView {
  const matchedCoverage =
    coverage.find((item) => item.account_id === record.account_id) ??
    coverage.find((item) => item.account_id === null) ?? {
      account_id: record.account_id,
      account_label: record.account_id ?? "Global",
      audit_count: 0,
      provider_pending_count: 0,
      webhook_issue_count: 0,
      failed_job_count: 0,
      export_enabled: true,
      coverage_result: "healthy",
      coverage_reason: "No coverage data",
      source: "hybrid" as const,
    };

  return {
    bundle_id: record.bundle_id,
    account_id: record.account_id,
    name: record.name,
    scope: record.scope,
    target_ref: record.target_ref,
    date_from: record.date_from,
    date_to: record.date_to,
    included_sources: [...record.included_sources],
    retention_days: record.retention_days,
    event_count: countBundleEvents(record.included_sources, record.account_id, matchedCoverage),
    anomaly_count: countBundleAnomalies(record.included_sources, matchedCoverage),
    export_enabled: matchedCoverage.export_enabled,
    status:
      !matchedCoverage.export_enabled && record.status === "ready"
        ? "review"
        : record.status,
    effective_reason: record.effective_reason,
    last_export_at: record.last_export_at,
    source: "hybrid",
  };
}

function buildIncidents(
  auditLogs: AuditLogEntry[],
  providerItems: ProviderStatusBufferEntry[],
  failedJobs: QueueJob[],
  requestedAccountId?: string
): EvidenceIncidentItem[] {
  const auditIncidents: EvidenceIncidentItem[] = auditLogs
    .filter((item) => /fail|error|replay|handover|security/i.test(item.action))
    .filter((item) => (requestedAccountId ? item.account_id === requestedAccountId : true))
    .slice(0, 4)
    .map((item) => ({
      incident_id: `audit:${item.id}`,
      account_id: item.account_id,
      source_kind: "audit",
      severity: /fail|error/i.test(item.action) ? "warning" : "info",
      title: item.action,
      summary: `${item.target_type} / ${item.target_id ?? "n/a"}`,
      occurred_at: item.created_at,
      target_page: "audit",
      system_log_id: `audit:${item.id}`,
      target_type: item.target_type,
      target_id: item.target_id,
      source: "api",
    }));

  const providerIncidents: EvidenceIncidentItem[] = providerItems
    .filter((item) => (requestedAccountId ? item.account_id === requestedAccountId : true))
    .slice(0, 4)
    .map((item) => ({
      incident_id: `provider:${item.id}`,
      account_id: item.account_id,
      source_kind: "provider",
      severity: item.error_code ? "critical" : "warning",
      title: `${item.provider_name} / ${item.external_status}`,
      summary: item.provider_message_id,
      occurred_at: item.occurred_at ?? item.last_seen_at,
      target_page: "provider_events",
      system_log_id: `provider:${item.id}`,
      provider_name: item.provider_name,
      provider_message_id: item.provider_message_id,
      source: "api",
    }));

  const queueIncidents: EvidenceIncidentItem[] = failedJobs
    .filter((item) => (requestedAccountId ? getPayloadAccountId(item) === requestedAccountId : true))
    .slice(0, 4)
    .map((item) => ({
      incident_id: `queue:${item.job_id}`,
      account_id: getPayloadAccountId(item),
      source_kind: "queue",
      severity: "critical",
      title: `${item.queue} failed`,
      summary: item.error ?? "Queue job failed",
      occurred_at: item.failed_at ?? item.updated_at,
      target_page: "system_logs",
      system_log_id: `queue:${item.job_id}`,
      source: "api",
    }));

  const webhookIncidents: EvidenceIncidentItem[] = providerItems
    .filter((item) => item.error_code)
    .filter((item) => (requestedAccountId ? item.account_id === requestedAccountId : true))
    .slice(0, 2)
    .map((item) => ({
      incident_id: `webhook:${item.id}`,
      account_id: item.account_id,
      source_kind: "webhook",
      severity: "critical",
      title: "Webhook anomaly",
      summary: item.error_code ?? item.external_status,
      occurred_at: item.occurred_at ?? item.last_seen_at,
      target_page: "provider_events",
      system_log_id: `provider:${item.id}`,
      provider_name: item.provider_name,
      provider_message_id: item.provider_message_id,
      source: "hybrid",
    }));

  return [...queueIncidents, ...providerIncidents, ...webhookIncidents, ...auditIncidents]
    .sort((left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at))
    .slice(0, 10);
}

export async function getEvidenceCenterSnapshot(accountId?: string): Promise<EvidenceCenterSnapshot> {
  const [runtimeResult, auditResult, providerResult, webhookResult, queueResult, accessResult] =
    await Promise.allSettled([
      listRuntimeState(),
      listAuditLogs({ account_id: accountId, limit: 120 }),
      listProviderStatusBuffer({ account_id: accountId, limit: 60 }),
      listMetaWebhookSubscriptions({ account_id: accountId }),
      listQueueStats(),
      getAccessControlSnapshot(accountId),
    ]);

  if (
    runtimeResult.status !== "fulfilled" &&
    auditResult.status !== "fulfilled" &&
    providerResult.status !== "fulfilled" &&
    webhookResult.status !== "fulfilled" &&
    queueResult.status !== "fulfilled"
  ) {
    throw new Error("Evidence center core sources unavailable");
  }

  const warnings: string[] = [];
  if (runtimeResult.status !== "fulfilled") warnings.push("Runtime accounts unavailable");
  if (auditResult.status !== "fulfilled") warnings.push("Audit logs unavailable");
  if (providerResult.status !== "fulfilled") warnings.push("Provider events unavailable");
  if (webhookResult.status !== "fulfilled") warnings.push("Webhook subscriptions unavailable");
  if (queueResult.status !== "fulfilled") warnings.push("Queue failures unavailable");
  if (accessResult.status !== "fulfilled") warnings.push("Access baseline unavailable");

  const runtimeAccounts = runtimeResult.status === "fulfilled" ? runtimeResult.value.accounts : [];
  const auditLogs = auditResult.status === "fulfilled" ? auditResult.value : [];
  const providerItems = providerResult.status === "fulfilled" ? providerResult.value.items : [];
  const subscriptions = webhookResult.status === "fulfilled" ? webhookResult.value : [];
  const failedJobs =
    queueResult.status === "fulfilled"
      ? queueResult.value.recent_failed_jobs.filter((item) =>
          accountId ? getPayloadAccountId(item) === accountId : true
        )
      : [];
  const policies = accessResult.status === "fulfilled" ? accessResult.value.policies : [];

  const coverage = buildCoverage(
    runtimeAccounts,
    auditLogs,
    providerItems,
    subscriptions,
    failedJobs,
    policies,
    accountId
  );
  const bundles = filterByAccount(bundleStore, accountId)
    .map((record) => mapBundle(record, coverage))
    .sort((left, right) => left.name.localeCompare(right.name, "en"));
  const bundleIds = new Set(bundles.map((item) => item.bundle_id));
  const exports = exportStore
    .filter((item) => bundleIds.has(item.bundle_id))
    .map(cloneExport)
    .sort((left, right) => Date.parse(right.requested_at) - Date.parse(left.requested_at));
  const incidents = buildIncidents(auditLogs, providerItems, failedJobs, accountId);

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    bundles,
    exports,
    coverage,
    incidents,
    warnings,
  };
}

export async function saveEvidenceBundle(
  payload: EvidenceBundlePayload
): Promise<EvidenceBundleRecord> {
  const normalizedAccountId = payload.account_id?.trim() || null;
  const nextRecord: EvidenceBundleRecord = {
    bundle_id: payload.bundle_id?.trim() || `evidence-bundle-${Date.now()}`,
    account_id: normalizedAccountId,
    name: payload.name.trim(),
    scope: payload.scope,
    target_ref: payload.target_ref?.trim() || null,
    date_from: payload.date_from,
    date_to: payload.date_to,
    included_sources: [...payload.included_sources],
    retention_days: payload.retention_days,
    status: payload.scope === "incident" ? "collecting" : "ready",
    effective_reason: payload.effective_reason.trim() || "Evidence bundle updated",
    last_export_at: null,
    source: "mock",
  };

  const targetIndex = bundleStore.findIndex((item) => item.bundle_id === nextRecord.bundle_id);
  if (targetIndex >= 0) {
    bundleStore[targetIndex] = nextRecord;
  } else {
    bundleStore.unshift(nextRecord);
  }

  return cloneBundleRecord(nextRecord);
}

export async function requestEvidenceExport(
  bundleId: string,
  fileFormat: EvidenceExportJob["file_format"]
): Promise<EvidenceExportJob> {
  const bundle = bundleStore.find((item) => item.bundle_id === bundleId);
  if (!bundle) {
    throw new Error("Evidence bundle not found");
  }

  const now = new Date().toISOString();
  bundle.last_export_at = now;

  const created: EvidenceExportJob = {
    export_id: `evidence-export-${Date.now()}`,
    bundle_id: bundle.bundle_id,
    account_id: bundle.account_id,
    file_format: fileFormat,
    status: "ready",
    requested_at: now,
    finished_at: now,
    file_name: `${bundle.name.toLowerCase().replace(/\s+/g, "-")}-${now.slice(0, 10)}.${fileFormat}`,
    item_count: bundle.included_sources.length * 12,
    warning_count: bundle.status === "review" ? 1 : 0,
    source: "mock",
  };
  exportStore.unshift(created);
  return cloneExport(created);
}

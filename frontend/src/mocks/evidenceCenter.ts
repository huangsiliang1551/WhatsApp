import type { EvidenceBundlePayload, EvidenceExportJob } from "../types/evidenceCenter";

export type EvidenceBundleRecord = Required<
  Pick<
    EvidenceBundlePayload,
    | "name"
    | "scope"
    | "date_from"
    | "date_to"
    | "included_sources"
    | "retention_days"
    | "effective_reason"
  >
> & {
  bundle_id: string;
  account_id: string | null;
  target_ref: string | null;
  status: "ready" | "collecting" | "review";
  last_export_at: string | null;
  source: "mock";
};

export const mockEvidenceBundles: EvidenceBundleRecord[] = [
  {
    bundle_id: "evidence-bundle-global-weekly",
    account_id: null,
    name: "Global Weekly Audit",
    scope: "system",
    target_ref: null,
    date_from: "2026-06-04",
    date_to: "2026-06-11",
    included_sources: ["audit", "provider", "queue", "webhook"],
    retention_days: 180,
    status: "review",
    effective_reason: "System-level weekly review bundle",
    last_export_at: "2026-06-11T09:20:00Z",
    source: "mock",
  },
  {
    bundle_id: "evidence-bundle-cn-account",
    account_id: "brand-demo-cn",
    name: "CN Account Evidence",
    scope: "account",
    target_ref: "brand-demo-cn",
    date_from: "2026-06-08",
    date_to: "2026-06-11",
    included_sources: ["audit", "provider", "webhook"],
    retention_days: 365,
    status: "ready",
    effective_reason: "CN account export ready",
    last_export_at: "2026-06-11T08:58:00Z",
    source: "mock",
  },
  {
    bundle_id: "evidence-bundle-es-incident",
    account_id: "brand-demo-es",
    name: "ES Incident Packet",
    scope: "incident",
    target_ref: "provider:signature_failed",
    date_from: "2026-06-10",
    date_to: "2026-06-11",
    included_sources: ["provider", "queue", "webhook"],
    retention_days: 90,
    status: "collecting",
    effective_reason: "ES webhook incident still collecting evidence",
    last_export_at: null,
    source: "mock",
  },
];

export const mockEvidenceExports: EvidenceExportJob[] = [
  {
    export_id: "evidence-export-1",
    bundle_id: "evidence-bundle-global-weekly",
    account_id: null,
    file_format: "zip",
    status: "ready",
    requested_at: "2026-06-11T09:18:00Z",
    finished_at: "2026-06-11T09:20:00Z",
    file_name: "global-weekly-audit-2026-06-11.zip",
    item_count: 84,
    warning_count: 2,
    source: "mock",
  },
  {
    export_id: "evidence-export-2",
    bundle_id: "evidence-bundle-cn-account",
    account_id: "brand-demo-cn",
    file_format: "json",
    status: "ready",
    requested_at: "2026-06-11T08:56:00Z",
    finished_at: "2026-06-11T08:58:00Z",
    file_name: "cn-account-evidence-2026-06-11.json",
    item_count: 37,
    warning_count: 0,
    source: "mock",
  },
  {
    export_id: "evidence-export-3",
    bundle_id: "evidence-bundle-es-incident",
    account_id: "brand-demo-es",
    file_format: "zip",
    status: "queued",
    requested_at: "2026-06-11T09:05:00Z",
    finished_at: null,
    file_name: "es-incident-packet-2026-06-11.zip",
    item_count: 0,
    warning_count: 1,
    source: "mock",
  },
];

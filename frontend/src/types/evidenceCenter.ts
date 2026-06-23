export type EvidenceSourceKind = "audit" | "provider" | "queue" | "webhook";

export type EvidenceBundleScope = "system" | "account" | "incident";

export type EvidenceBundleStatus = "ready" | "collecting" | "review";

export type EvidenceBundleView = {
  bundle_id: string;
  account_id: string | null;
  name: string;
  scope: EvidenceBundleScope;
  target_ref: string | null;
  date_from: string;
  date_to: string;
  included_sources: EvidenceSourceKind[];
  retention_days: number;
  event_count: number;
  anomaly_count: number;
  export_enabled: boolean;
  status: EvidenceBundleStatus;
  effective_reason: string;
  last_export_at: string | null;
  source: "hybrid";
};

export type EvidenceExportJob = {
  export_id: string;
  bundle_id: string;
  account_id: string | null;
  file_format: "zip" | "json";
  status: "queued" | "ready" | "failed";
  requested_at: string;
  finished_at: string | null;
  file_name: string;
  item_count: number;
  warning_count: number;
  source: "mock";
};

export type EvidenceCoverageItem = {
  account_id: string | null;
  account_label: string;
  audit_count: number;
  provider_pending_count: number;
  webhook_issue_count: number;
  failed_job_count: number;
  export_enabled: boolean;
  coverage_result: "healthy" | "warning" | "review";
  coverage_reason: string;
  source: "hybrid";
};

export type EvidenceIncidentItem = {
  incident_id: string;
  account_id: string | null;
  source_kind: EvidenceSourceKind;
  severity: "info" | "warning" | "critical";
  title: string;
  summary: string;
  occurred_at: string;
  target_page: "audit" | "provider_events" | "system_logs" | "monitoring";
  system_log_id?: string;
  target_type?: string | null;
  target_id?: string | null;
  provider_name?: string | null;
  provider_message_id?: string | null;
  source: "api" | "hybrid";
};

export type EvidenceBundlePayload = {
  bundle_id?: string;
  account_id?: string | null;
  name: string;
  scope: EvidenceBundleScope;
  target_ref?: string | null;
  date_from: string;
  date_to: string;
  included_sources: EvidenceSourceKind[];
  retention_days: number;
  effective_reason: string;
};

export type EvidenceCenterSnapshot = {
  generated_at: string;
  source: "hybrid";
  bundles: EvidenceBundleView[];
  exports: EvidenceExportJob[];
  coverage: EvidenceCoverageItem[];
  incidents: EvidenceIncidentItem[];
  warnings: string[];
};

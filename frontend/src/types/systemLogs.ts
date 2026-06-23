export type SystemLogSeverity = "info" | "warning" | "critical";

export type SystemLogSourceKind = "audit" | "provider" | "queue";

export type SystemLogEntry = {
  id: string;
  account_id: string | null;
  source_kind: SystemLogSourceKind;
  severity: SystemLogSeverity;
  title: string;
  summary: string;
  detail: string;
  occurred_at: string;
  source: "api";
  target_type?: string | null;
  target_id?: string | null;
  provider_name?: string | null;
  provider_message_id?: string | null;
};

export type SystemLogSnapshot = {
  generated_at: string;
  source: "api";
  audit_count: number;
  provider_pending_count: number;
  failed_job_count: number;
  critical_count: number;
  entries: SystemLogEntry[];
  warnings: string[];
};

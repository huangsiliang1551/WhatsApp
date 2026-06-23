import type {
  MetaWebhookRuntimeStatus,
  MetaWebhookVerificationStatus,
  RuntimeConfigSummary,
} from "../services/api";

export type SecurityAccountBindingStatus = "linked" | "limited" | "missing";
export type SecurityWebhookRuntimeState = MetaWebhookRuntimeStatus | "none";

export type SecurityPasswordPolicy = {
  min_length: number;
  require_uppercase: boolean;
  require_number: boolean;
  require_symbol: boolean;
  password_expiry_days: number;
  source: "mock" | "hybrid";
};

export type SecuritySsoProvider = {
  provider_id: string;
  account_id: string | null;
  provider_name: "google" | "microsoft" | "okta" | "custom_oidc";
  enabled: boolean;
  mapped_role_count: number;
  last_sync_at: string | null;
  effective_result: "enforced" | "partial" | "review";
  effective_reason: string;
  login_mode?: SecuritySessionPolicy["login_mode"];
  mfa_required?: boolean;
  member_count?: number;
  active_session_count?: number;
  account_binding_status?: SecurityAccountBindingStatus;
  account_binding_reason?: string;
  webhook_subscription_count?: number;
  webhook_signature_failure_count?: number;
  webhook_verification_status?: MetaWebhookVerificationStatus;
  webhook_last_verified_at?: string | null;
  webhook_last_verification_error?: string | null;
  webhook_runtime_status?: SecurityWebhookRuntimeState;
  webhook_last_event_received_at?: string | null;
  webhook_last_message_received_at?: string | null;
  webhook_last_signature_failed_at?: string | null;
  webhook_runtime_error?: string | null;
  webhook_delivery_state?: "ready" | "stale" | "silent" | "error" | "unverified";
  webhook_delivery_reason?: string;
  source: "mock" | "hybrid";
};

export type SecuritySessionPolicy = {
  account_id: string | null;
  login_mode: "password" | "sso" | "mixed" | "sso_first";
  mfa_required: boolean;
  session_timeout_minutes: number;
  max_parallel_sessions: number;
  suspicious_login_review: boolean;
  audit_retention_days: number;
  audit_export_enabled?: boolean;
  webhook_signature_enforced?: boolean;
  member_count?: number;
  active_session_count?: number;
  enabled_sso_provider_count?: number;
  webhook_subscription_count?: number;
  effective_result?: "enforced" | "partial" | "review";
  effective_reason?: string;
  source: "mock" | "hybrid";
};

export type SecurityPolicyUpdatePayload = {
  account_id?: string | null;
  login_mode: "password" | "sso" | "mixed" | "sso_first";
  mfa_required: boolean;
  session_timeout_minutes: number;
  max_parallel_sessions: number;
  suspicious_login_review: boolean;
  audit_retention_days: number;
};

export type SecuritySettingsSnapshot = {
  generated_at: string;
  source: "hybrid";
  config: Pick<RuntimeConfigSummary, "app_env" | "test_mode" | "console_language"> | null;
  password_policy: SecurityPasswordPolicy;
  session_policies: SecuritySessionPolicy[];
  sso_providers: SecuritySsoProvider[];
  summary: {
    member_count: number;
    active_session_count: number;
    linked_provider_count: number;
    review_policy_count: number;
    webhook_protected_policy_count: number;
    webhook_signature_failure_count: number;
  };
  warnings: string[];
};

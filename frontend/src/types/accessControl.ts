export type AccessLoginMode = "password" | "sso" | "mixed" | "sso_first";

export type AccessPolicyScope = "global" | "account";

export type AccessPolicyStatus = "enforced" | "partial" | "review";

export type AdminSessionStatus = "active" | "idle" | "revoked";

export type AccessPolicyItem = {
  policy_id: string;
  account_id: string | null;
  scope: AccessPolicyScope;
  login_mode: AccessLoginMode;
  mfa_required: boolean;
  session_timeout_minutes: number;
  ip_allowlist_enabled: boolean;
  audit_export_enabled: boolean;
  webhook_signature_enforced: boolean;
  effective_status: AccessPolicyStatus;
  effective_reason: string;
  updated_at: string;
  source: "hybrid" | "mock";
};

export type AdminSessionItem = {
  session_id: string;
  account_id: string | null;
  agent_id: string;
  display_name: string;
  role_name: string;
  login_mode: "password" | "sso";
  mfa_verified: boolean;
  ip_address: string;
  device_label: string;
  last_seen_at: string;
  status: AdminSessionStatus;
  source: "hybrid" | "mock";
};

export type AccessSecurityEvent = {
  event_id: string;
  account_id: string | null;
  title: string;
  summary: string;
  level: "info" | "warning" | "critical";
  occurred_at: string;
  source: "hybrid" | "mock";
};

export type AccessControlSnapshot = {
  generated_at: string;
  source: "hybrid" | "mock";
  global_settings: {
    login_mode: "mixed" | "sso_first";
    mfa_required: boolean;
    session_timeout_minutes: number;
    ip_allowlist_enabled: boolean;
    webhook_signature_enforced: boolean;
  };
  policies: AccessPolicyItem[];
  sessions: AdminSessionItem[];
  events: AccessSecurityEvent[];
};

export type AccessPolicyCreatePayload = {
  account_id?: string | null;
  login_mode: "password" | "sso" | "mixed";
  mfa_required: boolean;
  session_timeout_minutes: number;
  ip_allowlist_enabled: boolean;
  audit_export_enabled: boolean;
  webhook_signature_enforced: boolean;
  effective_reason: string;
};

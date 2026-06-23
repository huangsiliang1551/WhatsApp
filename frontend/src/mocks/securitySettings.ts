import type {
  SecurityPasswordPolicy,
  SecuritySessionPolicy,
  SecuritySsoProvider,
} from "../types/securitySettings";

export const mockPasswordPolicy: SecurityPasswordPolicy = {
  min_length: 10,
  require_uppercase: true,
  require_number: true,
  require_symbol: true,
  password_expiry_days: 90,
  source: "mock",
};

export const mockSessionPolicies: SecuritySessionPolicy[] = [
  {
    account_id: null,
    login_mode: "mixed",
    mfa_required: true,
    session_timeout_minutes: 480,
    max_parallel_sessions: 3,
    suspicious_login_review: true,
    audit_retention_days: 180,
    source: "mock",
  },
  {
    account_id: "brand-demo-cn",
    login_mode: "sso",
    mfa_required: true,
    session_timeout_minutes: 240,
    max_parallel_sessions: 2,
    suspicious_login_review: true,
    audit_retention_days: 365,
    source: "mock",
  },
  {
    account_id: "brand-demo-es",
    login_mode: "mixed",
    mfa_required: false,
    session_timeout_minutes: 360,
    max_parallel_sessions: 4,
    suspicious_login_review: false,
    audit_retention_days: 180,
    source: "mock",
  },
];

export const mockSsoProviders: SecuritySsoProvider[] = [
  {
    provider_id: "sso-google-global",
    account_id: null,
    provider_name: "google",
    enabled: true,
    mapped_role_count: 2,
    last_sync_at: "2026-06-11T09:12:00Z",
    effective_result: "partial",
    effective_reason: "平台管理员已启用，普通坐席未全量接入",
    source: "mock",
  },
  {
    provider_id: "sso-okta-cn",
    account_id: "brand-demo-cn",
    provider_name: "okta",
    enabled: true,
    mapped_role_count: 4,
    last_sync_at: "2026-06-11T08:55:00Z",
    effective_result: "enforced",
    effective_reason: "品牌 CN 已强制 SSO",
    source: "mock",
  },
  {
    provider_id: "sso-custom-es",
    account_id: "brand-demo-es",
    provider_name: "custom_oidc",
    enabled: false,
    mapped_role_count: 1,
    last_sync_at: null,
    effective_result: "review",
    effective_reason: "ES 账号仍在迁移旧登录方式",
    source: "mock",
  },
];

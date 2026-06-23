export type OrganizationProfile = {
  organization_id: string;
  display_name: string;
  owner_name: string;
  environment: string;
  provider_mode: "mock" | "production";
  default_language: string;
  data_region: string;
  seat_limit: number;
  seat_used: number;
  source: "hybrid";
};

export type OrganizationAccountScope = {
  account_id: string;
  display_name: string;
  is_active: boolean;
  ai_enabled: boolean;
  provider_type: string;
  meta_business_portfolio_id: string | null;
  primary_waba_id: string | null;
  site_count: number;
  member_count: number;
  active_member_count: number;
  waba_count: number;
  active_waba_count: number;
  phone_number_count: number;
  registered_phone_number_count: number;
  webhook_verification_status: string | null;
  webhook_runtime_status: string | null;
  ready_for_webhook_delivery: boolean;
  ready_for_outbound_messages: boolean;
  blocking_reasons: string[];
  primary_site_key: string | null;
  last_webhook_event_at: string | null;
  source: "api" | "mock";
};

export type OrganizationUnit = {
  unit_id: string;
  account_id: string | null;
  name: string;
  manager_name: string;
  member_count: number;
  account_scope: string[];
  status: "active" | "draft";
  source: "api" | "hybrid" | "mock";
};

export type OrganizationInviteDomain = {
  domain_id: string;
  account_id: string | null;
  domain: string;
  auto_join_role: string;
  sso_enforced: boolean;
  approval_mode: "auto" | "manual";
  verified: boolean;
  effective_result: "active" | "review";
  effective_reason: string;
  source: "api" | "hybrid" | "mock";
};

export type OrganizationApprovalChain = {
  chain_id: string;
  account_id: string | null;
  name: string;
  trigger_type: "member_invite" | "permission_change" | "critical_action";
  approvers: string[];
  sla_minutes: number;
  enabled: boolean;
  source: "api" | "hybrid" | "mock";
};

export type OrganizationCenterSnapshot = {
  generated_at: string;
  source: "hybrid";
  profile: OrganizationProfile;
  account_scopes: OrganizationAccountScope[];
  units: OrganizationUnit[];
  invite_domains: OrganizationInviteDomain[];
  approval_chains: OrganizationApprovalChain[];
  warnings: string[];
};

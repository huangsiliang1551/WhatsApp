import type { AccessLoginMode, AdminSessionStatus } from "./accessControl";
import type { RoleDefinition } from "./operations";
import type { SecuritySsoProvider } from "./securitySettings";

export type IdentityProviderStatus = "linked" | "limited" | "missing";

export type IdentitySyncResult = "active" | "review";

export type IdentityProviderView = {
  provider_id: string;
  account_id: string | null;
  provider_name: SecuritySsoProvider["provider_name"];
  enabled: boolean;
  login_mode: AccessLoginMode;
  mfa_required: boolean;
  mapped_role_count: number;
  mapped_member_count: number;
  directory_member_count: number;
  active_session_count: number;
  account_binding_status: IdentityProviderStatus;
  account_binding_reason: string;
  last_sync_at: string | null;
  effective_result: SecuritySsoProvider["effective_result"];
  effective_reason: string;
  source: "hybrid";
};

export type IdentityDomainBinding = {
  domain_id: string;
  provider_id: string;
  account_id: string | null;
  domain: string;
  auto_provision_enabled: boolean;
  jit_enabled: boolean;
  verified: boolean;
  effective_result: IdentitySyncResult;
  effective_reason: string;
  source: "mock";
};

export type IdentityRoleMapping = {
  mapping_id: string;
  provider_id: string;
  account_id: string | null;
  external_group: string;
  role_key: string;
  role_name: string;
  account_scope: string[];
  page_scope: string[];
  priority: number;
  mapped_member_count: number;
  effective_result: IdentitySyncResult;
  effective_reason: string;
  source: "hybrid";
};

export type IdentitySyncJob = {
  job_id: string;
  provider_id: string;
  account_id: string | null;
  status: "queued" | "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  imported_count: number;
  updated_count: number;
  error_count: number;
  summary: string;
  source: "mock";
};

export type IdentityMemberPreview = {
  provider_id: string;
  account_id: string | null;
  agent_id: string;
  display_name: string;
  role_labels: string[];
  access_result: "active" | "review" | "restricted";
  access_reason: string;
  source: "hybrid";
};

export type IdentitySessionPreview = {
  provider_id: string;
  account_id: string | null;
  session_id: string;
  display_name: string;
  role_name: string;
  status: AdminSessionStatus;
  login_mode: "password" | "sso";
  mfa_verified: boolean;
  last_seen_at: string;
  source: "hybrid" | "mock";
};

export type IdentityRoleMappingPayload = {
  provider_id: string;
  account_id?: string | null;
  external_group: string;
  role_key: string;
  account_scope: string[];
  page_scope: string[];
  priority: number;
  effective_reason: string;
};

export type IdentitySyncSnapshot = {
  generated_at: string;
  source: "hybrid";
  providers: IdentityProviderView[];
  roles: RoleDefinition[];
  domains: IdentityDomainBinding[];
  mappings: IdentityRoleMapping[];
  jobs: IdentitySyncJob[];
  members: IdentityMemberPreview[];
  sessions: IdentitySessionPreview[];
  warnings: string[];
};

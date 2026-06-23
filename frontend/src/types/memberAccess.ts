import type { AccessPolicyStatus, AdminSessionStatus } from "./accessControl";
import type { RoleDefinition } from "./operations";

export type MemberAccessResult = "active" | "review" | "restricted";

export type MemberAccessBindingView = {
  binding_id: string;
  agent_id: string;
  display_name: string;
  email: string | null;
  member_account_id: string | null;
  role_labels: string[];
  role_key: string | null;
  role_name: string | null;
  scope: "global" | "account";
  account_scope: string[];
  page_scope: string[];
  permission_count: number;
  assigned_open_conversations: number;
  assigned_total_conversations: number;
  session_status: AdminSessionStatus | "offline";
  session_login_mode: "password" | "sso" | "none";
  session_mfa_verified: boolean;
  access_policy_status: AccessPolicyStatus | "none";
  access_policy_reason: string;
  access_result: MemberAccessResult;
  access_result_reason: string;
  is_override: boolean;
  updated_at: string;
  source: "hybrid";
};

export type MemberAccessActivityItem = {
  activity_id: string;
  agent_id: string;
  account_id: string | null;
  title: string;
  summary: string;
  level: "info" | "warning";
  occurred_at: string;
  source: "mock";
};

export type MemberAccessBindingPatch = {
  agent_id: string;
  account_id?: string | null;
  role_key: string;
  scope: "global" | "account";
  account_scope: string[];
  page_scope: string[];
  access_reason: string;
};

export type MemberAccessSnapshot = {
  generated_at: string;
  source: "hybrid";
  account_ids: string[];
  roles: RoleDefinition[];
  bindings: MemberAccessBindingView[];
  activities: MemberAccessActivityItem[];
  warnings: string[];
};

import type { OperatorStatus } from "../stores/appStore";

export type MemberDirectoryItem = {
  account_id: string | null;
  agent_id: string;
  display_name: string;
  email: string | null;
  status: OperatorStatus;
  is_active: boolean;
  assigned_open_conversations: number;
  assigned_total_conversations: number;
  assigned_account_count: number;
  role_labels: string[];
  source: "api";
};

export type RolePermissionAction = "view" | "edit" | "assign" | "approve" | "export";

export type RolePermissionResource = {
  resource_key: string;
  label: string;
  group: "workspace" | "accounts" | "templates" | "customers" | "system";
  actions: Record<RolePermissionAction, boolean>;
};

export type RoleDefinition = {
  role_key: string;
  name: string;
  scope: "global" | "account";
  status: "active" | "draft";
  member_count: number;
  account_scope: string[];
  page_scope: string[];
  permissions: RolePermissionResource[];
  permission_origin?: "preset" | "derived" | "custom";
  permission_origin_role_key?: string | null;
  source: "api" | "hybrid" | "mock";
};

export type RoleDefinitionCreatePayload = {
  role_key: string;
  name: string;
  scope: "global" | "account";
  account_scope: string[];
};

export type CustomerConversationLink = {
  account_id: string;
  conversation_id: string;
  customer_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  status: string;
  management_mode: string;
  ai_enabled: boolean;
  effective_ai_enabled: boolean;
  ai_reason: string;
  assigned_agent_name: string | null;
  last_message_at: string | null;
  last_message_preview: string | null;
};

export type CustomerTicketLink = {
  id: string;
  account_id: string;
  category: string;
  status: string;
  priority: string;
  subject: string;
  updated_at: string;
};

export type CustomerProfileSummary = {
  id: string;
  account_id: string | null;
  public_user_id: string;
  display_name: string | null;
  registration_site_key: string | null;
  registration_site_domain: string | null;
  language_code: string;
  lifecycle_status: string;
  is_anonymous: boolean;
  has_whatsapp: boolean;
  is_invited_user: boolean;
  is_new_user: boolean;
  restrict_task_claim: boolean;
  last_active_at: string | null;
  registration_ip: string | null;
  registration_ips: string[];
  multi_ip: boolean;
  tag_keys: string[];
  identity_values: string[];
  relatedCustomerIds: string[];
  conversation_count: number;
  open_conversation_count: number;
  ticket_count: number;
  open_ticket_count: number;
};

export type CustomerProfileDetail = {
  profile: CustomerProfileSummary;
  identities: Array<{
    identity_type: string;
    identity_value: string;
    country_code: string | null;
    is_verified: boolean;
    is_primary: boolean;
  }>;
  tags: Array<{
    tag_key: string;
    name: string;
    color: string | null;
    source_type: string;
  }>;
  conversations: CustomerConversationLink[];
  tickets: CustomerTicketLink[];
};

export type AutomationRuleStatus = "active" | "paused" | "draft";

export type AutomationRuleScope = "global" | "account";

export type AutomationRuleCondition = {
  field: string;
  operator: string;
  value: string;
};

export type AutomationRuleAction = {
  action_type: string;
  summary: string;
};

export type AutomationRuleDefinition = {
  rule_id: string;
  account_id: string | null;
  name: string;
  scope: AutomationRuleScope;
  status: AutomationRuleStatus;
  priority: number;
  trigger_type: string;
  conditions: AutomationRuleCondition[];
  actions: AutomationRuleAction[];
  match_count_24h: number;
  updated_at: string;
  source: "mock";
};

export type AutomationRulePrototypePayload = {
  account_id?: string | null;
  name: string;
  scope: AutomationRuleScope;
  priority: number;
  trigger_type: string;
  condition_lines: string[];
  action_lines: string[];
};

export type AlertRuleSeverity = "critical" | "warning" | "info";

export type AlertRuleDefinition = {
  rule_id: string;
  account_id: string | null;
  name: string;
  severity: AlertRuleSeverity;
  status: "active" | "paused";
  target_scope: "system" | "account";
  condition_summary: string;
  notify_channels: string[];
  source: "mock";
};

export type AlertReplayPayload = {
  account_id: string;
  provider_name?: string;
  provider_message_id?: string;
  external_status?: string;
  waba_id?: string;
  phone_number_id?: string;
  limit?: number;
};

export type AlertCenterItem = {
  id: string;
  account_id: string | null;
  title: string;
  summary: string;
  severity: AlertRuleSeverity;
  category: "queue" | "provider" | "audit" | "runtime";
  source: "api" | "hybrid";
  status: string;
  occurred_at: string;
  action_label: string | null;
  replay_payload: AlertReplayPayload | null;
};

export type AlertCenterSnapshot = {
  account_id: string | null;
  generated_at: string;
  metrics_generated_at: string | null;
  service_health: "healthy" | "warning" | "critical";
  queue_backlog: number;
  failed_jobs: number;
  provider_pending: number;
  audit_event_count: number;
  runtime_alert_count: number;
  items: AlertCenterItem[];
};

export type ReportCenterKpi = {
  key: string;
  label: string;
  value: number | string;
  source: "api";
  detail: string;
};

export type ReportCenterDailyRow = {
  source_kind: "whatsapp" | "template";
  date: string;
  account_id: string;
  label: string;
  inbound_count?: number;
  outbound_count?: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  estimated_cost: number;
};

export type ReportTemplateOption = {
  template_id: string;
  account_id: string;
  name: string;
  language: string;
  status: string;
};

export type ReportTemplateAnalyticsView = {
  template_id: string;
  template_name: string;
  account_id: string;
  language: string;
  category: string;
  send_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  estimated_cost: number;
  failure_reasons: Array<{
    error_code: string;
    failed_count: number;
  }>;
};

export type ReportCenterSnapshot = {
  account_id: string | null;
  generated_at: string;
  kpis: ReportCenterKpi[];
  daily_rows: ReportCenterDailyRow[];
  template_options: ReportTemplateOption[];
  template_analytics: ReportTemplateAnalyticsView | null;
};

export type KnowledgeCategorySummary = {
  category: string;
  total_count: number;
  active_count: number;
  builtin_count: number;
  database_count: number;
};

export type KnowledgeEntrySummary = {
  account_id: string | null;
  article_id: string;
  route_name: string;
  category: string;
  title: string;
  source_language: string;
  is_active: boolean;
  source_type: string;
  keywords: string[];
};

export type ImportExportCenterSnapshot = {
  account_id: string | null;
  generated_at: string;
  total_entries: number;
  active_entries: number;
  builtin_entries: number;
  database_entries: number;
  categories: KnowledgeCategorySummary[];
  entries: KnowledgeEntrySummary[];
};

export type RiskProfileStatus = "allow" | "watchlist" | "blocklist";

export type RiskProfileItem = {
  id: string;
  account_id: string | null;
  target_type: "customer" | "phone" | "wa_id" | "keyword";
  target_value: string;
  display_name: string;
  status: RiskProfileStatus;
  reason: string;
  hit_count_7d: number;
  last_hit_at: string | null;
  source: "mock";
};

export type RiskCaseItem = {
  id: string;
  account_id: string | null;
  severity: "high" | "medium" | "low";
  category: "blacklist_hit" | "manual_review" | "keyword_risk";
  target_value: string;
  summary: string;
  status: "open" | "reviewing" | "closed";
  created_at: string;
  source: "mock" | "hybrid";
};

export type RiskProfileCreatePayload = {
  account_id?: string | null;
  target_type: RiskProfileItem["target_type"];
  target_value: string;
  display_name: string;
  status: RiskProfileStatus;
  reason: string;
};

export type RiskCenterSnapshot = {
  account_id: string | null;
  generated_at: string;
  profiles: RiskProfileItem[];
  cases: RiskCaseItem[];
};

export type OperationsBatchJobStatus = "draft" | "queued" | "running" | "completed";

export type OperationsBatchJob = {
  job_id: string;
  account_id: string | null;
  name: string;
  target_scope: string;
  status: OperationsBatchJobStatus;
  affected_count: number;
  updated_at: string;
  source: "mock";
};

export type OperationsTaskItem = {
  id: string;
  account_id: string | null;
  user_id: string;
  template_name: string;
  public_user_id: string;
  status: string;
  review_required: boolean;
  active_ticket_count: number;
  available_at: string;
  source: "api";
};

export type OperationsProviderBacklogItem = {
  id: string;
  account_id: string;
  provider_name: string;
  external_status: string;
  replay_state: string;
  provider_message_id: string;
  occurred_at: string | null;
  replay_payload: AlertReplayPayload;
  source: "api";
};

export type OperationsAuditItem = {
  id: string;
  account_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  created_at: string;
  source: "api";
};

export type OperationsCenterSnapshot = {
  account_id: string | null;
  generated_at: string;
  queued_jobs: number;
  processing_jobs: number;
  failed_jobs: number;
  provider_pending: number;
  tasks: OperationsTaskItem[];
  provider_backlog: OperationsProviderBacklogItem[];
  audit_items: OperationsAuditItem[];
  batch_jobs: OperationsBatchJob[];
};

export type OperationsBatchJobCreatePayload = {
  account_id?: string | null;
  name: string;
  target_scope: string;
  affected_count: number;
};

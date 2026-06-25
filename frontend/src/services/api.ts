import axios, { AxiosHeaders } from "axios";
import {
  findMockOrderDetail,
  findMockTrackingDetail,
  type EcommerceOrderDetail,
  type EcommerceOrderLookupResult,
  type EcommerceTrackingDetail,
  type EcommerceTrackingLookupResult,
  MOCK_ORDERS,
} from "./ecommerce";
import { useAppStore } from "../stores/appStore";
import { adminAuth } from "./adminAuth";

/** STUB-001: List ecommerce orders for an account */
export async function listEcommerceOrders(accountId: string): Promise<EcommerceOrderDetail[]> {
  try {
    const response = await api.get<EcommerceOrderDetail[]>(
      "/api/ecommerce/orders",
      { params: { account_id: accountId } }
    );
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) {
      return MOCK_ORDERS.filter(
        (o) => o.account_id.toLowerCase() === accountId.trim().toLowerCase()
      );
    }
    throw error;
  }
}

// 用于处理并发 refresh 的锁
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(callback: (token: string) => void): void {
  refreshSubscribers.push(callback);
}

function onTokenRefreshed(token: string): void {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

// ── Backup Types ──
export interface DbBackup {
  id: string;
  filename: string;
  file_path: string;
  file_size: number;
  backup_type: string;
  status: string;
  started_at: string;
  completed_at: string;
  error_message: string | null;
  created_by: string;
}

// ── Knowledge Types ──
export interface KnowledgeCategory {
  id: string;
  agency_id: string | null;
  name: string;
  description: string;
  sort_order: number;
  created_at: string;
}

export interface KnowledgeArticle {
  id: string;
  category_id: string;
  agency_id: string | null;
  title: string;
  content: string;
  keywords: string;
  is_published: boolean;
  view_count: number;
  created_at: string;
  updated_at: string;
}

// ── Customer Profile Types ──
export interface CustomerProfile {
  behavior: {
    sign_in_count: number;
    sign_in_streak: number;
    recharge_total: number;
    recharge_count: number;
    withdraw_total: number;
    conversation_count: number;
    last_active_at: string;
  };
  auto_tags: string[];
  manual_tags: string[];
}

export interface AutoTagRule {
  id: string;
  agency_id: string | null;
  name: string;
  condition_type: string;
  condition_operator: string;
  condition_value: number;
  tag_name: string;
  is_enabled: boolean;
  created_at: string;
}

// ── API Stats Types ──
export interface ApiStatsSummary {
  today_count: number;
  avg_ms: number;
  active_agencies: number;
  rate_limited: number;
}

export interface ApiStatsByAgency {
  agency_id: string;
  agency_name: string;
  count: number;
  avg_ms: number;
  peak_count: number;
}

export interface ApiStatsByEndpoint {
  endpoint: string;
  count: number;
  avg_ms: number;
}

// ── Rate Limit Types ──
export interface RateLimitRule {
  id: string;
  agency_id: string | null;
  agency_name?: string;
  endpoint_pattern: string;
  max_requests: number;
  window_seconds: number;
  ban_minutes: number;
  is_enabled: boolean;
  created_at: string;
}

export interface BannedIp {
  ip: string;
  banned_at: string;
  remaining_minutes: number;
}

// ── Email Config Types ──
export interface EmailConfig {
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  smtp_ssl: boolean;
  from_name: string;
  from_email: string;
}

// ── Health Check Types ──
export interface HealthCheckResult {
  check_type: string;
  target: string;
  status: string;
  response_time_ms: number;
  details: string;
  checked_at: string;
}

export interface HealthCheckSummary {
  db: string;
  redis: string;
  api: string;
  sites: string;
  ssl: string;
  last_check_at: string;
}

export type {
  EcommerceLookupSource,
  EcommerceMockExample,
  EcommerceOrderDetail,
  EcommerceOrderItem,
  EcommerceOrderLookupResult,
  EcommerceOrderShipment,
  EcommerceTrackingDetail,
  EcommerceTrackingEvent,
  EcommerceTrackingLookupResult,
} from "./ecommerce";

export { MOCK_ORDERS } from "./ecommerce";

export type ManagementMode = "ai_managed" | "human_managed" | "paused";
export type OperatorStatus = "online" | "busy" | "away" | "offline";

type ConversationSummaryCompatFields = {
  last_message_original_preview?: string | null;
  last_message_source_preview?: string | null;
  last_message_translated_preview?: string | null;
  last_message_display_preview?: string | null;
  last_message_console_preview?: string | null;
};

type ConversationMessageCompatFields = {
  source_text?: string | null;
  source_message_text?: string | null;
  customer_text?: string | null;
  translated_text?: string | null;
  display_text?: string | null;
  operator_text?: string | null;
  source_language_code?: string | null;
  source_language?: string | null;
  display_language_code?: string | null;
  translated_text_language_code?: string | null;
  operator_language_code?: string | null;
};

type RuntimeConfigCompatFields = {
  translation_enabled?: boolean;
  translation_assist_enabled?: boolean;
  translation_engine?: string | null;
  workspace_language?: string | null;
  operator_language?: string | null;
  inbound_translation_assist_enabled?: boolean;
  auto_translate_inbound?: boolean;
  auto_translate_inbound_to_operator?: boolean;
  outbound_translation_assist_enabled?: boolean;
  auto_translate_outbound_to_customer?: boolean;
};

export type ConversationSummary = ConversationSummaryCompatFields & {
  account_id: string;
  conversation_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  customer_id: string;
  customer_language: string;
  customer_language_source: string;
  status: string;
  management_mode: ManagementMode;
  ai_enabled: boolean;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  last_message_at: string | null;
  last_message_preview: string | null;
  latest_intent_name: string | null;
  latest_handover_recommended: boolean;
  latest_handover_reason: string | null;
  customer_lifecycle_status: string | null;
  is_sleeping: boolean;
  last_customer_message_at: string | null;
};

export type ConversationMessage = ConversationMessageCompatFields & {
  message_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  provider_message_id: string | null;
  provider_media_id: string | null;
  direction: "inbound" | "outbound";
  message_type: string;
  language_code: string | null;
  translated_language_code: string | null;
  original_text: string | null;
  translated_text: string | null;
  console_text: string | null;
  delivered_text?: string | null;
  translation_kind?: string | null;
  sender_id: string | null;
  recipient_id: string | null;
  ai_generated: boolean;
  created_at: string;
  payload: Record<string, unknown> | null;
  delivery_status?: string;
  delivery_status_updated_at?: string;
};

export type ConversationTimelineItem = {
  id: string;
  item_type: "audit" | "handover" | "message_event" | string;
  label: string;
  title: string;
  summary: string;
  actor_type: string | null;
  actor_id: string | null;
  created_at: string;
  payload: Record<string, unknown> | null;
};

export type MockInboundPayload = {
  account_id: string;
  conversation_id: string;
  user_id: string;
  text: string;
  mode: "echo" | "ai";
  language_hint?: string;
  phone_number_id?: string;
};

export type OutboundPayload = {
  text: string;
  agent_id?: string;
};

export type RuntimeAccountState = {
  account_id: string;
  display_name: string;
  provider_type: string;
  is_active: boolean;
  ai_enabled: boolean;
};

export type RuntimeConversationState = {
  account_id: string;
  conversation_id: string;
  phone_number_id: string | null;
  status: string;
  ai_enabled: boolean;
  management_mode: ManagementMode;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
};

export type AiBlockingReason = {
  scope: "global" | "account" | "conversation" | "management_mode" | "waba" | "phone_number";
  code: string;
  message: string;
};

export type ConversationAiStatus = {
  account_id: string;
  conversation_id: string;
  phone_number_id: string | null;
  global_ai_enabled: boolean;
  account_ai_enabled: boolean;
  conversation_ai_enabled: boolean;
  status: string;
  management_mode: ManagementMode;
  effective_ai_enabled: boolean;
  assigned_agent_id: string | null;
  blocking_reasons: AiBlockingReason[];
  primary_blocking_reason: AiBlockingReason | null;
};

export type RuntimeState = {
  global_ai_enabled: boolean;
  accounts: RuntimeAccountState[];
  conversations: RuntimeConversationState[];
};

export type RuntimeConfigSummary = RuntimeConfigCompatFields & {
  app_env: string;
  test_mode: boolean;
  messaging_provider: string;
  ai_provider: string;
  ai_model: string;
  ecommerce_provider: string;
  openai_configured: boolean;
  deepseek_configured: boolean;
  translation_provider: string;
  live_translation_enabled: boolean;
  console_language: string;
  auto_translate_to_console?: boolean;
  auto_translate_outbound?: boolean;
  auto_translate_on_human_handover: boolean;
  auto_translate_on_conversation_open: boolean;
  auto_translate_operator_outbound: boolean;
  queue_backend: string;
  queue_max_retries: number;
  queue_poll_timeout_seconds: number;
};

export type LaunchReadinessCheck = {
  key: string;
  category: "runtime" | "database" | "queue" | "ai" | "messaging" | "meta" | "monitoring" | "operations";
  status: "pass" | "warning" | "blocker";
  scope: "system" | "account";
  title: string;
  message: string;
  action_hint: string | null;
  account_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  metadata: Record<string, unknown>;
};

export type LaunchReadinessSummary = {
  checked_at: string;
  overall_status: "ready" | "needs_attention" | "blocked";
  scope: "system" | "account";
  account_id: string | null;
  blocker_count: number;
  warning_count: number;
  passed_count: number;
  active_account_count: number;
  meta_account_count: number;
  meta_ready_account_count: number;
  messaging_provider: string;
  ai_provider: string;
  queue_backend: string;
};

export type LaunchReadinessResponse = {
  summary: LaunchReadinessSummary;
  checks: LaunchReadinessCheck[];
};

export type LaunchReadinessQueryParams = {
  account_id?: string;
};

export type ProviderStatusBufferEntry = {
  id: string;
  account_id: string;
  provider_name: string;
  waba_id: string | null;
  phone_number_id: string | null;
  provider_message_id: string;
  external_status: string;
  recipient_id: string | null;
  occurred_at: string | null;
  error_code: string | null;
  payload: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  seen_count: number;
  replay_state: string;
  replayed_at: string | null;
  replayed_message_event_id: string | null;
  replay_error: string | null;
  pending_age_seconds: number;
};

export type ProviderStatusBufferListResponse = {
  items: ProviderStatusBufferEntry[];
  returned_count: number;
  pending_count: number;
  replayed_count: number;
};

export type ProviderStatusBufferListParams = {
  account_id?: string;
  provider_name?: string;
  provider_message_id?: string;
  external_status?: string;
  replay_state?: "pending" | "replayed";
  waba_id?: string;
  phone_number_id?: string;
  limit?: number;
};

export type ProviderStatusBufferReplayPayload = {
  account_id: string;
  provider_name?: string;
  provider_message_id?: string;
  external_status?: string;
  waba_id?: string;
  phone_number_id?: string;
  limit?: number;
};

export type ProviderStatusBufferReplayResponse = {
  account_id: string;
  provider_name: string | null;
  provider_message_id: string | null;
  external_status: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  checked_count: number;
  replayed_count: number;
  failed_count: number;
};

export type PlatformSite = {
  id: string;
  account_id: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  site_key: string;
  domain: string;
  brand_name: string;
  logo_url: string | null;
  default_language: string;
  status: string;
  metadata_json?: Record<string, unknown> | null;
  avg_response_time?: number;
  uptime_percent?: number;
  created_at: string;
  updated_at: string;
};

export type PlatformSiteCreatePayload = {
  account_id?: string;
  site_key: string;
  domain: string;
  brand_name: string;
  logo_url?: string;
  favicon_url?: string;
  default_language: string;
  status: string;
  template_id: string;
};

export type PlatformTag = {
  id: string;
  tag_key: string;
  name: string;
  description: string | null;
  color: string | null;
  source_type: string;
  rule_json?: Record<string, unknown> | null;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type PlatformTagCreatePayload = {
  tag_key: string;
  name: string;
  description?: string;
  color?: string;
  source_type: string;
  rule_json?: Record<string, unknown>;
  is_active: boolean;
};

export type PlatformUserIdentity = {
  identity_type: string;
  identity_value: string;
  country_code: string | null;
  is_verified: boolean;
  is_primary: boolean;
};

export type PlatformUserTag = {
  tag_key: string;
  name: string;
  description: string | null;
  color: string | null;
  source_type: string;
  is_active: boolean;
};

export type PlatformUser = {
  id: string;
  account_id: string | null;
  public_user_id: string;
  registration_site_id: string | null;
  registration_site_key: string | null;
  registration_site_domain: string | null;
  display_name: string | null;
  country_code: string | null;
  language_code: string;
  is_anonymous: boolean;
  lifecycle_status: string;
  has_phone: boolean;
  has_email: boolean;
  has_whatsapp: boolean;
  is_invited_user: boolean;
  is_new_user: boolean;
  restrict_task_claim: boolean;
  registration_invite_code: string | null;
  registration_ip: string | null;
  last_active_at: string | null;
  created_at: string;
  updated_at: string;
  identities: PlatformUserIdentity[];
  tags: PlatformUserTag[];
  /** Aggregated fields from CUS-001 backend enhancement */
  conversation_count?: number;
  open_conversation_count?: number;
  ticket_count?: number;
  wallet_balance?: number;
};

export interface PaginatedUserListResponse {
  items: PlatformUser[];
  total: number;
  page: number;
  size: number;
}

export interface PlatformUserListParams {
  page?: number;
  size?: number;
  search?: string;
  sort?: string;
  account_id?: string;
  lifecycle_status?: string;
  identity_type?: string;
  date_from?: string;
  date_to?: string;
};

export type PlatformUserCreatePayload = {
  account_id?: string;
  public_user_id: string;
  registration_site_id?: string;
  display_name?: string;
  country_code?: string;
  language_code: string;
  is_anonymous: boolean;
  lifecycle_status: string;
  restrict_task_claim: boolean;
  registration_invite_code?: string;
  registration_ip?: string;
  identities: Array<{
    identity_type: string;
    identity_value: string;
    country_code?: string;
    is_verified?: boolean;
    is_primary?: boolean;
  }>;
  tag_keys: string[];
};

export type AudienceRuleSet = {
  id: string;
  rule_key: string;
  name: string;
  scope_type: string;
  scope_id: string | null;
  status: string;
  description: string | null;
  rules_json: Record<string, unknown>;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AudienceRuleSetCreatePayload = {
  rule_key: string;
  name: string;
  scope_type: string;
  scope_id?: string;
  status: string;
  description?: string;
  rules_json: Record<string, unknown>;
};

export type TaskTemplate = {
  id: string;
  account_id: string | null;
  task_key: string;
  name: string;
  title: string;
  description: string | null;
  task_type: string;
  status: string;
  audience_rule_set_id: string | null;
  reward_amount: string | null;
  reward_points: number;
  claim_timeout_seconds: number;
  auto_review_enabled: boolean;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type MetaWebhookSubscriptionStatus =
  | "pending"
  | "mock_subscribed"
  | "remote_subscribed"
  | "remote_pending"
  | "subscribed";

export type MetaWebhookVerificationStatus =
  | "pending"
  | "verified"
  | "failed"
  | "unavailable";

export type MetaWebhookRuntimeStatus =
  | "pending"
  | "healthy"
  | "verification_pending"
  | "signature_failed"
  | "payload_invalid";

export type TaskTemplateCreatePayload = {
  account_id?: string;
  task_key: string;
  name: string;
  title: string;
  description?: string;
  task_type: string;
  status: string;
  audience_rule_set_id?: string;
  reward_amount?: string;
  reward_points: number;
  claim_timeout_seconds: number;
  auto_review_enabled: boolean;
  metadata_json?: Record<string, unknown>;
};

export type TaskInstance = {
  id: string;
  account_id: string | null;
  template_id: string;
  template_task_key: string;
  template_name: string;
  user_id: string;
  public_user_id: string;
  site_id: string | null;
  site_key: string | null;
  status: string;
  claim_timeout_seconds_snapshot: number;
  review_required: boolean;
  latest_submission_id?: string | null;
  active_ticket_count?: number;
  review_status_summary?: string | null;
  available_at: string;
  claimed_at: string | null;
  claim_deadline_at: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  completed_at: string | null;
  expired_at: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type TaskInstanceCreatePayload = {
  template_id: string;
  user_id: string;
  site_id?: string;
  account_id?: string;
  review_required: boolean;
  metadata_json?: Record<string, unknown>;
};

function pickString(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return null;
}

function pickBoolean(...values: Array<boolean | null | undefined>): boolean | undefined {
  for (const value of values) {
    if (typeof value === "boolean") {
      return value;
    }
  }
  return undefined;
}

function normalizeConversationSummary(summary: ConversationSummary): ConversationSummary {
  return {
    ...summary,
    last_message_original_preview: pickString(
      summary.last_message_original_preview,
      summary.last_message_source_preview
    ),
    last_message_translated_preview: pickString(
      summary.last_message_translated_preview,
      summary.last_message_display_preview,
      summary.last_message_console_preview
    ),
    customer_lifecycle_status: summary.customer_lifecycle_status ?? null,
  };
}

function normalizeConversationMessage(message: ConversationMessage): ConversationMessage {
  const originalText = pickString(
    message.original_text,
    message.source_text,
    message.source_message_text,
    message.customer_text,
    message.console_text
  );
  const assistText = pickString(
    message.translated_text,
    message.display_text,
    message.operator_text
  );

  return {
    ...message,
    original_text: originalText ?? assistText ?? null,
    translated_text: assistText ?? null,
    console_text: originalText ?? assistText ?? null,
    language_code: pickString(
      message.language_code,
      message.source_language_code,
      message.source_language
    ),
    translated_language_code: pickString(
      message.translated_language_code,
      message.display_language_code,
      message.translated_text_language_code,
      message.operator_language_code
    )
  };
}

function normalizeRuntimeConfigSummary(summary: RuntimeConfigSummary): RuntimeConfigSummary {
  return {
    ...summary,
    translation_provider:
      pickString(summary.translation_provider, summary.translation_engine) ?? "n/a",
    live_translation_enabled:
      pickBoolean(
        summary.live_translation_enabled,
        summary.translation_enabled,
        summary.translation_assist_enabled
      ) ?? false,
    console_language:
      pickString(summary.console_language, summary.workspace_language, summary.operator_language) ??
      "n/a",
    auto_translate_on_human_handover:
      pickBoolean(
        summary.auto_translate_on_human_handover,
        summary.inbound_translation_assist_enabled,
        summary.auto_translate_inbound,
        summary.auto_translate_inbound_to_operator
      ) ?? false,
    auto_translate_on_conversation_open:
      pickBoolean(summary.auto_translate_on_conversation_open) ?? false,
    auto_translate_operator_outbound:
      pickBoolean(
        summary.auto_translate_operator_outbound,
        summary.outbound_translation_assist_enabled,
        summary.auto_translate_outbound_to_customer
      ) ?? false
  };
}

function normalizeMetricsSummary(summary: MetricsSummaryResponse): MetricsSummaryResponse {
  return {
    ...summary,
    translation: {
      ...summary.translation,
      conversation_view_translated_total:
        summary.translation.conversation_view_translated_total ??
        summary.translation.console_translated_total ??
        0,
      conversation_view_fallback_total:
        summary.translation.conversation_view_fallback_total ??
        summary.translation.console_fallback_total ??
        0,
      conversation_view_skipped_total:
        summary.translation.conversation_view_skipped_total ??
        summary.translation.console_skipped_total ??
        0,
      outbound_operator_translated_total:
        summary.translation.outbound_operator_translated_total ??
        summary.translation.customer_translated_total ??
        0,
      outbound_operator_fallback_total:
        summary.translation.outbound_operator_fallback_total ??
        summary.translation.customer_fallback_total ??
        0,
      outbound_operator_skipped_total:
        summary.translation.outbound_operator_skipped_total ??
        summary.translation.customer_skipped_total ??
        0
    }
  };
}

export function getConversationPrimaryPreview(summary: ConversationSummary): string | null {
  return pickString(summary.last_message_original_preview, summary.last_message_preview);
}

export function getConversationTranslationPreview(summary: ConversationSummary): string | null {
  const primaryPreview = getConversationPrimaryPreview(summary);
  const translatedPreview = pickString(
    summary.last_message_translated_preview,
    summary.last_message_preview
  );

  if (!translatedPreview || translatedPreview === primaryPreview) {
    return null;
  }
  return translatedPreview;
}

export function getMessagePrimaryText(message: ConversationMessage): string | null {
  return pickString(message.original_text, message.console_text);
}

export function getMessageTranslationAssistText(message: ConversationMessage): string | null {
  const primaryText = getMessagePrimaryText(message);
  const assistText = pickString(message.translated_text);

  if (!assistText || assistText === primaryText) {
    return null;
  }
  return assistText;
}

export function getMessageSourceLanguageCode(message: ConversationMessage): string | null {
  return pickString(message.language_code);
}

export function getMessageAssistLanguageCode(message: ConversationMessage): string | null {
  if (!getMessageTranslationAssistText(message)) {
    return null;
  }
  return pickString(message.translated_language_code);
}

export type AuditLogEntry = {
  id: string;
  account_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type AuditLogListParams = {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  actor_type?: string;
  actor_id?: string;
  action?: string;
  target_type?: string;
  target_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
};

export type SupportKnowledgeEntryView = {
  account_id: string | null;
  article_id: string;
  route_name: string;
  category: string;
  title: string;
  answer: string;
  source_language: string;
  keywords: string[];
  minimum_score: number;
  priority: number;
  is_active: boolean;
  source_type: string;
};

export type SupportKnowledgeEntryCreatePayload = {
  account_id: string;
  article_id: string;
  route_name: string;
  category: string;
  title: string;
  answer: string;
  source_language: string;
  keywords: string[];
  minimum_score: number;
  priority: number;
  is_active: boolean;
};

export type SupportKnowledgeEntryUpdatePayload = {
  route_name?: string;
  category?: string;
  title?: string;
  answer?: string;
  source_language?: string;
  keywords?: string[];
  minimum_score?: number;
  priority?: number;
  is_active?: boolean;
};

export type SupportKnowledgeDeleteResponse = {
  account_id: string;
  article_id: string;
  deleted: boolean;
};

export type SupportKnowledgeExportBundle = {
  version: string;
  exported_at: string;
  total_entries: number;
  entries: SupportKnowledgeEntryCreatePayload[];
};

export type SupportKnowledgeImportPayload = {
  target_account_id?: string;
  upsert_existing: boolean;
  entries: SupportKnowledgeEntryCreatePayload[];
};

export type SupportKnowledgeImportItemResult = {
  account_id: string;
  article_id: string;
  route_name: string;
  status: string;
  detail: string;
};

export type SupportKnowledgeImportResult = {
  created_count: number;
  updated_count: number;
  skipped_count: number;
  items: SupportKnowledgeImportItemResult[];
};

export type QueueName = "ai_generation";
export type QueueJobStatus = "queued" | "processing" | "completed" | "failed";

export type QueueJob = {
  job_id: string;
  queue: QueueName;
  status: QueueJobStatus;
  payload: Record<string, unknown>;
  attempt_count: number;
  retry_count: number;
  max_retries: number;
  created_at: string;
  updated_at: string;
  last_attempt_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  error_history: string[];
};

export type QueueStatsItem = {
  queue: QueueName;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  retried_total: number;
};

export type QueueStatsResponse = {
  queues: QueueStatsItem[];
  recent_failed_jobs: QueueJob[];
};

export type MetricsAiSummary = {
  queued_total: number;
  success_total: number;
  routed_total: number;
  fallback_total: number;
  disabled_total: number;
  skipped_handover_total: number;
};

export type MetricsTemplateSummary = {
  sent_total: number;
  delivered_total: number;
  read_total: number;
  failed_total: number;
  failure_event_total: number;
};

export type MetricsTranslationSummary = {
  console_translated_total?: number;
  console_fallback_total?: number;
  console_skipped_total?: number;
  customer_translated_total?: number;
  customer_fallback_total?: number;
  customer_skipped_total?: number;
  conversation_view_translated_total: number;
  conversation_view_fallback_total: number;
  conversation_view_skipped_total: number;
  outbound_operator_translated_total: number;
  outbound_operator_fallback_total: number;
  outbound_operator_skipped_total: number;
};

export type MetricsWebhookSummary = {
  message_total: number;
  status_update_total: number;
  signature_failure_total: number;
  delivered_event_total: number;
  read_event_total: number;
  failed_event_total: number;
};

export type MetricsQueueSummary = {
  queued_total: number;
  completed_total: number;
  retried_total: number;
  failed_total: number;
  queued_current: number;
  processing_current: number;
  completed_current: number;
  failed_current: number;
};

export type MetricsInboundSummary = {
  mock_total: number;
  whatsapp_webhook_total: number;
  accepted_total: number;
  duplicate_total: number;
  skipped_total: number;
};

export type MetricsOutboundSummary = {
  accepted_total: number;
  failed_total: number;
  echo_total: number;
  manual_operator_total: number;
  ai_auto_reply_total: number;
  template_send_total: number;
};

export type MetricsProcessingFailureSummary = {
  mock_inbound_total: number;
  webhook_inbound_total: number;
  webhook_signature_total: number;
  manual_operator_total: number;
  ai_auto_reply_total: number;
  template_send_total: number;
};

export type MetricsSummaryResponse = {
  generated_at: string;
  inbound: MetricsInboundSummary;
  outbound: MetricsOutboundSummary;
  ai: MetricsAiSummary;
  templates: MetricsTemplateSummary;
  translation: MetricsTranslationSummary;
  webhook: MetricsWebhookSummary;
  queue: MetricsQueueSummary;
  processing_failures: MetricsProcessingFailureSummary;
};

export type WhatsAppStatsSummary = {
  conversation_count: number;
  unique_customer_count: number;
  inbound_message_count: number;
  outbound_message_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  billable_count: number;
  estimated_cost: number;
  estimated_cost_status: string;
  estimated_cost_note: string | null;
};

export type WhatsAppStatsDailyRow = {
  date: string;
  hour_bucket: number | null;
  account_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  conversation_origin_type: string | null;
  conversation_category: string | null;
  pricing_model: string | null;
  billable: boolean;
  conversation_count: number;
  unique_customer_count: number;
  inbound_message_count: number;
  outbound_message_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  billable_count: number;
  estimated_cost: number;
  estimated_cost_status: string;
  estimated_cost_note: string | null;
};

export type WhatsAppStatsDetailResponse = {
  summary: WhatsAppStatsSummary;
  daily_rows: WhatsAppStatsDailyRow[];
  generated_at: string | null;
};

export type WhatsAppStatsRebuildResponse = {
  account_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  date_from: string | null;
  date_to: string | null;
  rebuilt_at: string;
};

export type WhatsAppStatsQueryParams = {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  conversation_origin_type?: string;
  conversation_category?: string;
  pricing_model?: string;
  billable?: boolean;
  hour_bucket?: number;
  date_from?: string;
  date_to?: string;
};

export type RuntimeAgent = {
  account_id: string | null;
  agent_id: string;
  display_name: string;
  email: string | null;
  status: OperatorStatus;
  is_active: boolean;
};

export type AgentWorkload = RuntimeAgent & {
  assigned_open_conversations: number;
  assigned_total_conversations: number;
  assigned_account_count: number;
};

export type MetaPhoneNumber = {
  phone_number_id: string;
  display_phone_number: string;
  verified_name: string | null;
  quality_rating: "GREEN" | "YELLOW" | "RED" | "UNKNOWN";
  is_registered: boolean;
  is_active: boolean;
};

export type MetaPhoneNumberScopeView = {
  account_id: string;
  account_display_name: string;
  account_is_active: boolean;
  waba_id: string;
  phone_number_id: string;
  display_phone_number: string;
  verified_name: string | null;
  quality_rating: "GREEN" | "YELLOW" | "RED" | "UNKNOWN";
  is_registered: boolean;
  is_active: boolean;
  webhook_subscribed: boolean;
  webhook_subscription_status?: string | null;
  ready_for_webhook_delivery: boolean;
  ready_for_outbound_messages: boolean;
  ready_for_meta_activation: boolean;
  blocking_reasons: string[];
};

export type MetaWabaAccount = {
  account_id: string;
  display_name: string;
  account_is_active: boolean;
  notes: string | null;
  onboarding_mode: "manual" | "embedded_signup";
  meta_business_portfolio_id: string;
  waba_id: string;
  token_source: "system_user" | "user_access_token" | "embedded_signup";
  is_active: boolean;
  webhook_subscribed: boolean;
  webhook_subscription_status?: MetaWebhookSubscriptionStatus | null;
  webhook_callback_url: string | null;
  webhook_verify_path: string;
  webhook_root_verify_path: string;
  webhook_receive_path: string;
  webhook_root_receive_path: string;
  webhook_verification_status: MetaWebhookVerificationStatus;
  webhook_last_verified_at: string | null;
  webhook_last_verification_error: string | null;
  webhook_runtime_status: MetaWebhookRuntimeStatus;
  webhook_last_event_received_at: string | null;
  webhook_last_message_received_at: string | null;
  webhook_last_status_update_at: string | null;
  webhook_last_signature_failed_at: string | null;
  webhook_signature_failure_count: number;
  webhook_runtime_error: string | null;
  has_access_token: boolean;
  has_verify_token: boolean;
  has_app_secret: boolean;
  phone_number_count: number;
  registered_phone_number_count: number;
  ready_for_webhook_verification: boolean;
  ready_for_webhook_delivery: boolean;
  ready_for_outbound_messages: boolean;
  ready_for_meta_activation: boolean;
  ready_for_formal_activation: boolean;
  has_root_webhook_routing_conflict: boolean;
  blocking_reasons: string[];
  phone_numbers: MetaPhoneNumber[];
};

export type EmbeddedSignupSession = {
  session_id: string;
  account_id: string;
  display_name: string;
  redirect_uri: string;
  provider_name: string;
  status: "created" | "completed" | "failed";
  completion_stage:
    | "pending_callback"
    | "callback_recorded"
    | "remote_confirmed"
    | "local_waba_linked"
    | "webhook_verification_pending"
    | "failed";
  event_source: "operator" | "provider_callback" | "system_sync";
  remote_confirmed: boolean;
  waba_id: string | null;
  linked_waba_id?: string | null;
  provider_waba_id: string | null;
  meta_business_portfolio_id: string | null;
  setup_session_id: string | null;
  linked_phone_number_ids: string[];
  authorization_code_present: boolean;
  system_user_access_token_present: boolean;
  launch_context?: {
    session_id: string;
    state: string;
    callback_url: string;
    redirect_uri: string;
    expires_at: string;
    parameters: Record<string, unknown>;
  } | null;
  callback_received_at: string | null;
  completed_at: string | null;
  completion_message: string | null;
  error_message: string | null;
  webhook_callback_url?: string | null;
  webhook_verify_token_present?: boolean;
  webhook_app_id?: string | null;
  webhook_subscription_status?: MetaWebhookSubscriptionStatus | null;
  webhook_verification_status?: MetaWebhookVerificationStatus | null;
  webhook_runtime_status?: MetaWebhookRuntimeStatus | null;
  ready_for_webhook_delivery?: boolean;
  ready_for_outbound_messages?: boolean;
  ready_for_meta_activation?: boolean;
  webhook_blocking_reasons?: string[];
  completion_webhook_subscription_status?: MetaWebhookSubscriptionStatus | null;
  completion_webhook_verification_status?: MetaWebhookVerificationStatus | null;
  completion_webhook_runtime_status?: MetaWebhookRuntimeStatus | null;
  completion_ready_for_webhook_delivery?: boolean | null;
  completion_ready_for_outbound_messages?: boolean | null;
  completion_ready_for_meta_activation?: boolean | null;
  completion_webhook_blocking_reasons?: string[];
  session_snapshot?: {
    waba_id?: string | null;
    meta_business_portfolio_id?: string | null;
    linked_phone_number_ids: string[];
    webhook_callback_url?: string | null;
    webhook_verify_token_present: boolean;
    webhook_app_id?: string | null;
    webhook_subscription_status?: MetaWebhookSubscriptionStatus | null;
    webhook_verification_status?: MetaWebhookVerificationStatus | null;
    webhook_runtime_status?: MetaWebhookRuntimeStatus | null;
    ready_for_webhook_delivery?: boolean | null;
    ready_for_outbound_messages?: boolean | null;
    ready_for_meta_activation?: boolean | null;
    webhook_blocking_reasons: string[];
  } | null;
  current_waba_state?: {
    waba_id?: string | null;
    meta_business_portfolio_id?: string | null;
    webhook_callback_url?: string | null;
    webhook_verify_token_present: boolean;
    webhook_app_id?: string | null;
    webhook_subscription_status?: MetaWebhookSubscriptionStatus | null;
    webhook_verification_status?: MetaWebhookVerificationStatus | null;
    webhook_runtime_status?: MetaWebhookRuntimeStatus | null;
    ready_for_webhook_delivery: boolean;
    ready_for_outbound_messages: boolean;
    ready_for_meta_activation: boolean;
    webhook_blocking_reasons: string[];
  } | null;
};

export type ManualMetaAccountPayload = {
  account_id?: string;
  display_name: string;
  meta_business_portfolio_id: string;
  waba_id: string;
  access_token: string;
  token_source: "system_user" | "user_access_token";
  app_secret?: string;
  notes?: string;
  phone_numbers: MetaPhoneNumber[];
};

export type MetaAccountUpdatePayload = {
  display_name: string;
  meta_business_portfolio_id: string;
  access_token?: string;
  verify_token?: string;
  app_secret?: string;
  token_source?: "system_user" | "user_access_token" | "embedded_signup";
  notes?: string;
  phone_numbers: MetaPhoneNumber[];
};

export type MetaScopeStatusUpdatePayload = {
  is_active: boolean;
};

export type MetaAccountStatusUpdateResponse = {
  account_id: string;
  is_active: boolean;
  wabas: MetaWabaAccount[];
};

export type EmbeddedSignupWebhookSubscriptionPayload = {
  callback_url: string;
  verify_token?: string;
  app_id?: string;
};

export type EmbeddedSignupSessionPayload = {
  account_id: string;
  display_name: string;
  redirect_uri: string;
  webhook_subscription?: EmbeddedSignupWebhookSubscriptionPayload;
};

export type CompleteEmbeddedSignupSessionPayload = {
  waba_id?: string;
  meta_business_portfolio_id?: string;
  phone_number_ids?: string[];
  setup_session_id?: string;
  authorization_code?: string;
  system_user_access_token?: string;
  raw_payload?: Record<string, unknown>;
  event_source?: "operator" | "provider_callback" | "system_sync";
  webhook_subscription?: EmbeddedSignupWebhookSubscriptionPayload;
};

export type EmbeddedSignupCallbackPayload = {
  status: "completed" | "failed";
  state?: string;
  waba_id?: string;
  meta_business_portfolio_id?: string;
  phone_number_ids?: string[];
  setup_session_id?: string;
  authorization_code?: string;
  system_user_access_token?: string;
  error_message?: string;
  raw_payload?: Record<string, unknown>;
  event_source?: "provider_callback" | "system_sync";
  webhook_subscription?: EmbeddedSignupWebhookSubscriptionPayload;
};

export type FailEmbeddedSignupSessionPayload = {
  error_message: string;
  raw_payload?: Record<string, unknown>;
  event_source?: "operator" | "provider_callback" | "system_sync";
};

export type WebhookSubscriptionPayload = {
  callback_url: string;
  verify_token?: string;
  app_id?: string;
};

export type MetaWebhookSubscriptionView = {
  id: string;
  account_id: string;
  account_display_name: string;
  waba_id: string;
  callback_url: string;
  webhook_verify_path: string;
  webhook_root_verify_path: string;
  webhook_receive_path: string;
  verify_token_present: boolean;
  app_id: string | null;
  status: MetaWebhookSubscriptionStatus;
  subscribed_at: string | null;
  webhook_verification_status: MetaWebhookVerificationStatus;
  webhook_last_verified_at: string | null;
  webhook_last_verification_error: string | null;
  webhook_runtime_status: MetaWebhookRuntimeStatus;
  webhook_last_event_received_at: string | null;
  webhook_last_message_received_at: string | null;
  webhook_last_status_update_at: string | null;
  webhook_last_signature_failed_at: string | null;
  webhook_signature_failure_count: number;
  webhook_runtime_error: string | null;
  created_at: string;
  updated_at: string;
};

export type MetaPhoneNumberSyncResponse = {
  account_id: string;
  waba_id: string;
  provider_name: string;
  sync_mode: string;
  status: string;
  synced_count: number;
  phone_numbers: MetaPhoneNumber[];
  message: string | null;
};

export type TemplateCategory = "MARKETING" | "UTILITY" | "AUTHENTICATION";
export type TemplateStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "DRAFT"
  | "DISABLED"
  | "PAUSED";
export type TemplateSendStatus = "QUEUED" | "SENT" | "DELIVERED" | "READ" | "FAILED";

export type TemplateDraftPayload = {
  account_id: string;
  waba_id?: string;
  name: string;
  language: string;
  category: TemplateCategory;
  body_text: string;
  header_text?: string;
  header_media_asset_id?: string;
  header_media_handle?: string;
  footer_text?: string;
  sample_variables?: Record<string, string>;
};

export type TemplateDraftUpdatePayload = {
  waba_id?: string;
  name?: string;
  language?: string;
  category?: TemplateCategory;
  body_text?: string;
  header_text?: string;
  header_media_asset_id?: string;
  header_media_handle?: string;
  footer_text?: string;
  sample_variables?: Record<string, string>;
};

export type MessageTemplateView = {
  template_id: string;
  account_id: string;
  waba_id: string | null;
  name: string;
  language: string;
  category: TemplateCategory;
  status: TemplateStatus;
  meta_template_id: string | null;
  rejected_reason: string | null;
  body_text: string;
  header_text: string | null;
  header_media_asset_id: string | null;
  header_media_asset_name: string | null;
  header_media_asset_type: string | null;
  header_media_handle: string | null;
  footer_text: string | null;
  sample_variables: Record<string, string>;
  submitted_at: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TemplateSendLogView = {
  id: string;
  account_id: string;
  template_id: string | null;
  waba_id: string | null;
  template_name: string | null;
  template_language: string | null;
  template_category: TemplateCategory | null;
  template_code: string | null;
  header_media_asset_id: string | null;
  header_media_asset_name: string | null;
  header_media_asset_type: string | null;
  header_media_meta_media_id: string | null;
  header_media_sync_status: string | null;
  conversation_id: string | null;
  external_conversation_id: string | null;
  internal_conversation_id: string | null;
  phone_number_id: string | null;
  wa_id: string;
  message_id: string | null;
  idempotency_key: string | null;
  status: TemplateSendStatus;
  error_code: string | null;
  conversation_origin_type: string | null;
  conversation_category: string | null;
  pricing_model: string | null;
  billable: boolean;
  estimated_cost: number;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
  last_status_at: string | null;
  created_at: string;
};

export type TemplateStatsSummary = {
  send_count: number;
  delivered_count: number;
  delivery_rate: number;
  read_count: number;
  read_rate: number;
  read_rate_by_send: number;
  failed_count: number;
  billable_count: number;
  estimated_cost: number;
  estimated_cost_status: string;
  estimated_cost_note: string | null;
};

export type TemplateStatsDailyRow = {
  date: string;
  account_id: string;
  template_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  template_name: string;
  template_code: string | null;
  template_category: TemplateCategory;
  template_language: string;
  send_count: number;
  delivered_count: number;
  delivery_rate: number;
  read_count: number;
  read_rate: number;
  read_rate_by_send: number;
  failed_count: number;
  billable_count: number;
  estimated_cost: number;
  estimated_cost_status: string;
  estimated_cost_note: string | null;
};

export type TemplateStatsFailureReason = {
  error_code: string;
  failed_count: number;
};

export type TemplateStatsHourlyRow = {
  hour_bucket: number;
  send_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
};

export type TemplateStatsDetailResponse = {
  template_id: string;
  template_name: string;
  account_id: string;
  template_language: string;
  template_category: TemplateCategory;
  summary: TemplateStatsSummary;
  daily_rows: TemplateStatsDailyRow[];
  hourly_rows: TemplateStatsHourlyRow[];
  failure_reasons: TemplateStatsFailureReason[];
};

export type TemplateStatsRebuildResponse = {
  account_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  date_from: string | null;
  date_to: string | null;
  rebuilt_at: string;
};

export type TemplateStatusUpdatePayload = {
  status: TemplateStatus;
  rejected_reason?: string;
  meta_template_id?: string;
};

export type TemplateSendPayload = {
  account_id: string;
  conversation_id: string;
  phone_number_id?: string;
  variables?: Record<string, string>;
  agent_id?: string;
  idempotency_key?: string;
};

export type TemplateSendResponse = {
  template_id: string;
  account_id: string;
  conversation_id: string;
  external_conversation_id: string;
  internal_conversation_id: string;
  phone_number_id: string | null;
  status: TemplateSendStatus;
  delivered_text: string;
  template_language: string;
  header_media_asset_id: string | null;
  header_media_asset_name: string | null;
  header_media_asset_type: string | null;
  header_media_meta_media_id: string | null;
  header_media_sync_status: string | null;
  message_id: string | null;
  send_log_id: string;
  provider?: string | null;
};

export type TemplateSubmitResponse = {
  provider: string;
  action: string;
  remote_status: TemplateStatus;
  template: MessageTemplateView;
};

export type TemplateSyncPayload = {
  account_id: string;
  waba_id: string;
  import_missing?: boolean;
};

export type TemplateSyncResponse = {
  account_id: string;
  waba_id: string;
  provider: string;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  templates: MessageTemplateView[];
};

export type MediaAssetType = "image" | "audio" | "video" | "document";

export type MediaAssetCreatePayload = {
  account_id: string;
  waba_id?: string;
  phone_number_id?: string;
  name: string;
  asset_type: MediaAssetType;
  mime_type: string;
  file_size?: number;
  storage_key?: string;
  storage_url?: string;
  provider_media_id?: string;
  provider_media_status?: string;
  meta_media_id?: string;
  meta_media_status?: string;
  source?: string;
  tags?: string[];
};

export type MediaAssetUploadPayload = {
  account_id: string;
  file: File;
  waba_id?: string;
  phone_number_id?: string;
  name?: string;
  asset_type?: MediaAssetType;
  mime_type?: string;
  source?: string;
  tags?: string[];
};

export type MediaAssetUpdatePayload = {
  name?: string;
  waba_id?: string | null;
  phone_number_id?: string | null;
  is_active?: boolean;
  tags?: string[];
};

export type MediaAssetView = {
  asset_id: string;
  account_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  name: string;
  asset_type: MediaAssetType;
  mime_type: string;
  file_size: number | null;
  storage_key: string | null;
  storage_url: string | null;
  legacy_meta_media_id: string | null;
  legacy_meta_media_status: string | null;
  meta_media_id: string | null;
  meta_media_status: string | null;
  provider_references: MediaAssetProviderSyncView[];
  source: string;
  tags: string[];
  created_by: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type MediaAssetEventView = {
  id: string;
  account_id: string;
  asset_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  event_type: string;
  provider_media_id: string | null;
  meta_media_id: string | null;
  created_by: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type MediaAssetProviderSyncView = {
  id: string;
  account_id: string;
  asset_id: string;
  provider_name: string;
  waba_id: string | null;
  phone_number_id: string | null;
  provider_media_id: string | null;
  meta_media_id: string | null;
  sync_status: string;
  last_synced_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  raw_response: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type MediaAssetDetailResponse = {
  asset: MediaAssetView;
  usage: MediaAssetUsageSummary;
  provider_syncs: MediaAssetProviderSyncView[];
  events: MediaAssetEventView[];
};

export type MediaAssetUsageSummary = {
  total_events: number;
  sync_count: number;
  sync_failed_count: number;
  send_count: number;
  send_failed_count: number;
  template_send_count: number;
  template_send_failed_count: number;
  delivered_status_count: number;
  read_status_count: number;
  provider_failed_status_count: number;
  last_event_at: string | null;
  last_synced_at: string | null;
  last_sync_failed_at: string | null;
  last_sent_at: string | null;
  last_failed_at: string | null;
  last_delivered_at: string | null;
  last_read_at: string | null;
  last_provider_failed_at: string | null;
};

export type MediaAssetSendPayload = {
  asset_id: string;
  caption?: string;
  file_name?: string;
  agent_id?: string;
};

export type MediaAssetSendResponse = {
  account_id: string;
  conversation_id: string;
  external_conversation_id: string;
  internal_conversation_id: string;
  asset_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  provider_media_id: string | null;
  message_type: MediaAssetType;
  caption: string | null;
  delivered_caption: string | null;
  translated: boolean;
  message_id: string;
  provider: string;
  provider_message_id: string | null;
};

export type MediaAssetSyncPayload = {
  phone_number_id?: string;
  force_resync?: boolean;
};

export type MediaAssetSyncResponse = {
  asset_id: string;
  account_id: string;
  provider_name: string;
  waba_id: string | null;
  phone_number_id: string | null;
  provider_media_id: string | null;
  meta_media_id: string | null;
  sync_status: string;
  last_error_code: string | null;
  last_error_message: string | null;
  reused_existing: boolean;
  synced_at: string | null;
};

export type AiTogglePayload = {
  enabled: boolean;
};

export type HandoverPayload = {
  management_mode: ManagementMode;
  agent_id?: string | null;
  reason?: string | null;
};

export type CloseConversationPayload = {
  agent_id?: string;
  reason?: string;
};

export type AssignmentPayload = {
  agent_id: string;
  assigned_by_agent_id?: string;
  reason?: string;
};

export type RegisterAgentPayload = {
  account_id?: string | null;
  agent_id: string;
  display_name: string;
  email?: string | null;
  status: OperatorStatus;
  is_active: boolean;
};

export type AgentStatusPayload = {
  status: OperatorStatus;
};

// ── Backups API ──
export async function listBackups(): Promise<DbBackup[]> {
  try {
    const response = await api.get<DbBackup[]>("/api/backups");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function createBackup(): Promise<DbBackup> {
  const response = await api.post<DbBackup>("/api/backups");
  return response.data;
}

export async function restoreBackup(backupId: string): Promise<void> {
  await api.post(`/api/backups/${encodeURIComponent(backupId)}/restore`);
}

export async function deleteBackup(backupId: string): Promise<void> {
  await api.delete(`/api/backups/${encodeURIComponent(backupId)}`);
}

export function getBackupDownloadUrl(backupId: string): string {
  return `${resolvedApiBaseUrl}/api/backups/${encodeURIComponent(backupId)}/download`;
}

// ── Batch Operations API ──
export async function batchUpdateTags(params: {
  entity_type: string;
  entity_ids: string[];
  add_tags: string[];
  remove_tags: string[];
}): Promise<void> {
  await api.post("/api/batch/tags", params);
}

export async function batchAssignConversations(params: {
  conversation_ids: string[];
  agent_id: string;
}): Promise<void> {
  await api.post("/api/batch/assign-conversations", params);
}

export async function batchSendTemplate(params: {
  entity_type: string;
  entity_ids: string[];
  template_id: string;
  variables: Record<string, string>;
}): Promise<void> {
  await api.post("/api/batch/send-template", params);
}

export async function batchImportProducts(formData: FormData): Promise<void> {
  await api.post("/api/batch/import-products", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

// ── Knowledge API ──
export async function listKnowledgeCategories(): Promise<KnowledgeCategory[]> {
  try {
    const response = await api.get<KnowledgeCategory[]>("/api/knowledge/categories");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function createKnowledgeCategory(data: { name: string; description?: string }): Promise<KnowledgeCategory> {
  const response = await api.post<KnowledgeCategory>("/api/knowledge/categories", data);
  return response.data;
}

export async function updateKnowledgeCategory(id: string, data: { name?: string; description?: string }): Promise<void> {
  await api.patch(`/api/knowledge/categories/${encodeURIComponent(id)}`, data);
}

export async function deleteKnowledgeCategory(id: string): Promise<void> {
  await api.delete(`/api/knowledge/categories/${encodeURIComponent(id)}`);
}

export async function listKnowledgeArticles(params?: { category_id?: string; search?: string }): Promise<KnowledgeArticle[]> {
  try {
    const response = await api.get<KnowledgeArticle[]>("/api/knowledge/articles", { params });
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function createKnowledgeArticle(data: {
  title: string;
  category_id: string;
  content: string;
  keywords?: string;
}): Promise<KnowledgeArticle> {
  const response = await api.post<KnowledgeArticle>("/api/knowledge/articles", data);
  return response.data;
}

export async function updateKnowledgeArticle(id: string, data: Partial<{
  title: string;
  category_id: string;
  content: string;
  keywords: string;
}>): Promise<void> {
  await api.patch(`/api/knowledge/articles/${encodeURIComponent(id)}`, data);
}

export async function deleteKnowledgeArticle(id: string): Promise<void> {
  await api.delete(`/api/knowledge/articles/${encodeURIComponent(id)}`);
}

// ── Customer Profile API ──
export async function getCustomerProfile(customerId: string, accountId?: string): Promise<CustomerProfile> {
  const response = await api.get<CustomerProfile>(`/api/customers/${encodeURIComponent(customerId)}/profile`, {
    params: accountId ? { account_id: accountId } : undefined,
  });
  return response.data;
}

export async function listAutoTagRules(): Promise<AutoTagRule[]> {
  try {
    const response = await api.get<AutoTagRule[]>("/api/auto-tag-rules");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function createAutoTagRule(data: {
  name: string;
  condition_type: string;
  condition_operator: string;
  condition_value: number;
  tag_name: string;
}): Promise<AutoTagRule> {
  const response = await api.post<AutoTagRule>("/api/auto-tag-rules", data);
  return response.data;
}

export async function updateAutoTagRule(id: string, data: Partial<{
  name: string;
  condition_type: string;
  condition_operator: string;
  condition_value: number;
  tag_name: string;
  is_enabled: boolean;
}>): Promise<void> {
  await api.patch(`/api/auto-tag-rules/${encodeURIComponent(id)}`, data);
}

export async function deleteAutoTagRule(id: string): Promise<void> {
  await api.delete(`/api/auto-tag-rules/${encodeURIComponent(id)}`);
}

// ── Template Preview API ──
export async function getTemplateVariables(): Promise<Array<{ code: string; label: string }>> {
  try {
    const response = await api.get<
      Array<{ code: string; label: string }>
    >("/api/templates/variables");
    return response.data;
  } catch {
    return [
      { code: "{{customer_name}}", label: "客户姓名" },
      { code: "{{customer_phone}}", label: "客户手机号" },
      { code: "{{recharge_total}}", label: "累计充值" },
      { code: "{{withdraw_total}}", label: "累计提现" },
      { code: "{{brand_name}}", label: "品牌名称" },
      { code: "{{current_date}}", label: "当前日期" },
    ];
  }
}

export async function previewTemplate(content: string, variables: Record<string, string>): Promise<string> {
  const response = await api.post<string>("/api/templates/preview", { content, variables });
  return response.data;
}

// ── API Stats API ──
export async function getApiStatsSummary(): Promise<ApiStatsSummary> {
  const response = await api.get<ApiStatsSummary>("/api/api-stats/summary");
  return response.data;
}

export async function getApiStatsByAgency(): Promise<ApiStatsByAgency[]> {
  try {
    const response = await api.get<ApiStatsByAgency[]>("/api/api-stats/by-agency");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function getApiStatsByEndpoint(): Promise<ApiStatsByEndpoint[]> {
  try {
    const response = await api.get<ApiStatsByEndpoint[]>("/api/api-stats/by-endpoint");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

// ── Rate Limits API ──
export async function listRateLimitRules(): Promise<RateLimitRule[]> {
  try {
    const response = await api.get<RateLimitRule[]>("/api/rate-limits");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function createRateLimitRule(data: {
  agency_id?: string;
  endpoint_pattern: string;
  max_requests: number;
  window_seconds: number;
  ban_minutes: number;
}): Promise<RateLimitRule> {
  const response = await api.post<RateLimitRule>("/api/rate-limits", data);
  return response.data;
}

export async function updateRateLimitRule(id: string, data: Partial<{
  endpoint_pattern: string;
  max_requests: number;
  window_seconds: number;
  ban_minutes: number;
  is_enabled: boolean;
}>): Promise<void> {
  await api.patch(`/api/rate-limits/${encodeURIComponent(id)}`, data);
}

export async function deleteRateLimitRule(id: string): Promise<void> {
  await api.delete(`/api/rate-limits/${encodeURIComponent(id)}`);
}

export async function listBannedIps(): Promise<BannedIp[]> {
  try {
    const response = await api.get<BannedIp[]>("/api/rate-limits/banned-ips");
    return response.data;
  } catch (error) {
    if (shouldFallbackToMock(error)) return [];
    throw error;
  }
}

export async function unbanIp(ip: string): Promise<void> {
  await api.delete(`/api/rate-limits/banned-ips/${encodeURIComponent(ip)}`);
}

// ── Email Config API ──
export async function getEmailConfig(): Promise<EmailConfig | null> {
  try {
    const response = await api.get<EmailConfig>("/api/email-config");
    return response.data;
  } catch {
    return null;
  }
}

export async function updateEmailConfig(data: EmailConfig): Promise<void> {
  await api.put("/api/email-config", data);
}

export async function testEmailConfig(to: string): Promise<void> {
  await api.post("/api/email-config/test", { to });
}

// ── Health Check API ──
export async function getHealthCheckSummary(): Promise<HealthCheckSummary> {
  const response = await api.get<HealthCheckSummary>("/api/health-checks/summary");
  return response.data;
}

export async function runHealthCheck(): Promise<HealthCheckResult[]> {
  const response = await api.post<HealthCheckResult[]>("/api/health-checks/run");
  return response.data;
}

const resolvedApiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");

export const api = axios.create({
  baseURL: resolvedApiBaseUrl,
  timeout: 15000
});

api.interceptors.request.use((config) => {
  const actor = useAppStore.getState();
  const headers = AxiosHeaders.from(config.headers);
  headers.set("X-Actor-Id", actor.consoleAgentId);
  headers.set("X-Actor-Name", actor.consoleAgentName);
  headers.set("X-Actor-Role", actor.actorRole);
  if (actor.actorAccountIds.length > 0) {
    headers.set("X-Actor-Account-Ids", actor.actorAccountIds.join(","));
  }
  const userType = adminAuth.getUserType?.() || "";
  if (userType) {
    headers.set("X-Actor-Type", userType);
  }
  // 附加上 JWT access token
  const accessToken = adminAuth.getAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  config.headers = headers;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      !originalRequest._retry
    ) {
      originalRequest._retry = true;

      if (isRefreshing) {
        // 正在刷新中，排队等待新 token
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      isRefreshing = true;
      try {
        const refreshed = await adminAuth.refresh();
        if (!refreshed) throw new Error("Refresh failed");
        const newToken = adminAuth.getAccessToken();
        if (!newToken) throw new Error("No token after refresh");
        onTokenRefreshed(newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        // refresh 失败，清除认证并跳转登录（replace 避免历史循环）
        adminAuth.clearAuth();
        window.location.replace("/login");
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // 统一错误处理
    const status = error.response?.status;
    if (status === 403) {
      console.warn("[API] 403 Forbidden:", error.config?.url);
    } else if (status && status >= 500) {
      console.error("[API] 5xx Server Error:", error.config?.url, status);
    } else if (status === 429) {
      console.warn("[API] 429 Rate Limited:", error.config?.url);
    }

    return Promise.reject(error);
  }
);

export async function listConversations(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  assigned_agent_id?: string;
  status?: string;
  management_mode?: ManagementMode;
  latest_intent_name?: string;
  latest_handover_recommended?: boolean;
  is_sleeping?: boolean;
}): Promise<ConversationSummary[]> {
  const response = await api.get<{ items: ConversationSummary[] } | ConversationSummary[]>("/api/conversations", {
    params
  });
  const list = Array.isArray(response.data) ? response.data : response.data.items ?? [];
  return list.map(normalizeConversationSummary);
}

export async function listAssignedConversations(params?: {
  account_id?: string;
  agent_id?: string;
  status?: string;
  management_mode?: ManagementMode;
}): Promise<ConversationSummary[]> {
  const response = await api.get<ConversationSummary[]>("/api/conversations/assigned", {
    params
  });
  return response.data.map(normalizeConversationSummary);
}

/** F6: 唤醒沉睡会话 */
export async function wakeConversation(accountId: string, conversationId: string): Promise<ConversationSummary> {
  const response = await api.post<ConversationSummary>(
    `/api/conversations/${accountId}/${conversationId}/wake`
  );
  return normalizeConversationSummary(response.data);
}

/** F6: 会话统计（活跃/沉睡/关闭计数） */
export interface ConversationStats {
  active_count: number;
  sleeping_count: number;
  closed_count: number;
}

export async function getConversationStats(accountId?: string): Promise<ConversationStats> {
  const params: Record<string, string> = {};
  if (accountId) params.account_id = accountId;
  const response = await api.get<ConversationStats>("/api/conversations/stats", { params });
  return response.data;
}

export async function listMessages(
  accountId: string,
  conversationId: string,
  includeTranslations = false,
  offset?: number,
  limit?: number,
): Promise<ConversationMessage[]> {
  const params: Record<string, string | number | boolean> = {};
  if (includeTranslations) params.include_translations = true;
  if (offset !== undefined) params.offset = offset;
  if (limit !== undefined) params.limit = limit;
  const response = await api.get<ConversationMessage[]>(
    `/api/conversations/${accountId}/${conversationId}/messages`,
    { params }
  );
  return response.data.map(normalizeConversationMessage);
}

export async function listConversationTimeline(
  accountId: string,
  conversationId: string,
  limit = 50
): Promise<ConversationTimelineItem[]> {
  const response = await api.get<ConversationTimelineItem[]>(
    `/api/conversations/${accountId}/${conversationId}/timeline`,
    {
      params: { limit }
    }
  );
  return response.data;
}

export async function listRuntimeState(): Promise<RuntimeState> {
  const response = await api.get<RuntimeState>("/api/runtime/state");
  return response.data;
}

export async function getConversationAiStatus(
  accountId: string,
  conversationId: string
): Promise<ConversationAiStatus> {
  const response = await api.get<ConversationAiStatus>(
    `/api/runtime/conversations/${conversationId}/ai-status`,
    {
      params: { account_id: accountId }
    }
  );
  return response.data;
}

export async function getRuntimeConfigSummary(): Promise<RuntimeConfigSummary> {
  const response = await api.get<RuntimeConfigSummary>("/api/runtime/config-summary");
  return normalizeRuntimeConfigSummary(response.data);
}

export async function getLaunchReadiness(
  params?: LaunchReadinessQueryParams
): Promise<LaunchReadinessResponse> {
  const response = await api.get<LaunchReadinessResponse>("/api/runtime/launch-readiness", {
    params
  });
  return response.data;
}

export async function listProviderStatusBuffer(
  params?: ProviderStatusBufferListParams
): Promise<ProviderStatusBufferListResponse> {
  const response = await api.get<ProviderStatusBufferListResponse>(
    "/api/runtime/provider-status-buffer",
    { params }
  );
  return response.data;
}

export async function replayProviderStatusBuffer(
  payload: ProviderStatusBufferReplayPayload
): Promise<ProviderStatusBufferReplayResponse> {
  const response = await api.post<ProviderStatusBufferReplayResponse>(
    "/api/runtime/provider-status-buffer/replay",
    payload
  );
  return response.data;
}

export async function listPlatformSites(accountId?: string): Promise<PlatformSite[]> {
  const response = await api.get<PlatformSite[]>("/api/platform/sites");
  if (!accountId) {
    return response.data;
  }
  return response.data.filter((item) => item.account_id === accountId);
}

export async function createPlatformSite(
  payload: PlatformSiteCreatePayload
): Promise<PlatformSite> {
  const response = await api.post<PlatformSite>("/api/platform/sites", payload);
  return response.data;
}

export type PlatformSiteUpdatePayload = Partial<Omit<PlatformSiteCreatePayload, "site_key">> & {
  status?: string;
};

export async function updatePlatformSite(
  siteId: string,
  payload: PlatformSiteUpdatePayload
): Promise<PlatformSite> {
  const response = await api.put<PlatformSite>(`/api/platform/sites/${encodeURIComponent(siteId)}`, payload);
  return response.data;
}

export async function deletePlatformSite(
  siteId: string
): Promise<{ id: string; status: string }> {
  const response = await api.delete<{ id: string; status: string }>(
    `/api/platform/sites/${encodeURIComponent(siteId)}`
  );
  return response.data;
}

export type PlatformSiteConfigResponse = {
  id: string;
  site_id: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string | null;
  font_family: string | null;
  footer_text: string | null;
  enabled_pages: string[] | null;
  custom_css: string | null;
  deploy_type: string | null;
  ssh_host: string | null;
  ssh_user: string | null;
  ssh_key_path: string | null;
  domain: string | null;
  ssl_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type PlatformSiteConfigUpdatePayload = Partial<{
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  font_family: string;
  footer_text: string;
  enabled_pages: string[];
  custom_css: string;
  deploy_type: string;
  ssh_host: string;
  ssh_user: string;
  ssh_key_path: string;
  domain: string;
  ssl_enabled: boolean;
}>;

export async function getPlatformSiteConfig(
  siteId: string
): Promise<PlatformSiteConfigResponse> {
  const response = await api.get<PlatformSiteConfigResponse>(
    `/api/platform/sites/${encodeURIComponent(siteId)}/config`
  );
  return response.data;
}

export async function updatePlatformSiteConfig(
  siteId: string,
  payload: PlatformSiteConfigUpdatePayload
): Promise<PlatformSiteConfigResponse> {
  const response = await api.put<PlatformSiteConfigResponse>(
    `/api/platform/sites/${encodeURIComponent(siteId)}/config`,
    payload
  );
  return response.data;
}

// ── Site Enhancement (SITE-ENHANCE) ──

export type SiteAnalytics = {
  site_id: string;
  total_users: number;
  active_users_today: number;
  sign_in_count_today: number;
  task_completion_rate: number;
  revenue_today: number;
  last_verified_at: string | null;
  health_status: "healthy" | "warning" | "error" | "unverified";
};

export async function getSiteAnalytics(siteId: string): Promise<SiteAnalytics> {
  const response = await api.get<SiteAnalytics>(`/api/h5/sites/${encodeURIComponent(siteId)}/analytics`);
  return response.data;
}

export type CloneSitePayload = {
  new_site_key: string;
  new_brand_name: string;
  new_domain: string;
  clone_brand_config: boolean;
  clone_deploy_config: boolean;
  clone_translations: boolean;
  clone_permissions: boolean;
};

export async function cloneSite(siteId: string, payload: CloneSitePayload): Promise<PlatformSite> {
  const response = await api.post<PlatformSite>(`/api/h5/sites/${encodeURIComponent(siteId)}/clone`, payload);
  return response.data;
}

export async function exportSiteConfig(siteId: string): Promise<Record<string, unknown>> {
  const response = await api.get(`/api/h5/sites/${encodeURIComponent(siteId)}/export-config`);
  return response.data;
}

export async function importSiteConfig(config: Record<string, unknown>): Promise<PlatformSite> {
  const response = await api.post<PlatformSite>("/api/h5/sites/import-config", config);
  return response.data;
}

export type BatchUpdatePayload = {
  site_ids: string[];
  action: "pause" | "resume" | "delete" | "update_config";
  config?: Record<string, unknown>;
};

export async function batchUpdateSites(payload: BatchUpdatePayload): Promise<{ success_count: number; failed_count: number; errors: string[] }> {
  const response = await api.post("/api/h5/sites/batch-update", payload);
  return response.data;
}

export type DnsVerificationResult = {
  dns_valid: boolean;
  a_record: string;
  ssl_valid: boolean;
  ssl_expires_at: string;
  ssl_days_remaining: number;
};

export async function verifySiteDns(siteId: string): Promise<DnsVerificationResult> {
  const response = await api.post<DnsVerificationResult>(`/api/h5/sites/${encodeURIComponent(siteId)}/verify-dns`);
  return response.data;
}

export type DeployHistoryItem = {
  id: string;
  site_id: string;
  action: "build" | "deploy" | "verify" | "rollback";
  status: "success" | "error";
  details: string | null;
  created_by: string;
  created_at: string;
};

export async function getDeployHistory(siteId: string): Promise<DeployHistoryItem[]> {
  const response = await api.get<DeployHistoryItem[]>(`/api/h5/sites/${encodeURIComponent(siteId)}/deploy-history`);
  return response.data;
}

// ── Multi-Tenant Architecture (MT) ──

export type Agent = {
  id: string;
  name: string;
  username?: string;
  brand_name?: string | null;
  logo_url?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  member_count?: number;
  role_count?: number;
  granted_permission_count?: number;
};

export type AgentCreatePayload = {
  name: string;
  username?: string;
  password?: string;
  brand_name?: string;
  logo_url?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
};

export type AgentUpdatePayload = Partial<AgentCreatePayload> & { status?: string };

export type AgentMember = {
  id: string;
  agent_id: string;
  user_id: string;
  username?: string;
  display_name?: string;
  status?: string;
  role: string;
  created_at: string;
};

export type AgentBilling = {
  id: string;
  agency_id: string;
  billing_type: string;
  amount: number;
  billing_period_start: string | null;
  billing_period_end: string | null;
  status: "draft" | "pending" | "paid" | "verified" | "cancelled" | string;
  line_items?: AgentBillingLineItem[] | null;
  created_at: string | null;
};

export type AgentBillingLineItem = {
  description: string;
  quantity: number;
  unit_price: number;
};

export type AgentBillingListParams = {
  status?: string;
  billing_type?: string;
  period_start?: string;
  period_end?: string;
};

export type AgencyBillingPayload = {
  billing_type: string;
  amount: number;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  line_items?: AgentBillingLineItem[];
};

export type AgencyBillingUpdatePayload = Partial<AgencyBillingPayload> & {
  status?: string;
};

export type AgentDashboard = {
  total_sites: number;
  active_sites: number;
  active_users_today: number;
  revenue_this_month: number;
  pending_billing: number;
  total_members: number;
  online_support: number;
};

export type H5Template = {
  id: string;
  name: string;
  description: string | null;
  preview_url?: string | null;
  preview_path?: string | null;
  template_data: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  ref_count?: number;
  status?: string;
  technical_status?: string;
  publish_status?: string;
  published_at?: string | null;
  published_by?: string | null;
  business_status?: string;
  package_filename?: string | null;
  package_size?: number | null;
  package_uploaded_at?: string | null;
  manifest?: Record<string, unknown> | null;
};

// ── Agent APIs ──

export async function listAgents(): Promise<Agent[]> {
  const res = await api.get<Agent[]>("/api/agents");
  return res.data;
}

export async function checkAgentUsername(username: string): Promise<boolean> {
  const res = await api.get<{ exists: boolean }>("/api/agents/check-username", { params: { username } });
  return res.data.exists;
}

export async function createAgent(payload: AgentCreatePayload): Promise<Agent> {
  const res = await api.post<Agent>("/api/agents", payload);
  return res.data;
}

export async function updateAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> {
  const res = await api.patch<Agent>(`/api/agents/${encodeURIComponent(id)}`, payload);
  return res.data;
}

export async function deleteAgent(id: string): Promise<void> {
  await api.delete(`/api/agents/${encodeURIComponent(id)}`);
}

export async function updateAgentStatus(id: string, status: string): Promise<{ id: string; status: string }> {
  const res = await api.patch(`/api/agents/${encodeURIComponent(id)}/status`, { status });
  return res.data;
}

export async function restoreAgent(id: string): Promise<{ id: string; status: string }> {
  const res = await api.post(`/api/agents/${encodeURIComponent(id)}/restore`);
  return res.data;
}

export async function listAgentMembers(agentId: string): Promise<AgentMember[]> {
  const res = await api.get<AgentMember[]>(`/api/agents/${encodeURIComponent(agentId)}/members`);
  return res.data;
}

export async function addAgentMember(agentId: string, username: string, password: string, role: string): Promise<AgentMember> {
  const res = await api.post<AgentMember>(`/api/agents/${encodeURIComponent(agentId)}/members`, { username, password, role });
  return res.data;
}

export async function updateAgentMemberRole(agencyId: string, memberId: string, role: string, password?: string): Promise<AgentMember> {
  const payload: Record<string, unknown> = { role };
  if (password) payload.password = password;
  const res = await api.patch<AgentMember>(`/api/agents/${encodeURIComponent(agencyId)}/members/${encodeURIComponent(memberId)}`, payload);
  return res.data;
}

export async function removeAgentMember(agencyId: string, memberId: string): Promise<void> {
  await api.delete(`/api/agents/${encodeURIComponent(agencyId)}/members/${encodeURIComponent(memberId)}`);
}

export async function getAgentDashboard(): Promise<AgentDashboard> {
  const res = await api.get<AgentDashboard>("/api/agent-dashboard");
  return res.data;
}

// ── H5 Template APIs ──

export async function listH5Templates(): Promise<H5Template[]> {
  const res = await api.get<H5Template[]>("/api/h5-templates");
  return res.data;
}

// ── Agent Billing APIs ──

// ── Agent Password Reset / Billing Management (超管功能) ──

export async function resetAgentPassword(agentId: string, newPassword: string): Promise<void> {
  await api.post(`/api/agents/${encodeURIComponent(agentId)}/reset-password`, { new_password: newPassword });
}

export async function listAgencyBilling(
  agencyId: string,
  params: AgentBillingListParams = {},
): Promise<AgentBilling[]> {
  const res = await api.get<AgentBilling[]>(`/api/agents/${encodeURIComponent(agencyId)}/billing`, {
    params,
  });
  return res.data;
}

export async function getAgencyBillingDetail(agencyId: string, billingId: string): Promise<AgentBilling> {
  const res = await api.get<AgentBilling>(
    `/api/agents/${encodeURIComponent(agencyId)}/billing/${encodeURIComponent(billingId)}`,
  );
  return res.data;
}

export async function createAgencyBilling(
  agencyId: string,
  payload: AgencyBillingPayload,
): Promise<AgentBilling> {
  const res = await api.post<AgentBilling>(`/api/agents/${encodeURIComponent(agencyId)}/billing`, payload);
  return res.data;
}

export async function updateAgencyBilling(
  agencyId: string,
  billingId: string,
  payload: AgencyBillingUpdatePayload,
): Promise<AgentBilling> {
  const res = await api.patch<AgentBilling>(
    `/api/agents/${encodeURIComponent(agencyId)}/billing/${encodeURIComponent(billingId)}`,
    payload,
  );
  return res.data;
}

export async function cancelAgencyBilling(agencyId: string, billingId: string): Promise<AgentBilling> {
  const res = await api.delete<AgentBilling>(
    `/api/agents/${encodeURIComponent(agencyId)}/billing/${encodeURIComponent(billingId)}`,
  );
  return res.data;
}

export type AgencyBillingVerificationResult = {
  id: string;
  agency_id: string;
  status: string;
  message: string;
};

export async function verifyBillingPayment(
  agencyId: string,
  billingId: string,
): Promise<AgencyBillingVerificationResult> {
  const res = await api.post<AgencyBillingVerificationResult>(
    `/api/agents/${encodeURIComponent(agencyId)}/billing/${encodeURIComponent(billingId)}/verify`
  );
  return res.data;
}

// ── WABA Assignment APIs ──

export async function assignWabaToSite(wabaId: string, siteId: string): Promise<void> {
  await api.post(`/api/waba/${encodeURIComponent(wabaId)}/assign`, { site_id: siteId });
}

export async function getSiteWabas(siteId: string): Promise<Array<{ id: string; waba_id: string; phone_number_id: string | null; status: string }>> {
  const res = await api.get(`/api/sites/${encodeURIComponent(siteId)}/waba`);
  return res.data;
}

export async function listWabas(): Promise<Array<{ id: string; waba_id: string; name: string; status: string }>> {
  const res = await api.get("/api/waba");
  return res.data;
}

export async function revokeWabaFromSite(wabaId: string): Promise<void> {
  await api.post(`/api/waba/${encodeURIComponent(wabaId)}/revoke`);
}

export async function listPlatformUsers(): Promise<PlatformUser[]> {
  const response = await api.get<PlatformUser[]>("/api/platform/users");
  return response.data;
}

/** CUS-001: Paginated user list with filters */
export async function listPlatformUsersPaginated(
  params?: PlatformUserListParams
): Promise<PaginatedUserListResponse> {
  const response = await api.get<PaginatedUserListResponse>("/api/platform/users", { params });
  return response.data;
}

/** CUS-003: Batch update customer lifecycle (block/unblock) */
export type BatchLifecyclePayload = {
  customer_ids: string[];
  account_id?: string;
  lifecycle_status: string;
};

export async function batchUpdateCustomerLifecycle(
  payload: BatchLifecyclePayload
): Promise<{ success_count: number; failed_count: number; errors: string[] }> {
  const response = await api.post("/api/customers/batch-lifecycle", payload);
  return response.data;
}

/** CUS-002: Customer interaction timeline */
export type TimelineEvent = {
  type: string;
  time: string;
  summary: string;
  metadata?: Record<string, unknown>;
};

export async function getCustomerTimeline(
  customerId: string,
  params?: { account_id?: string; limit?: number }
): Promise<{ events: TimelineEvent[] }> {
  const response = await api.get<{ events: TimelineEvent[] }>(
    `/api/customers/${customerId}/timeline`,
    { params }
  );
  return response.data;
}

export async function createPlatformUser(
  payload: PlatformUserCreatePayload
): Promise<PlatformUser> {
  const response = await api.post<PlatformUser>("/api/platform/users", payload);
  return response.data;
}

export async function listPlatformTags(): Promise<PlatformTag[]> {
  const response = await api.get<PlatformTag[]>("/api/platform/tags");
  return response.data;
}

export async function createPlatformTag(
  payload: PlatformTagCreatePayload
): Promise<PlatformTag> {
  const response = await api.post<PlatformTag>("/api/platform/tags", payload);
  return response.data;
}

export async function listAudienceRuleSets(): Promise<AudienceRuleSet[]> {
  const response = await api.get<AudienceRuleSet[]>("/api/platform/audience-rules");
  return response.data;
}

export async function createAudienceRuleSet(
  payload: AudienceRuleSetCreatePayload
): Promise<AudienceRuleSet> {
  const response = await api.post<AudienceRuleSet>("/api/platform/audience-rules", payload);
  return response.data;
}

export type AIProviderConfig = {
  id: string;
  name: string;
  provider_type: string;
  api_base_url: string | null;
  has_api_key: boolean;
  model: string;
  priority: number;
  is_enabled: boolean;
  timeout_seconds: number;
  use_responses_api: boolean;
  metadata_json: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
};

export async function listAIProviders(): Promise<AIProviderConfig[]> {
  const response = await api.get<AIProviderConfig[]>("/api/ai-providers");
  return response.data;
}

/** STUB-BE-001: Update audience rule set */
export async function updateAudienceRuleSet(
  ruleSetId: string,
  payload: Partial<AudienceRuleSetCreatePayload> & { status?: string }
): Promise<AudienceRuleSet> {
  const response = await api.patch<AudienceRuleSet>(
    `/api/platform/audience-rules/${ruleSetId}`,
    payload
  );
  return response.data;
}

/** STUB-BE-001: Delete audience rule set */
export async function deleteAudienceRuleSet(ruleSetId: string): Promise<void> {
  await api.delete(`/api/platform/audience-rules/${ruleSetId}`);
}

export async function listTaskTemplates(params?: {
  account_id?: string;
  status?: string;
  task_type?: string;
}): Promise<TaskTemplate[]> {
  const response = await api.get<TaskTemplate[]>("/api/tasks/templates", {
    params
  });
  return response.data;
}

export async function createTaskTemplate(
  payload: TaskTemplateCreatePayload
): Promise<TaskTemplate> {
  const response = await api.post<TaskTemplate>("/api/tasks/templates", payload);
  return response.data;
}

export async function listTaskInstances(params?: {
  account_id?: string;
  status?: string;
  template_id?: string;
  user_id?: string;
}): Promise<TaskInstance[]> {
  const response = await api.get<TaskInstance[]>("/api/tasks/instances", {
    params
  });
  return response.data;
}

export async function createTaskInstance(
  payload: TaskInstanceCreatePayload
): Promise<TaskInstance> {
  const response = await api.post<TaskInstance>("/api/tasks/instances", payload);
  return response.data;
}

export async function claimTaskInstance(taskInstanceId: string): Promise<TaskInstance> {
  const response = await api.post<TaskInstance>(`/api/tasks/instances/${taskInstanceId}/claim`, {});
  return response.data;
}

/** STUB-003: Approve task review */
export async function approveTaskReview(
  taskInstanceId: string,
  payload?: { reason?: string }
): Promise<{ status: string; task_instance_id: string }> {
  const response = await api.post<{ status: string; task_instance_id: string }>(
    `/api/tasks/reviews/${taskInstanceId}/approve`,
    payload ?? {}
  );
  return response.data;
}

/** STUB-003: Reject task review */
export async function rejectTaskReview(
  taskInstanceId: string,
  payload?: { reason?: string }
): Promise<{ status: string; task_instance_id: string }> {
  const response = await api.post<{ status: string; task_instance_id: string }>(
    `/api/tasks/reviews/${taskInstanceId}/reject`,
    payload ?? {}
  );
  return response.data;
}

export async function listQueueStats(): Promise<QueueStatsResponse> {
  const response = await api.get<QueueStatsResponse>("/api/queue/stats");
  return response.data;
}

export async function getMetricsSummary(): Promise<MetricsSummaryResponse> {
  const response = await api.get<MetricsSummaryResponse>("/api/metrics/summary");
  return normalizeMetricsSummary(response.data);
}

export async function getWhatsAppStatsSummary(
  params?: WhatsAppStatsQueryParams
): Promise<WhatsAppStatsSummary> {
  const response = await api.get<WhatsAppStatsSummary>("/api/whatsapp/stats/summary", {
    params
  });
  return response.data;
}

export async function listWhatsAppDailyStats(
  params?: WhatsAppStatsQueryParams
): Promise<WhatsAppStatsDailyRow[]> {
  const response = await api.get<WhatsAppStatsDailyRow[]>("/api/whatsapp/stats/daily", {
    params
  });
  return response.data;
}

export async function getWhatsAppStatsDetail(
  params?: WhatsAppStatsQueryParams
): Promise<WhatsAppStatsDetailResponse> {
  const response = await api.get<WhatsAppStatsDetailResponse>("/api/whatsapp/stats/detail", {
    params
  });
  return response.data;
}

export async function rebuildWhatsAppStats(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<WhatsAppStatsRebuildResponse> {
  const response = await api.post<WhatsAppStatsRebuildResponse>(
    "/api/whatsapp/stats/rebuild",
    undefined,
    {
      params
    }
  );
  return response.data;
}

export async function listAuditLogs(params?: AuditLogListParams): Promise<AuditLogEntry[]> {
  const response = await api.get<AuditLogEntry[]>("/api/runtime/audit-logs", {
    params: {
      limit: params?.limit ?? 20,
      ...(params?.account_id ? { account_id: params.account_id } : {}),
      ...(params?.waba_id ? { waba_id: params.waba_id } : {}),
      ...(params?.phone_number_id ? { phone_number_id: params.phone_number_id } : {}),
      ...(params?.actor_type ? { actor_type: params.actor_type } : {}),
      ...(params?.actor_id ? { actor_id: params.actor_id } : {}),
      ...(params?.action ? { action: params.action } : {}),
      ...(params?.target_type ? { target_type: params.target_type } : {}),
      ...(params?.target_id ? { target_id: params.target_id } : {}),
      ...(params?.date_from ? { date_from: params.date_from } : {}),
      ...(params?.date_to ? { date_to: params.date_to } : {})
    }
  });
  return response.data;
}

export async function listSupportKnowledge(
  category?: string,
  accountId?: string,
  includeBuiltin = true
): Promise<SupportKnowledgeEntryView[]> {
  const response = await api.get<SupportKnowledgeEntryView[]>(
    "/api/runtime/support-knowledge",
    {
      params: {
        ...(category ? { category } : {}),
        ...(accountId ? { account_id: accountId } : {}),
        include_builtin: includeBuiltin
      }
    }
  );
  return response.data;
}

export async function createSupportKnowledgeEntry(
  payload: SupportKnowledgeEntryCreatePayload
): Promise<SupportKnowledgeEntryView> {
  const response = await api.post<SupportKnowledgeEntryView>(
    "/api/runtime/support-knowledge",
    payload
  );
  return response.data;
}

export async function updateSupportKnowledgeEntry(
  articleId: string,
  accountId: string,
  payload: SupportKnowledgeEntryUpdatePayload
): Promise<SupportKnowledgeEntryView> {
  const response = await api.post<SupportKnowledgeEntryView>(
    `/api/runtime/support-knowledge/${encodeURIComponent(articleId)}`,
    payload,
    {
      params: { account_id: accountId }
    }
  );
  return response.data;
}

export async function deleteSupportKnowledgeEntry(
  articleId: string,
  accountId: string
): Promise<SupportKnowledgeDeleteResponse> {
  const response = await api.delete<SupportKnowledgeDeleteResponse>(
    `/api/runtime/support-knowledge/${encodeURIComponent(articleId)}`,
    {
      params: { account_id: accountId }
    }
  );
  return response.data;
}

export async function exportSupportKnowledge(
  accountId?: string
): Promise<SupportKnowledgeExportBundle> {
  const response = await api.get<SupportKnowledgeExportBundle>(
    "/api/runtime/support-knowledge/export",
    {
      params: accountId ? { account_id: accountId } : undefined
    }
  );
  return response.data;
}

export async function importSupportKnowledge(
  payload: SupportKnowledgeImportPayload
): Promise<SupportKnowledgeImportResult> {
  const response = await api.post<SupportKnowledgeImportResult>(
    "/api/runtime/support-knowledge/import",
    payload
  );
  return response.data;
}

export async function listRuntimeAgents(
  status?: OperatorStatus,
  accountId?: string
): Promise<RuntimeAgent[]> {
  const response = await api.get<RuntimeAgent[]>("/api/runtime/agents", {
    params: {
      ...(status ? { status } : {}),
      ...(accountId ? { account_id: accountId } : {}),
    }
  });
  return response.data;
}

export async function listAgentWorkloads(
  status?: OperatorStatus,
  accountId?: string
): Promise<AgentWorkload[]> {
  const response = await api.get<AgentWorkload[]>("/api/runtime/agents/workloads", {
    params: {
      ...(status ? { status } : {}),
      ...(accountId ? { account_id: accountId } : {}),
    }
  });
  return response.data;
}

export type MetaAccountListParams = {
  account_id?: string;
  waba_id?: string;
  is_active?: boolean;
  account_is_active?: boolean;
  ready_for_webhook_delivery?: boolean;
  ready_for_outbound_messages?: boolean;
  ready_for_meta_activation?: boolean;
  webhook_verification_status?: MetaWebhookVerificationStatus;
  webhook_runtime_status?: MetaWebhookRuntimeStatus;
};

export async function listMetaAccounts(params?: MetaAccountListParams): Promise<MetaWabaAccount[]> {
  const axiosParams: Record<string, unknown> = {};
  if (params) {
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null && val !== "") {
        axiosParams[key] = val;
      }
    }
  }
  const response = await api.get<MetaWabaAccount[]>("/api/meta/accounts", {
    params: Object.keys(axiosParams).length > 0 ? axiosParams : undefined,
  });
  return response.data;
}

export type MetaPhoneNumberListParams = {
  account_id?: string;
  waba_id?: string;
  is_active?: boolean;
  is_registered?: boolean;
  quality_rating?: "GREEN" | "YELLOW" | "RED" | "UNKNOWN";
  ready_for_webhook_delivery?: boolean;
  ready_for_outbound_messages?: boolean;
  ready_for_meta_activation?: boolean;
};

export async function listMetaPhoneNumbers(
  params?: MetaPhoneNumberListParams
): Promise<MetaPhoneNumberScopeView[]> {
  const response = await api.get<MetaPhoneNumberScopeView[]>("/api/meta/accounts/phone-numbers", {
    params,
  });
  return response.data;
}

export async function createManualMetaAccount(
  payload: ManualMetaAccountPayload
): Promise<MetaWabaAccount> {
  const response = await api.post<MetaWabaAccount>("/api/meta/accounts/manual", payload);
  return response.data;
}

export interface DiscoverPayload {
  waba_id: string;
  access_token: string;
  account_id?: string;
}

export interface DiscoverResponse {
  ok: boolean;
  fields: Record<string, { status: string; value: unknown; error?: string; error_code?: number; warnings?: string[] }>;
  errors: string[];
  warnings: string[];
}

export async function discoverMetaAccount(payload: DiscoverPayload): Promise<DiscoverResponse> {
  const response = await api.post<DiscoverResponse>("/api/meta/accounts/discover", payload);
  return response.data;
}

export async function updateMetaAccount(
  accountId: string,
  wabaId: string,
  payload: MetaAccountUpdatePayload
): Promise<MetaWabaAccount> {
  const response = await api.patch<MetaWabaAccount>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}`,
    payload
  );
  return response.data;
}

export async function updateMetaWabaStatus(
  accountId: string,
  wabaId: string,
  payload: MetaScopeStatusUpdatePayload
): Promise<MetaWabaAccount> {
  const response = await api.patch<MetaWabaAccount>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/status`,
    payload
  );
  return response.data;
}

export async function updateMetaAccountStatus(
  accountId: string,
  payload: MetaScopeStatusUpdatePayload
): Promise<MetaAccountStatusUpdateResponse> {
  const response = await api.patch<MetaAccountStatusUpdateResponse>(
    `/api/meta/accounts/${accountId}/status`,
    payload
  );
  return response.data;
}

export async function updateMetaPhoneNumberStatus(
  accountId: string,
  wabaId: string,
  phoneNumberId: string,
  payload: MetaScopeStatusUpdatePayload
): Promise<MetaPhoneNumberScopeView> {
  const response = await api.patch<MetaPhoneNumberScopeView>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/phone-numbers/${phoneNumberId}/status`,
    payload
  );
  return response.data;
}

export type EmbeddedSignupSessionListParams = {
  account_id?: string;
  status?: EmbeddedSignupSession["status"];
  completion_stage?: EmbeddedSignupSession["completion_stage"];
  remote_confirmed?: boolean;
  waba_id?: string;
  webhook_subscription_status?: MetaWebhookSubscriptionStatus;
  webhook_verification_status?: MetaWebhookVerificationStatus;
  webhook_runtime_status?: MetaWebhookRuntimeStatus;
  ready_for_webhook_delivery?: boolean;
  ready_for_outbound_messages?: boolean;
  ready_for_meta_activation?: boolean;
};

export async function listEmbeddedSignupSessions(
  params?: string | EmbeddedSignupSessionListParams
): Promise<EmbeddedSignupSession[]> {
  const response = await api.get<EmbeddedSignupSession[]>(
    "/api/meta/accounts/embedded-signup/sessions",
    {
      params:
        typeof params === "string"
          ? { account_id: params }
          : params
    }
  );
  return response.data;
}

export async function createEmbeddedSignupSession(
  payload: EmbeddedSignupSessionPayload
): Promise<EmbeddedSignupSession> {
  const response = await api.post<EmbeddedSignupSession>(
    "/api/meta/accounts/embedded-signup/session",
    payload
  );
  return response.data;
}

export async function completeEmbeddedSignupSession(
  sessionId: string,
  payload: CompleteEmbeddedSignupSessionPayload
): Promise<EmbeddedSignupSession> {
  const response = await api.post<EmbeddedSignupSession>(
    `/api/meta/accounts/embedded-signup/session/${sessionId}/complete`,
    payload
  );
  return response.data;
}

export async function failEmbeddedSignupSession(
  sessionId: string,
  payload: FailEmbeddedSignupSessionPayload
): Promise<EmbeddedSignupSession> {
  const response = await api.post<EmbeddedSignupSession>(
    `/api/meta/accounts/embedded-signup/session/${sessionId}/fail`,
    payload
  );
  return response.data;
}

export async function ingestEmbeddedSignupCallback(
  sessionId: string,
  payload: EmbeddedSignupCallbackPayload
): Promise<EmbeddedSignupSession> {
  const response = await api.post<EmbeddedSignupSession>(
    `/api/meta/accounts/embedded-signup/session/${sessionId}/callback`,
    payload
  );
  return response.data;
}

export async function subscribeMetaWebhook(
  accountId: string,
  wabaId: string,
  payload: WebhookSubscriptionPayload
): Promise<MetaWabaAccount> {
  const response = await api.post<MetaWabaAccount>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/webhook-subscription`,
    payload
  );
  return response.data;
}

export type MetaWebhookSubscriptionListParams = {
  account_id?: string;
  waba_id?: string;
  status?: MetaWebhookSubscriptionStatus;
  webhook_verification_status?: MetaWebhookVerificationStatus;
  webhook_runtime_status?: MetaWebhookRuntimeStatus;
};

export async function listMetaWebhookSubscriptions(
  params?: MetaWebhookSubscriptionListParams
): Promise<MetaWebhookSubscriptionView[]> {
  const response = await api.get<MetaWebhookSubscriptionView[]>(
    "/api/meta/accounts/webhook-subscriptions",
    {
      params
    }
  );
  return response.data;
}

export async function syncMetaPhoneNumbers(
  accountId: string,
  wabaId: string
): Promise<MetaPhoneNumberSyncResponse> {
  const response = await api.post<MetaPhoneNumberSyncResponse>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/phone-numbers/sync`
  );
  return response.data;
}

export interface DeleteMetaAccountResponse {
  account_id: string;
  waba_id: string;
  deleted: boolean;
}

export async function deleteMetaAccount(
  accountId: string,
  wabaId: string
): Promise<DeleteMetaAccountResponse> {
  const response = await api.delete<DeleteMetaAccountResponse>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}`
  );
  return response.data;
}

export interface HealthCheckResponse {
  account_id: string;
  waba_id: string;
  status: "healthy" | "unhealthy" | "error";
  detail: Record<string, unknown>;
}

export async function healthCheckMetaAccount(
  accountId: string,
  wabaId: string
): Promise<HealthCheckResponse> {
  const response = await api.post<HealthCheckResponse>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/health-check`
  );
  return response.data;
}

export interface SendTestMessagePayload {
  phone_id: string;
  to: string;
  text: string;
}

export async function sendTestMessage(
  accountId: string,
  wabaId: string,
  payload: SendTestMessagePayload
): Promise<Record<string, unknown>> {
  const response = await api.post<Record<string, unknown>>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/send-message`,
    payload
  );
  return response.data;
}

export async function queryPhoneDetail(
  accountId: string,
  wabaId: string,
  phoneId: string
): Promise<Record<string, unknown>> {
  const response = await api.post<Record<string, unknown>>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/query-phone-detail`,
    { phone_id: phoneId }
  );
  return response.data;
}

export async function queryBusinessProfile(
  accountId: string,
  wabaId: string,
  phoneId: string
): Promise<Record<string, unknown>> {
  const response = await api.post<Record<string, unknown>>(
    `/api/meta/accounts/${accountId}/wabas/${wabaId}/query-business-profile`,
    { phone_id: phoneId }
  );
  return response.data;
}

export interface GlobalWebhookConfig {
  callback_url: string;
  verify_token: string;
}

export async function getGlobalWebhookConfig(): Promise<GlobalWebhookConfig> {
  const response = await api.get<GlobalWebhookConfig>(
    "/api/meta/accounts/global-webhook-config"
  );
  return response.data;
}

export async function updateGlobalWebhookConfig(
  payload: { callback_url: string; verify_token?: string }
): Promise<GlobalWebhookConfig> {
  const response = await api.put<GlobalWebhookConfig>(
    "/api/meta/accounts/global-webhook-config",
    payload
  );
  return response.data;
}

export async function listMessageTemplates(
  accountId?: string,
  wabaId?: string,
  filters?: {
    status?: TemplateStatus;
    language?: string;
  }
): Promise<MessageTemplateView[]> {
  const response = await api.get<{ items: MessageTemplateView[] } | MessageTemplateView[]>("/api/templates", {
    params: {
      ...(accountId ? { account_id: accountId } : {}),
      ...(wabaId ? { waba_id: wabaId } : {}),
      ...(filters?.status ? { status: filters.status } : {}),
      ...(filters?.language ? { language: filters.language } : {})
    }
  });
  const list = Array.isArray(response.data) ? response.data : response.data.items ?? [];
  return list;
}

export interface GroupedTemplates {
  global_templates: MessageTemplateView[];
  agency_templates: MessageTemplateView[];
}

export async function listGroupedTemplates(): Promise<GroupedTemplates> {
  const response = await api.get<GroupedTemplates>("/api/templates");
  return response.data;
}

export async function listTemplateSendLogs(params?: {
  account_id?: string;
  waba_id?: string;
  conversation_id?: string;
  external_conversation_id?: string;
  internal_conversation_id?: string;
  template_id?: string;
  phone_number_id?: string;
  status?: TemplateSendStatus;
  error_code?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}): Promise<TemplateSendLogView[]> {
  const response = await api.get<TemplateSendLogView[]>("/api/templates/send-logs", {
    params: params
  });
  return response.data;
}

export async function getTemplateStatsSummary(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  category?: TemplateCategory;
  language?: string;
  date_from?: string;
  date_to?: string;
}): Promise<TemplateStatsSummary> {
  const response = await api.get<TemplateStatsSummary>("/api/templates/stats/summary", {
    params
  });
  return response.data;
}

export async function listTemplateDailyStats(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  category?: TemplateCategory;
  language?: string;
  date_from?: string;
  date_to?: string;
}): Promise<TemplateStatsDailyRow[]> {
  const response = await api.get<TemplateStatsDailyRow[]>("/api/templates/stats/daily", {
    params
  });
  return response.data;
}

export async function rebuildTemplateStats(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<TemplateStatsRebuildResponse> {
  const response = await api.post<TemplateStatsRebuildResponse>(
    "/api/templates/stats/rebuild",
    undefined,
    {
      params
    }
  );
  return response.data;
}

export async function getTemplateAnalytics(
  templateId: string,
  params?: {
    waba_id?: string;
    phone_number_id?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<TemplateStatsDetailResponse> {
  const response = await api.get<TemplateStatsDetailResponse>(
    `/api/templates/${templateId}/analytics`,
    {
      params
    }
  );
  return response.data;
}

export async function createTemplateDraft(
  payload: TemplateDraftPayload
): Promise<MessageTemplateView> {
  const response = await api.post<MessageTemplateView>("/api/templates/drafts", payload);
  return response.data;
}

export async function updateTemplateDraft(
  templateId: string,
  payload: TemplateDraftUpdatePayload
): Promise<MessageTemplateView> {
  const response = await api.patch<MessageTemplateView>(
    `/api/templates/${templateId}/draft`,
    payload
  );
  return response.data;
}

export async function updateTemplateStatus(
  templateId: string,
  payload: TemplateStatusUpdatePayload
): Promise<MessageTemplateView> {
  const response = await api.post<MessageTemplateView>(
    `/api/templates/${templateId}/status`,
    payload
  );
  return response.data;
}

export async function submitTemplate(
  templateId: string
): Promise<TemplateSubmitResponse> {
  const response = await api.post<TemplateSubmitResponse>(
    `/api/templates/${templateId}/submit`
  );
  return response.data;
}

export async function syncTemplates(
  payload: TemplateSyncPayload
): Promise<TemplateSyncResponse> {
  const response = await api.post<TemplateSyncResponse>("/api/templates/sync", payload);
  return response.data;
}

export async function sendTemplateMessage(
  templateId: string,
  payload: TemplateSendPayload
): Promise<TemplateSendResponse> {
  const response = await api.post<TemplateSendResponse>(
    `/api/templates/${templateId}/send`,
    payload
  );
  return response.data;
}

export async function listMediaAssets(params?: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  asset_type?: MediaAssetType;
  is_active?: boolean;
  query?: string;
  tag?: string;
}): Promise<MediaAssetView[]> {
  const response = await api.get<MediaAssetView[]>("/api/media/assets", {
    params
  });
  return response.data;
}

export async function createMediaAsset(
  payload: MediaAssetCreatePayload
): Promise<MediaAssetView> {
  const response = await api.post<MediaAssetView>("/api/media/assets", payload);
  return response.data;
}

export async function uploadMediaAsset(
  payload: MediaAssetUploadPayload
): Promise<MediaAssetView> {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("account_id", payload.account_id);

  if (payload.waba_id) {
    formData.append("waba_id", payload.waba_id);
  }
  if (payload.phone_number_id) {
    formData.append("phone_number_id", payload.phone_number_id);
  }
  if (payload.name) {
    formData.append("name", payload.name);
  }
  if (payload.asset_type) {
    formData.append("asset_type", payload.asset_type);
  }
  if (payload.mime_type) {
    formData.append("mime_type", payload.mime_type);
  }
  if (payload.source) {
    formData.append("source", payload.source);
  }
  for (const tag of payload.tags ?? []) {
    formData.append("tags", tag);
  }

  const response = await api.post<MediaAssetView>("/api/media/assets/upload", formData);
  return response.data;
}

export async function updateMediaAsset(
  assetId: string,
  payload: MediaAssetUpdatePayload
): Promise<MediaAssetView> {
  const response = await api.patch<MediaAssetView>(
    `/api/media/assets/${assetId}`,
    payload
  );
  return response.data;
}

export async function getMediaAssetDetail(
  assetId: string
): Promise<MediaAssetDetailResponse> {
  const response = await api.get<MediaAssetDetailResponse>(
    `/api/media/assets/${assetId}`
  );
  return response.data;
}

export async function syncMediaAsset(
  assetId: string,
  payload: MediaAssetSyncPayload
): Promise<MediaAssetSyncResponse> {
  const response = await api.post<MediaAssetSyncResponse>(
    `/api/media/assets/${assetId}/sync`,
    payload
  );
  return response.data;
}

export async function sendConversationMediaMessage(
  accountId: string,
  conversationId: string,
  payload: MediaAssetSendPayload
): Promise<MediaAssetSendResponse> {
  const response = await api.post<MediaAssetSendResponse>(
    `/api/conversations/${accountId}/${conversationId}/messages/media`,
    payload
  );
  return response.data;
}

export async function registerRuntimeAgent(
  payload: RegisterAgentPayload
): Promise<RuntimeAgent> {
  const response = await api.post<RuntimeAgent>("/api/runtime/agents", payload);
  return response.data;
}

export async function setRuntimeAgentStatus(
  agentId: string,
  payload: AgentStatusPayload,
  accountId?: string
): Promise<RuntimeAgent> {
  const response = await api.post<RuntimeAgent>(
    `/api/runtime/agents/${agentId}/status`,
    payload,
    {
      params: accountId ? { account_id: accountId } : undefined,
    }
  );
  return response.data;
}

/** STUB-002: List agent presence (Redis online status) */
export type AgentPresenceRecord = {
  account_id: string | null;
  agent_id: string;
  status: string;
  last_heartbeat: number;
};

export async function listAgentPresence(accountId?: string): Promise<AgentPresenceRecord[]> {
  const response = await api.get<AgentPresenceRecord[]>("/api/agents/presence", {
    params: accountId ? { account_id: accountId } : undefined,
  });
  return response.data;
}

/** STUB-002: Set agent online (Redis presence) */
export async function setAgentOnline(
  agentId: string,
  accountId?: string
): Promise<AgentPresenceRecord> {
  const response = await api.post<AgentPresenceRecord>("/api/agents/presence/online", undefined, {
    params: { agent_id: agentId, ...(accountId ? { account_id: accountId } : {}) },
  });
  return response.data;
}

/** STUB-002: Set agent offline (Redis presence) */
export async function setAgentOffline(
  agentId: string,
  accountId?: string
): Promise<{ agent_id: string; status: string }> {
  const response = await api.post<{ agent_id: string; status: string }>(
    "/api/agents/presence/offline",
    undefined,
    {
      params: { agent_id: agentId, ...(accountId ? { account_id: accountId } : {}) },
    }
  );
  return response.data;
}

export async function sendMockInboundMessage(
  payload: MockInboundPayload
): Promise<void> {
  await api.post("/dev/mock/inbound-message", payload);
}

export async function sendOutboundMessage(
  accountId: string,
  conversationId: string,
  payload: OutboundPayload
): Promise<void> {
  await api.post(
    `/api/conversations/${accountId}/${conversationId}/messages/outbound`,
    payload
  );
}

export async function translateMessage(
  accountId: string,
  conversationId: string,
  messageId: string
): Promise<{ translated_text: string | null; translated_language_code: string | null }> {
  const response = await api.post<{ translated_text: string | null; translated_language_code: string | null }>(
    `/api/conversations/${accountId}/${conversationId}/messages/${messageId}/translate`
  );
  return response.data;
}

export async function batchTranslateMessages(
  accountId: string,
  conversationId: string
): Promise<{ count: number; translations: Record<string, string> }> {
  const response = await api.post<{ count: number; translations: Record<string, string> }>(
    `/api/conversations/${accountId}/${conversationId}/messages/translate-batch`,
    null,
    { timeout: 60000 }
  );
  return response.data;
}

export async function translateOutboundPreview(
  accountId: string,
  conversationId: string,
  text: string,
  targetLanguage: string
): Promise<{
  original_text: string;
  translated_text: string;
  source_language: string;
  target_language: string;
  was_translated: boolean;
}> {
  const response = await api.post<{
    original_text: string;
    translated_text: string;
    source_language: string;
    target_language: string;
    was_translated: boolean;
  }>(
    `/api/conversations/${accountId}/${conversationId}/messages/translate-outbound`,
    { text, target_language: targetLanguage }
  );
  return response.data;
}

export async function setConversationAiEnabled(
  accountId: string,
  conversationId: string,
  payload: AiTogglePayload
): Promise<RuntimeConversationState> {
  const response = await api.post<RuntimeConversationState>(
    `/api/runtime/conversations/${conversationId}/ai`,
    payload,
    {
      params: { account_id: accountId }
    }
  );
  return response.data;
}

export async function setGlobalAiEnabled(
  payload: AiTogglePayload
): Promise<RuntimeState> {
  const response = await api.post<RuntimeState>("/api/runtime/ai/global", payload);
  return response.data;
}

export async function setAccountAiEnabled(
  accountId: string,
  payload: AiTogglePayload
): Promise<RuntimeAccountState> {
  const response = await api.post<RuntimeAccountState>(
    `/api/runtime/accounts/${accountId}/ai`,
    payload
  );
  return response.data;
}

export async function setConversationManagementMode(
  accountId: string,
  conversationId: string,
  payload: HandoverPayload
): Promise<RuntimeConversationState> {
  const response = await api.post<RuntimeConversationState>(
    `/api/runtime/conversations/${conversationId}/handover`,
    payload,
    {
      params: { account_id: accountId }
    }
  );
  return response.data;
}

export async function assignConversation(
  accountId: string,
  conversationId: string,
  payload: AssignmentPayload
): Promise<RuntimeConversationState> {
  const response = await api.post<RuntimeConversationState>(
    `/api/conversations/${accountId}/${conversationId}/assignment`,
    payload
  );
  return response.data;
}

export async function closeConversation(
  accountId: string,
  conversationId: string,
  payload: CloseConversationPayload
): Promise<RuntimeConversationState> {
  const response = await api.post<RuntimeConversationState>(
    `/api/conversations/${accountId}/${conversationId}/close`,
    payload
  );
  return response.data;
}

export async function reopenConversation(
  accountId: string,
  conversationId: string,
  payload: CloseConversationPayload
): Promise<RuntimeConversationState> {
  const response = await api.post<RuntimeConversationState>(
    `/api/conversations/${accountId}/${conversationId}/reopen`,
    payload
  );
  return response.data;
}

export function isApiFeatureUnavailable(error: unknown): boolean {
  return (
    axios.isAxiosError(error) &&
    error.response?.status === 405
  );
}

function shouldFallbackToMock(error: unknown): boolean {
  return (
    (axios.isAxiosError(error) && !error.response) ||
    isApiFeatureUnavailable(error)
  );
}

export async function getEcommerceOrderDetail(
  accountId: string,
  orderId: string
): Promise<EcommerceOrderLookupResult> {
  try {
    const response = await api.get<EcommerceOrderDetail>(
      `/api/ecommerce/orders/${encodeURIComponent(orderId)}`,
      {
        params: { account_id: accountId }
      }
    );
    return {
      source: "api",
      data: response.data
    };
  } catch (error) {
    if (shouldFallbackToMock(error)) {
      const mockOrder = findMockOrderDetail(accountId, orderId);
      if (mockOrder) {
        return {
          source: "frontend_mock",
          data: mockOrder
        };
      }
    }
    throw error;
  }
}

export async function updatePlatformUser(
  userId: string,
  payload: { display_name?: string; language_code?: string }
): Promise<PlatformUser> {
  const response = await api.patch<PlatformUser>(`/api/platform/users/${userId}`, payload);
  return response.data;
}

export type MessageTemplateCreatePayload = {
  name: string;
  category: string;
  language: string;
  content: string;
};

export async function createMessageTemplate(
  payload: MessageTemplateCreatePayload
): Promise<MessageTemplateView> {
  const response = await api.post<MessageTemplateView>("/api/templates", payload);
  return response.data;
}

export async function syncMetaTemplates(): Promise<{ synced: number; failed: number }> {
  const response = await api.post<{ synced: number; failed: number }>("/api/templates/sync-meta");
  return response.data;
}

export type MetaAccountCreatePayload = {
  display_name: string;
  waba_id: string;
  phone_number: string;
  onboarding_mode: "manual" | "embedded_signup";
};

export async function createMetaAccount(
  payload: MetaAccountCreatePayload
): Promise<MetaWabaAccount> {
  const response = await api.post<MetaWabaAccount>("/api/meta/accounts", payload);
  return response.data;
}

export async function getEcommerceTrackingDetail(
  accountId: string,
  trackingNumber: string
): Promise<EcommerceTrackingLookupResult> {
  try {
    const response = await api.get<EcommerceTrackingDetail>(
      `/api/ecommerce/shipments/${encodeURIComponent(trackingNumber)}`,
      {
        params: { account_id: accountId }
      }
    );
    return {
      source: "api",
      data: response.data
    };
  } catch (error) {
    if (shouldFallbackToMock(error)) {
      const mockTracking = findMockTrackingDetail(accountId, trackingNumber);
      if (mockTracking) {
        return {
          source: "frontend_mock",
          data: mockTracking
        };
      }
    }
    throw error;
  }
}

// ── Dashboard APIs ──

export interface DashboardSummaryResponse {
  total_conversations: number;
  ai_managed: number;
  human_managed: number;
  paused: number;
  total_messages_today: number;
  ai_reply_rate: number;
}

export interface DashboardTodoResponse {
  pending_review_count: number;
  handover_recommended_count: number;
  paused_conversation_count: number;
}

export interface DailyAiPerformance {
  date: string;
  reply_rate: number;
  fallback_rate: number;
  handover_rate: number;
}

export interface AiPerformanceResponse {
  daily: DailyAiPerformance[];
}

export interface TopIntentItem {
  name: string;
  count: number;
  percentage: number;
}

export interface TopIntentsResponse {
  intents: TopIntentItem[];
}

export async function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  const response = await api.get<DashboardSummaryResponse>("/api/dashboard/summary");
  return response.data;
}

export async function getDashboardTodo(): Promise<DashboardTodoResponse> {
  const response = await api.get<DashboardTodoResponse>("/api/dashboard/todo");
  return response.data;
}

export async function getAiPerformance(params?: { days?: number }): Promise<AiPerformanceResponse> {
  const response = await api.get<AiPerformanceResponse>("/api/dashboard/ai-performance", { params });
  return response.data;
}

export async function getTopIntents(params?: { days?: number; limit?: number }): Promise<TopIntentsResponse> {
  const response = await api.get<TopIntentsResponse>("/api/dashboard/top-intents", { params });
  return response.data;
}

// ── Platform User APIs ──

export async function deletePlatformUser(userId: string): Promise<void> {
  await api.delete(`/api/platform/users/${userId}`);
}

// ── Review APIs ──

export async function updateReviewStatus(
  reviewId: string,
  action: "approve" | "reject",
  payload?: { reviewer_note?: string }
): Promise<void> {
  await api.post(`/api/reviews/${reviewId}/${action}`, payload);
}

export async function batchReviewAction(
  reviewIds: string[],
  action: "approve" | "reject",
  payload?: { reviewer_note?: string }
): Promise<{ success_count: number; failed_count: number }> {
  const response = await api.post(`/api/reviews/batch-${action}`, {
    review_ids: reviewIds,
    ...payload,
  });
  return response.data;
}

// ── Customer lifecycle APIs ──

export async function blockCustomer(customerId: string, accountId: string): Promise<{ customer_id: string; account_id: string; lifecycle_status: string; previous_status: string }> {
  const response = await api.patch(`/api/customers/${customerId}/lifecycle-status`, {
    lifecycle_status: "blacklisted",
  }, { params: { account_id: accountId } });
  return response.data;
}

export async function unblockCustomer(customerId: string, accountId: string): Promise<{ customer_id: string; account_id: string; lifecycle_status: string; previous_status: string }> {
  const response = await api.patch(`/api/customers/${customerId}/lifecycle-status`, {
    lifecycle_status: "active",
  }, { params: { account_id: accountId } });
  return response.data;
}

export interface CustomerSummaryResponse {
  customer: { id: string; public_user_id: string; display_name: string | null; language: string; created_at: string | null; lifecycle_status: string; registration_ip: string | null; registration_ips: string[]; multi_ip: boolean };
  wallet: { balance: number; total_recharged: number; total_withdrawn: number; recent_transactions: Array<{ type: string; amount: number; direction: string; created_at: string | null }> };
  member_status: { verification: { status: string; request_type?: string; updated_at?: string }; whatsapp_binding: { status: string; phone_number?: string; updated_at?: string } };
  member_profile: CustomerMemberProfileSummary | null;
  conversations: { total: number; open: number; items: Array<Record<string, unknown>> };
  tickets: { total: number; open: number; items: Array<Record<string, unknown>> };
  tags: string[];
}

export interface CustomerMemberProfileSummary {
  member_profile_id: string | null;
  member_no: string | null;
  current_owner_agency_id: string | null;
  current_owner_staff_user_id: string | null;
  current_owner_agency_member_id: string | null;
  current_owner_assignment_id: string | null;
  owner_assigned_at: string | null;
  current_ai_agent_id: string | null;
  current_ai_assignment_id: string | null;
  ai_assigned_at: string | null;
  registration_entry_link_id: string | null;
  registration_ai_agent_id: string | null;
  registration_staff_user_id: string | null;
  registration_channel: string | null;
  registration_source_type: string | null;
  attribution_status: string;
}

export async function getCustomerSummary(customerId: string, accountId?: string): Promise<CustomerSummaryResponse> {
  const params: Record<string, string> = {};
  if (accountId) params.account_id = accountId;
  const response = await api.get<CustomerSummaryResponse>(`/api/customers/${customerId}/summary`, { params });
  return response.data;
}

/** Search messages within a conversation by keyword query. */
export async function searchConversationMessages(
  accountId: string,
  conversationId: string,
  query: string,
  limit?: number,
  offset?: number
): Promise<ConversationMessage[]> {
  const params: Record<string, string | number> = { q: query };
  if (limit !== undefined) params.limit = limit;
  if (offset !== undefined) params.offset = offset;
  const response = await api.get<ConversationMessage[]>(
    `/api/conversations/${accountId}/${conversationId}/messages/search`,
    { params }
  );
  return response.data;
}

/** Brief representation of a customer conversation returned by the by-customer endpoint. */
export interface CustomerConversationBrief {
  conversation_id: string;
  account_id: string;
  customer_id: string;
  status: string;
  management_mode: string;
  last_message_at: string | null;
  last_message_preview: string | null;
}

/** List historical conversations for a specific customer, optionally excluding one conversation. */
export async function listCustomerConversations(
  accountId: string,
  customerId: string,
  excludeConversationId?: string,
  limit?: number
): Promise<CustomerConversationBrief[]> {
  const params: Record<string, string | number> = { account_id: accountId };
  if (excludeConversationId) params.exclude_conversation_id = excludeConversationId;
  if (limit !== undefined) params.limit = limit;
  const response = await api.get<CustomerConversationBrief[]>(
    `/api/conversations/by-customer/${customerId}`,
    { params }
  );
  return response.data;
}

/** Result returned after forwarding a message to another conversation. */
export interface ForwardMessageResult {
  message_id: string;
  conversation_id: string;
  account_id: string;
}

/** Forward a message from one conversation to another. */
export async function forwardMessage(
  accountId: string,
  conversationId: string,
  messageId: string,
  targetConversationId: string,
  includeContext?: boolean
): Promise<ForwardMessageResult> {
  const response = await api.post<ForwardMessageResult>(
    `/api/conversations/${accountId}/${conversationId}/messages/${messageId}/forward`,
    {
      target_conversation_id: targetConversationId,
      include_context: includeContext ?? false
    }
  );
  return response.data;
}

/** AI-powered sentiment analysis for a conversation. */
export interface ConversationSentiment {
  sentiment: 'angry' | 'anxious' | 'satisfied' | 'neutral';
  confidence: number;
  summary: string;
}

/** Get the current sentiment analysis for a conversation. */
export async function getConversationSentiment(
  accountId: string,
  conversationId: string
): Promise<ConversationSentiment> {
  const response = await api.get<ConversationSentiment>(
    `/api/conversations/${accountId}/${conversationId}/sentiment`
  );
  return response.data;
}

/** SLA timing information for a conversation. */
export interface ConversationSla {
  waiting_seconds: number;
  threshold_warning: number;
  threshold_critical: number;
  is_overdue: boolean;
  last_inbound_at: string | null;
  last_agent_reply_at: string | null;
}

/** Get SLA status and timing details for a conversation. */
export async function getConversationSla(
  accountId: string,
  conversationId: string
): Promise<ConversationSla> {
  const response = await api.get<ConversationSla>(
    `/api/conversations/${accountId}/${conversationId}/sla`
  );
  return response.data;
}

/** Preview text returned by the AI reply generator. */
export interface AiReplyPreview {
  preview_text: string;
  prompt_tokens?: number;
}

/** Request an AI-generated reply preview for a conversation. */
export async function getAiReplyPreview(
  accountId: string,
  conversationId: string
): Promise<AiReplyPreview> {
  const response = await api.post<AiReplyPreview>(
    `/api/conversations/${accountId}/${conversationId}/ai-preview`
  );
  return response.data;
}

/** A note attached to a conversation by an agent. */
export interface ConversationNote {
  id: string;
  account_id: string;
  conversation_id: string;
  content: string;
  agent_id: string;
  agent_name: string | null;
  created_at: string;
  updated_at?: string | null;
}

/** List all notes for a conversation. */
export async function listConversationNotes(
  accountId: string,
  conversationId: string
): Promise<ConversationNote[]> {
  const response = await api.get<ConversationNote[]>(
    `/api/conversations/${accountId}/${conversationId}/notes`
  );
  return response.data;
}

/** Create a note on a conversation. */
export async function createConversationNote(
  accountId: string,
  conversationId: string,
  content: string,
  agentName?: string
): Promise<ConversationNote> {
  const response = await api.post<ConversationNote>(
    `/api/conversations/${accountId}/${conversationId}/notes`,
    { content, agent_name: agentName }
  );
  return response.data;
}

/** Delete a note from a conversation. */
export async function deleteConversationNote(
  accountId: string,
  conversationId: string,
  noteId: string
): Promise<void> {
  await api.delete(
    `/api/conversations/${accountId}/${conversationId}/notes/${noteId}`
  );
}

/** Update a conversation note. */
export async function updateConversationNote(
  accountId: string,
  conversationId: string,
  noteId: string,
  content: string
): Promise<ConversationNote> {
  const response = await api.put<ConversationNote>(
    `/api/conversations/${accountId}/${conversationId}/notes/${noteId}`,
    { content }
  );
  return response.data;
}

/** A pre-defined canned response template. */
export interface CannedResponseItem {
  id: string;
  account_id: string | null;
  title: string;
  content: string;
  category: string;
  variables: string[];
  is_active: boolean;
  created_by: string | null;
}

/** List canned responses, optionally filtered by account, category, or search term. */
export async function listCannedResponses(
  accountId?: string,
  category?: string,
  search?: string
): Promise<CannedResponseItem[]> {
  const params: Record<string, string> = {};
  if (accountId) params.account_id = accountId;
  if (category) params.category = category;
  if (search) params.search = search;
  const response = await api.get<CannedResponseItem[]>('/api/canned-responses', { params });
  return response.data;
}

/** Create a new canned response. */
export async function createCannedResponse(
  data: { account_id?: string; title: string; content: string; category: string; variables?: string[] }
): Promise<CannedResponseItem> {
  const response = await api.post<CannedResponseItem>('/api/canned-responses', data);
  return response.data;
}

/** Update an existing canned response. */
export async function updateCannedResponse(
  id: string,
  data: { title?: string; content?: string; category?: string; variables?: string[]; is_active?: boolean }
): Promise<CannedResponseItem> {
  const response = await api.put<CannedResponseItem>(`/api/canned-responses/${id}`, data);
  return response.data;
}

/** Delete a canned response. */
export async function deleteCannedResponse(id: string): Promise<void> {
  await api.delete(`/api/canned-responses/${id}`);
}

/** Get tags associated with a conversation. */
export async function getConversationTags(
  accountId: string,
  conversationId: string
): Promise<{ tags: string[] }> {
  const response = await api.get<{ tags: string[] }>(
    `/api/conversations/${accountId}/${conversationId}/tags`
  );
  return response.data;
}

/** Update tags for a conversation (replaces all tags). */
export async function updateConversationTags(
  accountId: string,
  conversationId: string,
  tags: string[]
): Promise<{ tags: string[] }> {
  const response = await api.put<{ tags: string[] }>(
    `/api/conversations/${accountId}/${conversationId}/tags`,
    { tags }
  );
  return response.data;
}

/** Current status of an agent. */
export interface AgentStatus {
  agent_id: string;
  status: 'online' | 'busy' | 'away' | 'offline';
}

/** Set the status of an agent (online / busy / away / offline). */
export async function setAgentStatus(
  agentId: string,
  status: string,
  accountId?: string
): Promise<AgentStatus> {
  const params: Record<string, string> = {};
  if (accountId) params.account_id = accountId;
  const response = await api.post<AgentStatus>(
    `/api/agents/${agentId}/status`,
    { status },
    { params }
  );
  return response.data;
}

// ── Batch operations ──

/** Result of a single batch operation item. */
export interface BatchOperationResult {
  conversation_id: string;
  status: string; // "success" | "failed"
  error: string | null;
}

/** Response from a batch operation endpoint. */
export interface BatchOperationResponse {
  success_count: number;
  failed_count: number;
  results: BatchOperationResult[];
}

/** Batch handover conversations to human management. */
export async function batchHandoverConversations(
  conversationIds: string[],
  reason?: string
): Promise<BatchOperationResponse> {
  const response = await api.post<BatchOperationResponse>(
    '/api/conversations/batch-handover',
    { conversation_ids: conversationIds, reason }
  );
  return response.data;
}

/** Batch restore AI management for conversations. */
export async function batchRestoreAIConversations(
  conversationIds: string[],
  reason?: string
): Promise<BatchOperationResponse> {
  const response = await api.post<BatchOperationResponse>(
    '/api/conversations/batch-restore-ai',
    { conversation_ids: conversationIds, reason }
  );
  return response.data;
}

/** Batch close conversations. */
export async function batchCloseConversations(
  conversationIds: string[],
  reason?: string
): Promise<BatchOperationResponse> {
  const response = await api.post<BatchOperationResponse>(
    '/api/conversations/batch-close',
    { conversation_ids: conversationIds, reason }
  );
  return response.data;
}

/** Batch assign conversations to an agent. */
export async function batchAssignConversationsByAgent(
  conversationIds: string[],
  agentId: string,
  reason?: string
): Promise<BatchOperationResponse> {
  const response = await api.post<BatchOperationResponse>(
    '/api/conversations/batch-assign',
    { conversation_ids: conversationIds, agent_id: agentId, reason }
  );
  return response.data;
}

// ── Batch metadata (tags + sentiment + SLA) ──

export interface BatchMetadataItem {
  account_id: string;
  conversation_id: string;
  tags: string[];
  sentiment: string | null;
  sentiment_confidence: number | null;
  sla_overdue: boolean;
  sla_waiting_seconds: number;
  error: string | null;
}

export interface BatchMetadataResponse {
  items: BatchMetadataItem[];
}

/** Get tags, sentiment, and SLA for multiple conversations in a single request. */
export async function getConversationsMetadataBatch(
  ids: string[]
): Promise<BatchMetadataResponse> {
  const response = await api.get<BatchMetadataResponse>(
    '/api/conversations/metadata/batch',
    { params: { ids: ids.join(',') } }
  );
  return response.data;
}

// ── AI Chat Config Types ──
export interface AIChatConfig {
  id?: string;
  agency_id?: string | null;
  // 类别1: 系统提示词
  system_prompt: string;
  prompt_append_context: boolean;
  prompt_variables: Record<string, string>;
  // 类别2: 模型参数
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  stop_sequences: string[];
  // 类别3: 会话行为
  context_window_messages: number;
  context_window_tokens: number;
  conversation_memory: boolean;
  greeting_message: string;
  off_hours_message: string;
  off_hours_start: string;
  off_hours_end: string;
  off_hours_timezone: string;
  // 类别4: 自动回复
  auto_reply_enabled: boolean;
  auto_reply_delay_seconds: number;
  auto_reply_keywords: Record<string, string>;
  auto_reply_fallback: string;
  duplicate_message_filter: boolean;
  // 类别5: 转人工
  auto_escalation_enabled: boolean;
  escalation_keywords: string[];
  escalation_max_failures: number;
  escalation_sentiment_threshold: number;
  escalation_max_rounds: number;
  escalation_message: string;
  // 类别6: 安全
  blocked_topics: string[];
  content_filter_enabled: boolean;
  pii_protection: boolean;
  max_response_length: number;
  language_lock: boolean;
  // 类别7: 高级
  response_format: string;
  inject_brand_info: boolean;
  inject_knowledge_base: boolean;
  debug_mode: boolean;
  // 类别8: AI 工具调用
  tools_enabled: boolean;
  enabled_tools: string[];
  max_tool_calls_per_session: number;
  identity_verify_method: string;
  identity_auto_verify: boolean;
  tool_call_timeout_seconds: number;
}

export type TestChatMessage = {
  role: "user" | "assistant" | "tool_call";
  text: string;
  tool_calls?: string;
};

export type TestChatResponse = {
  reply_text: string;
  system_prompt: string;
  model_params: Record<string, number>;
  tools_enabled: boolean;
  tool_count: number;
  config_agency_id: string | null;
};

export type AvailableToolsResponse = {
  tools: Array<{
    type: "function";
    function: {
      name: string;
      description: string;
      parameters: Record<string, unknown>;
    };
  }>;
  default_allowed_tools: string[];
  tool_count: number;
};

export async function getSystemAIChatConfig(): Promise<AIChatConfig> {
  const response = await api.get<AIChatConfig>("/api/ai-chat-config/system");
  return response.data;
}

export async function saveSystemAIChatConfig(data: AIChatConfig): Promise<AIChatConfig> {
  const response = await api.put<AIChatConfig>("/api/ai-chat-config/system", data);
  return response.data;
}

export async function getAgencyAIChatConfig(agencyId: string): Promise<AIChatConfig> {
  const response = await api.get<AIChatConfig>(`/api/ai-chat-config/agency/${agencyId}`);
  return response.data;
}

export async function saveAgencyAIChatConfig(
  agencyId: string,
  data: AIChatConfig
): Promise<AIChatConfig> {
  const response = await api.put<AIChatConfig>(`/api/ai-chat-config/agency/${agencyId}`, data);
  return response.data;
}

export async function resetAgencyAIChatConfig(agencyId: string): Promise<AIChatConfig> {
  const response = await api.delete<AIChatConfig>(`/api/ai-chat-config/agency/${agencyId}`);
  return response.data;
}

export async function testAIChat(
  userMessage: string,
  agencyId?: string
): Promise<TestChatResponse> {
  const response = await api.post<TestChatResponse>("/api/ai-chat-config/test", {
    agency_id: agencyId || null,
    user_message: userMessage,
    customer_language: "zh-CN",
    conversation_history: [],
  });
  return response.data;
}

export async function previewAIChatPrompt(
  agencyId?: string,
  customerLanguage?: string
): Promise<{ prompt: string; variables: Record<string, string> }> {
  const params: Record<string, string> = {};
  if (agencyId) params.agency_id = agencyId;
  params.customer_language = customerLanguage || "auto";
  const response = await api.get<{ prompt: string; variables: Record<string, string> }>(
    "/api/ai-chat-config/preview-prompt",
    { params }
  );
  return response.data;
}

export async function listAvailableTools(): Promise<AvailableToolsResponse> {
  const response = await api.get<AvailableToolsResponse>("/api/ai-chat-config/tools");
  return response.data;
}

export async function listAgencies(): Promise<Array<{ id: string; name: string }>> {
  try {
    const response = await api.get<Array<{ id: string; name: string }>>("/api/agents");
    return response.data;
  } catch {
    return [
      { id: "agency-1", name: "默认代理商" },
      { id: "agency-2", name: "测试代理商" },
    ];
  }
}

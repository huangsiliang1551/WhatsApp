import type {
  AlertsPagePrefill,
  AuditPagePrefill,
  CustomersPagePrefill,
  EvidencePagePrefill,
  IntegrationsPagePrefill,
  IdentitySyncPagePrefill,
  ApiWebhooksPagePrefill,
  MetaAccountsPagePrefill,
  MemberAccessPagePrefill,
  MembersPagePrefill,
  NotificationsPagePrefill,
  OrganizationPagePrefill,
  OperationsPagePrefill,
  AppPageId,
  ProviderEventsPagePrefill,
  AccessControlPagePrefill,
  SecuritySettingsPagePrefill,
  SitesPagePrefill,
  SettingsPagePrefill,
  SystemLogsPagePrefill,
  TemplatePagePrefill,
  WhatsAppStatsPagePrefill,
  UsersPagePrefill,
  WorkspacePagePrefill,
} from "../stores/appStore";
import type { EvidenceSourceKind } from "../types/evidenceCenter";
import type { SystemLogSeverity, SystemLogSourceKind } from "../types/systemLogs";

type WorkspacePrefillPayload = Omit<WorkspacePagePrefill, "nonce">;
type AuditPrefillPayload = Omit<AuditPagePrefill, "nonce">;
type WhatsAppStatsPrefillPayload = Omit<WhatsAppStatsPagePrefill, "nonce">;
type ProviderEventsPrefillPayload = Omit<ProviderEventsPagePrefill, "nonce">;
type IntegrationsPrefillPayload = Omit<IntegrationsPagePrefill, "nonce">;
type ApiWebhooksPrefillPayload = Omit<ApiWebhooksPagePrefill, "nonce">;
type SystemLogsPrefillPayload = Omit<SystemLogsPagePrefill, "nonce">;
type AlertsPrefillPayload = Omit<AlertsPagePrefill, "nonce">;
type OperationsPrefillPayload = Omit<OperationsPagePrefill, "nonce">;
type CustomersPrefillPayload = Omit<CustomersPagePrefill, "nonce">;
type NotificationsPrefillPayload = Omit<NotificationsPagePrefill, "nonce">;
type UsersPrefillPayload = Omit<UsersPagePrefill, "nonce">;
type MemberAccessPrefillPayload = Omit<MemberAccessPagePrefill, "nonce">;
type MembersPrefillPayload = Omit<MembersPagePrefill, "nonce">;
type AccessControlPrefillPayload = Omit<AccessControlPagePrefill, "nonce">;
type SecuritySettingsPrefillPayload = Omit<SecuritySettingsPagePrefill, "nonce">;
type IdentitySyncPrefillPayload = Omit<IdentitySyncPagePrefill, "nonce">;
type OrganizationPrefillPayload = Omit<OrganizationPagePrefill, "nonce">;
type SettingsPrefillPayload = Omit<SettingsPagePrefill, "nonce">;
type SitesPrefillPayload = Omit<SitesPagePrefill, "nonce">;
type TemplatePrefillPayload = Omit<TemplatePagePrefill, "nonce">;
type MetaAccountsPrefillPayload = Omit<MetaAccountsPagePrefill, "nonce">;
type EvidencePrefillPayload = Omit<EvidencePagePrefill, "nonce">;
const EVIDENCE_SOURCE_KINDS: EvidenceSourceKind[] = ["audit", "provider", "queue", "webhook"];
const SYSTEM_LOG_SEVERITIES: SystemLogSeverity[] = ["info", "warning", "critical"];
const SYSTEM_LOG_SOURCE_KINDS: SystemLogSourceKind[] = ["audit", "provider", "queue"];

export type AdminPagePrefillMap = {
  conversations: WorkspacePrefillPayload | null;
  audit: AuditPrefillPayload | null;
  whatsapp_stats: WhatsAppStatsPrefillPayload | null;
  provider_events: ProviderEventsPrefillPayload | null;
  integrations: IntegrationsPrefillPayload | null;
  api_webhooks: ApiWebhooksPrefillPayload | null;
  system_logs: SystemLogsPrefillPayload | null;
  alerts: AlertsPrefillPayload | null;
  operations: OperationsPrefillPayload | null;
  customers: CustomersPrefillPayload | null;
  notifications: NotificationsPrefillPayload | null;
  users: UsersPrefillPayload | null;
  member_access: MemberAccessPrefillPayload | null;
  members: MembersPrefillPayload | null;
  access_control: AccessControlPrefillPayload | null;
  security_settings: SecuritySettingsPrefillPayload | null;
  identity_sync: IdentitySyncPrefillPayload | null;
  organization: OrganizationPrefillPayload | null;
  sites: SitesPrefillPayload | null;
  settings: SettingsPrefillPayload | null;
  templates: TemplatePrefillPayload | null;
  meta: MetaAccountsPrefillPayload | null;
  evidence_center: EvidencePrefillPayload | null;
};

function setStringParam(
  params: URLSearchParams,
  key: string,
  value: string | null | undefined,
  defaultValue?: string
): void {
  if (!value || value === defaultValue) {
    return;
  }
  params.set(key, value);
}

function parseBoolean(value: string | null): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

function parseNumber(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseEvidenceSourceKind(value: string | null): EvidenceSourceKind | undefined {
  if (!value) {
    return undefined;
  }
  return EVIDENCE_SOURCE_KINDS.includes(value as EvidenceSourceKind)
    ? (value as EvidenceSourceKind)
    : undefined;
}

function parseSystemLogSeverity(value: string | null): SystemLogSeverity | undefined {
  if (!value) {
    return undefined;
  }
  return SYSTEM_LOG_SEVERITIES.includes(value as SystemLogSeverity)
    ? (value as SystemLogSeverity)
    : undefined;
}

function parseSystemLogSourceKind(value: string | null): SystemLogSourceKind | undefined {
  if (!value) {
    return undefined;
  }
  return SYSTEM_LOG_SOURCE_KINDS.includes(value as SystemLogSourceKind)
    ? (value as SystemLogSourceKind)
    : undefined;
}

function buildWorkspaceParams(prefill: WorkspacePrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.accountId, "all");
  setStringParam(params, "waba_id", prefill.wabaId);
  setStringParam(params, "phone_number_id", prefill.phoneNumberId);
  setStringParam(params, "conversation_key", prefill.conversationKey);
  setStringParam(params, "handover_mode", prefill.handoverMode, "all");
  setStringParam(params, "management_mode", prefill.managementMode, "all");
  setStringParam(params, "search", prefill.search);
  return params;
}

function buildAuditParams(prefill: AuditPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "waba_id", prefill.waba_id);
  setStringParam(params, "phone_number_id", prefill.phone_number_id);
  setStringParam(params, "actor_type", prefill.actor_type);
  setStringParam(params, "actor_id", prefill.actor_id);
  setStringParam(params, "action", prefill.action);
  setStringParam(params, "target_type", prefill.target_type);
  setStringParam(params, "target_id", prefill.target_id);
  setStringParam(params, "date_from", prefill.date_from);
  setStringParam(params, "date_to", prefill.date_to);
  if (typeof prefill.limit === "number" && Number.isFinite(prefill.limit)) {
    params.set("limit", String(prefill.limit));
  }
  return params;
}

function buildWhatsAppStatsParams(
  prefill: WhatsAppStatsPrefillPayload | null
): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id);
  setStringParam(params, "waba_id", prefill.waba_id);
  setStringParam(params, "phone_number_id", prefill.phone_number_id);
  setStringParam(params, "conversation_origin_type", prefill.conversation_origin_type);
  setStringParam(params, "conversation_category", prefill.conversation_category);
  setStringParam(params, "pricing_model", prefill.pricing_model);
  if (typeof prefill.billable === "boolean") {
    params.set("billable", String(prefill.billable));
  }
  if (typeof prefill.hour_bucket === "number" && Number.isFinite(prefill.hour_bucket)) {
    params.set("hour_bucket", String(prefill.hour_bucket));
  }
  setStringParam(params, "date_from", prefill.date_from);
  setStringParam(params, "date_to", prefill.date_to);
  return params;
}

function buildProviderEventsParams(
  prefill: ProviderEventsPrefillPayload | null
): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "provider_name", prefill.provider_name);
  setStringParam(params, "provider_message_id", prefill.provider_message_id);
  setStringParam(params, "external_status", prefill.external_status);
  setStringParam(params, "replay_state", prefill.replay_state);
  setStringParam(params, "waba_id", prefill.waba_id);
  setStringParam(params, "phone_number_id", prefill.phone_number_id);
  setStringParam(params, "webhook_runtime_status", prefill.webhook_runtime_status, "ALL");
  return params;
}

function buildIntegrationsParams(prefill: IntegrationsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_account_key", prefill.selected_account_key);
  return params;
}

function buildApiWebhooksParams(prefill: ApiWebhooksPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_subscription_id", prefill.selected_subscription_id);
  setStringParam(params, "selected_policy_id", prefill.selected_policy_id);
  return params;
}

function buildSystemLogsParams(prefill: SystemLogsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "severity", prefill.severity);
  setStringParam(params, "source_kind", prefill.source_kind);
  setStringParam(params, "selected_log_id", prefill.selected_log_id);
  return params;
}

function buildAlertsParams(prefill: AlertsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_alert_id", prefill.selected_alert_id);
  return params;
}

function buildOperationsParams(prefill: OperationsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  return params;
}

function buildCustomersParams(prefill: CustomersPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "query", prefill.query);
  setStringParam(params, "selected_profile_id", prefill.selected_profile_id);
  setStringParam(params, "detail_tab", prefill.detail_tab);
  return params;
}

function buildNotificationsParams(prefill: NotificationsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_channel_id", prefill.selected_channel_id);
  return params;
}

function buildUsersParams(prefill: UsersPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "site_id", prefill.site_id, "ALL");
  setStringParam(params, "lifecycle_status", prefill.lifecycle_status, "ALL");
  setStringParam(params, "search", prefill.search);
  setStringParam(params, "selected_user_id", prefill.selected_user_id);
  return params;
}

function buildMemberAccessParams(prefill: MemberAccessPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "role_key", prefill.role_key, "ALL");
  setStringParam(params, "search", prefill.search);
  setStringParam(params, "selected_binding_id", prefill.selected_binding_id);
  return params;
}

function buildMembersParams(prefill: MembersPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "status", prefill.status, "ALL");
  setStringParam(params, "selected_member_key", prefill.selected_member_key);
  if (typeof prefill.is_active === "boolean") {
    params.set("is_active", String(prefill.is_active));
  }
  return params;
}

function buildAccessControlParams(prefill: AccessControlPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_policy_id", prefill.selected_policy_id);
  return params;
}

function buildSecuritySettingsParams(
  prefill: SecuritySettingsPrefillPayload | null
): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_policy_account", prefill.selected_policy_account, "global");
  return params;
}

function buildIdentitySyncParams(prefill: IdentitySyncPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_provider_id", prefill.selected_provider_id);
  setStringParam(params, "selected_mapping_id", prefill.selected_mapping_id);
  return params;
}

function buildOrganizationParams(prefill: OrganizationPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_account_id", prefill.selected_account_id);
  return params;
}

function buildSitesParams(prefill: SitesPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "status", prefill.status, "ALL");
  setStringParam(params, "selected_site_id", prefill.selected_site_id);
  setStringParam(params, "selected_site_key", prefill.selected_site_key);
  return params;
}

function buildSettingsParams(prefill: SettingsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "all");
  setStringParam(params, "category", prefill.category, "all");
  setStringParam(params, "source_type", prefill.source_type, "all");
  setStringParam(params, "search", prefill.search);
  setStringParam(params, "selected_conversation_key", prefill.selected_conversation_key);
  return params;
}

function buildTemplateParams(prefill: TemplatePrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "waba_id", prefill.waba_id, "ALL");
  setStringParam(params, "status", prefill.status, "ALL");
  setStringParam(params, "language", prefill.language);
  setStringParam(params, "selected_template_id", prefill.selected_template_id);
  return params;
}

function buildMetaAccountsParams(prefill: MetaAccountsPrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "focused_account_id", prefill.focused_account_id, "all");
  setStringParam(params, "selected_account_key", prefill.selected_account_key);
  setStringParam(params, "tab", prefill.active_tab, "accounts");
  return params;
}

function buildEvidenceParams(prefill: EvidencePrefillPayload | null): URLSearchParams {
  const params = new URLSearchParams();
  if (!prefill) return params;
  setStringParam(params, "account_id", prefill.account_id, "ALL");
  setStringParam(params, "selected_bundle_id", prefill.selected_bundle_id);
  setStringParam(params, "source_kind", prefill.source_kind);
  return params;
}

export function buildAdminLocationKey(
  pathname: string,
  pageId: AppPageId,
  prefills: Partial<AdminPagePrefillMap>
): string {
  let resolvedPathname = pathname;
  let params = new URLSearchParams();
  if (pageId === "conversations") {
    params = buildWorkspaceParams(prefills.conversations ?? null);
  } else if (pageId === "audit") {
    params = buildAuditParams(prefills.audit ?? null);
  } else if (pageId === "whatsapp_stats") {
    params = buildWhatsAppStatsParams(prefills.whatsapp_stats ?? null);
  } else if (pageId === "provider_events") {
    params = buildProviderEventsParams(prefills.provider_events ?? null);
  } else if (pageId === "integrations") {
    params = buildIntegrationsParams(prefills.integrations ?? null);
  } else if (pageId === "api_webhooks") {
    params = buildApiWebhooksParams(prefills.api_webhooks ?? null);
  } else if (pageId === "system_logs") {
    params = buildSystemLogsParams(prefills.system_logs ?? null);
  } else if (pageId === "alerts") {
    params = buildAlertsParams(prefills.alerts ?? null);
  } else if (pageId === "operations") {
    params = buildOperationsParams(prefills.operations ?? null);
  } else if (pageId === "customers") {
    params = buildCustomersParams(prefills.customers ?? null);
  } else if (pageId === "notifications") {
    params = buildNotificationsParams(prefills.notifications ?? null);
  } else if (pageId === "users") {
    params = buildUsersParams(prefills.users ?? null);
  } else if (pageId === "member_access") {
    params = buildMemberAccessParams(prefills.member_access ?? null);
  } else if (pageId === "members") {
    params = buildMembersParams(prefills.members ?? null);
  } else if (pageId === "access_control") {
    params = buildAccessControlParams(prefills.access_control ?? null);
  } else if (pageId === "security_settings") {
    params = buildSecuritySettingsParams(prefills.security_settings ?? null);
  } else if (pageId === "identity_sync") {
    params = buildIdentitySyncParams(prefills.identity_sync ?? null);
  } else if (pageId === "organization") {
    params = buildOrganizationParams(prefills.organization ?? null);
  } else if (pageId === "sites") {
    params = buildSitesParams(prefills.sites ?? null);
  } else if (pageId === "settings") {
    params = buildSettingsParams(prefills.settings ?? null);
  } else if (pageId === "templates") {
    params = buildTemplateParams(prefills.templates ?? null);
  } else if (pageId === "meta") {
    params = buildMetaAccountsParams(prefills.meta ?? null);
  } else if (pageId === "evidence_center") {
    params = buildEvidenceParams(prefills.evidence_center ?? null);
  }
  const query = params.toString();
  return query ? `${resolvedPathname}?${query}` : resolvedPathname;
}

export function parseAdminLocationPrefill(
  pageId: AppPageId,
  search: string
):
  | WorkspacePrefillPayload
  | AuditPrefillPayload
  | WhatsAppStatsPrefillPayload
  | ProviderEventsPrefillPayload
  | IntegrationsPrefillPayload
  | ApiWebhooksPrefillPayload
  | SystemLogsPrefillPayload
  | AlertsPrefillPayload
  | OperationsPrefillPayload
  | CustomersPrefillPayload
  | NotificationsPrefillPayload
  | UsersPrefillPayload
  | MemberAccessPrefillPayload
  | MembersPrefillPayload
  | AccessControlPrefillPayload
  | SecuritySettingsPrefillPayload
  | IdentitySyncPrefillPayload
  | OrganizationPrefillPayload
  | SitesPrefillPayload
  | SettingsPrefillPayload
  | TemplatePrefillPayload
  | MetaAccountsPrefillPayload
  | EvidencePrefillPayload
  | null {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  if ([...params.keys()].length === 0) {
    return null;
  }

  if (pageId === "conversations") {
    return {
      accountId: params.get("account_id") ?? undefined,
      wabaId: params.get("waba_id") ?? undefined,
      phoneNumberId: params.get("phone_number_id") ?? undefined,
      conversationKey: params.get("conversation_key") ?? undefined,
      handoverMode:
        (params.get("handover_mode") as WorkspacePrefillPayload["handoverMode"] | null) ?? undefined,
      managementMode:
        (params.get("management_mode") as WorkspacePrefillPayload["managementMode"] | null) ?? undefined,
      search: params.get("search") ?? undefined,
    };
  }

  if (pageId === "audit") {
    return {
      account_id: params.get("account_id") ?? undefined,
      waba_id: params.get("waba_id") ?? undefined,
      phone_number_id: params.get("phone_number_id") ?? undefined,
      actor_type: params.get("actor_type") ?? undefined,
      actor_id: params.get("actor_id") ?? undefined,
      action: params.get("action") ?? undefined,
      target_type: params.get("target_type") ?? undefined,
      target_id: params.get("target_id") ?? undefined,
      date_from: params.get("date_from") ?? undefined,
      date_to: params.get("date_to") ?? undefined,
      limit: parseNumber(params.get("limit")),
    };
  }

  if (pageId === "whatsapp_stats") {
    return {
      account_id: params.get("account_id") ?? undefined,
      waba_id: params.get("waba_id") ?? undefined,
      phone_number_id: params.get("phone_number_id") ?? undefined,
      conversation_origin_type: params.get("conversation_origin_type") ?? undefined,
      conversation_category: params.get("conversation_category") ?? undefined,
      pricing_model: params.get("pricing_model") ?? undefined,
      billable: parseBoolean(params.get("billable")),
      hour_bucket: parseNumber(params.get("hour_bucket")),
      date_from: params.get("date_from") ?? undefined,
      date_to: params.get("date_to") ?? undefined,
    };
  }

  if (pageId === "provider_events") {
    return {
      account_id: params.get("account_id") ?? undefined,
      provider_name: params.get("provider_name") ?? undefined,
      provider_message_id: params.get("provider_message_id") ?? undefined,
      external_status: params.get("external_status") ?? undefined,
      replay_state:
        (params.get("replay_state") as ProviderEventsPrefillPayload["replay_state"] | null) ?? undefined,
      waba_id: params.get("waba_id") ?? undefined,
      phone_number_id: params.get("phone_number_id") ?? undefined,
      webhook_runtime_status: params.get("webhook_runtime_status") ?? undefined,
    };
  }

  if (pageId === "integrations") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_account_key: params.get("selected_account_key") ?? undefined,
    };
  }

  if (pageId === "api_webhooks") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_subscription_id: params.get("selected_subscription_id") ?? undefined,
      selected_policy_id: params.get("selected_policy_id") ?? undefined,
    };
  }

  if (pageId === "system_logs") {
    return {
      account_id: params.get("account_id") ?? undefined,
      severity: parseSystemLogSeverity(params.get("severity")),
      source_kind: parseSystemLogSourceKind(params.get("source_kind")),
      selected_log_id: params.get("selected_log_id") ?? undefined,
    };
  }

  if (pageId === "alerts") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_alert_id: params.get("selected_alert_id") ?? undefined,
    };
  }

  if (pageId === "operations") {
    return {
      account_id: params.get("account_id") ?? undefined,
    };
  }

  if (pageId === "customers") {
    return {
      account_id: params.get("account_id") ?? undefined,
      query: params.get("query") ?? undefined,
      selected_profile_id: params.get("selected_profile_id") ?? undefined,
      detail_tab: (params.get("detail_tab") as CustomersPrefillPayload["detail_tab"] | null) ?? undefined,
    };
  }

  if (pageId === "notifications") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_channel_id: params.get("selected_channel_id") ?? undefined,
    };
  }

  if (pageId === "users") {
    return {
      account_id: params.get("account_id") ?? undefined,
      site_id: params.get("site_id") ?? undefined,
      lifecycle_status: params.get("lifecycle_status") ?? undefined,
      search: params.get("search") ?? undefined,
      selected_user_id: params.get("selected_user_id") ?? undefined,
    };
  }

  if (pageId === "member_access") {
    return {
      account_id: params.get("account_id") ?? undefined,
      role_key: params.get("role_key") ?? undefined,
      search: params.get("search") ?? undefined,
      selected_binding_id: params.get("selected_binding_id") ?? undefined,
    };
  }

  if (pageId === "members") {
    return {
      account_id: params.get("account_id") ?? undefined,
      status: (params.get("status") as MembersPrefillPayload["status"] | null) ?? undefined,
      is_active: parseBoolean(params.get("is_active")),
      selected_member_key: params.get("selected_member_key") ?? undefined,
    };
  }

  if (pageId === "access_control") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_policy_id: params.get("selected_policy_id") ?? undefined,
    };
  }

  if (pageId === "security_settings") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_policy_account: params.get("selected_policy_account") ?? undefined,
    };
  }

  if (pageId === "identity_sync") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_provider_id: params.get("selected_provider_id") ?? undefined,
      selected_mapping_id: params.get("selected_mapping_id") ?? undefined,
    };
  }

  if (pageId === "organization") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_account_id: params.get("selected_account_id") ?? undefined,
    };
  }

  if (pageId === "sites") {
    return {
      account_id: params.get("account_id") ?? undefined,
      status: params.get("status") ?? undefined,
      selected_site_id: params.get("selected_site_id") ?? undefined,
      selected_site_key: params.get("selected_site_key") ?? undefined,
    };
  }

  if (pageId === "settings") {
    return {
      account_id: params.get("account_id") ?? undefined,
      category: params.get("category") ?? undefined,
      source_type:
        (params.get("source_type") as SettingsPrefillPayload["source_type"] | null) ?? undefined,
      search: params.get("search") ?? undefined,
      selected_conversation_key: params.get("selected_conversation_key") ?? undefined,
    };
  }

  if (pageId === "templates") {
    return {
      account_id: params.get("account_id") ?? undefined,
      waba_id: params.get("waba_id") ?? undefined,
      status: (params.get("status") as TemplatePrefillPayload["status"] | null) ?? undefined,
      language: params.get("language") ?? undefined,
      selected_template_id: params.get("selected_template_id") ?? undefined,
    };
  }

  if (pageId === "meta") {
    return {
      focused_account_id: params.get("focused_account_id") ?? undefined,
      selected_account_key: params.get("selected_account_key") ?? undefined,
      active_tab: (params.get("tab") as MetaAccountsPrefillPayload["active_tab"] | null) ?? undefined,
    };
  }

  if (pageId === "evidence_center") {
    return {
      account_id: params.get("account_id") ?? undefined,
      selected_bundle_id: params.get("selected_bundle_id") ?? undefined,
      source_kind: parseEvidenceSourceKind(params.get("source_kind")),
    };
  }

  return null;
}

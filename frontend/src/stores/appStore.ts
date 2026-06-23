import { create } from "zustand";

export type OperatorStatus = "online" | "busy" | "away" | "offline";
export type ActorRole =
  | "super_admin"
  | ""
  | "agent"
  | "agent_member"
  | "operator"
  | "reviewer"
  | "support_agent"
  | "finance"
  | "risk_control"
  | "readonly";
export type AppPageId =
  | "dashboard"
  | "monitoring"
  | "provider_events"
  | "api_webhooks"
  | "integrations"
  | "system_logs"
  | "evidence_center"
  | "sites"
  | "organization"
  | "users"
  | "customers"
  | "members"
  | "assignments"
  | "automation"
  | "notifications"
  | "identity_sync"
  | "member_access"
  | "alerts"
  | "reports"
  | "imports"
  | "access_control"
  | "security_settings"
  | "tags"
  | "audience_rules"
  | "tasks"
  | "reviews"
  | "whatsapp_stats"
  | "audit"
  | "conversations"
  | "tickets"
  | "messages"
  | "ledger"
  | "withdrawals"
  | "risk"
  | "leaderboard"
  | "operations"
  | "meta"
  | "media"
  | "templates"
  | "settings"
  | "ecommerce"
  | "task_rules"
  | "debug_panel"
  | "whatsapp_api_test"
  | "agents"
  | "backups"
  | "knowledge"
  | "api_stats"
  | "rate_limits"
  | "ai_chat_config"
  | "profile"
  // Finance & Billing pages
  | "finance_settings"
  | "finance"
  | "agent_usage"
  | "agent_finance_settings"
  | "agent_finance"

export type WorkspacePagePrefill = {
  nonce: number;
  accountId?: string;
  wabaId?: string;
  phoneNumberId?: string;
  conversationKey?: string;
  handoverMode?: "all" | "recommended" | "normal";
  managementMode?: "all" | "ai_managed" | "human_managed" | "paused";
  search?: string;
};

export type AuditPagePrefill = {
  nonce: number;
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

export type WhatsAppStatsPagePrefill = {
  nonce: number;
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

export type ProviderEventsPagePrefill = {
  nonce: number;
  account_id?: string;
  provider_name?: string;
  provider_message_id?: string;
  external_status?: string;
  replay_state?: "pending" | "replayed";
  waba_id?: string;
  phone_number_id?: string;
  webhook_runtime_status?: string;
};

export type IntegrationsPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_account_key?: string;
};

export type ApiWebhooksPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_subscription_id?: string;
  selected_policy_id?: string;
};

export type SystemLogsPagePrefill = {
  nonce: number;
  account_id?: string;
  severity?: "info" | "warning" | "critical";
  source_kind?: "audit" | "provider" | "queue";
  selected_log_id?: string;
};

export type AlertsPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_alert_id?: string;
};

export type OperationsPagePrefill = {
  nonce: number;
  account_id?: string;
};

export type CustomersPagePrefill = {
  nonce: number;
  account_id?: string;
  query?: string;
  selected_profile_id?: string;
};

export type NotificationsPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_channel_id?: string;
};

export type UsersPagePrefill = {
  nonce: number;
  account_id?: string;
  site_id?: string;
  lifecycle_status?: string;
  search?: string;
  selected_user_id?: string;
};

export type MemberAccessPagePrefill = {
  nonce: number;
  account_id?: string;
  role_key?: string;
  search?: string;
  selected_binding_id?: string;
};

export type AccessControlPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_policy_id?: string;
};

export type SecuritySettingsPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_policy_account?: string;
};

export type IdentitySyncPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_provider_id?: string;
  selected_mapping_id?: string;
};

export type OrganizationPagePrefill = {
  nonce: number;
  account_id?: string;
  selected_account_id?: string;
};

export type MembersPagePrefill = {
  nonce: number;
  account_id?: string;
  status?: OperatorStatus | "ALL";
  is_active?: boolean;
  selected_member_key?: string;
};

export type SitesPagePrefill = {
  nonce: number;
  account_id?: string;
  status?: string;
  selected_site_id?: string;
  selected_site_key?: string;
};

export type SettingsPagePrefill = {
  nonce: number;
  account_id?: string;
  category?: string;
  source_type?: "all" | "builtin" | "database";
  search?: string;
  selected_conversation_key?: string;
};

export type TemplatePagePrefill = {
  nonce: number;
  account_id?: string;
  waba_id?: string;
  status?: "ALL" | "PENDING" | "APPROVED" | "REJECTED" | "DRAFT" | "DISABLED" | "PAUSED";
  language?: string;
  selected_template_id?: string;
};

export type MetaAccountsPagePrefill = {
  nonce: number;
  focused_account_id?: string;
  selected_account_key?: string;
  active_tab?: "accounts" | "phones" | "webhooks" | "signup";
};

export type EvidencePagePrefill = {
  nonce: number;
  account_id?: string;
  selected_bundle_id?: string;
  source_kind?: "audit" | "provider" | "queue" | "webhook";
};

type AppState = {
  aiProvider: "openai" | "deepseek";
  consoleAgentId: string;
  consoleAgentName: string;
  actorRole: ActorRole;
  actorAccountIds: string[];
  siteAccountIds: string[];
  operatorStatus: OperatorStatus;
  activePage: AppPageId;
  workspacePagePrefill: WorkspacePagePrefill | null;
  auditPagePrefill: AuditPagePrefill | null;
  whatsappStatsPagePrefill: WhatsAppStatsPagePrefill | null;
  providerEventsPagePrefill: ProviderEventsPagePrefill | null;
  integrationsPagePrefill: IntegrationsPagePrefill | null;
  apiWebhooksPagePrefill: ApiWebhooksPagePrefill | null;
  systemLogsPagePrefill: SystemLogsPagePrefill | null;
  alertsPagePrefill: AlertsPagePrefill | null;
  operationsPagePrefill: OperationsPagePrefill | null;
  customersPagePrefill: CustomersPagePrefill | null;
  notificationsPagePrefill: NotificationsPagePrefill | null;
  usersPagePrefill: UsersPagePrefill | null;
  memberAccessPagePrefill: MemberAccessPagePrefill | null;
  accessControlPagePrefill: AccessControlPagePrefill | null;
  securitySettingsPagePrefill: SecuritySettingsPagePrefill | null;
  identitySyncPagePrefill: IdentitySyncPagePrefill | null;
  organizationPagePrefill: OrganizationPagePrefill | null;
  membersPagePrefill: MembersPagePrefill | null;
  sitesPagePrefill: SitesPagePrefill | null;
  settingsPagePrefill: SettingsPagePrefill | null;
  templatePagePrefill: TemplatePagePrefill | null;
  metaAccountsPagePrefill: MetaAccountsPagePrefill | null;
  evidencePagePrefill: EvidencePagePrefill | null;
  setAiProvider: (provider: "openai" | "deepseek") => void;
  setConsoleAgentId: (agentId: string) => void;
  setConsoleAgentName: (agentName: string) => void;
  setActorRole: (role: ActorRole) => void;
  setActorAccountIds: (accountIds: string[]) => void;
  setSiteAccountIds: (accountIds: string[]) => void;
  setOperatorStatus: (status: OperatorStatus) => void;
  setActivePage: (page: AppPageId) => void;
  setWorkspacePagePrefill: (prefill: Omit<WorkspacePagePrefill, "nonce"> | null) => void;
  openWorkspacePage: (prefill?: Omit<WorkspacePagePrefill, "nonce">) => void;
  clearWorkspacePagePrefill: () => void;
  setAuditPagePrefill: (prefill: Omit<AuditPagePrefill, "nonce"> | null) => void;
  openAuditPage: (prefill?: Omit<AuditPagePrefill, "nonce">) => void;
  clearAuditPagePrefill: () => void;
  setWhatsAppStatsPagePrefill: (prefill: Omit<WhatsAppStatsPagePrefill, "nonce"> | null) => void;
  openWhatsAppStatsPage: (prefill?: Omit<WhatsAppStatsPagePrefill, "nonce">) => void;
  clearWhatsAppStatsPagePrefill: () => void;
  setProviderEventsPagePrefill: (
    prefill: Omit<ProviderEventsPagePrefill, "nonce"> | null
  ) => void;
  openProviderEventsPage: (prefill?: Omit<ProviderEventsPagePrefill, "nonce">) => void;
  clearProviderEventsPagePrefill: () => void;
  setIntegrationsPagePrefill: (prefill: Omit<IntegrationsPagePrefill, "nonce"> | null) => void;
  openIntegrationsPage: (prefill?: Omit<IntegrationsPagePrefill, "nonce">) => void;
  clearIntegrationsPagePrefill: () => void;
  setApiWebhooksPagePrefill: (prefill: Omit<ApiWebhooksPagePrefill, "nonce"> | null) => void;
  openApiWebhooksPage: (prefill?: Omit<ApiWebhooksPagePrefill, "nonce">) => void;
  clearApiWebhooksPagePrefill: () => void;
  setSystemLogsPagePrefill: (prefill: Omit<SystemLogsPagePrefill, "nonce"> | null) => void;
  openSystemLogsPage: (prefill?: Omit<SystemLogsPagePrefill, "nonce">) => void;
  clearSystemLogsPagePrefill: () => void;
  setAlertsPagePrefill: (prefill: Omit<AlertsPagePrefill, "nonce"> | null) => void;
  openAlertsPage: (prefill?: Omit<AlertsPagePrefill, "nonce">) => void;
  clearAlertsPagePrefill: () => void;
  setOperationsPagePrefill: (prefill: Omit<OperationsPagePrefill, "nonce"> | null) => void;
  openOperationsPage: (prefill?: Omit<OperationsPagePrefill, "nonce">) => void;
  clearOperationsPagePrefill: () => void;
  setCustomersPagePrefill: (prefill: Omit<CustomersPagePrefill, "nonce"> | null) => void;
  openCustomersPage: (prefill?: Omit<CustomersPagePrefill, "nonce">) => void;
  clearCustomersPagePrefill: () => void;
  setNotificationsPagePrefill: (
    prefill: Omit<NotificationsPagePrefill, "nonce"> | null
  ) => void;
  clearNotificationsPagePrefill: () => void;
  setUsersPagePrefill: (prefill: Omit<UsersPagePrefill, "nonce"> | null) => void;
  openUsersPage: (prefill?: Omit<UsersPagePrefill, "nonce">) => void;
  clearUsersPagePrefill: () => void;
  setMemberAccessPagePrefill: (prefill: Omit<MemberAccessPagePrefill, "nonce"> | null) => void;
  openMemberAccessPage: (prefill?: Omit<MemberAccessPagePrefill, "nonce">) => void;
  clearMemberAccessPagePrefill: () => void;
  setAccessControlPagePrefill: (
    prefill: Omit<AccessControlPagePrefill, "nonce"> | null
  ) => void;
  openAccessControlPage: (prefill?: Omit<AccessControlPagePrefill, "nonce">) => void;
  clearAccessControlPagePrefill: () => void;
  setSecuritySettingsPagePrefill: (
    prefill: Omit<SecuritySettingsPagePrefill, "nonce"> | null
  ) => void;
  openSecuritySettingsPage: (
    prefill?: Omit<SecuritySettingsPagePrefill, "nonce">
  ) => void;
  clearSecuritySettingsPagePrefill: () => void;
  setIdentitySyncPagePrefill: (prefill: Omit<IdentitySyncPagePrefill, "nonce"> | null) => void;
  openIdentitySyncPage: (prefill?: Omit<IdentitySyncPagePrefill, "nonce">) => void;
  clearIdentitySyncPagePrefill: () => void;
  setOrganizationPagePrefill: (prefill: Omit<OrganizationPagePrefill, "nonce"> | null) => void;
  openOrganizationPage: (prefill?: Omit<OrganizationPagePrefill, "nonce">) => void;
  clearOrganizationPagePrefill: () => void;
  setMembersPagePrefill: (prefill: Omit<MembersPagePrefill, "nonce"> | null) => void;
  openMembersPage: (prefill?: Omit<MembersPagePrefill, "nonce">) => void;
  clearMembersPagePrefill: () => void;
  setSitesPagePrefill: (prefill: Omit<SitesPagePrefill, "nonce"> | null) => void;
  openSitesPage: (prefill?: Omit<SitesPagePrefill, "nonce">) => void;
  clearSitesPagePrefill: () => void;
  setSettingsPagePrefill: (prefill: Omit<SettingsPagePrefill, "nonce"> | null) => void;
  openSettingsPage: (prefill?: Omit<SettingsPagePrefill, "nonce">) => void;
  clearSettingsPagePrefill: () => void;
  setTemplatePagePrefill: (prefill: Omit<TemplatePagePrefill, "nonce"> | null) => void;
  openTemplatePage: (prefill?: Omit<TemplatePagePrefill, "nonce">) => void;
  clearTemplatePagePrefill: () => void;
  setMetaAccountsPagePrefill: (
    prefill: Omit<MetaAccountsPagePrefill, "nonce"> | null
  ) => void;
  openMetaAccountsPage: (prefill?: Omit<MetaAccountsPagePrefill, "nonce">) => void;
  clearMetaAccountsPagePrefill: () => void;
  setEvidencePagePrefill: (prefill: Omit<EvidencePagePrefill, "nonce"> | null) => void;
  openEvidencePage: (prefill?: Omit<EvidencePagePrefill, "nonce">) => void;
  clearEvidencePagePrefill: () => void;
};

export const useAppStore = create<AppState>((set) => ({
  aiProvider: "openai",
  consoleAgentId: "agent-cn-console",
  consoleAgentName: "\u4e2d\u6587\u5ba2\u670d\u53f0",
  actorRole: "",
  actorAccountIds: [],
  siteAccountIds: [],
  operatorStatus: "online",
  activePage: "dashboard",
  workspacePagePrefill: null,
  auditPagePrefill: null,
  whatsappStatsPagePrefill: null,
  providerEventsPagePrefill: null,
  integrationsPagePrefill: null,
  apiWebhooksPagePrefill: null,
  systemLogsPagePrefill: null,
  alertsPagePrefill: null,
  operationsPagePrefill: null,
  customersPagePrefill: null,
  notificationsPagePrefill: null,
  usersPagePrefill: null,
  memberAccessPagePrefill: null,
  accessControlPagePrefill: null,
  securitySettingsPagePrefill: null,
  identitySyncPagePrefill: null,
  organizationPagePrefill: null,
  membersPagePrefill: null,
  sitesPagePrefill: null,
  settingsPagePrefill: null,
  templatePagePrefill: null,
  metaAccountsPagePrefill: null,
  evidencePagePrefill: null,
  setAiProvider: (provider) => set({ aiProvider: provider }),
  setConsoleAgentId: (agentId) => set({ consoleAgentId: agentId }),
  setConsoleAgentName: (agentName) => set({ consoleAgentName: agentName }),
  setActorRole: (role) => set({ actorRole: role }),
  setActorAccountIds: (accountIds) => set({ actorAccountIds: accountIds }),
  setSiteAccountIds: (accountIds) => set({ siteAccountIds: accountIds }),
  setOperatorStatus: (status) => set({ operatorStatus: status }),
  setActivePage: (page) => set({ activePage: page }),
  setWorkspacePagePrefill: (prefill) =>
    set({
      workspacePagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openWorkspacePage: (prefill) =>
    set({
      activePage: "conversations",
      workspacePagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearWorkspacePagePrefill: () => set({ workspacePagePrefill: null }),
  setAuditPagePrefill: (prefill) =>
    set({
      auditPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openAuditPage: (prefill) =>
    set({
      activePage: "audit",
      auditPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearAuditPagePrefill: () => set({ auditPagePrefill: null }),
  setWhatsAppStatsPagePrefill: (prefill) =>
    set({
      whatsappStatsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openWhatsAppStatsPage: (prefill) =>
    set({
      activePage: "whatsapp_stats",
      whatsappStatsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearWhatsAppStatsPagePrefill: () => set({ whatsappStatsPagePrefill: null }),
  setProviderEventsPagePrefill: (prefill) =>
    set({
      providerEventsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openProviderEventsPage: (prefill) =>
    set({
      activePage: "provider_events",
      providerEventsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearProviderEventsPagePrefill: () => set({ providerEventsPagePrefill: null }),
  setIntegrationsPagePrefill: (prefill) =>
    set({
      integrationsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openIntegrationsPage: (prefill) =>
    set({
      activePage: "integrations",
      integrationsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearIntegrationsPagePrefill: () => set({ integrationsPagePrefill: null }),
  setApiWebhooksPagePrefill: (prefill) =>
    set({
      apiWebhooksPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openApiWebhooksPage: (prefill) =>
    set({
      activePage: "api_webhooks",
      apiWebhooksPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearApiWebhooksPagePrefill: () => set({ apiWebhooksPagePrefill: null }),
  setSystemLogsPagePrefill: (prefill) =>
    set({
      systemLogsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openSystemLogsPage: (prefill) =>
    set({
      activePage: "system_logs",
      systemLogsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearSystemLogsPagePrefill: () => set({ systemLogsPagePrefill: null }),
  setAlertsPagePrefill: (prefill) =>
    set({
      alertsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openAlertsPage: (prefill) =>
    set({
      activePage: "alerts",
      alertsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearAlertsPagePrefill: () => set({ alertsPagePrefill: null }),
  setOperationsPagePrefill: (prefill) =>
    set({
      operationsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openOperationsPage: (prefill) =>
    set({
      activePage: "operations",
      operationsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearOperationsPagePrefill: () => set({ operationsPagePrefill: null }),
  setCustomersPagePrefill: (prefill) =>
    set({
      customersPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openCustomersPage: (prefill) =>
    set({
      activePage: "customers",
      customersPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearCustomersPagePrefill: () => set({ customersPagePrefill: null }),
  setNotificationsPagePrefill: (prefill) =>
    set({
      notificationsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  clearNotificationsPagePrefill: () => set({ notificationsPagePrefill: null }),
  setUsersPagePrefill: (prefill) =>
    set({
      usersPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openUsersPage: (prefill) =>
    set({
      activePage: "users",
      usersPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearUsersPagePrefill: () => set({ usersPagePrefill: null }),
  setMemberAccessPagePrefill: (prefill) =>
    set({
      memberAccessPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openMemberAccessPage: (prefill) =>
    set({
      activePage: "member_access",
      memberAccessPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearMemberAccessPagePrefill: () => set({ memberAccessPagePrefill: null }),
  setAccessControlPagePrefill: (prefill) =>
    set({
      accessControlPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openAccessControlPage: (prefill) =>
    set({
      activePage: "access_control",
      accessControlPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearAccessControlPagePrefill: () => set({ accessControlPagePrefill: null }),
  setSecuritySettingsPagePrefill: (prefill) =>
    set({
      securitySettingsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openSecuritySettingsPage: (prefill) =>
    set({
      activePage: "security_settings",
      securitySettingsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearSecuritySettingsPagePrefill: () => set({ securitySettingsPagePrefill: null }),
  setIdentitySyncPagePrefill: (prefill) =>
    set({
      identitySyncPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openIdentitySyncPage: (prefill) =>
    set({
      activePage: "identity_sync",
      identitySyncPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearIdentitySyncPagePrefill: () => set({ identitySyncPagePrefill: null }),
  setOrganizationPagePrefill: (prefill) =>
    set({
      organizationPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openOrganizationPage: (prefill) =>
    set({
      activePage: "organization",
      organizationPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearOrganizationPagePrefill: () => set({ organizationPagePrefill: null }),
  setMembersPagePrefill: (prefill) =>
    set({
      membersPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openMembersPage: (prefill) =>
    set({
      activePage: "members",
      membersPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearMembersPagePrefill: () => set({ membersPagePrefill: null }),
  setSitesPagePrefill: (prefill) =>
    set({
      sitesPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openSitesPage: (prefill) =>
    set({
      activePage: "sites",
      sitesPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearSitesPagePrefill: () => set({ sitesPagePrefill: null }),
  setSettingsPagePrefill: (prefill) =>
    set({
      settingsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openSettingsPage: (prefill) =>
    set({
      activePage: "settings",
      settingsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearSettingsPagePrefill: () => set({ settingsPagePrefill: null }),
  setTemplatePagePrefill: (prefill) =>
    set({
      templatePagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openTemplatePage: (prefill) =>
    set({
      activePage: "templates",
      templatePagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearTemplatePagePrefill: () => set({ templatePagePrefill: null }),
  setMetaAccountsPagePrefill: (prefill) =>
    set({
      metaAccountsPagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openMetaAccountsPage: (prefill) =>
    set({
      activePage: "meta",
      metaAccountsPagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearMetaAccountsPagePrefill: () => set({ metaAccountsPagePrefill: null }),
  setEvidencePagePrefill: (prefill) =>
    set({
      evidencePagePrefill: prefill
        ? {
            nonce: Date.now(),
            ...prefill
          }
        : null
    }),
  openEvidencePage: (prefill) =>
    set({
      activePage: "evidence_center",
      evidencePagePrefill: {
        nonce: Date.now(),
        ...prefill
      }
    }),
  clearEvidencePagePrefill: () => set({ evidencePagePrefill: null }),
}));

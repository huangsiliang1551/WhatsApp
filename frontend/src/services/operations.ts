import {
  claimTaskInstance,
  exportSupportKnowledge,
  getConversationAiStatus,
  getTemplateAnalytics,
  getTemplateStatsSummary,
  getMetricsSummary,
  getWhatsAppStatsSummary,
  importSupportKnowledge,
  listAuditLogs,
  listAgentWorkloads,
  listConversations,
  listMessageTemplates,
  listProviderStatusBuffer,
  listPlatformUsers,
  listQueueStats,
  listRuntimeAgents,
  listRuntimeState,
  listSupportKnowledge,
  listTaskInstances,
  listTemplateDailyStats,
  listWhatsAppDailyStats,
  registerRuntimeAgent,
  replayProviderStatusBuffer,
  setRuntimeAgentStatus,
  type RegisterAgentPayload,
  type AuditLogEntry,
  type MessageTemplateView,
  type PlatformUser,
  type ConversationSummary,
  type AgentWorkload,
  type MetricsSummaryResponse,
  type ProviderStatusBufferEntry,
  type QueueJob,
  type QueueStatsResponse,
  type RuntimeAgent,
  type RuntimeState,
  type SupportKnowledgeEntryView,
  type SupportKnowledgeExportBundle,
  type SupportKnowledgeImportResult,
  type TaskInstance,
  type TemplateStatsDailyRow,
  type TemplateStatsDetailResponse,
  type TemplateStatsSummary,
  type WhatsAppStatsDailyRow,
  type WhatsAppStatsSummary,
} from "./api";
import {
  listPlatformMemberVerifications,
  listPlatformMemberWhatsAppBindings,
  listSupportTickets,
  type PlatformMemberVerificationRequest,
  type PlatformMemberWhatsAppBindingRequest,
  type SupportTicket,
} from "./h5";
import {
  mockAlertRules,
  mockAutomationRules,
  mockOperationsBatchJobs,
  mockRiskCases,
  mockRiskProfiles,
  mockRoleDefinitions,
} from "../mocks/operations";
import type {
  AlertCenterItem,
  AlertCenterSnapshot,
  AlertRuleDefinition,
  CustomerConversationLink,
  CustomerProfileDetail,
  CustomerProfileSummary,
  CustomerTicketLink,
  ImportExportCenterSnapshot,
  KnowledgeCategorySummary,
  KnowledgeEntrySummary,
  MemberDirectoryItem,
  AlertReplayPayload,
  AutomationRuleDefinition,
  AutomationRulePrototypePayload,
  OperationsBatchJob,
  OperationsBatchJobCreatePayload,
  OperationsCenterSnapshot,
  OperationsProviderBacklogItem,
  OperationsTaskItem,
  ReportCenterDailyRow,
  ReportCenterKpi,
  ReportCenterSnapshot,
  ReportTemplateAnalyticsView,
  ReportTemplateOption,
  RiskCaseItem,
  RiskCenterSnapshot,
  RoleDefinitionCreatePayload,
  RolePermissionResource,
  RiskProfileCreatePayload,
  RiskProfileItem,
  RoleDefinition,
} from "../types/operations";
import type { OperatorStatus } from "../stores/appStore";

const automationRuleStore = mockAutomationRules.map(cloneAutomationRule);
const alertRuleStore = mockAlertRules.map(cloneAlertRule);
const riskProfileStore = mockRiskProfiles.map((item) => ({ ...item }));
const riskCaseStore = mockRiskCases.map((item) => ({ ...item }));
const operationsBatchJobStore = mockOperationsBatchJobs.map((item) => ({ ...item }));
const roleDefinitionStore = mockRoleDefinitions.map(cloneRoleDefinition);

function cloneAutomationRule(rule: AutomationRuleDefinition): AutomationRuleDefinition {
  return {
    ...rule,
    conditions: rule.conditions.map((item) => ({ ...item })),
    actions: rule.actions.map((item) => ({ ...item })),
  };
}

function cloneAlertRule(rule: AlertRuleDefinition): AlertRuleDefinition {
  return {
    ...rule,
    notify_channels: [...rule.notify_channels],
  };
}

function cloneRiskProfile(profile: RiskProfileItem): RiskProfileItem {
  return { ...profile };
}

function cloneRiskCase(riskCase: RiskCaseItem): RiskCaseItem {
  return { ...riskCase };
}

function cloneBatchJob(job: OperationsBatchJob): OperationsBatchJob {
  return { ...job };
}

function cloneRoleDefinition(role: RoleDefinition): RoleDefinition {
  return {
    ...role,
    account_scope: [...role.account_scope],
    page_scope: [...role.page_scope],
    permissions: role.permissions.map((permission) => ({
      ...permission,
      actions: { ...permission.actions },
    })),
  };
}

const ROLE_GROUP_ORDER: RolePermissionResource["group"][] = [
  "workspace",
  "accounts",
  "templates",
  "customers",
  "system",
];

function normalizeRoleText(value: string): string {
  return value.trim().toLowerCase().replace(/[\s_-]+/g, "");
}

function matchesRoleDefinition(member: MemberDirectoryItem, role: RoleDefinition): boolean {
  const normalizedName = normalizeRoleText(role.name);
  const normalizedKey = normalizeRoleText(role.role_key);
  return member.role_labels.some((label) => {
    const normalizedLabel = normalizeRoleText(label);
    if (!normalizedLabel) {
      return false;
    }
    return (
      normalizedLabel === normalizedName ||
      normalizedLabel === normalizedKey ||
      normalizedName.includes(normalizedLabel) ||
      normalizedLabel.includes(normalizedName) ||
      normalizedKey.includes(normalizedLabel) ||
      normalizedLabel.includes(normalizedKey)
    );
  });
}

function getMemberUniqueKey(member: MemberDirectoryItem): string {
  return `${member.account_id ?? "global"}:${member.agent_id}`;
}

function getScopedAccountIds(members: MemberDirectoryItem[]): string[] {
  return Array.from(
    new Set(
      members
        .map((member) => member.account_id)
        .filter((value): value is string => Boolean(value))
    )
  ).sort((left, right) => left.localeCompare(right, "zh-CN"));
}

function roleMatchesAccount(role: RoleDefinition, accountId?: string): boolean {
  if (!accountId) {
    return true;
  }
  return role.scope === "global" || role.account_scope.includes("ALL") || role.account_scope.includes(accountId);
}

function buildBlankRolePermissions(): RolePermissionResource[] {
  const resources = new Map<string, Omit<RolePermissionResource, "actions">>();
  roleDefinitionStore.forEach((role) => {
    role.permissions.forEach((permission) => {
      if (!resources.has(permission.resource_key)) {
        resources.set(permission.resource_key, {
          resource_key: permission.resource_key,
          label: permission.label,
          group: permission.group,
        });
      }
    });
  });

  return Array.from(resources.values())
    .sort((left, right) => {
      const groupOrder = ROLE_GROUP_ORDER.indexOf(left.group) - ROLE_GROUP_ORDER.indexOf(right.group);
      if (groupOrder !== 0) {
        return groupOrder;
      }
      return left.label.localeCompare(right.label, "zh-CN");
    })
    .map((resource) => ({
      ...resource,
      actions: {
        view: false,
        edit: false,
        assign: false,
        approve: false,
        export: false,
      },
    }));
}

function buildRoleDefinitionFromMembers(
  baseRole: RoleDefinition,
  matchedMembers: MemberDirectoryItem[]
): RoleDefinition {
  const scopedAccountIds = getScopedAccountIds(matchedMembers);
  return {
    ...cloneRoleDefinition(baseRole),
    member_count: matchedMembers.length || baseRole.member_count,
    account_scope:
      baseRole.scope === "global"
        ? ["ALL"]
        : scopedAccountIds.length
          ? scopedAccountIds
          : [...baseRole.account_scope],
    permission_origin: baseRole.permission_origin ?? "preset",
    permission_origin_role_key: baseRole.permission_origin_role_key ?? baseRole.role_key,
    source: matchedMembers.length > 0 ? "hybrid" : baseRole.source,
  };
}

function buildDerivedRoleKey(label: string, index: number): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return slug || `derived_role_${index + 1}`;
}

function getRoleTemplateForLabel(label: string): RoleDefinition {
  const normalizedLabel = normalizeRoleText(label);
  const template =
    roleDefinitionStore.find((role) => {
      const normalizedName = normalizeRoleText(role.name);
      const normalizedKey = normalizeRoleText(role.role_key);
      return (
        normalizedLabel === normalizedName ||
        normalizedLabel === normalizedKey ||
        normalizedName.includes(normalizedLabel) ||
        normalizedLabel.includes(normalizedName) ||
        normalizedKey.includes(normalizedLabel) ||
        normalizedLabel.includes(normalizedKey)
      );
    }) ??
    roleDefinitionStore[1] ??
    roleDefinitionStore[0];

  return cloneRoleDefinition(template);
}

function deriveRoleLabels(agent: RuntimeAgent): string[] {
  const seed = `${agent.agent_id}:${agent.display_name}`.toLowerCase();
  const labels: string[] = [];
  if (seed.includes("review")) labels.push("审核员");
  if (seed.includes("admin")) labels.push("管理员");
  if (seed.includes("support") || seed.includes("agent") || labels.length === 0) {
    labels.push("客服");
  }
  return Array.from(new Set(labels));
}

function mapMember(agent: RuntimeAgent, workload?: AgentWorkload): MemberDirectoryItem {
  return {
    account_id: agent.account_id,
    agent_id: agent.agent_id,
    display_name: agent.display_name,
    email: agent.email,
    status: agent.status,
    is_active: agent.is_active,
    assigned_open_conversations: workload?.assigned_open_conversations ?? 0,
    assigned_total_conversations: workload?.assigned_total_conversations ?? 0,
    assigned_account_count: workload?.assigned_account_count ?? (agent.account_id ? 1 : 0),
    role_labels: deriveRoleLabels(agent),
    source: "api",
  };
}

function matchesConversation(user: PlatformUser, conversation: ConversationSummary): boolean {
  if (user.account_id && conversation.account_id !== user.account_id) return false;
  if (conversation.customer_id === user.public_user_id) return true;
  return user.identities.some((identity) => identity.identity_value === conversation.customer_id);
}

function matchesTicket(user: PlatformUser, ticket: SupportTicket): boolean {
  if (ticket.public_user_id !== user.public_user_id) return false;
  if (user.account_id && ticket.account_id !== user.account_id) return false;
  return true;
}

function getScopedConversationKey(accountId: string, conversationId: string): string {
  return `${accountId}:${conversationId}`;
}

function mapCustomerSummary(
  user: PlatformUser,
  conversations: ConversationSummary[],
  tickets: SupportTicket[]
): CustomerProfileSummary {
  const relatedCustomerIds = Array.from(new Set(conversations.map((item) => item.customer_id)));
  return {
    id: user.id,
    account_id: user.account_id,
    public_user_id: user.public_user_id,
    display_name: user.display_name,
    registration_site_key: user.registration_site_key,
    registration_site_domain: user.registration_site_domain,
    language_code: user.language_code,
    lifecycle_status: user.lifecycle_status,
    is_anonymous: user.is_anonymous,
    has_whatsapp: user.has_whatsapp,
    is_invited_user: user.is_invited_user,
    is_new_user: user.is_new_user,
    restrict_task_claim: user.restrict_task_claim,
    last_active_at: user.last_active_at,
    registration_ip: user.registration_ip,
    registration_ips: [],
    multi_ip: false,
    tag_keys: user.tags.map((tag) => tag.tag_key),
    identity_values: user.identities.map((identity) => identity.identity_value),
    relatedCustomerIds,
    conversation_count: conversations.length,
    open_conversation_count: conversations.filter((item) => item.status === "open").length,
    ticket_count: tickets.length,
    open_ticket_count: tickets.filter((item) => !["resolved", "closed", "cancelled"].includes(item.status))
      .length,
  };
}

export type PlatformUserMemberStatusSnapshot = {
  verificationRequests: PlatformMemberVerificationRequest[];
  bindingRequests: PlatformMemberWhatsAppBindingRequest[];
};

export type PlatformUserMemberStatusSummary = {
  latestVerificationStatus: PlatformMemberVerificationRequest["status"] | null;
  latestBindingStatus: PlatformMemberWhatsAppBindingRequest["status"] | null;
  verificationCount: number;
  bindingCount: number;
  latestVerificationUpdatedAt: string | null;
  latestBindingUpdatedAt: string | null;
};

export type CustomerMemberStatusSnapshot = PlatformUserMemberStatusSnapshot;

type MemberStatusScope = Pick<CustomerProfileSummary, "id" | "account_id" | "public_user_id">;

type CustomerMemberScopedRecord = {
  accountId: string;
  memberProfileId: string;
  userId: string;
  publicUserId: string;
  updatedAt: string;
  createdAt: string;
};

function sortByLatestUpdatedAt<T extends { updatedAt: string; createdAt: string }>(items: T[]): T[] {
  return [...items].sort(
    (left, right) =>
      Date.parse(right.updatedAt || right.createdAt) - Date.parse(left.updatedAt || left.createdAt)
  );
}

function filterCustomerMemberScopedRecords<T extends CustomerMemberScopedRecord>(
  profile: MemberStatusScope,
  records: T[]
): T[] {
  const scopedRecords = records.filter((record) =>
    profile.account_id ? record.accountId === profile.account_id : true
  );
  const strongMatches = scopedRecords.filter(
    (record) => record.memberProfileId === profile.id || record.userId === profile.id
  );
  if (strongMatches.length > 0) {
    return sortByLatestUpdatedAt(strongMatches);
  }
  return sortByLatestUpdatedAt(
    scopedRecords.filter((record) => record.publicUserId === profile.public_user_id)
  );
}

async function listMemberStatusCollections(accountId?: string): Promise<{
  verifications: PlatformMemberVerificationRequest[];
  bindings: PlatformMemberWhatsAppBindingRequest[];
}> {
  const [verifications, bindings] = await Promise.all([
    listPlatformMemberVerifications({
      account_id: accountId ?? undefined,
    }),
    listPlatformMemberWhatsAppBindings({
      account_id: accountId ?? undefined,
    }),
  ]);

  return {
    verifications,
    bindings,
  };
}

export async function getPlatformUserMemberStatusSnapshot(
  profile: MemberStatusScope
): Promise<PlatformUserMemberStatusSnapshot> {
  const { verifications, bindings } = await listMemberStatusCollections(
    profile.account_id ?? undefined
  );

  return {
    verificationRequests: filterCustomerMemberScopedRecords(profile, verifications),
    bindingRequests: filterCustomerMemberScopedRecords(profile, bindings),
  };
}

function buildPlatformUserMemberStatusSummary(
  snapshot: PlatformUserMemberStatusSnapshot
): PlatformUserMemberStatusSummary {
  const latestVerification = snapshot.verificationRequests[0] ?? null;
  const latestBinding = snapshot.bindingRequests[0] ?? null;
  return {
    latestVerificationStatus: latestVerification?.status ?? null,
    latestBindingStatus: latestBinding?.status ?? null,
    verificationCount: snapshot.verificationRequests.length,
    bindingCount: snapshot.bindingRequests.length,
    latestVerificationUpdatedAt: latestVerification?.updatedAt ?? null,
    latestBindingUpdatedAt: latestBinding?.updatedAt ?? null,
  };
}

export async function listPlatformUserMemberStatusIndex(
  profiles: readonly MemberStatusScope[],
  accountId?: string
): Promise<Record<string, PlatformUserMemberStatusSummary>> {
  const { verifications, bindings } = await listMemberStatusCollections(accountId);
  return Object.fromEntries(
    profiles.map((profile) => {
      const snapshot: PlatformUserMemberStatusSnapshot = {
        verificationRequests: filterCustomerMemberScopedRecords(profile, verifications),
        bindingRequests: filterCustomerMemberScopedRecords(profile, bindings),
      };
      return [profile.id, buildPlatformUserMemberStatusSummary(snapshot)];
    })
  );
}

export async function getCustomerMemberStatusSnapshot(
  profile: MemberStatusScope
): Promise<CustomerMemberStatusSnapshot> {
  return getPlatformUserMemberStatusSnapshot(profile);
}

export async function listMemberDirectory(accountId?: string): Promise<MemberDirectoryItem[]> {
  const [agents, workloads] = await Promise.all([
    listRuntimeAgents(undefined, accountId),
    listAgentWorkloads(undefined, accountId),
  ]);
  const workloadMap = new Map(workloads.map((item) => [item.agent_id, item]));
  return agents
    .map((agent) => mapMember(agent, workloadMap.get(agent.agent_id)))
    .sort((left, right) => left.display_name.localeCompare(right.display_name, "zh-CN"));
}

export async function createMemberDirectoryEntry(
  payload: RegisterAgentPayload
): Promise<MemberDirectoryItem> {
  const created = await registerRuntimeAgent(payload);
  const workloads = await listAgentWorkloads(undefined, payload.account_id ?? undefined).catch(
    () => []
  );
  const workload = workloads.find((item) => item.agent_id === created.agent_id);
  return mapMember(created, workload);
}

export async function updateMemberDirectoryStatus(
  agentId: string,
  status: OperatorStatus,
  accountId?: string
): Promise<MemberDirectoryItem> {
  const updated = await setRuntimeAgentStatus(agentId, { status }, accountId);
  const workloads = await listAgentWorkloads(undefined, accountId).catch(() => []);
  const workload = workloads.find((item) => item.agent_id === updated.agent_id);
  return mapMember(updated, workload);
}

export async function listRoleDefinitions(accountId?: string): Promise<RoleDefinition[]> {
  const baseRoles = roleDefinitionStore
    .map(cloneRoleDefinition)
    .filter((role) => roleMatchesAccount(role, accountId));

  let members: MemberDirectoryItem[] = [];
  try {
    members = await listMemberDirectory(accountId);
  } catch {
    return baseRoles;
  }

  const claimedMembers = new Set<string>();
  const hydratedRoles = baseRoles.map((role) => {
    const matchedMembers = members.filter((member) => matchesRoleDefinition(member, role));
    matchedMembers.forEach((member) => claimedMembers.add(getMemberUniqueKey(member)));
    return buildRoleDefinitionFromMembers(role, matchedMembers);
  });

  const derivedBuckets = new Map<string, MemberDirectoryItem[]>();
  members.forEach((member) => {
    if (claimedMembers.has(getMemberUniqueKey(member))) {
      return;
    }
    const label = member.role_labels.find((value) => value.trim())?.trim();
    if (!label) {
      return;
    }
    const bucket = derivedBuckets.get(label) ?? [];
    bucket.push(member);
    derivedBuckets.set(label, bucket);
  });

  const derivedRoles: RoleDefinition[] = Array.from(derivedBuckets.entries()).map(
    ([label, scopedMembers], index) => {
      const template = getRoleTemplateForLabel(label);
      const scopedAccountIds = getScopedAccountIds(scopedMembers);
      return {
        ...cloneRoleDefinition(template),
        role_key: buildDerivedRoleKey(label, index),
        name: label,
        scope: scopedMembers.some((member) => member.account_id === null) ? "global" : "account",
        member_count: scopedMembers.length,
        account_scope: scopedAccountIds.length ? scopedAccountIds : ["ALL"],
        permission_origin: "derived",
        permission_origin_role_key: template.role_key,
        source: "hybrid",
      };
    }
  );

  return [...hydratedRoles, ...derivedRoles].sort((left, right) =>
    left.name.localeCompare(right.name, "zh-CN")
  );
}

export async function createRoleDefinition(
  payload: RoleDefinitionCreatePayload
): Promise<RoleDefinition> {
  const created: RoleDefinition = {
    role_key: payload.role_key.trim(),
    name: payload.name.trim(),
    scope: payload.scope,
    status: "draft",
    member_count: 0,
    account_scope: payload.scope === "global" ? ["ALL"] : payload.account_scope,
    page_scope: [],
    permissions: buildBlankRolePermissions(),
    permission_origin: "custom",
    permission_origin_role_key: null,
    source: "mock",
  };

  roleDefinitionStore.unshift(created);
  return cloneRoleDefinition(created);
}

export async function listAutomationRules(
  accountId?: string
): Promise<AutomationRuleDefinition[]> {
  return automationRuleStore
    .filter((item) => (accountId ? item.account_id === null || item.account_id === accountId : true))
    .map(cloneAutomationRule);
}

export async function createAutomationRulePrototype(
  payload: AutomationRulePrototypePayload
): Promise<AutomationRuleDefinition> {
  const now = new Date().toISOString();
  const created: AutomationRuleDefinition = {
    rule_id: `rule-${Date.now()}`,
    account_id: payload.scope === "account" ? payload.account_id?.trim() || null : null,
    name: payload.name.trim(),
    scope: payload.scope,
    status: "draft",
    priority: payload.priority,
    trigger_type: payload.trigger_type.trim(),
    conditions: payload.condition_lines
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => ({
        field: `condition_${index + 1}`,
        operator: "match",
        value: line,
      })),
    actions: payload.action_lines
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => ({
        action_type: "custom_action",
        summary: line,
      })),
    match_count_24h: 0,
    updated_at: now,
    source: "mock",
  };
  automationRuleStore.unshift(created);
  return cloneAutomationRule(created);
}

export async function updateAutomationRuleStatus(
  ruleId: string,
  status: AutomationRuleDefinition["status"]
): Promise<AutomationRuleDefinition> {
  const target = automationRuleStore.find((item) => item.rule_id === ruleId);
  if (!target) {
    throw new Error("Automation rule not found");
  }
  target.status = status;
  target.updated_at = new Date().toISOString();
  return cloneAutomationRule(target);
}

export async function listAlertRules(accountId?: string): Promise<AlertRuleDefinition[]> {
  return alertRuleStore
    .filter((item) => (accountId ? item.account_id === null || item.account_id === accountId : true))
    .map(cloneAlertRule);
}

export async function listCustomerProfiles(accountId?: string): Promise<CustomerProfileSummary[]> {
  const [users, conversations, ticketsResult] = await Promise.all([
    listPlatformUsers(),
    listConversations(accountId ? { account_id: accountId } : undefined),
    listSupportTickets(accountId ? { account_id: accountId } : undefined).catch(() => [] as SupportTicket[]),
  ]);
  const tickets = ticketsResult as SupportTicket[];

  return users
    .filter((user) => (accountId ? user.account_id === accountId : true))
    .map((user) => {
      const matchedConversations = conversations.filter((conversation) =>
        matchesConversation(user, conversation)
      );
      const matchedTickets = tickets.filter((ticket) => matchesTicket(user, ticket));
      return mapCustomerSummary(user, matchedConversations, matchedTickets);
    })
    .sort((left, right) => {
      const leftTime = left.last_active_at ? new Date(left.last_active_at).getTime() : 0;
      const rightTime = right.last_active_at ? new Date(right.last_active_at).getTime() : 0;
      return rightTime - leftTime;
    });
}

export function selectCustomerProfileForConversation(
  profiles: readonly CustomerProfileSummary[],
  conversation: Pick<ConversationSummary, "customer_id">
): CustomerProfileSummary | null {
  const exactPublicUserMatch =
    profiles.find((profile) => profile.public_user_id === conversation.customer_id) ?? null;
  if (exactPublicUserMatch) {
    return exactPublicUserMatch;
  }

  const relatedMatches = profiles.filter(
    (profile) =>
      profile.relatedCustomerIds.includes(conversation.customer_id) ||
      profile.identity_values.includes(conversation.customer_id)
  );
  if (relatedMatches.length === 0) {
    return null;
  }

  return [...relatedMatches].sort((left, right) => {
    const leftTime = left.last_active_at ? Date.parse(left.last_active_at) : 0;
    const rightTime = right.last_active_at ? Date.parse(right.last_active_at) : 0;
    return rightTime - leftTime;
  })[0] ?? null;
}

export async function resolveCustomerProfileSummaryByConversation(
  conversation: Pick<ConversationSummary, "account_id" | "customer_id">
): Promise<CustomerProfileSummary | null> {
  const profiles = await listCustomerProfiles(conversation.account_id);
  return selectCustomerProfileForConversation(profiles, conversation);
}

export async function getCustomerProfileDetail(
  profileId: string,
  accountId?: string
): Promise<CustomerProfileDetail> {
  const [users, conversations, tickets] = await Promise.all([
    listPlatformUsers(),
    listConversations(accountId ? { account_id: accountId } : undefined),
    listSupportTickets(accountId ? { account_id: accountId } : undefined),
  ]);

  const user = users.find((item) => item.id === profileId);
  if (!user) {
    throw new Error("未找到客户档案。");
  }

  if (accountId && user.account_id !== accountId) {
    throw new Error("褰撳墠璐﹀彿涓嬫湭鎵惧埌瀹㈡埛妗ｆ銆?");
  }

  const matchedConversations = conversations.filter((conversation) =>
    matchesConversation(user, conversation)
  );
  const matchedTickets = tickets.filter((ticket) => matchesTicket(user, ticket));
  const profile = mapCustomerSummary(user, matchedConversations, matchedTickets);
  const aiStatusEntries = await Promise.all(
    matchedConversations.map(async (conversation) => {
      try {
        const status = await getConversationAiStatus(
          conversation.account_id,
          conversation.conversation_id
        );
        return [getScopedConversationKey(conversation.account_id, conversation.conversation_id), status] as const;
      } catch {
        return [getScopedConversationKey(conversation.account_id, conversation.conversation_id), null] as const;
      }
    })
  );
  const aiStatusMap = new Map(aiStatusEntries);

  const conversationLinks: CustomerConversationLink[] = matchedConversations.map((conversation) => ({
    account_id: conversation.account_id,
    conversation_id: conversation.conversation_id,
    customer_id: conversation.customer_id,
    waba_id: conversation.waba_id,
    phone_number_id: conversation.phone_number_id,
    status: conversation.status,
    management_mode: conversation.management_mode,
    ai_enabled: conversation.ai_enabled,
    effective_ai_enabled:
      aiStatusMap.get(getScopedConversationKey(conversation.account_id, conversation.conversation_id))
        ?.effective_ai_enabled ??
      conversation.ai_enabled,
    ai_reason:
      aiStatusMap.get(getScopedConversationKey(conversation.account_id, conversation.conversation_id))
        ?.primary_blocking_reason?.message ??
      (aiStatusMap.get(getScopedConversationKey(conversation.account_id, conversation.conversation_id))
        ?.effective_ai_enabled
        ? "鍏ㄥ眬 / 璐﹀彿 / 浼氳瘽 / 鎺ョ閾捐矾鍏佽"
        : "AI 鐘舵€佹帴鍙ｄ笉鍙敤锛屽洖閫€浼氳瘽鏍囪"),
    assigned_agent_name: conversation.assigned_agent_name,
    last_message_at: conversation.last_message_at,
    last_message_preview: conversation.last_message_preview,
  }));

  const ticketLinks: CustomerTicketLink[] = matchedTickets.map((ticket) => ({
    id: ticket.id,
    account_id: ticket.account_id,
    category: ticket.category,
    status: ticket.status,
    priority: ticket.priority,
    subject: ticket.subject,
    updated_at: ticket.updated_at,
  }));

  return {
    profile,
    identities: user.identities,
    tags: user.tags.map((tag) => ({
      tag_key: tag.tag_key,
      name: tag.name,
      color: tag.color,
      source_type: tag.source_type,
    })),
    conversations: conversationLinks,
    tickets: ticketLinks,
  };
}

function buildQueueAlertItems(
  queueStats: QueueStatsResponse | null
): AlertCenterItem[] {
  if (!queueStats) return [];

  return queueStats.recent_failed_jobs.slice(0, 4).map((job: QueueJob) => ({
    id: `queue:${job.job_id}`,
    account_id:
      typeof job.payload.account_id === "string" ? job.payload.account_id : null,
    title: `队列失败 / ${job.queue}`,
    summary: job.error ?? "任务失败",
    severity: "critical",
    category: "queue",
    source: "api",
    status: job.status,
    occurred_at: job.failed_at ?? job.updated_at,
    action_label: null,
    replay_payload: null,
  }));
}

function buildProviderReplayPayload(
  entry: ProviderStatusBufferEntry
): AlertReplayPayload {
  return {
    account_id: entry.account_id,
    provider_name: entry.provider_name,
    provider_message_id: entry.provider_message_id,
    external_status: entry.external_status,
    waba_id: entry.waba_id ?? undefined,
    phone_number_id: entry.phone_number_id ?? undefined,
    limit: 1,
  };
}

function buildProviderAlertItems(
  entries: ProviderStatusBufferEntry[]
): AlertCenterItem[] {
  return entries.slice(0, 6).map((entry) => ({
    id: `provider:${entry.id}`,
    account_id: entry.account_id,
    title: `Provider 状态积压 / ${entry.provider_name}`,
    summary: `${entry.external_status} / ${entry.provider_message_id}`,
    severity: entry.error_code ? "critical" : "warning",
    category: "provider",
    source: "api",
    status: entry.replay_state,
    occurred_at: entry.last_seen_at,
    action_label: "回放状态",
    replay_payload: buildProviderReplayPayload(entry),
  }));
}

function buildAuditAlertItems(auditLogs: AuditLogEntry[]): AlertCenterItem[] {
  return auditLogs.slice(0, 4).map((entry) => ({
    id: `audit:${entry.id}`,
    account_id: entry.account_id,
    title: `审计事件 / ${entry.action}`,
    summary: `${entry.target_type} / ${entry.target_id ?? "n/a"}`,
    severity:
      entry.action.toLowerCase().includes("fail") || entry.action.toLowerCase().includes("error")
        ? "warning"
        : "info",
    category: "audit",
    source: "api",
    status: entry.actor_type,
    occurred_at: entry.created_at,
    action_label: null,
    replay_payload: null,
  }));
}

function buildConversationAlertItems(
  conversations: ConversationSummary[],
  accountId?: string
): AlertCenterItem[] {
  const openConversations = conversations.filter((item) => item.status === "open");
  const unassigned = openConversations.filter((item) => !item.assigned_agent_id);
  const handoverRecommended = openConversations.filter((item) => item.latest_handover_recommended);
  const items: AlertCenterItem[] = [];

  if (unassigned.length > 0) {
    items.push({
      id: `conversation:unassigned:${accountId ?? "all"}`,
      account_id: accountId ?? null,
      title: "开放会话未分配",
      summary: `${unassigned.length} 个开放会话未分配客服`,
      severity: unassigned.length >= 10 ? "critical" : "warning",
      category: "runtime",
      source: "hybrid",
      status: "unassigned",
      occurred_at: unassigned[0]?.last_message_at ?? new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  if (handoverRecommended.length > 0) {
    items.push({
      id: `conversation:handover:${accountId ?? "all"}`,
      account_id: accountId ?? null,
      title: "建议转人工会话",
      summary:
        handoverRecommended[0]?.latest_handover_reason ??
        `${handoverRecommended.length} 个会话建议人工接管`,
      severity: handoverRecommended.length >= 5 ? "warning" : "info",
      category: "runtime",
      source: "hybrid",
      status: "handover_recommended",
      occurred_at: handoverRecommended[0]?.last_message_at ?? new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  return items;
}

function buildTicketAlertItems(
  tickets: SupportTicket[],
  accountId?: string
): AlertCenterItem[] {
  const activeTickets = tickets.filter((item) => !["resolved", "closed", "cancelled"].includes(item.status));
  const urgentTickets = activeTickets.filter((item) => ["high", "urgent"].includes(item.priority));
  const stalePendingUser = activeTickets.filter((item) => {
    if (item.status !== "pending_user") return false;
    const anchor = item.last_reply_at ?? item.updated_at;
    return Date.now() - Date.parse(anchor) >= 4 * 60 * 60 * 1000;
  });
  const items: AlertCenterItem[] = [];

  if (urgentTickets.length > 0) {
    items.push({
      id: `ticket:priority:${accountId ?? "all"}`,
      account_id: accountId ?? null,
      title: "高优先级工单积压",
      summary: `${urgentTickets.length} 个高优先级工单待处理`,
      severity: urgentTickets.some((item) => item.priority === "urgent") ? "critical" : "warning",
      category: "runtime",
      source: "hybrid",
      status: "high_priority_ticket",
      occurred_at: urgentTickets[0]?.updated_at ?? new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  if (stalePendingUser.length > 0) {
    items.push({
      id: `ticket:pending-user:${accountId ?? "all"}`,
      account_id: accountId ?? null,
      title: "待用户补充工单超时",
      summary: `${stalePendingUser.length} 个工单超过 4 小时未跟进`,
      severity: "info",
      category: "runtime",
      source: "hybrid",
      status: "pending_user",
      occurred_at: stalePendingUser[0]?.last_reply_at ?? stalePendingUser[0]?.updated_at ?? new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  return items;
}

function buildRuntimeAlertItems(runtimeState: RuntimeState | null, accountId?: string): AlertCenterItem[] {
  if (!runtimeState) return [];

  const scopedConversations = runtimeState.conversations.filter((item) =>
    accountId ? item.account_id === accountId : true
  );
  const humanManaged = scopedConversations.filter((item) => item.management_mode === "human_managed");
  const paused = scopedConversations.filter((item) => item.management_mode === "paused");
  const items: AlertCenterItem[] = [];

  if (humanManaged.length > 0) {
    items.push({
      id: "runtime:human-managed",
      account_id: accountId ?? null,
      title: "人工接管会话",
      summary: `${humanManaged.length} 个会话处于人工接管`,
      severity: humanManaged.length >= 10 ? "warning" : "info",
      category: "runtime",
      source: "hybrid",
      status: "human_managed",
      occurred_at: new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  if (paused.length > 0) {
    items.push({
      id: "runtime:paused",
      account_id: accountId ?? null,
      title: "暂停会话",
      summary: `${paused.length} 个会话处于暂停`,
      severity: "info",
      category: "runtime",
      source: "hybrid",
      status: "paused",
      occurred_at: new Date().toISOString(),
      action_label: null,
      replay_payload: null,
    });
  }

  return items;
}

function sortAlertItems(items: AlertCenterItem[]): AlertCenterItem[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.occurred_at).getTime();
    const rightTime = new Date(right.occurred_at).getTime();
    return rightTime - leftTime;
  });
}

function resolveAlertHealth(
  metrics: MetricsSummaryResponse | null,
  queueStats: QueueStatsResponse | null,
  providerItems: ProviderStatusBufferEntry[]
): AlertCenterSnapshot["service_health"] {
  const failedJobs = queueStats?.recent_failed_jobs.length ?? 0;
  if (failedJobs > 0) return "critical";
  if ((metrics?.queue.failed_current ?? 0) > 0) return "critical";
  if (providerItems.length > 0) return "warning";
  return "healthy";
}

export async function getAlertCenterSnapshot(
  accountId?: string
): Promise<AlertCenterSnapshot> {
  const [
    runtimeResult,
    queueResult,
    metricsResult,
    providerResult,
    auditResult,
    conversationsResult,
    ticketsResult,
  ] = await Promise.allSettled([
    listRuntimeState(),
    listQueueStats(),
    getMetricsSummary(),
    listProviderStatusBuffer({
      account_id: accountId,
      replay_state: "pending",
      limit: 6,
    }),
    listAuditLogs(accountId ? { account_id: accountId, limit: 8 } : { limit: 8 }),
    listConversations(accountId ? { account_id: accountId } : undefined),
    listSupportTickets(accountId ? { account_id: accountId } : undefined),
  ]);

  const runtimeState = runtimeResult.status === "fulfilled" ? runtimeResult.value : null;
  const queueStats = queueResult.status === "fulfilled" ? queueResult.value : null;
  const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
  const providerItems =
    providerResult.status === "fulfilled" ? providerResult.value.items : [];
  const auditLogs = auditResult.status === "fulfilled" ? auditResult.value : [];
  const conversations = conversationsResult.status === "fulfilled" ? conversationsResult.value : [];
  const tickets = ticketsResult.status === "fulfilled" ? ticketsResult.value : [];

  const items = sortAlertItems([
    ...buildQueueAlertItems(queueStats),
    ...buildProviderAlertItems(providerItems),
    ...buildAuditAlertItems(auditLogs),
    ...buildConversationAlertItems(conversations, accountId),
    ...buildTicketAlertItems(tickets, accountId),
    ...buildRuntimeAlertItems(runtimeState, accountId),
  ]);

  return {
    account_id: accountId ?? null,
    generated_at: new Date().toISOString(),
    metrics_generated_at: metrics?.generated_at ?? null,
    service_health: resolveAlertHealth(metrics, queueStats, providerItems),
    queue_backlog:
      (metrics?.queue.queued_current ?? 0) + (metrics?.queue.processing_current ?? 0),
    failed_jobs:
      queueStats?.recent_failed_jobs.length ?? metrics?.queue.failed_current ?? 0,
    provider_pending: providerItems.length,
    audit_event_count: auditLogs.length,
    runtime_alert_count: items.filter((item) => item.category === "runtime").length,
    items,
  };
}

function buildReportKpis(
  metrics: MetricsSummaryResponse | null,
  whatsAppSummary: WhatsAppStatsSummary | null,
  templateSummary: TemplateStatsSummary | null
): ReportCenterKpi[] {
  return [
    {
      key: "inbound",
      label: "入站消息",
      value: whatsAppSummary?.inbound_message_count ?? metrics?.inbound.accepted_total ?? 0,
      source: "api",
      detail: "WhatsApp 统计 / metrics",
    },
    {
      key: "outbound",
      label: "出站消息",
      value: whatsAppSummary?.outbound_message_count ?? metrics?.outbound.accepted_total ?? 0,
      source: "api",
      detail: "WhatsApp 统计 / metrics",
    },
    {
      key: "delivered",
      label: "已送达",
      value: whatsAppSummary?.delivered_count ?? templateSummary?.delivered_count ?? 0,
      source: "api",
      detail: "送达汇总",
    },
    {
      key: "read",
      label: "已读",
      value: whatsAppSummary?.read_count ?? templateSummary?.read_count ?? 0,
      source: "api",
      detail: "已读汇总",
    },
    {
      key: "failed",
      label: "失败量",
      value: whatsAppSummary?.failed_count ?? templateSummary?.failed_count ?? 0,
      source: "api",
      detail: "失败统计",
    },
    {
      key: "cost",
      label: "预估成本",
      value:
        whatsAppSummary?.estimated_cost ??
        templateSummary?.estimated_cost ??
        0,
      source: "api",
      detail: "计费估算",
    },
  ];
}

function mapWhatsAppDailyRows(rows: WhatsAppStatsDailyRow[]): ReportCenterDailyRow[] {
  return rows.map((row) => ({
    source_kind: "whatsapp",
    date: row.date,
    account_id: row.account_id,
    label: row.phone_number_id ?? row.waba_id ?? "whatsapp",
    inbound_count: row.inbound_message_count,
    outbound_count: row.outbound_message_count,
    delivered_count: row.delivered_count,
    read_count: row.read_count,
    failed_count: row.failed_count,
    estimated_cost: row.estimated_cost,
  }));
}

function mapTemplateDailyRows(rows: TemplateStatsDailyRow[]): ReportCenterDailyRow[] {
  return rows.map((row) => ({
    source_kind: "template",
    date: row.date,
    account_id: row.account_id,
    label: row.template_name,
    delivered_count: row.delivered_count,
    read_count: row.read_count,
    failed_count: row.failed_count,
    estimated_cost: row.estimated_cost,
  }));
}

function mapTemplateOption(template: MessageTemplateView): ReportTemplateOption {
  return {
    template_id: template.template_id,
    account_id: template.account_id,
    name: template.name,
    language: template.language,
    status: template.status,
  };
}

function mapTemplateAnalytics(
  detail: TemplateStatsDetailResponse | null
): ReportTemplateAnalyticsView | null {
  if (!detail) return null;
  return {
    template_id: detail.template_id,
    template_name: detail.template_name,
    account_id: detail.account_id,
    language: detail.template_language,
    category: detail.template_category,
    send_count: detail.summary.send_count,
    delivered_count: detail.summary.delivered_count,
    read_count: detail.summary.read_count,
    failed_count: detail.summary.failed_count,
    estimated_cost: detail.summary.estimated_cost,
    failure_reasons: detail.failure_reasons.map((item) => ({ ...item })),
  };
}

export async function getReportCenterSnapshot(
  accountId?: string,
  templateId?: string
): Promise<ReportCenterSnapshot> {
  const [metricsResult, whatsAppSummaryResult, whatsAppDailyResult, templateSummaryResult, templateDailyResult, templateListResult, templateAnalyticsResult] =
    await Promise.allSettled([
      getMetricsSummary(),
      getWhatsAppStatsSummary(accountId ? { account_id: accountId } : undefined),
      listWhatsAppDailyStats(accountId ? { account_id: accountId } : undefined),
      getTemplateStatsSummary(accountId ? { account_id: accountId } : undefined),
      listTemplateDailyStats(accountId ? { account_id: accountId } : undefined),
      listMessageTemplates(accountId),
      templateId ? getTemplateAnalytics(templateId) : Promise.resolve(null),
    ]);

  const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : null;
  const whatsAppSummary =
    whatsAppSummaryResult.status === "fulfilled" ? whatsAppSummaryResult.value : null;
  const whatsAppDaily =
    whatsAppDailyResult.status === "fulfilled" ? whatsAppDailyResult.value : [];
  const templateSummary =
    templateSummaryResult.status === "fulfilled" ? templateSummaryResult.value : null;
  const templateDaily =
    templateDailyResult.status === "fulfilled" ? templateDailyResult.value : [];
  const templateList =
    templateListResult.status === "fulfilled" ? templateListResult.value : [];
  const templateAnalytics =
    templateAnalyticsResult.status === "fulfilled"
      ? mapTemplateAnalytics(templateAnalyticsResult.value)
      : null;

  return {
    account_id: accountId ?? null,
    generated_at: new Date().toISOString(),
    kpis: buildReportKpis(metrics, whatsAppSummary, templateSummary),
    daily_rows: [...mapWhatsAppDailyRows(whatsAppDaily), ...mapTemplateDailyRows(templateDaily)]
      .sort((left, right) => right.date.localeCompare(left.date))
      .slice(0, 20),
    template_options: templateList.map(mapTemplateOption),
    template_analytics: templateAnalytics,
  };
}

function mapKnowledgeEntry(entry: SupportKnowledgeEntryView): KnowledgeEntrySummary {
  return {
    account_id: entry.account_id,
    article_id: entry.article_id,
    route_name: entry.route_name,
    category: entry.category,
    title: entry.title,
    source_language: entry.source_language,
    is_active: entry.is_active,
    source_type: entry.source_type,
    keywords: [...entry.keywords],
  };
}

export async function getImportExportCenterSnapshot(
  accountId?: string
): Promise<ImportExportCenterSnapshot> {
  const entries = await listSupportKnowledge(undefined, accountId, true);
  const categoriesMap = new Map<string, KnowledgeCategorySummary>();

  for (const entry of entries) {
    const current = categoriesMap.get(entry.category) ?? {
      category: entry.category,
      total_count: 0,
      active_count: 0,
      builtin_count: 0,
      database_count: 0,
    };
    current.total_count += 1;
    if (entry.is_active) current.active_count += 1;
    if (entry.source_type === "builtin") current.builtin_count += 1;
    if (entry.source_type === "database") current.database_count += 1;
    categoriesMap.set(entry.category, current);
  }

  return {
    account_id: accountId ?? null,
    generated_at: new Date().toISOString(),
    total_entries: entries.length,
    active_entries: entries.filter((item) => item.is_active).length,
    builtin_entries: entries.filter((item) => item.source_type === "builtin").length,
    database_entries: entries.filter((item) => item.source_type === "database").length,
    categories: Array.from(categoriesMap.values()).sort((left, right) =>
      left.category.localeCompare(right.category, "zh-CN")
    ),
    entries: entries.map(mapKnowledgeEntry),
  };
}

export async function runSupportKnowledgeExport(
  accountId?: string
): Promise<SupportKnowledgeExportBundle> {
  return exportSupportKnowledge(accountId);
}

export async function runSupportKnowledgeImport(
  rawText: string,
  targetAccountId?: string,
  upsertExisting = true
): Promise<SupportKnowledgeImportResult> {
  const parsed = JSON.parse(rawText) as
    | SupportKnowledgeExportBundle
    | SupportKnowledgeEntryView[]
    | { entries?: SupportKnowledgeExportBundle["entries"] };

  const entries = Array.isArray(parsed)
    ? parsed.map((item) => ({
        account_id: item.account_id ?? targetAccountId ?? "",
        article_id: item.article_id,
        route_name: item.route_name,
        category: item.category,
        title: item.title,
        answer: "answer" in item ? item.answer : "",
        source_language: item.source_language,
        keywords: [...item.keywords],
        minimum_score: "minimum_score" in item ? item.minimum_score : 1,
        priority: "priority" in item ? item.priority : 100,
        is_active: "is_active" in item ? item.is_active : true,
      }))
    : "entries" in parsed && Array.isArray(parsed.entries)
      ? parsed.entries
      : [];

  if (entries.length === 0) {
    throw new Error("No import entries found");
  }

  return importSupportKnowledge({
    target_account_id: targetAccountId,
    upsert_existing: upsertExisting,
    entries,
  });
}

function buildRiskCases(accountId?: string): RiskCaseItem[] {
  return riskCaseStore
    .filter((item) => (accountId ? item.account_id === accountId : true))
    .map(cloneRiskCase)
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
}

export async function getRiskCenterSnapshot(accountId?: string): Promise<RiskCenterSnapshot> {
  return {
    account_id: accountId ?? null,
    generated_at: new Date().toISOString(),
    profiles: riskProfileStore
      .filter((item) => (accountId ? item.account_id === accountId : true))
      .map(cloneRiskProfile)
      .sort((left, right) => (right.last_hit_at ?? "").localeCompare(left.last_hit_at ?? "")),
    cases: buildRiskCases(accountId),
  };
}

export async function createRiskProfile(
  payload: RiskProfileCreatePayload
): Promise<RiskProfileItem> {
  const created: RiskProfileItem = {
    id: `risk-profile-${Date.now()}`,
    account_id: payload.account_id ?? null,
    target_type: payload.target_type,
    target_value: payload.target_value.trim(),
    display_name: payload.display_name.trim(),
    status: payload.status,
    reason: payload.reason.trim(),
    hit_count_7d: 0,
    last_hit_at: null,
    source: "mock",
  };
  riskProfileStore.unshift(created);
  return cloneRiskProfile(created);
}

export async function updateRiskProfileStatus(
  profileId: string,
  status: RiskProfileItem["status"]
): Promise<RiskProfileItem> {
  const target = riskProfileStore.find((item) => item.id === profileId);
  if (!target) {
    throw new Error("Risk profile not found");
  }
  target.status = status;
  target.last_hit_at = target.last_hit_at ?? new Date().toISOString();
  return cloneRiskProfile(target);
}

function mapOperationsTask(task: TaskInstance): OperationsTaskItem {
  return {
    id: task.id,
    account_id: task.account_id,
    user_id: task.user_id,
    template_name: task.template_name,
    public_user_id: task.public_user_id,
    status: task.status,
    review_required: task.review_required,
    active_ticket_count: task.active_ticket_count ?? 0,
    available_at: task.available_at,
    source: "api",
  };
}

function mapOperationsProviderItem(
  entry: ProviderStatusBufferEntry
): OperationsProviderBacklogItem {
  return {
    id: entry.id,
    account_id: entry.account_id,
    provider_name: entry.provider_name,
    external_status: entry.external_status,
    replay_state: entry.replay_state,
    provider_message_id: entry.provider_message_id,
    occurred_at: entry.occurred_at,
    replay_payload: buildProviderReplayPayload(entry),
    source: "api",
  };
}

export async function getOperationsCenterSnapshot(
  accountId?: string
): Promise<OperationsCenterSnapshot> {
  const [queueResult, tasksResult, providerResult, auditResult] = await Promise.allSettled([
    listQueueStats(),
    listTaskInstances(accountId ? { account_id: accountId } : undefined),
    listProviderStatusBuffer({
      account_id: accountId,
      replay_state: "pending",
      limit: 8,
    }),
    listAuditLogs(accountId ? { account_id: accountId, limit: 8 } : { limit: 8 }),
  ]);

  const queueStats = queueResult.status === "fulfilled" ? queueResult.value : null;
  const tasks = tasksResult.status === "fulfilled" ? tasksResult.value : [];
  const providerItems =
    providerResult.status === "fulfilled" ? providerResult.value.items : [];
  const auditItems = auditResult.status === "fulfilled" ? auditResult.value : [];

  return {
    account_id: accountId ?? null,
    generated_at: new Date().toISOString(),
    queued_jobs: queueStats?.queues.reduce((sum, item) => sum + item.queued, 0) ?? 0,
    processing_jobs: queueStats?.queues.reduce((sum, item) => sum + item.processing, 0) ?? 0,
    failed_jobs: queueStats?.recent_failed_jobs.length ?? 0,
    provider_pending: providerItems.length,
    tasks: tasks.slice(0, 10).map(mapOperationsTask),
    provider_backlog: providerItems.map(mapOperationsProviderItem),
    audit_items: auditItems.map((item) => ({
      id: item.id,
      account_id: item.account_id,
      action: item.action,
      target_type: item.target_type,
      target_id: item.target_id,
      created_at: item.created_at,
      source: "api" as const,
    })),
    batch_jobs: operationsBatchJobStore
      .filter((item) => (accountId ? item.account_id === accountId : true))
      .map(cloneBatchJob),
  };
}

export async function claimOperationsTask(taskId: string): Promise<OperationsTaskItem> {
  const claimed = await claimTaskInstance(taskId);
  return mapOperationsTask(claimed);
}

export async function replayOperationsProviderStatus(
  payload: AlertReplayPayload
): Promise<{ replayed_count: number; failed_count: number }> {
  const result = await replayProviderStatusBuffer(payload);
  return {
    replayed_count: result.replayed_count,
    failed_count: result.failed_count,
  };
}

export async function createOperationsBatchJob(
  payload: OperationsBatchJobCreatePayload
): Promise<OperationsBatchJob> {
  const created: OperationsBatchJob = {
    job_id: `batch-job-${Date.now()}`,
    account_id: payload.account_id ?? null,
    name: payload.name.trim(),
    target_scope: payload.target_scope.trim(),
    status: "queued",
    affected_count: payload.affected_count,
    updated_at: new Date().toISOString(),
    source: "mock",
  };
  operationsBatchJobStore.unshift(created);
  return cloneBatchJob(created);
}

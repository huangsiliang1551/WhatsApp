import { getAccessControlSnapshot } from "./accessControl";
import { getIntegrationCenterSnapshot } from "./adminCenter";
import { listMemberDirectory, listRoleDefinitions } from "./operations";
import { getSecuritySettingsSnapshot } from "./securityCenter";
import {
  mockIdentityDomains,
  mockIdentityMappings,
  mockIdentitySyncJobs,
} from "../mocks/identitySync";
import type {
  IdentityDomainBinding,
  IdentityMemberPreview,
  IdentityProviderStatus,
  IdentityProviderView,
  IdentityRoleMapping,
  IdentityRoleMappingPayload,
  IdentitySessionPreview,
  IdentitySyncJob,
  IdentitySyncSnapshot,
} from "../types/identitySync";
import type { IntegrationCenterSnapshot } from "../types/integrations";
import type { RoleDefinition } from "../types/operations";
import type {
  AccessControlSnapshot,
  AccessPolicyItem,
  AdminSessionItem,
} from "../types/accessControl";
import type { SecuritySessionPolicy, SecuritySsoProvider } from "../types/securitySettings";

const domainStore = mockIdentityDomains.map(cloneDomain);
const mappingStore = mockIdentityMappings.map(cloneMapping);
const jobStore = mockIdentitySyncJobs.map(cloneJob);

function cloneDomain(domain: IdentityDomainBinding): IdentityDomainBinding {
  return { ...domain };
}

function cloneMapping(mapping: IdentityRoleMapping): IdentityRoleMapping {
  return {
    ...mapping,
    account_scope: [...mapping.account_scope],
    page_scope: [...mapping.page_scope],
  };
}

function cloneJob(job: IdentitySyncJob): IdentitySyncJob {
  return { ...job };
}

function filterByAccount<T extends { account_id: string | null }>(items: T[], accountId?: string): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

function findPolicy(
  accountId: string | null,
  policies: AccessPolicyItem[],
  sessionPolicies: SecuritySessionPolicy[]
): { login_mode: SecuritySessionPolicy["login_mode"]; mfa_required: boolean } {
  const sessionPolicy =
    sessionPolicies.find((item) => item.account_id && item.account_id === accountId) ??
    sessionPolicies.find((item) => item.account_id === null) ??
    null;
  const accessPolicy =
    policies.find((item) => item.account_id && item.account_id === accountId) ??
    policies.find((item) => item.account_id === null) ??
    null;

  return {
    login_mode: sessionPolicy?.login_mode ?? accessPolicy?.login_mode ?? "mixed",
    mfa_required: sessionPolicy?.mfa_required ?? accessPolicy?.mfa_required ?? true,
  };
}

function getLatestTimestamp(values: Array<string | null | undefined>): string | null {
  const timestamps = values
    .filter((value): value is string => Boolean(value))
    .map((value) => Date.parse(value))
    .filter((value) => Number.isFinite(value));
  if (!timestamps.length) {
    return null;
  }
  return new Date(Math.max(...timestamps)).toISOString();
}

function getAccountBindingState(
  provider: SecuritySsoProvider,
  integrations: IntegrationCenterSnapshot | null
): { status: IdentityProviderStatus; reason: string } {
  if (!provider.account_id) {
    return {
      status: "linked",
      reason: "全局后台身份源不依赖单一 Meta 账号",
    };
  }

  const matched = integrations?.accounts.find((item) => item.account_id === provider.account_id) ?? null;
  if (!matched) {
    return {
      status: "missing",
      reason: "未发现对应账号接入摘要",
    };
  }

  if (matched.ready_for_formal_activation || matched.ready_for_webhook_delivery) {
    return {
      status: "linked",
      reason: "账号接入已就绪，可继续联调身份源规则",
    };
  }

  return {
    status: "limited",
    reason: matched.blocking_reasons[0] ?? "账号接入仍有待补项",
  };
}

function mapProvider(
  provider: SecuritySsoProvider,
  roles: RoleDefinition[],
  members: IdentityMemberPreview[],
  sessions: IdentitySessionPreview[],
  accessSnapshot: AccessControlSnapshot | null,
  sessionPolicies: SecuritySessionPolicy[],
  integrations: IntegrationCenterSnapshot | null
): IdentityProviderView {
  const scopedMappings = mappingStore.filter((item) => item.provider_id === provider.provider_id);
  const scopedMembers = members.filter((item) => item.provider_id === provider.provider_id);
  const scopedSessions = sessions.filter((item) => item.provider_id === provider.provider_id);
  const policy = findPolicy(provider.account_id, accessSnapshot?.policies ?? [], sessionPolicies);
  const bindingState = getAccountBindingState(provider, integrations);

  const derivedRoleCount = scopedMappings.filter((item) =>
    roles.some((role) => role.role_key === item.role_key)
  ).length;

  return {
    provider_id: provider.provider_id,
    account_id: provider.account_id,
    provider_name: provider.provider_name,
    enabled: provider.enabled,
    login_mode: policy.login_mode,
    mfa_required: policy.mfa_required,
    mapped_role_count: Math.max(provider.mapped_role_count, derivedRoleCount),
    mapped_member_count: scopedMembers.filter((item) => item.access_result !== "restricted").length,
    directory_member_count: scopedMembers.length,
    active_session_count: scopedSessions.filter((item) => item.status !== "revoked").length,
    account_binding_status: bindingState.status,
    account_binding_reason: bindingState.reason,
    last_sync_at: getLatestTimestamp([
      provider.last_sync_at,
      ...jobStore
        .filter((item) => item.provider_id === provider.provider_id)
        .map((item) => item.finished_at ?? item.started_at),
    ]),
    effective_result: provider.effective_result,
    effective_reason: provider.effective_reason,
    source: "hybrid",
  };
}

function buildMembers(
  providers: SecuritySsoProvider[],
  members: Awaited<ReturnType<typeof listMemberDirectory>>,
  accessSnapshot: AccessControlSnapshot | null
): IdentityMemberPreview[] {
  return providers.flatMap((provider) => {
    const scopedMembers = members.filter((item) =>
      provider.account_id ? item.account_id === provider.account_id : true
    );
    return scopedMembers.map((member) => {
      const matchedPolicy =
        accessSnapshot?.policies.find(
          (item) => item.account_id === member.account_id || item.account_id === null
        ) ?? null;
      const session =
        accessSnapshot?.sessions.find(
          (item) => item.agent_id === member.agent_id && item.account_id === member.account_id
        ) ?? null;
      const access_result = !member.is_active
        ? "restricted"
        : matchedPolicy?.effective_status === "review" || matchedPolicy?.effective_status === "partial"
          ? "review"
          : "active";
      const access_reason = !member.is_active
        ? "成员已停用"
        : session?.login_mode === "sso"
          ? "已通过 SSO 会话进入后台"
          : matchedPolicy?.effective_reason ?? "目录成员已进入身份源作用域";

      return {
        provider_id: provider.provider_id,
        account_id: member.account_id,
        agent_id: member.agent_id,
        display_name: member.display_name,
        role_labels: [...member.role_labels],
        access_result,
        access_reason,
        source: "hybrid",
      };
    });
  });
}

function buildSessions(
  providers: SecuritySsoProvider[],
  sessions: AdminSessionItem[]
): IdentitySessionPreview[] {
  return providers.flatMap((provider) =>
    sessions
      .filter((session) => (provider.account_id ? session.account_id === provider.account_id : true))
      .map((session) => ({
        provider_id: provider.provider_id,
        account_id: session.account_id,
        session_id: session.session_id,
        display_name: session.display_name,
        role_name: session.role_name,
        status: session.status,
        login_mode: session.login_mode,
        mfa_verified: session.mfa_verified,
        last_seen_at: session.last_seen_at,
        source: session.source,
      }))
  );
}

function updateMappingRoleDetails(mapping: IdentityRoleMapping, roles: RoleDefinition[]): IdentityRoleMapping {
  const matchedRole = roles.find((item) => item.role_key === mapping.role_key);
  return {
    ...mapping,
    role_name: matchedRole?.name ?? mapping.role_name,
    page_scope: mapping.page_scope.length ? [...mapping.page_scope] : [...(matchedRole?.page_scope ?? [])],
    account_scope:
      mapping.account_scope.length ? [...mapping.account_scope] : [...(matchedRole?.account_scope ?? [])],
  };
}

export async function getIdentitySyncSnapshot(accountId?: string): Promise<IdentitySyncSnapshot> {
  const [securityResult, accessResult, membersResult, rolesResult, integrationResult] =
    await Promise.allSettled([
      getSecuritySettingsSnapshot(accountId),
      getAccessControlSnapshot(accountId),
      listMemberDirectory(accountId),
      listRoleDefinitions(),
      getIntegrationCenterSnapshot(accountId),
    ]);

  if (securityResult.status !== "fulfilled") {
    throw new Error(
      securityResult.reason instanceof Error
        ? securityResult.reason.message
        : "身份源页加载失败"
    );
  }

  const warnings: string[] = [...securityResult.value.warnings];
  if (accessResult.status !== "fulfilled") warnings.push("访问控制快照加载失败");
  if (membersResult.status !== "fulfilled") warnings.push("成员目录加载失败");
  if (rolesResult.status !== "fulfilled") warnings.push("角色目录加载失败");
  if (integrationResult.status !== "fulfilled") warnings.push("账号接入摘要加载失败");

  const accessSnapshot = accessResult.status === "fulfilled" ? accessResult.value : null;
  const members = membersResult.status === "fulfilled" ? membersResult.value : [];
  const roles = rolesResult.status === "fulfilled" ? rolesResult.value : [];
  const integrations = integrationResult.status === "fulfilled" ? integrationResult.value : null;
  const securitySnapshot = securityResult.value;

  const memberPreviews = buildMembers(securitySnapshot.sso_providers, members, accessSnapshot);
  const sessionPreviews = buildSessions(securitySnapshot.sso_providers, accessSnapshot?.sessions ?? []);

  const providers = filterByAccount(securitySnapshot.sso_providers, accountId)
    .map((provider) =>
      mapProvider(
        provider,
        roles,
        memberPreviews,
        sessionPreviews,
        accessSnapshot,
        securitySnapshot.session_policies,
        integrations
      )
    )
    .sort((left, right) => left.provider_name.localeCompare(right.provider_name, "zh-CN"));

  const mappings = filterByAccount(mappingStore, accountId)
    .map((mapping) => updateMappingRoleDetails(cloneMapping(mapping), roles))
    .sort((left, right) => right.priority - left.priority);

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    providers,
    roles,
    domains: filterByAccount(domainStore, accountId).map(cloneDomain),
    mappings,
    jobs: filterByAccount(jobStore, accountId)
      .map(cloneJob)
      .sort((left, right) => Date.parse(right.started_at) - Date.parse(left.started_at)),
    members: memberPreviews.filter((item) => providers.some((provider) => provider.provider_id === item.provider_id)),
    sessions: sessionPreviews.filter((item) =>
      providers.some((provider) => provider.provider_id === item.provider_id)
    ),
    warnings,
  };
}

export async function saveIdentityRoleMapping(
  payload: IdentityRoleMappingPayload
): Promise<IdentityRoleMapping> {
  const normalizedAccountId = payload.account_id?.trim() || null;
  const now = new Date().toISOString();
  const nextMapping: IdentityRoleMapping = {
    mapping_id: `identity-mapping-${payload.provider_id}-${payload.external_group}`.toLowerCase(),
    provider_id: payload.provider_id,
    account_id: normalizedAccountId,
    external_group: payload.external_group.trim(),
    role_key: payload.role_key,
    role_name: payload.role_key,
    account_scope: payload.account_scope.length ? [...payload.account_scope] : ["ALL"],
    page_scope: [...payload.page_scope],
    priority: payload.priority,
    mapped_member_count: 0,
    effective_result: "review",
    effective_reason: payload.effective_reason.trim() || "身份源映射已更新",
    source: "hybrid",
  };

  const targetIndex = mappingStore.findIndex(
    (item) =>
      item.provider_id === payload.provider_id &&
      item.external_group.toLowerCase() === payload.external_group.trim().toLowerCase()
  );

  if (targetIndex >= 0) {
    mappingStore[targetIndex] = nextMapping;
  } else {
    mappingStore.unshift(nextMapping);
  }

  jobStore.unshift({
    job_id: `identity-sync-job-${Date.now()}`,
    provider_id: payload.provider_id,
    account_id: normalizedAccountId,
    status: "queued",
    started_at: now,
    finished_at: null,
    imported_count: 0,
    updated_count: 1,
    error_count: 0,
    summary: `映射已保存，等待目录同步 / ${payload.external_group.trim()}`,
    source: "mock",
  });

  return cloneMapping(nextMapping);
}

export async function toggleIdentityDomain(domainId: string): Promise<IdentityDomainBinding> {
  const target = domainStore.find((item) => item.domain_id === domainId);
  if (!target) {
    throw new Error("身份域名不存在");
  }

  target.auto_provision_enabled = !target.auto_provision_enabled;
  target.effective_result =
    target.auto_provision_enabled && target.verified ? "active" : "review";
  target.effective_reason = target.auto_provision_enabled
    ? "已启用自动入站，等待下一轮目录同步"
    : "已关闭自动入站，目录成员仅保留现有绑定";

  return cloneDomain(target);
}

export async function triggerIdentitySync(providerId: string): Promise<IdentitySyncJob> {
  const providerMappings = mappingStore.filter((item) => item.provider_id === providerId);
  const providerDomains = domainStore.filter((item) => item.provider_id === providerId);
  const startedAt = new Date().toISOString();
  const created: IdentitySyncJob = {
    job_id: `identity-sync-job-${Date.now()}`,
    provider_id: providerId,
    account_id: providerMappings[0]?.account_id ?? providerDomains[0]?.account_id ?? null,
    status: "completed",
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    imported_count: providerDomains.filter((item) => item.verified).length * 3,
    updated_count: providerMappings.length,
    error_count: providerDomains.some((item) => !item.verified) ? 1 : 0,
    summary:
      providerDomains.some((item) => !item.verified)
        ? "同步完成，仍有未验证域名"
        : "同步完成，目录与角色映射已刷新",
    source: "mock",
  };
  jobStore.unshift(created);
  return cloneJob(created);
}

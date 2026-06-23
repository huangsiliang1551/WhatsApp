import {
  getRuntimeConfigSummary,
  listMetaAccounts,
  listPlatformSites,
  listRuntimeState,
  type MetaWabaAccount,
  type PlatformSite,
  type RuntimeAccountState,
  type RuntimeConfigSummary,
} from "./api";
import { listMemberDirectory } from "./operations";
import {
  mockOrganizationAccountScopes,
  mockOrganizationApprovalChains,
  mockOrganizationInviteDomains,
  mockOrganizationProfile,
  mockOrganizationUnits,
} from "../mocks/organization";
import type { MemberDirectoryItem } from "../types/operations";
import type {
  OrganizationAccountScope,
  OrganizationApprovalChain,
  OrganizationCenterSnapshot,
  OrganizationInviteDomain,
  OrganizationProfile,
  OrganizationUnit,
} from "../types/organization";

type MetaVerificationStatus = MetaWabaAccount["webhook_verification_status"];
type MetaRuntimeStatus = MetaWabaAccount["webhook_runtime_status"];

function cloneProfile(profile: OrganizationProfile): OrganizationProfile {
  return { ...profile };
}

function cloneScope(scope: OrganizationAccountScope): OrganizationAccountScope {
  return { ...scope };
}

function cloneUnit(unit: OrganizationUnit): OrganizationUnit {
  return {
    ...unit,
    account_scope: [...unit.account_scope],
  };
}

function cloneInviteDomain(domain: OrganizationInviteDomain): OrganizationInviteDomain {
  return { ...domain };
}

function cloneApprovalChain(chain: OrganizationApprovalChain): OrganizationApprovalChain {
  return {
    ...chain,
    approvers: [...chain.approvers],
  };
}

function getLatestIsoString(values: Array<string | null | undefined>): string | null {
  const timestamps = values
    .filter((value): value is string => Boolean(value))
    .map((value) => Date.parse(value))
    .filter((value) => Number.isFinite(value));
  if (!timestamps.length) {
    return null;
  }
  return new Date(Math.max(...timestamps)).toISOString();
}

function getVerificationPriority(status: MetaVerificationStatus | null | undefined): number {
  if (status === "failed") return 4;
  if (status === "pending") return 3;
  if (status === "unavailable") return 2;
  if (status === "verified") return 1;
  return 0;
}

function getRuntimePriority(status: MetaRuntimeStatus | null | undefined): number {
  if (status === "signature_failed" || status === "payload_invalid") return 5;
  if (status === "verification_pending") return 4;
  if (status === "pending") return 3;
  if (status === "healthy") return 2;
  return 0;
}

function getAggregateVerificationStatus(accounts: MetaWabaAccount[]): MetaVerificationStatus | null {
  if (!accounts.length) {
    return null;
  }
  return [...accounts]
    .sort(
      (left, right) =>
        getVerificationPriority(right.webhook_verification_status) -
        getVerificationPriority(left.webhook_verification_status)
    )[0]?.webhook_verification_status ?? null;
}

function getAggregateRuntimeStatus(accounts: MetaWabaAccount[]): MetaRuntimeStatus | null {
  if (!accounts.length) {
    return null;
  }
  return [...accounts]
    .sort(
      (left, right) =>
        getRuntimePriority(right.webhook_runtime_status) - getRuntimePriority(left.webhook_runtime_status)
    )[0]?.webhook_runtime_status ?? null;
}

function filterAccountScoped<T extends { account_id: string | null }>(
  items: T[],
  accountId?: string
): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

function buildProfile(
  config: RuntimeConfigSummary | null,
  accountScopes: OrganizationAccountScope[],
  memberCount: number | null
): OrganizationProfile {
  return {
    ...cloneProfile(mockOrganizationProfile),
    environment: config?.app_env ?? mockOrganizationProfile.environment,
    provider_mode: config ? (config.test_mode ? "mock" : "production") : mockOrganizationProfile.provider_mode,
    default_language: config?.console_language ?? mockOrganizationProfile.default_language,
    seat_used: memberCount ?? mockOrganizationProfile.seat_used,
    seat_limit: Math.max(
      mockOrganizationProfile.seat_limit,
      (memberCount ?? mockOrganizationProfile.seat_used) + 8
    ),
    source: "hybrid",
  };
}

function buildRealScopes(
  runtimeAccounts: RuntimeAccountState[],
  sites: PlatformSite[],
  members: MemberDirectoryItem[],
  metaAccounts: MetaWabaAccount[],
  requestedAccountId?: string
): OrganizationAccountScope[] {
  const accountIds = new Set<string>();
  runtimeAccounts.forEach((item) => item.account_id && accountIds.add(item.account_id));
  sites.forEach((item) => item.account_id && accountIds.add(item.account_id));
  members.forEach((item) => item.account_id && accountIds.add(item.account_id));
  metaAccounts.forEach((item) => item.account_id && accountIds.add(item.account_id));

  const filteredAccountIds = Array.from(accountIds)
    .filter((item) => (requestedAccountId ? item === requestedAccountId : true))
    .sort((left, right) => left.localeCompare(right, "zh-CN"));

  return filteredAccountIds.map((accountId) => {
    const runtimeAccount = runtimeAccounts.find((item) => item.account_id === accountId) ?? null;
    const scopedSites = sites.filter((item) => item.account_id === accountId);
    const scopedMembers = members.filter((item) => item.account_id === accountId);
    const scopedMetaAccounts = metaAccounts.filter((item) => item.account_id === accountId);
    const primaryMetaAccount =
      scopedMetaAccounts.find((item) => item.is_active || item.account_is_active) ?? scopedMetaAccounts[0] ?? null;

    return {
      account_id: accountId,
      display_name:
        runtimeAccount?.display_name ??
        scopedMetaAccounts[0]?.display_name ??
        mockOrganizationAccountScopes.find((item) => item.account_id === accountId)?.display_name ??
        accountId,
      is_active:
        runtimeAccount?.is_active ??
        scopedMetaAccounts.some((item) => item.account_is_active || item.is_active),
      ai_enabled: runtimeAccount?.ai_enabled ?? false,
      provider_type: runtimeAccount?.provider_type ?? "whatsapp",
      meta_business_portfolio_id: primaryMetaAccount?.meta_business_portfolio_id ?? null,
      primary_waba_id: primaryMetaAccount?.waba_id ?? null,
      site_count: scopedSites.length,
      member_count: scopedMembers.length,
      active_member_count: scopedMembers.filter((item) => item.is_active).length,
      waba_count: scopedMetaAccounts.length,
      active_waba_count: scopedMetaAccounts.filter((item) => item.is_active).length,
      phone_number_count: scopedMetaAccounts.reduce((sum, item) => sum + item.phone_number_count, 0),
      registered_phone_number_count: scopedMetaAccounts.reduce(
        (sum, item) => sum + item.registered_phone_number_count,
        0
      ),
      webhook_verification_status: getAggregateVerificationStatus(scopedMetaAccounts),
      webhook_runtime_status: getAggregateRuntimeStatus(scopedMetaAccounts),
      ready_for_webhook_delivery: scopedMetaAccounts.some((item) => item.ready_for_webhook_delivery),
      ready_for_outbound_messages: scopedMetaAccounts.some((item) => item.ready_for_outbound_messages),
      blocking_reasons: Array.from(
        new Set(scopedMetaAccounts.flatMap((item) => item.blocking_reasons).filter(Boolean))
      ),
      primary_site_key: scopedSites[0]?.site_key ?? null,
      last_webhook_event_at: getLatestIsoString(
        scopedMetaAccounts.map((item) => item.webhook_last_event_received_at)
      ),
      source: "api",
    };
  });
}

function getManagerName(members: MemberDirectoryItem[], fallbackName: string): string {
  const candidate = [...members]
    .sort((left, right) => {
      if (left.is_active !== right.is_active) {
        return left.is_active ? -1 : 1;
      }
      if (left.assigned_open_conversations !== right.assigned_open_conversations) {
        return right.assigned_open_conversations - left.assigned_open_conversations;
      }
      return left.display_name.localeCompare(right.display_name, "zh-CN");
    })
    .find((item) => item.display_name.trim().length > 0);
  return candidate?.display_name ?? fallbackName;
}

function buildDerivedUnits(
  accountScopes: OrganizationAccountScope[],
  members: MemberDirectoryItem[]
): OrganizationUnit[] {
  const units: OrganizationUnit[] = [];

  if (accountScopes.length || members.length) {
    units.push({
      unit_id: "unit-derived-platform",
      account_id: null,
      name: "平台治理",
      manager_name: getManagerName(members, mockOrganizationProfile.owner_name),
      member_count: members.length || accountScopes.reduce((sum, item) => sum + item.member_count, 0),
      account_scope: accountScopes.map((item) => item.account_id),
      status: "active",
      source: "hybrid",
    });
  }

  accountScopes.forEach((scope) => {
    const scopedMembers = members.filter((item) => item.account_id === scope.account_id);
    units.push({
      unit_id: `unit-derived-${scope.account_id}`,
      account_id: scope.account_id,
      name: `${scope.display_name} 服务组`,
      manager_name: getManagerName(
        scopedMembers,
        mockOrganizationUnits.find((item) => item.account_id === scope.account_id)?.manager_name ??
          mockOrganizationProfile.owner_name
      ),
      member_count: scopedMembers.length || scope.member_count,
      account_scope: [scope.account_id],
      status: scope.is_active ? "active" : "draft",
      source: "hybrid",
    });
  });

  const coveredAccounts = new Set(units.map((item) => item.account_id ?? "__global__"));
  const fallbackUnits = mockOrganizationUnits
    .filter((item) => !coveredAccounts.has(item.account_id ?? "__global__"))
    .map(cloneUnit);

  return [...units, ...fallbackUnits];
}

function buildDerivedInviteDomains(
  sites: PlatformSite[],
  accountScopes: OrganizationAccountScope[]
): OrganizationInviteDomain[] {
  if (!sites.length) {
    return mockOrganizationInviteDomains.map(cloneInviteDomain);
  }

  const derivedDomains: OrganizationInviteDomain[] = sites.map((site) => {
    const matchedScope = site.account_id
      ? accountScopes.find((item) => item.account_id === site.account_id) ?? null
      : null;
    const matchedMock =
      mockOrganizationInviteDomains.find((item) => item.domain === site.domain) ??
      mockOrganizationInviteDomains.find(
        (item) => item.account_id !== null && item.account_id === site.account_id
      ) ??
      null;
    const verified = matchedMock?.verified ?? site.status === "active";
    const ssoEnforced =
      matchedMock?.sso_enforced ?? Boolean(matchedScope && matchedScope.active_member_count > 0);
    const approvalMode =
      matchedMock?.approval_mode ?? ((matchedScope?.active_member_count ?? 0) >= 4 ? "auto" : "manual");

    return {
      domain_id: `derived-domain-${site.id}`,
      account_id: site.account_id,
      domain: site.domain,
      auto_join_role: matchedMock?.auto_join_role ?? "support_agent",
      sso_enforced: ssoEnforced,
      approval_mode: approvalMode,
      verified,
      effective_result: verified ? "active" : "review",
      effective_reason:
        matchedMock?.effective_reason ?? (verified ? "域名已纳入站点范围" : "域名待完成校验"),
      source: "hybrid",
    };
  });

  const existingKeys = new Set(
    derivedDomains.map((item) => `${item.account_id ?? "global"}:${item.domain.toLowerCase()}`)
  );
  const fallbackDomains = mockOrganizationInviteDomains
    .filter((item) => !existingKeys.has(`${item.account_id ?? "global"}:${item.domain.toLowerCase()}`))
    .map(cloneInviteDomain);

  return [...derivedDomains, ...fallbackDomains];
}

function getApproverNames(members: MemberDirectoryItem[], fallbackNames: string[]): string[] {
  const names = Array.from(
    new Set(
      [...members]
        .sort((left, right) => {
          if (left.is_active !== right.is_active) {
            return left.is_active ? -1 : 1;
          }
          if (left.assigned_open_conversations !== right.assigned_open_conversations) {
            return right.assigned_open_conversations - left.assigned_open_conversations;
          }
          return left.display_name.localeCompare(right.display_name, "zh-CN");
        })
        .map((item) => item.display_name.trim())
        .filter(Boolean)
    )
  ).slice(0, 2);

  return names.length ? names : fallbackNames;
}

function buildDerivedApprovalChains(
  accountScopes: OrganizationAccountScope[],
  members: MemberDirectoryItem[]
): OrganizationApprovalChain[] {
  const derivedChains: OrganizationApprovalChain[] = [];

  if (accountScopes.length || members.length) {
    derivedChains.push({
      chain_id: "approval-derived-invite",
      account_id: null,
      name: "成员邀请",
      trigger_type: "member_invite",
      approvers: getApproverNames(
        members,
        mockOrganizationApprovalChains.find((item) => item.trigger_type === "member_invite")
          ?.approvers ?? [mockOrganizationProfile.owner_name]
      ),
      sla_minutes: 240,
      enabled: true,
      source: "hybrid",
    });
    derivedChains.push({
      chain_id: "approval-derived-critical",
      account_id: null,
      name: "高风险操作",
      trigger_type: "critical_action",
      approvers: getApproverNames(
        members,
        mockOrganizationApprovalChains.find((item) => item.trigger_type === "critical_action")
          ?.approvers ?? [mockOrganizationProfile.owner_name]
      ),
      sla_minutes: 30,
      enabled: true,
      source: "hybrid",
    });
  }

  accountScopes.forEach((scope) => {
    const scopedMembers = members.filter((item) => item.account_id === scope.account_id);
    derivedChains.push({
      chain_id: `approval-derived-permission-${scope.account_id}`,
      account_id: scope.account_id,
      name: `${scope.display_name} 权限变更`,
      trigger_type: "permission_change",
      approvers: getApproverNames(
        scopedMembers,
        mockOrganizationApprovalChains.find((item) => item.account_id === scope.account_id)
          ?.approvers ?? [mockOrganizationProfile.owner_name]
      ),
      sla_minutes: scope.is_active ? 120 : 240,
      enabled: scope.is_active,
      source: "hybrid",
    });
  });

  const existingKeys = new Set(
    derivedChains.map((item) => `${item.account_id ?? "global"}:${item.trigger_type}`)
  );
  const fallbackChains = mockOrganizationApprovalChains
    .filter((item) => !existingKeys.has(`${item.account_id ?? "global"}:${item.trigger_type}`))
    .map(cloneApprovalChain);

  return [...derivedChains, ...fallbackChains];
}

export async function getOrganizationCenterSnapshot(
  accountId?: string
): Promise<OrganizationCenterSnapshot> {
  const [configResult, runtimeResult, sitesResult, membersResult, metaResult] =
    await Promise.allSettled([
      getRuntimeConfigSummary(),
      listRuntimeState(),
      listPlatformSites(),
      listMemberDirectory(accountId),
      listMetaAccounts(accountId ? { account_id: accountId } : undefined),
    ]);

  const warnings: string[] = [];
  if (configResult.status !== "fulfilled") warnings.push("运行配置加载失败");
  if (runtimeResult.status !== "fulfilled") warnings.push("运行时账号加载失败");
  if (sitesResult.status !== "fulfilled") warnings.push("站点范围加载失败");
  if (membersResult.status !== "fulfilled") warnings.push("成员目录加载失败");
  if (metaResult.status !== "fulfilled") warnings.push("Meta 账户加载失败");

  const config = configResult.status === "fulfilled" ? configResult.value : null;
  const runtimeAccounts =
    runtimeResult.status === "fulfilled"
      ? runtimeResult.value.accounts.filter((item) =>
          accountId ? item.account_id === accountId : true
        )
      : [];
  const sites =
    sitesResult.status === "fulfilled"
      ? sitesResult.value.filter((item) => (accountId ? item.account_id === accountId : true))
      : [];
  const members = membersResult.status === "fulfilled" ? membersResult.value : [];
  const metaAccounts = metaResult.status === "fulfilled" ? metaResult.value : [];

  const realScopes = buildRealScopes(runtimeAccounts, sites, members, metaAccounts, accountId);
  const fallbackScopes = mockOrganizationAccountScopes
    .filter((item) => (accountId ? item.account_id === accountId : true))
    .map(cloneScope);
  const accountScopes = realScopes.length ? realScopes : fallbackScopes;

  const profile = buildProfile(
    config,
    accountScopes,
    membersResult.status === "fulfilled" ? members.length : null
  );
  const units = filterAccountScoped(buildDerivedUnits(accountScopes, members), accountId);
  const inviteDomains = filterAccountScoped(
    buildDerivedInviteDomains(sites, accountScopes),
    accountId
  );
  const approvalChains = filterAccountScoped(
    buildDerivedApprovalChains(accountScopes, members),
    accountId
  );

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    profile,
    account_scopes: accountScopes,
    units,
    invite_domains: inviteDomains,
    approval_chains: approvalChains,
    warnings,
  };
}

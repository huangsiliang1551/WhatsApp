import {
  getRuntimeConfigSummary,
  listMetaWebhookSubscriptions,
  type MetaWebhookVerificationStatus,
  type MetaWebhookSubscriptionView,
  type RuntimeConfigSummary,
} from "./api";
import { getAccessControlSnapshot } from "./accessControl";
import { listMemberDirectory } from "./operations";
import {
  mockPasswordPolicy,
  mockSessionPolicies,
  mockSsoProviders,
} from "../mocks/securitySettings";
import type { AccessControlSnapshot } from "../types/accessControl";
import type { MemberDirectoryItem } from "../types/operations";
import type {
  SecurityAccountBindingStatus,
  SecurityPasswordPolicy,
  SecurityPolicyUpdatePayload,
  SecuritySessionPolicy,
  SecuritySettingsSnapshot,
  SecuritySsoProvider,
  SecurityWebhookRuntimeState,
} from "../types/securitySettings";

const sessionPolicyStore = mockSessionPolicies.map((item) => ({ ...item }));
const ssoProviderStore = mockSsoProviders.map((item) => ({ ...item }));
let runtimeSessionPolicyCache: SecuritySessionPolicy[] = [];
let runtimeSsoProviderCache: SecuritySsoProvider[] = [];

type WebhookAggregate = {
  subscriptionCount: number;
  signatureFailureCount: number;
  verificationStatus: MetaWebhookVerificationStatus;
  runtimeStatus: SecurityWebhookRuntimeState;
  latestEventAt: string | null;
  latestMessageAt: string | null;
  latestStatusUpdateAt: string | null;
  latestVerifiedAt: string | null;
  lastVerificationError: string | null;
  lastSignatureFailedAt: string | null;
  runtimeError: string | null;
  deliveryState: NonNullable<SecuritySsoProvider["webhook_delivery_state"]>;
  deliveryReason: string;
};

const WEBHOOK_STALE_DAYS = 30;

function clonePasswordPolicy(policy: SecurityPasswordPolicy): SecurityPasswordPolicy {
  return { ...policy };
}

function cloneSessionPolicy(policy: SecuritySessionPolicy): SecuritySessionPolicy {
  return { ...policy };
}

function cloneSsoProvider(provider: SecuritySsoProvider): SecuritySsoProvider {
  return { ...provider };
}

function filterByAccount<T extends { account_id: string | null }>(items: T[], accountId?: string): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

function getAccountKey(accountId: string | null): string {
  return accountId ?? "global";
}

function sortAccountIds(values: Iterable<string | null>): Array<string | null> {
  return Array.from(new Set(values)).sort((left, right) => {
    if (left === right) return 0;
    if (left === null) return -1;
    if (right === null) return 1;
    return left.localeCompare(right, "zh-CN");
  });
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

function isTimestampOlderThanDays(value: string | null, days: number): boolean {
  if (!value) {
    return false;
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return false;
  }
  return Date.now() - parsed > days * 24 * 60 * 60 * 1000;
}

function getRuntimeStatusPriority(status: SecurityWebhookRuntimeState): number {
  if (status === "signature_failed" || status === "payload_invalid") return 5;
  if (status === "verification_pending") return 4;
  if (status === "pending") return 3;
  if (status === "healthy") return 2;
  if (status === "none") return 1;
  return 0;
}

function getAggregateRuntimeStatus(
  subscriptions: MetaWebhookSubscriptionView[]
): SecurityWebhookRuntimeState {
  if (!subscriptions.length) {
    return "none";
  }

  return subscriptions
    .map((item) => item.webhook_runtime_status)
    .sort((left, right) => getRuntimeStatusPriority(right) - getRuntimeStatusPriority(left))[0];
}

function getVerificationStatusPriority(status: MetaWebhookVerificationStatus): number {
  if (status === "failed") return 4;
  if (status === "pending") return 3;
  if (status === "unavailable") return 2;
  if (status === "verified") return 1;
  return 0;
}

function getAggregateVerificationStatus(
  subscriptions: MetaWebhookSubscriptionView[]
): MetaWebhookVerificationStatus {
  if (!subscriptions.length) {
    return "unavailable";
  }

  return subscriptions
    .map((item) => item.webhook_verification_status)
    .sort((left, right) => getVerificationStatusPriority(right) - getVerificationStatusPriority(left))[0];
}

function getWebhookDeliveryState(
  aggregate: Pick<
    WebhookAggregate,
    | "subscriptionCount"
    | "verificationStatus"
    | "signatureFailureCount"
    | "runtimeStatus"
    | "latestEventAt"
    | "latestMessageAt"
    | "runtimeError"
  >
): Pick<WebhookAggregate, "deliveryState" | "deliveryReason"> {
  const latestRuntimeEventAt = getLatestTimestamp([aggregate.latestMessageAt, aggregate.latestEventAt]);
  if (aggregate.subscriptionCount === 0) {
    return { deliveryState: "unverified", deliveryReason: "缺少 Webhook 订阅" };
  }
  if (aggregate.verificationStatus !== "verified") {
    return {
      deliveryState: "unverified",
      deliveryReason:
        aggregate.verificationStatus === "failed"
          ? "Webhook 验证失败"
          : aggregate.verificationStatus === "pending"
            ? "Webhook 待验证"
            : "Webhook 验证不可用",
    };
  }
  if (aggregate.signatureFailureCount > 0) {
    return { deliveryState: "error", deliveryReason: "存在签名失败记录" };
  }
  if (aggregate.runtimeStatus === "signature_failed" || aggregate.runtimeStatus === "payload_invalid") {
    return { deliveryState: "error", deliveryReason: "Webhook 运行状态异常" };
  }
  if (aggregate.runtimeError) {
    return { deliveryState: "error", deliveryReason: aggregate.runtimeError };
  }
  if (!latestRuntimeEventAt) {
    return { deliveryState: "silent", deliveryReason: "已验证但暂无运行事件" };
  }
  if (isTimestampOlderThanDays(latestRuntimeEventAt, WEBHOOK_STALE_DAYS)) {
    return { deliveryState: "stale", deliveryReason: `最近运行事件超过 ${WEBHOOK_STALE_DAYS} 天` };
  }
  return { deliveryState: "ready", deliveryReason: "Webhook 验证与运行状态正常" };
}

function buildWebhookAggregate(
  subscriptions: MetaWebhookSubscriptionView[]
): Map<string, WebhookAggregate> {
  const grouped = new Map<string, MetaWebhookSubscriptionView[]>();

  for (const subscription of subscriptions) {
    const key = getAccountKey(subscription.account_id);
    const bucket = grouped.get(key) ?? [];
    bucket.push(subscription);
    grouped.set(key, bucket);
  }

  const aggregate = new Map<string, WebhookAggregate>();
  for (const [key, scopedSubscriptions] of grouped.entries()) {
    const latestEventAt = getLatestTimestamp(
      scopedSubscriptions.map((item) => item.webhook_last_event_received_at)
    );
    const latestMessageAt = getLatestTimestamp(
      scopedSubscriptions.map((item) => item.webhook_last_message_received_at)
    );
    const deliverySummary = getWebhookDeliveryState({
      subscriptionCount: scopedSubscriptions.length,
      verificationStatus: getAggregateVerificationStatus(scopedSubscriptions),
      signatureFailureCount: scopedSubscriptions.reduce(
        (total, item) => total + item.webhook_signature_failure_count,
        0
      ),
      runtimeStatus: getAggregateRuntimeStatus(scopedSubscriptions),
      latestEventAt,
      latestMessageAt,
      runtimeError:
        scopedSubscriptions.find((item) => item.webhook_runtime_error)?.webhook_runtime_error ?? null,
    });

    aggregate.set(key, {
      subscriptionCount: scopedSubscriptions.length,
      signatureFailureCount: scopedSubscriptions.reduce(
        (total, item) => total + item.webhook_signature_failure_count,
        0
      ),
      verificationStatus: getAggregateVerificationStatus(scopedSubscriptions),
      runtimeStatus: getAggregateRuntimeStatus(scopedSubscriptions),
      latestEventAt,
      latestMessageAt,
      latestStatusUpdateAt: getLatestTimestamp(
        scopedSubscriptions.map((item) => item.webhook_last_status_update_at)
      ),
      latestVerifiedAt: getLatestTimestamp(
        scopedSubscriptions.map((item) => item.webhook_last_verified_at)
      ),
      lastVerificationError:
        scopedSubscriptions.find((item) => item.webhook_last_verification_error)
          ?.webhook_last_verification_error ?? null,
      lastSignatureFailedAt: getLatestTimestamp(
        scopedSubscriptions.map((item) => item.webhook_last_signature_failed_at)
      ),
      runtimeError:
        scopedSubscriptions.find((item) => item.webhook_runtime_error)?.webhook_runtime_error ?? null,
      deliveryState: deliverySummary.deliveryState,
      deliveryReason: deliverySummary.deliveryReason,
    });
  }

  return aggregate;
}

function buildPasswordPolicy(config: RuntimeConfigSummary | null): SecurityPasswordPolicy {
  if (!config) {
    return clonePasswordPolicy(mockPasswordPolicy);
  }

  return {
    min_length: config.test_mode ? mockPasswordPolicy.min_length : Math.max(12, mockPasswordPolicy.min_length),
    require_uppercase: true,
    require_number: true,
    require_symbol: !config.test_mode || mockPasswordPolicy.require_symbol,
    password_expiry_days: config.test_mode ? mockPasswordPolicy.password_expiry_days : 60,
    source: "hybrid",
  };
}

function deriveMaxParallelSessions(
  storeValue: number | undefined,
  memberCount: number,
  activeSessionCount: number
): number {
  if (typeof storeValue === "number" && Number.isFinite(storeValue)) {
    return storeValue;
  }
  const derived = Math.max(activeSessionCount, memberCount > 0 ? Math.min(memberCount, 5) : 2);
  return Math.min(Math.max(derived, 1), 10);
}

function deriveAuditRetentionDays(
  storeValue: number | undefined,
  config: RuntimeConfigSummary | null
): number {
  if (typeof storeValue === "number" && Number.isFinite(storeValue)) {
    return storeValue;
  }
  return config?.test_mode ? 180 : 365;
}

function getPolicyReason(
  accessPolicy: AccessControlSnapshot["policies"][number] | null,
  memberCount: number,
  activeSessionCount: number,
  webhookAggregate: WebhookAggregate | null
): string {
  if (accessPolicy?.effective_reason) {
    return accessPolicy.effective_reason;
  }
  if (webhookAggregate && webhookAggregate.deliveryState !== "ready") {
    return webhookAggregate.deliveryReason;
  }
  if (memberCount === 0) {
    return "当前账号暂无后台成员";
  }
  if (activeSessionCount === 0) {
    return "当前账号暂无活跃后台会话";
  }
  return "已按运行时与访问控制派生";
}

function buildSessionPolicyMap(
  accountIds: Array<string | null>,
  accessSnapshot: AccessControlSnapshot | null,
  members: MemberDirectoryItem[],
  webhookAggregate: Map<string, WebhookAggregate>,
  config: RuntimeConfigSummary | null
): Map<string, SecuritySessionPolicy> {
  const memberCountByAccount = new Map<string, number>();
  for (const member of members) {
    const key = getAccountKey(member.account_id);
    memberCountByAccount.set(key, (memberCountByAccount.get(key) ?? 0) + 1);
  }

  const activeSessionCountByAccount = new Map<string, number>();
  for (const session of accessSnapshot?.sessions ?? []) {
    if (session.status === "revoked") {
      continue;
    }
    const key = getAccountKey(session.account_id);
    activeSessionCountByAccount.set(key, (activeSessionCountByAccount.get(key) ?? 0) + 1);
  }

  const enabledProviderCountByAccount = new Map<string, number>();
  for (const provider of ssoProviderStore) {
    if (!provider.enabled) {
      continue;
    }
    const key = getAccountKey(provider.account_id);
    enabledProviderCountByAccount.set(key, (enabledProviderCountByAccount.get(key) ?? 0) + 1);
  }

  const policyMap = new Map<string, SecuritySessionPolicy>();

  for (const accountId of accountIds) {
    const key = getAccountKey(accountId);
    const accessPolicy =
      accessSnapshot?.policies.find((item) => item.account_id === accountId) ??
      (accountId !== null
        ? accessSnapshot?.policies.find((item) => item.account_id === null) ?? null
        : null);
    const storeOverride =
      sessionPolicyStore.find((item) => item.account_id === accountId) ??
      (accountId !== null ? sessionPolicyStore.find((item) => item.account_id === null) ?? null : null);
    const memberCount = memberCountByAccount.get(key) ?? 0;
    const activeSessionCount = activeSessionCountByAccount.get(key) ?? 0;
    const webhookForAccount = webhookAggregate.get(key) ?? null;
    const effectiveResult = accessPolicy?.effective_status ?? "review";

    policyMap.set(key, {
      account_id: accountId,
      login_mode: storeOverride?.login_mode ?? accessPolicy?.login_mode ?? "mixed",
      mfa_required: storeOverride?.mfa_required ?? accessPolicy?.mfa_required ?? true,
      session_timeout_minutes:
        storeOverride?.session_timeout_minutes ?? accessPolicy?.session_timeout_minutes ?? 480,
      max_parallel_sessions: deriveMaxParallelSessions(
        storeOverride?.max_parallel_sessions,
        memberCount,
        activeSessionCount
      ),
      suspicious_login_review:
        storeOverride?.suspicious_login_review ??
        (effectiveResult !== "enforced"),
      audit_retention_days: deriveAuditRetentionDays(storeOverride?.audit_retention_days, config),
      audit_export_enabled: accessPolicy?.audit_export_enabled ?? true,
      webhook_signature_enforced:
        accessPolicy?.webhook_signature_enforced ??
        Boolean(config?.messaging_provider === "whatsapp" && webhookForAccount?.subscriptionCount),
      member_count: memberCount,
      active_session_count: activeSessionCount,
      enabled_sso_provider_count: enabledProviderCountByAccount.get(key) ?? 0,
      webhook_subscription_count: webhookForAccount?.subscriptionCount ?? 0,
      effective_result: effectiveResult,
      effective_reason: getPolicyReason(
        accessPolicy ?? null,
        memberCount,
        activeSessionCount,
        webhookForAccount
      ),
      source: storeOverride?.source ?? (accessSnapshot ? "hybrid" : "mock"),
    });
  }

  return policyMap;
}

function getBindingState(
  provider: SecuritySsoProvider,
  policy: SecuritySessionPolicy | null,
  webhookAggregate: WebhookAggregate | null
): { status: SecurityAccountBindingStatus; reason: string } {
  if (!provider.account_id) {
    return {
      status: "linked",
      reason: "全局身份源已绑定后台登录",
    };
  }

  if (!webhookAggregate || webhookAggregate.subscriptionCount === 0) {
    return {
      status: "missing",
      reason: "当前账号缺少 Webhook 订阅",
    };
  }

  if (webhookAggregate.deliveryState === "unverified") {
    return {
      status: "missing",
      reason: webhookAggregate.deliveryReason,
    };
  }

  if (
    webhookAggregate.deliveryState === "error" ||
    webhookAggregate.deliveryState === "silent" ||
    webhookAggregate.deliveryState === "stale"
  ) {
    return {
      status: "limited",
      reason: webhookAggregate.deliveryReason,
    };
  }

  if (policy?.webhook_signature_enforced === false) {
    return {
      status: "limited",
      reason: "签名校验尚未强制启用",
    };
  }

  return {
    status: "linked",
    reason: "账号订阅与签名策略可用",
  };
}

function getProviderEffectiveResult(
  provider: SecuritySsoProvider,
  policy: SecuritySessionPolicy | null,
  bindingStatus: SecurityAccountBindingStatus
): SecuritySsoProvider["effective_result"] {
  if (!provider.enabled) {
    return "review";
  }
  if (bindingStatus === "linked" && policy?.login_mode !== "mixed" && policy?.mfa_required) {
    return "enforced";
  }
  if (bindingStatus === "missing") {
    return "review";
  }
  return "partial";
}

function getProviderEffectiveReason(
  provider: SecuritySsoProvider,
  policy: SecuritySessionPolicy | null,
  bindingReason: string
): string {
  if (!provider.enabled) {
    return provider.effective_reason || "SSO 已暂停";
  }
  if (policy?.login_mode === "sso" || policy?.login_mode === "sso_first") {
    return bindingReason;
  }
  return provider.effective_reason || bindingReason;
}

function buildDerivedProvider(
  accountId: string | null,
  policy: SecuritySessionPolicy | null
): SecuritySsoProvider {
  return {
    provider_id: `derived-sso:${accountId ?? "global"}`,
    account_id: accountId,
    provider_name: accountId ? "custom_oidc" : "google",
    enabled: policy?.login_mode === "sso" || policy?.login_mode === "sso_first",
    mapped_role_count: 0,
    last_sync_at: null,
    effective_result: "review",
    effective_reason: "SSO 提供方待接入",
    source: "hybrid",
  };
}

function buildProviders(
  accountIds: Array<string | null>,
  scopedProviders: SecuritySsoProvider[],
  policyMap: Map<string, SecuritySessionPolicy>,
  webhookAggregate: Map<string, WebhookAggregate>
): SecuritySsoProvider[] {
  return accountIds.map((accountId) => {
    const provider =
      scopedProviders.find((item) => item.account_id === accountId) ??
      buildDerivedProvider(accountId, policyMap.get(getAccountKey(accountId)) ?? null);
    const key = getAccountKey(provider.account_id);
    const policy = policyMap.get(key) ?? policyMap.get("global") ?? null;
    const webhookForAccount = webhookAggregate.get(key) ?? null;
    const binding = getBindingState(provider, policy, webhookForAccount);

    return {
      ...cloneSsoProvider(provider),
      login_mode: policy?.login_mode ?? "mixed",
      mfa_required: policy?.mfa_required ?? true,
      member_count: policy?.member_count ?? 0,
      active_session_count: policy?.active_session_count ?? 0,
      account_binding_status: binding.status,
      account_binding_reason: binding.reason,
      webhook_subscription_count: webhookForAccount?.subscriptionCount ?? 0,
      webhook_signature_failure_count: webhookForAccount?.signatureFailureCount ?? 0,
      webhook_verification_status: webhookForAccount?.verificationStatus ?? "unavailable",
      webhook_last_verified_at: webhookForAccount?.latestVerifiedAt ?? null,
      webhook_last_verification_error: webhookForAccount?.lastVerificationError ?? null,
      webhook_runtime_status: webhookForAccount?.runtimeStatus ?? "none",
      webhook_last_event_received_at: webhookForAccount?.latestEventAt ?? null,
      webhook_last_message_received_at: webhookForAccount?.latestMessageAt ?? null,
      webhook_last_signature_failed_at: webhookForAccount?.lastSignatureFailedAt ?? null,
      webhook_runtime_error: webhookForAccount?.runtimeError ?? null,
      webhook_delivery_state: webhookForAccount?.deliveryState ?? "unverified",
      webhook_delivery_reason: webhookForAccount?.deliveryReason ?? "Webhook 未接入",
      last_sync_at: getLatestTimestamp([
        provider.last_sync_at,
        webhookForAccount?.latestEventAt,
        webhookForAccount?.latestStatusUpdateAt,
      ]),
      effective_result: getProviderEffectiveResult(provider, policy, binding.status),
      effective_reason: getProviderEffectiveReason(provider, policy, binding.reason),
      source: provider.source === "mock" ? "mock" : policy || webhookForAccount || provider.account_id === null ? "hybrid" : provider.source,
    };
  });
}

function buildSummary(
  policies: SecuritySessionPolicy[],
  providers: SecuritySsoProvider[]
): SecuritySettingsSnapshot["summary"] {
  return {
    member_count: policies.reduce((total, item) => total + (item.member_count ?? 0), 0),
    active_session_count: policies.reduce((total, item) => total + (item.active_session_count ?? 0), 0),
    linked_provider_count: providers.filter(
      (item) => item.enabled && item.account_binding_status === "linked"
    ).length,
    review_policy_count: policies.filter((item) => item.effective_result !== "enforced").length,
    webhook_protected_policy_count: policies.filter((item) => item.webhook_signature_enforced).length,
    webhook_signature_failure_count: providers.reduce(
      (total, item) => total + (item.webhook_signature_failure_count ?? 0),
      0
    ),
  };
}

function getScopedAccountIds(
  accountId: string | undefined,
  accessSnapshot: AccessControlSnapshot | null,
  members: MemberDirectoryItem[],
  subscriptions: MetaWebhookSubscriptionView[]
): Array<string | null> {
  if (accountId) {
    return sortAccountIds([null, accountId]);
  }

  return sortAccountIds([
    null,
    ...sessionPolicyStore.map((item) => item.account_id),
    ...ssoProviderStore.map((item) => item.account_id),
    ...(accessSnapshot?.policies.map((item) => item.account_id) ?? []),
    ...members.map((item) => item.account_id),
    ...subscriptions.map((item) => item.account_id),
  ]);
}

export async function getSecuritySettingsSnapshot(
  accountId?: string
): Promise<SecuritySettingsSnapshot> {
  const [configResult, accessResult, membersResult, webhookResult] = await Promise.allSettled([
    getRuntimeConfigSummary(),
    getAccessControlSnapshot(accountId),
    listMemberDirectory(accountId),
    listMetaWebhookSubscriptions(accountId ? { account_id: accountId } : undefined),
  ]);

  const config = configResult.status === "fulfilled" ? configResult.value : null;
  const accessSnapshot = accessResult.status === "fulfilled" ? accessResult.value : null;
  const members = membersResult.status === "fulfilled" ? membersResult.value : [];
  const subscriptions = webhookResult.status === "fulfilled" ? webhookResult.value : [];
  const warnings: string[] = [];

  if (!config) {
    warnings.push("运行时配置加载失败");
  }
  if (!accessSnapshot) {
    warnings.push("访问控制快照加载失败");
  }
  if (membersResult.status !== "fulfilled") {
    warnings.push("成员目录加载失败");
  }
  if (webhookResult.status !== "fulfilled") {
    warnings.push("Webhook 订阅加载失败");
  }

  const scopedProviders = filterByAccount(ssoProviderStore, accountId).map(cloneSsoProvider);
  const accountIds = getScopedAccountIds(accountId, accessSnapshot, members, subscriptions);
  const webhookAggregate = buildWebhookAggregate(subscriptions);
  const policyMap = buildSessionPolicyMap(accountIds, accessSnapshot, members, webhookAggregate, config);
  const sessionPolicies = accountIds
    .map((value) => policyMap.get(getAccountKey(value)))
    .filter((item): item is SecuritySessionPolicy => Boolean(item));
  runtimeSessionPolicyCache = sessionPolicies.map(cloneSessionPolicy);
  const ssoProviders = buildProviders(accountIds, scopedProviders, policyMap, webhookAggregate).sort((left, right) => {
    if (left.account_id === right.account_id) {
      return left.provider_name.localeCompare(right.provider_name, "zh-CN");
    }
    if (left.account_id === null) return -1;
    if (right.account_id === null) return 1;
    return left.account_id.localeCompare(right.account_id, "zh-CN");
  });
  runtimeSsoProviderCache = ssoProviders.map(cloneSsoProvider);

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    config: config
      ? {
          app_env: config.app_env,
          test_mode: config.test_mode,
          console_language: config.console_language,
        }
      : null,
    password_policy: buildPasswordPolicy(config),
    session_policies: sessionPolicies,
    sso_providers: ssoProviders,
    summary: buildSummary(sessionPolicies, ssoProviders),
    warnings,
  };
}

export async function updateSecuritySessionPolicy(
  payload: SecurityPolicyUpdatePayload
): Promise<SecuritySessionPolicy> {
  const targetAccountId = payload.account_id?.trim() || null;
  const target =
    sessionPolicyStore.find((item) => item.account_id === targetAccountId) ??
    runtimeSessionPolicyCache.find((item) => item.account_id === targetAccountId) ??
    (() => {
      const created: SecuritySessionPolicy = {
        account_id: targetAccountId,
        login_mode: payload.login_mode,
        mfa_required: payload.mfa_required,
        session_timeout_minutes: payload.session_timeout_minutes,
        max_parallel_sessions: payload.max_parallel_sessions,
        suspicious_login_review: payload.suspicious_login_review,
        audit_retention_days: payload.audit_retention_days,
        source: "mock",
      };
      sessionPolicyStore.unshift(created);
      return created;
    })();

  target.login_mode = payload.login_mode;
  target.mfa_required = payload.mfa_required;
  target.session_timeout_minutes = payload.session_timeout_minutes;
  target.max_parallel_sessions = payload.max_parallel_sessions;
  target.suspicious_login_review = payload.suspicious_login_review;
  target.audit_retention_days = payload.audit_retention_days;
  target.source = "mock";

  const targetIndex = sessionPolicyStore.findIndex((item) => item.account_id === targetAccountId);
  if (targetIndex >= 0) {
    sessionPolicyStore[targetIndex] = { ...target };
  } else {
    sessionPolicyStore.unshift({ ...target });
  }
  return cloneSessionPolicy(target);
}

export async function toggleSsoProvider(providerId: string): Promise<SecuritySsoProvider> {
  let target = ssoProviderStore.find((item) => item.provider_id === providerId);
  if (!target) {
    const runtimeTarget = runtimeSsoProviderCache.find((item) => item.provider_id === providerId);
    if (runtimeTarget) {
      target = { ...cloneSsoProvider(runtimeTarget), source: "mock" };
      ssoProviderStore.unshift(target);
    }
  }
  if (!target) {
    throw new Error("SSO 提供方不存在");
  }

  target.enabled = !target.enabled;
  target.effective_reason = target.enabled ? "已启用 SSO" : "已暂停 SSO";
  target.last_sync_at = target.enabled ? new Date().toISOString() : target.last_sync_at;
  target.source = "mock";
  return cloneSsoProvider(target);
}

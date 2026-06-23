import {
  getRuntimeConfigSummary,
  listRuntimeAgents,
  listRuntimeState,
  type RuntimeAccountState,
  type RuntimeAgent,
  type RuntimeConfigSummary,
} from "./api";
import {
  mockAccessControlSnapshot,
  mockAccessEvents,
  mockAccessPolicies,
  mockAdminSessions,
} from "../mocks/accessControl";
import type {
  AccessControlSnapshot,
  AccessPolicyCreatePayload,
  AccessPolicyItem,
  AccessSecurityEvent,
  AdminSessionItem,
} from "../types/accessControl";

const policyStore = mockAccessPolicies.map(clonePolicy);
const sessionStore = mockAdminSessions.map(cloneSession);
const eventStore = mockAccessEvents.map(cloneEvent);
let runtimeSessionCache: AdminSessionItem[] = [];
let runtimePolicyCache: AccessPolicyItem[] = [];

function clonePolicy(policy: AccessPolicyItem): AccessPolicyItem {
  return { ...policy };
}

function cloneSession(session: AdminSessionItem): AdminSessionItem {
  return { ...session };
}

function cloneEvent(event: AccessSecurityEvent): AccessSecurityEvent {
  return { ...event };
}

function cloneGlobalSettings(
  settings: AccessControlSnapshot["global_settings"]
): AccessControlSnapshot["global_settings"] {
  return { ...settings };
}

function filterByAccount<T extends { account_id: string | null }>(items: T[], accountId?: string): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

function buildGlobalSettings(
  config: RuntimeConfigSummary | null
): AccessControlSnapshot["global_settings"] {
  if (!config) {
    return cloneGlobalSettings(mockAccessControlSnapshot.global_settings);
  }
  return {
    login_mode: config.test_mode ? "mixed" : "sso_first",
    mfa_required: !config.test_mode,
    session_timeout_minutes: config.test_mode ? 360 : 480,
    ip_allowlist_enabled: !config.test_mode,
    webhook_signature_enforced: config.messaging_provider === "whatsapp",
  };
}

function getPolicyStatus(
  policy: Pick<
    AccessPolicyItem,
    "login_mode" | "mfa_required" | "ip_allowlist_enabled" | "webhook_signature_enforced"
  >
): AccessPolicyItem["effective_status"] {
  if (
    policy.mfa_required &&
    policy.ip_allowlist_enabled &&
    policy.webhook_signature_enforced &&
    policy.login_mode !== "mixed"
  ) {
    return "enforced";
  }
  if (policy.mfa_required || policy.login_mode !== "mixed") {
    return "partial";
  }
  return "review";
}

function buildPolicyReason(
  accountId: string | null,
  status: AccessPolicyItem["effective_status"],
  isActive: boolean
): string {
  if (!isActive && accountId) {
    return "账号未启用，访问策略待激活";
  }
  if (status === "enforced") {
    return accountId ? "账号访问基线已生效" : "全局访问基线已生效";
  }
  if (status === "partial") {
    return accountId ? "账号访问基线部分生效" : "全局访问基线部分生效";
  }
  return accountId ? "账号访问策略待补齐" : "全局访问策略待补齐";
}

function buildRuntimePolicy(
  account: RuntimeAccountState | null,
  config: RuntimeConfigSummary | null,
  globalSettings: AccessControlSnapshot["global_settings"]
): AccessPolicyItem {
  const accountId = account?.account_id ?? null;
  const policy: AccessPolicyItem = {
    policy_id: accountId ? `runtime-policy:${accountId}` : "runtime-policy:global",
    account_id: accountId,
    scope: accountId ? "account" : "global",
    login_mode: account?.is_active === false ? "mixed" : globalSettings.login_mode,
    mfa_required: globalSettings.mfa_required,
    session_timeout_minutes: globalSettings.session_timeout_minutes,
    ip_allowlist_enabled: globalSettings.ip_allowlist_enabled,
    audit_export_enabled: true,
    webhook_signature_enforced:
      account?.provider_type === "whatsapp"
        ? globalSettings.webhook_signature_enforced
        : Boolean(config?.messaging_provider === "whatsapp"),
    effective_status: "review",
    effective_reason: "",
    updated_at: new Date().toISOString(),
    source: "hybrid",
  };
  policy.effective_status = getPolicyStatus(policy);
  policy.effective_reason = buildPolicyReason(accountId, policy.effective_status, account?.is_active ?? true);
  return policy;
}

function mergePolicies(
  derivedPolicies: AccessPolicyItem[],
  accountId?: string
): AccessPolicyItem[] {
  const merged = new Map<string, AccessPolicyItem>();
  derivedPolicies.forEach((policy) => {
    merged.set(policy.policy_id, policy);
  });

  policyStore.forEach((override) => {
    const key = override.account_id ? `runtime-policy:${override.account_id}` : "runtime-policy:global";
    const base = merged.get(key);
    if (base) {
      merged.set(key, {
        ...base,
        ...clonePolicy(override),
        policy_id: key,
        source: "hybrid",
      });
      return;
    }
    merged.set(override.policy_id, clonePolicy(override));
  });

  return filterByAccount(Array.from(merged.values()), accountId).sort((left, right) =>
    (left.account_id ?? "").localeCompare(right.account_id ?? "", "zh-CN")
  );
}

function hashText(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function buildRoleName(agent: RuntimeAgent): string {
  const seed = `${agent.agent_id}:${agent.display_name}:${agent.email ?? ""}`.toLowerCase();
  if (seed.includes("review")) return "审核员";
  if (seed.includes("admin") || seed.includes("manager")) return "账号管理员";
  if (seed.includes("sec")) return "平台安全";
  return "客服坐席";
}

function buildSessionStatus(agent: RuntimeAgent): AdminSessionItem["status"] {
  if (agent.status === "online" || agent.status === "busy") {
    return "active";
  }
  if (agent.status === "away") {
    return "idle";
  }
  return "revoked";
}

function buildRuntimeSession(agent: RuntimeAgent, policy: AccessPolicyItem | null): AdminSessionItem {
  const seed = `${agent.account_id ?? "global"}:${agent.agent_id}`;
  const hash = hashText(seed);
  const status = buildSessionStatus(agent);
  const login_mode: AdminSessionItem["login_mode"] =
    policy?.login_mode === "sso" || policy?.login_mode === "sso_first" ? "sso" : "password";
  return {
    session_id: `runtime-session:${seed}`,
    account_id: agent.account_id,
    agent_id: agent.agent_id,
    display_name: agent.display_name,
    role_name: buildRoleName(agent),
    login_mode,
    mfa_verified: status !== "revoked" && (policy?.mfa_required ?? true),
    ip_address: `10.${(hash % 200) + 10}.${((hash >> 3) % 200) + 10}.${((hash >> 6) % 200) + 10}`,
    device_label: hash % 2 === 0 ? "Chrome / Windows" : "Chrome / macOS",
    last_seen_at: new Date().toISOString(),
    status,
    source: "hybrid",
  };
}

function mergeSessions(
  runtimeSessions: AdminSessionItem[],
  accountId?: string
): AdminSessionItem[] {
  const merged = new Map<string, AdminSessionItem>();
  runtimeSessions.forEach((session) => {
    merged.set(session.session_id, session);
  });

  sessionStore.forEach((override) => {
    const runtimeKey = `runtime-session:${override.account_id ?? "global"}:${override.agent_id}`;
    const base = merged.get(runtimeKey);
    if (base) {
      merged.set(runtimeKey, {
        ...base,
        ...cloneSession(override),
        session_id: runtimeKey,
        source: "hybrid",
      });
      return;
    }
    merged.set(override.session_id, cloneSession(override));
  });

  return filterByAccount(Array.from(merged.values()), accountId).sort(
    (left, right) => Date.parse(right.last_seen_at) - Date.parse(left.last_seen_at)
  );
}

function buildDerivedEvents(
  policies: AccessPolicyItem[],
  sessions: AdminSessionItem[]
): AccessSecurityEvent[] {
  const items: AccessSecurityEvent[] = [];
  policies.forEach((policy) => {
    if (policy.effective_status === "review" || policy.effective_status === "partial") {
      items.push({
        event_id: `access-derived-policy:${policy.account_id ?? "global"}`,
        account_id: policy.account_id,
        title: policy.effective_status === "review" ? "访问策略待补齐" : "访问策略部分生效",
        summary: policy.effective_reason,
        level: policy.effective_status === "review" ? "critical" : "warning",
        occurred_at: policy.updated_at,
        source: "hybrid",
      });
    }
  });

  sessions
    .filter((session) => session.status === "revoked")
    .forEach((session) => {
      items.push({
        event_id: `access-derived-session:${session.session_id}`,
        account_id: session.account_id,
        title: "后台会话已失效",
        summary: `${session.display_name} / ${session.role_name}`,
        level: "warning",
        occurred_at: session.last_seen_at,
        source: "hybrid",
      });
    });

  return items;
}

function mergeEvents(
  derivedEvents: AccessSecurityEvent[],
  accountId?: string
): AccessSecurityEvent[] {
  return [...filterByAccount(derivedEvents, accountId), ...filterByAccount(eventStore, accountId)]
    .map(cloneEvent)
    .sort((left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at));
}

export async function getAccessControlSnapshot(accountId?: string): Promise<AccessControlSnapshot> {
  const [configResult, stateResult, agentsResult] = await Promise.allSettled([
    getRuntimeConfigSummary(),
    listRuntimeState(),
    listRuntimeAgents(undefined, accountId),
  ]);

  const config = configResult.status === "fulfilled" ? configResult.value : null;
  const runtimeAccounts =
    stateResult.status === "fulfilled"
      ? stateResult.value.accounts.filter((item) => (accountId ? item.account_id === accountId : true))
      : [];
  const globalSettings = buildGlobalSettings(config);
  const runtimePolicies = [
    buildRuntimePolicy(null, config, globalSettings),
    ...runtimeAccounts.map((account) => buildRuntimePolicy(account, config, globalSettings)),
  ];
  const policies = mergePolicies(runtimePolicies, accountId);
  runtimePolicyCache = policies.map(clonePolicy);

  const runtimeAgents = agentsResult.status === "fulfilled" ? agentsResult.value : [];
  const policyByAccount = new Map<string, AccessPolicyItem>(
    policies
      .filter((item) => item.account_id)
      .map((item) => [item.account_id as string, item])
  );
  const globalPolicy = policies.find((item) => item.account_id === null) ?? null;
  const runtimeSessions = runtimeAgents.map((agent) =>
    buildRuntimeSession(agent, (agent.account_id ? policyByAccount.get(agent.account_id) : null) ?? globalPolicy)
  );
  const sessions = mergeSessions(runtimeSessions, accountId);
  runtimeSessionCache = sessions.map(cloneSession);
  const events = mergeEvents(buildDerivedEvents(policies, sessions), accountId);

  return {
    generated_at: new Date().toISOString(),
    source: config ? "hybrid" : "mock",
    global_settings: globalSettings,
    policies,
    sessions,
    events,
  };
}

export async function createAccessPolicy(
  payload: AccessPolicyCreatePayload
): Promise<AccessPolicyItem> {
  const targetPolicyId = payload.account_id?.trim()
    ? `runtime-policy:${payload.account_id.trim()}`
    : "runtime-policy:global";
  const normalizedAccountId = payload.account_id?.trim() || null;
  const created: AccessPolicyItem = {
    policy_id: targetPolicyId,
    account_id: normalizedAccountId,
    scope: normalizedAccountId ? "account" : "global",
    login_mode: payload.login_mode,
    mfa_required: payload.mfa_required,
    session_timeout_minutes: payload.session_timeout_minutes,
    ip_allowlist_enabled: payload.ip_allowlist_enabled,
    audit_export_enabled: payload.audit_export_enabled,
    webhook_signature_enforced: payload.webhook_signature_enforced,
    effective_status: "review",
    effective_reason: payload.effective_reason.trim() || "新策略待审核",
    updated_at: new Date().toISOString(),
    source: "mock",
  };
  created.effective_status = getPolicyStatus(created);
  created.effective_reason =
    payload.effective_reason.trim() ||
    buildPolicyReason(normalizedAccountId, created.effective_status, true);
  policyStore.unshift(created);
  eventStore.unshift({
    event_id: `access-event-${Date.now()}`,
    account_id: created.account_id,
    title: "新增访问策略",
    summary: created.effective_reason,
    level: created.effective_status === "review" ? "warning" : "info",
    occurred_at: created.updated_at,
    source: "mock",
  });
  return clonePolicy(created);
}

export async function applyAccessBaseline(policyId: string): Promise<AccessPolicyItem> {
  let target = policyStore.find((item) => item.policy_id === policyId);
  if (!target) {
    const runtimeTarget = runtimePolicyCache.find((item) => item.policy_id === policyId);
    if (!runtimeTarget) {
      throw new Error("访问策略不存在");
    }
    target = clonePolicy(runtimeTarget);
    policyStore.unshift(target);
  }

  target.mfa_required = true;
  target.ip_allowlist_enabled = true;
  target.audit_export_enabled = true;
  target.webhook_signature_enforced = true;
  target.effective_status = "enforced";
  target.effective_reason = "已套用访问基线";
  target.updated_at = new Date().toISOString();

  eventStore.unshift({
    event_id: `access-event-${Date.now()}`,
    account_id: target.account_id,
    title: "访问基线已应用",
    summary: target.account_id ?? "全局策略",
    level: "info",
    occurred_at: target.updated_at,
    source: "mock",
  });

  return clonePolicy(target);
}

export async function revokeAdminSession(sessionId: string): Promise<AdminSessionItem> {
  let target = sessionStore.find((item) => item.session_id === sessionId);
  if (!target) {
    const runtimeTarget = runtimeSessionCache.find((item) => item.session_id === sessionId);
    if (!runtimeTarget) {
      throw new Error("后台会话不存在");
    }
    target = {
      ...cloneSession(runtimeTarget),
      source: "mock",
    };
    sessionStore.unshift(target);
  }

  target.status = "revoked";
  target.last_seen_at = new Date().toISOString();

  eventStore.unshift({
    event_id: `access-event-${Date.now()}`,
    account_id: target.account_id,
    title: "后台会话已下线",
    summary: `${target.display_name} / ${target.role_name}`,
    level: "warning",
    occurred_at: target.last_seen_at,
    source: "mock",
  });

  return cloneSession(target);
}

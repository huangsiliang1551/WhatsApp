import { getAccessControlSnapshot } from "./accessControl";
import { listMemberDirectory, listRoleDefinitions } from "./operations";
import {
  mockMemberAccessActivities,
  mockMemberAccessBindings,
  type MemberAccessBindingRecord,
} from "../mocks/memberAccess";
import type { AccessPolicyItem, AccessPolicyStatus, AdminSessionItem } from "../types/accessControl";
import type {
  MemberAccessActivityItem,
  MemberAccessBindingPatch,
  MemberAccessBindingView,
  MemberAccessResult,
  MemberAccessSnapshot,
} from "../types/memberAccess";
import type { MemberDirectoryItem, RoleDefinition } from "../types/operations";

const bindingStore = mockMemberAccessBindings.map(cloneBindingRecord);
const activityStore = mockMemberAccessActivities.map(cloneActivity);

function cloneBindingRecord(record: MemberAccessBindingRecord): MemberAccessBindingRecord {
  return {
    ...record,
    account_scope: [...record.account_scope],
    page_scope: [...record.page_scope],
  };
}

function cloneActivity(item: MemberAccessActivityItem): MemberAccessActivityItem {
  return { ...item };
}

function normalizeLabel(value: string): string {
  return value.toLowerCase().replace(/\s+/g, "");
}

function findRoleByDerivedLabels(
  member: MemberDirectoryItem,
  roles: RoleDefinition[]
): RoleDefinition | null {
  const normalizedLabels = member.role_labels.map(normalizeLabel);
  return (
    roles.find((role) => {
      const normalizedName = normalizeLabel(role.name);
      const normalizedKey = normalizeLabel(role.role_key);
      return normalizedLabels.some(
        (label) =>
          label === normalizedName ||
          label === normalizedKey ||
          normalizedName.includes(label) ||
          label.includes(normalizedName)
      );
    }) ?? null
  );
}

function findSession(
  member: MemberDirectoryItem,
  sessions: AdminSessionItem[]
): AdminSessionItem | null {
  const exactMatch =
    sessions.find(
      (session) => session.agent_id === member.agent_id && session.account_id === member.account_id
    ) ?? null;
  if (exactMatch) {
    return exactMatch;
  }
  return sessions.find((session) => session.agent_id === member.agent_id && session.account_id === null) ?? null;
}

function findPolicy(
  member: MemberDirectoryItem,
  policies: AccessPolicyItem[]
): AccessPolicyItem | null {
  const accountPolicy =
    policies.find((policy) => policy.account_id && policy.account_id === member.account_id) ?? null;
  if (accountPolicy) {
    return accountPolicy;
  }
  return policies.find((policy) => policy.account_id === null) ?? null;
}

function countRolePermissions(role: RoleDefinition | null): number {
  if (!role) {
    return 0;
  }
  return role.permissions.reduce((sum, resource) => {
    const enabledCount = Object.values(resource.actions).filter(Boolean).length;
    return sum + enabledCount;
  }, 0);
}

function deriveAccessResult(
  member: MemberDirectoryItem,
  role: RoleDefinition | null,
  policy: AccessPolicyItem | null,
  overrideRecord: MemberAccessBindingRecord | undefined
): {
  result: MemberAccessResult;
  reason: string;
  policyStatus: AccessPolicyStatus | "none";
  policyReason: string;
} {
  if (!member.is_active) {
    return {
      result: "restricted",
      reason: "成员已停用",
      policyStatus: policy?.effective_status ?? "none",
      policyReason: policy?.effective_reason ?? "未命中访问策略",
    };
  }

  if (!role && overrideRecord?.role_key === null) {
    return {
      result: "restricted",
      reason: "当前成员未绑定角色",
      policyStatus: policy?.effective_status ?? "none",
      policyReason: policy?.effective_reason ?? "未命中访问策略",
    };
  }

  if (!role) {
    return {
      result: "review",
      reason: "成员角色仍是派生标签，待显式绑定",
      policyStatus: policy?.effective_status ?? "none",
      policyReason: policy?.effective_reason ?? "未命中访问策略",
    };
  }

  if (policy?.effective_status === "review") {
    return {
      result: "review",
      reason: "账号访问策略仍在复核",
      policyStatus: policy.effective_status,
      policyReason: policy.effective_reason,
    };
  }

  if (policy?.effective_status === "partial") {
    return {
      result: "review",
      reason: "账号访问策略仅部分生效",
      policyStatus: policy.effective_status,
      policyReason: policy.effective_reason,
    };
  }

  return {
    result: "active",
    reason: overrideRecord?.access_reason ?? "角色与账号策略已生效",
    policyStatus: policy?.effective_status ?? "none",
    policyReason: policy?.effective_reason ?? "未命中访问策略",
  };
}

function buildBindingView(
  member: MemberDirectoryItem,
  roles: RoleDefinition[],
  sessions: AdminSessionItem[],
  policies: AccessPolicyItem[]
): MemberAccessBindingView {
  const overrideRecord =
    bindingStore.find(
      (item) => item.agent_id === member.agent_id && item.account_id === member.account_id
    ) ??
    bindingStore.find((item) => item.agent_id === member.agent_id && item.account_id === null);
  const derivedRole = findRoleByDerivedLabels(member, roles);
  const role =
    (overrideRecord?.role_key
      ? roles.find((item) => item.role_key === overrideRecord.role_key) ?? null
      : overrideRecord?.role_key === null
        ? null
        : derivedRole) ?? null;
  const session = findSession(member, sessions);
  const policy = findPolicy(member, policies);
  const accessResult = deriveAccessResult(member, role, policy, overrideRecord);

  return {
    binding_id:
      overrideRecord?.binding_id ?? `derived:${member.agent_id}:${member.account_id ?? "global"}`,
    agent_id: member.agent_id,
    display_name: member.display_name,
    email: member.email,
    member_account_id: member.account_id,
    role_labels: [...member.role_labels],
    role_key: role?.role_key ?? null,
    role_name: role?.name ?? null,
    scope: overrideRecord?.scope ?? role?.scope ?? "account",
    account_scope: overrideRecord?.account_scope.length
      ? [...overrideRecord.account_scope]
      : role?.account_scope
        ? [...role.account_scope]
        : member.account_id
          ? [member.account_id]
          : ["ALL"],
    page_scope: overrideRecord?.page_scope.length
      ? [...overrideRecord.page_scope]
      : role?.page_scope
        ? [...role.page_scope]
        : [],
    permission_count: countRolePermissions(role),
    assigned_open_conversations: member.assigned_open_conversations,
    assigned_total_conversations: member.assigned_total_conversations,
    session_status: session?.status ?? "offline",
    session_login_mode: session?.login_mode ?? "none",
    session_mfa_verified: session?.mfa_verified ?? false,
    access_policy_status: accessResult.policyStatus,
    access_policy_reason: accessResult.policyReason,
    access_result: accessResult.result,
    access_result_reason: accessResult.reason,
    is_override: Boolean(overrideRecord),
    updated_at: overrideRecord?.updated_at ?? new Date(0).toISOString(),
    source: "hybrid",
  };
}

function filterByAccount<T extends { account_id: string | null }>(
  items: T[],
  accountId?: string
): T[] {
  if (!accountId) {
    return items;
  }
  return items.filter((item) => item.account_id === null || item.account_id === accountId);
}

export async function getMemberAccessSnapshot(accountId?: string): Promise<MemberAccessSnapshot> {
  const [membersResult, rolesResult, accessResult] = await Promise.allSettled([
    listMemberDirectory(accountId),
    listRoleDefinitions(accountId),
    getAccessControlSnapshot(accountId),
  ]);

  if (membersResult.status !== "fulfilled") {
    throw new Error(
      membersResult.reason instanceof Error ? membersResult.reason.message : "成员授权加载失败"
    );
  }

  const warnings: string[] = [];
  if (rolesResult.status !== "fulfilled") warnings.push("角色目录加载失败");
  if (accessResult.status !== "fulfilled") warnings.push("访问策略加载失败");

  const roles = rolesResult.status === "fulfilled" ? rolesResult.value : [];
  const sessions = accessResult.status === "fulfilled" ? accessResult.value.sessions : [];
  const policies = accessResult.status === "fulfilled" ? accessResult.value.policies : [];

  const bindings = membersResult.value
    .map((member) => buildBindingView(member, roles, sessions, policies))
    .sort((left, right) => left.display_name.localeCompare(right.display_name, "zh-CN"));

  const accountIds = Array.from(
    new Set(
      bindings
        .map((binding) => binding.member_account_id)
        .filter((value): value is string => Boolean(value))
    )
  ).sort((left, right) => left.localeCompare(right, "zh-CN"));

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    account_ids: accountIds,
    roles,
    bindings,
    activities: filterByAccount(activityStore, accountId).map(cloneActivity),
    warnings,
  };
}

export async function saveMemberAccessBinding(
  payload: MemberAccessBindingPatch
): Promise<MemberAccessBindingRecord> {
  const now = new Date().toISOString();
  const normalizedAccountId = payload.account_id?.trim() || null;
  const nextRecord: MemberAccessBindingRecord = {
    binding_id: `binding-${payload.agent_id}-${normalizedAccountId ?? "global"}`,
    agent_id: payload.agent_id,
    account_id: normalizedAccountId,
    role_key: payload.role_key,
    scope: payload.scope,
    account_scope: [...payload.account_scope],
    page_scope: [...payload.page_scope],
    access_reason: payload.access_reason.trim() || "成员授权已更新",
    updated_at: now,
    source: "mock",
  };

  const targetIndex = bindingStore.findIndex(
    (item) => item.agent_id === payload.agent_id && item.account_id === normalizedAccountId
  );
  if (targetIndex >= 0) {
    bindingStore[targetIndex] = nextRecord;
  } else {
    bindingStore.unshift(nextRecord);
  }

  activityStore.unshift({
    activity_id: `member-access-activity-${Date.now()}`,
    agent_id: payload.agent_id,
    account_id: normalizedAccountId,
    title: "成员授权已保存",
    summary: nextRecord.access_reason,
    level: "info",
    occurred_at: now,
    source: "mock",
  });

  return cloneBindingRecord(nextRecord);
}

export async function clearMemberAccessBinding(
  agentId: string,
  accountId?: string | null
): Promise<MemberAccessBindingRecord> {
  const now = new Date().toISOString();
  const normalizedAccountId = accountId?.trim() || null;
  const clearedRecord: MemberAccessBindingRecord = {
    binding_id: `binding-${agentId}-${normalizedAccountId ?? "global"}`,
    agent_id: agentId,
    account_id: normalizedAccountId,
    role_key: null,
    scope: normalizedAccountId ? "account" : "global",
    account_scope: [],
    page_scope: [],
    access_reason: "成员角色已移除",
    updated_at: now,
    source: "mock",
  };

  const targetIndex = bindingStore.findIndex(
    (item) => item.agent_id === agentId && item.account_id === normalizedAccountId
  );
  if (targetIndex >= 0) {
    bindingStore[targetIndex] = clearedRecord;
  } else {
    bindingStore.unshift(clearedRecord);
  }

  activityStore.unshift({
    activity_id: `member-access-activity-${Date.now()}`,
    agent_id: agentId,
    account_id: normalizedAccountId,
    title: "成员角色已移除",
    summary: normalizedAccountId ?? "全局授权已清空",
    level: "warning",
    occurred_at: now,
    source: "mock",
  });

  return cloneBindingRecord(clearedRecord);
}

export async function resetMemberAccessBinding(
  agentId: string,
  accountId?: string | null
): Promise<void> {
  const normalizedAccountId = accountId?.trim() || null;
  const targetIndex = bindingStore.findIndex(
    (item) => item.agent_id === agentId && item.account_id === normalizedAccountId
  );
  if (targetIndex >= 0) {
    bindingStore.splice(targetIndex, 1);
  }

  activityStore.unshift({
    activity_id: `member-access-activity-${Date.now()}`,
    agent_id: agentId,
    account_id: normalizedAccountId,
    title: "成员授权已重置",
    summary: "回退到派生角色与默认范围",
    level: "info",
    occurred_at: new Date().toISOString(),
    source: "mock",
  });
}

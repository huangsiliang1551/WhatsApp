import type { MemberAccessActivityItem } from "../types/memberAccess";

export type MemberAccessBindingRecord = {
  binding_id: string;
  agent_id: string;
  account_id: string | null;
  role_key: string | null;
  scope: "global" | "account";
  account_scope: string[];
  page_scope: string[];
  access_reason: string;
  updated_at: string;
  source: "mock";
};

export const mockMemberAccessBindings: MemberAccessBindingRecord[] = [
  {
    binding_id: "binding-platform-sec-1",
    agent_id: "agent-platform-sec-1",
    account_id: null,
    role_key: "super_admin",
    scope: "global",
    account_scope: ["ALL"],
    page_scope: ["全部后台"],
    access_reason: "平台安全账号保留全局管理权限",
    updated_at: "2026-06-11T09:08:00Z",
    source: "mock",
  },
  {
    binding_id: "binding-cn-review-1",
    agent_id: "agent-cn-review-1",
    account_id: "brand-demo-cn",
    role_key: "reviewer",
    scope: "account",
    account_scope: ["brand-demo-cn"],
    page_scope: ["审核", "工单", "客户档案"],
    access_reason: "CN 审核员仅保留审核与工单范围",
    updated_at: "2026-06-11T08:42:00Z",
    source: "mock",
  },
  {
    binding_id: "binding-es-admin-1",
    agent_id: "agent-es-admin-1",
    account_id: "brand-demo-es",
    role_key: "operator",
    scope: "account",
    account_scope: ["brand-demo-es"],
    page_scope: ["工作台", "客户档案", "工单", "模板"],
    access_reason: "ES 账号仍按坐席权限运行",
    updated_at: "2026-06-11T08:18:00Z",
    source: "mock",
  },
];

export const mockMemberAccessActivities: MemberAccessActivityItem[] = [
  {
    activity_id: "member-access-activity-1",
    agent_id: "agent-cn-review-1",
    account_id: "brand-demo-cn",
    title: "审核权限已收口",
    summary: "仅保留 CN 账号审核、工单与客户档案访问",
    level: "info",
    occurred_at: "2026-06-11T08:42:00Z",
    source: "mock",
  },
  {
    activity_id: "member-access-activity-2",
    agent_id: "agent-es-admin-1",
    account_id: "brand-demo-es",
    title: "ES 账号待切换 SSO",
    summary: "密码登录仍在迁移，暂不开放系统级页面",
    level: "warning",
    occurred_at: "2026-06-11T08:18:00Z",
    source: "mock",
  },
  {
    activity_id: "member-access-activity-3",
    agent_id: "agent-platform-sec-1",
    account_id: null,
    title: "全局管理员保留",
    summary: "平台安全账号继续保留全局基线处理权限",
    level: "info",
    occurred_at: "2026-06-11T07:55:00Z",
    source: "mock",
  },
];

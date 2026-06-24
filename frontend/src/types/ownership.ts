// 归属 / 划转 / 会话 AI 类型（spec 5.4-5.10, 9, 10）

export interface MemberOwnerAssignment {
  id: string;
  account_id: string;
  agency_id: string | null;
  site_id: string | null;
  user_id: string;
  member_profile_id: string;
  owner_staff_user_id: string;
  owner_agency_member_id: string | null;
  source_type: string;
  source_entry_link_id: string | null;
  source_invite_code: string | null;
  source_referrer_user_id: string | null;
  assigned_at: string;
  ended_at: string | null;
  is_current: boolean;
  changed_by_actor_id: string | null;
  transfer_batch_id: string | null;
  reason: string | null;
}

export interface MemberAIAssignment {
  id: string;
  account_id: string;
  agency_id: string | null;
  site_id: string | null;
  user_id: string;
  member_profile_id: string;
  ai_agent_id: string;
  source_type: string;
  source_entry_link_id: string | null;
  assigned_at: string;
  ended_at: string | null;
  is_current: boolean;
  reason: string | null;
}

export interface ConversationAIAssignment {
  id: string;
  conversation_id: string;
  account_id: string;
  bound_ai_agent_id: string | null;
  actual_ai_agent_id: string;
  source_type: string;
  failover_from_ai_agent_id: string | null;
  failover_reason: string | null;
  is_current: boolean;
  assigned_at: string;
}

export interface OwnershipTransferInput {
  from_staff_user_id?: string | null;
  to_staff_user_id?: string | null;
  from_ai_agent_id?: string | null;
  to_ai_agent_id?: string | null;
  member_profile_ids?: string[];
  transfer_all_current_owned_members?: boolean;
  include_open_conversations?: boolean;
  dry_run?: boolean;
  reason?: string | null;
  site_id?: string | null;
}

export interface OwnershipTransferResult {
  batch_id?: string;
  affected_count: number;
  dry_run: boolean;
  member_profile_ids?: string[];
}

export interface OwnershipAuditEvent {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  actor_type: string;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

// 归属快照口径说明（spec 12）：当前列表用 current_*，历史报表用 *_snapshot
export const OWNERSHIP_REPORTING_CALIBER = {
  current: "当前列表口径：使用 MemberProfile.current_* / Conversation.current_* 字段",
  history: "历史报表口径：使用业务记录创建时写入的 owner_*_snapshot / ai_*_snapshot 字段，划转不改历史",
} as const;

// AI failover 口径
export const AI_FAILOVER_CALIBER = {
  temporary: "临时 failover：不改 MemberProfile.current_ai_agent_id，会话 actual_ai 切到兜底 AI",
  permanent: "永久迁移：结束旧 MemberAIAssignment，更新 current_ai_agent_id，历史消息不变",
} as const;

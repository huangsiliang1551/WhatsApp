// 归属 / 划转 / 会话 AI 服务（spec 3.2, 9, 10.4-10.6）

import { api } from "./api";
import type {
  ConversationAIAssignment,
  OwnershipAuditEvent,
  OwnershipTransferInput,
  OwnershipTransferResult,
} from "../types/ownership";

export async function transferMembers(
  input: OwnershipTransferInput,
): Promise<OwnershipTransferResult> {
  const response = await api.post<OwnershipTransferResult>(
    "/api/member-ownership/transfers",
    input,
  );
  return response.data;
}

export async function transferMemberAI(
  input: OwnershipTransferInput,
): Promise<OwnershipTransferResult> {
  const response = await api.post<OwnershipTransferResult>(
    "/api/member-ai-ownership/transfers",
    input,
  );
  return response.data;
}

export async function runAIFailoverMigration(
  input: OwnershipTransferInput,
): Promise<{ affected_count: number; from_ai_agent_id: string; to_ai_agent_id: string }> {
  const response = await api.post(
    "/api/member-ai-ownership/failover/run",
    input,
  );
  return response.data;
}

export async function getConversationAIAssignment(
  conversationId: string,
  accountId: string,
): Promise<ConversationAIAssignment> {
  const response = await api.get<ConversationAIAssignment>(
    `/api/conversations/${conversationId}/ai-assignment`,
    { params: { account_id: accountId } },
  );
  return response.data;
}

export async function switchConversationAI(
  conversationId: string,
  accountId: string,
  toAiAgentId: string,
  reason?: string,
): Promise<{ assignment_id: string; actual_ai_agent_id: string }> {
  const response = await api.post(
    `/api/conversations/${conversationId}/ai-assignment/switch`,
    { to_ai_agent_id: toAiAgentId, reason },
    { params: { account_id: accountId } },
  );
  return response.data;
}

export async function listOwnershipAuditEvents(params?: {
  target_type?: string;
  target_id?: string;
  action?: string;
  limit?: number;
}): Promise<OwnershipAuditEvent[]> {
  const response = await api.get<OwnershipAuditEvent[]>(
    "/api/ownership-audit/events",
    { params },
  );
  return response.data;
}

// 归属 / AI 接待 / 入口链接 报表前端服务（spec 13）。

import { api } from "./api";

export interface OwnershipReport {
  current: {
    owner: {
      by_owner: Array<{ owner_staff_user_id: string | null; member_count: number }>;
      unattributed: number;
    };
    ai: {
      by_ai_agent: Array<{ ai_agent_id: string | null; member_count: number }>;
      no_ai_assignment: number;
    };
  };
  history: {
    owner: Array<{
      owner_staff_user_id: string | null;
      direction: string;
      message_count: number;
    }>;
    ai: Array<{ ai_agent_id: string | null; ai_message_count: number }>;
    entry_link: Array<{ entry_link_id: string | null; message_count: number }>;
  };
  ai_reception: {
    ai_message_count: number;
    conversation_count: number;
    failover_event_count: number;
    handover_log_count: number;
  };
  entry_links: Array<{
    entry_link_id: string;
    code: string;
    link_type: string;
    status: string;
    usage_count: number;
    last_used_at: string | null;
    members_registered: number;
    ai_assigned: number;
    conversations: number;
    ai_messages: number;
  }>;
  anomalies: {
    no_owner_member_count: number;
    no_ai_member_count: number;
    entry_link_pointing_disabled_ai: number;
    ai_without_fallback_staff: number;
    generated_at: string;
  };
}

export async function fetchOwnershipReport(params?: {
  account_id?: string;
}): Promise<OwnershipReport> {
  const response = await api.get<OwnershipReport>("/api/reports/ownership", { params });
  return response.data;
}

export async function createAIOutboundJob(payload: {
  account_id: string;
  agency_id?: string | null;
  site_id?: string | null;
  ai_agent_id: string;
  user_id?: string | null;
  member_profile_id?: string | null;
  conversation_id?: string | null;
  waba_id?: string | null;
  phone_number_id?: string | null;
  recipient_wa_id?: string | null;
  trigger_type: string;
  generated_text?: string | null;
  template_id?: string | null;
  template_name?: string | null;
  template_language?: string | null;
  opt_in?: boolean;
  scheduled_at?: string | null;
  source_entry_link_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
}): Promise<{
  id: string;
  status: string;
  message_policy: string;
  error_message: string | null;
  template_id: string | null;
  template_name: string | null;
}> {
  const response = await api.post("/api/ai-outbound-jobs", payload);
  return response.data;
}

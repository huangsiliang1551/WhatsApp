// 归属 / AI 接待 / 入口链接 前端类型（spec 3.2, 5.1-5.10）

export interface EntryLink {
  id: string;
  code: string;
  link_type: string;
  channel: string;
  status: string;
  target_type: string;
  target_staff_user_id: string | null;
  target_agency_member_id: string | null;
  target_ai_agent_id: string | null;
  site_id: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  whatsapp_phone_number: string | null;
  usage_count: number;
  usage_limit: number | null;
  expires_at: string | null;
  last_used_at: string | null;
  h5_register_url: string | null;
  whatsapp_chat_url: string | null;
  qr_payload: string | null;
  created_at: string;
}

export interface EntryLinkStats {
  id: string;
  code: string;
  usage_count: number;
  usage_limit: number | null;
  status: string;
  last_used_at: string | null;
}

export interface EntryLinkCreateInput {
  link_type: string;
  channel?: string;
  target_type: string;
  target_staff_user_id?: string | null;
  target_ai_agent_id?: string | null;
  site_id?: string | null;
  waba_id?: string | null;
  phone_number_id?: string | null;
  whatsapp_phone_number?: string | null;
  usage_limit?: number | null;
  expires_at?: string | null;
}

export const ENTRY_LINK_TYPES = [
  "staff_register",
  "ai_register",
  "ai_chat",
  "staff_ai_register",
  "member_invite",
  "site_default_staff",
  "site_default_ai",
  "qr",
  "ad",
] as const;

export const ENTRY_LINK_STATUSES = [
  "active",
  "disabled",
  "revoked",
  "expired",
  "target_unavailable",
  "usage_limit_reached",
] as const;

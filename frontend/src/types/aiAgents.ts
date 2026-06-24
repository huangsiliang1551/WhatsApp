// AI Agent 主体类型（spec 5.2, 6.2）

export interface AIAgent {
  id: string;
  account_id: string;
  agency_id: string | null;
  site_id: string | null;
  name: string;
  display_name: string;
  description: string | null;
  status: AIAgentStatus;
  provider_name: string;
  model_name: string;
  prompt_version: string | null;
  waba_id: string | null;
  phone_number_id: string | null;
  owning_staff_user_id: string | null;
  fallback_staff_user_id: string | null;
  fallback_ai_agent_id: string | null;
  auto_reply_enabled: boolean;
  proactive_send_enabled: boolean;
  health_status: AIAgentHealthStatus;
  last_health_check_at: string | null;
  created_at: string;
}

export type AIAgentStatus =
  | "active"
  | "disabled"
  | "suspended"
  | "archived"
  | "deleted";

export type AIAgentHealthStatus =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "disabled"
  | "suspended";

export interface AIAgentCreateInput {
  name: string;
  display_name: string;
  description?: string | null;
  agency_id?: string | null;
  site_id?: string | null;
  provider_name?: string;
  model_name?: string;
  prompt_version?: string | null;
  system_prompt?: string | null;
  waba_id?: string | null;
  phone_number_id?: string | null;
  owning_staff_user_id?: string | null;
  fallback_staff_user_id?: string | null;
  fallback_ai_agent_id?: string | null;
  auto_reply_enabled?: boolean;
  proactive_send_enabled?: boolean;
}

export interface AIAgentPatchInput {
  name?: string;
  display_name?: string;
  description?: string | null;
  system_prompt?: string | null;
  owning_staff_user_id?: string | null;
  fallback_staff_user_id?: string | null;
  fallback_ai_agent_id?: string | null;
  auto_reply_enabled?: boolean;
  proactive_send_enabled?: boolean;
}

export const AI_AGENT_STATUSES: AIAgentStatus[] = [
  "active",
  "disabled",
  "suspended",
  "archived",
  "deleted",
];

export const AI_AGENT_HEALTH_STATUSES: AIAgentHealthStatus[] = [
  "healthy",
  "degraded",
  "unavailable",
  "disabled",
  "suspended",
];

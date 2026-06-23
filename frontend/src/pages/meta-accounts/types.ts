import type { MetaPhoneNumber } from "../../services/api";

export type ActiveTabId = "accounts" | "phones" | "webhooks" | "signups";

/** 手动添加表单值（对齐 ManualMetaAccountPayload） */
export interface ManualFormValues {
  display_name: string;
  meta_business_portfolio_id: string;
  waba_id: string;
  access_token: string;
  app_secret?: string;
  token_source: "system_user" | "user_access_token";
  notes?: string;
  phone_numbers: Array<{
    phone_number_id: string;
    display_phone_number: string;
    verified_name?: string;
    quality_rating: "GREEN" | "YELLOW" | "RED" | "UNKNOWN";
    is_registered: boolean;
  }>;
}

/** Tab 配置 */
export interface TabConfig {
  key: ActiveTabId;
  label: string;
  /** 统计 badge 数，null 时不显示 */
  count?: (data: Record<string, unknown>) => number;
}

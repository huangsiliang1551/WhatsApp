import type {
  EmbeddedSignupSession,
  LaunchReadinessResponse,
  MetaWebhookSubscriptionView,
  MetaWabaAccount,
  RuntimeConfigSummary,
} from "../services/api";

export type IntegrationAccountSummary = {
  account_id: string;
  display_name: string;
  waba_id: string;
  meta_business_portfolio_id: string;
  onboarding_mode: MetaWabaAccount["onboarding_mode"];
  account_is_active: boolean;
  is_active: boolean;
  phone_number_count: number;
  registered_phone_number_count: number;
  webhook_runtime_status: MetaWabaAccount["webhook_runtime_status"];
  webhook_verification_status: MetaWabaAccount["webhook_verification_status"];
  webhook_subscription_status: MetaWabaAccount["webhook_subscription_status"];
  ready_for_webhook_delivery: boolean;
  ready_for_outbound_messages: boolean;
  ready_for_formal_activation: boolean;
  blocking_reasons: string[];
  last_signup_status: EmbeddedSignupSession["status"] | null;
  last_signup_stage: EmbeddedSignupSession["completion_stage"] | null;
  last_signup_at: string | null;
};

export type IntegrationCenterSnapshot = {
  generated_at: string;
  source: "api";
  config: Pick<
    RuntimeConfigSummary,
    | "app_env"
    | "test_mode"
    | "messaging_provider"
    | "ai_provider"
    | "queue_backend"
    | "openai_configured"
    | "deepseek_configured"
  > | null;
  launch_readiness: LaunchReadinessResponse | null;
  accounts: IntegrationAccountSummary[];
  subscriptions: MetaWebhookSubscriptionView[];
  signup_sessions: EmbeddedSignupSession[];
  warnings: string[];
};

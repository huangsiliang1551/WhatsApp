import type {
  LaunchReadinessResponse,
  MetaWebhookSubscriptionView,
  MetaWabaAccount,
  ProviderStatusBufferEntry,
  RuntimeConfigSummary,
} from "../services/api";

export type ApiWebhookPolicyItem = {
  policy_id: string;
  account_id: string | null;
  policy_name: string;
  signature_mode: "strict" | "compat";
  replay_limit_per_minute: number;
  ip_allowlist_enabled: boolean;
  secret_rotation_state: "ready" | "pending" | "overdue";
  effective_result: "enforced" | "partial" | "review";
  effective_reason: string;
  updated_at: string;
  source: "mock";
};

export type ApiWebhookPolicyCreatePayload = {
  account_id?: string | null;
  policy_name: string;
  signature_mode: "strict" | "compat";
  replay_limit_per_minute: number;
  ip_allowlist_enabled: boolean;
  effective_reason: string;
};

export type ApiWebhookSnapshot = {
  generated_at: string;
  source: "hybrid";
  config: Pick<
    RuntimeConfigSummary,
    "app_env" | "test_mode" | "messaging_provider" | "queue_backend"
  > | null;
  launch_readiness: LaunchReadinessResponse | null;
  subscriptions: MetaWebhookSubscriptionView[];
  accounts: MetaWabaAccount[];
  provider_pending: ProviderStatusBufferEntry[];
  policies: ApiWebhookPolicyItem[];
  warnings: string[];
};

import {
  getLaunchReadiness,
  getRuntimeConfigSummary,
  listMetaAccounts,
  listMetaWebhookSubscriptions,
  listProviderStatusBuffer,
} from "./api";
import { mockApiWebhookPolicies } from "../mocks/apiWebhooks";
import type {
  ApiWebhookPolicyCreatePayload,
  ApiWebhookPolicyItem,
  ApiWebhookSnapshot,
} from "../types/apiWebhooks";

const policyStore = mockApiWebhookPolicies.map((item) => ({ ...item }));

function clonePolicy(policy: ApiWebhookPolicyItem): ApiWebhookPolicyItem {
  return { ...policy };
}

function filterPolicies(accountId?: string): ApiWebhookPolicyItem[] {
  if (!accountId) {
    return policyStore.map(clonePolicy);
  }
  return policyStore
    .filter((item) => item.account_id === null || item.account_id === accountId)
    .map(clonePolicy);
}

export async function getApiWebhookSnapshot(accountId?: string): Promise<ApiWebhookSnapshot> {
  const [configResult, readinessResult, subscriptionsResult, accountsResult, providerResult] =
    await Promise.allSettled([
      getRuntimeConfigSummary(),
      getLaunchReadiness(accountId ? { account_id: accountId } : undefined),
      listMetaWebhookSubscriptions(accountId ? { account_id: accountId } : undefined),
      listMetaAccounts(accountId ? { account_id: accountId } : undefined),
      listProviderStatusBuffer({
        account_id: accountId,
        replay_state: "pending",
        limit: 20,
      }),
    ]);

  const warnings: string[] = [];
  if (configResult.status !== "fulfilled") warnings.push("运行配置加载失败");
  if (readinessResult.status !== "fulfilled") warnings.push("接入就绪加载失败");
  if (subscriptionsResult.status !== "fulfilled") warnings.push("Webhook 订阅加载失败");
  if (accountsResult.status !== "fulfilled") warnings.push("Meta 账户加载失败");
  if (providerResult.status !== "fulfilled") warnings.push("状态回放积压加载失败");

  if (
    subscriptionsResult.status !== "fulfilled" &&
    accountsResult.status !== "fulfilled" &&
    providerResult.status !== "fulfilled"
  ) {
    throw new Error("API / Webhook 关键接口不可用");
  }

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    config:
      configResult.status === "fulfilled"
        ? {
            app_env: configResult.value.app_env,
            test_mode: configResult.value.test_mode,
            messaging_provider: configResult.value.messaging_provider,
            queue_backend: configResult.value.queue_backend,
          }
        : null,
    launch_readiness: readinessResult.status === "fulfilled" ? readinessResult.value : null,
    subscriptions: subscriptionsResult.status === "fulfilled" ? subscriptionsResult.value : [],
    accounts: accountsResult.status === "fulfilled" ? accountsResult.value : [],
    provider_pending: providerResult.status === "fulfilled" ? providerResult.value.items : [],
    policies: filterPolicies(accountId),
    warnings,
  };
}

export async function createApiWebhookPolicy(
  payload: ApiWebhookPolicyCreatePayload
): Promise<ApiWebhookPolicyItem> {
  const created: ApiWebhookPolicyItem = {
    policy_id: `policy-webhook-${Date.now()}`,
    account_id: payload.account_id?.trim() || null,
    policy_name: payload.policy_name.trim(),
    signature_mode: payload.signature_mode,
    replay_limit_per_minute: payload.replay_limit_per_minute,
    ip_allowlist_enabled: payload.ip_allowlist_enabled,
    secret_rotation_state: "pending",
    effective_result: payload.signature_mode === "strict" ? "enforced" : "review",
    effective_reason: payload.effective_reason.trim() || "新策略待校验",
    updated_at: new Date().toISOString(),
    source: "mock",
  };
  policyStore.unshift(created);
  return clonePolicy(created);
}

export async function rotateWebhookSecret(policyId: string): Promise<ApiWebhookPolicyItem> {
  const target = policyStore.find((item) => item.policy_id === policyId);
  if (!target) {
    throw new Error("Webhook 策略不存在");
  }
  target.secret_rotation_state = "ready";
  target.updated_at = new Date().toISOString();
  target.effective_reason = "已完成一次轮换";
  return clonePolicy(target);
}

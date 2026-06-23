import {
  getLaunchReadiness,
  getRuntimeConfigSummary,
  listAuditLogs,
  listEmbeddedSignupSessions,
  listMetaAccounts,
  listMetaWebhookSubscriptions,
  listProviderStatusBuffer,
  listQueueStats,
  type AuditLogEntry,
  type EmbeddedSignupSession,
  type MetaWabaAccount,
  type ProviderStatusBufferEntry,
  type QueueJob,
} from "./api";
import type { IntegrationAccountSummary, IntegrationCenterSnapshot } from "../types/integrations";
import type { SystemLogEntry, SystemLogSnapshot } from "../types/systemLogs";

function getEventTimestamp(value: string | null | undefined): string {
  return value ?? new Date(0).toISOString();
}

function pickPayloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function getLatestSignupSession(
  sessions: EmbeddedSignupSession[],
  account: MetaWabaAccount
): EmbeddedSignupSession | null {
  const matched = sessions.filter(
    (item) =>
      item.account_id === account.account_id &&
      (item.waba_id === account.waba_id || item.linked_waba_id === account.waba_id)
  );
  if (!matched.length) {
    return null;
  }
  return [...matched].sort(
    (left, right) =>
      Date.parse(getEventTimestamp(right.completed_at ?? right.callback_received_at)) -
      Date.parse(getEventTimestamp(left.completed_at ?? left.callback_received_at))
  )[0];
}

function mapIntegrationAccount(
  account: MetaWabaAccount,
  signupSessions: EmbeddedSignupSession[]
): IntegrationAccountSummary {
  const latestSignup = getLatestSignupSession(signupSessions, account);
  return {
    account_id: account.account_id,
    display_name: account.display_name,
    waba_id: account.waba_id,
    meta_business_portfolio_id: account.meta_business_portfolio_id,
    onboarding_mode: account.onboarding_mode,
    account_is_active: account.account_is_active,
    is_active: account.is_active,
    phone_number_count: account.phone_number_count,
    registered_phone_number_count: account.registered_phone_number_count,
    webhook_runtime_status: account.webhook_runtime_status,
    webhook_verification_status: account.webhook_verification_status,
    webhook_subscription_status: account.webhook_subscription_status,
    ready_for_webhook_delivery: account.ready_for_webhook_delivery,
    ready_for_outbound_messages: account.ready_for_outbound_messages,
    ready_for_formal_activation: account.ready_for_formal_activation,
    blocking_reasons: [...account.blocking_reasons],
    last_signup_status: latestSignup?.status ?? null,
    last_signup_stage: latestSignup?.completion_stage ?? null,
    last_signup_at: latestSignup?.completed_at ?? latestSignup?.callback_received_at ?? null,
  };
}

export async function getIntegrationCenterSnapshot(
  accountId?: string
): Promise<IntegrationCenterSnapshot> {
  const [configResult, readinessResult, accountsResult, subscriptionsResult, sessionsResult] =
    await Promise.allSettled([
      getRuntimeConfigSummary(),
      getLaunchReadiness(accountId ? { account_id: accountId } : undefined),
      listMetaAccounts(accountId ? { account_id: accountId } : undefined),
      listMetaWebhookSubscriptions(accountId ? { account_id: accountId } : undefined),
      listEmbeddedSignupSessions(accountId ? { account_id: accountId } : undefined),
    ]);

  const warnings: string[] = [];
  if (configResult.status !== "fulfilled") warnings.push("运行配置加载失败");
  if (readinessResult.status !== "fulfilled") warnings.push("接入就绪加载失败");
  if (accountsResult.status !== "fulfilled") warnings.push("Meta 账户加载失败");
  if (subscriptionsResult.status !== "fulfilled") warnings.push("Webhook 订阅加载失败");
  if (sessionsResult.status !== "fulfilled") warnings.push("嵌入注册加载失败");

  if (
    accountsResult.status !== "fulfilled" &&
    subscriptionsResult.status !== "fulfilled" &&
    sessionsResult.status !== "fulfilled"
  ) {
    throw new Error("集成管理核心接口不可用");
  }

  const signupSessions = sessionsResult.status === "fulfilled" ? sessionsResult.value : [];
  const accounts =
    accountsResult.status === "fulfilled"
      ? accountsResult.value.map((item) => mapIntegrationAccount(item, signupSessions))
      : [];

  return {
    generated_at: new Date().toISOString(),
    source: "api",
    config: configResult.status === "fulfilled" ? configResult.value : null,
    launch_readiness: readinessResult.status === "fulfilled" ? readinessResult.value : null,
    accounts,
    subscriptions: subscriptionsResult.status === "fulfilled" ? subscriptionsResult.value : [],
    signup_sessions: signupSessions,
    warnings,
  };
}

function mapAuditLog(entry: AuditLogEntry): SystemLogEntry {
  return {
    id: `audit:${entry.id}`,
    account_id: entry.account_id,
    source_kind: "audit",
    severity: "info",
    title: entry.action,
    summary: `${entry.target_type} / ${entry.target_id ?? "暂无"}`,
    detail: `${entry.actor_type} / ${entry.actor_id ?? "暂无"}`,
    occurred_at: entry.created_at,
    source: "api",
    target_type: entry.target_type,
    target_id: entry.target_id,
  };
}

function mapProviderEntry(entry: ProviderStatusBufferEntry): SystemLogEntry {
  const severity = entry.replay_state === "pending" ? "warning" : "info";
  return {
    id: `provider:${entry.id}`,
    account_id: entry.account_id,
    source_kind: "provider",
    severity,
    title: `${entry.provider_name} / ${entry.external_status}`,
    summary: `${entry.waba_id ?? "暂无 WABA"} / ${entry.phone_number_id ?? "暂无号码"}`,
    detail: `${entry.provider_message_id} / ${entry.replay_state}`,
    occurred_at: entry.occurred_at ?? entry.last_seen_at,
    source: "api",
    provider_name: entry.provider_name,
    provider_message_id: entry.provider_message_id,
  };
}

function mapFailedJob(job: QueueJob): SystemLogEntry {
  const accountId = pickPayloadString(job.payload, "account_id");
  const conversationId = pickPayloadString(job.payload, "conversation_id");
  const jobType = pickPayloadString(job.payload, "job_type");

  return {
    id: `queue:${job.job_id}`,
    account_id: accountId,
    source_kind: "queue",
    severity: "critical",
    title: `${job.queue} 失败`,
    summary: `${conversationId ?? "暂无会话"} / ${jobType ?? "任务"}`,
    detail: job.error ?? "无错误详情",
    occurred_at: job.failed_at ?? job.updated_at,
    source: "api",
  };
}

export async function getSystemLogSnapshot(accountId?: string): Promise<SystemLogSnapshot> {
  const [auditResult, providerResult, queueResult] = await Promise.allSettled([
    listAuditLogs({ account_id: accountId, limit: 30 }),
    listProviderStatusBuffer({ account_id: accountId, limit: 30 }),
    listQueueStats(),
  ]);

  const warnings: string[] = [];
  if (auditResult.status !== "fulfilled") warnings.push("审计日志加载失败");
  if (providerResult.status !== "fulfilled") warnings.push("状态回放日志加载失败");
  if (queueResult.status !== "fulfilled") warnings.push("队列失败日志加载失败");

  if (
    auditResult.status !== "fulfilled" &&
    providerResult.status !== "fulfilled" &&
    queueResult.status !== "fulfilled"
  ) {
    throw new Error("系统日志核心接口不可用");
  }

  const auditEntries =
    auditResult.status === "fulfilled" ? auditResult.value.map((item) => mapAuditLog(item)) : [];
  const providerEntries =
    providerResult.status === "fulfilled"
      ? providerResult.value.items.map((item) => mapProviderEntry(item))
      : [];
  const failedJobs =
    queueResult.status === "fulfilled"
      ? queueResult.value.recent_failed_jobs
          .filter((job) => (accountId ? pickPayloadString(job.payload, "account_id") === accountId : true))
          .map((item) => mapFailedJob(item))
      : [];

  const entries = [...failedJobs, ...providerEntries, ...auditEntries].sort(
    (left, right) => Date.parse(right.occurred_at) - Date.parse(left.occurred_at)
  );

  return {
    generated_at: new Date().toISOString(),
    source: "api",
    audit_count: auditEntries.length,
    provider_pending_count: providerEntries.filter((item) => item.severity === "warning").length,
    failed_job_count: failedJobs.length,
    critical_count: entries.filter((item) => item.severity === "critical").length,
    entries,
    warnings,
  };
}

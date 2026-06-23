import { mockNotificationChannels } from "../mocks/notifications";
import { getAlertCenterSnapshot, listAlertRules, listMemberDirectory } from "./operations";
import type {
  NotificationCenterSnapshot,
  NotificationChannelConfig,
  NotificationChannelCreatePayload,
  NotificationDeliveryLog,
} from "../types/notifications";

const channelStore = mockNotificationChannels.map((item) => ({ ...item }));
let runtimeChannelCache: NotificationChannelConfig[] = [];

function cloneChannel(channel: NotificationChannelConfig): NotificationChannelConfig {
  return { ...channel };
}

function filterChannels(accountId?: string): NotificationChannelConfig[] {
  if (!accountId) {
    return channelStore.map(cloneChannel);
  }
  return channelStore
    .filter((item) => item.account_id === null || item.account_id === accountId)
    .map(cloneChannel);
}

function hasConfiguredChannel(
  channels: NotificationChannelConfig[],
  accountId: string | null,
  channelType: NotificationChannelConfig["channel_type"]
): boolean {
  return channels.some(
    (item) => item.account_id === accountId && item.channel_type === channelType
  );
}

function mapRuleChannelType(label: string): NotificationChannelConfig["channel_type"] | null {
  if (label.includes("控制台")) return "console";
  if (label.includes("邮件")) return "email";
  if (label.includes("企业微信")) return "wecom";
  if (label.toLowerCase().includes("webhook")) return "webhook";
  return null;
}

function getDerivedChannelName(
  accountId: string | null,
  channelType: NotificationChannelConfig["channel_type"]
): string {
  const scopeLabel = accountId ?? "全局";
  if (channelType === "console") return `${scopeLabel} 控制台`;
  if (channelType === "email") return `${scopeLabel} 邮件`;
  if (channelType === "wecom") return `${scopeLabel} 企业微信`;
  return `${scopeLabel} Webhook`;
}

function getDerivedChannelTarget(
  channelType: NotificationChannelConfig["channel_type"],
  scopedMembers: NotificationCenterSnapshot["members"]
): string {
  if (channelType === "console") {
    const onlineCount = scopedMembers.filter((member) => member.status === "online").length;
    return `在线成员 ${onlineCount}/${scopedMembers.length}`;
  }
  if (channelType === "email") return "alerts@example.com";
  if (channelType === "wecom") return "wecom://group/duty";
  return "https://hooks.example.com/runtime-alerts";
}

function buildDerivedChannels(
  configuredChannels: NotificationChannelConfig[],
  members: NotificationCenterSnapshot["members"],
  alertSnapshot: NotificationCenterSnapshot["alert_snapshot"],
  rules: NotificationCenterSnapshot["rules"],
  accountId?: string
): NotificationChannelConfig[] {
  const accountIds = new Set<string>();
  members.forEach((member) => {
    if (member.account_id) {
      accountIds.add(member.account_id);
    }
  });
  alertSnapshot?.items.forEach((item) => {
    if (item.account_id) {
      accountIds.add(item.account_id);
    }
  });
  rules.forEach((item) => {
    if (item.account_id) {
      accountIds.add(item.account_id);
    }
  });

  const derived: NotificationChannelConfig[] = [];

  if (!hasConfiguredChannel(configuredChannels, null, "console")) {
    const onlineCount = members.filter((member) => member.status === "online").length;
    derived.push({
      channel_id: "derived-channel:console:global",
      account_id: null,
      channel_type: "console",
      name: "全局控制台",
      target: `在线成员 ${onlineCount}/${members.length}`,
      enabled: true,
      delivery_mode: "immediate",
      effective_result: members.length > 0 ? "enforced" : "partial",
      effective_reason: members.length > 0 ? "已接入运行态成员覆盖" : "暂无运行态成员覆盖",
      source: "hybrid",
    });
  }

  Array.from(accountIds)
    .filter((item) => (accountId ? item === accountId : true))
    .sort((left, right) => left.localeCompare(right, "zh-CN"))
    .forEach((scopedAccountId) => {
      if (hasConfiguredChannel(configuredChannels, scopedAccountId, "console")) {
        return;
      }
      const scopedMembers = members.filter((member) => member.account_id === scopedAccountId);
      const onlineCount = scopedMembers.filter((member) => member.status === "online").length;
      derived.push({
        channel_id: `derived-channel:console:${scopedAccountId}`,
        account_id: scopedAccountId,
        channel_type: "console",
        name: `${scopedAccountId} 控制台值班`,
        target: `在线成员 ${onlineCount}/${scopedMembers.length}`,
        enabled: true,
        delivery_mode: "immediate",
        effective_result: scopedMembers.length > 0 ? "enforced" : "partial",
        effective_reason:
          scopedMembers.length > 0 ? "按账号运行态成员自动派生" : "该账号暂无可用成员覆盖",
        source: "hybrid",
      });
    });

  const activeRules = rules.filter((item) => item.status === "active");
  activeRules.forEach((rule) => {
    rule.notify_channels.forEach((label) => {
      const channelType = mapRuleChannelType(label);
      if (!channelType) {
        return;
      }
      if (hasConfiguredChannel(configuredChannels, rule.account_id, channelType)) {
        return;
      }
      if (derived.some((item) => item.account_id === rule.account_id && item.channel_type === channelType)) {
        return;
      }

      const scopedMembers = members.filter((member) =>
        rule.account_id ? member.account_id === rule.account_id : true
      );
      derived.push({
        channel_id: `derived-rule-channel:${rule.rule_id}:${channelType}`,
        account_id: rule.account_id,
        channel_type: channelType,
        name: getDerivedChannelName(rule.account_id, channelType),
        target: getDerivedChannelTarget(channelType, scopedMembers),
        enabled: true,
        delivery_mode: rule.severity === "critical" ? "immediate" : "batch",
        effective_result: scopedMembers.length > 0 || channelType !== "console" ? "partial" : "review",
        effective_reason: `${rule.name} / ${rule.condition_summary}`,
        source: "hybrid",
      });
    });
  });

  return derived;
}

function mergeChannels(
  configuredChannels: NotificationChannelConfig[],
  derivedChannels: NotificationChannelConfig[],
  accountId?: string
): NotificationChannelConfig[] {
  return [...configuredChannels, ...derivedChannels]
    .filter((item) => (accountId ? item.account_id === null || item.account_id === accountId : true))
    .sort((left, right) =>
      `${left.account_id ?? ""}:${left.name}`.localeCompare(
        `${right.account_id ?? ""}:${right.name}`,
        "zh-CN"
      )
    );
}

function getDeliveryStatus(
  severity: NotificationDeliveryLog["severity"],
  channel: NotificationChannelConfig
): NotificationDeliveryLog["delivery_status"] {
  if (!channel.enabled) return "pending";
  if (channel.channel_type === "webhook" && severity !== "critical") return "pending";
  if (channel.channel_type === "email" && severity === "critical") return "failed";
  return "delivered";
}

function buildDeliveries(
  items: NonNullable<NotificationCenterSnapshot["alert_snapshot"]>["items"],
  channels: NotificationChannelConfig[]
): NotificationDeliveryLog[] {
  return items.flatMap((item) =>
    channels
      .filter((channel) => channel.account_id === null || channel.account_id === item.account_id)
      .slice(0, 2)
      .map((channel, index) => ({
        delivery_id: `${item.id}:${channel.channel_id}:${index}`,
        account_id: item.account_id,
        channel_id: channel.channel_id,
        channel_name: channel.name,
        channel_type: channel.channel_type,
        severity: item.severity,
        title: item.title,
        summary: item.summary,
        delivery_status: getDeliveryStatus(item.severity, channel),
        sent_at: item.occurred_at,
        source: "hybrid",
      }))
  );
}

export async function getNotificationCenterSnapshot(
  accountId?: string
): Promise<NotificationCenterSnapshot> {
  const [snapshotResult, rulesResult, membersResult] = await Promise.allSettled([
    getAlertCenterSnapshot(accountId),
    listAlertRules(accountId),
    listMemberDirectory(accountId),
  ]);

  const warnings: string[] = [];
  if (snapshotResult.status !== "fulfilled") warnings.push("告警快照加载失败");
  if (rulesResult.status !== "fulfilled") warnings.push("告警规则加载失败");
  if (membersResult.status !== "fulfilled") warnings.push("成员目录加载失败");

  if (
    snapshotResult.status !== "fulfilled" &&
    rulesResult.status !== "fulfilled" &&
    membersResult.status !== "fulfilled"
  ) {
    throw new Error("通知中心核心接口不可用");
  }

  const configuredChannels = filterChannels(accountId);
  const members = membersResult.status === "fulfilled" ? membersResult.value : [];
  const rules =
    rulesResult.status === "fulfilled"
      ? rulesResult.value.filter((item) =>
          accountId ? item.account_id === null || item.account_id === accountId : true
        )
      : [];
  const derivedChannels = buildDerivedChannels(
    configuredChannels,
    members,
    snapshotResult.status === "fulfilled" ? snapshotResult.value : null,
    rules,
    accountId
  );
  const channels = mergeChannels(configuredChannels, derivedChannels, accountId);
  runtimeChannelCache = channels.map(cloneChannel);
  const deliveries =
    snapshotResult.status === "fulfilled" ? buildDeliveries(snapshotResult.value.items, channels) : [];

  return {
    generated_at: new Date().toISOString(),
    source: "hybrid",
    alert_snapshot: snapshotResult.status === "fulfilled" ? snapshotResult.value : null,
    rules,
    members,
    channels,
    deliveries,
    warnings,
  };
}

export async function createNotificationChannel(
  payload: NotificationChannelCreatePayload
): Promise<NotificationChannelConfig> {
  const created: NotificationChannelConfig = {
    channel_id: `channel-${Date.now()}`,
    account_id: payload.account_id?.trim() || null,
    channel_type: payload.channel_type,
    name: payload.name.trim(),
    target: payload.target.trim(),
    enabled: payload.enabled ?? true,
    delivery_mode: payload.delivery_mode,
    effective_result: payload.delivery_mode === "immediate" ? "enforced" : "review",
    effective_reason: payload.effective_reason.trim() || "新渠道待校验",
    source: "mock",
  };
  channelStore.unshift(created);
  return cloneChannel(created);
}

export async function toggleNotificationChannel(channelId: string): Promise<NotificationChannelConfig> {
  let target = channelStore.find((item) => item.channel_id === channelId);
  if (!target) {
    const runtimeTarget = runtimeChannelCache.find((item) => item.channel_id === channelId);
    if (!runtimeTarget) {
      throw new Error("通知渠道不存在");
    }
    target = {
      ...cloneChannel(runtimeTarget),
      source: "mock",
    };
    channelStore.unshift(target);
  }
  target.enabled = !target.enabled;
  target.effective_reason = target.enabled ? "已启用通知" : "已暂停通知";
  return cloneChannel(target);
}

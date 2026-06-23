import type { AlertCenterSnapshot, AlertRuleDefinition, MemberDirectoryItem } from "./operations";

export type NotificationChannelType = "console" | "email" | "wecom" | "webhook";

export type NotificationChannelConfig = {
  channel_id: string;
  account_id: string | null;
  channel_type: NotificationChannelType;
  name: string;
  target: string;
  enabled: boolean;
  delivery_mode: "immediate" | "batch";
  effective_result: "enforced" | "partial" | "review";
  effective_reason: string;
  source: "hybrid" | "mock";
};

export type NotificationChannelCreatePayload = {
  account_id?: string | null;
  channel_type: NotificationChannelType;
  name: string;
  target: string;
  delivery_mode: "immediate" | "batch";
  effective_reason: string;
  enabled?: boolean;
};

export type NotificationDeliveryLog = {
  delivery_id: string;
  account_id: string | null;
  channel_id: string;
  channel_name: string;
  channel_type: NotificationChannelType;
  severity: "critical" | "warning" | "info";
  title: string;
  summary: string;
  delivery_status: "delivered" | "pending" | "failed";
  sent_at: string;
  source: "hybrid";
};

export type NotificationCenterSnapshot = {
  generated_at: string;
  source: "hybrid";
  alert_snapshot: AlertCenterSnapshot | null;
  rules: AlertRuleDefinition[];
  members: MemberDirectoryItem[];
  channels: NotificationChannelConfig[];
  deliveries: NotificationDeliveryLog[];
  warnings: string[];
};

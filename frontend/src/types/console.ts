import type { AppPageId } from "../stores/appStore";

export type ConsoleDataSourceTone = "api" | "hybrid" | "mock" | "placeholder";

export type ConsoleDataSourceBadge = {
  label: string;
  tone: ConsoleDataSourceTone;
  detail: string;
};

export type ConsolePageProgressTone = "done" | "in_progress" | "planned";

export type ConsolePageProgress = {
  label: string;
  tone: ConsolePageProgressTone;
  detail: string;
};

export type ConsoleRouteGroup =
  | "workspace"      // 工作台（原 core_workspace）
  | "content"        // 内容中心（原 assets）
  | "people"         // 人员管理（新）
  | "analytics"      // 数据报表（新）
  | "finance"        // 财务管理（新）
  | "settings"       // 系统设置（新）
  | "devops";        // 运维监控（新）

export type ConsoleRouteIconKey =
  | "dashboard"
  | "workspace"
  | "accounts"
  | "templates"
  | "analytics"
  | "monitoring"
  | "webhooks"
  | "provider_events"
  | "integrations"
  | "system_logs"
  | "evidence_center"
  | "media"
  | "tags"
  | "audience_rules"
  | "ecommerce"
  | "tasks"
  | "reviews"
  | "tickets"
  | "users"
  | "customers"
  | "members"
  | "assignments"
  | "automation"
  | "notifications"
  | "identity_sync"
  | "member_access"
  | "alerts"
  | "reports"
  | "imports"
  | "security"
  | "security_settings"
  | "risk"
  | "operations"
  | "my_queue"
  | "team"
  | "security_center"
  | "ops_board"
  | "sites"
  | "organization"
  | "agents"
  | "settings"
  | "audit"
  | "debug"
  | "api_test"
  | "ai_chat"

export type ConsoleRouteDefinition = {
  id: AppPageId;
  path: string;
  navLabel: string;
  eyebrow: string;
  title: string;
  description: string;
  visibleInNav: boolean;
  hideInMenu?: boolean;
  group: ConsoleRouteGroup;
  order: number;
  icon: ConsoleRouteIconKey;
  dataBadges: ConsoleDataSourceBadge[];
  progress: ConsolePageProgress;
};

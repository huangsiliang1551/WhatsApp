import { api } from "./api";

export type NotificationItem = {
  id: string;
  account_id: string;
  type: string;
  category: string;
  title: string;
  message: string | null;
  severity: string;
  is_read: boolean;
  action_url: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  read_at: string | null;
};

export type NotificationListResponse = {
  items: NotificationItem[];
  total: number;
  limit: number;
  offset: number;
};

export type UnreadCountResponse = {
  unread_count: number;
};

export type MarkReadResponse = {
  marked_count: number;
};

const MOCK_NOTIFICATIONS: NotificationItem[] = [
  { id: "n1", account_id: "mock", type: "alert", category: "ai", title: "AI 回复失败", message: "OpenAI API 返回超时，已降级为规则回复", severity: "error", is_read: false, action_url: null, metadata: null, created_at: new Date(Date.now() - 60000).toISOString(), read_at: null },
  { id: "n2", account_id: "mock", type: "info", category: "system", title: "商品包任务完成", message: "用户完成「新人大礼包」所有任务", severity: "info", is_read: false, action_url: null, metadata: null, created_at: new Date(Date.now() - 120000).toISOString(), read_at: null },
  { id: "n3", account_id: "mock", type: "warning", category: "system", title: "商品任务余额不足", message: "账号 acct-001 的任务余额不足，请及时充值", severity: "warning", is_read: false, action_url: null, metadata: null, created_at: new Date(Date.now() - 300000).toISOString(), read_at: null },
  { id: "n4", account_id: "mock", type: "alert", category: "queue", title: "队列积压警告", message: "AI 处理队列积压超过 100 条", severity: "warning", is_read: true, action_url: null, metadata: null, created_at: new Date(Date.now() - 3600000).toISOString(), read_at: new Date().toISOString() },
  { id: "n5", account_id: "mock", type: "info", category: "template", title: "模板审核通过", message: "模板「优惠提醒」已通过 Meta 审核", severity: "info", is_read: true, action_url: null, metadata: null, created_at: new Date(Date.now() - 7200000).toISOString(), read_at: new Date().toISOString() },
  { id: "n6", account_id: "mock", type: "alert", category: "meta", title: "Meta API 错误", message: "Token 即将过期，请及时更新", severity: "error", is_read: false, action_url: null, metadata: null, created_at: new Date(Date.now() - 14400000).toISOString(), read_at: null },
  { id: "n7", account_id: "mock", type: "info", category: "system", title: "用户注册成功", message: "新用户 xyz 已完成注册", severity: "info", is_read: true, action_url: null, metadata: null, created_at: new Date(Date.now() - 86400000).toISOString(), read_at: new Date().toISOString() },
];

function filterMockNotifications(params: {
  unread?: boolean;
  category?: string;
  limit?: number;
  offset?: number;
}): NotificationListResponse {
  let items = [...MOCK_NOTIFICATIONS];
  if (params.unread) items = items.filter((n) => !n.is_read);
  if (params.category) items = items.filter((n) => n.category === params.category);
  const total = items.length;
  const offset = params.offset ?? 0;
  const limit = params.limit ?? 20;
  items = items.slice(offset, offset + limit);
  return { items, total, limit, offset };
}

export async function listNotifications(params: {
  unread?: boolean;
  category?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<NotificationListResponse> {
  try {
    const r = await api.get<NotificationListResponse>("/api/notifications", { params });
    return r.data;
  } catch {
    return filterMockNotifications(params);
  }
}

export async function getUnreadCount(): Promise<number> {
  try {
    const r = await api.get<UnreadCountResponse>("/api/notifications/unread-count");
    return r.data.unread_count;
  } catch {
    return MOCK_NOTIFICATIONS.filter((n) => !n.is_read).length;
  }
}

export async function getRecentNotifications(limit = 5): Promise<NotificationItem[]> {
  try {
    const r = await api.get<NotificationListResponse>("/api/notifications", {
      params: { limit },
    });
    return r.data.items;
  } catch {
    return MOCK_NOTIFICATIONS.slice(0, limit);
  }
}

export async function markNotificationsRead(ids: string[]): Promise<number> {
  try {
    const r = await api.post<MarkReadResponse>("/api/notifications/mark-read", ids);
    return r.data.marked_count;
  } catch {
    let count = 0;
    for (const id of ids) {
      const n = MOCK_NOTIFICATIONS.find((x) => x.id === id);
      if (n && !n.is_read) { n.is_read = true; n.read_at = new Date().toISOString(); count++; }
    }
    return count;
  }
}

export async function markAllNotificationsRead(): Promise<number> {
  try {
    const r = await api.post<MarkReadResponse>("/api/notifications/mark-all-read", {},
      { params: { account_id: "" } }
    );
    return r.data.marked_count;
  } catch {
    let count = 0;
    for (const n of MOCK_NOTIFICATIONS) {
      if (!n.is_read) { n.is_read = true; n.read_at = new Date().toISOString(); count++; }
    }
    return count;
  }
}

export function getCategoryColor(category: string): string {
  const map: Record<string, string> = {
    ai: "blue", queue: "orange", template: "purple", meta: "red", system: "green",
  };
  return map[category] ?? "default";
}

export function getSeverityColor(severity: string): string {
  const map: Record<string, string> = {
    info: "#1677ff", warning: "#faad14", error: "#ff4d4f", critical: "#cf1322",
  };
  return map[severity] ?? "#999";
}

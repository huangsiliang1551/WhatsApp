/**
 * ChatRealtimeService – SSE + fallback polling 实时聊天服务
 *
 * 职责：
 * - SSE 连接 /api/conversations/stream（?token= 鉴权）
 * - 自动重连（指数退避 1s→2s→4s→8s→max 30s）
 * - new_message / status_change / handover 事件分发
 * - SSE 不可用时降级为轮询（GET /api/conversations/poll?since= 每 5s）
 */

import { adminAuth } from "./adminAuth";

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

export interface NewMessageEvent {
  account_id: string;
  conversation_id: string;
  message_id: string;
  content: string;
  sender_type: "user" | "agent" | "ai";
  timestamp: string;
}

export interface StatusChangeEvent {
  account_id: string;
  conversation_id: string;
  old_status: string;
  new_status: string;
}

export interface HandoverEvent {
  account_id: string;
  conversation_id: string;
  mode: string;
  handover_to?: string;
}

type SseEventMap = {
  new_message: NewMessageEvent;
  status_change: StatusChangeEvent;
  handover: HandoverEvent;
};

type SseEventName = keyof SseEventMap;

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------

const resolvedApiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  (import.meta.env.DEV ? "http://localhost:8000" : "");

/** 指数退避延迟计算，单位 ms */
function backoffDelay(attempt: number): number {
  const delay = Math.min(1000 * 2 ** attempt, 30_000);
  // 加入随机抖动 ±25%
  return delay + Math.floor(Math.random() * delay * 0.5 - delay * 0.25);
}

// ---------------------------------------------------------------------------
// ChatRealtimeService
// ---------------------------------------------------------------------------

export class ChatRealtimeService {
  // SSE
  private eventSource: EventSource | null = null;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;

  // Polling fallback
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private pollSince: string | null = null;
  private usePolling = false;

  // 认证
  private token: string | null = null;
  private currentUser: { id: string; role: string; display_name: string } | null = null;

  // 事件回调
  private handlers: Map<SseEventName, Array<(event: SseEventMap[SseEventName]) => void>> = new Map();

  // -----------------------------------------------------------------------
  // 公共方法
  // -----------------------------------------------------------------------

  connect(token: string): void {
    this.token = token;
    this.shouldReconnect = true;
    this.reconnectAttempt = 0;
    this.pollSince = null;

    // 缓存当前用户信息，确保轮询时始终可用
    const user = adminAuth.getCurrentUser();
    this.currentUser = user ? { id: user.id, role: user.role, display_name: user.display_name } : null;

    // 先关闭旧连接
    this.disconnectInternal();

    this.tryConnect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.disconnectInternal();
  }

  onMessage(callback: (msg: NewMessageEvent) => void): void {
    this.registerHandler("new_message", callback as (e: SseEventMap["new_message"]) => void);
  }

  onStatusChange(callback: (event: StatusChangeEvent) => void): void {
    this.registerHandler("status_change", callback as (e: SseEventMap["status_change"]) => void);
  }

  onHandover(callback: (event: HandoverEvent) => void): void {
    this.registerHandler("handover", callback as (e: SseEventMap["handover"]) => void);
  }

  // -----------------------------------------------------------------------
  // 内部
  // -----------------------------------------------------------------------

  private registerHandler<K extends SseEventName>(
    name: K,
    callback: (event: SseEventMap[K]) => void,
  ): void {
    const list = this.handlers.get(name) ?? [];
    list.push(callback as (event: SseEventMap[SseEventName]) => void);
    this.handlers.set(name, list);
  }

  private dispatch<K extends SseEventName>(name: K, data: SseEventMap[K]): void {
    const list = this.handlers.get(name);
    if (list) {
      list.forEach((cb) => cb(data as SseEventMap[SseEventName]));
    }
  }

  private disconnectInternal(): void {
    // 清除 SSE
    if (this.eventSource) {
      this.eventSource.onopen = null;
      this.eventSource.onerror = null;
      this.eventSource.onmessage = null;
      this.eventSource.close();
      this.eventSource = null;
    }

    // 清除重连定时器
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    // 清除轮询
    this.stopPolling();

    // 清除用户缓存
    this.currentUser = null;
  }

  // -----------------------------------------------------------------------
  // 连接策略
  // -----------------------------------------------------------------------

  private tryConnect(): void {
    if (!this.shouldReconnect) return;

    // 尝试 SSE
    this.connectSse();
  }

  private connectSse(): void {
    if (!this.token) return;

    const url = `${resolvedApiBaseUrl}/api/conversations/stream?token=${encodeURIComponent(this.token)}`;

    try {
      const es = new EventSource(url);
      this.eventSource = es;

      es.onopen = () => {
        // SSE 连接成功 —— 放弃轮询
        this.reconnectAttempt = 0;
        this.usePolling = false;
        this.stopPolling();
      };

      es.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data);
          this.handleSseMessage(parsed);
        } catch {
          // 忽略无法解析的消息
        }
      };

      es.addEventListener("new_message", (event: Event) => {
        this.handleNamedSseEvent("new_message", event as MessageEvent);
      });

      es.addEventListener("status_change", (event: Event) => {
        this.handleNamedSseEvent("status_change", event as MessageEvent);
      });

      es.addEventListener("handover", (event: Event) => {
        this.handleNamedSseEvent("handover", event as MessageEvent);
      });

      es.onerror = () => {
        es.close();
        this.eventSource = null;

        if (!this.shouldReconnect) return;

        // SSE 不可用 → 降级为轮询
        if (!this.usePolling) {
          this.usePolling = true;
          this.startPolling();
        }

        // 尝试重连 SSE
        this.scheduleReconnect();
      };
    } catch {
      // 创建 EventSource 失败 → 直接降级轮询
      this.eventSource = null;
      if (!this.usePolling && this.shouldReconnect) {
        this.usePolling = true;
        this.startPolling();
      }
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = backoffDelay(this.reconnectAttempt);
    this.reconnectAttempt += 1;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connectSse();
    }, delay);
  }

  private handleSseMessage(parsed: Record<string, unknown>): void {
    const eventType = parsed.event as string | undefined;
    if (!eventType) return;

    switch (eventType) {
      case "new_message":
        this.dispatch("new_message", parsed as unknown as NewMessageEvent);
        break;
      case "status_change":
        this.dispatch("status_change", parsed as unknown as StatusChangeEvent);
        break;
      case "handover":
        this.dispatch("handover", parsed as unknown as HandoverEvent);
        break;
      default:
        break;
    }
  }

  private handleNamedSseEvent(name: SseEventName, event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as SseEventMap[typeof name];
      this.dispatch(name, data);
    } catch {
      // 忽略无法解析的消息
    }
  }

  // -----------------------------------------------------------------------
  // 轮询降级
  // -----------------------------------------------------------------------

  private startPolling(): void {
    if (this.pollTimer !== null) return;

    this.pollTimer = setInterval(() => {
      this.poll();
    }, 5000);

    // 立即执行一次
    this.poll();
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private async poll(): Promise<void> {
    if (!this.token) return;

    const since = this.pollSince ?? new Date().toISOString();
    const url = `${resolvedApiBaseUrl}/api/conversations/poll?since=${encodeURIComponent(since)}`;

    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
    };
    if (this.currentUser) {
      headers["X-Actor-Id"] = this.currentUser.id;
      headers["X-Actor-Role"] = this.currentUser.role;
      headers["X-Actor-Name"] = this.currentUser.display_name;
    }

    try {
      const response = await fetch(url, { headers });

      if (!response.ok) return;

      const data = (await response.json()) as {
        events?: Array<{
          event: string;
          data: Record<string, unknown>;
        }>;
      };

      if (data.events && Array.isArray(data.events)) {
        for (const entry of data.events) {
          // entry already contains {event, account_id, conversation_id, ...}
          this.handleSseMessage(entry as Record<string, unknown>);
        }
      }

      // 推进游标到当前时间，下次轮询只查新事件
      this.pollSince = new Date().toISOString();
    } catch {
      // 轮询失败，下次再试
    }
  }
}

export const chatRealtime = new ChatRealtimeService();

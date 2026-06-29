import { adminAuth } from "./adminAuth";
import {
  normalizeTaskMonitorAlertEventResponse,
  type TaskMonitorAlertEvent,
} from "./api";
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";

const resolvedApiBaseUrl = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL as string | undefined,
  import.meta.env.DEV,
);

type StreamOptions = {
  accountId?: string;
  status?: string;
  onSnapshot: (events: TaskMonitorAlertEvent[]) => void;
  onError?: (error: Error) => void;
  reconnectDelayMs?: number;
  reconnectOnClose?: boolean;
};

function buildStreamUrl(accountId?: string, status?: string): string {
  const params = new URLSearchParams();
  if (accountId) {
    params.set("account_id", accountId);
  }
  if (status) {
    params.set("status", status);
  }
  const query = params.toString();
  return `${resolvedApiBaseUrl}/api/tasks/monitor/alerts/stream${query ? `?${query}` : ""}`;
}

function buildStreamHeaders(): HeadersInit {
  const headers = new Headers();
  const accessToken = adminAuth.getAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const userType = adminAuth.getUserType();
  if (userType) {
    headers.set("X-Actor-Type", userType);
  }
  const currentUser = adminAuth.getCurrentUser();
  if (currentUser) {
    headers.set("X-Actor-Id", currentUser.id);
    headers.set("X-Actor-Role", currentUser.role);
    headers.set("X-Actor-Name", currentUser.display_name);
  }
  return headers;
}

export class TaskMonitorAlertRealtimeService {
  private abortController: AbortController | null = null;

  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private currentOptions: StreamOptions | null = null;

  private shouldReconnect = false;

  connect(options: StreamOptions): void {
    this.disconnect();
    this.currentOptions = options;
    this.shouldReconnect = true;
    void this.openStream();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private async openStream(): Promise<void> {
    if (!this.currentOptions) {
      return;
    }
    this.abortController = new AbortController();
    try {
      const response = await fetch(
        buildStreamUrl(this.currentOptions.accountId, this.currentOptions.status),
        {
          method: "GET",
          headers: buildStreamHeaders(),
          signal: this.abortController.signal,
        },
      );
      if (!response.ok || !response.body) {
        throw new Error(`Task monitor stream failed with HTTP ${response.status}`);
      }
      await this.consumeStream(response.body, this.currentOptions.onSnapshot);
      if (this.shouldReconnect && this.currentOptions.reconnectOnClose !== false) {
        this.scheduleReconnect();
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        return;
      }
      this.currentOptions?.onError?.(
        error instanceof Error ? error : new Error("Task monitor realtime connection failed"),
      );
      if (this.shouldReconnect && this.currentOptions?.reconnectOnClose !== false) {
        this.scheduleReconnect();
      }
    }
  }

  private scheduleReconnect(): void {
    if (!this.currentOptions || this.reconnectTimer !== null) {
      return;
    }
    const delayMs = this.currentOptions.reconnectDelayMs ?? 3000;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) {
        void this.openStream();
      }
    }, delayMs);
  }

  private async consumeStream(
    stream: ReadableStream<Uint8Array>,
    onSnapshot: (events: TaskMonitorAlertEvent[]) => void,
  ): Promise<void> {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const parsed = this.parseFrame(frame);
        if (parsed?.event === "snapshot" && Array.isArray(parsed.data)) {
          onSnapshot(
            parsed.data.map((item) =>
              normalizeTaskMonitorAlertEventResponse(item as never),
            ),
          );
        }
      }
    }
  }

  private parseFrame(frame: string): { event: string; data: unknown } | null {
    const lines = frame
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0 && !line.startsWith(":"));
    if (lines.length === 0) {
      return null;
    }
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trim());
      }
    }
    if (dataLines.length === 0) {
      return null;
    }
    return {
      event: eventName,
      data: JSON.parse(dataLines.join("\n")),
    };
  }
}

export const taskMonitorAlertRealtime = new TaskMonitorAlertRealtimeService();

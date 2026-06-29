import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TaskMonitorAlertRealtimeService } from "./taskMonitorAlertRealtime";

vi.mock("./adminAuth", () => ({
  adminAuth: {
    getAccessToken: () => "token-1",
    getUserType: () => "super_admin",
    getCurrentUser: () => ({
      id: "admin-1",
      role: "super_admin",
      display_name: "Admin 1",
    }),
  },
}));

function createStreamResponse(body: string): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(body));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("TaskMonitorAlertRealtimeService", () => {
  let service: TaskMonitorAlertRealtimeService;

  beforeEach(() => {
    service = new TaskMonitorAlertRealtimeService();
  });

  afterEach(() => {
    service.disconnect();
    vi.restoreAllMocks();
  });

  it("parses snapshot events from the task monitor alert stream", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createStreamResponse(
        'event: snapshot\ndata: [{"id":"evt-1","accountId":"acct-1","alertRuleId":"rule-1","packageId":"pkg-1","userId":"user-1","publicUserId":"pub-u1","status":"open","priority":"high","ruleName":"High Amount","currentValue":150,"thresholdValue":130,"soundEnabled":true,"triggeredAt":"2026-06-24T00:00:00Z","acknowledgedAt":null,"acknowledgedBy":null,"resolvedAt":null,"resolvedBy":null}]\n\n',
      ),
    );
    const onSnapshot = vi.fn();

    service.connect({
      accountId: "acct-1",
      onSnapshot,
      reconnectOnClose: false,
    });

    await Promise.resolve();
    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalled();
    expect(onSnapshot).toHaveBeenCalledWith([
      expect.objectContaining({
        id: "evt-1",
        account_id: "acct-1",
        package_id: "pkg-1",
        rule_name: "High Amount",
        current_value: 150,
      }),
    ]);
  });

  it("reports stream failures to the error callback", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));
    const onError = vi.fn();

    service.connect({
      accountId: "acct-1",
      onSnapshot: vi.fn(),
      onError,
      reconnectOnClose: false,
    });

    await Promise.resolve();
    await Promise.resolve();

    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "network down" }));
  });
});

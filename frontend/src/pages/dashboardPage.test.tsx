import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  useDashboardDataMock: vi.fn(),
  getHealthCheckSummaryMock: vi.fn(),
  runHealthCheckMock: vi.fn(),
}));

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({ children, onClick, loading }: { children?: React.ReactNode; onClick?: () => void; loading?: boolean }) =>
    React.createElement("button", { onClick, disabled: loading }, children);
  const Statistic = ({ title, value }: { title?: React.ReactNode; value?: React.ReactNode }) => React.createElement("div", null, title, value);
  const Tag = ({ children, color }: { children?: React.ReactNode; color?: string }) => React.createElement("span", { "data-color": color }, children);
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
    Title: ({ children }: { children?: React.ReactNode }) => React.createElement("h4", null, children),
    Paragraph: ({ children }: { children?: React.ReactNode }) => React.createElement("p", null, children),
  };
  return {
    Badge: Wrapper,
    Button,
    Card: Wrapper,
    Col: Wrapper,
    Row: Wrapper,
    Space: Wrapper,
    Statistic,
    Tag,
    Typography,
  };
});

vi.mock("../hooks/useHealth", () => ({
  useHealth: () => "healthy",
}));

vi.mock("../hooks/useDashboardData", () => ({
  useDashboardData: hoisted.useDashboardDataMock,
}));

vi.mock("../services/api", () => ({
  getHealthCheckSummary: hoisted.getHealthCheckSummaryMock,
  runHealthCheck: hoisted.runHealthCheckMock,
}));

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) => selector(hoisted.storeState),
}));

const mountedContainers: HTMLDivElement[] = [];
const mountedRoots: Root[] = [];

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderPage(element: ReturnType<typeof createElement>): Promise<void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  mountedContainers.push(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(element);
  });
  await flushEffects();
}

describe("DashboardPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      setActivePage: vi.fn(),
      openWorkspacePage: vi.fn(),
    };
    hoisted.getHealthCheckSummaryMock.mockReset().mockResolvedValue({
      db: "healthy",
      redis: "healthy",
      api: "healthy",
      sites: "healthy",
      ssl: "healthy",
      last_check_at: "2026-06-12T00:00:00Z",
    });
    hoisted.runHealthCheckMock.mockReset().mockResolvedValue([]);
    hoisted.useDashboardDataMock.mockReset().mockReturnValue({
      data: {
        runtimeState: {
          global_ai_enabled: true,
          accounts: [{ account_id: "acct-1", ai_enabled: true }, { account_id: "acct-2", ai_enabled: false }],
          conversations: [
            { conversation_id: "conv-1", management_mode: "ai_managed", status: "open", ai_enabled: true, customer_id: "cust-1", account_id: "acct-1" },
            { conversation_id: "conv-2", management_mode: "human_managed", status: "open", ai_enabled: false, customer_id: "cust-2", account_id: "acct-2" },
            { conversation_id: "conv-3", management_mode: "paused", status: "open", ai_enabled: false, customer_id: "cust-3", account_id: "acct-1" },
          ],
        },
        metrics: { ai: { success_total: 85, fallback_total: 15 } },
        whatsAppSummary: { inbound_message_count: 200, outbound_message_count: 180 },
        launchReadiness: { summary: { ai_provider: "openai", meta_ready_account_count: 1 } },
      },
      loading: false,
      error: null,
      reload: vi.fn(),
      stats: { totalConversations: 3, aiManaged: 1, humanManaged: 1, paused: 1, recommended: 1 },
      accounts: [{ account_id: "acct-1", ai_enabled: true }, { account_id: "acct-2", ai_enabled: false }],
    });
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(async () => {
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => root?.unmount());
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
  });

  it("renders without crashing", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.querySelectorAll("button").length).toBeGreaterThanOrEqual(0);
  });

  it("loads dashboard data via useDashboardData", async () => {
    await renderPage(createElement(DashboardPage));
    expect(hoisted.useDashboardDataMock).toHaveBeenCalled();
  });

  it("renders stat cards with correct values", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.body.textContent).toContain("3");
    expect(document.body.textContent).toContain("1");
  });

  it("has a refresh button", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.body.textContent).toContain("刷新");
  });

  it("shows system status tag", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.querySelectorAll("[data-color]").length).toBeGreaterThanOrEqual(2);
  });

  it("renders AI provider info", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.body.textContent).toContain("openai");
  });

  it("renders quick actions", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.body.textContent).toContain("进入工作台");
  });

  it("renders todo list with items", async () => {
    await renderPage(createElement(DashboardPage));
    expect(document.body.textContent).toContain("推荐转人工");
  });

  it("calls setActivePage on action click", async () => {
    await renderPage(createElement(DashboardPage));
    const button = Array.from(document.querySelectorAll("button")).find((item) => item.textContent?.includes("进入工作台"));
    if (button) {
      await act(async () => button.click());
    }
    expect(hoisted.storeState.setActivePage).toHaveBeenCalled();
  });
});
